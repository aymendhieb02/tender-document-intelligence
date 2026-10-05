import { mountShell } from "./components/shell.js?v=focused-sprint-1";
import { renderDashboard } from "./pages/dashboard.js?v=focused-sprint-1";
import { renderCdcUpload } from "./pages/cdc-upload.js?v=mvp-fix-01";
import { renderInvoicePage } from "./pages/invoice.js?v=platform-refactor-5";
import { renderLibrary } from "./pages/library.js?v=library-2";

const path = window.location.pathname.replace(/\/$/, "") || "/";
if (path.startsWith("/cdc/male")) document.title = "Ministère des Affaires Locales · Tender Intelligence";
else if (path.startsWith("/cdc")) document.title = "Cahier des Charges · Tender Intelligence";
else if (path.startsWith("/invoice")) document.title = "Analyse de facture · Tender Intelligence";
else if (path === "/analyses") document.title = "Mes analyses · Tender Intelligence";
const invoiceContent = document.getElementById("legacyInvoice");
const content = invoiceContent || document.createElement("div");
content.classList.add("page-content");
const outlet = mountShell(content, path);

if (invoiceContent || path === "/invoice" || path.startsWith("/invoice/result/")) {
  renderInvoicePage(invoiceContent || content);
} else if (path === "/cdc" || path === "/cdc/male" || path.startsWith("/cdc/result/") || path.startsWith("/cdc/male/result/")) {
  renderCdcRoute(outlet, path);
} else if (path === "/analyses") {
  renderLibrary(outlet);
} else {
  renderDashboard(outlet);
}

async function renderCdcRoute(outlet, route) {
  const { renderCdcWorkspace } = await import("./pages/cdc-workspace.js?v=pricing-1");
  if (route.includes("/result/")) {
    const { loadTenderAnalysis } = await import("./api.js?v=persisted-results-3");
    const documentId = decodeURIComponent(route.split("/result/").at(-1) || "");
    try {
      const payload = await loadTenderAnalysis(documentId);
      renderCdcWorkspace(outlet, payload, null, route.startsWith("/cdc/male") ? "male" : "cdc");
      return;
    } catch (error) {
      // Fall through to an actionable upload page when the local record expired or is damaged.
    }
  }
  renderCdcUpload(outlet, {
    workflow: route.startsWith("/cdc/male") ? "male" : "cdc",
    showUnavailable: route.includes("/result/"),
    onSuccess: (payload, file, workflow) => renderCdcWorkspace(outlet, payload, file, workflow),
  });
}
