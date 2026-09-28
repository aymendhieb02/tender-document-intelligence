/** @typedef {"cdc" | "male"} TenderWorkflow */

/** @param {File} file @param {TenderWorkflow} workflow */
export async function analyzeTenderDocument(file, workflow) {
  const form = new FormData();
  form.append("file", file);
  const endpoint = workflow === "male" ? "/api/cdc/male/analyze" : "/api/cdc/analyze";
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
