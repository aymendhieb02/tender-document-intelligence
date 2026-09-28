from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.document_intelligence import DocumentProcessor
from app.api.contracts_v2 import ErrorEnvelopeV1, TenderAnalysisResponseV2
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PDF = ROOT / "datasets/boq/male_municipal_maintenance_v1/reference/MM_Cahier-des-charges-type-Entretien.pdf"
client = TestClient(app)


def make_pdf(path: Path, lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((40, 45 + index * 28), line)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_application_startup_and_workflow_routes():
    root = client.get("/")
    assert root.status_code == 200
    assert "html" in root.headers["content-type"]
    assert client.get("/health").json()["status"] == "ok"
    routes = client.get("/openapi.json").json()["paths"]
    assert "/api/invoices/analyze" in routes
    assert "/api/cdc/analyze" in routes
    assert "/api/cdc/male/analyze" in routes
    assert "/api/cdc/male/export.csv" in routes
    assert "/api/v2/cdc/analyze" in routes
    assert "/api/v2/cdc/male/analyze" in routes


def test_invalid_upload_has_stable_error_envelope():
    response = client.post("/api/cdc/analyze", files={"file": ("notes.exe", b"bad", "application/octet-stream")})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_upload"
    assert error["workflow"] == "cdc"
    assert "traceback" not in response.text.lower()


def test_v2_cdc_envelope_is_typed_and_does_not_change_v1_payload():
    source = REFERENCE_PDF.read_bytes()
    v1 = client.post("/api/cdc/analyze", files={"file": (REFERENCE_PDF.name, source, "application/pdf")})
    assert v1.status_code == 200, v1.text
    assert "contract_version" not in v1.json()

    response = client.post("/api/v2/cdc/analyze", files={"file": (REFERENCE_PDF.name, source, "application/pdf")})
    assert response.status_code == 200, response.text
    payload = response.json()
    contract = TenderAnalysisResponseV2.model_validate(payload)
    assert contract.contract_version == "2.0"
    assert contract.document.document_id == v1.json()["document_id"]
    assert contract.document.page_count == 30
    assert contract.tender_document.document_id == payload["document"]["document_id"]
    assert contract.modules.summary.availability == "available"
    assert contract.modules.summary.data["document_id"] == contract.tender_document.document_id
    assert contract.modules.requirements_intelligence.availability == "available"
    assert isinstance(contract.modules.requirements_intelligence.data, list)
    assert all(item["review_status"] == "NEEDS_REVIEW"
               for item in contract.modules.requirements_intelligence.data)
    assert contract.modules.financial_deadline_intelligence.availability in {"available", "partial"}
    assert isinstance(contract.modules.financial_deadline_intelligence.data, list)
    assert all(item["id"].startswith("fin-") and item["evidence"]
               for item in contract.modules.financial_deadline_intelligence.data)
    assert contract.modules.dossier.availability == "partial"
    assert contract.modules.dossier.data["grouping"]["status"] == "review"
    assert len(contract.modules.dossier.data["documents"]) == 1
    assert contract.modules.compliance.availability == "unavailable"
    assert contract.modules.compliance.reason == "not_in_wave_1"
    assert contract.modules.boq.availability == "not_run"

    references = contract.modules.evidence.data
    assert references
    reference = references[0].model_dump(mode="json")
    assert {"document_id", "page_number", "element_id", "evidence_id"}.issubset(reference)
    assert "raw_text" not in reference
    assert "pages" not in payload
    assert "document_result" not in payload


def test_v2_ministry_marks_unrecognized_boq_unavailable_without_fake_data(tmp_path):
    data = make_pdf(tmp_path / "ordinary.pdf", ["Ordinary correspondence", "No price schedule here."])
    response = client.post("/api/v2/cdc/male/analyze", files={"file": ("ordinary.pdf", data, "application/pdf")})
    assert response.status_code == 200, response.text
    payload = response.json()
    contract = TenderAnalysisResponseV2.model_validate(payload)
    assert contract.modules.boq.availability == "unavailable"
    assert contract.modules.boq.data is None
    assert contract.modules.boq.reason == "supported_template_not_detected"
    assert "cdc_did_not_detect_boq_handoff" in contract.diagnostics


def test_v2_errors_validate_against_existing_structured_error_contract():
    response = client.post("/api/v2/cdc/analyze", files={"file": ("notes.exe", b"bad", "application/octet-stream")})
    assert response.status_code == 400
    error = ErrorEnvelopeV1.model_validate(response.json()).error
    assert error.code == "invalid_upload"
    assert error.workflow == "cdc"
    assert error.message
    assert error.recoverable is True
    assert isinstance(error.diagnostics, list)
    assert "tender-document-intelligence-" not in response.text


def test_v2_processes_document_once_and_uses_same_result_for_modules(tmp_path, monkeypatch):
    from app.api import workflow_routes

    data = make_pdf(tmp_path / "cdc.pdf", [
        "Cahier des charges", "Le candidat doit fournir une offre valable 60 jours.",
    ])
    original = workflow_routes.DocumentProcessor
    calls = 0

    class CountingProcessor:
        def __init__(self, *args, **kwargs):
            self.delegate = original(*args, **kwargs)

        def process(self, path):
            nonlocal calls
            calls += 1
            return self.delegate.process(path)

    monkeypatch.setattr(workflow_routes, "DocumentProcessor", CountingProcessor)
    response = client.post("/api/v2/cdc/analyze", files={"file": ("CDC.pdf", data, "application/pdf")})
    assert response.status_code == 200, response.text
    payload = TenderAnalysisResponseV2.model_validate(response.json())
    assert calls == 1
    assert payload.modules.summary.availability == "available"
    facts = payload.modules.financial_deadline_intelligence.data
    assert any(fact["category"] == "offer_validity" and fact["normalized"] == {"value": "60", "unit": "DAY"}
               for fact in facts)


def test_cdc_api_processes_reference_and_serves_document():
    source = REFERENCE_PDF.read_bytes()
    response = client.post("/api/cdc/analyze", files={"file": (REFERENCE_PDF.name, source, "application/pdf")})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["page_count"] == 30
    assert payload["document_id"] == payload["tender_document"]["document_id"]
    assert any(item["handoff"] == "boq_agent" for item in payload["tender_document"]["detected_special_documents"])
    retrieved = client.get(payload["document_url"])
    assert retrieved.status_code == 200
    assert retrieved.content == source
    assert retrieved.headers["content-type"] == "application/pdf"
    assert retrieved.headers["content-disposition"].startswith("inline;")
    page = client.get(f"{payload['document_url']}/pages/3.png")
    assert page.status_code == 200
    assert page.headers["content-type"] == "image/png"
    assert page.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert "D:\\" not in response.text


def test_ministry_api_recognizes_empty_template_without_fabricating_amounts():
    source = REFERENCE_PDF.read_bytes()
    response = client.post("/api/cdc/male/analyze", files={"file": (REFERENCE_PDF.name, source, "application/pdf")})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["template_detected"] is True
    assert payload["template_family"] == "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1"
    assert len(payload["boq_results"]) == 1
    boq = payload["boq_results"][0]["result"]
    assert len(boq["rows"]) == 5
    assert all(row["source_page"] == 25 for row in boq["rows"])
    for row in boq["rows"]:
        for field in ("quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"):
            assert row[field]["normalized_value"] is None
        if row["article"]["value_origin"] == "TEMPLATE_INFERRED":
            assert row["article"]["evidence"] == []

    v2 = client.post("/api/v2/cdc/male/analyze", files={"file": (REFERENCE_PDF.name, source, "application/pdf")})
    assert v2.status_code == 200, v2.text
    v2_contract = TenderAnalysisResponseV2.model_validate(v2.json())
    assert v2_contract.modules.boq.availability == "available"
    assert len(v2_contract.modules.boq.data) == 1
    assert v2_contract.modules.boq.data[0]["result"]["rows"]


def test_ministry_csv_export_keeps_blank_amounts_empty_and_utf8():
    source = REFERENCE_PDF.read_bytes()
    response = client.post("/api/cdc/male/export.csv", files={"file": (REFERENCE_PDF.name, source, "application/pdf")})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv; charset=utf-8")
    assert 'filename="boq-export.csv"' in response.headers["content-disposition"]
    text = response.content.decode("utf-8")
    assert "item_number,designation,unit,quantity,unit_price_ht,total_ht,unit_price_ttc,total_ttc,status,page" in text
    rows = list(csv.DictReader(StringIO(text)))
    assert len(rows) == 5
    assert rows[0]["item_number"] == "01"
    assert all(row["quantity"] == "" and row["unit_price_ht"] == "" for row in rows)


def test_unrecognized_ministry_template_is_structured_not_server_error(tmp_path):
    data = make_pdf(tmp_path / "ordinary.pdf", ["Ordinary correspondence", "No BOQ or price schedule here."])
    response = client.post("/api/cdc/male/analyze", files={"file": ("ordinary.pdf", data, "application/pdf")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["template_detected"] is False
    assert payload["template_family"] is None
    assert payload["boq_results"] == []
    assert "cdc_did_not_detect_boq_handoff" in payload["diagnostics"]


def test_application_rejects_out_of_range_evidence_without_creating_a_physical_page(monkeypatch):
    document = DocumentProcessor(mode="native", use_cache=False).process(REFERENCE_PDF)
    first = document.pages[0]
    invalid_element = first.elements[0].model_copy(update={"page_number": 31})
    invalid_page = first.model_copy(update={"elements": [invalid_element, *first.elements[1:]]})
    invalid = document.model_copy(update={"pages": [invalid_page, *document.pages[1:]]})

    class Processor:
        def process(self, path):
            return invalid

    from app.api import workflow_routes
    monkeypatch.setattr(workflow_routes, "DocumentProcessor", Processor)
    response = client.post("/api/cdc/analyze", files={"file": (REFERENCE_PDF.name, REFERENCE_PDF.read_bytes(), "application/pdf")})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "cdc_analysis_failed"
    assert "evidence_page_mismatch" in error["diagnostics"]
    assert "31" not in response.text


def test_invoice_api_uses_document_result_without_a_second_full_ocr_pass(tmp_path, monkeypatch):
    data = make_pdf(tmp_path / "invoice.pdf", [
        "ACME Services", "Invoice Number: INV-TEST-001", "Invoice Date: 2026-06-10",
        "Subtotal 250.00", "VAT 20% 50.00", "Total Amount USD 300.00",
    ])
    from app.services.ocr_engine import OCREngine
    monkeypatch.setattr(OCREngine, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy full OCR must not run")))
    response = client.post("/api/invoices/analyze", files={"file": ("invoice.pdf", data, "application/pdf")})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["detected_fields"]["invoice_number"] == "INV-TEST-001"
    assert payload["detected_fields"]["amount_ht"] == 250.0
    assert payload["detected_fields"]["amount_ttc"] == 300.0
    assert payload["validation"]["status"] in {"valid", "needs_review", "invalid"}
    assert payload["document_id"]
    assert client.get(payload["document_url"]).content == data


def test_legacy_invoice_route_delegates_to_the_contract_boundary(tmp_path):
    data = make_pdf(tmp_path / "invoice.pdf", ["Invoice Number: LEGACY-001", "Total TTC 10.00 TND"])
    response = client.post("/process-invoice", files={"file": ("invoice.pdf", data, "application/pdf")})
    assert response.status_code == 200, response.text
    assert response.json()["detected_fields"]["invoice_number"] == "LEGACY-001"


def test_corrupt_document_returns_sanitized_processing_error():
    response = client.post("/api/cdc/analyze", files={"file": ("broken.pdf", b"not a PDF", "application/pdf")})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "document_processing_failed"
    assert error["technical_detail"]
    assert "tender-document-intelligence-" not in response.text
    assert "traceback" not in response.text.lower()
