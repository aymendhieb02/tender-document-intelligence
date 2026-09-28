from __future__ import annotations

from statistics import mean

from app.core.schemas import OCRLine, OCRResult
from app.document_intelligence.schemas import DocumentResult
from app.services.ocr_engine import OCREngine


class DocumentResultInvoiceAdapter:
    """Expose Contract 1.0 evidence to the historical invoice semantics pipeline."""

    mode = "document_intelligence"

    def __init__(self, document_result: DocumentResult) -> None:
        self.document_result = document_result
        self.timing_recorder = None
        self.last_timings: dict = {"ocr_engine_used": "Document Intelligence Contract 1.0"}
        self._targeted_engine: OCREngine | None = None

    def run(self, images, embedded_text: str = "") -> OCRResult:
        lines: list[OCRLine] = []
        page_numbers = [page.page_number for page in self.document_result.pages]
        if page_numbers != list(range(1, len(page_numbers) + 1)):
            raise ValueError("DocumentResult pages are not contiguous 1-based physical pages")
        for page in self.document_result.pages:
            for element in page.elements:
                if element.page_number != page.page_number:
                    raise ValueError("DocumentResult evidence page differs from its physical page")
                if page.page_number not in page_numbers:
                    raise ValueError("DocumentResult evidence references an unavailable physical page")
                lines.append(OCRLine(
                    text=element.text,
                    confidence=element.confidence,
                    page_number=page.page_number,
                    bbox=element.bbox,
                    page_width=page.width,
                    page_height=page.height,
                    coordinate_space=element.coordinate_space,
                    source=element.source,
                ))
        confidences = [line.confidence for line in lines if line.confidence is not None]
        return OCRResult(
            raw_text="\n".join(line.text for line in lines),
            lines=lines,
            confidence=mean(confidences) if confidences else None,
            engine="Document Intelligence Contract 1.0",
            page_count=len(self.document_result.pages),
        )

    def _get_targeted_engine(self) -> OCREngine:
        if self._targeted_engine is None:
            self._targeted_engine = OCREngine(timing_recorder=self.timing_recorder)
        return self._targeted_engine

    def run_fallback_regions(self, images, regions, *, page_numbers=None):
        return self._get_targeted_engine().run_fallback_regions(images, regions, page_numbers=page_numbers)

    def run_targeted_region(self, image, region, *, page_number: int):
        return self._get_targeted_engine().run_targeted_region(image, region, page_number=page_number)
