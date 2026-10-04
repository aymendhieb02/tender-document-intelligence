from decimal import Decimal
import csv
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.boq.adapter import adapt_page
from app.boq.detect import detect_male_municipal_v1
from app.boq.evaluate import evaluate
from app.boq.extractor import extract_male_municipal_from_document, extract_male_municipal_v1
from app.boq.normalize import normalize_header, parse_french_decimal
from app.boq.detect import normalize_male_municipal_header
from app.boq.models import BOQDocument, BOQRow, BoundingBox, ParsedValue
from app.boq.export import CSV_COLUMNS, export_boq_csv
from app.boq.generic import FAMILY as GENERIC_FAMILY, extract_boq_candidates, extract_generic_boq
from app.boq.validate import validate_document, validate_row
try:
    from app.document_intelligence.schemas import DocumentDiagnostics, DocumentResult, EvidenceElement, PageResult
except ModuleNotFoundError:
    DocumentDiagnostics = DocumentResult = EvidenceElement = PageResult = None


def make_evidence(*, id, text, page_number, bbox, confidence=None, source="native_pdf", source_coordinate_space="pdf_unrotated_points", native_order=None):
    values = dict(id=id,text=text,page_number=page_number,bbox=bbox,confidence=confidence,source=source,
        source_bbox=bbox,source_coordinate_space=source_coordinate_space,
        source_to_page=[[1,0,0],[0,1,0],[0,0,1]],native_order=native_order)
    if EvidenceElement and isinstance(bbox, BoundingBox):
        values["bbox"] = bbox.model_dump()
        values["source_bbox"] = bbox.model_dump()
    return EvidenceElement(**values) if EvidenceElement else SimpleNamespace(**values)


def make_page(*, page_number, width, height, elements):
    return PageResult(page_number=page_number,width=width,height=height,elements=elements) if PageResult else SimpleNamespace(page_number=page_number,width=width,height=height,elements=elements)


def make_document(*, document_id, pages):
    diagnostics = DocumentDiagnostics(processing_ms=0,timings_ms={},missing_geometry_count=0,ocr_page_count=0,fallback_page_count=0,cache_enabled=False) if DocumentDiagnostics else SimpleNamespace()
    return DocumentResult(document_id=document_id,source_type="pdf",mode="native",pages=pages,diagnostics=diagnostics) if DocumentResult else SimpleNamespace(document_id=document_id,pages=pages)


def test_boq_csv_preserves_missing_values_and_neutralizes_formula_text():
    document = BOQDocument(extractor_family="test", detected=True, rows=[BOQRow(
        designation=ParsedValue(raw_value="=HYPERLINK(\"https://example.invalid\")",
                                normalized_value="=HYPERLINK(\"https://example.invalid\")",
                                parse_status="PARSED", value_origin="OBSERVED"),
        quantity=ParsedValue(normalized_value=None),
        unit_price_ht=ParsedValue(normalized_value=Decimal("-12.50")),
    )])
    exported = list(csv.DictReader(StringIO(export_boq_csv([document]))))[0]
    assert exported["designation"].startswith("'=")
    assert exported["quantity"] == ""
    assert exported["unit_price_ht"] == "-12.50"


def page(items, *, shift=0):
    elements = []
    for i, (text, x, y, confidence) in enumerate(items):
        elements.append(make_evidence(id=f"e{i}",text=text,page_number=1,bbox=BoundingBox(x1=x-15+shift,y1=y-8,x2=x+15+shift,y2=y+8),confidence=confidence,source="paddleocr",source_coordinate_space="ocr_inference_pixels"))
    return make_page(page_number=1,width=1000,height=1400,elements=elements)


def test_generic_boq_reconstructs_observed_cells_without_filling_missing_values():
    # Synthetic positioned evidence: a different header and geometry from the Ministry template.
    items = [("Bordereau des prix unitaires", 280, 100, .99),
             ("N°", 100, 220, .99), ("Désignation", 310, 220, .99),
             ("Unité", 470, 220, .99), ("Quantité", 580, 220, .99),
             ("Prix unitaire", 720, 220, .99), ("Montant", 880, 220, .99),
             ("A1", 100, 310, .99), ("Terrassement", 310, 310, .99),
             ("m3", 470, 310, .99), ("2", 580, 310, .99),
             ("100,000", 720, 310, .99), ("200,000", 880, 310, .99),
             ("A2", 100, 400, .99), ("Drainage", 310, 400, .99),
             ("m", 470, 400, .99), ("50,000", 720, 400, .99)]
    source = make_document(document_id="synthetic-generic", pages=[page(items)])
    results = extract_boq_candidates(source)
    assert len(results) == 1
    result = results[0]
    assert result.extractor_family == GENERIC_FAMILY
    assert result.column_mapping["quantity"] == "quantity"
    assert len(result.rows) == 2
    assert result.rows[0].quantity.normalized_value == Decimal("2")
    assert result.rows[0].total_ht.normalized_value == Decimal("200.000")
    assert result.rows[0].quantity.evidence[0].source_page == 1
    assert result.rows[1].quantity.normalized_value is None
    assert result.rows[1].quantity.parse_status == "MISSING"
    assert any(check.status == "NOT_CHECKABLE" for check in result.rows[1].validation)


def test_generic_boq_rejects_heading_without_positioned_column_evidence():
    source = page([("Devis estimatif", 200, 100, .99), ("Le devis sera remis plus tard", 200, 200, .99)])
    assert not extract_generic_boq(source).detected


ANCHORS = [("Annexe 05", 80, 80, .99), ("BORDEREAU DES PRIX", 300, 130, .99),
    ("DEVIS ESTIMATIF", 300, 155, .99), ("Prix HTVA", 700, 250, .99), ("Prix TTC", 880, 250, .99)]


def filled(*, shift=0, french=False, imperfect=False, missing=False, bad_total=False, missing_article=False):
    data = ANCHORS + [("Article", 155, 280, .99), ("Désignation", 347, 280, .99), ("Qté", 530, 280, .99)]
    if imperfect:
        data = [("Prix H7VA" if t == "Prix HTVA" else "Qte" if t == "Qté" else "TotaI" if t == "Total" else t, x,y,c) for t,x,y,c in data]
    rows = [("01", "Entretien voirie", "2", "125,000", "250,100" if bad_total else "250,000", "148,750", "297,500"),
            ("02", "Réfection réseau", "1", "100,000", "100,000", "119,000", "119,000")]
    for ri, row in enumerate(rows):
        y = 500 + ri*100
        data += [(row[0],155,y,.97), (row[1],347,y,.91), (row[2],530,y,.93),
                 (row[3],596,y,.92), (row[4],668,y,.90), (row[5],740,y,.89), (row[6],811,y,.88)]
    if missing_article:
        data = [item for item in data if not (item[0] == "01" and item[2] == 500)]
    if missing:
        data = [item for item in data if not (item[0] == "2" and item[2] == 500)]
    data += [("Total HTVA",200,1000,.99), ("350,000" if not bad_total else "350,100",790,1000,.94),
             ("TVA (19%)",200,1030,.99), ("66,500" if not bad_total else "66,519",790,1030,.94),
             ("Total TTC",200,1060,.99), ("416,500" if not bad_total else "416,619",790,1060,.94)]
    if french:
        data = [(t.replace("125,250", "1 250,500").replace("250,500", "250,500"),x,y,c) for t,x,y,c in data]
    return page(data, shift=shift)


def public_pdf_page(source_page, page_number):
    elements = [make_evidence(id=f"pdf{page_number}w{i}",text=word[4],page_number=page_number,
        bbox=BoundingBox(x1=word[0],y1=word[1],x2=word[2],y2=word[3]),source="native_pdf",
        native_order=(word[5],word[6],i)) for i,word in enumerate(source_page.get_text("words"))]
    return make_page(page_number=page_number,width=int(source_page.rect.width),height=int(source_page.rect.height),elements=elements)


def test_template_detection_requires_independent_anchor_combination():
    assert detect_male_municipal_v1(page(ANCHORS)).matched
    assert not detect_male_municipal_v1(page(ANCHORS[:-1])).matched
    negative = page([(t,x,y,c) for t,x,y,c in ANCHORS if t not in ("Annexe 05", "BORDEREAU DES PRIX", "DEVIS ESTIMATIF")])
    assert not detect_male_municipal_v1(negative).matched
    for text in (("Annexe 04", "Soumission", "Prix TTC"),
                 ("Annexe 03", "Engagement capacité technique"),
                 ("Annexes 06", "Caution provisoire", "Total TTC"),
                 ("Spécifications techniques", "Article", "Prix HTVA")):
        negative_page = page([(item, 100+i*30, 100+i*25, .99) for i,item in enumerate(text)])
        assert not detect_male_municipal_v1(negative_page).matched
    assert not detect_male_municipal_v1(page([("Prix TTC",100,100,.99)])).matched
    assert not detect_male_municipal_v1(page([("Devis estimatif",100,100,.99)])).matched


def test_header_normalization_and_adapter():
    assert normalize_header("Désignation / Qté") == "designation qte"
    assert normalize_header("Prix H7VA; TotaI") == "prix h7va totai"
    assert normalize_male_municipal_header("Prix H7VA; TotaI") == "prix htva total"
    assert adapt_page(page(ANCHORS)).page_number == 1


@pytest.mark.parametrize(("raw", "expected"), [("1 250,500", Decimal("1250.500")), ("1.250,500", Decimal("1250.500")), ("1250,25", Decimal("1250.25")), ("1250", Decimal("1250"))])
def test_french_numeric_decimal_parsing(raw, expected):
    parsed = parse_french_decimal(raw)
    assert parsed.parse_status == "PARSED"
    assert parsed.value_origin == "OBSERVED"
    assert parsed.normalized_value == expected


def test_ambiguous_separator_and_bad_numeric():
    assert parse_french_decimal("1250.500").parse_status == "AMBIGUOUS"
    assert parse_french_decimal("1,25,0").parse_status == "AMBIGUOUS"
    assert parse_french_decimal("1O0").parse_status == "INVALID"


def test_filled_rows_decimal_validation_and_provenance():
    result = extract_male_municipal_v1(filled())
    assert result.detected and len(result.rows) == 5
    assert result.rows[0].article.raw_value == "01"
    assert result.rows[0].quantity.raw_value == "2"
    assert result.rows[0].total_ht.normalized_value == Decimal("250.000")
    assert result.rows[0].total_ht.evidence[0].source_bbox is not None
    assert result.rows[0].quantity.evidence[0].source_bbox == BoundingBox(x1=515,y1=492,x2=545,y2=508)
    assert result.rows[0].unit. parse_status == "MISSING"
    assert result.rows[0].quantity.evidence[0].ocr_confidence == .93


def test_empty_template_recognized_without_inventing_financial_values():
    result = extract_male_municipal_v1(page(ANCHORS))
    assert result.detected and len(result.rows) == 5
    assert [row.article.normalized_value for row in result.rows] == ["01", "02", "03", "04", "05"]
    assert all(row.article.raw_value is None and row.article.value_origin == "TEMPLATE_INFERRED" and not row.article.evidence for row in result.rows)
    assert result.rows[0].quantity.normalized_value is None
    assert result.totals.total_ht.normalized_value is None


def test_missing_cell_is_not_fabricated_and_arithmetic_error_is_detected():
    missing = extract_male_municipal_v1(filled(missing=True))
    assert missing.rows[0].quantity.parse_status == "MISSING"
    assert missing.rows[0].validation_status == "NEEDS_REVIEW"
    wrong = extract_male_municipal_v1(filled(bad_total=True))
    arithmetic = {check.rule: check for check in wrong.rows[0].validation}
    assert arithmetic["quantity_x_unit_price_ht"].status == "INVALID"


def test_missing_article_anchor_keeps_row_geometry_and_requests_review():
    result = extract_male_municipal_v1(filled(missing_article=True))
    assert len(result.rows) == 5
    assert result.rows[0].article.normalized_value is None
    assert result.rows[0].quantity.normalized_value == Decimal("2")
    assert result.rows[0].validation_status == "NEEDS_REVIEW"


def test_populated_rows_report_missing_fields_and_document_slot_duplicate_checks():
    result = extract_male_municipal_v1(filled())
    result.rows[0].designation = result.rows[0].designation.model_copy(update={
        "normalized_value": None, "raw_value": None, "parse_status": "MISSING", "value_origin": "MISSING"})
    validate_row(result.rows[0])
    assert "designation_present" in {check.rule for check in result.rows[0].validation}
    result.rows[1].article = result.rows[0].article.model_copy(deep=True)
    validate_document(result)
    checks = {check.rule: check for check in result.validation}
    assert checks["expected_row_slots"].status == "VALID"
    assert checks["duplicate_item_numbers"].status == "NEEDS_REVIEW"


def test_csv_export_preserves_french_utf8_and_nulls_as_empty_cells():
    result = extract_male_municipal_v1(filled())
    result.rows[0].designation.normalized_value = "Réfection réseau – façade"
    result.rows[0].quantity.normalized_value = None
    text = export_boq_csv([result])
    encoded = text.encode("utf-8")
    decoded = encoded.decode("utf-8")
    rows = list(csv.DictReader(StringIO(decoded)))
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows[0]["designation"] == "Réfection réseau – façade"
    assert rows[0]["quantity"] == ""
    assert rows[0]["page"] == "1"
    assert "0.0" not in rows[0]["quantity"]


def test_ocr_aliases_and_shifted_geometry():
    a = extract_male_municipal_v1(filled(imperfect=True))
    b = extract_male_municipal_v1(filled(shift=9))
    assert a.detected and b.detected
    assert a.rows[0].unit_price_ht.raw_value == "125,000"
    assert b.rows[0].total_ttc.raw_value == "297,500"


def test_reference_pdf_and_generated_clean_pdf_round_trip():
    import fitz
    root = Path(__file__).resolve().parents[2]
    base = root / "datasets/boq/male_municipal_maintenance_v1"
    cases = [(base / "reference/MM_Cahier-des-charges-type-Entretien.pdf", True),
             (base / "synthetic/fixture_a_clean.pdf", False)]
    for path, empty in cases:
        pdf = fitz.open(path)
        source_page = pdf[24] if len(pdf) > 1 else pdf[0]
        page_result = public_pdf_page(source_page,25)
        document = make_document(document_id=path.stem,pages=[page_result])
        result = extract_male_municipal_from_document(document,page_number=25)
        assert result.document_id == path.stem
        assert result.detected and len(result.rows) == 5 and result.table_bbox is not None
        if empty:
            assert all(row.quantity.normalized_value is None for row in result.rows)
            assert result.totals.total_ht.normalized_value is None
            assert len(result.rows[0].ancillary_evidence) == 1
            assert all(value.ocr_confidence is None for value in result.rows[0].ancillary_evidence)
        else:
            assert result.rows[0].quantity.normalized_value == Decimal("2")
            assert result.totals.total_ht.normalized_value == Decimal("350.000")
            assert all(check.status == "VALID" for check in result.validation)
            assert result.rows[0].article.raw_value == "01"
            assert result.rows[0].article.value_origin == "OBSERVED"
            assert result.rows[0].article.evidence[0].element_ids


def test_all_pdf_fixture_variants_extract_the_controlled_rows():
    import fitz
    root = Path(__file__).resolve().parents[2] / "datasets/boq/male_municipal_maintenance_v1/synthetic"
    cases = {"fixture_a_clean.pdf": ("VALID", Decimal("350.000")),
             "fixture_b_french_numbers.pdf": ("VALID", Decimal("350.100")),
             "fixture_d_missing_quantity.pdf": ("NEEDS_REVIEW", Decimal("350.000")),
             "fixture_e_arithmetic_error.pdf": ("INVALID", Decimal("350.100")),
             "fixture_f_shifted_geometry.pdf": ("VALID", Decimal("350.000"))}
    for name, (expected_row_state, expected_total) in cases.items():
        pdf = fitz.open(root/name); source_page = pdf[0]
        result = extract_male_municipal_v1(public_pdf_page(source_page,25))
        assert result.detected and len(result.rows) == 5
        assert result.totals.total_ht.normalized_value == expected_total
        assert result.rows[0].validation_status == expected_row_state


def test_actual_non_boq_pages_from_reference_cahier_are_rejected():
    import fitz
    root = Path(__file__).resolve().parents[2] / "datasets/boq/male_municipal_maintenance_v1/reference/MM_Cahier-des-charges-type-Entretien.pdf"
    pdf = fitz.open(root)
    # Annexes 03/04/06 and a technical specification page in this same source document.
    for page_index in (22, 23, 25, 13):
        source_page = pdf[page_index]
        assert not detect_male_municipal_v1(public_pdf_page(source_page,page_index+1)).matched


def test_evaluation_reports_separate_metrics_and_real_not_measurable():
    empty = page(ANCHORS)
    truth = {"source_type": "synthetic", "template_detected": True,
             "rows": [{"article_raw": article} for article in ("01", "02", "03", "04", "05")]}
    report = evaluate([(empty, truth)])
    assert report["synthetic"]["template_detection_rate"] == 1
    assert report["synthetic"]["table_detection_rate"] == 1
    assert report["synthetic"]["header_mapping_rate"] == 1
    assert report["real"]["status"] == "NOT YET MEASURABLE"


def test_malformed_input_fails_explicitly():
    with pytest.raises(TypeError):
        adapt_page(object())


def test_document_contract_requires_one_explicit_page_selection():
    page_result = page(ANCHORS)
    document = make_document(document_id="contract-doc",pages=[page_result])
    result = extract_male_municipal_from_document(document,page_number=1)
    assert result.document_id == "contract-doc"
    with pytest.raises(ValueError, match="found 0"):
        extract_male_municipal_from_document(document,page_number=2)
    duplicate = make_document(document_id="contract-doc",pages=[page_result,page_result])
    with pytest.raises(ValueError, match="found 2"):
        extract_male_municipal_from_document(duplicate,page_number=1)
