let activeAnalysis = null;
let sourceFile = null;

export function setActiveAnalysis(payload, file, workflow) {
  activeAnalysis = { payload, workflow };
  sourceFile = file;
  const id = payload.document_result?.document_id;
  if (id) history.pushState({ documentId: id }, "", workflow === "male" ? `/cdc/male/result/${encodeURIComponent(id)}` : `/cdc/result/${encodeURIComponent(id)}`);
}

export function getActiveAnalysis() { return activeAnalysis; }
export function getSourceFile() { return sourceFile; }
