import os

import fitz
import pytest

from app.document_intelligence import DocumentProcessor
from scripts.smoke_document_ocr import create_fixture


@pytest.mark.skipif(os.environ.get("RUN_REAL_OCR") != "1", reason="Explicit RUN_REAL_OCR=1 requires real local Paddle models")
def test_real_paddle_image_scanned_and_mixed_pdf(tmp_path):
    image = create_fixture(tmp_path)
    processor = DocumentProcessor(use_cache=False, allow_fallback=False)
    result = processor.process(image)
    evidence = result.pages[0].elements
    assert "BORDEREAU" in " ".join(e.text for e in evidence).upper()
    assert evidence and all(e.bbox and e.confidence is not None and e.source == "paddleocr" for e in evidence)
    assert not result.pages[0].diagnostics.fallback_used
    with fitz.open(tmp_path / "synthetic.pdf") as pdf:
        page = pdf.new_page(width=720, height=260)
        page.insert_image(page.rect, filename=str(image))
        page = pdf.new_page(width=720, height=260)
        page.insert_text((20, 50), "Native final page evidence", fontsize=20)
        pdf.save(tmp_path / "mixed.pdf")
    mixed = processor.process(tmp_path / "mixed.pdf")
    assert [p.diagnostics.ocr_used for p in mixed.pages] == [False, True, False]
    assert all(e.page_number == 2 and e.source == "paddleocr" for e in mixed.pages[1].elements)
    assert "BORDEREAU" in " ".join(e.text for e in mixed.pages[1].elements).upper()
