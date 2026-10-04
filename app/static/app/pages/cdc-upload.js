import { analyzeTenderDocument } from "../api.js?v=platform-refactor-qa1";
import { setActiveAnalysis } from "../state.js?v=platform-refactor-5";

const workflowCopy = {
  cdc: { title: "Cahier des Charges", subtitle: "Analyse structurée d’un dossier d’appel d’offres.", endpointName: "l’analyse documentaire et la structuration du dossier" },
  male: { title: "Ministère des Affaires Locales", subtitle: "Analyse des cahiers des charges et bordereaux du Ministère.", endpointName: "l’analyse documentaire, des exigences et des bordereaux" },
};

export function renderCdcUpload(outlet, { workflow, showUnavailable, onSuccess }) {
  const config = workflowCopy[workflow];
  outlet.innerHTML = `<section class="upload-page"><div class="page-heading"><div><div class="breadcrumbs"><a href="/">ACCUEIL</a> <span>/</span> ${workflow === "male" ? "MINISTÈRE DES AFFAIRES LOCALES" : "CAHIER DES CHARGES"}</div><p class="eyebrow">${workflow === "male" ? "DOCUMENTS DU MINISTÈRE" : "APPELS D’OFFRES"}</p><h1>${config.title}</h1><p class="page-description">${config.subtitle}</p></div></div>${showUnavailable ? `<div class="notice notice-neutral"><strong>Cette analyse n’est plus disponible.</strong><span>Les résultats ne sont pas persistés entre les sessions. Importez à nouveau le document pour relancer l’analyse.</span></div>` : ""}<section class="upload-card"><div class="upload-card-heading"><div><h2>Importer un document</h2><p>Document transmis à ${config.endpointName}.</p></div><span class="secure-label">TRAITEMENT LOCAL</span></div><form class="document-upload-form"><label class="upload-drop" for="documentFile"><input id="documentFile" name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" required><span class="upload-icon">PDF</span><span class="upload-primary">Déposez le document ici ou <b>parcourir</b></span><span class="upload-secondary">PDF, PNG, JPG ou TIFF · Taille selon les limites du serveur</span><span class="selected-file hidden"></span></label><div class="upload-form-footer"><span class="upload-hint">Un document par analyse</span><button class="button button-primary" type="submit" disabled>Analyser le document <span aria-hidden="true">→</span></button></div></form></section><div class="processing-panel hidden" aria-live="polite" aria-busy="false"></div><div class="error-panel hidden" role="alert"></div><div class="workflow-note"><span class="note-label">À PROPOS DE L’ANALYSE</span><p>${workflow === "male" ? "Ce parcours analyse le cahier des charges et tente de reconnaître certains formats de bordereau pris en charge. L’analyse générale reste disponible même si le bordereau spécialisé ne correspond pas." : "Le résultat présente la structure du document, les exigences candidates et les annexes avec leurs pages et éléments de preuve."}</p></div></section>`;
  const form = outlet.querySelector(".document-upload-form");
  const input = outlet.querySelector("#documentFile");
  const submit = form.querySelector("button[type=submit]");
  const drop = outlet.querySelector(".upload-drop");
  let submitting = false;
  input.addEventListener("change", () => {
    const file = input.files?.[0];
    submit.disabled = !file;
    const label = drop.querySelector(".selected-file");
    label.textContent = file ? file.name : "";
    label.classList.toggle("hidden", !file);
  });
  for (const name of ["dragenter", "dragover"]) drop.addEventListener(name, event => { event.preventDefault(); drop.classList.add("dragging"); });
  for (const name of ["dragleave", "drop"]) drop.addEventListener(name, event => { event.preventDefault(); drop.classList.remove("dragging"); });
  drop.addEventListener("drop", event => {
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const file = input.files?.[0]; if (!file || submitting) return;
    submitting = true;
    setBusy(outlet);
    try {
      const payload = await analyzeTenderDocument(file, workflow);
      setActiveAnalysis(payload, file, workflow);
      onSuccess(payload, file, workflow);
    } catch (error) { showError(outlet, error); }
    finally { submitting = false; clearBusy(outlet); }
  });
}

function setBusy(outlet) {
  const processing = outlet.querySelector(".processing-panel");
  outlet.querySelector(".upload-card").classList.add("is-processing");
  processing.innerHTML = `<span class="processing-indicator" aria-hidden="true"></span><div><strong>Analyse du document en cours</strong><p>Le traitement d’un document volumineux peut prendre un moment.</p><p class="elapsed-time" data-elapsed-time>Temps écoulé : 00:00</p></div>`;
  processing.classList.remove("hidden"); processing.setAttribute("aria-busy", "true");
  const startedAt = performance.now();
  const updateElapsed = () => {
    const seconds = Math.floor((performance.now() - startedAt) / 1000);
    const time = processing.querySelector("[data-elapsed-time]");
    if (time) time.textContent = `Temps écoulé : ${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  };
  updateElapsed();
  processing._elapsedTimer = window.setInterval(updateElapsed, 1000);
  outlet.querySelector(".document-upload-form button").disabled = true;
  outlet.querySelector(".error-panel").classList.add("hidden");
}
function clearBusy(outlet) {
  outlet.querySelector(".upload-card")?.classList.remove("is-processing");
  const panel = outlet.querySelector(".processing-panel");
  if (panel) { window.clearInterval(panel._elapsedTimer); panel._elapsedTimer = null; panel.classList.add("hidden"); panel.setAttribute("aria-busy", "false"); }
  const input = outlet.querySelector("#documentFile");
  const button = outlet.querySelector(".document-upload-form button");
  if (button) button.disabled = !input?.files?.[0];
}
function showError(outlet, error) {
  const panel = outlet.querySelector(".error-panel");
  const diagnostics = [error.code, ...(error.diagnostics || [])].filter(Boolean);
  panel.innerHTML = `<strong>${escapeHtml(error.message || "Le document n’a pas pu être analysé.")}</strong><p>Vérifiez le fichier puis relancez l’analyse.</p>${error.technicalDetail || diagnostics.length ? `<details><summary>Détails techniques</summary><pre>${escapeHtml([error.technicalDetail, ...diagnostics].filter(Boolean).join("\n"))}</pre></details>` : ""}`;
  panel.classList.remove("hidden");
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]); }
