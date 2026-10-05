"""Exact-decimal pricing drafts layered over immutable extracted BOQ evidence."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field

from .models import BOQDocument, ParsedValue


class PricingRowInput(BaseModel):
    index: int = Field(ge=0)
    unit_price: str | None = Field(default=None, max_length=80)
    unit_price_ht: str | None = Field(default=None, max_length=80)
    unit_price_ttc: str | None = Field(default=None, max_length=80)


class PricingUpdate(BaseModel):
    rows: list[PricingRowInput] = Field(default_factory=list)
    tax_rate: str | None = Field(default=None, max_length=80)


def source_fingerprint(boq: BOQDocument) -> str:
    encoded = json.dumps(boq.model_dump(mode="json"), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal_input(raw: str | None, *, rate: bool = False) -> tuple[Decimal | None, str | None]:
    if raw is None or not raw.strip():
        return None, None
    text = raw.strip().replace("\u00a0", " ").replace("\u202f", " ")
    # The pricing form explicitly treats dot or comma as the decimal separator.
    # Grouping symbols and exponent notation are rejected rather than guessed.
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", text):
        return None, "Saisissez un nombre positif avec un point ou une virgule décimale."
    value = Decimal(text.replace(",", "."))
    if rate and value > 100:
        return None, "Le taux doit être compris entre 0 et 100 %."
    return value, None


def _source_decimal(parsed: ParsedValue) -> Decimal | None:
    if parsed.parse_status != "PARSED" or parsed.normalized_value is None:
        return None
    try:
        return Decimal(str(parsed.normalized_value))
    except Exception:
        return None


def _value(number: Decimal | None, origin: str, *, source_page: int | None = None) -> dict:
    return {"value": format(number, "f") if number is not None else None,
            "origin": origin if number is not None else "missing", "source_page": source_page}


def pricing_profile(boq: BOQDocument) -> dict:
    specialized = boq.extractor_family == "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1"
    basis = "ht" if specialized else boq.detection.get("price_basis", "unknown")
    has_ttc = specialized or basis == "ttc"
    return {"basis": basis, "has_ht": specialized or basis == "ht",
            "has_ttc": has_ttc, "currency": boq.currency,
            "tax_rate_origin": "source" if _source_decimal(boq.totals.vat_rate) is not None else "unknown"}


def build_pricing_draft(boq: BOQDocument, document_id: str, boq_index: int,
                        update: PricingUpdate | None = None, *, updated_at: str | None = None) -> dict:
    """Calculate from current inputs; never edit the source BOQ or infer absent values."""
    update = update or PricingUpdate()
    fingerprint = source_fingerprint(boq)
    draft_id = uuid5(NAMESPACE_URL, f"tender-pricing:{document_id}:{boq_index}:{fingerprint}").hex
    if len(update.rows) != len({row.index for row in update.rows}) or any(
            row.index >= len(boq.rows) for row in update.rows):
        raise ValueError("Pricing rows contain a duplicate or unknown index")
    inputs = {row.index: row for row in update.rows}
    profile = pricing_profile(boq)
    source_rate = _source_decimal(boq.totals.vat_rate)
    entered_rate, rate_error = _decimal_input(update.tax_rate, rate=True)
    issues = []
    if source_rate is not None:
        if update.tax_rate and entered_rate != source_rate:
            issues.append("Le taux du document ne peut pas être remplacé dans ce brouillon.")
        rate = source_rate
        rate_origin = "source"
    else:
        rate = entered_rate
        rate_origin = "user_configured"
        if rate_error:
            issues.append(rate_error)
    price_fields = (["unit_price_ht", "unit_price_ttc"] if profile["has_ht"] and profile["has_ttc"] else
                    ["unit_price_ht"] if profile["has_ht"] else
                    ["unit_price_ttc"] if profile["has_ttc"] else ["unit_price"])
    rows = []
    priced = complete = 0
    for index, source in enumerate(boq.rows):
        entry = inputs.get(index, PricingRowInput(index=index))
        quantity = _source_decimal(source.quantity)
        row_issues = []
        if quantity is None:
            row_issues.append("Quantité source absente ou ambiguë : calcul impossible.")
        elif quantity < 0:
            row_issues.append("Quantité négative à vérifier avant calcul.")
            quantity = None
        parsed = {}
        for field in ("unit_price", "unit_price_ht", "unit_price_ttc"):
            raw = getattr(entry, field)
            value, error = _decimal_input(raw)
            parsed[field] = value
            if error:
                row_issues.append(f"{field}: {error}")
        if any(parsed[field] is not None for field in price_fields):
            priced += 1
        ht = quantity * parsed["unit_price_ht"] if quantity is not None and parsed["unit_price_ht"] is not None and profile["has_ht"] else None
        direct_ttc = quantity * parsed["unit_price_ttc"] if quantity is not None and parsed["unit_price_ttc"] is not None and profile["has_ttc"] else None
        rate_ttc = ht * (Decimal(1) + rate / 100) if ht is not None and rate is not None else None
        ttc = direct_ttc if direct_ttc is not None else rate_ttc
        other_total = quantity * parsed["unit_price"] if quantity is not None and parsed["unit_price"] is not None and profile["basis"] == "unknown" else None
        if direct_ttc is not None and rate_ttc is not None and direct_ttc != rate_ttc:
            row_issues.append("Prix TTC saisi et TTC calculé à partir du taux divergent.")
        for field, computed in (("total_ht", ht), ("total_ttc", ttc)):
            observed = _source_decimal(getattr(source, field))
            if observed is not None and computed is not None and observed != computed:
                row_issues.append(f"{field}: montant source et montant calculé divergent.")
        required = ["unit_price_ht"] if profile["has_ht"] and rate is not None else price_fields
        calculable = (ht is not None if profile["has_ht"] else ttc is not None if profile["has_ttc"] else other_total is not None)
        row_complete = calculable and all(parsed[field] is not None for field in required) and not row_issues
        if row_complete:
            complete += 1
        rows.append({"index": index, "source": {
                         "article": source.article.model_dump(mode="json"),
                         "designation": source.designation.model_dump(mode="json"),
                         "unit": source.unit.model_dump(mode="json"),
                         "quantity": source.quantity.model_dump(mode="json"),
                         "total_ht": source.total_ht.model_dump(mode="json"),
                         "total_ttc": source.total_ttc.model_dump(mode="json"),
                         "page": source.source_page},
                     "input": entry.model_dump(exclude={"index"}),
                     "input_origin": {field: "user" if getattr(entry, field) not in (None, "") else "missing"
                                      for field in ("unit_price", "unit_price_ht", "unit_price_ttc")},
                     "computed": {"line_total": _value(other_total, "computed"),
                                  "line_total_ht": _value(ht, "computed"),
                                  "line_total_ttc": _value(ttc, "computed")},
                     "issues": row_issues,
                     "status": "complete" if row_complete else "needs_review" if row_issues else "in_progress" if any(getattr(entry, field) for field in price_fields) else "not_started"})
    def summed(key: str) -> Decimal | None:
        values = [Decimal(row["computed"][key]["value"]) for row in rows if row["computed"][key]["value"] is not None]
        return sum(values, Decimal(0)) if rows and len(values) == len(rows) else None
    total_ht = summed("line_total_ht") if profile["has_ht"] else None
    total_ttc = summed("line_total_ttc") if profile["has_ttc"] or rate is not None else None
    total_unspecified = summed("line_total") if profile["basis"] == "unknown" else None
    tax_amount = total_ht * rate / 100 if total_ht is not None and rate is not None else None
    if total_ht is not None and total_ttc is not None and tax_amount is not None and total_ht + tax_amount != total_ttc:
        issues.append("Total TTC saisi et montant calculé avec la TVA divergent.")
    for field, computed in (("total_ht", total_ht), ("total_ttc", total_ttc), ("vat", tax_amount)):
        observed = _source_decimal(getattr(boq.totals, field))
        if observed is not None and computed is not None and observed != computed:
            issues.append(f"{field}: total source et total calculé divergent.")
    started = bool(priced or update.tax_rate or any(any(getattr(row, field) for field in price_fields) for row in update.rows))
    status = ("needs_review" if issues or any(row["issues"] for row in rows if row["status"] != "not_started") else
              "complete" if rows and complete == len(rows) else "in_progress" if started else "not_started")
    return {"schema_version": 1, "draft_id": draft_id, "document_id": document_id,
            "boq_index": boq_index, "source_fingerprint": fingerprint,
            "updated_at": updated_at, "status": status, "priced_rows": priced,
            "complete_rows": complete, "total_rows": len(rows), "profile": profile,
            "tax_rate": {"raw": update.tax_rate, "value": format(rate, "f") if rate is not None else None,
                         "origin": rate_origin if rate is not None else "unknown", "error": rate_error},
            "rows": rows, "totals": {"total": _value(total_unspecified, "computed"),
                                    "total_ht": _value(total_ht, "computed"),
                                    "tax_amount": _value(tax_amount, "computed"),
                                    "total_ttc": _value(total_ttc, "computed")},
            "issues": issues}


def pricing_csv(draft: dict) -> str:
    """Separate pricing export; never substitutes for the extracted-source CSV."""
    columns = ["article", "designation", "unit", "quantity", "quantity_origin", "unit_price",
               "unit_price_ht", "unit_price_ttc", "unit_price_origin", "unit_price_ht_origin",
               "unit_price_ttc_origin", "line_total", "line_total_ht", "line_total_ttc",
               "tax_rate", "tax_rate_origin", "row_status", "source_page"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    def safe(value):
        text = str(value or "")
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) and not re.fullmatch(r"-?\d+(?:\.\d+)?", text) else text
    for row in draft["rows"]:
        source = row["source"]
        writer.writerow({"article": safe(source["article"].get("normalized_value")),
                         "designation": safe(source["designation"].get("normalized_value")),
                         "unit": safe(source["unit"].get("normalized_value")),
                         "quantity": safe(source["quantity"].get("normalized_value")),
                         "quantity_origin": "source" if source["quantity"].get("normalized_value") is not None else "missing",
                         **{field: safe(row["input"].get(field)) for field in ("unit_price", "unit_price_ht", "unit_price_ttc")},
                         **{field + "_origin": row["input_origin"][field] for field in ("unit_price", "unit_price_ht", "unit_price_ttc")},
                         **{field: row["computed"][field]["value"] or "" for field in ("line_total", "line_total_ht", "line_total_ttc")},
                         "tax_rate": draft["tax_rate"]["value"] or "",
                         "tax_rate_origin": draft["tax_rate"]["origin"],
                         "row_status": row["status"], "source_page": source["page"] or ""})
    return output.getvalue()
