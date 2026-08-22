"""EPUB 解析（仅标准库，无额外依赖）：按 spine 顺序抽取章节文本。

epub 本质是 zip 包：META-INF/container.xml 定位 opf，opf 的 spine 定义章节顺序，
每个 spine 项对应一个 XHTML 章节。这里按顺序抽文本，一个 spine 项 ≈ 一章。
"""
import html
import io
import re
import zipfile
from xml.etree import ElementTree as ET


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_epub(raw: bytes) -> tuple:
    """返回 (title, chapters)。chapters: [{index, title, content}]"""
    title, chapters = "未命名", []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        try:
            container = z.read("META-INF/container.xml").decode("utf-8", "ignore")
        except KeyError:
            return title, chapters
        m = re.search(r'full-path="([^"]+)"', container)
        if not m:
            return title, chapters
        opf_path = m.group(1)
        opf_dir = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""
        opf_root = ET.fromstring(z.read(opf_path).decode("utf-8", "ignore"))

        manifest = {}
        for el in opf_root.iter():
            if _local(el.tag) == "item":
                iid, href = el.get("id"), el.get("href")
                if iid and href:
                    manifest[iid] = opf_dir + href

        spine = []
        for el in opf_root.iter():
            if _local(el.tag) == "itemref" and el.get("idref"):
                spine.append(el.get("idref"))

        for el in opf_root.iter():
            if _local(el.tag) == "title" and el.text:
                title = el.text.strip()
                break

        for iid in spine:
            href = manifest.get(iid)
            if not href:
                continue
            try:
                html_text = z.read(href).decode("utf-8", "ignore")
            except KeyError:
                continue
            text = _html_to_text(html_text)
            if text.strip():
                chapters.append({
                    "index": len(chapters),
                    "title": f"第{len(chapters) + 1}章",
                    "content": text,
                })
    return title, chapters


def _html_to_text(raw_html: str) -> str:
    raw_html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.I)
    raw_html = re.sub(r"<(p|div|br|h[1-6]|li)[^>]*>", "\n", raw_html, flags=re.I)
    raw_html = re.sub(r"<[^>]+>", "", raw_html)
    text = html.unescape(raw_html)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n[ \n]+", "\n", text)
    return text.strip()
