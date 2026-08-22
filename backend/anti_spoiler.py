"""防剧透硬隔离 + 上下文构建（滑动窗口摘要 + 近期原文 + 关键词检索）。

这是「每次问答只基于当前阅读进度」的实现核心，对应方案 5.8：

1. 硬隔离 —— 只允许 chapters[:progress+1] 进入上下文，之后的章节物理上不存在，
   从根上杜绝剧透（不依赖 prompt 自觉）。
2. 滑动窗口摘要 —— 早期章节压成 300 字背景摘要（缓存复用），避免长文本撑爆上下文。
3. 近期原文 —— 最近 3 章保留原文，保证「当前场景」细节准确。
4. 关键词检索 —— 对早期章节做中文 2-gram 匹配，召回与提问相关的片段，
   弥补摘要丢掉的细节（如读者问到早期某个伏笔）。

生产版：早期摘要 → 增量摘要 + 向量库；关键词检索 → embedding 语义检索。
"""
import retrieval
import store
import summarizer

RECENT_CHAPTERS = 3
CHAPTER_SNIPPET_CHARS = 2000
MAX_CONTEXT_CHARS = 8000
SUMMARY_STALE_TOLERANCE = 2  # 早期窗口增长 <=2 章时不重生成摘要


async def build_context(book: dict, progress_chapter: int, question: str) -> str:
    """构建注入给 LLM 的「已读上下文」（已硬隔离，绝不包含进度之后的内容）。"""
    chapters = book.get("chapters", [])
    if not chapters:
        return ""

    progress = max(0, min(progress_chapter, len(chapters) - 1))
    allowed = chapters[: progress + 1]  # 硬隔离边界

    early = allowed[:-RECENT_CHAPTERS] if len(allowed) > RECENT_CHAPTERS else []
    recent = allowed[-RECENT_CHAPTERS:]

    parts = []

    # 1) 背景摘要（早期章节）
    if early:
        summary = await _summary(book, early)
        if summary:
            parts.append(f"【全书背景摘要（前 {len(early)} 章）】\n{summary}")

    # 2) 关键词召回（在早期章节里找与提问相关的片段）
    if early:
        retrieved = retrieval.keyword_retrieve(early, question)
        if retrieved:
            parts.append("【与提问相关的早期情节片段】\n" + "\n---\n".join(retrieved))

    # 3) 近期原文
    recent_text = "\n\n".join(
        f"第{ch['index'] + 1}章 {ch['title']}：\n{ch['content'][:CHAPTER_SNIPPET_CHARS]}"
        for ch in recent
    )
    parts.append(f"【近期章节原文（截止第 {progress + 1} 章）】\n{recent_text}")

    return "\n\n".join(parts)[-MAX_CONTEXT_CHARS:]


async def _summary(book: dict, early: list) -> str:
    """生成/复用早期章节背景摘要，结果缓存到 book JSON。"""
    cache = book.get("summary") or {}
    up_to = len(early)

    cached_up_to = cache.get("up_to")
    if cached_up_to is not None and cache.get("text"):
        # 早期窗口只涨了几章，复用旧摘要，避免每翻一章就重生成
        if up_to <= cached_up_to + SUMMARY_STALE_TOLERANCE:
            return cache["text"]

    text = "".join(ch["content"][:1500] for ch in early[:40])
    summary = await summarizer.generate_summary(book.get("title", ""), text)
    if summary:
        book["summary"] = {"up_to": up_to, "text": summary}
        store.save_book(book)
    return summary
