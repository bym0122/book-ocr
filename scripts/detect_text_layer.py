#!/usr/bin/env python3
"""Detect whether a PDF already has a usable text layer."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def page_count(pdf: Path) -> int:
    r = subprocess.run(
        ["pdfinfo", str(pdf)],
        capture_output=True,
        text=True,
        check=False,
    )
    m = re.search(r"Pages:\s*(\d+)", r.stdout or "")
    return int(m.group(1)) if m else 0


def extract_sample(pdf: Path, max_pages: int = 5) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", "-f", "1", "-l", str(max_pages), str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout or ""


def is_usable_text(text: str, min_chars_per_page: int = 80) -> bool:
    cleaned = re.sub(r"\s+", "", text)
    if len(cleaned) < min_chars_per_page:
        return False
    cjk = len(re.findall(r"[\u4e00-\u9fff]", cleaned))
    latin = len(re.findall(r"[A-Za-z]", cleaned))
    return (cjk + latin) >= min_chars_per_page * 0.3


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("pdf", type=Path)
    p.add_argument("--out-json", type=Path, default=None)
    args = p.parse_args()

    pages = page_count(args.pdf)
    sample = extract_sample(args.pdf)
    usable = is_usable_text(sample)
    result = {
        "path": str(args.pdf),
        "pages": pages,
        "has_text_layer": usable,
        "sample_chars": len(sample),
        "sample_preview": sample[:200].replace("\n", " "),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.out_json:
        args.out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
