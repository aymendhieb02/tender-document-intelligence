from app.cdc_analysis.schema import Article, Evidence, Requirement, TenderDocument
from app.requirements_intelligence import (
    MandatoryStatus,
    RequirementCategory,
    RequirementReviewStatus,
    classify_document,
    classify_text,
)


def evidence(text: str = "source wording", *, page: int = 3) -> Evidence:
    return Evidence(document_id="doc-1", page=page, element_id="cdc-element-7",
                    raw_text=text, source_element_ids=["producer-word-11", "producer-word-12"])


def test_french_explicit_obligation_and_evidence_are_preserved():
    source = evidence("Le candidat doit fournir une attestation fiscale.")
    item = classify_text(source.raw_text, evidence=[source], source_article_id="article-4")

    assert item.category == RequirementCategory.REQUIRED_DOCUMENT
    assert item.mandatory_status == MandatoryStatus.MANDATORY
    assert item.responsible_party == "Le candidat"
    assert item.action == "submit"
    assert item.source_article_id == "article-4"
    assert item.evidence == (source,)
    assert item.evidence_ids == ("cdc-element-7", "producer-word-11", "producer-word-12")
    assert item.page == 3
    assert item.review_status == RequirementReviewStatus.NEEDS_REVIEW


def test_arabic_obligation_categorizes_bank_guarantee():
    source = evidence("يلتزم المتعهد بتقديم ضمان بنكي")
    item = classify_text(source.raw_text, evidence=[source])

    assert item.category == RequirementCategory.GUARANTEE
    assert item.mandatory_status == MandatoryStatus.MANDATORY
    assert item.action == "submit"


def test_optional_and_conditional_wording_do_not_become_unconditional_mandatory():
    optional = classify_text("Le candidat peut fournir une assurance facultative.", evidence=[evidence()])
    conditional = classify_text(
        "Si le candidat est retenu, il doit présenter son certificat.", evidence=[evidence()])

    assert optional.category == RequirementCategory.INSURANCE
    assert optional.mandatory_status == MandatoryStatus.OPTIONAL
    assert conditional.category == RequirementCategory.REQUIRED_DOCUMENT
    assert conditional.mandatory_status == MandatoryStatus.CONDITIONAL
    assert conditional.condition.startswith("Si le candidat")


def test_personnel_equipment_guarantee_and_eligibility_taxonomy():
    texts_and_categories = [
        ("Le soumissionnaire doit fournir un ingénieur qualifié.", RequirementCategory.PERSONNEL),
        ("Le titulaire doit disposer du matériel requis.", RequirementCategory.EQUIPMENT),
        ("Une caution provisoire est obligatoire.", RequirementCategory.GUARANTEE),
        ("Les conditions d'éligibilité doivent être respectées.", RequirementCategory.ELIGIBILITY),
    ]
    for text, expected in texts_and_categories:
        assert classify_text(text, evidence=[evidence(text)]).category == expected


def test_ambiguous_text_stays_unclear_and_no_evidence_is_never_invented():
    item = classify_text("Garantie bancaire.", evidence=[evidence("Garantie bancaire.")])

    assert item.category == RequirementCategory.GUARANTEE
    assert item.mandatory_status == MandatoryStatus.UNCLEAR
    assert item.page == 3
    assert item.evidence_ids
    try:
        classify_text("Le candidat doit fournir un document.", evidence=[])
    except ValueError as exc:
        assert "existing source evidence" in str(exc)
    else:
        raise AssertionError("classification without source evidence must fail")


def test_document_consumes_cdc_output_and_never_adds_values_or_pages():
    source = evidence("Le candidat doit présenter son offre.", page=8)
    candidate = Requirement(id="candidate-2", type="submission_documents", text=source.raw_text,
                            source_page=8, source_article="article-9", source_evidence=[source])
    document = TenderDocument(
        document_id="doc-1",
        requirements=[candidate],
        articles=[Article(id="article-9", title="Offres", text=source.raw_text,
                          page_start=8, page_end=8, source_evidence=[source])],
    )

    output = classify_document(document)

    assert len(output) == 1
    assert output[0].category == RequirementCategory.SUBMISSION
    assert output[0].source_requirement_id == "candidate-2"
    assert output[0].page == 8
    assert output[0].evidence == (source,)
    assert output[0].related_value_refs == ()
    assert output[0].model_dump(mode="json")["related_value_refs"] == []


def test_document_skips_semantics_when_cdc_item_has_no_evidence():
    document = TenderDocument(document_id="doc-1", requirements=[
        Requirement(id="candidate-3", type="eligibility", text="must submit", source_page=0,
                    source_evidence=[]),
    ])

    assert classify_document(document) == []
