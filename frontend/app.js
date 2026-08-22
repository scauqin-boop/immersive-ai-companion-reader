/* AI 伴读 · 通用阅读器 前端逻辑 */
const PAGE_CHARS = 900; // 每页字符数（翻页粒度）

const SETTINGS_KEY = 'ai-reader-settings';
const PROGRESS_KEY = 'ai-reader-progress';

const state = {
  book: null,        // 当前书籍完整对象
  pages: [],         // [{chapter, chapterTitle, text}]
  pageIndex: 0,
  chapterStart: {},  // chapter index -> 该章第一页的 pageIndex（目录跳章用）
  currentCharacter: null,
  history: [],       // 同进度多轮历史 [{role, content}]，换章/换人物即清空
  anchorChapter: null, // 当前对话锚定的章节（跨章/换人物即重置，防剧透）
};

const settings = loadSettings();

const $ = (id) => document.getElementById(id);

/* ---------- 初始化 ---------- */
async function init() {
  bindEvents();
  applySettings();
  await loadBooks();
  // 恢复上次阅读的书籍与进度
  const progress = loadProgressAll();
  if (progress._last) {
    $('bookSelect').value = progress._last;
    loadBook(progress._last);
  }
}
init();

function bindEvents() {
  $('importBtn').addEventListener('click', () => $('fileInput').click());
  $('fileInput').addEventListener('change', (e) => {
    if (e.target.files[0]) importFile(e.target.files[0]);
  });
  $('bookSelect').addEventListener('change', (e) => {
    if (e.target.value) loadBook(e.target.value);
  });
  $('prevPage').addEventListener('click', () => flip(-1));
  $('nextPage').addEventListener('click', () => flip(1));
  $('sendBtn').addEventListener('click', sendChat);
  $('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendChat();
  });
  $('addCharBtn').addEventListener('click', () => {
    $('addCharForm').hidden = !$('addCharForm').hidden;
  });
  $('saveCharBtn').addEventListener('click', addCharacter);
  $('interpretClose').addEventListener('click', () => ($('interpretPop').hidden = true));

  // 目录
  $('tocBtn').addEventListener('click', openToc);
  $('tocClose').addEventListener('click', closeToc);
  $('tocOverlay').addEventListener('click', (e) => {
    if (e.target === $('tocOverlay')) closeToc();
  });

  // 字号 / 主题
  $('fontDec').addEventListener('click', () => changeFont(-1));
  $('fontInc').addEventListener('click', () => changeFont(1));
  $('themeBtn').addEventListener('click', toggleTheme);

  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'ArrowLeft') flip(-1);
    if (e.key === 'ArrowRight') flip(1);
    if (e.key === 'Escape') closeToc();
  });
  // 划选文字 → 浮出「解读」
  $('pageText').addEventListener('mouseup', onTextSelection);
  document.addEventListener('mousedown', (e) => {
    if (!$('interpretPop').contains(e.target)) $('interpretPop').hidden = true;
  });
}

/* ---------- 书库 ---------- */
async function loadBooks() {
  const books = await fetchJSON('/api/books');
  const sel = $('bookSelect');
  sel.innerHTML = '<option value="">选择一本书…</option>';
  books.forEach((b) => {
    const opt = document.createElement('option');
    opt.value = b.id;
    opt.textContent = `${b.title}（${b.chapter_count}章）`;
    sel.appendChild(opt);
  });
}

async function importFile(file) {
  const form = new FormData();
  form.append('file', file);
  setImportBusy(true);
  try {
    const book = await fetchJSON('/api/books/import', { method: 'POST', body: form });
    await loadBooks();
    $('bookSelect').value = book.id;
    loadBook(book.id);
  } catch (err) {
    alert('导入失败：' + err.message);
  } finally {
    setImportBusy(false);
  }
}

function setImportBusy(busy) {
  $('importBtn').textContent = busy ? '导入中…' : '导入小说';
  $('importBtn').disabled = busy;
}

/* ---------- 书籍加载与翻页 ---------- */
async function loadBook(id) {
  const book = await fetchJSON('/api/books/' + id);
  state.book = book;
  state.currentCharacter = null;
  state.history = [];
  state.anchorChapter = null;
  buildPages(book);
  const saved = loadProgressAll()[id];
  state.pageIndex = (typeof saved === 'number' && saved < state.pages.length) ? saved : 0;
  renderPage();
  renderCharacters();
  renderTOC();
  resetChat();
  saveProgress();
}

function buildPages(book) {
  const pages = [];
  const chapterStart = {};
  book.chapters.forEach((ch) => {
    const text = ch.content.trim();
    if (!text) return;
    chapterStart[ch.index] = pages.length;
    for (let i = 0; i < text.length; i += PAGE_CHARS) {
      pages.push({
        chapter: ch.index,
        chapterTitle: ch.title,
        text: text.slice(i, i + PAGE_CHARS),
      });
    }
  });
  state.chapterStart = chapterStart;
  state.pages = pages.length ? pages : [{ chapter: 0, chapterTitle: '—', text: '（无内容）' }];
}

function currentChapter() {
  return state.pages[state.pageIndex].chapter;
}

function renderPage() {
  const p = state.pages[state.pageIndex];
  $('pageText').textContent = p.text;
  $('chapterLabel').textContent = `第${p.chapter + 1}章 · ${p.chapterTitle}`;
  $('pageIndicator').textContent = `${state.pageIndex + 1} / ${state.pages.length}`;
  $('progressLabel').textContent = `已读进度锚定：截止第 ${p.chapter + 1} 章`;
  $('progressBadge').textContent = `第 ${p.chapter + 1} 章`;
  renderCharacters(); // 进度变化会改变人物锁定状态
  updateTocHighlight();
}

function flip(delta) {
  const next = state.pageIndex + delta;
  if (next < 0 || next >= state.pages.length) return;
  const oldChapter = currentChapter();
  state.pageIndex = next;
  if (currentChapter() !== oldChapter) {
    resetConversation(); // 进度锚点变化 → 清空历史，跨章不继承记忆（防剧透）
  }
  renderPage();
  saveProgress();
}

/* 重置当前对话：清空历史并重新锚定到当前章节 */
function resetConversation() {
  state.history = [];
  state.anchorChapter = currentChapter();
  resetChat();
}

/* ---------- 阅读进度持久化 ---------- */
function loadProgressAll() {
  try { return JSON.parse(localStorage.getItem(PROGRESS_KEY)) || {}; }
  catch (_) { return {}; }
}

function saveProgress() {
  if (!state.book) return;
  try {
    const all = loadProgressAll();
    all[state.book.id] = state.pageIndex;
    all._last = state.book.id;
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(all));
  } catch (_) {}
}

/* ---------- 章节目录 ---------- */
function renderTOC() {
  const list = $('tocList');
  list.innerHTML = '';
  const chapters = state.book?.chapters || [];
  const cur = currentChapter();
  chapters.forEach((ch) => {
    const item = document.createElement('div');
    item.className = 'toc-item' + (ch.index === cur ? ' current' : '');
    const idx = document.createElement('span');
    idx.className = 'toc-idx';
    idx.textContent = `第${ch.index + 1}章`;
    const title = document.createElement('span');
    title.className = 'toc-title';
    title.textContent = ch.title;
    item.appendChild(idx);
    item.appendChild(title);
    item.addEventListener('click', () => jumpToChapter(ch.index));
    list.appendChild(item);
  });
  const curEl = list.querySelector('.toc-item.current');
  if (curEl) curEl.scrollIntoView({ block: 'center' });
}

function updateTocHighlight() {
  const cur = currentChapter();
  $('tocList').querySelectorAll('.toc-item').forEach((el, i) => {
    el.classList.toggle('current', i === cur);
  });
}

function jumpToChapter(index) {
  const start = state.chapterStart[index];
  if (typeof start !== 'number') return;
  state.pageIndex = start;
  renderPage();
  saveProgress();
  closeToc();
}

function openToc() {
  $('tocOverlay').hidden = false;
  renderTOC();
}

function closeToc() {
  $('tocOverlay').hidden = true;
}

/* ---------- 字号 / 主题 ---------- */
function loadSettings() {
  try { return JSON.parse(localStorage.getItem(SETTINGS_KEY)) || { fontSize: 17, theme: 'light' }; }
  catch (_) { return { fontSize: 17, theme: 'light' }; }
}

function saveSettings() {
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch (_) {}
}

function applySettings() {
  document.documentElement.style.setProperty('--reader-font-size', settings.fontSize + 'px');
  document.body.dataset.theme = settings.theme;
  $('themeBtn').textContent = settings.theme === 'dark' ? '日间' : '夜间';
  $('fontSizeLabel').textContent = settings.fontSize;
}

function changeFont(delta) {
  settings.fontSize = Math.min(24, Math.max(14, settings.fontSize + delta));
  saveSettings();
  applySettings();
}

function toggleTheme() {
  settings.theme = settings.theme === 'dark' ? 'light' : 'dark';
  saveSettings();
  applySettings();
}

/* ---------- 人物 ---------- */
function renderCharacters() {
  const box = $('charList');
  box.innerHTML = '';
  const chars = state.book?.characters || [];
  const chapter = currentChapter();

  chars.forEach((c) => {
    const chip = document.createElement('div');
    chip.className = 'char-chip';
    const locked = c.first_appearance > chapter;
    if (locked) {
      chip.classList.add('locked');
      chip.textContent = `${c.name}（未出场）`;
      chip.title = c.description || '';
    } else {
      chip.textContent = c.name;
      chip.title = c.description || '';
      if (c.name === state.currentCharacter) chip.classList.add('active');
      chip.addEventListener('click', () => selectCharacter(c.name));
    }
    box.appendChild(chip);
  });

  const canChat = !!state.currentCharacter;
  $('chatInput').disabled = !canChat;
  $('sendBtn').disabled = !canChat;
  if (!canChat && chars.length) $('chatEmpty').textContent = '选中一个人物，问问 TA 此刻的想法。';
}

function selectCharacter(name) {
  state.currentCharacter = name;
  resetConversation();
  renderCharacters();
}

async function addCharacter() {
  const name = $('charName').value.trim();
  const desc = $('charDesc').value.trim();
  if (!name) return;
  const book = await fetchJSON(`/api/books/${state.book.id}/characters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description: desc, first_appearance: currentChapter() }),
  });
  state.book = book;
  $('charName').value = '';
  $('charDesc').value = '';
  $('addCharForm').hidden = true;
  renderCharacters();
}

/* ---------- 对话 ---------- */
function resetChat() {
  $('chat').innerHTML = '';
  const empty = document.createElement('div');
  empty.className = 'chat-empty';
  empty.id = 'chatEmpty';
  empty.textContent = state.currentCharacter
    ? `和 ${state.currentCharacter} 聊聊 TA 此刻的想法吧。`
    : '选中一个人物，问问 TA 此刻的想法。';
  $('chat').appendChild(empty);
}

const MAX_HISTORY = 8; // 最多保留最近 8 条消息（4 轮问答），避免历史无限增长

async function sendChat() {
  const input = $('chatInput');
  const message = input.value.trim();
  if (!message || !state.currentCharacter || !state.book) return;

  const chapter = currentChapter();
  if (chapter !== state.anchorChapter) resetConversation(); // 兜底：锚点变化则重开

  input.value = '';
  appendMessage('user', message, '你');
  appendMessage('ai', '…', state.currentCharacter, true);

  const history = state.history.slice(); // 发送前快照（不含本条）
  try {
    const data = await fetchJSON('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: state.book.id,
        character: state.currentCharacter,
        progress_chapter: chapter,
        message,
        history,
      }),
    });
    replaceLastAi(data.reply, state.currentCharacter, data.ok);
    state.history.push({ role: 'user', content: message });
    state.history.push({ role: 'assistant', content: data.reply });
    if (state.history.length > MAX_HISTORY) {
      state.history = state.history.slice(-MAX_HISTORY);
    }
  } catch (err) {
    replaceLastAi('出错了：' + err.message, state.currentCharacter, false);
  }
}

function appendMessage(role, text, tag, pending = false) {
  const empty = $('chatEmpty');
  if (empty) empty.remove();

  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const t = document.createElement('span');
  t.className = 'tag';
  t.textContent = tag;
  const body = document.createElement('span');
  body.textContent = text;
  div.appendChild(t);
  div.appendChild(body);
  if (pending) div.dataset.pending = '1';
  $('chat').appendChild(div);
  $('chat').scrollTop = $('chat').scrollHeight;
  return div;
}

function replaceLastAi(text, tag, ok) {
  const msgs = $('chat').querySelectorAll('.msg.ai');
  const last = msgs[msgs.length - 1];
  if (!last) return;
  last.querySelector('span:last-child').textContent = text;
  last.querySelector('.tag').textContent = ok ? tag : `${tag} · 降级演示`;
  $('chat').scrollTop = $('chat').scrollHeight;
}

/* ---------- 划选解读 ---------- */
function onTextSelection() {
  const sel = window.getSelection();
  const text = sel.toString().trim();
  if (!text || !state.book) return;

  const rect = sel.getRangeAt(0).getBoundingClientRect();
  const pop = $('interpretPop');
  pop.hidden = false;
  pop.style.left = Math.min(rect.left, window.innerWidth - 340) + 'px';
  pop.style.top = (rect.bottom + 8) + 'px';
  $('interpretBody').textContent = '解读中…';

  const chapter = currentChapter();
  const character = state.currentCharacter || firstUnlockedCharacter();
  if (!character) {
    $('interpretBody').textContent = '请先在右侧选中或添加一个人物。';
    return;
  }
  interpret(text, character, chapter);
}

function firstUnlockedCharacter() {
  const chapter = currentChapter();
  return (state.book?.characters || []).find((c) => c.first_appearance <= chapter)?.name || null;
}

async function interpret(text, character, chapter) {
  try {
    const data = await fetchJSON('/api/interpret', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_id: state.book.id,
        character,
        progress_chapter: chapter,
        text,
      }),
    });
    $('interpretBody').textContent = data.ok
      ? `【${character}】${data.reply}`
      : `【${character} · 降级演示】${data.reply}`;
  } catch (err) {
    $('interpretBody').textContent = '出错了：' + err.message;
  }
}

/* ---------- 工具 ---------- */
async function fetchJSON(url, opts = {}) {
  const resp = await fetch(url, opts);
  if (!resp.ok) {
    let msg = resp.status + '';
    try { msg = (await resp.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return resp.json();
}
