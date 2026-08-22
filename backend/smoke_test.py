"""冒烟测试：不依赖外部 API key，验证 导入(txt/epub) → 分章 → 防剧透 → 对话/解读 全链路。

运行：cd backend && python smoke_test.py
"""
import asyncio
import io
import zipfile

from fastapi.testclient import TestClient

import anti_spoiler
import book_parser
import epub_parser
import main

client = TestClient(main.app)
SAMPLE = "../sample/雾港_示例.txt"


def test_anti_spoiler():
    with open(SAMPLE, encoding="utf-8") as f:
        chapters = book_parser.split_chapters(f.read())
    assert len(chapters) == 3, f"期望 3 章，实际 {len(chapters)}"

    book = {"id": "t", "title": "雾港", "chapters": chapters, "characters": [], "summary": None}
    ctx0 = asyncio.run(anti_spoiler.build_context(book, 0, "苏辰是谁"))  # 只读到第 1 章
    assert "苏辰" not in ctx0, "防剧透失败：进度=0 时泄露了第 2 章人物"
    assert "暗潮" not in ctx0, "防剧透失败：进度=0 时泄露了第 3 章内容"

    ctx2 = asyncio.run(anti_spoiler.build_context(book, 2, "暗潮是什么"))  # 读到第 3 章
    assert "苏辰" in ctx2 and "暗潮" in ctx2, "进度=2 应包含全部已读内容"
    print("[OK] 防剧透硬隔离：进度=0 只含第1章，进度=2 含全部3章")


def test_epub_parser():
    # 构造一个最小 epub，验证 spine 解析 + HTML 去标签
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        z.writestr(
            "content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf">'
            '<metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">测试书</dc:title></metadata>'
            '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="c1"/></spine></package>',
        )
        z.writestr(
            "c1.xhtml",
            "<html><body><h1>第一章</h1><p>这是一个测试段落，包含人物 苏辰。</p></body></html>",
        )

    title, chapters = epub_parser.parse_epub(buf.getvalue())
    assert title == "测试书", title
    assert len(chapters) == 1, chapters
    assert "苏辰" in chapters[0]["content"], chapters[0]["content"]
    print(f"[OK] EPUB 解析 -> 《{title}》{len(chapters)}章（含 苏辰）")


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


def test_multi_turn(book):
    r = client.post("/api/chat", json={
        "book_id": book["id"],
        "character": "林晚",
        "progress_chapter": 0,
        "message": "那后来呢？",
        "history": [
            {"role": "user", "content": "你现在在想什么？"},
            {"role": "assistant", "content": "我正站在渡口，看着雾一点点漫上来。"},
        ],
    })
    assert r.status_code == 200, r.text
    assert r.json()["reply"], "多轮对话应返回回复"
    print(f"[OK] 同进度多轮对话(带 history) -> {r.json()['reply'][:40]}…")


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
    test_epub_parser()
    book = test_import()
    test_chat(book)
    test_multi_turn(book)
    test_interpret(book)
    print("\n[OK] 全部冒烟测试通过")
