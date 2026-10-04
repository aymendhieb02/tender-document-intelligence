import { analyzeTenderDocument, exportBoqCsv } from "../api.js?v=persisted-results-3";
import { DocumentViewer } from "../components/document-viewer.js?v=platform-refactor-qa4";
import { createEvidenceController } from "../components/evidence-highlight.js?v=platform-refactor-5";
import { originBadge, statusBadge } from "../components/status-badge.js?v=platform-refactor-5";
import { setActiveAnalysis } from "../state.js?v=platform-refactor-5";
import { renderBoqWorkspace } from "./boq-workspace.js?v=mvp-fix-01";
import { askTender } from "../api.js?v=persisted-results-3";

const primaryViews = [["Vue d’ensemble", 0], ["Exigences", 2], ["Finances & Délais", 7], ["Bordereau", 4], ["Sources", 5], ["Ask Tender", 8]];
const technicalViews = [["Structure", 1], ["Annexes", 3], ["Diagnostics", 6]];

export function renderCdcWorkspace(outlet, payload, file, workflow) {
  const cdc = payload.tender_document;
  const documentResult = payload.document_result;
  const male = workflow === "male";
  const pageCount = documentResult.pages?.length || 0;
  const documentIdLabel = documentResult.document_id ? documentResult.document_id.slice(0, 12) : "—";
  const refs = [];
  let askEvidenceItems = [];
  const tenderTitle = summaryIdentity(payload, "title") || cdc.title || file?.name || "—";
  const boqDiagnostics = payload.boq_document?.diagnostics || payload.modules?.boq?.diagnostics || [];
  const noHandoff = boqDiagnostics.includes("cdc_did_not_detect_boq_handoff");
  const optionalBoqNotice = male && !payload.boq_document?.detected
    ? `<div class="notice notice-neutral boq-availability"><strong>Analyse générale terminée · bordereau spécialisé indisponible</strong><span>${noHandoff ? "Aucun bordereau n’a été repéré dans les annexes." : "Le bordereau ne correspond pas au modèle spécialisé pris en charge."} Structure, exigences, finances, preuves et Ask Tender restent disponibles.</span></div>`
    : "";
  outlet.innerHTML = `<section class="analysis-page"><header class="analysis-document-header"><div class="document-heading"><a class="text-back" href="${male ? "/cdc/male" : "/cdc"}">‹ Retour</a><h1>${escapeHtml(tenderTitle)}</h1><div class="document-meta"><span>Référence ${escapeHtml(summaryIdentity(payload, "reference"))}</span><span>Autorité ${escapeHtml(summaryIdentity(payload, "contracting_organization"))}</span><span>${pageCount || "—"} pages</span><span title="${escapeHtml(documentResult.document_id || "")}">ID ${escapeHtml(documentIdLabel)}</span></div></div><div class="document-status"><button type="button" class="button button-primary ask-tender-cta" data-open-ask-tender><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 4.5h14v9H9l-4.5 3v-3H3z"/></svg><span>Ask Tender</span></button>${statusBadge(male ? (payload.boq_document?.detected ? "detected" : "needs_review") : "needs_review")}</div></header>${optionalBoqNotice}<div class="analysis-layout"><aside class="document-tree-panel"><div class="panel-overline">DOCUMENT</div><h2>Structure</h2><div class="tree-scroll">${renderDocumentTree(cdc, refs)}</div></aside><section class="viewer-panel"><div class="viewer-heading"><strong>Document source</strong><span>Page physique et preuve</span></div><div id="documentViewer" class="document-viewer"></div><section class="evidence-panel"><div id="evidenceInspector"></div></section></section><section class="analysis-panel"><nav class="analysis-tabs" aria-label="Navigation de l’analyse"><div class="analysis-tabs-primary" role="tablist" aria-label="Vues principales">${primaryViews.map(([label, index], i) => `<button type="button" role="tab" aria-selected="${i === 0}" class="analysis-tab ${i === 0 ? "active" : ""} ${index === 8 ? "ask-tab" : ""}" data-analysis-view="${index}">${index === 8 ? '<svg class="ask-tab-icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 4.5h14v9H9l-4.5 3v-3H3z"/></svg>' : ""}<span>${label}</span></button>`).join("")}</div><div class="more-views"><button type="button" class="more-views-button" aria-haspopup="menu" aria-expanded="false" data-more-views>Plus <span aria-hidden="true">▾</span></button><div class="more-views-menu hidden" role="menu" aria-label="Détails techniques">${technicalViews.map(([label, index]) => `<button type="button" role="menuitem" class="analysis-tab" data-analysis-view="${index}">${label}</button>`).join("")}</div></div></nav><div class="analysis-view" id="analysisView" role="tabpanel"></div></section></div></section>`;
  const viewer = new DocumentViewer(outlet.querySelector("#documentViewer"), documentResult, file, payload.document_url);
  const evidenceController = createEvidenceController(viewer, outlet.querySelector("#evidenceInspector"));
  outlet.querySelectorAll("[data-evidence-ref]").forEach(button => button.addEventListener("click", () => selectReference(Number(button.dataset.evidenceRef))));
  const view = outlet.querySelector("#analysisView");
  const registerEvidence = (evidence, title) => refs.push({ evidence, title }) - 1;
  const moreViewsButton = outlet.querySelector("[data-more-views]");
  const moreViewsMenu = outlet.querySelector(".more-views-menu");
  outlet.querySelector("[data-open-ask-tender]").addEventListener("click", () => {
    const askTab = outlet.querySelector('[data-analysis-view="8"]');
    askTab?.click();
    outlet.querySelector(".analysis-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  moreViewsButton.addEventListener("click", () => {
    const open = moreViewsMenu.classList.toggle("hidden") === false;
    moreViewsButton.setAttribute("aria-expanded", String(open));
  });
  outlet.querySelectorAll("[data-analysis-view]").forEach(button => button.addEventListener("click", () => {
    const index = Number(button.dataset.analysisView);
    activateAnalysisView(outlet, index);
    renderAnalysisView(view, index, cdc, payload, documentResult, file, workflow, registerEvidence, selectReference);
  }));
  renderAnalysisView(view, 0, cdc, payload, documentResult, file, workflow, registerEvidence, selectReference);
  outlet.classList.add("has-analysis");

  function selectReference(index) {
    const ref = refs[index];
    if (!ref) return;
    evidenceController.select(ref.evidence, ref.title);
    activateAnalysisView(outlet, 5);
    renderAnalysisView(view, 5, cdc, payload, documentResult, file, workflow, registerEvidence, selectReference, ref.evidence);
  }
  outlet.querySelector("#analysisView").addEventListener("click", async event => {
    const exportButton = event.target.closest("[data-boq-export]");
    if (exportButton) {
      const status = outlet.querySelector("[data-boq-export-status]");
      exportButton.disabled = true;
      status.textContent = "Préparation du fichier CSV…";
      try {
        await exportBoqCsv(payload.document_store_id);
        status.textContent = "Le fichier CSV a été téléchargé.";
      } catch (error) {
        status.textContent = error.message;
      } finally { exportButton.disabled = false; }
      return;
    }
    const evidenceButton = event.target.closest("[data-boq-evidence]");
    if (evidenceButton) {
      const [rowIndex, fieldName] = evidenceButton.dataset.boqEvidence.split(":");
      const value = payload.boq_document?.rows?.[Number(rowIndex)]?.[fieldName];
      if (value?.evidence?.[0]) evidenceController.select(adaptBoqEvidence(value.evidence[0], documentResult), `${fieldName} · ${value.value_origin || "OBSERVED"}`);
      return;
    }
    const askEvidenceButton = event.target.closest("[data-ask-evidence]");
    if (askEvidenceButton) {
      const item = askEvidenceItems[Number(askEvidenceButton.dataset.askEvidence)];
      const reference = item?.reference;
      if (reference?.page_number) {
        evidenceController.select({ page: reference.page_number, element_id: reference.element_id,
          raw_text: item.text, bbox: reference.bbox, coordinate_space: reference.coordinate_space,
          source_element_ids: [reference.element_id] }, `${item.label || "Passage source"} · p. ${reference.page_number}`);
      }
      return;
    }
    if (!event.target.closest("[data-analyze-boq]")) return;
    if (!file) return;
    const button = event.target.closest("[data-analyze-boq]");
    button.disabled = true; button.textContent = "Analyse du modèle en cours…";
    try {
      const malePayload = await analyzeTenderDocument(file, "male");
      setActiveAnalysis(malePayload, file, "male");
      renderCdcWorkspace(outlet, malePayload, file, "male");
    } catch (error) {
      button.disabled = false; button.textContent = "Analyser le bordereau";
      const target = button.parentElement.querySelector(".handoff-error");
      if (target) target.textContent = error.message;
    }
  });
  outlet.querySelector("#analysisView").addEventListener("submit", async event => {
    const form = event.target.closest("[data-ask-tender]");
    if (!form) return;
    event.preventDefault();
    const input = form.querySelector("[name=question]");
    const button = form.querySelector("button[type=submit]");
    const result = form.querySelector("[data-ask-result]");
    const question = input.value.trim();
    if (!question) return;
    button.disabled = true;
    result.innerHTML = `<p role="status">Recherche dans le dossier…</p>`;
    try {
      const answer = await askTender(payload.document_store_id, question);
      askEvidenceItems = answer.evidence || answer.sources || [];
      if (answer.unavailable) result.innerHTML = `<div class="notice notice-neutral"><strong>Ask Tender indisponible</strong><span>Le service de questions n’est pas encore connecté.</span></div>`;
      else if (answer.status === "insufficient_evidence" || answer.no_evidence || answer.status === "not_found" || answer.status === "no_evidence") result.innerHTML = `<div class="notice notice-warning"><strong>Aucune preuve trouvée</strong><span>Le dossier ne fournit pas de source suffisante pour répondre.</span></div>`;
      else result.innerHTML = `<article class="ask-answer">${answer.status === "generation_unavailable" ? `<div class="notice notice-neutral"><strong>Génération locale indisponible</strong><span>Des passages correspondants sont présentés ci-dessous pour vérification.</span></div>` : ""}<h3>${answer.status === "generation_unavailable" ? "Passages retrouvés" : "Réponse"}</h3>${answer.status === "generation_unavailable" ? "" : `<p>${escapeHtml(answer.answer || "—")}</p>`}${renderAskEvidence(answer.evidence || answer.sources || [])}</article>`;
    } catch (error) {
      result.innerHTML = `<div class="notice notice-warning"><strong>Impossible d’interroger le dossier</strong><span>${escapeHtml(error.message)}</span></div>`;
    } finally { button.disabled = false; }
  });
}

function activateAnalysisView(outlet, index) {
  outlet.querySelectorAll("[role=tab][data-analysis-view]").forEach(tab => {
    const selected = Number(tab.dataset.analysisView) === index;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  const menuButton = outlet.querySelector("[data-more-views]");
  const menu = outlet.querySelector(".more-views-menu");
  const technical = technicalViews.some(([, viewIndex]) => viewIndex === index);
  menuButton.classList.toggle("has-active-detail", technical);
  menu.classList.add("hidden");
  menuButton.setAttribute("aria-expanded", "false");
}

export function renderDocumentTree(document, refs = []) {
  const items = [];
  (document.sections || []).forEach(section => items.push(renderTreeNode(section, "section", refs)));
  (document.articles || []).forEach(article => items.push(renderTreeNode(article, "article", refs)));
  (document.paragraphs || []).forEach(paragraph => items.push(renderTreeNode(paragraph, "paragraph", refs)));
  (document.annexes || []).forEach(annex => items.push(renderTreeNode(annex, "annex", refs)));
  return items.length ? `<ul class="document-tree">${items.join("")}</ul>` : `<div class="empty-state"><strong>Structure non détectée</strong><span>Aucune section ou annexe n’est disponible dans le résultat.</span></div>`;
}

function renderTreeNode(node, kind, refs, depth = 0) {
  const evidence = (node.source_evidence || [])[0];
  const refIndex = evidence ? refs.push({ evidence, title: `${kindLabel(kind)} ${node.number || node.title || ""}` }) - 1 : -1;
  const page = node.page_start ?? node.start_page ?? evidence?.page ?? node.page_end ?? node.end_page;
  const name = node.title || node.number || (kind === "paragraph" ? node.text?.slice(0, 70) || "Paragraphe" : kindLabel(kind));
  const children = [
    ...(node.subsections || []).map(item => renderTreeNode(item, "section", refs, depth + 1)),
    ...(node.articles || []).map(item => renderTreeNode(item, "article", refs, depth + 1)),
    ...(node.clauses || []).map(item => renderTreeNode(item, "paragraph", refs, depth + 1)),
    ...(node.paragraphs || []).map(item => renderTreeNode(item, "paragraph", refs, depth + 1)),
  ];
  return `<li class="tree-node depth-${Math.min(depth, 4)}"><button type="button" ${refIndex >= 0 ? `data-evidence-ref="${refIndex}"` : "disabled"}><span class="tree-node-label">${escapeHtml(node.number ? `${node.number} · ${name}` : name)}</span><span class="tree-page">${page ? `p. ${page}` : ""}</span></button>${children.length ? `<ul>${children.join("")}</ul>` : ""}</li>`;
}

function renderAnalysisView(root, index, cdc, payload, documentResult, file, workflow, registerEvidence, selectEvidence, selectedEvidence = null) {
  if (index === 0) root.innerHTML = renderOverview(cdc, documentResult, payload, workflow);
  if (index === 1) root.innerHTML = `<div class="view-heading"><div><p class="eyebrow">DOCUMENT</p><h2>Structure du document</h2><p>Hiérarchie extraite du cahier des charges.</p></div></div>${renderStructure(cdc, registerEvidence)}`;
  if (index === 2) { const items = payload.modules?.requirements_intelligence?.data || cdc.requirements || []; root.innerHTML = `<div class="view-heading"><div><p class="eyebrow">CANDIDATS</p><h2>Exigences</h2><p>${items.length} éléments structurés avec leur état de revue.</p></div></div>${renderRequirements(items, registerEvidence)}`; }
  if (index === 3) root.innerHTML = `<div class="view-heading"><div><p class="eyebrow">ANNEXES</p><h2>Annexes</h2><p>Classement et plages de pages détectées.</p></div></div>${renderAnnexes(cdc.annexes || [], workflow, payload)}`;
  if (index === 4) root.innerHTML = workflow === "male" ? renderBoqWorkspace(payload.boq_document, { canExport: Boolean(payload.document_store_id) }) : renderBqHandoff(cdc, payload);
  if (index === 5) root.innerHTML = selectedEvidence ? `<div class="view-heading"><div><p class="eyebrow">PROVENANCE</p><h2>Élément source</h2></div></div>${renderEvidenceDetail(selectedEvidence)}` : `<div class="view-heading"><div><p class="eyebrow">PROVENANCE</p><h2>Preuves</h2><p>Sélectionnez une exigence, un article ou une annexe pour afficher sa preuve dans le panneau Document.</p></div></div><div class="empty-state"><strong>Aucune preuve sélectionnée</strong><span>Les identifiants et coordonnées sont issus du résultat d’analyse.</span></div>`;
  if (index === 6) root.innerHTML = renderDiagnostics(documentResult, cdc, payload);
  if (index === 7) root.innerHTML = renderFinancial(payload, registerEvidence);
  if (index === 8) root.innerHTML = renderAskTender();
  root.querySelectorAll("[data-ref-select]").forEach(button => button.addEventListener("click", () => selectEvidence(Number(button.dataset.refSelect))));
}

function renderOverview(cdc, result, payload, workflow) {
  const pages = result.pages || [];
  const requirementItems = payload.modules?.requirements_intelligence?.data ?? cdc.requirements;
  const financialItems = payload.modules?.financial_deadline_intelligence?.data;
  const warnings = pages.flatMap(page => page.diagnostics?.warnings || []);
  const cdcDiagnostics = (cdc.diagnostics || []).map(item => item.message || item.code);
  const summary = payload.modules?.summary?.data;
  const identity = summary?.identity || {};
  const fact = key => identity[key]?.value ?? identity[key]?.raw_text ?? "—";
  return `<div class="view-heading"><div><p class="eyebrow">SYNTHÈSE</p><h2>Vue d’ensemble</h2><p>Résumé du dossier et état du traitement.</p></div></div>${summary ? `<section class="diagnostic-summary"><h3>Identité du marché</h3><dl class="metadata-list"><div><dt>Objet</dt><dd>${escapeHtml(fact("title") || fact("object"))}</dd></div><div><dt>Référence</dt><dd>${escapeHtml(fact("reference"))}</dd></div><div><dt>Autorité contractante</dt><dd>${escapeHtml(fact("contracting_organization"))}</dd></div></dl></section>` : ""}<div class="overview-grid"><article class="overview-stat"><span>Pages physiques</span><strong>${pages.length || "—"}</strong></article><article class="overview-stat"><span>Sections</span><strong>${countNodes(cdc.sections)}</strong></article><article class="overview-stat"><span>Exigences</span><strong>${arrayCount(requirementItems)}</strong></article><article class="overview-stat"><span>Obligatoires</span><strong>${Array.isArray(requirementItems) ? requirementItems.filter(item => item.mandatory_status === "MANDATORY").length : "—"}</strong></article><article class="overview-stat"><span>À vérifier</span><strong>${summary?.requirements?.review_required ?? "—"}</strong></article><article class="overview-stat"><span>Faits financiers</span><strong>${arrayCount(financialItems)}</strong></article><article class="overview-stat"><span>Annexes</span><strong>${arrayCount(cdc.annexes)}</strong></article><article class="overview-stat"><span>Lignes BOQ</span><strong>${payload.boq_document?.detected ? payload.boq_document.rows?.length ?? "—" : "—"}</strong></article></div>${workflow === "male" ? `<div class="notice ${payload.boq_document?.detected ? "notice-positive" : "notice-warning"}"><strong>${payload.boq_document?.detected ? "Bordereau spécialisé reconnu" : "Bordereau spécialisé indisponible"}</strong><span>${payload.boq_document?.detected ? `${payload.boq_document.rows?.length || 0} lignes structurelles détectées.` : "L’analyse générale du cahier des charges reste disponible."}</span></div>` : ""}<section class="diagnostic-summary"><div class="subsection-heading"><h3>Traitement</h3>${statusBadge("detected")}</div><dl class="metadata-list"><div><dt>Document ID</dt><dd>${escapeHtml(result.document_id || "—")}</dd></div><div><dt>Mode</dt><dd>${escapeHtml(result.mode || "—")}</dd></div><div><dt>Source</dt><dd>${escapeHtml(result.source_type || "—")}</dd></div><div><dt>Temps total</dt><dd>${formatMs(result.diagnostics?.processing_ms)}</dd></div><div><dt>Avertissements</dt><dd>${warnings.length + cdcDiagnostics.length}</dd></div></dl></section>`;
}

function renderFinancial(payload, registerEvidence) {
  const module = payload.modules?.financial_deadline_intelligence;
  const facts = Array.isArray(module?.data) ? module.data : [];
  if (!module || ["not_implemented", "not_run", "unavailable"].includes(module.availability)) return emptyBlock("Données financières indisponibles", "Aucune donnée financière et d’échéance n’a été produite par ce workflow.");
  if (!facts.length) return emptyBlock("Aucun fait financier détecté", "Aucun fait financier ou délai n’a été retourné.");
  return `<div class="view-heading"><div><p class="eyebrow">FAITS EXTRAITS · ${escapeHtml(module.availability)}</p><h2>Finances & échéances</h2><p>Valeurs brutes et normalisées avec leur état de revue.</p></div></div><div class="requirement-list">${facts.map((item, index) => {
    const ev = item.evidence?.[0]; const ref = ev ? payloadEvidenceRef(ev, registerEvidence, item.category) : -1;
    return `<article class="requirement-card"><div class="requirement-card-heading"><div><span class="requirement-type">${escapeHtml(item.category || "FAIT")}</span><h3>${escapeHtml(item.raw ?? "—")}</h3></div>${statusBadge(item.status || "needs_review")}</div><dl class="requirement-meta"><div><dt>Valeur source</dt><dd>${escapeHtml(item.raw ?? "—")}</dd></div><div><dt>Valeur normalisée</dt><dd>${escapeHtml(display(item.normalized))}</dd></div><div><dt>Revue</dt><dd>${escapeHtml(item.status || "—")}${item.conflict_group ? ` · Conflit ${escapeHtml(item.conflict_group)}` : ""}</dd></div><div><dt>Page</dt><dd>${ev?.page_number ?? ev?.page ?? "—"}</dd></div></dl>${ref >= 0 ? `<button class="button button-secondary" data-ref-select="${ref}">Voir la preuve</button>` : ""}</article>`;
  }).join("")}</div>`;
}
function payloadEvidenceRef(evidence, registerEvidence, title) { return registerEvidence({ page: evidence.page_number ?? evidence.page, element_id: evidence.element_id, raw_text: evidence.raw_text, source_element_ids: [evidence.element_id], coordinate_space: evidence.coordinate_space }, title); }
function renderAskTender() { return `<div class="view-heading"><div><p class="eyebrow">QUESTIONS AU DOSSIER</p><h2>Ask Tender</h2><p>Les réponses doivent être accompagnées de preuves du document.</p></div></div><form data-ask-tender class="ask-form"><label for="tenderQuestion">Votre question</label><textarea id="tenderQuestion" name="question" rows="3" placeholder="Posez une question sur cet appel d’offres…" required></textarea><button class="button button-primary" type="submit">Poser la question</button><div data-ask-result aria-live="polite"></div></form><p class="muted-note">La recherche locale reste disponible hors ligne. La génération de réponses par modèle local est facultative; les passages cités restent consultables sans elle.</p>`; }
function renderAskEvidence(items) { return items.length ? `<ul class="ask-evidence">${items.map((item, index) => { const reference = item.reference || item; const page = reference.page_number ?? reference.page ?? "—"; return `<li><button type="button" class="ask-evidence-link" data-ask-evidence="${index}">${escapeHtml(item.label || item.article || "Passage source")} · p. ${page}</button><p>${escapeHtml(item.text || "")}</p></li>`; }).join("")}</ul>` : `<div class="notice notice-warning"><strong>Aucune preuve associée</strong><span>La réponse ne contient pas de références vérifiables.</span></div>`; }

function renderStructure(cdc, registerEvidence) {
  const refs = [];
  const tree = renderDocumentTree(cdc, refs);
  const all = [...(cdc.sections || []), ...(cdc.articles || []), ...(cdc.annexes || [])];
  const rows = flattenNodes(all);
  return rows.length ? `<div class="structure-list">${rows.map(item => { const ref = item.node.source_evidence?.[0] ? registerEvidence(item.node.source_evidence[0], item.node.title || item.node.number || kindLabel(item.kind)) : -1; return `<article class="structure-row"><div><span class="structure-kind">${kindLabel(item.kind)}</span><h3>${escapeHtml(item.node.number || "")} ${escapeHtml(item.node.title || item.node.text?.slice(0, 100) || "Sans titre")}</h3><p>${escapeHtml(item.node.text || "")}</p><small>Pages ${item.node.page_start ?? item.node.start_page ?? "—"}–${item.node.page_end ?? item.node.end_page ?? "—"}</small></div>${ref >= 0 ? `<button class="button button-secondary" data-ref-select="${ref}">Voir la preuve</button>` : ""}</article>`; }).join("")}</div>` : tree;
}

function renderRequirements(requirements, registerEvidence) {
  if (!requirements.length) return emptyBlock("Aucune exigence candidate", "Aucune exigence structurée n’a été retournée par l’analyse.");
  return `<div class="requirement-list">${requirements.map((item, index) => {
    const evidence = item.source_evidence?.[0] || item.evidence?.[0];
    const text = item.text || item.description || item.title || "—";
    const ref = evidence ? registerEvidence(evidence.page_number ? { page: evidence.page_number, element_id: evidence.element_id, raw_text: evidence.raw_text, source_element_ids: [evidence.element_id], coordinate_space: evidence.coordinate_space } : evidence, text) : -1;
    return `<article class="requirement-card"><div class="requirement-card-heading"><div><span class="requirement-type">${escapeHtml(item.category || item.type || "Exigence")}</span><h3>${escapeHtml(text)}</h3></div>${statusBadge(item.review_status || item.evidence_status || item.mandatory_status)}</div>${item.action ? `<p>${escapeHtml(item.action)}</p>` : ""}<dl class="requirement-meta"><div><dt>Modalité</dt><dd>${escapeHtml(item.mandatory_status || "—")}</dd></div><div><dt>Source</dt><dd>${escapeHtml(item.source_article || item.source_article_id || item.source_section || item.source_annex || "—")}</dd></div><div><dt>Page</dt><dd>${item.source_page ?? item.page ?? evidence?.page ?? "—"}</dd></div><div><dt>Revue</dt><dd>${escapeHtml(item.review_status || item.extraction_status || "needs_review")}</dd></div></dl>${ref >= 0 ? `<button class="button button-secondary" data-ref-select="${ref}">Voir la preuve <span>→</span></button>` : `<span class="muted-note">Aucune référence de preuve fournie</span>`}</article>`;
  }).join("")}</div>`;
}

function renderAnnexes(annexes, workflow, payload) {
  if (!annexes.length) return emptyBlock("Aucune annexe détectée", "Aucune annexe n’est disponible dans la structure retournée.");
  const handoffs = [...(payload.boq_handoffs || []), ...(payload.tender_document?.detected_special_documents || [])];
  return `<div class="annex-list">${annexes.map(annex => {
    const hasHandoff = handoffs.some(item => item.handoff === "boq_agent" && item.page_start <= annex.page_end && item.page_end >= annex.page_start);
    const isBoq = hasHandoff || /boq|bordereau|devis estimatif/i.test(`${annex.annex_type || ""} ${annex.title || ""}`);
    return `<article class="annex-card"><div class="annex-index">${escapeHtml(annex.number || "—")}</div><div class="annex-content"><div class="annex-title-line"><h3>${escapeHtml(annex.title || "Annexe sans titre")}</h3>${statusBadge(annex.evidence_status || "detected")}</div><dl class="requirement-meta"><div><dt>Pages</dt><dd>${annex.page_start ?? "—"}–${annex.page_end ?? "—"}</dd></div><div><dt>Classification</dt><dd>${escapeHtml(annex.annex_type || "Non classée")}</dd></div><div><dt>Revue</dt><dd>${escapeHtml(annex.evidence_status || "détectée")}</dd></div></dl>${isBoq ? `<div class="annex-handoff"><span class="handoff-mark">Prix</span><strong>Bordereau détecté</strong><button type="button" class="button button-secondary" data-analyze-boq>Analyser le bordereau <span>→</span></button><small class="handoff-error" aria-live="polite"></small></div>` : ""}</div></article>`;
  }).join("")}</div>`;
}

function renderBqHandoff(cdc, payload) {
  const handoffs = [...(payload.boq_handoffs || []), ...(cdc.detected_special_documents || [])].filter(item => item.handoff === "boq_agent");
  if (!handoffs.length) return emptyBlock("Aucun bordereau transmis", "Aucun bordereau n’a été identifié dans les annexes retournées.");
  return `<div class="view-heading"><div><p class="eyebrow">DEVIS ESTIMATIF</p><h2>Bordereau des prix détecté</h2><p>Plages de pages transmises pour l’analyse spécialisée.</p></div></div>${handoffs.map(handoff => `<div class="handoff-card"><strong>Bordereau des prix · ${escapeHtml(handoff.document_type || "document détecté")}</strong><span>Pages ${handoff.page_start ?? "—"}–${handoff.page_end ?? "—"}</span><button type="button" class="button button-primary" data-analyze-boq>Analyser le bordereau <span>→</span></button><small class="handoff-error" aria-live="polite"></small></div>`).join("")}`;
}

function renderEvidenceDetail(evidence) {
  return `<article class="evidence-detail"><span class="eyebrow">TEXTE OBSERVÉ</span><blockquote>${escapeHtml(evidence.raw_text || "Aucun texte source associé.")}</blockquote><dl class="metadata-list"><div><dt>Page physique</dt><dd>${evidence.page ?? evidence.source_page ?? "—"}</dd></div><div><dt>Élément source</dt><dd>${escapeHtml((evidence.source_element_ids || [evidence.element_id].filter(Boolean)).join(", ") || "—")}</dd></div><div><dt>Coordonnées</dt><dd>${escapeHtml(evidence.coordinate_space || "—")}</dd></div></dl></article>`;
}

function renderDiagnostics(result, cdc, payload) {
  const pages = result.pages || [];
  const workflowDiagnostics = (payload.diagnostics || []).map(item => typeof item === "string" ? item : `${item.code || "diagnostic"} · ${item.message || ""}`);
  return `<div class="view-heading"><div><p class="eyebrow">DÉTAILS TECHNIQUES</p><h2>Diagnostics</h2><p>Données utiles à la revue, présentées hors du résultat métier.</p></div></div><dl class="metadata-list diagnostics-list"><div><dt>Document ID</dt><dd>${escapeHtml(result.document_id || "—")}</dd></div><div><dt>Contrat</dt><dd>Document Intelligence 1.0</dd></div><div><dt>Pages physiques</dt><dd>${pages.length}</dd></div><div><dt>Pages OCR</dt><dd>${pages.filter(page => page.diagnostics?.ocr_used).length}</dd></div><div><dt>Pages natives</dt><dd>${pages.filter(page => page.diagnostics?.native_text_available).length}</dd></div><div><dt>Éléments de preuve</dt><dd>${pages.reduce((count, page) => count + (page.elements?.length || 0), 0)}</dd></div><div><dt>Temps total</dt><dd>${formatMs(result.diagnostics?.processing_ms)}</dd></div></dl><details class="diagnostics-details"><summary>Avertissements Document Intelligence</summary><ul>${pages.flatMap(page => (page.diagnostics?.warnings || []).map(warning => `<li>Page ${page.page_number} · ${escapeHtml(warning)}</li>`)).join("") || "<li>Aucun avertissement.</li>"}</ul></details><details class="diagnostics-details"><summary>Diagnostics CDC et bordereau</summary><ul>${[...(cdc.diagnostics || []).map(item => `${item.code} · ${item.message}`), ...workflowDiagnostics].map(item => `<li>${escapeHtml(item)}</li>`).join("") || "<li>Aucun diagnostic.</li>"}</ul></details>`;
}

function flattenNodes(nodes, result = [], kind = "section") {
  for (const node of nodes || []) {
    result.push({ node, kind });
    flattenNodes(node.subsections, result, "section");
    flattenNodes(node.articles, result, "article");
    flattenNodes(node.clauses, result, "paragraph");
    flattenNodes(node.paragraphs, result, "paragraph");
  }
  return result;
}
function display(value) { return value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value); }
function summaryIdentity(payload, key) { const fact = payload.modules?.summary?.data?.identity?.[key]; return fact?.value ?? fact?.raw_text ?? "—"; }
function countNodes(nodes) { return Array.isArray(nodes) ? nodes.reduce((sum, node) => sum + 1 + countNodes(node.subsections || []) + (node.articles || []).length, 0) : "—"; }
function arrayCount(items) { return Array.isArray(items) ? items.length : "—"; }
function kindLabel(kind) { return ({ section: "Section", article: "Article", annex: "Annexe", paragraph: "Clause" })[kind] || "Élément"; }
function formatMs(value) { return Number.isFinite(value) ? `${Math.round(value)} ms` : "—"; }
function adaptBoqEvidence(source, documentResult) {
  const pageNumber = source.source_page;
  const page = documentResult.pages?.find(item => item.page_number === pageNumber);
  const ids = new Set(source.element_ids || []);
  const elements = (page?.elements || []).filter(element => ids.has(element.id) && element.bbox);
  const boxes = elements.map(element => element.bbox);
  const bbox = boxes.length ? [Math.min(...boxes.map(box => box.x1)), Math.min(...boxes.map(box => box.y1)), Math.max(...boxes.map(box => box.x2)), Math.max(...boxes.map(box => box.y2))] : null;
  return { page: pageNumber, page_width: page?.width, page_height: page?.height, bbox, raw_text: source.raw_text, source_element_ids: source.element_ids, coordinate_space: page?.coordinate_space || "rendered_page_pixels" };
}
function emptyBlock(title, copy) { return `<div class="empty-state"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(copy)}</span></div>`; }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]); }
