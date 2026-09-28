import { mountShell } from "./components/shell.js?v=platform-refactor-5";
import { renderDashboard } from "./pages/dashboard.js?v=platform-refactor-5";
import { renderCdcUpload } from "./pages/cdc-upload.js?v=platform-refactor-qa1";
import { renderInvoicePage } from "./pages/invoice.js?v=platform-refactor-5";

const path = window.location.pathname.replace(/\/$/, "") || "/";
if (path.startsWith("/cdc/male")) document.title = "Ministère des Affaires Locales · Tender Intelligence";
else if (path.startsWith("/cdc")) document.title = "Cahier des Charges · Tender Intelligence";
else if (path.startsWith("/invoice")) document.title = "Analyse de facture · Tender Intelligence";
const invoiceContent = document.getElementById("legacyInvoice");
const content = invoiceContent || document.createElement("div");
content.classList.add("page-content");
const outlet = mountShell(content, path);

if (invoiceContent || path === "/invoice" || path.startsWith("/invoice/result/")) {
  renderInvoicePage(invoiceContent || content);
} else if (path === "/cdc" || path === "/cdc/male" || path.startsWith("/cdc/result/") || path.startsWith("/cdc/male/result/")) {
  renderCdcRoute(outlet, path);
} else {
  renderDashboard(outlet);
}

async function renderCdcRoute(outlet, route) {
  const { renderCdcWorkspace } = await import("./pages/cdc-workspace.js?v=ask-tender-mvp1");
  renderCdcUpload(outlet, {
    workflow: route.startsWith("/cdc/male") ? "male" : "cdc",
    showUnavailable: route.includes("/result/"),
    onSuccess: (payload, file, workflow) => renderCdcWorkspace(outlet, payload, file, workflow),
  });
}
