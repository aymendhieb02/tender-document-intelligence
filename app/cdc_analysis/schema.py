from __future__ import annotations

from typing import Any, Literal, Protocol
from pydantic import BaseModel, Field

EvidenceStatus = Literal["detected", "probable", "ambiguous", "needs_review"]


class Evidence(BaseModel):
    document_id: str
    page: int
    element_id: str
    raw_text: str
    bbox: tuple[float, float, float, float] | None = None
    coordinate_space: str | None = None
    page_width: float | None = None
    page_height: float | None = None
    line_index: int | None = None
    source_element_ids: list[str] = Field(default_factory=list)
    source_text_parts: list[str] = Field(default_factory=list)


class Review(BaseModel):
    target_id: str
    field: str
    machine_value: Any = None
    reviewed_value: Any = None
    reviewer: str
    reviewed_at: str


class Paragraph(BaseModel):
    id: str
    number: str | None = None
    text: str
    page_start: int
    page_end: int
    source_evidence: list[Evidence]


class Article(BaseModel):
    id: str
    number: str | None = None
    title: str | None = None
    text: str = ""
    page_start: int
    page_end: int
    source_evidence: list[Evidence]
    clauses: list[Paragraph] = Field(default_factory=list)
    table_refs: list[str] = Field(default_factory=list)
    evidence_status: EvidenceStatus = "detected"


class Section(BaseModel):
    id: str
    number: str | None = None
    title: str | None = None
    normalized_title: str | None = None
    start_page: int
    end_page: int
    source_evidence: list[Evidence]
    subsections: list[Section] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)
    paragraphs: list[Paragraph] = Field(default_factory=list)
    table_refs: list[str] = Field(default_factory=list)
    evidence_status: EvidenceStatus = "detected"
    signals: dict[str, bool] = Field(default_factory=dict)


class Annex(BaseModel):
    id: str
    number: str | None = None
    title: str | None = None
    page_start: int
    page_end: int
    annex_type: str = "unknown"
    source_section: str | None = None
    source_evidence: list[Evidence]
    paragraphs: list[Paragraph] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)
    subsections: list[Section] = Field(default_factory=list)
    table_refs: list[str] = Field(default_factory=list)
    evidence_status: EvidenceStatus = "detected"


class Requirement(BaseModel):
    id: str
    type: str
    text: str
    normalized_value: Any = None
    unit: str | None = None
    source_page: int
    source_bbox: tuple[float, float, float, float] | None = None
    source_section: str | None = None
    source_article: str | None = None
    source_annex: str | None = None
    source_evidence: list[Evidence]
    extraction_status: Literal["extracted_value", "candidate_only"] = "candidate_only"
    reviewed_business_interpretation: Any = None
    evidence_status: EvidenceStatus = "probable"
    review_status: EvidenceStatus = "needs_review"


class TableReference(BaseModel):
    id: str
    table_id: str
    table_type: str = "unknown"
    source_section: str | None = None
    source_annex: str | None = None
    source_evidence: list[Evidence]


class SpecialDocument(BaseModel):
    id: str
    document_type: str
    page_start: int
    page_end: int
    source_node: str
    source_evidence: list[Evidence]
    handoff: str | None = None


class Diagnostic(BaseModel):
    code: str
    message: str
    evidence_status: EvidenceStatus = "needs_review"
    source_evidence: list[Evidence] = Field(default_factory=list)


class TenderDocument(BaseModel):
    schema_version: str = "1.0"
    document_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    title_evidence: list[Evidence] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)
    annexes: list[Annex] = Field(default_factory=list)
    paragraphs: list[Paragraph] = Field(default_factory=list)
    tables: list[TableReference] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    detected_special_documents: list[SpecialDocument] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    furniture_evidence: list[Evidence] = Field(default_factory=list)
    toc_evidence: list[Evidence] = Field(default_factory=list)
    source_order: list[str] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)


class SemanticAnalyzer(Protocol):
    def analyze(self, document: TenderDocument) -> list[Requirement]:
        """Optional future semantics over evidence, never raw PDFs."""
        ...
