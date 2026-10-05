import { listTenderAnalyses, deleteTenderAnalysis } from "../api.js?v=library-2";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

export async function renderLibrary(outlet) {
  outlet.innerHTML = `<section class="dashboard-page library-page"><div class="page-heading"><div><div class="breadcrumbs"><a href="/">ACCUEIL</a> <span>/</span> MES ANALYSES</div><p class="eyebrow">CAHIERS DES CHARGES</p><h1>Mes analyses</h1><p class="page-description">Retrouvez les dossiers analysés sur cet appareil.</p></div><a class="button button-primary" href="/cdc">Nouvelle analyse</a></div><label class="library-search-label" for="analysisSearch">Rechercher un dossier</label><input id="analysisSearch" class="library-search" type="search" placeholder="Nom ou identifiant du dossier" autocomplete="off"><div class="library-results" aria-live="polite"><p class="muted-note">Chargement des analyses…</p></div></section>`;
  const results = outlet.querySelector(".library-results");
  try {
    const items = await listTenderAnalyses();
    function draw() {
      const query = outlet.querySelector("#analysisSearch").value.trim().toLocaleLowerCase("fr");
      const visible = items.filter(item => `${item.filename} ${item.document_id}`.toLocaleLowerCase("fr").includes(query));
      results.innerHTML = visible.length ? `<div class="library-list">${visible.map(item => {
      const route = item.workflow === "ministry_boq" ? "/cdc/male/result/" : "/cdc/result/";
      const when = new Date(item.analyzed_at);
      const date = Number.isNaN(when.valueOf()) ? "Date indisponible" : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(when);
      const pricing = { complete: "Complet", in_progress: "En cours", needs_review: "À vérifier", not_started: "Non commencé" }[item.pricing_status] || "Non commencé";
      return `<article class="library-item"><div><h2>${escapeHtml(item.filename)}</h2><p>${escapeHtml(item.page_count)} pages · Analysé le ${escapeHtml(date)} · Chiffrage : ${pricing}</p></div><div class="library-actions"><a class="button button-secondary" href="${route}${encodeURIComponent(item.document_id)}">Ouvrir</a><button type="button" class="button button-secondary" data-library-delete="${escapeHtml(item.document_id)}">Supprimer</button></div></article>`;
    }).join("")}</div>` : `<div class="recent-empty"><span class="empty-mark">—</span><div><strong>${query ? "Aucun résultat" : "Aucune analyse enregistrée"}</strong><p>${query ? "Essayez un autre nom ou identifiant." : "Importez un cahier des charges pour le retrouver ici."}</p></div></div>`;
    }
    outlet.querySelector("#analysisSearch").addEventListener("input", draw);
    results.addEventListener("click", async event => {
      const button = event.target.closest("[data-library-delete]");
      if (!button) return;
      const item = items.find(record => record.document_id === button.dataset.libraryDelete);
      if (!item || !window.confirm(`Supprimer définitivement « ${item.filename} » et son chiffrage enregistré ?`)) return;
      button.disabled = true;
      try { await deleteTenderAnalysis(item.document_id); items.splice(items.indexOf(item), 1); draw(); }
      catch { button.disabled = false; window.alert("La suppression a échoué. Réessayez."); }
    });
    draw();
  } catch {
    results.innerHTML = `<div class="notice notice-neutral"><strong>Liste indisponible</strong><span>Réessayez lorsque l’API locale est accessible.</span></div>`;
  }
}
