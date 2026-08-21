"""防剧透硬隔离：只把「已读进度及之前」的章节内容喂给模型。

对应方案 5.8 数据层「动态切片向量库」的 MVP 简化版：
- 生产版：全文本按章节切片入向量库，用户读到第 N 章，只开放前 N 章检索权限。
- demo 版：直接用章节索引做硬过滤，只拼接 chapters[:progress+1] 的内容，
  超出进度的章节物理上不进入上下文，从根源杜绝剧透。
"""

MAX_CONTEXT_CHARS = 6000


def build_context(chapters: list, progress_chapter: int) -> str:
    """构建已读内容上下文。progress_chapter 为 0-based 章序号，含本章。"""
    progress_chapter = max(0, min(progress_chapter, len(chapters) - 1))
    allowed = chapters[: progress_chapter + 1]  # 硬隔离：之后的章节完全不可见

    # 从最近章节往前补，直到接近上下文预算（对应方案「滑动窗口摘要」的朴素版）
    parts, total = [], 0
    for ch in reversed(allowed):
        snippet = f"【第{ch['index'] + 1}章 {ch['title']}】\n{ch['content'][:2000]}"
        parts.append(snippet)
        total += len(snippet)
        if total >= MAX_CONTEXT_CHARS:
            break
    parts.reverse()
    return "\n\n".join(parts)[-MAX_CONTEXT_CHARS:]
