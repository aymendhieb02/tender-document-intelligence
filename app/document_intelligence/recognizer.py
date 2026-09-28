"""Generic orchestration around the verified Paddle adapters; no field extraction."""
from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from pydantic import ValidationError

from app.services.ocr_engine import (
    PREPROCESSING_VERSION, _ensure_color_image, _get_paddle_instance,
    _iter_paddle_items, _run_paddle_prediction, _tesseract_data_lines,
    _tesseract_string_lines, normalize_paddle_bbox,
    _paddle_fingerprint,
)
from app.services.ocr_profiles import effective_ocr_config
from app.services.performance_timer import PipelineTimer
from app.services.preprocessing import preprocess_image_with_transform
from app.services.region_policy import FullPageRegionPolicy
from .geometry import transform_bbox
from .schemas import EvidenceElement

logger = logging.getLogger(__name__)
CACHE_VERSION = "document-evidence-1"


class OCRRecognizer:
    def __init__(self, *, use_cache: bool = True,
                 cache_dir: Path = Path(".cache/document_intelligence"),
                 allow_fallback: bool = True) -> None:
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir)
        self.allow_fallback = allow_fallback
        self.region_policy = FullPageRegionPolicy()

    def recognize(self, image: np.ndarray, page_number: int, timer: PipelineTimer
                  ) -> tuple[list[EvidenceElement], dict]:
        config = effective_ocr_config()
        region = self.region_policy.regions(image)[0]
        with timer.stage("preprocessing", page_number=page_number):
            processed, original_to_inference = preprocess_image_with_transform(
                region.image, profile=config["preprocessing_profile"], max_side=config["input_max_side"])
            processed = _ensure_color_image(processed)
        inverse = np.linalg.inv(original_to_inference)
        signature = {
            "schema": CACHE_VERSION, "page": page_number,
            "image": hashlib.sha256(image.tobytes()).hexdigest(), "shape": list(image.shape),
            "processed": hashlib.sha256(processed.tobytes()).hexdigest(),
            "config": config, "preprocessing": PREPROCESSING_VERSION,
            "recognizer_config": _paddle_fingerprint(),
            "versions": {name: version(name) for name in ("paddleocr", "paddlepaddle", "paddlex", "opencv-contrib-python")},
        }
        key = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
        cached = self._read(key) if self.use_cache else None
        if cached is not None:
            return cached, {"cache_hit": True, "fallback_used": False, "warnings": []}
        fallback = False
        warnings = []
        with timer.stage("ocr", page_number=page_number):
            try:
                prediction = _run_paddle_prediction(_get_paddle_instance(), processed)
                items = list(_iter_paddle_items(prediction, page_number=page_number))
                source = "paddleocr"
            except (ImportError, RuntimeError, OSError, ValueError) as exc:
                if not self.allow_fallback:
                    raise
                logger.warning("PaddleOCR unavailable on page %s (%s); trying fallback",
                               page_number, type(exc).__name__)
                warnings.append(f"paddleocr_failed:{type(exc).__name__}")
                fallback = True
                import pytesseract
                lines = _tesseract_data_lines(pytesseract, processed, page_number, "--oem 3 --psm 11")
                if not lines:
                    lines = _tesseract_string_lines(pytesseract, processed, page_number, "--oem 3 --psm 11")
                items = [line.model_dump() for line in lines]
                source = "tesseract"
        elements = []
        for i, item in enumerate(items):
            text = str(item.get("text") or "")
            if not text.strip():
                continue
            source_box = normalize_paddle_bbox(item.get("bbox"))
            elements.append(EvidenceElement(
                id=f"p{page_number}-ocr-{i:06d}", text=text,
                bbox=transform_bbox(source_box, inverse) if source_box else None,
                source_bbox=source_box, source_coordinate_space="ocr_inference_pixels",
                source_to_page=inverse.tolist(), confidence=item.get("confidence"),
                page_number=page_number, page_width=image.shape[1], page_height=image.shape[0],
                line_index=i, source=source,
            ))
        if not elements:
            warnings.append("no_text_detected")
        if any(e.bbox is None for e in elements):
            warnings.append("missing_geometry")
        # Failed Paddle calls are never cached as successful Paddle evidence.
        if self.use_cache and not fallback:
            self._write(key, elements)
        logger.info("OCR completed page=%s elements=%s fallback=%s", page_number, len(elements), fallback)
        return elements, {"cache_hit": False, "fallback_used": fallback, "warnings": warnings}

    def _read(self, key: str) -> list[EvidenceElement] | None:
        path = self.cache_dir / f"{key}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["schema"] != CACHE_VERSION:
                return None
            return [EvidenceElement.model_validate(item) for item in data["elements"]]
        except (OSError, ValueError, KeyError, TypeError, ValidationError):
            return None

    def _write(self, key: str, elements: list[EvidenceElement]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.cache_dir, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"schema": CACHE_VERSION, "elements": [e.model_dump(mode="json") for e in elements]}, stream)
            temporary.replace(self.cache_dir / f"{key}.json")
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
