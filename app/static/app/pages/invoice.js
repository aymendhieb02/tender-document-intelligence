export function renderInvoicePage(root) {
  const heading = root.querySelector(".hero h1");
  const product = root.querySelector(".hero [data-i18n='app.product_name']");
  const subtitle = root.querySelector(".hero .subtitle");
  if (heading) heading.textContent = "Analyse de facture";
  if (product) product.textContent = "FACTURES";
  if (subtitle) subtitle.textContent = "Extraction, contrôle et validation des données de facturation.";
  const uploadLabel = root.querySelector(".drop-zone .drop-title");
  if (uploadLabel) uploadLabel.textContent = "Importer une facture";
  const process = root.querySelector("#processBtn");
  if (process) process.textContent = "Analyser la facture";
  const landing = root.querySelector(".landing-summary");
  if (landing) landing.remove();
  if (window.location.pathname.startsWith("/invoice/result/")) {
    const notice = document.createElement("div");
    notice.className = "notice notice-neutral invoice-session-expired";
    notice.innerHTML = "<strong>Cette analyse n’est plus disponible.</strong><span>Les résultats de facture ne sont pas conservés après l’actualisation ou le redémarrage du serveur. Importez à nouveau le document pour relancer l’analyse.</span>";
    root.querySelector(".invoice-workspace")?.prepend(notice);
  }
}
