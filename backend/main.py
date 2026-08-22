"""AI 伴读 · 通用阅读器 —— FastAPI 后端。

启动：在 backend 目录下执行 `uvicorn main:app --reload`
（需先 `pip install -r requirements.txt`，并设置环境变量 DEEPSEEK_API_KEY）
"""
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import anti_spoiler
import book_parser
import character_extract
import llm
import prompt
import store

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.abspath(os.path.join(BASE, "..", "frontend"))

app = FastAPI(title="AI 伴读 · 通用阅读器")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


class ChatRequest(BaseModel):
    book_id: str
    character: str
    progress_chapter: int
    message: str


class InterpretRequest(BaseModel):
    book_id: str
    character: str
    progress_chapter: int
    text: str


class AddCharacterRequest(BaseModel):
    name: str
    description: str = ""
    first_appearance: int = 0


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))


@app.get("/api/books")
def list_books():
    return store.list_books()


@app.post("/api/books/import")
async def import_book(file: UploadFile = File(...)):
    raw = await file.read()
    title, chapters = book_parser.parse_document(file.filename, raw)
    if not chapters:
        raise HTTPException(400, "未解析出内容，请确认是 txt 或 epub 文件")

    head_text = "".join(c["content"][:2000] for c in chapters[:2])
    characters = await character_extract.extract_characters(head_text)

    book = store.create_book(title, chapters, characters, {"source": file.filename})
    return book


@app.get("/api/books/{book_id}")
def get_book(book_id: str):
    return store.load_book(book_id)


@app.post("/api/books/{book_id}/characters")
def add_character(book_id: str, req: AddCharacterRequest):
    book = store.load_book(book_id)
    book["characters"].append({
        "name": req.name.strip(),
        "description": req.description.strip(),
        "first_appearance": req.first_appearance,
    })
    store.save_book(book)
    return book


@app.post("/api/chat")
async def chat(req: ChatRequest):
    book = store.load_book(req.book_id)
    character = next((c for c in book["characters"] if c["name"] == req.character), None)
    desc = character["description"] if character else ""

    context = await anti_spoiler.build_context(book, req.progress_chapter, req.message)
    system = prompt.build_system_prompt(
        book["title"], req.character, desc, req.progress_chapter, context
    )
    ok, reply = await llm.chat_deepseek(system, req.message)
    return {"reply": reply, "ok": ok, "progress_chapter": req.progress_chapter}


@app.post("/api/interpret")
async def interpret(req: InterpretRequest):
    book = store.load_book(req.book_id)
    context = await anti_spoiler.build_context(book, req.progress_chapter, req.text)
    system = prompt.build_system_prompt(
        book["title"], req.character, "", req.progress_chapter, context
    )
    user = f"请以第一人称，解读下面这段话里人物的心理与动机（不剧透后续）：\n{req.text}"
    ok, reply = await llm.chat_deepseek(system, user)
    return {"reply": reply, "ok": ok}
