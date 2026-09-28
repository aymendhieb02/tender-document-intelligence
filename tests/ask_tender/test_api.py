from fastapi.testclient import TestClient

from app.api.document_store import StoredDocument, document_store
from app.ask_tender.service import AskResponse
from app.main import app
from app.cdc_analysis.schema import TenderDocument


def test_v2_ask_endpoint_contract_and_unknown_document(monkeypatch, tmp_path):
    from app.api import workflow_routes
    source = tmp_path / "tender.pdf"
    source.write_bytes(b"private source")
    stored = StoredDocument("ask-test-id", source, "tender.pdf", "application/pdf")
    monkeypatch.setattr(document_store, "get", lambda document_id: stored if document_id == stored.document_id else None)

    class Processor:
        def process(self, path): return object()
    class Analyzer:
        def analyze(self, result): return TenderDocument(document_id="ask-test-id")
    monkeypatch.setattr(workflow_routes, "DocumentProcessor", Processor)
    monkeypatch.setattr(workflow_routes, "CDCAnalyzer", Analyzer)
    monkeypatch.setattr(workflow_routes, "answer_question", lambda tender, question: AskResponse(
        answer="The information was not found in the analyzed tender.", status="insufficient_evidence",
        evidence=[], backend="deterministic"))

    client = TestClient(app)
    response = client.post("/api/v2/cdc/ask-test-id/ask", json={"question": "What is the deadline?"})
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_evidence"
    assert response.json()["evidence"] == []
    assert str(tmp_path) not in response.text
    missing = client.post("/api/v2/cdc/missing/ask", json={"question": "Deadline?"})
    assert missing.status_code == 404
