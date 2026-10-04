"""Interoperable UTF-8 CSV export for specialized BOQ results."""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Iterable

from .models import BOQDocument, BOQRow


CSV_COLUMNS = (
    "item_number", "designation", "unit", "quantity", "unit_price_ht", "total_ht",
    "unit_price_ttc", "total_ttc", "status", "page",
)


def _cell(row: BOQRow, field: str) -> str:
    value = getattr(row, field)
    normalized = value.normalized_value
    if normalized is None:
        return ""
    text = str(normalized)
    # Spreadsheet applications may execute cells beginning with formula markers.
    candidate = text.lstrip("\ufeff \t\r\n")
    try:
        Decimal(candidate)
        is_number = True
    except InvalidOperation:
        is_number = False
    return f"'{text}" if not is_number and candidate.startswith(("=", "+", "-", "@")) else text


def export_boq_csv(documents: Iterable[BOQDocument]) -> str:
    """Return a UTF-8-ready CSV string; absent domain values become empty cells."""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for document in documents:
        for row in document.rows:
            writer.writerow({
                "item_number": _cell(row, "article"),
                "designation": _cell(row, "designation"),
                "unit": _cell(row, "unit"),
                "quantity": _cell(row, "quantity"),
                "unit_price_ht": _cell(row, "unit_price_ht"),
                "total_ht": _cell(row, "total_ht"),
                "unit_price_ttc": _cell(row, "unit_price_ttc"),
                "total_ttc": _cell(row, "total_ttc"),
                "status": row.validation_status,
                "page": "" if row.source_page is None else str(row.source_page),
            })
    return output.getvalue()
