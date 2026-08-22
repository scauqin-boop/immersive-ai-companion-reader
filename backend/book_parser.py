"""文本导入解析：txt（编码识别 + 章节切分）/ epub（spine 抽取）。

统一入口 parse_document()，根据扩展名分发；返回 (title, chapters)。
"""
import os
import re

import epub_parser

_CHAPTER_RE = re.compile(
    r"(第[零一二三四五六七八九十百千万0-9]+[章回卷节])|(Chapter\s+\d+)",
    re.IGNORECASE,
)

_FALLBACK_CHUNK_CHARS = 3000


def decode(raw: bytes) -> str:
    """按常见中文编码依次尝试解码，兜底忽略非法字节。"""
    for enc in ("utf-8", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def split_chapters(text: str) -> list:
    """按章节正则切分，匹配不到时退化为固定长度分块。返回 [{index, title, content}]。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(_CHAPTER_RE.finditer(text))
    if not matches:
        return _fallback_split(text)

    chapters = []
    for i, m in enumerate(matches):
        title = m.group(0).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            chapters.append({"index": len(chapters), "title": title, "content": content})
    return chapters


def _fallback_split(text: str) -> list:
    chunks = [text[i : i + _FALLBACK_CHUNK_CHARS] for i in range(0, len(text), _FALLBACK_CHUNK_CHARS)]
    return [
        {"index": i, "title": f"第{i + 1}节", "content": c.strip()}
        for i, c in enumerate(chunks)
        if c.strip()
    ]


def parse_document(filename: str, raw: bytes) -> tuple:
    """统一导入入口：epub 走 spine 解析，其余按 txt 处理。返回 (title, chapters)。"""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".epub":
        return epub_parser.parse_epub(raw)
    title = os.path.splitext(filename or "未命名")[0]
    return title, split_chapters(decode(raw))
