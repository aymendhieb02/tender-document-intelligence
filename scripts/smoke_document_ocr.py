"""Controlled synthetic fixture; real PaddleOCR only, never fallback or cached text."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def create_fixture(directory: Path) -> Path:
    import fitz

    directory.mkdir(parents=True, exist_ok=True)
    pdf = fitz.open()
    page = pdf.new_page(width=720, height=260)
    for y, text in (
        (55, "BORDEREAU DES PRIX"),
        (110, "Article    Designation          Qte    Prix Unitaire"),
        (165, "001        Test article         10     25,500"),
    ):
        page.insert_text((35, y), text, fontsize=22, fontname="helv")
    pdf.save(directory / "synthetic.pdf")
    image = directory / "synthetic.png"
    page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(image)
    pdf.close()
    return image


def main() -> None:
    import cv2
    from app.services.ocr_engine import OCREngine

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/document-intelligence-smoke")
    parser.add_argument("--compare", action="store_true", help="Also verify generic processor text/confidence against the legacy recognizer")
    args = parser.parse_args()
    image = cv2.imread(str(create_fixture(args.output)))
    engine = OCREngine(mode="fast", use_disk_cache=False)
    # Direct Paddle call makes fallback incapable of concealing a broken environment.
    lines = engine._run_paddle([image])
    assert lines, "PaddleOCR returned no evidence"
    assert all(line.bbox and line.confidence is not None and line.page_number == 1 for line in lines)
    assert "BORDEREAU" in " ".join(line.text for line in lines).upper()
    payload = {"synthetic": True, "engine": "paddleocr", "cache_enabled": False,
               "lines": [line.model_dump(mode="json") for line in lines]}
    (args.output / "real-paddle-baseline.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Real PaddleOCR: {len(lines)} elements with text, bbox, confidence and page")
    if args.compare:
        from app.document_intelligence import DocumentProcessor
        result = DocumentProcessor(use_cache=False, allow_fallback=False).process(args.output / "synthetic.png")
        before = sorted((line.text, line.confidence) for line in lines)
        after = sorted((element.text, element.confidence) for element in result.pages[0].elements)
        assert before == after, "Recognition changed across the generic boundary"
        (args.output / "document-result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print("Generic processor: identical text/confidence, explicit provenance and coordinate transforms")


if __name__ == "__main__":
    main()
