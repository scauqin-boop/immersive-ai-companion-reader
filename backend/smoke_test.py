"""冒烟测试：不依赖外部 API key，验证 导入 → 分章 → 防剧透 → 对话/解读 全链路。

运行：cd backend && python smoke_test.py
"""
from fastapi.testclient import TestClient

import anti_spoiler
import book_parser
import main

client = TestClient(main.app)
SAMPLE = "../sample/雾港_示例.txt"


def test_anti_spoiler():
    with open(SAMPLE, encoding="utf-8") as f:
        chapters = book_parser.split_chapters(f.read())
    assert len(chapters) == 3, f"期望 3 章，实际 {len(chapters)}"

    ctx0 = anti_spoiler.build_context(chapters, 0)  # 只读到第 1 章
    assert "苏辰" not in ctx0, "防剧透失败：进度=0 时泄露了第 2 章人物"
    assert "暗潮" not in ctx0, "防剧透失败：进度=0 时泄露了第 3 章内容"

    ctx2 = anti_spoiler.build_context(chapters, 2)  # 读到第 3 章
    assert "苏辰" in ctx2 and "暗潮" in ctx2, "进度=2 应包含全部已读内容"
    print("[OK] 防剧透硬隔离：进度=0 只含第1章，进度=2 含全部3章")


def test_import():
    with open(SAMPLE, "rb") as f:
        r = client.post("/api/books/import", files={"file": ("雾港_示例.txt", f, "text/plain")})
    assert r.status_code == 200, r.text
    book = r.json()
    assert len(book["chapters"]) == 3
    print(f"[OK] 导入《{book['title']}》 -> {len(book['chapters'])} 章, "
          f"人物={[c['name'] for c in book['characters']] or '（无 key，未自动抽取）'}")
    return book


def test_chat(book):
    r = client.post("/api/chat", json={
        "book_id": book["id"],
        "character": "林晚",
        "progress_chapter": 0,
        "message": "你现在在想什么？",
    })
    assert r.status_code == 200, r.text
    print(f"[OK] 对话(进度0, {'真实' if r.json()['ok'] else 'mock兜底'}) -> {r.json()['reply'][:40]}…")


def test_interpret(book):
    r = client.post("/api/interpret", json={
        "book_id": book["id"],
        "character": "林晚",
        "progress_chapter": 0,
        "text": "林晚站在渡口，把信纸又看了一遍。",
    })
    assert r.status_code == 200, r.text
    print(f"[OK] 划选解读 -> {r.json()['reply'][:40]}…")


if __name__ == "__main__":
    test_anti_spoiler()
    book = test_import()
    test_chat(book)
    test_interpret(book)
    print("\n✅ 全部冒烟测试通过")
