import json

import fitz
import numpy as np
import pytest
from PIL import Image

from app.core.schemas import BoundingBox
from app.document_intelligence import DocumentProcessor
from app.document_intelligence.geometry import transform_bbox
from app.document_intelligence.schemas import DocumentResult, EvidenceElement


class StubRecognizer:
    def __init__(self):
        self.pages = []

    def recognize(self, image, page_number, timer):
        self.pages.append(page_number)
        return [EvidenceElement(id=f"p{page_number}-ocr-000000", text="Same repeated text",
            page_number=page_number, page_width=image.shape[1], page_height=image.shape[0],
            bbox=BoundingBox(x1=10, y1=20, x2=60, y2=40), confidence=0.87, source="paddleocr",
            source_coordinate_space="ocr_inference_pixels", source_to_page=np.eye(3).tolist())], {}


def make_pdf(tmp_path, kinds):
    path = tmp_path / "document.pdf"
    with fitz.open() as document:
        for kind in kinds:
            page = document.new_page(width=300, height=200)
            if kind == "native":
                page.insert_text((20, 50), "Evidence across page boundary", fontsize=12)
            else:
                # A real image-only PDF page; recognition is injected for deterministic tests.
                pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 300, 200), False)
                pix.clear_with(255)
                page.insert_image(page.rect, pixmap=pix)
        document.save(path)
    return path


def test_mixed_pdf_uses_per_page_decision_and_keeps_page_boundaries(tmp_path):
    recognizer = StubRecognizer()
    result = DocumentProcessor(recognizer=recognizer).process(make_pdf(tmp_path, ["native", "scan", "native", "scan"]))
    assert recognizer.pages == [2, 4]
    assert [p.page_number for p in result.pages] == [1, 2, 3, 4]
    for page in result.pages:
        assert all(e.page_number == page.page_number for e in page.elements)
    assert result.pages[1].elements[0].text == result.pages[3].elements[0].text
    assert result.diagnostics.ocr_page_count == 2
    assert result.pages[0].elements[0].confidence is None
    assert result.pages[1].elements[0].confidence == 0.87


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("cropped", [False, True])
def test_native_pdf_geometry_matches_rendered_ink(tmp_path, rotation, cropped):
    path = tmp_path / "rotated.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        page.insert_text((100, 120), "SOURCE EVIDENCE", fontsize=16)
        if cropped:
            page.set_cropbox(fitz.Rect(40, 30, 360, 260))
        page.set_rotation(rotation)
        pdf.save(path)
    result = DocumentProcessor(mode="native").process(path)
    page_result = result.pages[0]
    with fitz.open(path) as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csRGB, alpha=False)
        pixels = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    assert (page_result.width, page_result.height) == (pix.width, pix.height)
    for element in page_result.elements:
        b = element.bbox
        region = pixels[max(0, int(b.y1)):int(np.ceil(b.y2)), max(0, int(b.x1)):int(np.ceil(b.x2))]
        assert region.size and (region < 128).any()
        original = transform_bbox(b, np.linalg.inv(np.array(element.source_to_page)))
        assert np.allclose(list(original.model_dump().values()), list(element.source_bbox.model_dump().values()))
        assert element.native_order is not None
        assert element.coordinate_space == "rendered_page_pixels"


@pytest.mark.parametrize("mode, expected_calls, sources", [
    ("auto", [], {"native_pdf"}), ("native", [], {"native_pdf"}),
    ("ocr", [1], {"paddleocr"}), ("hybrid", [1], {"native_pdf", "paddleocr"}),
])
def test_modes_are_explicit(tmp_path, mode, expected_calls, sources):
    stub = StubRecognizer()
    result = DocumentProcessor(mode=mode, recognizer=stub).process(make_pdf(tmp_path, ["native"]))
    assert stub.pages == expected_calls
    assert {e.source for e in result.pages[0].elements} == sources
    if mode == "hybrid":
        assert "hybrid_unmerged_evidence" in result.pages[0].diagnostics.warnings


def test_native_mode_does_not_fabricate_scan_text(tmp_path):
    result = DocumentProcessor(mode="native").process(make_pdf(tmp_path, ["scan"]))
    assert result.pages[0].elements == []
    assert "native_text_not_usable" in result.pages[0].diagnostics.warnings


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".tiff"])
def test_image_input_and_identity(tmp_path, suffix):
    path = tmp_path / f"image{suffix}"
    Image.new("RGB", (80, 50), "white").save(path)
    result = DocumentProcessor(recognizer=StubRecognizer()).process(path)
    assert result.source_type == "image"
    assert (result.pages[0].width, result.pages[0].height) == (80, 50)
    assert len(result.document_id) == 64
    with pytest.raises(ValueError, match="native mode"):
        DocumentProcessor(mode="native").process(path)


def test_multiframe_image(tmp_path):
    path = tmp_path / "frames.tiff"
    Image.new("RGB", (80, 50)).save(path, save_all=True, append_images=[Image.new("RGB", (90, 60))])
    stub = StubRecognizer()
    result = DocumentProcessor(recognizer=stub).process(path)
    assert stub.pages == [1, 2]
    assert result.pages[1].width == 90


def test_limits_and_invalid_mode(tmp_path):
    path = make_pdf(tmp_path, ["native", "native"])
    with pytest.raises(ValueError, match="page count"):
        DocumentProcessor(max_pages=1).process(path)
    with pytest.raises(ValueError, match="pixel limit"):
        DocumentProcessor(max_page_pixels=100).process(path)
    with pytest.raises(ValueError, match="byte limit"):
        DocumentProcessor(max_bytes=10).process(path)
    with pytest.raises(ValueError, match="mode"):
        DocumentProcessor(mode="invoice")


def test_serialization_is_domain_neutral_and_evidence_survives(tmp_path):
    result = DocumentProcessor().process(make_pdf(tmp_path, ["native", "native"]))
    encoded = result.model_dump_json()
    restored = DocumentResult.model_validate_json(encoded)
    assert restored == result
    forbidden = {"supplier", "customer", "invoice_number", "article", "quantity", "unit_price", "penalty", "guarantee"}

    def walk(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(json.loads(encoded))
    assert all(e.confidence is None for p in result.pages for e in p.elements)
    assert set(result.diagnostics.timings_ms) >= {"load", "render", "native_extraction", "ocr", "preprocessing", "layout", "total_pipeline"}


def test_reading_order_does_not_follow_pdf_insertion_order(tmp_path):
    path = tmp_path / "order.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((200, 150), "bottom")
        page.insert_text((200, 50), "right")
        page.insert_text((20, 50), "left")
        pdf.save(path)
    page = DocumentProcessor().process(path).pages[0]
    assert [e.text for e in page.elements] == ["left", "right", "bottom"]
    assert page.geometry.rows[0].element_ids == [page.elements[0].id, page.elements[1].id]


def test_generic_alignment_evidence_preserves_sources(tmp_path):
    path = tmp_path / "aligned.pdf"
    with fitz.open() as pdf:
        page = pdf.new_page()
        for y in [40, 70, 100]:
            page.insert_text((20, y), "alpha")
            page.insert_text((200, y), "beta")
        pdf.save(path)
    page = DocumentProcessor().process(path).pages[0]
    assert len(page.geometry.rows) == 3
    assert len(page.geometry.columns) == 2
    assert len(page.geometry.regions) == 1
    known_ids = {e.id for e in page.elements}
    assert set(page.geometry.regions[0].element_ids) == known_ids
    assert all(set(c.element_ids) <= known_ids for c in page.geometry.cells)
