import { listTenderAnalyses } from "../api.js?v=library-1";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

export async function renderLibrary(outlet) {
  outlet.innerHTML = `<section class="dashboard-page library-page"><div class="page-heading"><div><div class="breadcrumbs"><a href="/">ACCUEIL</a> <span>/</span> MES ANALYSES</div><p class="eyebrow">CAHIERS DES CHARGES</p><h1>Mes analyses</h1><p class="page-description">Retrouvez les dossiers analysés sur cet appareil.</p></div><a class="button button-primary" href="/cdc">Nouvelle analyse</a></div><div class="library-results" aria-live="polite"><p class="muted-note">Chargement des analyses…</p></div></section>`;
  const results = outlet.querySelector(".library-results");
  try {
    const items = await listTenderAnalyses();
    results.innerHTML = items.length ? `<div class="library-list">${items.map(item => {
      const route = item.workflow === "ministry_boq" ? "/cdc/male/result/" : "/cdc/result/";
      const when = new Date(item.analyzed_at);
      const date = Number.isNaN(when.valueOf()) ? "Date indisponible" : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" }).format(when);
      return `<article class="library-item"><div><h2>${escapeHtml(item.filename)}</h2><p>${escapeHtml(item.page_count)} pages · Analysé le ${escapeHtml(date)}</p></div><a class="button button-secondary" href="${route}${encodeURIComponent(item.document_id)}">Ouvrir</a></article>`;
    }).join("")}</div>` : `<div class="recent-empty"><span class="empty-mark">—</span><div><strong>Aucune analyse enregistrée</strong><p>Importez un cahier des charges pour le retrouver ici.</p></div></div>`;
  } catch {
    results.innerHTML = `<div class="notice notice-neutral"><strong>Liste indisponible</strong><span>Réessayez lorsque l’API locale est accessible.</span></div>`;
  }
}
