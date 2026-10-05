"""Versioned API envelopes that compose existing domain contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.cdc_analysis.schema import TenderDocument
from app.tender_intelligence_v2 import compose_tender_modules


ModuleAvailability = Literal[
    "available",
    "partial",
    "not_run",
    "not_implemented",
    "not_applicable",
    "unavailable",
]


class StructuredError(BaseModel):
    code: str
    workflow: str
    message: str
    technical_detail: str | None = None
    recoverable: bool
    diagnostics: list[str] = Field(default_factory=list)


class ErrorEnvelopeV1(BaseModel):
    """Typed description of the existing compatible error payload."""

    error: StructuredError


class DocumentIdentityV2(BaseModel):
    document_id: str
    document_url: str
    filename: str | None = None
    source_type: Literal["pdf", "image"]
    page_count: int = Field(ge=1)


class EvidenceReferenceV2(BaseModel):
    """Pointer to source evidence; intentionally excludes copied OCR text."""

    evidence_id: str
    document_id: str
    page_number: int = Field(ge=1)
    element_id: str
    bbox: tuple[float, float, float, float] | None = None
    coordinate_space: str | None = None
    source: str | None = None


class ModuleResultV2(BaseModel):
    availability: ModuleAvailability
    data: Any = None
    reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)


class EvidenceModuleResultV2(ModuleResultV2):
    data: list[EvidenceReferenceV2] | None = None


class FinancialFactV2(BaseModel):
    id: str
    category: str
    raw: str
    normalized: dict[str, Any] | None = None
    status: str
    conflict_group: str | None = None
    evidence: list[EvidenceReferenceV2] = Field(default_factory=list)
    evidence_scope: Literal["matched_source_element", "candidate_context"]
    source_requirement_id: str | None = None
    source_article_id: str | None = None


class TenderModulesV2(BaseModel):
    summary: ModuleResultV2
    requirements_intelligence: ModuleResultV2
    financial_deadline_intelligence: ModuleResultV2
    dossier: ModuleResultV2
    compliance: ModuleResultV2
    boq: ModuleResultV2
    evidence: EvidenceModuleResultV2
    diagnostics: ModuleResultV2


class TenderAnalysisResponseV2(BaseModel):
    contract_version: Literal["2.0"] = "2.0"
    document: DocumentIdentityV2
    tender_document: TenderDocument
    modules: TenderModulesV2
    diagnostics: list[str] = Field(default_factory=list)
    quality_signals: list[dict[str, Any]] = Field(default_factory=list)


def _evidence_references(value: Any) -> list[EvidenceReferenceV2]:
    references: dict[tuple[str, int, str], EvidenceReferenceV2] = {}

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            if {"document_id", "page", "element_id"}.issubset(item):
                document_id = item.get("document_id")
                page = item.get("page")
                element_id = item.get("element_id")
                if isinstance(document_id, str) and isinstance(page, int) and isinstance(element_id, str):
                    key = (document_id, page, element_id)
                    source = item.get("source")
                    if source is None:
                        source_types = item.get("source_element_types") or []
                        source = next((candidate for candidate in source_types if candidate), None)
                    bbox = item.get("bbox")
                    references.setdefault(
                        key,
                        EvidenceReferenceV2(
                            evidence_id=f"{document_id}:{page}:{element_id}",
                            document_id=document_id,
                            page_number=page,
                            element_id=element_id,
                            bbox=tuple(bbox) if bbox is not None else None,
                            coordinate_space=item.get("coordinate_space"),
                            source=source,
                        ),
                    )
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return list(references.values())


def build_tender_analysis_v2(
    payload: dict[str, Any], *, workflow: str, document_result: Any | None = None,
    filename: str | None = None,
) -> TenderAnalysisResponseV2:
    """Compose V2 modules from the existing single-pass producer/analyzer result."""
    tender = TenderDocument.model_validate(payload["tender_document"])
    integrated = compose_tender_modules(
        tender,
        document_result=document_result if document_result is not None else tender,
        filename=filename or str(tender.metadata.get("filename") or ""),
    )
    references = _evidence_references(payload["tender_document"])
    workflow_diagnostics = list(payload.get("diagnostics") or [])
    workflow_diagnostics.extend(
        item["code"]
        for item in payload["tender_document"].get("diagnostics", [])
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    )
    # Preserve order while avoiding repeated codes from multiple evidence paths.
    workflow_diagnostics = list(dict.fromkeys(workflow_diagnostics))

    if payload.get("template_detected"):
        boq = ModuleResultV2(availability="available", data=payload["boq_results"])
    elif workflow == "ministry_boq":
        boq = ModuleResultV2(
            availability="unavailable", reason="supported_template_not_detected",
            diagnostics=workflow_diagnostics,
        )
    else:
        boq = ModuleResultV2(availability="not_run", reason="boq_workflow_not_invoked")

    requirement_items = integrated["requirements"]
    financial_items = integrated["financial_facts"]
    financial_data = [
        FinancialFactV2(
            id=item.id,
            category=item.fact.category,
            raw=item.fact.raw,
            normalized=item.fact.as_dict()["normalized"],
            status=item.fact.status,
            conflict_group=item.fact.conflict_group,
            evidence=[
                EvidenceReferenceV2(
                    evidence_id=f"{ev.document_id}:{ev.page}:{ev.element_id}",
                    document_id=ev.document_id,
                    page_number=ev.page,
                    element_id=ev.element_id,
                    bbox=ev.bbox,
                    coordinate_space=ev.coordinate_space,
                    source=next((source for source in ev.source_element_types if source), None),
                )
                for ev in item.evidence
            ],
            evidence_scope=item.evidence_scope,
            source_requirement_id=item.source_requirement_id,
            source_article_id=item.source_article_id,
        ) for item in financial_items
    ]
    requirements_data = [item.model_dump(mode="json") for item in requirement_items]
    module_diagnostics = integrated["financial_diagnostics"]
    financial_availability: ModuleAvailability = "partial" if module_diagnostics else "available"

    quality_signals = []
    if document_result is not None and hasattr(document_result, "pages"):
        native_pages = sum(not page.diagnostics.ocr_used for page in document_result.pages)
        ocr_pages = sum(page.diagnostics.ocr_used for page in document_result.pages)
        low_ocr_pages = sum(page.diagnostics.ocr_used and any(
            element.confidence is not None and element.confidence < .60 for element in page.elements)
            for page in document_result.pages)
        quality_signals.extend(({"code": "native_pages", "count": native_pages},
                                {"code": "ocr_pages", "count": ocr_pages},
                                {"code": "ocr_low_confidence_pages", "count": low_ocr_pages}))
    if boq.availability == "available":
        documents = [item.get("result", item) for item in (boq.data or [])]
        empty = all(not any(row.get("quantity", {}).get("normalized_value") is not None for row in doc.get("rows", []))
                    for doc in documents)
        quality_signals.append({"code": "boq_empty_template" if empty else "boq_detected", "count": len(documents)})
    elif boq.availability in {"unavailable", "not_run"}:
        quality_signals.append({"code": "boq_unavailable", "count": 0})
    quality_signals.append({"code": "ask_evidence_available", "count": len(references)})
    return TenderAnalysisResponseV2(
        document=DocumentIdentityV2(
            document_id=payload["document_id"],
            document_url=payload["document_url"],
            filename=filename,
            source_type=payload["source_type"],
            page_count=payload["page_count"],
        ),
        tender_document=tender,
        modules=TenderModulesV2(
            summary=ModuleResultV2(
                availability="available", data=integrated["summary"].model_dump(mode="json")
            ),
            requirements_intelligence=ModuleResultV2(
                availability="available", data=requirements_data,
                diagnostics=["machine_interpretations_require_review"] if requirements_data else [],
            ),
            financial_deadline_intelligence=ModuleResultV2(
                availability=financial_availability, data=[item.model_dump(mode="json") for item in financial_data],
                diagnostics=module_diagnostics,
            ),
            dossier=ModuleResultV2(
                availability="partial", data=integrated["dossier"], reason=integrated["dossier_reason"],
            ),
            compliance=ModuleResultV2(availability="unavailable", reason="not_in_wave_1"),
            boq=boq,
            evidence=EvidenceModuleResultV2(
                availability="available" if references else "unavailable",
                data=references or None,
                reason=None if references else "no_evidence_references_available",
            ),
            diagnostics=ModuleResultV2(availability="available", data=workflow_diagnostics),
        ),
        diagnostics=workflow_diagnostics,
        quality_signals=quality_signals,
    )
