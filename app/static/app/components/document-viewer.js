export class DocumentViewer {
  constructor(root, documentResult, file, documentUrl = null) {
    this.root = root;
    this.documentResult = documentResult;
    this.file = file;
    this.page = 1;
    this.zoom = "page-width";
    this.evidence = null;
    this.sourceUrl = documentUrl;
    this.objectUrl = documentUrl ? null : (file ? URL.createObjectURL(file) : null);
    this.render();
    if (documentUrl) this.loadSource(documentUrl);
  }

  async loadSource(url) {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Le document source est indisponible.");
      const blob = await response.blob();
      this.objectUrl = URL.createObjectURL(blob);
      this.render();
    } catch {
      const empty = this.root.querySelector(".viewer-empty");
      if (empty) {
        empty.textContent = "Le document source est indisponible. Vous pouvez relancer l’analyse pour le recharger.";
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "Ouvrir le document original";
        empty.append(" ", link);
        empty.classList.remove("hidden");
      }
    }
  }

  render() {
    const maxPage = Math.max(this.documentResult?.pages?.length || 1, 1);
    this.root.innerHTML = `<div class="viewer-toolbar"><div class="viewer-page-control"><button type="button" data-page-step="-1" aria-label="Page précédente">‹</button><input class="viewer-page-input" type="number" min="1" max="${maxPage}" value="${this.page}" aria-label="Numéro de page"><span>/ ${maxPage}</span><button type="button" data-page-step="1" aria-label="Page suivante">›</button></div><div class="viewer-zoom-control"><button type="button" data-zoom="out" aria-label="Réduire">−</button><button type="button" data-zoom="in" aria-label="Agrandir">+</button><select aria-label="Ajustement"><option value="page-width">Ajuster à la largeur</option><option value="page-fit">Ajuster à la page</option><option value="100">100 %</option></select></div></div><div class="viewer-stage"><div class="viewer-paper" id="viewerPaper"></div><div class="evidence-overlay hidden" aria-hidden="true"></div><div class="viewer-empty hidden">Aperçu indisponible pour ce format.</div></div><div class="viewer-caption"><span>Document source</span><span class="viewer-page-label">Page physique ${this.page}</span></div>`;
    const paper = this.root.querySelector("#viewerPaper");
    if (this.objectUrl && (this.file?.type === "application/pdf" || this.file?.name?.toLowerCase().endsWith(".pdf") || this.objectUrl.toLowerCase().includes(".pdf"))) {
      paper.innerHTML = `<iframe title="Aperçu du document PDF" src="${this.objectUrl}#toolbar=0&navpanes=0&page=${this.page}&zoom=page-width"></iframe>`;
    } else if (this.objectUrl) {
      paper.innerHTML = `<img src="${this.objectUrl}" alt="Page ${this.page} du document source">`;
    } else {
      const empty = this.root.querySelector(".viewer-empty");
      if (this.sourceUrl) empty.textContent = "Chargement du document source…";
      empty.classList.remove("hidden");
    }
    this.bind();
    this.setEvidence(this.evidence);
  }

  bind() {
    this.root.querySelectorAll("[data-page-step]").forEach(button => button.addEventListener("click", () => this.goToPage(this.page + Number(button.dataset.pageStep))));
    this.root.querySelector(".viewer-page-input").addEventListener("change", event => this.goToPage(Number(event.target.value)));
    this.root.querySelector("[data-zoom=out]").addEventListener("click", () => this.zoomBy(-10));
    this.root.querySelector("[data-zoom=in]").addEventListener("click", () => this.zoomBy(10));
    this.root.querySelector("select").addEventListener("change", event => { this.zoom = event.target.value; this.refreshSource(); });
  }

  goToPage(page) {
    const maximum = Math.max(this.documentResult?.pages?.length || 1, 1);
    this.page = Math.max(1, Math.min(maximum, page || 1));
    this.root.querySelector(".viewer-page-input").value = this.page;
    this.root.querySelector(".viewer-page-label").textContent = `Page physique ${this.page}`;
    this.refreshSource();
    this.setEvidence(this.evidence);
  }

  refreshSource() {
    const iframe = this.root.querySelector("iframe");
    if (iframe && this.objectUrl) iframe.src = `${this.objectUrl}#toolbar=0&navpanes=0&page=${this.page}&zoom=${this.zoom}`;
    this.root.querySelector(".viewer-stage")?.classList.toggle("zoomed", this.zoom === "100");
  }

  zoomBy(delta) {
    const select = this.root.querySelector("select");
    const current = Number.parseInt(this.zoom, 10) || 100;
    this.zoom = String(Math.max(50, Math.min(200, current + delta)));
    select.value = [...select.options].some(option => option.value === this.zoom) ? this.zoom : "100";
    this.refreshSource();
  }

  setEvidence(evidence) {
    this.evidence = evidence || null;
    const overlay = this.root.querySelector(".evidence-overlay");
    if (!overlay) return;
    overlay.innerHTML = "";
    const pageNumber = physicalPageForEvidence(evidence);
    if (pageNumber && pageNumber !== this.page) this.goToPage(pageNumber);
    const page = this.documentResult?.pages?.find(item => item.page_number === pageNumber);
    const width = evidence?.page_width || page?.width;
    const height = evidence?.page_height || page?.height;
    const normalized = normalizeEvidenceBox(evidence, { width, height });
    // The built-in PDF renderer does not expose its rendered page geometry. Keep
    // the source/provenance detail and page navigation, but avoid false overlays.
    if (!normalized || this.root.querySelector("iframe")) { overlay.classList.add("hidden"); return; }
    const mark = document.createElement("span");
    mark.className = "evidence-rectangle";
    mark.style.left = `${normalized.left}%`;
    mark.style.top = `${normalized.top}%`;
    mark.style.width = `${normalized.width}%`;
    mark.style.height = `${normalized.height}%`;
    overlay.append(mark);
    overlay.classList.remove("hidden");
  }
}

export function physicalPageForEvidence(evidence) { return evidence?.page ?? evidence?.source_page ?? null; }

export function normalizeEvidenceBox(evidence, dimensions = {}) {
  const rawBox = evidence?.bbox || evidence?.source_bbox;
  const box = Array.isArray(rawBox) ? rawBox : rawBox ? [rawBox.x1, rawBox.y1, rawBox.x2, rawBox.y2] : null;
  const width = evidence?.page_width || dimensions.width;
  const height = evidence?.page_height || dimensions.height;
  if (!box || !width || !height || box.some(value => !Number.isFinite(value))) return null;
  const [x1, y1, x2, y2] = box;
  return { left: 100 * x1 / width, top: 100 * y1 / height, width: 100 * (x2 - x1) / width, height: 100 * (y2 - y1) / height };
}
