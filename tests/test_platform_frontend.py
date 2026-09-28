from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def test_primary_pages_share_the_modular_platform_shell():
    home = client.get("/")
    invoice = client.get("/invoice")
    cdc = client.get("/cdc")
    ministry = client.get("/cdc/male")

    assert all(response.status_code == 200 for response in (home, invoice, cdc, ministry))
    assert "legacyInvoice" not in home.text
    assert "Analyse de facture" in invoice.text
    assert "router.js" in home.text and "router.js" in cdc.text
    assert "affaires locales" in (ROOT / "app/static/app/pages/dashboard.js").read_text(encoding="utf-8").lower()


def test_frontend_adapts_backend_v1_and_does_not_claim_false_pdf_highlights():
    api = (ROOT / "app/static/app/api.js").read_text(encoding="utf-8")
    viewer = (ROOT / "app/static/app/components/document-viewer.js").read_text(encoding="utf-8")
    invoice = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert '"/api/cdc/analyze"' in api
    assert '"/api/cdc/male/analyze"' in api
    assert "payload.boq_results?.[0]?.result" in api
    assert "fetch(url)" in viewer
    assert "if (!normalized || this.root.querySelector(\"iframe\"))" in viewer
    assert 'fetch("/api/invoices/analyze"' in invoice


def test_cdc_views_use_recursive_nodes_and_backend_handoffs_without_fixture_numbers():
    cdc = (ROOT / "app/static/app/pages/cdc-workspace.js").read_text(encoding="utf-8")
    boq = (ROOT / "app/static/app/pages/boq-workspace.js").read_text(encoding="utf-8")

    assert "node.subsections" in cdc and "node.articles" in cdc and "node.clauses" in cdc
    assert 'item.handoff === "boq_agent"' in cdc
    assert '"(?:^|[^\\d])0?5' not in cdc
    assert "Diagnostics CDC et bordereau" in cdc
    assert 'value_origin === "TEMPLATE_INFERRED"' in boq
    assert '"—"' in boq


def test_invoice_upload_contains_no_production_demo_actions():
    page = (ROOT / "app/static/invoice.html").read_text(encoding="utf-8")
    client_js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "data-demo-id" not in page
    assert "/demo-documents/" not in client_js
    assert "Importer une facture" in page


def test_shared_workspace_defines_tablet_and_mobile_layouts():
    shell = (ROOT / "app/static/app/styles/shell.css").read_text(encoding="utf-8")
    workspace = (ROOT / "app/static/app/styles/workspace.css").read_text(encoding="utf-8")
    assert "@media (max-width: 1200px)" in workspace
    assert "@media (max-width: 760px)" in workspace
    assert "grid-template-columns: 1fr" in shell
    assert ".tree-scroll" in workspace and "overflow" in workspace
