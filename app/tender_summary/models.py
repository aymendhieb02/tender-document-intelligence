from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FactState(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class EvidenceReference(BaseModel):
    """Clickable source location retaining producer IDs and source wording."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    page: int
    element_id: str
    element_ids: list[str] = Field(default_factory=list)
    raw_text: str
    source_text_parts: list[str] = Field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None
    coordinate_space: str | None = None


class KeyFact(BaseModel):
    state: FactState
    value: Any = None
    raw_text: str | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


class CountFact(BaseModel):
    state: FactState
    value: int | None = None


class RequirementCounts(BaseModel):
    by_category: dict[str, int] = Field(default_factory=dict)
    review_required: int


class BOQSummary(BaseModel):
    detected: KeyFact
    pages: list[int] | None = None


class SourceCoverage(BaseModel):
    evidence_reference_count: int
    pages_with_evidence: list[int]
    total_pages: int | None = None
    coverage_ratio: float | None = None


class SummaryDiagnostic(BaseModel):
    code: str
    message: str
    state: FactState = FactState.NEEDS_REVIEW
    evidence: list[EvidenceReference] = Field(default_factory=list)


class TenderSummary(BaseModel):
    contract_version: str = "1.0"
    document_id: str
    identity: dict[str, KeyFact]
    dates: dict[str, KeyFact]
    financial: dict[str, KeyFact]
    structure: dict[str, CountFact]
    boq: BOQSummary
    requirements: RequirementCounts
    missing_or_ambiguous: list[str] = Field(default_factory=list)
    source_coverage: SourceCoverage
    uncertain_fields: list[str] = Field(default_factory=list)
    review_items: list[SummaryDiagnostic] = Field(default_factory=list)
