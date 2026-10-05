from app.ask_tender import service
from app.cdc_analysis.schema import Article, Evidence, TenderDocument


def sample_document():
    evidence = Evidence(document_id="doc-1", page=7, element_id="el-1", raw_text="Warranty lasts two years.")
    article = Article(id="article-15", number="15", title="Warranty", text="Warranty lasts two years.",
                     page_start=7, page_end=7, source_evidence=[evidence])
    return TenderDocument(document_id="doc-1", articles=[article])


def test_retrieval_is_ranked_and_carries_v2_evidence_reference():
    items = service.retrieve(sample_document(), "What does the tender say about warranty?")
    assert items
    assert items[0].label == "Article 15 Warranty"
    assert items[0].reference.page_number == 7
    assert items[0].reference.element_id == "el-1"


def test_insufficient_evidence_does_not_call_model(monkeypatch):
    monkeypatch.setattr(service, "_ollama", lambda *args: (_ for _ in ()).throw(AssertionError("no evidence")))
    result = service.answer_question(sample_document(), "What is the submission deadline?")
    assert result.status == "insufficient_evidence"
    assert "not found" in result.answer
    assert result.evidence == []


def test_structured_deadline_fast_path_uses_fact_evidence():
    evidence = service.AskEvidence(kind="financial_fact", label="Financial fact fin-1 · submission deadline",
        text="31 October 2026", status="normalized")
    assert service.fast_path("What is the submission deadline?", [evidence]) == (
        "Financial fact fin-1 · submission deadline: 31 October 2026")


def test_ollama_unavailable_returns_cited_review_fallback(monkeypatch):
    monkeypatch.setattr(service, "_ollama", lambda *args: (None, "llama3.2:3b"))
    result = service.answer_question(sample_document(), "Summarize Article 15")
    assert result.status == "generation_unavailable"
    assert result.backend == "ollama"
    assert result.evidence[0].reference.page_number == 7


def test_ollama_success_and_timeout_boundary(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"response": "The warranty lasts two years."}
    monkeypatch.setattr(service.requests, "post", lambda *args, **kwargs: Response())
    answer, model = service._ollama("warranty?", service.retrieve(sample_document(), "warranty"))
    assert answer == "The warranty lasts two years."
    assert model == "llama3.2:3b"
    def timeout(*args, **kwargs):
        raise service.requests.Timeout("timed out")
    monkeypatch.setattr(service.requests, "post", timeout)
    answer, model = service._ollama("warranty?", [])
    assert answer is None
    assert model == "llama3.2:3b"


def test_french_procurement_paraphrases_retrieve_expected_evidence_in_top_three(monkeypatch):
    # Synthetic reviewed retrieval set: evaluate evidence reachability, not answer accuracy.
    passages = [
        (3, "Les offres doivent parvenir au plus tard le 31 octobre 2026 au bureau d’ordre."),
        (4, "La caution provisoire est fixée à 1 000 dinars."),
        (5, "Le délai d’exécution des travaux est de 60 jours."),
        (6, "Les pièces à fournir comprennent le registre et l’attestation fiscale."),
    ]
    articles = [Article(id=f"a-{page}", number=str(page), text=text, page_start=page, page_end=page,
                        source_evidence=[Evidence(document_id="synthetic-retrieval", page=page,
                                                  element_id=f"e-{page}", raw_text=text)])
                for page, text in passages]
    document = TenderDocument(document_id="synthetic-retrieval", articles=articles)
    questions = [
        ("Jusqu'à quand peut-on déposer l'offre ?", 3),
        ("Quel est le montant de la garantie provisoire ?", 4),
        ("Quelle est la durée des travaux ?", 5),
        ("Quels documents sont demandés ?", 6),
    ]
    for question, expected_page in questions:
        ranked = service.retrieve(document, question, limit=3)
        assert expected_page in [item.reference.page_number for item in ranked], question
    monkeypatch.setattr(service, "_ollama", lambda *args: (None, "offline"))
    result = service.answer_question(document, questions[0][0])
    assert result.status == "generation_unavailable"
    assert result.evidence and result.evidence[0].reference.page_number == 3


def test_expanded_procurement_concepts_rank_observed_passages_without_fabricating_facts():
    passages = [
        (1, "Le bureau d'ordre à Tunis est le lieu de dépôt des offres.", "Où déposer l'offre ?"),
        (2, "La garantie définitive sera fournie après attribution.", "Quelle est la caution définitive ?"),
        (3, "La validité des offres est de 90 jours.", "Quelle durée de validité pour l'offre ?"),
        (4, "Les modalités de paiement sont définies à l'article 12.", "Quelles conditions de paiement ?"),
        (5, "Des pénalités de retard s'appliquent après le délai.", "Quelles pénalités de retard ?"),
        (6, "Les critères d'évaluation incluent le prix et la technique.", "Quels critères de sélection ?"),
        (7, "Le devis estimatif figure dans l'annexe.", "Où est le bordereau des prix ?"),
    ]
    document = TenderDocument(document_id="synthetic-concepts", articles=[
        Article(id=f"a-{page}", number=str(page), text=text, page_start=page, page_end=page,
                source_evidence=[Evidence(document_id="synthetic-concepts", page=page,
                                          element_id=f"e-{page}", raw_text=text)])
        for page, text, _ in passages])
    ranks = []
    for expected_page, _, question in passages:
        pages = [item.reference.page_number for item in service.retrieve(document, question, limit=7)]
        ranks.append(pages.index(expected_page) + 1 if expected_page in pages else None)
    assert sum(rank == 1 for rank in ranks) >= 5
    assert all(rank is not None and rank <= 3 for rank in ranks)


def test_retrieval_deduplicates_same_evidence_passage():
    evidence = Evidence(document_id="doc", page=1, element_id="same", raw_text="Validité des offres: 90 jours")
    article = Article(id="a", number="1", text="Validité des offres: 90 jours",
                      page_start=1, page_end=1, source_evidence=[evidence])
    document = TenderDocument(document_id="doc", articles=[article, article])
    found = service.retrieve(document, "validité des offres", limit=6)
    assert len(found) == 1
