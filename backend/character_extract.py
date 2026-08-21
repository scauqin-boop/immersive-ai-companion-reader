"""人物抽取：用 DeepSeek 从开篇提取主要人物，失败则返回空（由用户手动添加）。

返回 [{name, description, first_appearance}]，first_appearance 为 0-based 章序号。
"""
import json
import re

import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = DEEPSEEK_MODEL
API_KEY = DEEPSEEK_API_KEY

_EXTRACT_PROMPT = """请从下面的小说文本中提取主要人物（最多 8 个）。
对每个人物，给出：姓名、一句话人物介绍（含身份/性格）、首次出现的章序号（0-based，未明确则填 0）。
只输出一个 JSON 数组，格式：[{{"name":"叶文洁","description":"...","first_appearance":0}}]
不要输出任何多余文字或解释。

【小说文本】
{text}
"""


async def extract_characters(text: str, api_key: str = None) -> list:
    key = api_key or API_KEY
    if not key:
        return []

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
                        {"role": "user", "content": _EXTRACT_PROMPT.format(text=text[:6000])}
                    ],
                    "temperature": 0.2,
                },
            )
        if resp.status_code != 200:
            return []
        content = resp.json()["choices"][0]["message"]["content"]
        m = re.search(r"\[.*\]", content, re.DOTALL)
        arr = json.loads(m.group(0) if m else content)
        return [
            {
                "name": str(c.get("name", "")).strip(),
                "description": str(c.get("description", "")).strip(),
                "first_appearance": int(c.get("first_appearance", 0)),
            }
            for c in arr
            if c.get("name")
        ]
    except Exception:
        return []
