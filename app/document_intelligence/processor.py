"""Local, multi-page document evidence with per-page native/OCR selection."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import time
from typing import Literal, Protocol

import cv2
import fitz
import numpy as np
from PIL import Image

from app.core.schemas import BoundingBox
from app.services.performance_timer import PipelineTimer
from .geometry import layout_evidence, reading_order, transform_bbox
from .recognizer import OCRRecognizer
from .schemas import DocumentDiagnostics, DocumentResult, EvidenceElement, PageDiagnostics, PageResult

logger = logging.getLogger(__name__)
Mode = Literal["auto", "native", "ocr", "hybrid"]


class Recognizer(Protocol):
    def recognize(self, image: np.ndarray, page_number: int, timer: PipelineTimer
                  ) -> tuple[list[EvidenceElement], dict]: ...


class DocumentProcessor:
    def __init__(self, *, mode: Mode = "auto", render_scale: float = 2.0,
                 use_cache: bool = True, allow_fallback: bool = True,
                 recognizer: Recognizer | None = None, max_pages: int = 500,
                 max_bytes: int = 100 * 1024 * 1024, max_page_pixels: int = 40_000_000) -> None:
        if mode not in {"auto", "native", "ocr", "hybrid"}:
            raise ValueError("mode must be auto, native, ocr or hybrid")
        if not np.isfinite(render_scale) or not 0 < render_scale <= 4:
            raise ValueError("render_scale must be positive and at most 4")
        if min(max_pages, max_bytes, max_page_pixels) <= 0:
            raise ValueError("Resource limits must be positive")
        self.mode = mode
        self.render_scale = render_scale
        self.use_cache = use_cache
        self.recognizer = recognizer or OCRRecognizer(use_cache=use_cache, allow_fallback=allow_fallback)
        self.max_pages, self.max_bytes, self.max_page_pixels = max_pages, max_bytes, max_page_pixels

    def process(self, path: str | Path) -> DocumentResult:
        path = Path(path)
        timer = PipelineTimer(enabled=True)
        pages = []
        with timer.stage("total_pipeline"):
            with timer.stage("load"):
                if path.stat().st_size > self.max_bytes:
                    raise ValueError("Document exceeds configured byte limit")
                data = path.read_bytes()
                document_id = hashlib.sha256(data).hexdigest()
            logger.info("Document loaded id=%s", document_id[:12])
            if path.suffix.lower() == ".pdf":
                with fitz.open(stream=data, filetype="pdf") as pdf:
                    if pdf.needs_pass:
                        raise ValueError("Encrypted PDFs require decryption before processing")
                    if not 0 < len(pdf) <= self.max_pages:
                        raise ValueError("PDF page count exceeds configured limit or is empty")
                    for page in pdf:
                        pages.append(self._pdf_page(page, timer))
                source_type = "pdf"
            else:
                if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".jfif", ".tif", ".tiff", ".bmp", ".avif"}:
                    raise ValueError("Unsupported image type")
                if self.mode == "native":
                    raise ValueError("native mode requires PDF input")
                if path.suffix.lower() == ".avif":
                    import pillow_avif  # noqa: F401
                # Decode the same bytes used for identity, avoiding a second file read.
                from io import BytesIO
                with Image.open(BytesIO(data)) as image:
                    frame_count = getattr(image, "n_frames", 1)
                    if frame_count > self.max_pages:
                        raise ValueError("Image frame count exceeds configured page limit")
                    for index in range(frame_count):
                        image.seek(index)
                        self._check_size(*image.size)
                        with timer.stage("load", page_number=index + 1):
                            pixels = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
                        pages.append(self._image_page(pixels, index + 1, timer))
                source_type = "image"
        timings = {key: value * 1000 for key, value in timer.aggregate().items()}
        for key in ("load", "render", "native_extraction", "preprocessing", "ocr", "layout"):
            timings.setdefault(key, 0.0)
        return DocumentResult(document_id=document_id, source_type=source_type, mode=self.mode, pages=pages,
            diagnostics=DocumentDiagnostics(processing_ms=timings["total_pipeline"], timings_ms=timings,
                missing_geometry_count=sum(p.diagnostics.missing_geometry_count for p in pages),
                ocr_page_count=sum(p.diagnostics.ocr_used for p in pages),
                fallback_page_count=sum(p.diagnostics.fallback_used for p in pages), cache_enabled=self.use_cache))

    def _check_size(self, width: int, height: int) -> None:
        if width * height > self.max_page_pixels:
            raise ValueError("Page exceeds configured pixel limit")

    def _pdf_page(self, page: fitz.Page, timer: PipelineTimer) -> PageResult:
        started = time.perf_counter()
        number = page.number + 1
        # PyMuPDF text boxes are unrotated crop-relative points. Rotation precedes render scaling.
        rotation = page.rotation_matrix
        matrix = np.array([[rotation.a, rotation.c, rotation.e],
                           [rotation.b, rotation.d, rotation.f], [0, 0, 1]], dtype=float)
        matrix = np.diag([self.render_scale, self.render_scale, 1.0]) @ matrix
        rectangle = (page.rect * fitz.Matrix(self.render_scale, self.render_scale)).irect
        width, height = rectangle.width, rectangle.height
        matrix[0, 2] -= rectangle.x0
        matrix[1, 2] -= rectangle.y0
        self._check_size(width, height)
        with timer.stage("native_extraction", page_number=number):
            words = page.get_text("words", sort=False)
            native = [EvidenceElement(id=f"p{number}-native-{i:06d}", text=w[4],
                      bbox=transform_bbox(BoundingBox(x1=w[0], y1=w[1], x2=w[2], y2=w[3]), matrix),
                      source_bbox=BoundingBox(x1=w[0], y1=w[1], x2=w[2], y2=w[3]),
                      source_coordinate_space="pdf_unrotated_points", source_to_page=matrix.tolist(),
                      native_order=(w[5], w[6], w[7]), source="native_pdf", confidence=None,
                      page_number=number, page_width=width, page_height=height, line_index=i)
                      for i, w in enumerate(words) if w[4].strip()]
        usable = native_is_usable(native)
        do_ocr = self.mode in {"ocr", "hybrid"} or (self.mode == "auto" and not usable)
        diagnostics = PageDiagnostics(native_text_available=bool(native), native_text_usable=usable,
            ocr_used=do_ocr, selected_path="hybrid" if self.mode == "hybrid" else "ocr" if do_ocr else "native")
        logger.info("Page path selected page=%s path=%s", number, diagnostics.selected_path)
        elements = native if self.mode != "ocr" and (not do_ocr or self.mode == "hybrid") else []
        if do_ocr:
            with timer.stage("render", page_number=number):
                pixmap = page.get_pixmap(matrix=fitz.Matrix(self.render_scale, self.render_scale),
                                        colorspace=fitz.csRGB, alpha=False)
                pixels = cv2.cvtColor(np.frombuffer(pixmap.samples, np.uint8).reshape(height, width, 3), cv2.COLOR_RGB2BGR)
            ocr, details = self.recognizer.recognize(pixels, number, timer)
            elements.extend(ocr)
            diagnostics.fallback_used = details.get("fallback_used", False)
            diagnostics.cache_hit = details.get("cache_hit", False)
            diagnostics.warnings.extend(details.get("warnings", []))
        elif not usable:
            diagnostics.warnings.append("native_text_not_usable")
        if self.mode == "hybrid":
            diagnostics.warnings.append("hybrid_unmerged_evidence")
        return self._finish(number, width, height, elements, diagnostics, timer, started,
                            pdf_to_page=matrix.tolist(), pdf_rotation=page.rotation)

    def _image_page(self, pixels: np.ndarray, number: int, timer: PipelineTimer) -> PageResult:
        started = time.perf_counter()
        elements, details = self.recognizer.recognize(pixels, number, timer)
        diagnostics = PageDiagnostics(ocr_used=True, selected_path="ocr",
            fallback_used=details.get("fallback_used", False), cache_hit=details.get("cache_hit", False),
            warnings=details.get("warnings", []))
        return self._finish(number, pixels.shape[1], pixels.shape[0], elements, diagnostics, timer, started)

    @staticmethod
    def _finish(number, width, height, elements, diagnostics, timer, started, **metadata) -> PageResult:
        with timer.stage("layout", page_number=number):
            elements = reading_order(elements)
            geometry = layout_evidence(elements)
        diagnostics.missing_geometry_count = sum(e.bbox is None for e in elements)
        if diagnostics.missing_geometry_count and "missing_geometry" not in diagnostics.warnings:
            diagnostics.warnings.append("missing_geometry")
        diagnostics.processing_ms = (time.perf_counter() - started) * 1000
        return PageResult(page_number=number, width=width, height=height, elements=elements,
                          geometry=geometry, diagnostics=diagnostics, **metadata)


def native_is_usable(elements: list[EvidenceElement]) -> bool:
    """Conservative, explicit page rule; quality of invisible OCR layers is not inferred."""
    text = "".join(e.text for e in elements)
    if len(text.strip()) < 12:
        return False
    readable = sum(character.isprintable() and character != "\ufffd" for character in text)
    return readable / len(text) >= 0.95 and all(e.bbox and e.bbox.x2 > e.bbox.x1 and e.bbox.y2 > e.bbox.y1 for e in elements)
