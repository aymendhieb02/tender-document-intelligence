"""Domain-neutral evidence, using the existing OCRLine and BoundingBox contract."""
from typing import Final, Literal

from pydantic import BaseModel, Field

from app.core.schemas import BoundingBox, OCRLine


# Version the public contract without changing existing serialized results.
document_intelligence_contract_version: Final[str] = "1.0"


class EvidenceElement(OCRLine):
    id: str
    source: Literal["native_pdf", "paddleocr", "tesseract"]
    coordinate_space: Literal["rendered_page_pixels"] = "rendered_page_pixels"
    source_bbox: BoundingBox | None = None
    source_coordinate_space: Literal["pdf_unrotated_points", "ocr_inference_pixels"]
    source_to_page: list[list[float]]
    native_order: tuple[int, int, int] | None = None


class GeometryGroup(BaseModel):
    id: str
    bbox: BoundingBox
    element_ids: list[str]


class PageGeometry(BaseModel):
    """Visual rows/cells, not semantic headers or reconstructed business rows."""
    rows: list[GeometryGroup] = Field(default_factory=list)
    cells: list[GeometryGroup] = Field(default_factory=list)
    regions: list[GeometryGroup] = Field(default_factory=list)
    columns: list[GeometryGroup] = Field(default_factory=list)
    coordinate_space: str = "rendered_page_pixels"
    method: str = "vertical_overlap_and_repeated_left_edges"


class PageDiagnostics(BaseModel):
    native_text_available: bool = False
    native_text_usable: bool = False
    ocr_used: bool = False
    fallback_used: bool = False
    missing_geometry_count: int = 0
    cache_hit: bool = False
    selected_path: str = "native"
    warnings: list[str] = Field(default_factory=list)
    processing_ms: float = 0


class PageResult(BaseModel):
    page_number: int
    width: int
    height: int
    coordinate_space: Literal["rendered_page_pixels"] = "rendered_page_pixels"
    pdf_to_page: list[list[float]] | None = None
    pdf_rotation: int | None = None
    elements: list[EvidenceElement] = Field(default_factory=list)
    geometry: PageGeometry = Field(default_factory=PageGeometry)
    diagnostics: PageDiagnostics = Field(default_factory=PageDiagnostics)


class DocumentDiagnostics(BaseModel):
    processing_ms: float
    timings_ms: dict[str, float]
    missing_geometry_count: int
    ocr_page_count: int
    fallback_page_count: int
    cache_enabled: bool


class DocumentResult(BaseModel):
    document_id: str
    source_type: Literal["pdf", "image"]
    mode: Literal["auto", "native", "ocr", "hybrid"]
    pages: list[PageResult]
    diagnostics: DocumentDiagnostics
