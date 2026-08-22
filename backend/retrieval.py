"""轻量关键词检索（中文 2-gram 匹配），召回与提问相关的已读片段。

为什么不用向量库：embedding + 向量库需要额外 API 与存储，demo 阶段先用
字符 n-gram 做「关键词召回」，验证召回机制本身。生产版替换为 embedding 语义检索
（可处理同义词），即方案 5.8 的 GraphRAG 检索层。
"""
import re

# 高频虚词：纯虚词组成的 2-gram 无检索价值，过滤掉
_STOP_CHARS = set("的了是在有和就不人都一说我要也他她它们你这那什么么怎为以个与及或等而于被把从")


def _grams(text: str) -> set:
    text = re.sub(r"[^一-龥]", "", text)
    grams = set()
    for i in range(len(text) - 1):
        g = text[i : i + 2]
        if g[0] in _STOP_CHARS and g[1] in _STOP_CHARS:
            continue
        grams.add(g)
    return grams


def keyword_retrieve(chapters: list, question: str, top_k: int = 2, chunk_chars: int = 600) -> list:
    """在 chapters（已读、已硬隔离）中召回与 question 相关的片段，返回 Top-K 字符串。"""
    qgrams = _grams(question)
    if not qgrams:
        return []

    scored = []
    for ch in chapters:
        content = ch["content"]
        for i in range(0, len(content), chunk_chars):
            chunk = content[i : i + chunk_chars]
            overlap = len(qgrams & _grams(chunk))
            if overlap:
                scored.append((overlap, ch["index"], chunk))

    scored.sort(key=lambda x: -x[0])
    seen, result = set(), []
    for _, idx, chunk in scored:
        if idx in seen:
            continue
        seen.add(idx)
        result.append(f"（第{idx + 1}章）{chunk}")
        if len(result) >= top_k:
            break
    return result
