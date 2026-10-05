from __future__ import annotations

import logging
import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import Response
import fitz

from app.api.document_store import document_store
from app.api.contracts_v2 import TenderAnalysisResponseV2, build_tender_analysis_v2
from app.core.config import settings
from app.core.schemas import ProcessInvoiceResponse
from app.cdc_analysis import CDCAnalyzer
from app.document_intelligence import DocumentProcessor
from app.document_intelligence.schemas import DocumentResult
from app.boq import BOQDocument, export_boq_csv, extract_boq_candidates
from app.boq.pricing import PricingUpdate, build_pricing_draft, pricing_csv, source_fingerprint
from app.invoice.document_result_adapter import DocumentResultInvoiceAdapter
from app.ask_tender.service import AskRequest, AskResponse, answer_question
from app.services.pipeline_runner import process_document_file
from app.cdc_analysis.schema import TenderDocument

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


class WorkflowError(Exception):
    def __init__(self, code: str, workflow: str, message: str, *, status_code: int = 422,
                 technical_detail: str | None = None, recoverable: bool = False,
                 diagnostics: list[str] | None = None) -> None:
        self.code = code
        self.workflow = workflow
        self.message = message
        self.status_code = status_code
        self.technical_detail = technical_detail
        self.recoverable = recoverable
        self.diagnostics = diagnostics or []
        super().__init__(message)

    def as_payload(self) -> dict[str, Any]:
        return {"error": {
            "code": self.code, "workflow": self.workflow, "message": self.message,
            "technical_detail": self.technical_detail, "recoverable": self.recoverable,
            "diagnostics": self.diagnostics,
        }}


async def _process_upload(file: UploadFile, workflow: str):
    started = perf_counter()
    try:
        stored = await document_store.save_upload(file, max_bytes=MAX_UPLOAD_BYTES)
    except ValueError as exc:
        raise WorkflowError("invalid_upload", workflow, str(exc), status_code=400,
                            technical_detail=str(exc), recoverable=True) from exc
    try:
        result = DocumentProcessor().process(stored.path)
    except Exception as exc:
        logger.exception("Document processing failed (%s)", workflow)
        raise WorkflowError("document_processing_failed", workflow,
                            "The document could not be processed.", status_code=422,
                            technical_detail=type(exc).__name__, recoverable=True) from exc
    if not result.pages:
        raise WorkflowError("empty_document", workflow, "No physical pages were produced.", status_code=422)
    logger.info("Tender timing workflow=%s stage=document_intelligence total_ms=%.1f timings_ms=%s",
                workflow, result.diagnostics.processing_ms, result.diagnostics.timings_ms)
    logger.info("Tender timing workflow=%s stage=upload_to_document_result total_ms=%.1f",
                workflow, (perf_counter() - started) * 1000)
    return stored, result


def _document_link(document_id: str) -> str:
    return f"/api/documents/{document_id}"


@router.get("/documents/{document_id}", name="get_uploaded_document")
def get_uploaded_document(document_id: str) -> FileResponse:
    stored = document_store.get(document_id)
    if stored is None:
        raise WorkflowError("document_not_found", "documents", "The document is unavailable or expired.",
                            status_code=404, recoverable=True)
    # Source documents are embedded in the CDC workspace and must be renderable
    # by the browser PDF viewer. `attachment` forces downloads and prevents this.
    return FileResponse(stored.path, media_type=stored.media_type,
                        filename=stored.filename, content_disposition_type="inline")


@router.get("/documents/{document_id}/pages/{page_number}.png", name="render_uploaded_document_page")
def render_uploaded_document_page(document_id: str, page_number: int, width: int = 1200) -> Response:
    stored = document_store.get(document_id)
    if stored is None:
        raise WorkflowError("document_not_found", "documents", "The document is unavailable or expired.",
                            status_code=404, recoverable=True)
    if stored.media_type != "application/pdf":
        raise WorkflowError("unsupported_document", "documents", "Page rendering is available for PDF documents.",
                            status_code=415)
    try:
        with fitz.open(stored.path) as source:
            if page_number < 1 or page_number > source.page_count:
                raise WorkflowError("page_not_found", "documents", "The requested page is unavailable.",
                                    status_code=404)
            page = source[page_number - 1]
            scale = max(0.5, min(3.0, max(1, min(width, 2400)) / page.rect.width))
            png = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("png")
    except WorkflowError:
        raise
    except Exception as exc:
        logger.exception("Source PDF page rendering failed")
        raise WorkflowError("document_render_failed", "documents", "The source page could not be rendered.",
                            status_code=422, recoverable=True) from exc
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


async def _run_cdc_upload(file: UploadFile) -> tuple[dict[str, Any], Any, Any]:
    started = perf_counter()
    stored, document = await _process_upload(file, "cdc")
    try:
        cdc_started = perf_counter()
        tender = CDCAnalyzer().analyze(document)
        logger.info("Tender timing workflow=cdc stage=cdc_analysis total_ms=%.1f", (perf_counter() - cdc_started) * 1000)
    except Exception as exc:
        logger.exception("CDC analysis failed")
        raise WorkflowError("cdc_analysis_failed", "cdc", "Tender structure could not be analyzed.",
                            status_code=422, technical_detail=type(exc).__name__, recoverable=True,
                            diagnostics=["evidence_page_mismatch"] if isinstance(exc, ValueError) and "Element page does not match" in str(exc) else []) from exc
    payload = {
        "document_id": document.document_id,
        "document_url": _document_link(stored.document_id),
        "source_type": document.source_type,
        "page_count": len(document.pages),
        "pages": [{"page_number": page.page_number, "width": page.width, "height": page.height,
                   "coordinate_space": page.coordinate_space} for page in document.pages],
        "tender_document": tender.model_dump(mode="json"),
    }
    boq_started = perf_counter()
    candidates = extract_boq_candidates(document)
    payload["boq_results"] = [
        {"source_page": item.rows[0].source_page, "result": item.model_dump(mode="json")}
        for item in candidates
    ]
    payload["template_detected"] = bool(candidates)
    logger.info("Tender timing workflow=cdc stage=boq_detection total_ms=%.1f detected=%s",
                (perf_counter() - boq_started) * 1000, bool(candidates))
    document_store.save_analysis(stored.document_id, workflow="cdc",
                                 tender_document=tender.model_dump(mode="json"), response={})
    logger.info("Tender timing workflow=cdc stage=workflow_total total_ms=%.1f", (perf_counter() - started) * 1000)
    return payload, stored, document


@router.post("/cdc/analyze")
async def analyze_cdc(file: UploadFile = File(...)) -> dict[str, Any]:
    payload, _, _ = await _run_cdc_upload(file)
    return payload


async def _run_ministry_upload(file: UploadFile) -> tuple[dict[str, Any], Any, Any]:
    started = perf_counter()
    stored, document = await _process_upload(file, "ministry_boq")
    try:
        cdc_started = perf_counter()
        tender = CDCAnalyzer().analyze(document)
        logger.info("Tender timing workflow=ministry_boq stage=cdc_analysis total_ms=%.1f", (perf_counter() - cdc_started) * 1000)
    except Exception as exc:
        logger.exception("CDC analysis for Ministry workflow failed")
        raise WorkflowError("cdc_analysis_failed", "ministry_boq", "Tender structure could not be analyzed.",
                            status_code=422, technical_detail=type(exc).__name__, recoverable=True,
                            diagnostics=["evidence_page_mismatch"] if isinstance(exc, ValueError) and "Element page does not match" in str(exc) else []) from exc

    handoffs = [item for item in tender.detected_special_documents if item.handoff == "boq_agent"]
    boq_results = []
    diagnostics: list[str] = []
    boq_started = perf_counter()
    physical_pages = {page.page_number for page in document.pages}
    if any(page_number not in physical_pages for handoff in handoffs
           for page_number in range(handoff.page_start, handoff.page_end + 1)):
        diagnostics.append("boq_handoff_references_unavailable_physical_page")
    try:
        boq_results = [{"source_page": item.rows[0].source_page, "result": item.model_dump(mode="json")}
                       for item in extract_boq_candidates(document)]
    except Exception as exc:
        logger.exception("BOQ extraction failed")
        raise WorkflowError("boq_extraction_failed", "ministry_boq",
                            "The BOQ candidate could not be extracted.", status_code=422,
                            technical_detail=type(exc).__name__, recoverable=True) from exc

    detected = bool(boq_results)
    logger.info("Tender timing workflow=ministry_boq stage=boq_detection total_ms=%.1f handoffs=%s detected=%s",
                (perf_counter() - boq_started) * 1000, len(handoffs), detected)
    if not handoffs:
        diagnostics.append("cdc_did_not_detect_boq_handoff")
    payload = {
        "document_id": document.document_id,
        "document_url": _document_link(stored.document_id),
        "source_type": document.source_type,
        "page_count": len(document.pages),
        "tender_document": tender.model_dump(mode="json"),
        "template_detected": detected,
        "template_family": boq_results[0]["result"]["extractor_family"] if detected else None,
        "boq_handoffs": [item.model_dump(mode="json") for item in handoffs],
        "boq_results": boq_results,
        "diagnostics": diagnostics,
    }
    document_store.save_analysis(stored.document_id, workflow="ministry_boq",
                                 tender_document=tender.model_dump(mode="json"), response={})
    logger.info("Tender timing workflow=ministry_boq stage=workflow_total total_ms=%.1f", (perf_counter() - started) * 1000)
    return payload, stored, document


@router.post("/cdc/male/analyze")
async def analyze_ministry(file: UploadFile = File(...)) -> dict[str, Any]:
    payload, _, _ = await _run_ministry_upload(file)
    return payload


@router.post("/cdc/male/export.csv", name="export_ministry_boq_csv")
async def export_ministry_boq_csv(file: UploadFile = File(...)) -> Response:
    """Analyze a Ministry tender and download any recognized BOQ rows as UTF-8 CSV."""
    payload, _, _ = await _run_ministry_upload(file)
    documents = [BOQDocument.model_validate(item["result"]) for item in payload["boq_results"]]
    return Response(content=export_boq_csv(documents), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="boq-export.csv"'})


@router.post("/v2/cdc/analyze", response_model=TenderAnalysisResponseV2)
async def analyze_cdc_v2(file: UploadFile = File(...)) -> TenderAnalysisResponseV2:
    """Versioned envelope over the existing single-pass deterministic CDC workflow."""
    payload, stored, document = await _run_cdc_upload(file)
    started = perf_counter()
    response = build_tender_analysis_v2(payload, workflow="cdc", document_result=document,
                                        filename=stored.filename)
    document_store.save_analysis(stored.document_id, workflow="cdc",
                                 tender_document=response.tender_document.model_dump(mode="json"),
                                 response=response.model_dump(mode="json"))
    logger.info("Tender timing workflow=cdc stage=response_build total_ms=%.1f", (perf_counter() - started) * 1000)
    return response


@router.post("/v2/cdc/male/analyze", response_model=TenderAnalysisResponseV2)
async def analyze_ministry_v2(file: UploadFile = File(...)) -> TenderAnalysisResponseV2:
    """Versioned envelope over the existing Ministry/BOQ workflow."""
    payload, stored, document = await _run_ministry_upload(file)
    started = perf_counter()
    response = build_tender_analysis_v2(payload, workflow="ministry_boq", document_result=document,
                                        filename=stored.filename)
    document_store.save_analysis(stored.document_id, workflow="ministry_boq",
                                 tender_document=response.tender_document.model_dump(mode="json"),
                                 response=response.model_dump(mode="json"))
    logger.info("Tender timing workflow=ministry_boq stage=response_build total_ms=%.1f", (perf_counter() - started) * 1000)
    return response


@router.get("/v2/cdc")
def list_tender_results() -> list[dict]:
    """Return compact metadata for previously analyzed local tenders."""
    return document_store.list_analyses()


@router.delete("/v2/cdc/{document_id}")
def delete_tender_result(document_id: str) -> dict:
    if not document_store.delete_analysis(document_id):
        raise WorkflowError("analysis_not_found", "cdc", "The saved analysis is unavailable.",
                            status_code=404, recoverable=True)
    return {"document_id": document_id, "deleted": True}


class FactReviewUpdate(BaseModel):
    status: str
    corrected_value: str | None = Field(default=None, max_length=1000)


def _review_facts(saved: dict) -> list[dict]:
    response = TenderAnalysisResponseV2.model_validate(saved["response"])
    summary = response.modules.summary.data or {}
    identity = summary.get("identity", {}) if isinstance(summary, dict) else {}
    facts = []
    for key in ("title", "reference", "contracting_organization"):
        item = identity.get(key)
        if isinstance(item, dict) and (item.get("value") or item.get("raw_text")):
            facts.append({"key": f"identity:{key}", "category": key,
                          "machine_value": item.get("value") or item.get("raw_text"),
                          "evidence": item.get("evidence") or item.get("source_evidence") or []})
    for item in response.modules.financial_deadline_intelligence.data or []:
        if isinstance(item, dict) and item.get("id"):
            facts.append({"key": f"financial:{item['id']}", "category": item.get("category"),
                          "machine_value": item.get("raw"), "evidence": item.get("evidence") or []})
    return facts


def _review_context(document_id: str) -> tuple[list[dict], dict]:
    saved = document_store.get_analysis(document_id)
    if saved is None:
        raise WorkflowError("analysis_not_found", "review", "The saved analysis is unavailable.",
                            status_code=404, recoverable=True)
    try:
        facts = _review_facts(saved)
    except Exception as exc:
        raise WorkflowError("saved_analysis_invalid", "review", "The saved analysis is invalid.",
                            status_code=422, recoverable=True) from exc
    return facts, document_store.get_review(document_id)


def _review_view(facts: list[dict], saved_review: dict) -> dict:
    records = saved_review.get("facts", {})
    result = []
    for fact in facts:
        fingerprint = hashlib.sha256(json.dumps(fact, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        record = records.get(fact["key"], {})
        if record.get("source_fingerprint") != fingerprint:
            record = {}
        result.append({**fact, "source_fingerprint": fingerprint,
                       "status": record.get("status", "unreviewed"),
                       "corrected_value": record.get("corrected_value"),
                       "updated_at": record.get("updated_at")})
    return {"schema_version": 1, "facts": result}


@router.get("/v2/cdc/{document_id}/review")
def get_tender_review(document_id: str) -> dict:
    facts, review = _review_context(document_id)
    return _review_view(facts, review)


@router.put("/v2/cdc/{document_id}/review/{fact_key:path}")
def save_tender_review(document_id: str, fact_key: str, update: FactReviewUpdate) -> dict:
    facts, review = _review_context(document_id)
    current = next((item for item in _review_view(facts, review)["facts"] if item["key"] == fact_key), None)
    if current is None:
        raise WorkflowError("review_fact_not_found", "review", "The fact is unavailable.",
                            status_code=404, recoverable=True)
    if update.status not in {"unreviewed", "approved", "corrected"} or (
            update.status == "corrected" and not (update.corrected_value or "").strip()) or (
            update.status != "corrected" and update.corrected_value):
        raise WorkflowError("review_invalid", "review", "The review status or correction is invalid.",
                            status_code=422, recoverable=True)
    records = review.get("facts", {})
    records[fact_key] = {"source_fingerprint": current["source_fingerprint"],
                         "status": update.status,
                         "corrected_value": update.corrected_value.strip() if update.status == "corrected" else None,
                         "updated_at": datetime.now(timezone.utc).isoformat()}
    document_store.save_review(document_id, {"schema_version": 1, "facts": records})
    return next(item for item in _review_view(facts, {"facts": records})["facts"] if item["key"] == fact_key)


@router.get("/v2/cdc/{document_id}", response_model=TenderAnalysisResponseV2)
def get_tender_result(document_id: str) -> TenderAnalysisResponseV2:
    """Reload a completed local analysis without parsing or OCRing its source again."""
    saved = document_store.get_analysis(document_id)
    if saved is None:
        raise WorkflowError("analysis_not_found", "cdc", "The saved analysis is unavailable.",
                            status_code=404, recoverable=True)
    try:
        return TenderAnalysisResponseV2.model_validate(saved["response"])
    except Exception as exc:
        logger.exception("Saved tender analysis could not be restored")
        raise WorkflowError("saved_analysis_invalid", "cdc", "The saved analysis could not be restored.",
                            status_code=422, technical_detail=type(exc).__name__, recoverable=True) from exc


@router.get("/v2/cdc/{document_id}/boq.csv")
def export_saved_boq_csv(document_id: str) -> Response:
    saved = document_store.get_analysis(document_id)
    if saved is None:
        raise WorkflowError("analysis_not_found", "boq", "The saved analysis is unavailable.",
                            status_code=404, recoverable=True)
    result = TenderAnalysisResponseV2.model_validate(saved["response"])
    if result.modules.boq.availability != "available" or not result.modules.boq.data:
        raise WorkflowError("boq_unavailable", "boq", "A supported BOQ was not extracted from this document.",
                            status_code=404, recoverable=True)
    documents = [BOQDocument.model_validate(item.get("result", item)) for item in result.modules.boq.data]
    return Response(content=export_boq_csv(documents), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="boq-export.csv"'})


def _pricing_context(document_id: str, boq_index: int) -> tuple[BOQDocument, dict | None]:
    saved = document_store.get_analysis(document_id)
    if saved is None:
        raise WorkflowError("analysis_not_found", "boq_pricing", "L'analyse enregistrée est introuvable.",
                            status_code=404, recoverable=True)
    try:
        response = TenderAnalysisResponseV2.model_validate(saved["response"])
        data = response.modules.boq.data if response.modules.boq.availability == "available" else None
        if data is None or boq_index < 0 or boq_index >= len(data):
            raise IndexError("BOQ index unavailable")
        boq = BOQDocument.model_validate(data[boq_index].get("result", data[boq_index]))
    except IndexError as exc:
        raise WorkflowError("boq_unavailable", "boq_pricing", "Ce bordereau est indisponible.",
                            status_code=404, recoverable=True) from exc
    except Exception as exc:
        raise WorkflowError("saved_analysis_invalid", "boq_pricing", "Le bordereau enregistré est illisible.",
                            status_code=422, recoverable=True) from exc
    pricing = document_store.get_pricing(document_id, boq_index)
    if pricing and pricing.get("source_fingerprint") != source_fingerprint(boq):
        raise WorkflowError("pricing_source_changed", "boq_pricing",
                            "Le bordereau source a changé; le brouillon doit être revu.",
                            status_code=409, recoverable=True)
    return boq, pricing


def _pricing_result(document_id: str, boq_index: int, boq: BOQDocument, pricing: dict | None) -> dict:
    try:
        update = PricingUpdate.model_validate(pricing["inputs"]) if pricing else PricingUpdate()
        return build_pricing_draft(boq, document_id, boq_index, update,
                                   updated_at=pricing.get("updated_at") if pricing else None)
    except (ValueError, KeyError, TypeError) as exc:
        raise WorkflowError("pricing_invalid", "boq_pricing", "Le brouillon de chiffrage est invalide.",
                            status_code=422, recoverable=True) from exc


@router.get("/v2/cdc/{document_id}/boq/{boq_index}/pricing")
def get_boq_pricing(document_id: str, boq_index: int) -> dict:
    boq, pricing = _pricing_context(document_id, boq_index)
    return _pricing_result(document_id, boq_index, boq, pricing)


@router.put("/v2/cdc/{document_id}/boq/{boq_index}/pricing")
def save_boq_pricing(document_id: str, boq_index: int, update: PricingUpdate) -> dict:
    boq, _ = _pricing_context(document_id, boq_index)
    updated_at = datetime.now(timezone.utc).isoformat()
    try:
        draft = build_pricing_draft(boq, document_id, boq_index, update, updated_at=updated_at)
    except ValueError as exc:
        raise WorkflowError("pricing_invalid", "boq_pricing", str(exc),
                            status_code=422, recoverable=True) from exc
    document_store.save_pricing(document_id, boq_index, {
        "schema_version": 1, "source_fingerprint": draft["source_fingerprint"],
        "draft_id": draft["draft_id"], "updated_at": updated_at,
        "status": draft["status"], "priced_rows": draft["priced_rows"],
        "total_rows": draft["total_rows"], "inputs": update.model_dump(mode="json"),
    })
    return draft


@router.get("/v2/cdc/{document_id}/boq/{boq_index}/pricing.csv")
def export_boq_pricing(document_id: str, boq_index: int) -> Response:
    boq, pricing = _pricing_context(document_id, boq_index)
    draft = _pricing_result(document_id, boq_index, boq, pricing)
    return Response(content=pricing_csv(draft), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="boq-pricing.csv"'})


@router.post("/v2/cdc/{document_id}/ask", response_model=AskResponse)
def ask_tender_v2(document_id: str, request: AskRequest) -> AskResponse:
    """Ask a single evidence-grounded question about a previously uploaded tender."""
    stored = document_store.get(document_id)
    if stored is None:
        raise WorkflowError("document_not_found", "ask_tender", "The document is unavailable or expired.",
                            status_code=404, recoverable=True)
    try:
        saved = document_store.get_analysis(document_id)
        if saved is not None:
            tender = TenderDocument.model_validate(saved["tender_document"])
        else:
            # Recover source-only records from before the structured record was written.
            document_result = DocumentProcessor().process(stored.path)
            tender = CDCAnalyzer().analyze(document_result)
            try:
                document_store.save_analysis(document_id, workflow="cdc",
                                             tender_document=tender.model_dump(mode="json"), response={})
            except OSError:
                logger.warning("Recovered Ask Tender result could not be persisted for %s", document_id)
    except Exception as exc:
        logger.exception("Ask Tender source analysis failed")
        raise WorkflowError("cdc_analysis_failed", "ask_tender", "Tender evidence could not be analyzed.",
                            status_code=422, technical_detail=type(exc).__name__, recoverable=True) from exc
    return answer_question(tender, request.question)


@router.post("/invoices/analyze", response_model=ProcessInvoiceResponse)
async def analyze_invoice(file: UploadFile = File(...)) -> ProcessInvoiceResponse:
    stored, document_result = await _process_upload(file, "invoice")
    try:
        adapter = DocumentResultInvoiceAdapter(document_result)
        result = process_document_file(
            stored.path,
            original_filename=stored.filename,
            ocr_engine=adapter,
            include_preview=True,
            persist_erp_json=False,
        )
    except ValueError as exc:
        raise WorkflowError("invoice_extraction_failed", "invoice",
                            "Invoice extraction did not produce usable results.", status_code=422,
                            technical_detail=type(exc).__name__, recoverable=True) from exc
    except Exception as exc:
        logger.exception("Invoice extraction failed")
        raise WorkflowError("invoice_extraction_failed", "invoice", "Invoice extraction failed.",
                            status_code=422, technical_detail=type(exc).__name__,
                            recoverable=True) from exc
    payload = result.model_dump(mode="json")
    payload.update({"document_id": document_result.document_id,
                    "document_url": _document_link(stored.document_id)})
    return ProcessInvoiceResponse.model_validate(payload)
