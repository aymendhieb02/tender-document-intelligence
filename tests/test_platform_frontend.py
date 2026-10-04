from pathlib import Path
from html.parser import HTMLParser
import json
import subprocess

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


def test_frontend_adapts_backend_v2_and_does_not_claim_false_pdf_highlights():
    api = (ROOT / "app/static/app/api.js").read_text(encoding="utf-8")
    viewer = (ROOT / "app/static/app/components/document-viewer.js").read_text(encoding="utf-8")
    invoice = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert '"/api/v2/cdc/analyze"' in api
    assert '"/api/v2/cdc/male/analyze"' in api
    assert '${encodeURIComponent(documentId)}/ask' in api
    assert 'document_store_id: storedDocumentId(payload.document.document_url)' in api
    assert "payload.boq_results?.[0]?.result" in api
    assert "/pages/${this.page}.png" in viewer
    assert "this.sourceUrl" in viewer and "physicalPageForEvidence(evidence)" in viewer
    assert 'this.page = Math.max(1, Math.min(maximum, page || 1));' in viewer
    assert "renderWidth()" in viewer and "sizeSourceImage(image)" in viewer
    assert "this.setEvidence(this.evidence);" not in viewer.split("goToPage(page)", 1)[1].split("refreshSource()", 1)[0]
    assert "if (!normalized || this.sourceUrl || this.root.querySelector(\"iframe\"))" in viewer
    assert 'fetch("/api/invoices/analyze"' in invoice


def test_tender_workspace_uses_real_v2_modules_and_truthful_empty_states():
    api = (ROOT / "app/static/app/api.js").read_text(encoding="utf-8")
    cdc = (ROOT / "app/static/app/pages/cdc-workspace.js").read_text(encoding="utf-8")
    boq = (ROOT / "app/static/app/pages/boq-workspace.js").read_text(encoding="utf-8")
    assert 'payload.contract_version === "2.0"' in api
    assert 'payload.modules?.summary?.data' in cdc
    assert 'payload.modules?.requirements_intelligence?.data' in cdc
    assert 'payload.modules?.financial_deadline_intelligence' in cdc
    assert 'payload.modules.boq?.data' in api
    assert 'answer.unavailable' in cdc and 'answer.no_evidence' in cdc
    assert 'display(item.normalized)' in cdc
    assert 'item.raw ?? "—"' in cdc
    assert 'Ask Tender' in cdc and 'Finances & échéances' in cdc
    assert 'askTender(payload.document_store_id, question)' in cdc
    assert 'exportBoqCsv(payload.document_store_id)' in cdc
    assert 'reference.page_number ?? reference.page' in cdc
    assert 'data-ask-evidence' in cdc
    assert 'data-boq-export' in boq
    assert 'fetch(`/api/v2/cdc/${encodeURIComponent(documentId)}/boq.csv`)' in api
    router = (ROOT / "app/static/app/router.js").read_text(encoding="utf-8")
    state = (ROOT / "app/static/app/state.js").read_text(encoding="utf-8")
    assert "loadTenderAnalysis(documentId)" in router
    assert "payload.document_store_id || payload.document_result?.document_id" in state


def test_important_tender_and_invoice_routes_remain_available():
    for route in ("/", "/invoice", "/invoice/result/abc", "/cdc", "/cdc/result/abc",
                  "/cdc/male", "/cdc/male/result/abc"):
        assert client.get(route).status_code == 200


def test_sidebar_uses_only_the_most_specific_tender_route():
    shell = (ROOT / "app/static/app/components/shell.js").read_text(encoding="utf-8")
    assert 'activePath === "/cdc" || activePath.startsWith("/cdc/result/")' in shell
    assert 'activePath.startsWith(`${href}/`)' in shell
    # The special handling for /cdc must avoid matching Ministry result routes.
    assert 'href === "/cdc" ?' in shell


def test_sidebar_rendered_dom_has_one_active_route_with_aria_current():
    class LinkParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and "side-link" in attrs.get("class", ""):
                self.links.append(attrs)

    script = r'''import { mountShell } from "./app/static/app/components/shell.js";
globalThis.Node = class Node {};
const target = new Node(); target.append = () => {};
const root = { innerHTML: "", querySelector: (selector) => selector === "#mainContent" ? target : { addEventListener() {}, setAttribute() {}, textContent: "" } };
globalThis.document = { getElementById: () => root };
globalThis.fetch = async () => ({ json: async () => ({ status: "ok" }) });
mountShell(null, process.argv[1]);
console.log(root.innerHTML);'''
    expected = {
        "/cdc": "/cdc",
        "/cdc/result/abc": "/cdc",
        "/cdc/male": "/cdc/male",
        "/cdc/male/result/abc": "/cdc/male",
        "/invoice/result/abc": "/invoice",
    }
    for route, active_href in expected.items():
        rendered = subprocess.run(
            ["node", "--experimental-default-type=module", "-e", script, route],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
        parser = LinkParser()
        parser.feed(rendered)
        active = [link for link in parser.links if "active" in link.get("class", "").split()]
        current = [link for link in parser.links if link.get("aria-current") == "page"]
        assert [link.get("href") for link in active] == [active_href], (route, active)
        assert [link.get("href") for link in current] == [active_href], (route, current)


def test_upload_loading_and_workspace_actions_are_discoverable():
    upload = (ROOT / "app/static/app/pages/cdc-upload.js").read_text(encoding="utf-8")
    workspace = (ROOT / "app/static/app/pages/cdc-workspace.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app/styles/workspace.css").read_text(encoding="utf-8")
    assert "Analyse du document en cours" in upload
    assert "data-elapsed-time" in upload and "window.setInterval" in upload
    assert "if (!file || submitting) return" in upload
    assert "finally { submitting = false; clearBusy(outlet); }" in upload
    assert '"Finances & Délais", 7' in workspace
    assert '"Ask Tender", 8' in workspace and 'class="ask-tab-icon"' in workspace
    assert '"Structure", 1' in workspace and '"Annexes", 3' in workspace and '"Diagnostics", 6' in workspace
    assert 'role="menu" aria-label="Détails techniques"' in workspace
    assert ".analysis-tabs { display: grid; grid-template-columns: minmax(0, 1fr) auto" in css
    assert "overflow-x: auto" not in css[css.rfind(".analysis-tabs {"):]
    assert "analyse générale terminée" in workspace.lower()


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
