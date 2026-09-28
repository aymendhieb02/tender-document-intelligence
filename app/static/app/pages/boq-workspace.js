import { originBadge, statusBadge } from "../components/status-badge.js?v=platform-refactor-5";

const amountFields = ["quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"];
const visibleFields = ["article", "designation", "quantity", "unit", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"];
const labels = { article: "Art.", designation: "Désignation", quantity: "Qté", unit: "Unité", unit_price_ht: "PU HT", total_ht: "Total HT", unit_price_ttc: "PU TTC", total_ttc: "Total TTC" };

export function renderBoqWorkspace(boq) {
  if (!boq?.detected) return `<div class="view-heading"><div><p class="eyebrow">MINISTÈRE DES AFFAIRES LOCALES</p><h2>Devis estimatif</h2></div></div>${empty("Document du Ministère non reconnu", "Le document n’a pas été reconnu. Aucun bordereau n’a été extrait.")}`;
  const rows = boq.rows || [];
  const blank = rows.length > 0 && rows.every(row => amountFields.every(field => !hasValue(row[field])));
  const body = rows.map((row, rowIndex) => `<tr>${visibleFields.map(field => `<td>${renderValue(row[field], rowIndex, field)}</td>`).join("")}<td>${statusBadge(row.validation_status || "NOT_CHECKABLE")}</td></tr>`).join("");
  return `<div class="view-heading"><div><p class="eyebrow">MINISTÈRE DES AFFAIRES LOCALES</p><h2>Devis estimatif</h2><p>${rows.length} lignes structurelles · ${escapeHtml(boq.currency || "—")}</p></div>${statusBadge(boq.review_status || "NOT_CHECKABLE")}</div>${blank ? `<div class="notice notice-positive"><strong>Document du Ministère reconnu · ${rows.length} lignes structurelles détectées</strong><span>Données financières non renseignées dans ce document.</span></div>` : ""}<div class="boq-table-wrap"><table class="boq-table"><thead><tr>${visibleFields.map(field => `<th>${labels[field]}</th>`).join("")}<th>Validation</th></tr></thead><tbody>${body}</tbody></table></div><section class="validation-section"><div class="subsection-heading"><div><p class="eyebrow">CONTRÔLES ARITHMÉTIQUES</p><h3>Validation distincte de l’évidence</h3></div></div>${(boq.validation || []).length ? (boq.validation || []).map(check => `<div class="validation-row"><span>${escapeHtml(check.rule)}</span>${statusBadge(check.status)}<small>${escapeHtml(check.reason || check.difference || "")}</small></div>`).join("") : `<p class="muted-note">${blank ? "Aucune valeur financière à vérifier." : "Aucun contrôle arithmétique retourné."}</p>`}</section><section class="validation-section"><div class="subsection-heading"><div><p class="eyebrow">ORIGINE DES VALEURS</p><h3>Valeurs et preuves source</h3></div></div><div class="boq-origin-list">${rows.map((row, index) => `<details><summary>Article ${escapeHtml(value(row.article))}</summary>${visibleFields.map(field => renderOriginField(row[field], index, field)).join("")}</details>`).join("")}</div></section>${(boq.totals && Object.values(boq.totals).some(hasValue)) ? `<section class="validation-section"><h3>Totaux retournés</h3><dl class="metadata-list">${Object.entries(boq.totals).map(([key, parsed]) => `<div><dt>${escapeHtml(labels[key] || key.replaceAll("_", " "))}</dt><dd>${escapeHtml(value(parsed))} ${originBadge(parsed?.value_origin)}</dd></div>`).join("")}</dl></section>` : ""}`;
}

export function formatBoqValue(parsed) { return value(parsed); }

function renderValue(parsed, rowIndex, field) {
  const source = parsed?.value_origin === "OBSERVED" && parsed?.evidence?.length;
  return `<span class="boq-cell-content">${escapeHtml(value(parsed))}${originBadge(parsed?.value_origin)}</span>${parsed?.value_origin === "TEMPLATE_INFERRED" ? `<small class="template-note">Structure issue du modèle vérifié</small>` : source ? `<button type="button" class="inline-link" data-boq-evidence="${rowIndex}:${field}">Voir la preuve</button>` : ""}`;
}

function renderOriginField(parsed, rowIndex, field) {
  const template = parsed?.value_origin === "TEMPLATE_INFERRED";
  const evidence = parsed?.evidence?.length > 0 && parsed?.value_origin === "OBSERVED";
  return `<div class="origin-row"><span>${labels[field] || field}</span>${originBadge(parsed?.value_origin)}<span>${escapeHtml(value(parsed))}</span>${template ? `<small>Structure issue du modèle vérifié. Aucune preuve OCR n’est associée.</small>` : evidence ? `<button type="button" class="inline-link" data-boq-evidence="${rowIndex}:${field}">Afficher la preuve</button>` : ""}</div>`;
}

function value(parsed) {
  if (parsed == null) return "—";
  const normalized = typeof parsed === "object" && "normalized_value" in parsed ? (parsed.normalized_value ?? parsed.raw_value) : parsed;
  return normalized == null || normalized === "" ? "—" : typeof normalized === "object" ? JSON.stringify(normalized) : String(normalized);
}
function hasValue(parsed) { return parsed?.normalized_value != null || Boolean(parsed?.raw_value); }
function empty(title, copy) { return `<div class="empty-state"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(copy)}</span></div>`; }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]); }
