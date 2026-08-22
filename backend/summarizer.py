"""早期章节 → 背景摘要（DeepSeek 生成，结果缓存复用）。

对应方案 5.8「滑动窗口摘要」：早期章节压缩为全局背景摘要，避免长文本撑爆上下文。
无 key / 生成失败时返回空串，上层自动降级为「近期原文 + 关键词召回」。
"""
import llm


async def generate_summary(book_title: str, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    system = "你是一名资深小说内容编辑，擅长用简洁准确的语言概括长篇小说的情节脉络与人物关系。"
    user = (
        f"请用 300 字以内，概括《{book_title}》以下已读内容的核心剧情、主要人物关系与关键悬念。"
        f"严格只概括已提供的文本，不要延伸、不要剧透后续。\n\n【已读文本】\n{text}"
    )
    ok, reply = await llm.chat_deepseek(system, user)
    return reply if ok else ""
