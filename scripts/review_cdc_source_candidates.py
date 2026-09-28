"""Print source-PDF text cues for human ground-truth review; never reads predictions."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re

import fitz

PATTERN = re.compile(r"^\s*(?:ARTICLE\s+|Article\s+|CHAPITRE\s+|Partie\s+[IVX]+|ANNEXE\s+|[A-D]\s*[–-]\s|\d+\s*[.)-]\s*ARTICLE|الفصل|الباب|الملحق|جزء)", re.I)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/cdc_real_v1/corpus_manifest.csv"))
    parser.add_argument("--ids", nargs="+", required=True)
    args = parser.parse_args()
    with args.manifest.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["document_id"]: row for row in csv.DictReader(stream)}
    for document_id in args.ids:
        path = args.corpus / rows[document_id]["relative_path"]
        with fitz.open(path) as pdf:
            print(f"\n### {document_id} | {rows[document_id]['filename']} | {len(pdf)} pages")
            for index, page in enumerate(pdf):
                text = page.get_text()
                if index < 3 or (index < 20 and any(key in text.upper() for key in ("TABLE DES MATIERES", "SOMMAIRE", "CONTENTS"))):
                    compact = " ".join(text.split())
                    if compact:
                        print(f"PAGE {index + 1}: {compact[:700]}")
            print("HEADINGS (source text only):")
            for index, page in enumerate(pdf):
                for line in page.get_text().splitlines():
                    if PATTERN.match(line):
                        print(f"{index + 1}: {line.strip()[:180]}")


if __name__ == "__main__":
    main()
