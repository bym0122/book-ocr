#!/usr/bin/env python3
"""Main entry: process one PDF or EPUB under input/ into output/<stem>/."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check)


def process_pdf(src: Path, out_dir: Path, lang: str, force_ocr: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    detect = subprocess.run(
        [sys.executable, str(SCRIPTS / "detect_text_layer.py"), str(src)],
        capture_output=True,
        text=True,
    )
    has_text = detect.returncode == 0
    print(detect.stdout)

    ocr_pdf = out_dir / "book_ocr.pdf"
    if has_text and not force_ocr:
        shutil.copy2(src, ocr_pdf)
        mode = "pdftotext"
        print("Text layer detected — skipping OCR", flush=True)
    else:
        mode = "ocr"
        text_flag = "--redo-ocr" if (force_ocr and has_text) else "--force-ocr"
        cmd = [
            "ocrmypdf",
            "--language", lang,
            "--rotate-pages",
            "--deskew",
            "--output-type", "pdfa",
            "--optimize", "1",
            "--jobs", "2",
            text_flag,
            str(src),
            str(ocr_pdf),
        ]
        run(cmd)

    run([
        sys.executable,
        str(SCRIPTS / "split_pages.py"),
        "--pdf", str(ocr_pdf),
        "--source-name", src.name,
        "--out-dir", str(out_dir),
        "--lang", lang,
        "--had-text-layer", "true" if has_text else "false",
        "--ocr-mode", mode,
        "--started-at", started,
    ])
    return json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))


def process_epub(src: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    run([
        sys.executable,
        str(SCRIPTS / "epub_to_text.py"),
        str(src),
        "--out-dir", str(out_dir),
    ])
    meta = json.loads((out_dir / "epub_meta.json").read_text(encoding="utf-8"))
    chapters_dir = out_dir / "chapters"
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(exist_ok=True)
    chunks = 0
    if chapters_dir.exists():
        for i, f in enumerate(sorted(chapters_dir.glob("*.txt")), 1):
            target = pages_dir / f"{i:04d}.txt"
            target.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            chunks += 1
    manifest = {
        "source_file": src.name,
        "output_pdf": None,
        "total_pages": chunks or meta.get("chapter_count", 0),
        "ocr_success": chunks or meta.get("chapter_count", 0),
        "ocr_suspect": 0,
        "suspect_pages": [],
        "text_chars": meta.get("text_chars", 0),
        "chunks": chunks or meta.get("chapter_count", 0),
        "ocr_language": None,
        "had_text_layer": True,
        "ocr_mode": "epub",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "pages_dir": "pages/",
        "title": meta.get("title"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Process PDF/EPUB books for full-text extraction")
    ap.add_argument("--input", type=Path, default=ROOT / "input")
    ap.add_argument("--output", type=Path, default=ROOT / "output")
    ap.add_argument("--lang", default="chi_sim+eng", help="Tesseract languages, e.g. chi_sim+eng")
    ap.add_argument("--force-ocr", action="store_true")
    ap.add_argument("--file", type=str, default="", help="Process only this filename under input/")
    args = ap.parse_args()

    inp = args.input
    if not inp.exists():
        print(f"Input dir missing: {inp}", file=sys.stderr)
        return 1

    if args.file:
        p = inp / args.file
        if not p.exists():
            print(f"File not found: {p}", file=sys.stderr)
            return 1
        files = [p]
    else:
        files = sorted(
            [f for f in inp.iterdir() if f.suffix.lower() in (".pdf", ".epub") and f.is_file()]
        )

    if not files:
        print("No PDF/EPUB files in input/. Nothing to do.")
        return 0

    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for src in files:
        stem = src.stem
        out_dir = args.output / stem
        print(f"=== Processing {src.name} → {out_dir} ===", flush=True)
        if src.suffix.lower() == ".pdf":
            m = process_pdf(src, out_dir, args.lang, args.force_ocr)
        else:
            m = process_epub(src, out_dir)
        summaries.append(m)

    index = {"books": summaries, "count": len(summaries)}
    (args.output / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Done.", json.dumps(index, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
