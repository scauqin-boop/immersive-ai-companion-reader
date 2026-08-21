"""DeepSeek 调用 + mock 降级兜底。

真实 API 不可用（无 key / 网络失败 / 非 200）时，返回示例回复，
保证面试现场断网或无 key 也能完整演示交互流程。
"""
import random

import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = DEEPSEEK_MODEL
API_KEY = DEEPSEEK_API_KEY

# mock 兜底回复（无 key / 断网时展示交互链路用）
_MOCK = [
    "（示例·降级回复）我此刻心里翻涌着很多话，却不知从何说起……你既然问到这里，我或许该让你看清眼前这一步。",
    "（示例·降级回复）这件事说来话长。我只能说，我看到的、我做的，都有我不得不做的理由。",
    "（示例·降级回复）你问我的这一点，恰恰是我一直放不下的地方。",
]


async def chat_deepseek(system: str, user: str, api_key: str = None) -> tuple:
    """返回 (ok: bool, reply: str)。ok=False 表示走的是 mock 兜底。"""
    key = api_key or API_KEY
    if not key:
        return False, _mock_reply()

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 300,
                },
            )
        if resp.status_code != 200:
            return False, _mock_reply()
        data = resp.json()
        return True, data["choices"][0]["message"]["content"].strip()
    except Exception:
        return False, _mock_reply()


def _mock_reply() -> str:
    return random.choice(_MOCK)
