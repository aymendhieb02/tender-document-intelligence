export class DocumentViewer {
  constructor(root, documentResult, file, documentUrl = null) {
    this.root = root;
    this.documentResult = documentResult;
    this.file = file;
    this.page = 1;
    this.zoom = "page-width";
    this.evidence = null;
    this.sourceUrl = documentUrl;
    this.objectUrl = file ? URL.createObjectURL(file) : null;
    this.render();
  }

  render() {
    const maxPage = Math.max(this.documentResult?.pages?.length || 1, 1);
    this.root.innerHTML = `<div class="viewer-toolbar"><div class="viewer-page-control"><button type="button" data-page-step="-1" aria-label="Page précédente">‹</button><input class="viewer-page-input" type="number" min="1" max="${maxPage}" value="${this.page}" aria-label="Numéro de page"><span>/ ${maxPage}</span><button type="button" data-page-step="1" aria-label="Page suivante">›</button></div><div class="viewer-zoom-control"><button type="button" data-zoom="out" aria-label="Réduire">−</button><button type="button" data-zoom="in" aria-label="Agrandir">+</button><select aria-label="Ajustement"><option value="page-width">Ajuster à la largeur</option><option value="page-fit">Ajuster à la page</option><option value="100">100 %</option></select></div></div><div class="viewer-stage"><div class="viewer-paper" id="viewerPaper"></div><div class="evidence-overlay hidden" aria-hidden="true"></div><div class="viewer-empty hidden">Aperçu indisponible pour ce format.</div></div><div class="viewer-caption"><span>Document source</span><span class="viewer-page-label">Page physique ${this.page}</span></div>`;
    const paper = this.root.querySelector("#viewerPaper");
    if (this.sourceUrl) {
      const pageUrl = new URL(this.sourceUrl, window.location.href);
      pageUrl.pathname = `${pageUrl.pathname.replace(/\/$/, "")}/pages/${this.page}.png`;
      pageUrl.searchParams.set("width", String(this.renderWidth()));
      paper.innerHTML = `<img src="${pageUrl.href}" alt="Page ${this.page} du document source">`;
      this.sizeSourceImage(paper.querySelector("img"));
    } else if (this.objectUrl && (this.file?.type === "application/pdf" || this.file?.name?.toLowerCase().endsWith(".pdf") || this.objectUrl.toLowerCase().includes(".pdf"))) {
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
  }

  refreshSource() {
    if (this.sourceUrl) {
      const paper = this.root.querySelector("#viewerPaper");
      const pageUrl = new URL(this.sourceUrl, window.location.href);
      pageUrl.pathname = `${pageUrl.pathname.replace(/\/$/, "")}/pages/${this.page}.png`;
      pageUrl.searchParams.set("width", String(this.renderWidth()));
      const image = paper?.querySelector("img");
      if (image) {
        image.src = pageUrl.href;
        image.alt = `Page ${this.page} du document source`;
        this.sizeSourceImage(image);
      }
    }
    const iframe = this.root.querySelector("iframe");
    if (iframe && this.objectUrl) iframe.src = `${this.objectUrl}#toolbar=0&navpanes=0&page=${this.page}&zoom=${this.zoom}`;
    this.root.querySelector(".viewer-stage")?.classList.toggle("zoomed", this.zoom === "100");
  }

  renderWidth() {
    if (this.zoom === "page-fit") return 1000;
    const zoom = Number.parseInt(this.zoom, 10);
    return zoom ? Math.round(1200 * zoom / 100) : 1200;
  }

  sizeSourceImage(image) {
    if (!image) return;
    if (this.zoom === "page-fit") {
      image.style.width = "auto";
      image.style.height = "100%";
      image.style.maxWidth = "100%";
      return;
    }
    image.style.width = this.zoom === "page-width" ? "100%" : `${Number.parseInt(this.zoom, 10) || 100}%`;
    image.style.height = this.zoom === "page-width" ? "100%" : "auto";
    image.style.maxWidth = this.zoom === "page-width" ? "100%" : "none";
  }

  zoomBy(delta) {
    const select = this.root.querySelector("select");
    const current = Number.parseInt(this.zoom, 10) || 100;
    this.zoom = String(Math.max(50, Math.min(200, current + delta)));
    let option = [...select.options].find(item => item.value === this.zoom);
    if (!option) {
      option = document.createElement("option");
      option.value = this.zoom;
      option.textContent = `${this.zoom} %`;
      select.append(option);
    }
    select.value = this.zoom;
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
    if (!normalized || this.sourceUrl || this.root.querySelector("iframe")) { overlay.classList.add("hidden"); return; }
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
