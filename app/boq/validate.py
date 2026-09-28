from __future__ import annotations

from decimal import Decimal

from .models import BOQDocument, BOQRow, ValidationCheck


def _value(row, field):
    parsed = getattr(row, field)
    return parsed.normalized_value if parsed.parse_status == "PARSED" else None


def validate_row(row: BOQRow, tolerance: Decimal = Decimal("0.010")) -> BOQRow:
    checks = []
    has_row_content = any(getattr(row, name).parse_status != "MISSING" for name in
        ("designation", "unit", "quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"))
    # A recognized blank tender template has structural slots but no content to
    # validate. Once a row contains observed content, expose absent core fields.
    if has_row_content:
        # This family does not yet have a validated physical-unit column mapping;
        # its “L’unité … DT” text remains ancillary evidence.
        for field in ("designation", "quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"):
            if getattr(row, field).parse_status == "MISSING":
                checks.append(ValidationCheck(rule=f"{field}_present", status="NEEDS_REVIEW",
                    reason=f"{field.replace('_', ' ').capitalize()} is missing from this populated row"))
    for suffix, price_name, total_name in (("ht", "unit_price_ht", "total_ht"), ("ttc", "unit_price_ttc", "total_ttc")):
        quantity, price, total = _value(row, "quantity"), _value(row, price_name), _value(row, total_name)
        if any(v is None for v in (quantity, price, total)):
            checks.append(ValidationCheck(rule=f"quantity_x_unit_price_{suffix}", status="NOT_CHECKABLE", reason="Quantity, unit price, or line total is missing or unparsed"))
            continue
        expected = quantity * price
        delta = abs(expected-total)
        checks.append(ValidationCheck(rule=f"quantity_x_unit_price_{suffix}", status="VALID" if delta <= tolerance else "INVALID",
            expected=str(expected), observed=str(total), difference=str(delta), reason=None if delta <= tolerance else "Quantity × unit price differs from line total"))
    row.validation = checks
    statuses = {item.status for item in checks}
    parse_states = {getattr(row, name).parse_status for name in ("quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc")}
    row_has_data = any(getattr(row, name).parse_status != "MISSING" for name in
        ("designation", "quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"))
    if row.article.parse_status == "MISSING" and row_has_data:
        checks.append(ValidationCheck(rule="article_anchor_present", status="NEEDS_REVIEW", reason="Row values found without a readable article anchor"))
        statuses.add("NEEDS_REVIEW")
        row.validation = checks
    row.validation_status = ("INVALID" if "INVALID" in statuses or "INVALID" in parse_states else
        "NEEDS_REVIEW" if "NEEDS_REVIEW" in statuses or "AMBIGUOUS" in parse_states else
        "VALID" if statuses == {"VALID"} else "NOT_CHECKABLE")
    return row


def validate_document(document: BOQDocument, tolerance: Decimal = Decimal("0.010")) -> BOQDocument:
    for row in document.rows:
        validate_row(row, tolerance)
    active_rows = [row for row in document.rows if any(getattr(row, field).parse_status != "MISSING"
        for field in ("designation", "quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"))]
    ht = document.totals.total_ht.normalized_value if document.totals.total_ht.parse_status == "PARSED" else None
    ttc = document.totals.total_ttc.normalized_value if document.totals.total_ttc.parse_status == "PARSED" else None
    vat = document.totals.vat.normalized_value if document.totals.vat.parse_status == "PARSED" else None
    rate = document.totals.vat_rate.normalized_value if document.totals.vat_rate.parse_status == "PARSED" else None
    row_ht = [r.total_ht.normalized_value for r in active_rows if r.total_ht.parse_status == "PARSED"]
    row_ttc = [r.total_ttc.normalized_value for r in active_rows if r.total_ttc.parse_status == "PARSED"]
    checks = []
    if document.detected:
        expected_slots = 5 if document.extractor_family == "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1" else None
        if expected_slots is not None:
            checks.append(ValidationCheck(rule="expected_row_slots", status="VALID" if len(document.rows) == expected_slots else "NEEDS_REVIEW",
                expected=str(expected_slots), observed=str(len(document.rows)),
                reason=None if len(document.rows) == expected_slots else "Detected row count differs from the supported template"))
        seen: set[str] = set()
        duplicates: set[str] = set()
        for row in document.rows:
            article = row.article.normalized_value if row.article.parse_status == "PARSED" else None
            if article is not None:
                normalized = str(article).strip()
                if normalized in seen:
                    duplicates.add(normalized)
                seen.add(normalized)
        checks.append(ValidationCheck(rule="duplicate_item_numbers", status="NEEDS_REVIEW" if duplicates else "VALID",
            observed=", ".join(sorted(duplicates)) if duplicates else None,
            reason="Duplicate item numbers: " + ", ".join(sorted(duplicates)) if duplicates else None))
    for rule, values, observed in (("sum_rows_total_ht", row_ht, ht), ("sum_rows_total_ttc", row_ttc, ttc)):
        if observed is None or not values or len(values) != len(active_rows):
            checks.append(ValidationCheck(rule=rule, status="NOT_CHECKABLE", reason="Totals or row values are missing"))
        else:
            expected = sum(values, Decimal(0)); delta = abs(expected-observed)
            checks.append(ValidationCheck(rule=rule, status="VALID" if delta <= tolerance else "INVALID", expected=str(expected), observed=str(observed), difference=str(delta), reason=None if delta <= tolerance else "Sum of row totals differs from document total"))
    if ht is None or ttc is None or vat is None:
        checks.append(ValidationCheck(rule="total_ht_plus_vat_equals_ttc", status="NOT_CHECKABLE", reason="One or more document totals are missing"))
    else:
        delta = abs(ht+vat-ttc)
        checks.append(ValidationCheck(rule="total_ht_plus_vat_equals_ttc", status="VALID" if delta <= tolerance else "INVALID", expected=str(ht+vat), observed=str(ttc), difference=str(delta), reason=None if delta <= tolerance else "HT plus VAT differs from TTC"))
    if ht is None or vat is None or rate is None:
        checks.append(ValidationCheck(rule="vat_rate_x_total_ht_equals_vat", status="NOT_CHECKABLE", reason="HT amount, VAT amount, or VAT rate is missing"))
    else:
        expected_vat = (ht*rate/Decimal(100)).quantize(tolerance)
        delta = abs(expected_vat-vat)
        checks.append(ValidationCheck(rule="vat_rate_x_total_ht_equals_vat", status="VALID" if delta <= tolerance else "INVALID", expected=str(expected_vat), observed=str(vat), difference=str(delta), reason=None if delta <= tolerance else "VAT amount differs from total HT × VAT rate"))
    document.validation = checks
    if any(c.status == "INVALID" for c in checks) or any(r.validation_status == "INVALID" for r in active_rows):
        document.review_status = "NEEDS_REVIEW"
    elif any(r.validation_status == "NEEDS_REVIEW" for r in active_rows) or any(c.status == "NEEDS_REVIEW" for c in checks):
        document.review_status = "NEEDS_REVIEW"
    elif any(r.validation_status == "NOT_CHECKABLE" for r in active_rows) or any(c.status == "NOT_CHECKABLE" for c in checks):
        document.review_status = "NOT_CHECKABLE"
    else:
        document.review_status = "READY"
    return document
