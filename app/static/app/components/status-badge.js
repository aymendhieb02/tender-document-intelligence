const labels = {
  detected: ["Détecté", "status-detected"], probable: ["Probable", "status-probable"],
  ambiguous: ["Ambigu", "status-ambiguous"], needs_review: ["À vérifier", "status-review"],
  reviewed: ["Vérifié", "status-reviewed"], missing: ["Manquant", "status-missing"],
  VALID: ["Valide", "status-reviewed"], INVALID: ["Invalide", "status-invalid"],
  NOT_CHECKABLE: ["Non vérifiable", "status-neutral"], NEEDS_REVIEW: ["À vérifier", "status-review"],
};

export function statusBadge(status) {
  const [label, style] = labels[status] || [humanize(status || "inconnu"), "status-neutral"];
  return `<span class="status-badge ${style}">${escapeHtml(label)}</span>`;
}
export function originBadge(origin) {
  const map = { OBSERVED: ["Observé", "origin-observed"], TEMPLATE_INFERRED: ["Structure du modèle", "origin-template"], DERIVED: ["Calculé", "origin-derived"], MISSING: ["Non renseigné", "origin-missing"] };
  const [label, style] = map[origin] || map.MISSING;
  return `<span class="origin-badge ${style}">${label}</span>`;
}
function humanize(value) { return String(value).replaceAll("_", " "); }
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]); }
