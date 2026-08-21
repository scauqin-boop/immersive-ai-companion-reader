"""书库持久化：每本书存为一个 JSON 文件（backend/data/*.json）。

MVP 阶段用文件存储即可，接口收敛为 create/save/load/list，后续可无痛替换为数据库。
"""
import json
import os
import time
import uuid

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def _path(book_id: str) -> str:
    return os.path.join(DATA_DIR, f"{book_id}.json")


def create_book(title: str, chapters: list, characters: list, meta: dict = None) -> dict:
    """新建一本书。chapters: [{index,title,content}]，characters: [{name,description,first_appearance}]"""
    book = {
        "id": uuid.uuid4().hex[:10],
        "title": title,
        "created_at": int(time.time()),
        "chapters": chapters,
        "characters": characters,
        "meta": meta or {},
    }
    save_book(book)
    return book


def save_book(book: dict) -> None:
    with open(_path(book["id"]), "w", encoding="utf-8") as f:
        json.dump(book, f, ensure_ascii=False, indent=2)


def load_book(book_id: str) -> dict:
    with open(_path(book_id), "r", encoding="utf-8") as f:
        return json.load(f)


def list_books() -> list:
    books = []
    for fn in os.listdir(DATA_DIR):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
            b = json.load(f)
        books.append({
            "id": b["id"],
            "title": b["title"],
            "chapter_count": len(b["chapters"]),
            "characters": [c["name"] for c in b["characters"]],
            "created_at": b["created_at"],
        })
    return sorted(books, key=lambda x: -x["created_at"])
