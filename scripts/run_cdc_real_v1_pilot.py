"""Run the frozen PDF -> Document Intelligence -> CDC Analyzer pilot locally."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cdc_analysis import CDCAnalyzer
from app.document_intelligence import DocumentProcessor, document_intelligence_contract_version


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--reuse-document-result", action="append", default=[],
                        help="Reuse a just-produced DocumentResult as id=relative/path.json")
    args = parser.parse_args()
    corpus = args.corpus.resolve(strict=True)
    out = ROOT / "benchmarks" / "cdc_real_v1"
    selection = json.loads((out / "pilot_selection.json").read_text(encoding="utf-8"))
    reusable = {}
    for value in args.reuse_document_result:
        document_id, path = value.split("=", 1)
        reusable[document_id] = Path(path)
    processor = DocumentProcessor(mode="auto", use_cache=False, allow_fallback=True)
    analyzer = CDCAnalyzer()
    entries = []
    (out / "document_results").mkdir(parents=True, exist_ok=True)
    (out / "predictions").mkdir(parents=True, exist_ok=True)

    for item in selection["documents"]:
        source = corpus / item["relative_path"]
        sha = file_hash(source)
        if sha != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {item['document_id']}")
        document_result_path = reusable.get(item["document_id"])
        if document_result_path:
            payload = json.loads(document_result_path.read_text(encoding="utf-8"))
            if payload.get("document_id") != sha:
                raise ValueError(f"DocumentResult source hash mismatch for {item['document_id']}")
            processing = "reused immediately preceding full PDF run"
        else:
            payload = processor.process(source).model_dump(mode="json")
            processing = "DocumentProcessor(mode=auto,use_cache=False,allow_fallback=True)"
        document_result_path = out / "document_results" / f"{item['document_id']}.document_result.json"
        document_result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        prediction = analyzer.analyze(payload)
        pred_path = out / "predictions" / f"{item['document_id']}.prediction.json"
        pred_path.write_text(prediction.model_dump_json(indent=2) + "\n", encoding="utf-8")
        pages = payload["pages"]
        evidence_sources = sorted({element["source"] for page in pages for element in page["elements"]})
        entries.append({
            **item,
            "processing": processing,
            "document_intelligence_contract_version": document_intelligence_contract_version,
            "document_intelligence_mode": payload.get("mode"),
            "evidence_sources": evidence_sources,
            "page_count": len(pages),
            "ocr_pages": sum(page["diagnostics"]["ocr_used"] for page in pages),
            "fallback_pages": sum(page["diagnostics"]["fallback_used"] for page in pages),
            "evidence_elements": sum(len(page["elements"]) for page in pages),
            "prediction_file": f"predictions/{item['document_id']}.prediction.json",
            "document_result_file": f"document_results/{item['document_id']}.document_result.json",
            "prediction_counts": {
                "sections": len(prediction.sections), "articles_top_level": len(prediction.articles),
                "annexes": len(prediction.annexes), "requirements": len(prediction.requirements),
                "detected_special_documents": len(prediction.detected_special_documents),
            },
            "ground_truth_status": "DRAFT",
            "scored": False,
        })
        print(f"{item['document_id']}: pages={len(pages)} OCR={sum(p['diagnostics']['ocr_used'] for p in pages)} "
              f"sections={len(prediction.sections)} articles={len(prediction.articles)} annexes={len(prediction.annexes)}")

    results = {
        "corpus": "CDC_DEVELOPMENT_CORPUS_V1",
        "baseline": "CDC_ANALYZER_REAL_BASELINE_V1",
        "tested_commit": "cc6e4566d62954f0bc4d0820f833dbd39e9b5994",
        "document_intelligence_contract_version": document_intelligence_contract_version,
        "cdc_analyzer_version": "CDC_ANALYZER_BASELINE_V1",
        "execution_scope": "End-to-end PDF -> Document Intelligence DocumentResult -> CDC Analyzer TenderDocument.",
        "documents": entries,
        "gate_result": "NOT YET MEASURABLE: pilot ground truth remains in draft pending source-evidence annotation review",
    }
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
