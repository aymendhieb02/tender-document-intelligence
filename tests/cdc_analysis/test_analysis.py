import json
import sys
from pathlib import Path

import pytest

from app.cdc_analysis import CDCAnalyzer, DocumentInput
from app.cdc_analysis.benchmark import evaluate, structural_records
from app.cdc_analysis.headings import HeadingDetector, LanguagePack
from app.cdc_analysis.schema import Review, TenderDocument
from app.cdc_analysis.__main__ import main as cdc_main


def document(*pages):
    return {"document_id": "test", "pages": [
        {"page_number": i, "width": 600, "height": 800, "coordinate_space": "pdf_points",
         "elements": [{"id": f"p{i}-{j}", **({"text": e} if isinstance(e, str) else e)}
                      for j, e in enumerate(elements)]}
        for i, elements in enumerate(pages, 1)]}


@pytest.mark.parametrize("text,kind,number", [
    ("ARTICLE 1", "article", "1"), ("Article 2 : Objet", "article", "2"),
    ("ARTICLE N° 1", "article", "1"), ("Art. 1", "article", "1"),
    ("A — Conditions", "section", "A"), ("B - Technique", "section", "B"),
    ("ANNEXE 01", "annex", "01"), ("ANNEXE N°1", "annex", "1"),
    ("ANNEXE 1", "annex", "1"), ("1.2 Procédure", "subsection", "1.2"),
])
def test_patterns(text, kind, number):
    heading = HeadingDetector(LanguagePack()).detect(text)
    assert (heading.kind, heading.number) == (kind, number)


def test_hierarchy_ranges_and_provenance():
    value = document(["Cahier des Charges", "A - Consultation", "1.1 Modalités", "Article 1 - Objet", "Premier paragraphe"],
                     [{"text": "1.1 Clause", "bbox": [20, 120, 560, 145]}, "suite de la clause"],
                     ["Article 2 : Durée", "Délai d'exécution : 30 jours"], ["B - Technique", "Article 1 : Matériel"])
    result = CDCAnalyzer().analyze(value)
    a, b = result.sections
    assert (a.start_page, a.end_page, b.start_page) == (1, 3, 4)
    first = a.subsections[0].articles[0]
    assert (first.page_start, first.page_end) == (1, 2)
    assert "suite de la clause" in first.text
    assert first.clauses[1].number == "1.1"
    ev = first.clauses[1].source_evidence[0]
    assert (ev.page, ev.element_id, ev.bbox, ev.coordinate_space) == (2, "p2-0", (20, 120, 560, 145), "pdf_points")
    assert result.requirements[0].type == "execution_duration"
    assert result.requirements[0].normalized_value is None
    assert result.title == "Cahier des Charges"
    assert TenderDocument.model_validate_json(result.model_dump_json()) == result


def test_annex_boq_handoff_and_table_boundary():
    result = CDCAnalyzer().analyze(document(["D — Annexes", "Annexe 01 - Bordereau des prix – devis estimatif",
        {"kind": "table", "text": "article quantity total TVA", "table_id": "upstream-table"}],
        ["Annexe 02 - Fiche technique", "description"]))
    assert [a.annex_type for a in result.annexes] == ["boq", "technical_sheet"]
    assert result.annexes[0].page_end == 1
    assert result.tables[0].table_id == "upstream-table"
    assert result.tables[0].table_type == "boq"
    assert result.annexes[0].paragraphs == []
    assert result.requirements == []
    assert result.detected_special_documents[0].handoff == "boq_agent"


def test_repeated_margin_and_explicit_furniture_suppressed():
    pages = [[{"text": "A - Institution", "bbox": [0, 5, 300, 30]},
              {"text": f"Page {i}", "bbox": [200, 760, 300, 790]},
              {"text": "Article 99", "kind": "header"},
              "A - Conditions" if i == 1 else "texte"] for i in range(1, 4)]
    result = CDCAnalyzer().analyze(document(*pages))
    assert len(result.sections) == 1
    assert len(result.furniture_evidence) == 9
    assert result.sections[0].end_page == 3


def test_repeated_body_not_suppressed():
    result = CDCAnalyzer().analyze(document(["A - Conditions", "Obligation"], ["Obligation"], ["Obligation"]))
    assert len(result.sections[0].paragraphs) == 3


def test_toc_disagreement_and_unconfirmed_do_not_create_nodes():
    result = CDCAnalyzer().analyze(document(["Sommaire", "A - Conditions .... 8", "B - Fantôme .... 9"],
                                          ["A - Conditions", "Article 1 - Objet", "corps"]))
    assert len(result.sections) == 1
    assert result.sections[0].start_page == 2
    assert result.sections[0].signals["toc_match"]
    assert {d.code for d in result.diagnostics} >= {"toc_disagreement", "toc_unconfirmed"}


def test_unknown_heading_missing_fields_and_orphan_articles():
    result = CDCAnalyzer().analyze(document(["Article 1", "texte", {"kind": "heading", "text": "Unusual Heading"}, "contenu"]))
    assert result.articles[0].title is None
    assert result.title is None
    assert result.sections[0].title == "Unusual Heading"
    assert result.sections[0].number is None
    assert result.sections[0].evidence_status == "probable"
    assert CDCAnalyzer().analyze({"document_id": "empty"}).sections == []


def test_inline_reference_not_heading():
    result = CDCAnalyzer().analyze(document(["A - Conditions", "Article 1 du présent cahier définit les conditions."]))
    assert result.sections[0].articles == []


def test_split_titles_and_annex_spanning_pages():
    result = CDCAnalyzer().analyze(document(
        ["A -", {"text": "Conditions", "kind": "heading"}, "Article 1", {"text": "Objet", "bold": True}, "corps"],
        ["D - Annexes", "Annexe 01", {"text": "Bordereau des prix – devis estimatif", "kind": "heading"}],
        [{"kind": "table", "table_id": "t1"}], ["Annexe 02 - Déclaration sur l'honneur"]))
    assert result.sections[0].title == "Conditions"
    assert result.sections[0].articles[0].title == "Objet"
    assert len(result.sections) == 2
    assert result.annexes[0].annex_type == "boq"
    assert (result.annexes[0].page_start, result.annexes[0].page_end) == (2, 3)
    assert result.detected_special_documents[0].page_end == 3


def test_multiline_original_evidence_and_same_page_boundaries():
    raw = "A - Conditions\nArticle 1 - Objet\ntexte\nArticle 2 - Durée\nsuite"
    result = CDCAnalyzer().analyze(document([raw]))
    articles = result.sections[0].articles
    assert [a.page_end for a in articles] == [1, 1]
    assert articles[1].source_evidence[0].line_index == 3
    assert articles[1].source_evidence[0].raw_text == raw


def test_missing_hierarchy_parent_and_duplicate_article_are_reviewable():
    result = CDCAnalyzer().analyze(document([
        {"text": "Sous-section isolée", "kind": "heading", "heading_level": 3},
        "Article 1 - Premier", "texte", "Article 1 - Répétition"]))
    assert {d.code for d in result.diagnostics} >= {"hierarchy_gap", "duplicate_article_number"}


def test_unknown_annex_and_unassigned_content_retained():
    result = CDCAnalyzer().analyze(document(["Préambule", "Annexe 9 - Divers", "Contenu inconnu"]))
    assert result.paragraphs[0].text == "Préambule"
    assert result.annexes[0].paragraphs[0].text == "Contenu inconnu"
    assert result.annexes[0].annex_type == "unknown"
    assert any(d.code == "unknown_annex_type" for d in result.diagnostics)


def test_custom_language_pack_and_adapter():
    class Adapter:
        def adapt(self, source):
            return DocumentInput.model_validate(document([source]))
    pack = LanguagePack(article=r"^الفصل\s+(?P<number>\d+)\s*(?P<title>.*)$")
    result = CDCAnalyzer(pack, Adapter()).analyze("الفصل 1 شروط")
    assert result.articles[0].number == "1"


def test_input_order_and_unsupported_contract_rejected():
    value = document(["one"], ["two"])
    value["pages"].reverse()
    with pytest.raises(ValueError):
        CDCAnalyzer().analyze(value)
    with pytest.raises(TypeError):
        CDCAnalyzer().analyze(object())


def test_public_document_result_contract_adapter_without_producer_imports():
    producer = {
        "document_id": "producer-test", "source_type": "pdf", "mode": "native",
        "diagnostics": {"processing_ms": 0, "timings_ms": {}, "missing_geometry_count": 0,
                        "ocr_page_count": 0, "fallback_page_count": 0, "cache_enabled": False},
        "pages": [{"page_number": 1, "width": 600, "height": 800, "coordinate_space": "rendered_page_pixels",
                   "elements": [{"id": "original-id", "text": "A - Conditions", "page_number": 1,
                                 "bbox": {"x1": 20, "y1": 120, "x2": 560, "y2": 150},
                                 "source": "native_pdf", "source_coordinate_space": "pdf_unrotated_points",
                                 "source_to_page": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}]}]}
    result = CDCAnalyzer().analyze(producer)
    assert result.sections[0].source_evidence[0].source_element_ids == ["original-id"]
    assert result.sections[0].source_evidence[0].bbox == (20, 120, 560, 150)
    assert result.sections[0].source_evidence[0].coordinate_space == "rendered_page_pixels"
    assert result.tables == []
    assert CDCAnalyzer().analyze(producer) == result


def test_reviews_keep_machine_value_and_evidence():
    result = CDCAnalyzer().analyze(document(["A - Conditions"]))
    result.reviews.append(Review(target_id="section-1", field="title", machine_value="Conditions",
                                reviewed_value="Conditions générales", reviewer="human", reviewed_at="2026-09-28"))
    assert result.sections[0].title == "Conditions"
    assert result.sections[0].source_evidence[0].raw_text == "A - Conditions"


def test_synthetic_fixture_and_benchmark_gate():
    root = Path(__file__).resolve().parents[2]
    value = json.loads((root / "dataset/cdc/raw/tunisian_structure_synthetic.json").read_text(encoding="utf-8"))
    result = CDCAnalyzer().analyze(value)
    assert [s.number for s in result.sections] == ["A", "B", "C", "D"]
    assert result.annexes[-1].annex_type == "boq"
    assert evaluate(result, {"status": "unverified"})["status"] == "NOT YET MEASURABLE"
    # Exercise metric arithmetic with synthetic labels only, not corpus accuracy.
    labels = {"status": "verified", "reviewer": "test-only", "verified_at": "test-only",
              "source_sha256": "test-only", "document_id": result.document_id,
              "records": {"sections": structural_records(result)["sections"]}}
    labels["records"]["sections"][0]["end"] = 999
    metrics = evaluate(result, labels)["metrics"]
    assert metrics["sections"]["recall"] == .75
    assert "requirements" not in metrics


def test_real_reference_document_result_integration():
    root = Path(__file__).resolve().parents[2]
    source = root / "dataset/cdc/document_results/MM_Cahier-des-charges-type-Entretien.document_result.json"
    prediction_path = root / "dataset/cdc/predictions/MM_Cahier-des-charges-type-Entretien.prediction.json"
    if not source.exists() or not prediction_path.exists():
        pytest.skip("Run the real Document Intelligence producer fixture first")
    producer_result = json.loads(source.read_text(encoding="utf-8"))
    result = CDCAnalyzer().analyze(producer_result)
    assert len(producer_result["pages"]) == 30
    assert [section.number for section in result.sections] == ["A", "B", "C", "D", "E"]
    section_a, section_b, section_c, section_d, section_e = result.sections
    assert (section_a.start_page, section_a.end_page, len(section_a.articles)) == (3, 9, 27)
    assert (section_b.start_page, section_b.end_page, len(section_b.articles)) == (10, 11, 9)
    assert (section_c.start_page, section_c.end_page) == (12, 19)
    assert (section_d.start_page, section_d.end_page) == (20, 28)
    assert (section_e.start_page, section_e.end_page) == (29, 29)
    assert len(section_c.subsections) == 4
    assert [len(parent.subsections) for parent in section_c.subsections] == [8, 3, 5, 4]
    assert [(annex.number, annex.page_start, annex.page_end) for annex in result.annexes] == [
        ("01", 21, 21), ("02", 22, 22), ("03", 23, 23), ("04", 24, 24),
        ("05", 25, 25), ("06", 26, 28)]
    assert result.annexes[-1].title == "Engagements de cautions personnelles et solidaires au titre de :"
    assert any(evidence.page == 20 for evidence in result.annexes[-1].source_evidence)
    assert [child.number for child in result.annexes[-1].subsections] == ["6.1", "6.2", "6.3"]
    assert [(child.start_page, child.end_page) for child in result.annexes[-1].subsections] == [(26, 26), (27, 27), (28, 28)]
    boq = next(item for item in result.detected_special_documents if item.document_type == "boq")
    assert (boq.page_start, boq.page_end, boq.source_node, boq.handoff) == (25, 25, "annex-5", "boq_agent")
    assert result.tables == []
    normalized = {item.type: item.normalized_value for item in result.requirements if item.normalized_value is not None}
    assert normalized["offer_validity"]["value"] == 60
    assert normalized["final_guarantee"]["value"] == 3
    assert normalized["retention_guarantee"]["value"] == 10
    assert normalized["delay_penalty"]["denominator"] == 1000
    assert normalized["guarantee_period"]["value"] == 1
    assert normalized["order_volume_variation"]["value"] == 20
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    assert TenderDocument.model_validate(prediction) == result
    ground_truth_path = root / "dataset/cdc/ground_truth/MM_Cahier-des-charges-type-Entretien.structure.json"
    manifest = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    assert prediction_path.resolve() != ground_truth_path.resolve()
    assert manifest["verification_status"] == "human_review_required"
    assert evaluate(result, manifest)["status"] == "NOT YET MEASURABLE"
    assert result.sections[0].source_evidence[0].source_element_ids
    assert all(requirement.review_status == "needs_review" for requirement in result.requirements)
    assert all(requirement.reviewed_business_interpretation is None for requirement in result.requirements)
    assert all(requirement.extraction_status in ("extracted_value", "candidate_only") for requirement in result.requirements)


def test_cli_refuses_prediction_inside_ground_truth(tmp_path, monkeypatch):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(document(["A - Consultation"])), encoding="utf-8")
    output = tmp_path / "ground_truth" / "manifest.json"
    monkeypatch.setattr(sys, "argv", ["cdc", str(source), "--output", str(output)])
    with pytest.raises(SystemExit) as error:
        cdc_main()
    assert error.value.code == 2
    assert not output.exists()
