/** @typedef {"cdc" | "male"} TenderWorkflow */

/** @param {File} file @param {TenderWorkflow} workflow */
export async function analyzeTenderDocument(file, workflow) {
  const form = new FormData();
  form.append("file", file);
  const endpoint = workflow === "male" ? "/api/v2/cdc/male/analyze" : "/api/v2/cdc/analyze";
  const response = await fetch(endpoint, { method: "POST", body: form });
  const payload = await response.json();
  if (!response.ok) {
    const detail = payload.error || payload.detail || {};
    const error = new Error(typeof detail === "string" ? detail : detail.message || "Le traitement a échoué.");
    error.code = detail.code || "document_processing_failed";
    error.technicalDetail = detail.technical_detail || "";
    error.diagnostics = detail.diagnostics || [];
    throw error;
  }
  if (payload.contract_version === "2.0" && payload.document && payload.modules) {
    const firstBoq = payload.modules.boq?.data?.[0]?.result || payload.modules.boq?.data?.[0];
    return {
      ...payload,
      document_id: payload.document.document_id,
      document_url: payload.document.document_url,
      document_store_id: storedDocumentId(payload.document.document_url),
      source_type: payload.document.source_type,
      page_count: payload.document.page_count,
      document_result: {
        document_id: payload.document.document_id,
        source_type: payload.document.source_type,
        mode: "Document Intelligence",
        pages: Array.from({ length: payload.document.page_count }, (_, index) => ({ page_number: index + 1 })),
        diagnostics: { processing_ms: null },
      },
      boq_document: firstBoq || { detected: false, rows: [], diagnostics: payload.modules.boq?.diagnostics || [] },
    };
  }
  if (!payload.tender_document || (!Array.isArray(payload.pages) && !Number.isInteger(payload.page_count))) {
    throw new Error("La réponse ne respecte pas le contrat d’analyse attendu.");
  }
  // The general CDC endpoint returns page metadata while the specialized
  // Ministry endpoint returns only page_count. Normalize both API V1 shapes
  // for the shared document workspace without changing either contract.
  const pages = Array.isArray(payload.pages)
    ? payload.pages
    : Array.from({ length: payload.page_count }, (_, index) => ({ page_number: index + 1 }));
  const firstBoq = payload.boq_results?.[0]?.result;
  return {
    ...payload,
    document_store_id: storedDocumentId(payload.document_url),
    document_result: {
      document_id: payload.document_id,
      source_type: payload.source_type,
      mode: "Document Intelligence",
      pages,
      diagnostics: { processing_ms: null },
    },
    boq_document: firstBoq || { detected: false, rows: [], diagnostics: payload.diagnostics || [] },
  };
}

function storedDocumentId(documentUrl) {
  return String(documentUrl || "").match(/^\/api\/documents\/([^/?#]+)/)?.[1] || null;
}

export async function askTender(documentId, question) {
  if (!documentId) throw new Error("Identifiant du dossier manquant.");
  const response = await fetch(`/api/v2/cdc/${encodeURIComponent(documentId)}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.error || payload.detail || {};
    const error = new Error(typeof detail === "string" ? detail : detail.message || "La question n’a pas pu être traitée.");
    error.code = detail.code || "ask_tender_error";
    error.status = response.status;
    throw error;
  }
  return payload;
}

export async function loadTenderAnalysis(documentId) {
  const response = await fetch(`/api/v2/cdc/${encodeURIComponent(documentId)}`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error?.message || "Cette analyse n’est plus disponible.");
  const firstBoq = payload.modules?.boq?.data?.[0]?.result || payload.modules?.boq?.data?.[0];
  return {
    ...payload,
    document_id: payload.document.document_id,
    document_url: payload.document.document_url,
    document_store_id: storedDocumentId(payload.document.document_url),
    source_type: payload.document.source_type,
    page_count: payload.document.page_count,
    document_result: {
      document_id: payload.document.document_id,
      source_type: payload.document.source_type,
      mode: "Document Intelligence",
      pages: Array.from({ length: payload.document.page_count }, (_, index) => ({ page_number: index + 1 })),
      diagnostics: { processing_ms: null },
    },
    boq_document: firstBoq || { detected: false, rows: [], diagnostics: payload.modules?.boq?.diagnostics || [] },
  };
}

export async function listTenderAnalyses() {
  const response = await fetch("/api/v2/cdc");
  if (!response.ok) throw new Error("Les analyses enregistrées sont indisponibles.");
  return response.json();
}

export async function exportBoqCsv(documentId) {
  if (!documentId) throw new Error("Identifiant du dossier manquant.");
  const response = await fetch(`/api/v2/cdc/${encodeURIComponent(documentId)}/boq.csv`);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.error || payload.detail || {};
    throw new Error(typeof detail === "string" ? detail : detail.message || "L’export CSV a échoué.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = "boq-export.csv";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
