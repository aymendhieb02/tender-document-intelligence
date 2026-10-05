"""Synthetic pricing cases; no claim about completed real-tender accuracy."""
from decimal import Decimal
from copy import deepcopy

from app.boq.models import BOQDocument, BOQRow, ParsedValue
from app.boq.pricing import PricingRowInput, PricingUpdate, build_pricing_draft, pricing_csv


def observed(value):
    return ParsedValue(raw_value=str(value), normalized_value=value, parse_status="PARSED",
                       value_origin="OBSERVED")


def fixture(*, quantity=Decimal("1000"), tax_rate=None, second=False, source_total=None,
            family="MALE_MUNICIPAL_MAINTENANCE_BOQ_V1", price_basis="ht"):
    row = BOQRow(article=observed("01"), designation=observed("Produit A"),
                 quantity=observed(quantity) if quantity is not None else ParsedValue(),
                 total_ht=observed(source_total) if source_total is not None else ParsedValue(),
                 source_page=25)
    result = BOQDocument(extractor_family=family, detected=True, rows=[row],
                         detection={"price_basis": price_basis})
    if second:
        result.rows.append(BOQRow(article=observed("02"), designation=observed("Produit B"),
                                  quantity=observed(Decimal("2")), source_page=25))
    if tax_rate is not None:
        result.totals.vat_rate = observed(Decimal(str(tax_rate)))
    return result


def draft(boq, rows=(), tax_rate=None):
    return build_pricing_draft(boq, "a" * 32, 0, PricingUpdate(rows=list(rows), tax_rate=tax_rate))


def test_exact_ht_price_and_no_invented_tax_or_ttc():
    boq = fixture()
    before = deepcopy(boq.model_dump(mode="json"))
    result = draft(boq, [PricingRowInput(index=0, unit_price_ht="12.500")])
    assert result["rows"][0]["computed"]["line_total_ht"] == {
        "value": "12500.000", "origin": "computed", "source_page": None}
    assert result["totals"]["total_ht"]["value"] == "12500.000"
    assert result["totals"]["tax_amount"]["value"] is None
    assert result["totals"]["total_ttc"]["value"] is None
    assert result["tax_rate"]["origin"] == "unknown"
    assert result["status"] == "in_progress"  # This source also asks for TTC prices.
    assert boq.model_dump(mode="json") == before


def test_decimal_quantity_zero_quantity_and_missing_values():
    decimal = draft(fixture(quantity=Decimal("1.25"), family="GENERIC_LAYOUT_BOQ_V1"),
                    [PricingRowInput(index=0, unit_price_ht="8,400")])
    assert Decimal(decimal["rows"][0]["computed"]["line_total_ht"]["value"]) == Decimal("10.50000")
    assert decimal["status"] == "complete"
    zero = draft(fixture(quantity=Decimal("0"), family="GENERIC_LAYOUT_BOQ_V1"),
                 [PricingRowInput(index=0, unit_price_ht="12.500")])
    assert zero["rows"][0]["computed"]["line_total_ht"]["value"] == "0.000"
    missing_quantity = draft(fixture(quantity=None), [PricingRowInput(index=0, unit_price_ht="12.500")])
    assert missing_quantity["rows"][0]["computed"]["line_total_ht"]["value"] is None
    assert missing_quantity["status"] == "needs_review"
    missing_price = draft(fixture())
    assert missing_price["status"] == "not_started"
    assert missing_price["rows"][0]["computed"]["line_total_ht"]["value"] is None


def test_invalid_and_negative_price_are_preserved_for_review_without_calculation():
    for raw in ("abc", "-12.500", "1 000,000", "=1+1"):
        result = draft(fixture(), [PricingRowInput(index=0, unit_price_ht=raw)])
        assert result["rows"][0]["input"]["unit_price_ht"] == raw
        assert result["rows"][0]["computed"]["line_total_ht"]["value"] is None
        assert result["status"] == "needs_review"


def test_explicit_source_and_user_configured_tax_calculate_without_default_rate():
    source = draft(fixture(tax_rate="19"), [PricingRowInput(index=0, unit_price_ht="12.500")])
    assert source["tax_rate"]["origin"] == "source"
    assert Decimal(source["totals"]["tax_amount"]["value"]) == Decimal("2375.000")
    assert Decimal(source["totals"]["total_ttc"]["value"]) == Decimal("14875.000")
    assert source["status"] == "complete"
    configured = draft(fixture(), [PricingRowInput(index=0, unit_price_ht="12.500")], tax_rate="19")
    assert configured["tax_rate"]["origin"] == "user_configured"
    assert Decimal(configured["totals"]["total_ttc"]["value"]) == Decimal("14875.000")
    bad_rate = draft(fixture(), [PricingRowInput(index=0, unit_price_ht="12.500")], tax_rate="150")
    assert bad_rate["totals"]["tax_amount"]["value"] is None
    assert bad_rate["status"] == "needs_review"


def test_source_mismatch_partial_status_and_csv_formula_protection():
    boq = fixture(source_total=Decimal("13000.000"), second=True)
    boq.rows[0].designation = observed('=HYPERLINK("https://example.invalid")')
    result = draft(boq, [PricingRowInput(index=0, unit_price_ht="12.500", unit_price_ttc="14.875")])
    assert result["priced_rows"] == 1 and result["total_rows"] == 2
    assert result["totals"]["total_ht"]["value"] is None
    assert any("source" in issue for issue in result["rows"][0]["issues"])
    assert result["status"] == "needs_review"
    exported = pricing_csv(result)
    assert "'=HYPERLINK" in exported
    assert "12500.000" in exported
    assert "13000.000" not in exported  # Pricing export keeps computed amount distinct.


def test_unknown_generic_price_basis_never_labels_amount_ht():
    boq = fixture(family="GENERIC_LAYOUT_BOQ_V1", price_basis="unknown")
    result = draft(boq, [PricingRowInput(index=0, unit_price="12.500")])
    assert result["profile"]["basis"] == "unknown"
    assert result["rows"][0]["computed"]["line_total"]["value"] == "12500.000"
    assert result["rows"][0]["computed"]["line_total_ht"]["value"] is None
    assert result["totals"]["total_ttc"]["value"] is None


def test_ttc_generic_draft_uses_ttc_inputs_without_ht_or_tax_inference():
    boq = fixture(family="GENERIC_LAYOUT_BOQ_V1", price_basis="ttc")
    result = draft(boq, [PricingRowInput(index=0, unit_price_ttc="14.875")])
    assert result["profile"]["has_ht"] is False
    assert result["rows"][0]["computed"]["line_total_ht"]["value"] is None
    assert result["rows"][0]["computed"]["line_total_ttc"]["value"] == "14875.000"
    assert result["totals"]["tax_amount"]["value"] is None
