"""Frozen public contract; no consumer-specific expectations or OCR tuning."""
import hashlib
import json
from pathlib import Path

import fitz
import numpy as np
import pytest
from pydantic import ValidationError

from app.core.schemas import BoundingBox
from app.document_intelligence import DocumentProcessor, document_intelligence_contract_version
from app.document_intelligence.geometry import layout_evidence, transform_bbox
from app.document_intelligence.recognizer import OCRRecognizer
from app.document_intelligence.schemas import DocumentResult, EvidenceElement
from app.services.performance_timer import PipelineTimer

FIXTURES = Path(__file__).with_name("fixtures")


@pytest.fixture
def specimen():
    return DocumentResult.model_validate_json((FIXTURES / "document_result_v1.json").read_text(encoding="utf-8"))


def test_version_and_public_schema_are_frozen():
    assert document_intelligence_contract_version == "1.0"
    assert DocumentResult.model_json_schema() == json.loads(
        (FIXTURES / "document_result_v1.schema.json").read_text(encoding="utf-8"))
    metadata = json.loads((FIXTURES / "document_result_v1.meta.json").read_text(encoding="utf-8"))
    assert metadata["synthetic"] is True
    assert metadata["document_intelligence_contract_version"] == document_intelligence_contract_version
    # Version is out-of-band, preserving the V1 wire shape.
    assert "document_intelligence_contract_version" not in DocumentResult.model_fields


def test_shared_fixture_is_exactly_round_trippable(specimen):
    assert json.loads(specimen.model_dump_json()) == json.loads(
        (FIXTURES / "document_result_v1.json").read_text(encoding="utf-8"))
    assert [p.page_number for p in specimen.pages] == [1, 2]
    assert {e.source for e in specimen.pages[0].elements} == {"native_pdf"}
    assert {e.source for e in specimen.pages[1].elements} == {"paddleocr"}


def test_source_ids_repeated_text_and_geometry_references(specimen):
    all_ids = []
    for page in specimen.pages:
        index = {e.id: e for e in page.elements}
        assert len(index) == len(page.elements)
        all_ids.extend(index)
        assert all(e.page_number == page.page_number for e in page.elements)
        repeated = [e for e in page.elements if e.text == "Repeat"]
        assert len(repeated) == 2 and repeated[0].id != repeated[1].id
        assert page.geometry == layout_evidence(page.elements)
        for groups in (page.geometry.rows, page.geometry.cells, page.geometry.columns, page.geometry.regions):
            assert len({g.id for g in groups}) == len(groups)
            for group in groups:
                assert group.element_ids and set(group.element_ids) <= index.keys()
                assert all(index[source_id].bbox is not None for source_id in group.element_ids)
        assert len(page.geometry.rows) == 2 and len(page.geometry.columns) == 2
        assert len(page.geometry.cells) == 4
        assert page.geometry.cells[0].element_ids == [page.elements[0].id]
    assert len(set(all_ids)) == len(all_ids)
    # Geometry IDs are page-scoped, unlike the element references they contain.
    assert specimen.pages[0].geometry.rows[0].id == specimen.pages[1].geometry.rows[0].id == "row-0"


def test_bbox_representation_coordinate_spaces_and_nulls(specimen):
    for page in specimen.pages:
        assert page.coordinate_space == page.geometry.coordinate_space == "rendered_page_pixels"
        for element in page.elements:
            assert element.coordinate_space == page.coordinate_space
            assert (element.page_width, element.page_height) == (page.width, page.height)
            if element.bbox is None:
                assert element.source_bbox is None
                continue
            assert set(element.bbox.model_dump()) == {"x1", "y1", "x2", "y2"}
            mapped = transform_bbox(element.source_bbox, np.array(element.source_to_page))
            assert mapped == element.bbox
    native = specimen.pages[0].elements[0]
    assert native.source_coordinate_space == "pdf_unrotated_points"
    assert native.source_bbox == BoundingBox(x1=20, y1=40, x2=60, y2=50)
    assert native.bbox == BoundingBox(x1=40, y1=80, x2=120, y2=100)
    ocr = specimen.pages[1].elements[0]
    assert ocr.source_coordinate_space == "ocr_inference_pixels"
    assert ocr.source_bbox == BoundingBox(x1=80, y1=160, x2=240, y2=200)
    assert ocr.bbox == native.bbox
    assert specimen.pages[1].elements[-1].bbox is None


def test_confidence_is_evidence_not_business_certainty(specimen):
    assert all(e.confidence is None for e in specimen.pages[0].elements)
    assert [e.confidence for e in specimen.pages[1].elements] == [0.94, 0.0, 0.87, 0.91, None]
    assert specimen.pages[1].elements[1].confidence is not None
    assert specimen.pages[1].diagnostics.missing_geometry_count == 1
    assert "missing_geometry" in specimen.pages[1].diagnostics.warnings


@pytest.mark.parametrize("source", ["native_pdf", "paddleocr", "tesseract"])
def test_exact_source_vocabulary(specimen, source):
    data = specimen.pages[1].elements[0].model_dump()
    data["source"] = source
    assert EvidenceElement.model_validate(data).source == source
    data["source"] = "invoice_ocr"
    with pytest.raises(ValidationError):
        EvidenceElement.model_validate(data)
    data["source"] = "paddleocr"
    data["coordinate_space"] = "normalized"
    with pytest.raises(ValidationError):
        EvidenceElement.model_validate(data)


def test_producer_physical_pages_identity_and_native_confidence(tmp_path):
    path = tmp_path / "three-pages.pdf"
    with fitz.open() as pdf:
        for text in ("Repeated source", "", "Repeated source"):
            page = pdf.new_page(width=300, height=200)
            if text:
                page.insert_text((20, 40), text)
        pdf.save(path)
    first = DocumentProcessor(mode="native").process(path)
    second = DocumentProcessor(mode="native").process(path)
    assert first.document_id == second.document_id == hashlib.sha256(path.read_bytes()).hexdigest()
    assert [p.page_number for p in first.pages] == [1, 2, 3]
    assert first.pages[1].elements == []
    for left, right in zip(first.pages, second.pages):
        assert left.elements == right.elements
        assert all(e.confidence is None and e.source == "native_pdf" for e in left.elements)
        assert all(e.coordinate_space == "rendered_page_pixels" for e in left.elements)
    assert [e.id for e in first.pages[0].elements] == ["p1-native-000000", "p1-native-000001"]
    assert [e.id for e in first.pages[2].elements] == ["p3-native-000000", "p3-native-000001"]


def test_ocr_identity_is_source_index_not_text_or_reading_position(monkeypatch):
    module = "app.document_intelligence.recognizer"
    monkeypatch.setattr(f"{module}._get_paddle_instance", lambda: object())
    monkeypatch.setattr(f"{module}._run_paddle_prediction", lambda *args: [
        {"text": "Repeat", "bbox": [600, 200, 800, 240], "confidence": 0.0},
        {"text": "Repeat", "bbox": [40, 80, 180, 120], "confidence": 0.83},
        {"text": "Unpositioned", "confidence": None},
    ])
    recognizer = OCRRecognizer(use_cache=False, allow_fallback=False)
    image = np.full((400, 1400, 3), 255, np.uint8)
    elements, _ = recognizer.recognize(image, 2, PipelineTimer())
    from app.document_intelligence.geometry import reading_order
    ordered = reading_order(elements)
    assert [e.id for e in ordered] == ["p2-ocr-000001", "p2-ocr-000000", "p2-ocr-000002"]
    assert [e.confidence for e in ordered] == [0.83, 0.0, None]
    assert all(e.source == "paddleocr" and e.page_number == 2 for e in ordered)
    assert ordered[2].bbox is None
    assert ordered[0].bbox == BoundingBox(x1=40, y1=80, x2=180, y2=120)
