#!/usr/bin/env python3
"""Parse EPUB → ordered plain text + markdown + chapter files."""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        if tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
}


def find_opf(zf: zipfile.ZipFile) -> str:
    try:
        root = ET.fromstring(zf.read("META-INF/container.xml"))
        rootfile = root.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
        if rootfile is not None and rootfile.get("full-path"):
            return rootfile.get("full-path")
    except KeyError:
        pass
    for name in zf.namelist():
        if name.endswith(".opf"):
            return name
    raise FileNotFoundError("No OPF found in EPUB")


def parse_epub(epub_path: Path) -> dict:
    with zipfile.ZipFile(epub_path, "r") as zf:
        opf_path = find_opf(zf)
        opf_dir = str(Path(opf_path).parent)
        if opf_dir == ".":
            opf_dir = ""
        opf = ET.fromstring(zf.read(opf_path))

        title_el = opf.find(".//{http://purl.org/dc/elements/1.1/}title")
        title = (title_el.text or epub_path.stem) if title_el is not None else epub_path.stem

        manifest = {}
        for item in opf.findall(".//{http://www.idpf.org/2007/opf}item"):
            iid = item.get("id")
            href = item.get("href")
            if iid and href:
                if opf_dir:
                    href = str(Path(opf_dir) / href)
                manifest[iid] = href.replace("\\", "/")

        spine_ids = []
        for itemref in opf.findall(".//{http://www.idpf.org/2007/opf}itemref"):
            idref = itemref.get("idref")
            if idref:
                spine_ids.append(idref)

        chapters = []
        full_parts = []
        for i, iid in enumerate(spine_ids, 1):
            href = manifest.get(iid)
            if not href:
                continue
            try:
                raw = zf.read(href).decode("utf-8", errors="replace")
            except KeyError:
                continue
            parser = HTMLTextExtractor()
            try:
                parser.feed(raw)
            except Exception:
                continue
            text = parser.text()
            if not text or len(text) < 20:
                continue
            chapters.append({"index": i, "href": href, "chars": len(text), "text": text})
            full_parts.append(f"\n\n===== Chapter {i} ({href}) =====\n\n{text}")

        full_text = "\n".join(full_parts).strip()
        return {
            "title": title,
            "chapters": chapters,
            "full_text": full_text,
            "chapter_count": len(chapters),
            "text_chars": len(full_text),
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("epub", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    chapters_dir = out / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    data = parse_epub(args.epub)
    (out / "book.txt").write_text(data["full_text"], encoding="utf-8")

    md_parts = [f"# {data['title']}\n"]
    for ch in data["chapters"]:
        fname = f"{ch['index']:04d}.txt"
        (chapters_dir / fname).write_text(ch["text"], encoding="utf-8")
        md_parts.append(f"\n## Chapter {ch['index']}\n\n{ch['text']}\n")
    (out / "book.md").write_text("\n".join(md_parts), encoding="utf-8")

    meta = {
        "title": data["title"],
        "chapter_count": data["chapter_count"],
        "text_chars": data["text_chars"],
        "source": str(args.epub.name),
    }
    (out / "epub_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
