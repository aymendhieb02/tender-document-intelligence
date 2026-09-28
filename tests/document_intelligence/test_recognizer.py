import numpy as np
import pytest

from app.core.schemas import BoundingBox, OCRLine
from app.document_intelligence.geometry import transform_bbox
from app.document_intelligence.recognizer import OCRRecognizer
from app.services.performance_timer import PipelineTimer
from app.services.preprocessing import preprocess_image_with_transform
from app.services.region_policy import FullPageRegionPolicy, InvoiceRegionPolicy

MODULE = "app.document_intelligence.recognizer"


def fake_paddle(monkeypatch):
    calls = []
    monkeypatch.setattr(f"{MODULE}._get_paddle_instance", lambda: object())
    def predict(model, image):
        calls.append(image.shape)
        return [{"text": " repeated ", "confidence": 0.93, "bbox": [140, 140, 280, 280]},
                {"text": " repeated ", "confidence": 0.81, "bbox": [420, 140, 560, 280]}]
    monkeypatch.setattr(f"{MODULE}._run_paddle_prediction", predict)
    return calls


def test_generic_policy_never_uses_invoice_regions(monkeypatch):
    def fail(image):
        raise AssertionError("Invoice policy invoked")
    monkeypatch.setattr("app.services.region_policy.build_ocr_regions", fail)
    regions = FullPageRegionPolicy().regions(np.zeros((50, 100, 3), np.uint8), "accurate")
    assert [r.name for r in regions] == ["full_page"]


def test_legacy_policy_preserved():
    image = np.zeros((200, 200, 3), np.uint8)
    assert len(InvoiceRegionPolicy().regions(image, "accurate")) > 1
    assert len(InvoiceRegionPolicy().regions(image, "balanced")) == 1


def test_ocr_preserves_duplicates_confidence_and_rescaled_boxes(monkeypatch):
    calls = fake_paddle(monkeypatch)
    elements, details = OCRRecognizer(use_cache=False).recognize(
        np.full((100, 100, 3), 255, np.uint8), 3, PipelineTimer(enabled=True))
    assert len(elements) == 2 and len(calls) == 1
    assert [e.text for e in elements] == [" repeated ", " repeated "]
    assert [e.confidence for e in elements] == [0.93, 0.81]
    assert elements[0].bbox == BoundingBox(x1=10, y1=10, x2=20, y2=20)
    assert all(e.page_number == 3 for e in elements)
    assert not details["fallback_used"]


def test_cache_identity_disabled_execution_and_stale_schema(tmp_path, monkeypatch):
    calls = fake_paddle(monkeypatch)
    image = np.full((80, 100, 3), 255, np.uint8)
    engine = OCRRecognizer(cache_dir=tmp_path)
    timer = PipelineTimer()
    first, _ = engine.recognize(image, 1, timer)
    second, info = engine.recognize(image, 1, timer)
    assert first == second and info["cache_hit"] and len(calls) == 1
    engine.recognize(image, 2, timer)
    assert len(calls) == 2
    OCRRecognizer(use_cache=False, cache_dir=tmp_path).recognize(image, 1, timer)
    assert len(calls) == 3
    for path in tmp_path.glob("*.json"):
        path.write_text('{"schema": "invoice-era", "elements": []}')
    engine.recognize(image, 1, timer)
    assert len(calls) == 4
    image[0, 0] = 0
    engine.recognize(image, 1, timer)
    assert len(calls) == 5
    monkeypatch.setattr(f"{MODULE}.version", lambda name: "different-version")
    engine.recognize(image, 1, timer)
    assert len(calls) == 6


@pytest.mark.parametrize("with_box", [True, False])
def test_tesseract_fallback_maps_geometry_or_reports_missing(monkeypatch, with_box):
    def fail():
        raise RuntimeError("controlled Paddle failure")
    monkeypatch.setattr(f"{MODULE}._get_paddle_instance", fail)
    monkeypatch.setattr(f"{MODULE}._tesseract_data_lines", lambda *args: [OCRLine(
        text="fallback evidence", page_number=1, confidence=0.72,
        bbox=BoundingBox(x1=140, y1=140, x2=280, y2=280) if with_box else None)])
    elements, info = OCRRecognizer(use_cache=False).recognize(
        np.full((100, 100, 3), 255, np.uint8), 7, PipelineTimer())
    assert info["fallback_used"]
    assert elements[0].source == "tesseract" and elements[0].page_number == 7
    assert elements[0].confidence == 0.72
    if with_box:
        assert elements[0].bbox == BoundingBox(x1=10, y1=10, x2=20, y2=20)
    else:
        assert elements[0].bbox is None and "missing_geometry" in info["warnings"]


def test_no_fallback_when_disabled(monkeypatch):
    monkeypatch.setattr(f"{MODULE}._get_paddle_instance", lambda: (_ for _ in ()).throw(RuntimeError("failure")))
    with pytest.raises(RuntimeError, match="failure"):
        OCRRecognizer(use_cache=False, allow_fallback=False).recognize(np.ones((20, 20, 3), np.uint8), 1, PipelineTimer())


def test_skew_transform_is_recorded_without_changing_pixels(monkeypatch):
    import cv2
    from app.services.preprocessing import deskew, deskew_with_transform
    monkeypatch.setattr(cv2, "minAreaRect", lambda coords: ((0, 0), (20, 40), 5.0))
    gray = np.full((80, 120), 220, np.uint8)
    actual, matrix = deskew_with_transform(gray)
    expected_matrix = cv2.getRotationMatrix2D((60, 40), -5.0, 1.0)
    expected = cv2.warpAffine(gray, expected_matrix, (120, 80), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    assert np.array_equal(actual, expected) and np.array_equal(deskew(gray), expected)
    assert np.allclose(matrix[:2], expected_matrix)
    _, combined = preprocess_image_with_transform(np.stack([gray] * 3, axis=2))
    assert not np.allclose(combined[:2, :2], np.diag(np.diag(combined[:2, :2])))


def test_affine_maps_all_corners():
    box = BoundingBox(x1=10, y1=20, x2=30, y2=50)
    matrix = np.array([[0, -2, 200], [2, 0, 0], [0, 0, 1]])
    transformed = transform_bbox(box, matrix)
    assert transformed == BoundingBox(x1=100, y1=20, x2=160, y2=60)
    assert transform_bbox(transformed, np.linalg.inv(matrix)) == box


def test_existing_tesseract_data_adapter_preserves_word_union():
    from types import SimpleNamespace
    from app.services.ocr_engine import _tesseract_data_lines
    engine = SimpleNamespace(Output=SimpleNamespace(DICT="dict"), image_to_data=lambda *a, **kw: {
        "text": ["left", "right"], "block_num": [1, 1], "par_num": [1, 1], "line_num": [1, 1],
        "left": [20, 70], "top": [10, 12], "width": [40, 50], "height": [20, 20], "conf": ["90", "80"],
    })
    line = _tesseract_data_lines(engine, np.zeros((50, 150, 3), np.uint8), 4, "--psm 11")[0]
    assert line.bbox == BoundingBox(x1=20, y1=10, x2=120, y2=32)
    assert line.text == "left right" and line.confidence == 0.85 and line.page_number == 4
