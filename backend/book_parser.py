"""文本导入与分章解析。

支持 txt 导入，自动识别编码，按章节标记切分，兜底按段落切块。
"""
import re

# 中文「第X章/回/卷/节」与英文「Chapter N」
_CHAPTER_RE = re.compile(
    r"(第[零一二三四五六七八九十百千万0-9]+[章回卷节])|(Chapter\s+\d+)",
    re.IGNORECASE,
)

_FALLBACK_CHUNK = 3000  # 兜底切块时每块字符数


def split_chapters(text: str) -> list:
    """把整本书文本切成章节列表，返回 [{index, title, content}]。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(_CHAPTER_RE.finditer(text))

    if len(matches) >= 1:
        raw = []  # [(title, content)]
        if matches[0].start() > 0 and text[: matches[0].start()].strip():
            raw.append(("开篇", text[: matches[0].start()].strip()))
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            seg = text[start:end].strip()
            title = seg.split("\n")[0].strip()[:40] or f"第{i + 1}章"
            raw.append((title, seg))
    else:
        raw = _fallback_split(text)

    return [
        {"index": i, "title": title, "content": content}
        for i, (title, content) in enumerate(raw)
        if content.strip()
    ]


def _fallback_split(text: str) -> list:
    """无章节标记时，按段落边界凑成 ~3000 字一块。"""
    paras = text.split("\n\n")
    raw, chunk, idx = [], "", 0
    for p in paras:
        if len(chunk) + len(p) > _FALLBACK_CHUNK and chunk:
            raw.append((f"第{idx + 1}部分", chunk))
            idx += 1
            chunk = ""
        chunk += p + "\n\n"
    if chunk.strip():
        raw.append((f"第{idx + 1}部分", chunk))
    return raw
