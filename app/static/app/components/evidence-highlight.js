export function createEvidenceController(viewer, inspector) {
  let selected = null;
  return {
    select(evidence, title = "Preuve source") {
      selected = evidence || null;
      viewer.setEvidence(selected);
      inspector.innerHTML = selected ? `<div class="evidence-inspector"><div class="evidence-inspector-head"><span class="eyebrow">PROVENANCE</span><strong>${escapeHtml(title)}</strong></div><p class="evidence-raw">${escapeHtml(selected.raw_text || selected.rawText || "Aucun texte source associé.")}</p><dl><div><dt>Page physique</dt><dd>${selected.page ?? selected.source_page ?? "—"}</dd></div><div><dt>Élément source</dt><dd>${escapeHtml((selected.source_element_ids || [selected.element_id].filter(Boolean)).join(", ") || "—")}</dd></div><div><dt>Coordonnées</dt><dd>${escapeHtml(selected.coordinate_space || "—")}</dd></div></dl></div>` : `<div class="empty-state"><strong>Aucune preuve sélectionnée</strong><span>Sélectionnez un article ou une exigence pour consulter sa source.</span></div>`;
    },
    current: () => selected,
  };
}

function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]); }
