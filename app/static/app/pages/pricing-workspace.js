import { loadBoqPricing, saveBoqPricing, exportBoqPricingCsv } from "../api.js?v=pricing-1";

const statusLabels = { not_started: "Non commencé", in_progress: "En cours", complete: "Complet", needs_review: "À vérifier" };
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}
function sourceValue(parsed) {
  return parsed?.normalized_value == null ? "—" : String(parsed.normalized_value);
}
function output(value) { return value == null ? "—" : String(value); }

export async function renderPricingWorkspace(root, documentId, boqIndex = 0, { onBack, onSource } = {}) {
  root.innerHTML = `<p role="status">Chargement du chiffrage…</p>`;
  let draft;
  try { draft = await loadBoqPricing(documentId, boqIndex); }
  catch (error) { root.innerHTML = `<div class="notice notice-warning"><strong>Chiffrage indisponible</strong><span>${escapeHtml(error.message)}</span></div>`; return; }
  const fields = draft.profile.basis === "unknown" ? ["unit_price"] :
    draft.profile.has_ht && draft.profile.has_ttc ? ["unit_price_ht", "unit_price_ttc"] :
    draft.profile.has_ht ? ["unit_price_ht"] : ["unit_price_ttc"];
  const labels = { unit_price: "Prix unitaire", unit_price_ht: "Prix U. HT", unit_price_ttc: "Prix U. TTC" };
  const amountFields = draft.profile.basis === "unknown" ? [["line_total", "Montant"]] :
    draft.profile.has_ht && draft.profile.has_ttc ? [["line_total_ht", "Montant HT"], ["line_total_ttc", "Montant TTC"]] :
    draft.profile.has_ht ? [["line_total_ht", "Montant HT"]] : [["line_total_ttc", "Montant TTC"]];
  const primaryTotal = draft.profile.has_ht ? "total_ht" : draft.profile.has_ttc ? "total_ttc" : "total";
  const primaryTotalLabel = draft.profile.has_ht ? "Total HT" : draft.profile.has_ttc ? "Total TTC" : "Montant calculé";
  root.innerHTML = `<section class="pricing-workspace"><div class="view-heading"><div><p class="eyebrow">BORDEREAU · BROUILLON SÉPARÉ</p><h2>Chiffrage du bordereau</h2><p>Les valeurs du document restent inchangées. Les prix saisis et montants calculés sont enregistrés séparément.</p></div><div class="view-actions"><button type="button" class="button button-secondary" data-pricing-back>Consulter le bordereau</button><button type="button" class="button button-secondary" data-pricing-export>Exporter le chiffrage</button></div></div><div class="pricing-legend"><span>Document : données source</span><span>Saisie : prix du soumissionnaire</span><span>Calcul : montant obtenu</span></div><div class="pricing-summary"><strong data-pricing-count>${draft.priced_rows} / ${draft.total_rows} lignes chiffrées</strong><span data-pricing-state>${statusLabels[draft.status] || draft.status}</span><span data-pricing-save aria-live="polite">${draft.updated_at ? "Enregistré" : "Non enregistré"}</span></div>${draft.profile.basis === "unknown" ? `<div class="notice notice-warning"><strong>Base fiscale non précisée</strong><span>Le montant est calculé sans le qualifier de HT ou TTC. Vérifiez le bordereau source.</span></div>` : ""}<div class="boq-table-wrap"><table class="boq-table pricing-table"><thead><tr><th>N°<small>Document</small></th><th>Désignation<small>Document</small></th><th>Unité<small>Document</small></th><th>Quantité<small>Document</small></th>${fields.map(field => `<th>${labels[field]}<small>Saisie</small></th>`).join("")}${amountFields.map(([, label]) => `<th>${label}<small>Calcul</small></th>`).join("")}<th>État</th></tr></thead><tbody>${draft.rows.map(row => `<tr><td>${escapeHtml(sourceValue(row.source.article))}</td><td>${escapeHtml(sourceValue(row.source.designation))}</td><td>${escapeHtml(sourceValue(row.source.unit))}</td><td>${escapeHtml(sourceValue(row.source.quantity))}${row.source.page ? `<button type="button" class="inline-link" data-pricing-source="${row.source.page}">p. ${row.source.page}</button>` : ""}</td>${fields.map(field => `<td><input class="pricing-input" aria-label="${labels[field]} article ${escapeHtml(sourceValue(row.source.article))}" inputmode="decimal" autocomplete="off" data-price-index="${row.index}" data-price-field="${field}" value="${escapeHtml(row.input[field] || "")}" placeholder="—"></td>`).join("")}${amountFields.map(([field]) => `<td data-pricing-amount="${row.index}:${field}">${escapeHtml(output(row.computed[field].value))}</td>`).join("")}<td><span data-pricing-row-status="${row.index}">${statusLabels[row.status] || row.status}</span><small class="pricing-row-issue" data-pricing-row-issue="${row.index}">${escapeHtml(row.issues.join(" "))}</small></td></tr>`).join("")}</tbody></table></div><div class="pricing-totals"><div><span>${primaryTotalLabel}</span><strong data-pricing-total="${primaryTotal}">${escapeHtml(output(draft.totals[primaryTotal].value))}</strong></div>${draft.profile.has_ht ? `<div class="pricing-tax"><label for="pricingTaxRate">TVA (%) ${draft.tax_rate.origin === "source" ? "· document" : "· taux à renseigner explicitement"}</label>${draft.tax_rate.origin === "source" ? `<strong>${escapeHtml(draft.tax_rate.value)} %</strong>` : `<input id="pricingTaxRate" class="pricing-input" inputmode="decimal" autocomplete="off" value="${escapeHtml(draft.tax_rate.raw || "")}" placeholder="Non renseignée">`}<small data-pricing-tax-error>${escapeHtml(draft.tax_rate.error || "")}</small></div><div><span>Montant TVA</span><strong data-pricing-total="tax_amount">${escapeHtml(output(draft.totals.tax_amount.value))}</strong></div><div><span>Total TTC</span><strong data-pricing-total="total_ttc">${escapeHtml(output(draft.totals.total_ttc.value))}</strong></div>` : ""}<p class="pricing-issues" data-pricing-issues>${escapeHtml(draft.issues.join(" "))}</p></div><p class="muted-note" data-pricing-export-status aria-live="polite"></p></section>`;
  let revision = 0;
  let savedRevision = 0;
  let timer = null;
  let inFlight = false;
  let currentSave = null;
  const saveState = root.querySelector("[data-pricing-save]");
  function collectInputs() {
    const rows = draft.rows.map(row => ({ index: row.index }));
    root.querySelectorAll("[data-price-index]").forEach(input => {
      rows[Number(input.dataset.priceIndex)][input.dataset.priceField] = input.value;
    });
    return { rows, tax_rate: root.querySelector("#pricingTaxRate")?.value ?? null };
  }
  function updateResult(next) {
    draft = next;
    root.querySelector("[data-pricing-count]").textContent = `${next.priced_rows} / ${next.total_rows} lignes chiffrées`;
    root.querySelector("[data-pricing-state]").textContent = statusLabels[next.status] || next.status;
    next.rows.forEach(row => {
      Object.entries(row.computed).forEach(([field, value]) => {
        const cell = root.querySelector(`[data-pricing-amount="${row.index}:${field}"]`);
        if (cell) cell.textContent = output(value.value);
      });
      root.querySelector(`[data-pricing-row-status="${row.index}"]`).textContent = statusLabels[row.status] || row.status;
      root.querySelector(`[data-pricing-row-issue="${row.index}"]`).textContent = row.issues.join(" ");
    });
    Object.entries(next.totals).forEach(([field, value]) => {
      const cell = root.querySelector(`[data-pricing-total="${field}"]`);
      if (cell) cell.textContent = output(value.value);
    });
    const taxError = root.querySelector("[data-pricing-tax-error]");
    if (taxError) taxError.textContent = next.tax_rate.error || "";
    root.querySelector("[data-pricing-issues]").textContent = next.issues.join(" ");
  }
  async function saveNow() {
    if (timer) { window.clearTimeout(timer); timer = null; }
    if (inFlight) {
      const priorSucceeded = await currentSave;
      if (!priorSucceeded) return false;
      return savedRevision === revision ? true : saveNow();
    }
    inFlight = true;
    const sentRevision = revision;
    const inputs = collectInputs();
    saveState.textContent = "Enregistrement…";
    currentSave = (async () => {
      try {
        const next = await saveBoqPricing(documentId, boqIndex, inputs);
        savedRevision = sentRevision;
        if (sentRevision === revision && root.isConnected) {
          updateResult(next);
          saveState.textContent = "Enregistré";
        }
        return true;
      } catch (error) {
        if (root.isConnected) saveState.textContent = `Échec de l’enregistrement : ${error.message}`;
        return false;
      } finally { inFlight = false; }
    })();
    const success = await currentSave;
    return sentRevision === revision ? success : saveNow();
  }
  function schedule(delay = 450) {
    revision += 1;
    saveState.textContent = "Modifications non enregistrées";
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(saveNow, delay);
  }
  root.querySelectorAll(".pricing-input").forEach(input => {
    input.addEventListener("input", () => schedule());
    input.addEventListener("change", () => schedule(0));
  });
  root.querySelector("[data-pricing-back]").addEventListener("click", async () => {
    if (!revision || await saveNow()) onBack?.();
  });
  root.querySelector("[data-pricing-export]").addEventListener("click", async event => {
    const status = root.querySelector("[data-pricing-export-status]");
    event.currentTarget.disabled = true;
    if ((timer || inFlight) && !await saveNow()) {
      status.textContent = "Enregistrez le brouillon avant de l’exporter.";
      event.currentTarget.disabled = false;
      return;
    }
    try { await exportBoqPricingCsv(documentId, boqIndex); status.textContent = "Le chiffrage CSV a été téléchargé."; }
    catch (error) { status.textContent = error.message; }
    finally { event.currentTarget.disabled = false; }
  });
  root.querySelectorAll("[data-pricing-source]").forEach(button => button.addEventListener("click", () => onSource?.(Number(button.dataset.pricingSource))));
  return { flush: async () => !revision || savedRevision === revision || await saveNow() };
}
