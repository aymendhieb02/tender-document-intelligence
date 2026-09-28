from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field



class BoundingBox(BaseModel):
    """BOQ evidence geometry normalized to the public PageResult coordinates."""
    x1: float = 0
    y1: float = 0
    x2: float = 0
    y2: float = 0


class SourceEvidence(BaseModel):
    source_page: int
    source_bbox: BoundingBox | None = None
    raw_text: str
    ocr_confidence: float | None = None
    source: str | None = None
    element_ids: list[str] = Field(default_factory=list)


class ParsedValue(BaseModel):
    raw_value: str | None = None
    normalized_value: Any = None
    parse_status: Literal["PARSED", "MISSING", "AMBIGUOUS", "INVALID"] = "MISSING"
    value_origin: Literal["OBSERVED", "TEMPLATE_INFERRED", "DERIVED", "MISSING"] = "MISSING"
    reason: str | None = None
    evidence: list[SourceEvidence] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    rule: str
    status: Literal["VALID", "NEEDS_REVIEW", "INVALID", "NOT_CHECKABLE"]
    expected: str | None = None
    observed: str | None = None
    difference: str | None = None
    reason: str | None = None


class BOQRow(BaseModel):
    article: ParsedValue = Field(default_factory=ParsedValue)
    designation: ParsedValue = Field(default_factory=ParsedValue)
    unit: ParsedValue = Field(default_factory=ParsedValue)
    quantity: ParsedValue = Field(default_factory=ParsedValue)
    unit_price_ht: ParsedValue = Field(default_factory=ParsedValue)
    total_ht: ParsedValue = Field(default_factory=ParsedValue)
    unit_price_ttc: ParsedValue = Field(default_factory=ParsedValue)
    total_ttc: ParsedValue = Field(default_factory=ParsedValue)
    validation_status: Literal["VALID", "NEEDS_REVIEW", "INVALID", "NOT_CHECKABLE"] = "NOT_CHECKABLE"
    validation: list[ValidationCheck] = Field(default_factory=list)
    ancillary_evidence: list[SourceEvidence] = Field(default_factory=list)
    source_page: int | None = None
    source_bbox: BoundingBox | None = None


class BOQTotals(BaseModel):
    total_ht: ParsedValue = Field(default_factory=ParsedValue)
    vat: ParsedValue = Field(default_factory=ParsedValue)
    vat_rate: ParsedValue = Field(default_factory=ParsedValue)
    total_ttc: ParsedValue = Field(default_factory=ParsedValue)


class BOQDocument(BaseModel):
    document_id: str | None = None
    extractor_family: str
    consultation_reference: ParsedValue = Field(default_factory=ParsedValue)
    project_title: ParsedValue = Field(default_factory=ParsedValue)
    lot_number: ParsedValue = Field(default_factory=ParsedValue)
    currency: str = "TND"
    rows: list[BOQRow] = Field(default_factory=list)
    table_bbox: BoundingBox | None = None
    column_mapping: dict[str, str] = Field(default_factory=dict)
    totals: BOQTotals = Field(default_factory=BOQTotals)
    validation: list[ValidationCheck] = Field(default_factory=list)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    review_status: Literal["READY", "NEEDS_REVIEW", "NOT_CHECKABLE"] = "NOT_CHECKABLE"
    detected: bool = False
    diagnostics: list[str] = Field(default_factory=list)
    detection: dict[str, Any] = Field(default_factory=dict)
