from app.cdc_analysis.schema import (
    Annex, Article, Evidence, Requirement, Section, SpecialDocument, TenderDocument,
)
from app.tender_summary import FactState, build_tender_summary


def evidence(page=2, element_id="el-7", raw_text="Validité de l'offre: 60 jours"):
    return Evidence(document_id="doc-1", page=page, element_id=element_id,
                    raw_text=raw_text, bbox=(10, 20, 200, 40),
                    coordinate_space="rendered_page_pixels",
                    source_element_ids=[element_id, f"{element_id}-word"],
                    source_text_parts=[raw_text], source_element_types=["text"],
                    source_element_confidences=[None])


def requirement(kind, value, *, status="extracted_value", review="needs_review", page=2):
    return Requirement(id=f"req-{kind}-{page}", type=kind, text=f"source wording {kind}",
                       normalized_value=value, source_page=page,
                       source_evidence=[evidence(page, f"el-{kind}-{page}", f"source wording {kind}")],
                       extraction_status=status, review_status=review,
                       evidence_status="detected" if value is not None else "probable")


def complete_document():
    article = Article(id="article-1", number="1", title="Submission", text="Offers validity",
                      page_start=2, page_end=2, source_evidence=[evidence()],
                      clauses=[])
    section = Section(id="section-1", number="1", title="Tender", normalized_title="tender",
                      start_page=1, end_page=3, source_evidence=[evidence(1, "heading")],
                      articles=[article])
    annex = Annex(id="annex-1", number="A", title="Bordereau des prix",
                  page_start=8, page_end=10, annex_type="boq", source_section=None,
                  source_evidence=[evidence(8, "boq-heading")])
    return TenderDocument(
        document_id="doc-1", title="Road works", title_evidence=[evidence(1, "title", "Road works")],
        metadata={"reference": "TN-42", "contracting_organization": "Municipality",
                  "procurement_type": "open", "language": "fr", "publication_date": "2026-01-01",
                  "submission_deadline": {"value": "2026-02-01", "evidence": [evidence(1, "deadline")]},
                  "page_count": 10},
        sections=[section], annexes=[annex], detected_special_documents=[
            SpecialDocument(id="special-boq", document_type="boq", page_start=8, page_end=10,
                            source_node="annex-1", source_evidence=[evidence(8, "boq-heading")])],
        requirements=[
            requirement("offer_validity", {"value": 60, "unit": "days"}, review="needs_review"),
            requirement("final_guarantee", {"value": 3, "unit": "percent"}, page=3),
            requirement("retention_guarantee", {"value": 10, "unit": "percent"}, page=4),
            requirement("delay_penalty", {"numerator": 1, "denominator": 1000}, page=5),
            requirement("delay_penalty_cap", {"value": 10, "unit": "percent"}, page=5),
            requirement("execution_deadline", None, status="candidate_only", page=6),
        ],
    )


def test_complete_summary_maps_facts_counts_and_boq_pages():
    summary = build_tender_summary(complete_document())

    assert summary.identity["title"].value == "Road works"
    assert summary.identity["reference"].value == "TN-42"
    assert summary.dates["publication"].value == "2026-01-01"
    assert summary.dates["submission_deadline"].evidence[0].element_id == "deadline"
    assert summary.dates["offer_validity"].value == {"value": 60, "unit": "days"}
    assert summary.financial["final_performance_guarantee"].value["value"] == 3
    assert summary.financial["retention"].value["value"] == 10
    assert summary.structure["section_count"].value == 1
    assert summary.structure["article_count"].value == 1
    assert summary.structure["annex_count"].value == 1
    assert summary.boq.detected.state == FactState.PRESENT
    assert summary.boq.detected.value is True
    assert summary.boq.pages == list(range(8, 11))
    assert summary.requirements.by_category["offer_validity"] == 1
    assert summary.requirements.review_required == 6


def test_sparse_and_template_document_keep_missing_values_null():
    summary = build_tender_summary(TenderDocument(document_id="template-1", metadata={"is_template": True}))

    assert summary.identity["title"].state == FactState.MISSING
    assert summary.dates["publication"].value is None
    assert summary.dates["submission_deadline"].state == FactState.MISSING
    assert summary.financial["penalties"].value is None
    assert summary.boq.detected.state == FactState.MISSING
    assert summary.boq.detected.value is None
    assert summary.boq.pages is None
    assert summary.source_coverage.total_pages is None
    assert "identity.title" in summary.missing_or_ambiguous


def test_ambiguous_values_keep_all_evidence_and_candidate_ids():
    doc = TenderDocument(document_id="doc-1", requirements=[
        requirement("offer_validity", {"value": 30, "unit": "days"}, page=2),
        requirement("offer_validity", {"value": 60, "unit": "days"}, page=3),
    ])

    fact = build_tender_summary(doc).dates["offer_validity"]
    assert fact.state == FactState.AMBIGUOUS
    assert fact.value is None
    assert fact.candidate_ids == ["req-offer_validity-2", "req-offer_validity-3"]
    assert [item.page for item in fact.evidence] == [2, 3]


def test_candidate_without_normalized_value_is_needs_review_not_zero_or_false():
    doc = TenderDocument(document_id="doc-1", requirements=[
        requirement("final_guarantee", None, status="candidate_only")])

    fact = build_tender_summary(doc).financial["final_performance_guarantee"]
    assert fact.state == FactState.NEEDS_REVIEW
    assert fact.value is None
    assert fact.evidence[0].raw_text == "source wording final_guarantee"


def test_counts_include_nested_articles_and_requirement_review_count():
    nested_article = Article(id="a2", number="2", page_start=3, page_end=3,
                             source_evidence=[evidence(3, "a2")])
    child = Section(id="s2", number="1.1", title="Nested", start_page=3, end_page=3,
                    source_evidence=[evidence(3, "s2")], articles=[nested_article])
    top = Section(id="s1", number="1", title="Root", start_page=1, end_page=4,
                  source_evidence=[evidence(1, "s1")], subsections=[child])
    summary = build_tender_summary(TenderDocument(document_id="doc-1", sections=[top],
                                                 requirements=[requirement("foo", None)]))

    assert summary.structure["section_count"].value == 2
    assert summary.structure["article_count"].value == 1
    assert summary.requirements.review_required == 1


def test_summary_is_deterministic_for_model_and_json_input():
    doc = complete_document()
    first = build_tender_summary(doc).model_dump(mode="json")
    second = build_tender_summary(doc.model_dump(mode="json")).model_dump(mode="json")

    assert first == second
