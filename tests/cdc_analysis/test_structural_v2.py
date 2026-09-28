from app.cdc_analysis import CDCAnalyzer
from app.cdc_analysis.headings import HeadingDetector, LanguagePack


def _element(element_id, text, box):
    return {"id": element_id, "text": text, "bbox": box, "source_type": "native_pdf"}


def _document(elements):
    return {"document_id": "structural-v2-test", "pages": [{
        "page_number": 1, "width": 800, "height": 1000, "coordinate_space": "pdf_points",
        "elements": elements,
    }]}


def test_french_article_and_arabic_article_number_forms():
    detector = HeadingDetector(LanguagePack())
    assert (detector.detect("Article 12 : Objet").kind, detector.detect("Article 12 : Objet").number) == ("article", "12")
    assert detector.detect("الفصل 12: موضوع").number == "12"
    assert detector.detect("الفصل ١٢: موضوع").number == "12"
    assert detector.detect("الفصل األول : موضوع").number == "1"
    assert detector.detect("الفصل الثاني: موضوع").number == "2"


def test_split_arabic_heading_tokens_are_composed_and_provenance_is_retained():
    # Deliberately scrambled source order; visual geometry gives the RTL token order.
    source = _document([
        _element("title", "الموضوع", (300, 100, 390, 130)),
        _element("punct", ":", (420, 100, 428, 130)),
        _element("number", "٣", (435, 100, 450, 130)),
        _element("cue", "الفصل", (460, 100, 530, 130)),
    ])
    result = CDCAnalyzer().analyze(source)
    assert [(article.number, article.title) for article in result.articles] == [("3", "الموضوع")]
    evidence = result.articles[0].source_evidence[0]
    assert evidence.page == 1
    assert evidence.source_element_ids == ["cue", "number", "punct", "title"]
    assert evidence.source_text_parts == ["الفصل", "٣", ":", "الموضوع"]


def test_partie_hierarchy_and_lot_are_distinct_from_sections_and_annexes():
    source = _document([
        _element("part-i", "Partie", (250, 100, 310, 125)),
        _element("part-i-number", "I", (318, 100, 328, 125)),
        *[_element(f"i-title-{i}", word, (100 + 44 * i, 135, 140 + 44 * i, 160))
          for i, word in enumerate("Cahier des Clauses Administratives Particulières".split())],
        _element("article", "Article 1 - Objet", (100, 180, 300, 205)),
        _element("lot", "II. Lot n°1 : Plateforme", (100, 220, 360, 245)),
        _element("body", "Cette partie décrit le lot n°2 dans le texte.", (100, 260, 430, 285)),
        _element("part-ii", "PARTIE", (250, 320, 320, 345)),
        _element("part-ii-number", "II", (328, 320, 350, 345)),
        *[_element(f"ii-title-{i}", word, (100 + 44 * i, 355, 140 + 44 * i, 380))
          for i, word in enumerate("Cahier des Clauses Techniques Particulières".split())],
        _element("annex", "Annexe 01 - Bordereau des prix", (100, 400, 400, 425)),
    ])
    result = CDCAnalyzer().analyze(source)
    assert [(section.number, section.structural_type, section.title) for section in result.sections] == [
        ("I", "part", "Cahier des Clauses Administratives Particulières"),
        ("II", "part", "Cahier des Clauses Techniques Particulières"),
    ]
    assert [article.number for article in result.sections[0].articles] == ["1"]
    assert [(lot.number, lot.source_section) for lot in result.lots] == [("1", result.sections[0].id)]
    assert [(annex.number, annex.annex_type) for annex in result.annexes] == [("01", "price_schedule")]


def test_partie_variants_and_non_heading_mentions():
    detector = HeadingDetector(LanguagePack())
    assert detector.detect("Partie I").kind == "part"
    assert detector.detect("PARTIE II").number == "II"
    assert detector.detect("Partie 1").number == "1"
    assert detector.detect("Partie 2").number == "2"
    assert detector.detect("Cette partie décrit le lot n°2") is None
    assert detector.detect("Le lot n°2 est cité dans ce paragraphe") is None
    assert detector.detect("Le montant du lot est de 1200 dinars") is None
    assert detector.detect("Lot 500 DT") is None
    assert detector.detect("Annexe 01 - Bordereau des prix").kind == "annex"
    assert detector.detect("La procédure comprend plusieurs parties.") is None
