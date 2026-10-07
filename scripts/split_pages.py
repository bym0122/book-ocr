#!/usr/bin/env python3
"""Split PDF text into per-page TXT files and build manifest."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def pdf_page_count(pdf: Path) -> int:
    r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=False)
    m = re.search(r"Pages:\s*(\d+)", r.stdout or "")
    return int(m.group(1)) if m else 0


def extract_page(pdf: Path, page: int) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (r.stdout or "").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True, help="OCR or original PDF to extract from")
    ap.add_argument("--source-name", type=str, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--lang", type=str, default="chi_sim+eng")
    ap.add_argument("--had-text-layer", type=str, default="false")
    ap.add_argument("--ocr-mode", type=str, default="skip")
    ap.add_argument("--started-at", type=str, default="")
    args = ap.parse_args()

    out = args.out_dir
    pages_dir = out / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    total = pdf_page_count(args.pdf)
    full_parts: list[str] = []
    suspect: list[dict] = []
    success = 0
    min_chars = 30

    for i in range(1, total + 1):
        text = extract_page(args.pdf, i)
        fname = f"{i:04d}.txt"
        (pages_dir / fname).write_text(text + ("\n" if text else ""), encoding="utf-8")
        full_parts.append(f"\n\n===== Page {i} =====\n\n{text}")
        chars = len(re.sub(r"\s+", "", text))
        if chars >= min_chars:
            success += 1
        else:
            suspect.append({"page": i, "chars": chars})

    full_text = "\n".join(full_parts).strip() + "\n"
    (out / "book.txt").write_text(full_text, encoding="utf-8")

    if suspect:
        lines = [f"page={s['page']} chars={s['chars']}" for s in suspect]
        (out / "ocr_errors.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ended = datetime.now(timezone.utc).isoformat()
    manifest = {
        "source_file": args.source_name,
        "output_pdf": str(args.pdf.name) if args.pdf.exists() else None,
        "total_pages": total,
        "ocr_success": success,
        "ocr_suspect": len(suspect),
        "suspect_pages": [s["page"] for s in suspect],
        "text_chars": len(full_text),
        "chunks": total,
        "ocr_language": args.lang,
        "had_text_layer": args.had_text_layer.lower() in ("1", "true", "yes"),
        "ocr_mode": args.ocr_mode,
        "started_at": args.started_at or None,
        "finished_at": ended,
        "pages_dir": "pages/",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
