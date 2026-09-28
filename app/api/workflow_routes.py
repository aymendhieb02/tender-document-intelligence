from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.document_store import document_store
from app.core.config import settings
from app.core.schemas import ProcessInvoiceResponse
from app.cdc_analysis import CDCAnalyzer
from app.document_intelligence import DocumentProcessor
from app.document_intelligence.schemas import DocumentResult
from app.boq import extract_male_municipal_from_document
from app.invoice.document_result_adapter import DocumentResultInvoiceAdapter
from app.services.pipeline_runner import process_document_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024
BOQ_FAMILY = "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1"


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
    return stored, result


def _document_link(document_id: str) -> str:
    return f"/api/documents/{document_id}"


@router.get("/documents/{document_id}", name="get_uploaded_document")
def get_uploaded_document(document_id: str) -> FileResponse:
    stored = document_store.get(document_id)
    if stored is None:
        raise WorkflowError("document_not_found", "documents", "The document is unavailable or expired.",
                            status_code=404, recoverable=True)
    return FileResponse(stored.path, media_type=stored.media_type, filename=stored.filename)


@router.post("/cdc/analyze")
async def analyze_cdc(file: UploadFile = File(...)) -> dict[str, Any]:
    stored, document = await _process_upload(file, "cdc")
    try:
        tender = CDCAnalyzer().analyze(document)
    except Exception as exc:
        logger.exception("CDC analysis failed")
        raise WorkflowError("cdc_analysis_failed", "cdc", "Tender structure could not be analyzed.",
                            status_code=422, technical_detail=type(exc).__name__, recoverable=True,
                            diagnostics=["evidence_page_mismatch"] if isinstance(exc, ValueError) and "Element page does not match" in str(exc) else []) from exc
    return {
        "document_id": document.document_id,
        "document_url": _document_link(stored.document_id),
        "source_type": document.source_type,
        "page_count": len(document.pages),
        "pages": [{"page_number": page.page_number, "width": page.width, "height": page.height,
                   "coordinate_space": page.coordinate_space} for page in document.pages],
        "tender_document": tender.model_dump(mode="json"),
    }


@router.post("/cdc/male/analyze")
async def analyze_ministry(file: UploadFile = File(...)) -> dict[str, Any]:
    stored, document = await _process_upload(file, "ministry_boq")
    try:
        tender = CDCAnalyzer().analyze(document)
    except Exception as exc:
        logger.exception("CDC analysis for Ministry workflow failed")
        raise WorkflowError("cdc_analysis_failed", "ministry_boq", "Tender structure could not be analyzed.",
                            status_code=422, technical_detail=type(exc).__name__, recoverable=True,
                            diagnostics=["evidence_page_mismatch"] if isinstance(exc, ValueError) and "Element page does not match" in str(exc) else []) from exc

    handoffs = [item for item in tender.detected_special_documents if item.handoff == "boq_agent"]
    physical_pages = {page.page_number for page in document.pages}
    boq_results = []
    diagnostics: list[str] = []
    for handoff in handoffs:
        requested_pages = range(handoff.page_start, handoff.page_end + 1)
        valid_pages = [page_number for page_number in requested_pages if page_number in physical_pages]
        missing_pages = [page_number for page_number in requested_pages if page_number not in physical_pages]
        if missing_pages:
            diagnostics.append("boq_handoff_references_unavailable_physical_page")
        for page_number in valid_pages:
            try:
                result = extract_male_municipal_from_document(document, page_number=page_number)
            except Exception as exc:
                logger.exception("Specialized BOQ extraction failed")
                raise WorkflowError("boq_extraction_failed", "ministry_boq",
                                    "The supported BOQ page could not be extracted.", status_code=422,
                                    technical_detail=type(exc).__name__,
                                    recoverable=True) from exc
            if result.detected:
                boq_results.append({"source_page": page_number, "result": result.model_dump(mode="json")})
            else:
                diagnostics.extend(result.diagnostics)

    detected = bool(boq_results)
    if not handoffs:
        diagnostics.append("cdc_did_not_detect_boq_handoff")
    return {
        "document_id": document.document_id,
        "document_url": _document_link(stored.document_id),
        "source_type": document.source_type,
        "page_count": len(document.pages),
        "tender_document": tender.model_dump(mode="json"),
        "template_detected": detected,
        "template_family": BOQ_FAMILY if detected else None,
        "boq_handoffs": [item.model_dump(mode="json") for item in handoffs],
        "boq_results": boq_results,
        "diagnostics": diagnostics,
    }


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
