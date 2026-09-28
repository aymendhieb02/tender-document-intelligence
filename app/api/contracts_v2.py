"""Versioned API envelopes that compose existing domain contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.cdc_analysis.schema import TenderDocument


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


def build_tender_analysis_v2(payload: dict[str, Any], *, workflow: str) -> TenderAnalysisResponseV2:
    """Wrap a successful existing workflow payload without rerunning extraction."""
    tender = TenderDocument.model_validate(payload["tender_document"])
    references = _evidence_references(payload["tender_document"])
    workflow_diagnostics = list(payload.get("diagnostics") or [])
    workflow_diagnostics.extend(
        item["code"]
        for item in payload["tender_document"].get("diagnostics", [])
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    )
    # Preserve order while avoiding repeated codes from multiple evidence paths.
    workflow_diagnostics = list(dict.fromkeys(workflow_diagnostics))

    if workflow == "ministry_boq":
        boq_detected = bool(payload.get("template_detected"))
        boq = ModuleResultV2(
            availability="available" if boq_detected else "unavailable",
            data=payload.get("boq_results") if boq_detected else None,
            reason=None if boq_detected else "supported_template_not_detected",
            diagnostics=workflow_diagnostics if not boq_detected else [],
        )
    else:
        boq = ModuleResultV2(availability="not_run", reason="boq_workflow_not_invoked")

    return TenderAnalysisResponseV2(
        document=DocumentIdentityV2(
            document_id=payload["document_id"],
            document_url=payload["document_url"],
            source_type=payload["source_type"],
            page_count=payload["page_count"],
        ),
        tender_document=tender,
        modules=TenderModulesV2(
            summary=ModuleResultV2(availability="not_implemented", reason="summary_producer_not_implemented"),
            requirements_intelligence=ModuleResultV2(
                availability="not_implemented",
                reason="candidate_requirements_remain_in_tender_document",
            ),
            financial_deadline_intelligence=ModuleResultV2(
                availability="not_implemented", reason="financial_deadline_producer_not_implemented"
            ),
            dossier=ModuleResultV2(availability="not_run", reason="dossier_workflow_not_invoked"),
            compliance=ModuleResultV2(availability="not_implemented", reason="compliance_producer_not_implemented"),
            boq=boq,
            evidence=EvidenceModuleResultV2(
                availability="available" if references else "unavailable",
                data=references or None,
                reason=None if references else "no_evidence_references_available",
            ),
            diagnostics=ModuleResultV2(availability="available", data=workflow_diagnostics),
        ),
        diagnostics=workflow_diagnostics,
    )
