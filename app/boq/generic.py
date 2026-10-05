"""Conservative layout baseline for BOQ tables outside the supported template."""
from __future__ import annotations

import re
from collections import defaultdict

from .adapter import adapt_page, element_value
from .extractor import _bbox, _evidence, _text_value
from .models import BOQDocument, BOQRow, BoundingBox
from .normalize import normalize_header
from .validate import validate_document

FAMILY = "GENERIC_LAYOUT_BOQ_V1"
HEADINGS = ("bordereau des prix", "bordereau de prix", "prix unitaires", "devis estimatif",
            "detail quantitatif", "dqe", "bpu")
HEADERS = {
    "article": ("numero", "n", "article", "reference", "ref"),
    "designation": ("designation", "description", "libelle", "nature des travaux"),
    "unit": ("unite", "u"),
    "quantity": ("quantite", "qte"),
    "unit_price_ht": ("prix unitaire ht", "prix unitaire", "pu ht", "p u ht", "p u", "pu"),
    "total_ht": ("prix total ht", "montant ht", "total ht", "prix total", "montant"),
}
NUMERIC = {"quantity", "unit_price_ht", "total_ht"}


def _lines(page):
    """Group positioned evidence by its vertical centre; ignore text without geometry."""
    lines: list[list] = []
    tolerance = max(4, page.height * .006)
    elements = []
    for element in page.elements:
        box = _bbox(element)
        if box and str(element_value(element, "text", "")).strip():
            elements.append((element, (box.y1 + box.y2) / 2, box.x1))
    for element, y, _ in sorted(elements, key=lambda item: (item[1], item[2])):
        if lines and abs(_line_y(lines[-1]) - y) <= tolerance:
            lines[-1].append(element)
        else:
            lines.append([element])
    return [sorted(line, key=lambda item: _bbox(item).x1) for line in lines]


def _line_y(line):
    return sum((_bbox(item).y1 + _bbox(item).y2) / 2 for item in line) / len(line)


def _header_columns(line):
    """Find semantic phrases on a header line and keep their observed x positions."""
    words = []
    for element in line:
        box = _bbox(element)
        words.extend((word, (box.x1 + box.x2) / 2, element)
                     for word in normalize_header(str(element_value(element, "text", ""))).split())
    found = {}
    for field, aliases in HEADERS.items():
        matches = []
        for alias in aliases:
            tokens = alias.split()
            for index in range(len(words) - len(tokens) + 1):
                if [item[0] for item in words[index:index + len(tokens)]] == tokens:
                    matches.append((len(tokens), sum(item[1] for item in words[index:index + len(tokens)]) / len(tokens)))
        if matches:
            found[field] = max(matches, key=lambda item: item[0])[1]
    return found


def _heading_present(page):
    text = normalize_header(" ".join(str(element_value(item, "text", "")) for item in page.elements))
    return any(re.search(rf"\b{re.escape(heading)}\b", text) for heading in HEADINGS)


def detect_generic_boq(page):
    """Return observed header line and columns only when heading and table clues agree."""
    page = adapt_page(page)
    if not _heading_present(page):
        return None
    candidates = []
    lines = _lines(page)
    for index, line in enumerate(lines):
        for span in (1, 2):
            if span == 2 and (index + 1 >= len(lines) or _line_y(lines[index + 1]) - _line_y(line) > 40):
                continue
            header_lines = lines[index:index + span]
            elements = sorted((element for part in header_lines for element in part),
                              key=lambda element: (_bbox(element).x1, (_bbox(element).y1 + _bbox(element).y2) / 2))
            columns = _header_columns(elements)
            if "designation" in columns and len(columns) >= 3 and any(field in columns for field in NUMERIC):
                header_text = normalize_header(" ".join(str(element_value(item, "text", "")) for item in elements))
                candidates.append((len(columns), -span, _line_y(header_lines[-1]), columns, header_text))
    if not candidates:
        return None
    _, _, header_y, columns, header_text = max(candidates, key=lambda item: (item[0], -item[2], item[1]))
    price_basis = ("ht" if re.search(r"\b(ht|htva|hors taxes?)\b", header_text) else
                   "ttc" if re.search(r"\bttc\b", header_text) else "unknown")
    ordered = sorted(columns.items(), key=lambda item: item[1])
    if len({round(x, 1) for _, x in ordered}) != len(ordered):
        return None
    return header_y, ordered, price_basis


def extract_generic_boq(page, *, document_id: str | None = None) -> BOQDocument:
    page = adapt_page(page)
    detected = detect_generic_boq(page)
    result = BOQDocument(document_id=document_id, extractor_family=FAMILY,
                         detected=detected is not None,
                         diagnostics=[] if detected else ["generic_header_not_detected"])
    if detected is None:
        return result
    header_y, ordered, price_basis = detected
    price_field = {"unit_price_ht": "unit_price_ttc", "total_ht": "total_ttc"} if price_basis == "ttc" else {}
    result.column_mapping = {price_field.get(field, field): price_field.get(field, field) for field, _ in ordered}
    result.detection = {"method": "heading_and_positioned_header", "header_page": page.page_number,
                        "column_centres": {field: round(x, 2) for field, x in ordered},
                        "price_basis": price_basis}
    mids = [(ordered[index][1] + ordered[index + 1][1]) / 2 for index in range(len(ordered) - 1)]
    previous_y = None
    for line in _lines(page):
        y = _line_y(line)
        if y <= header_y + max(5, page.height * .007):
            continue
        text = normalize_header(" ".join(str(element_value(item, "text", "")) for item in line))
        if text.startswith(("total", "sous total", "tva", "montant total")):
            continue
        repeated = _header_columns(line)
        if "designation" in repeated and len(repeated) >= 3:
            continue
        cells = defaultdict(list)
        for element in line:
            box = _bbox(element)
            centre = (box.x1 + box.x2) / 2
            index = next((index for index, boundary in enumerate(mids) if centre < boundary), len(mids))
            cells[ordered[index][0]].append(element)
        if set(cells) == {"designation"} and result.rows and previous_y is not None and (
                y - previous_y <= max(35, page.height * .03)):
            continuation = _text_value(page, cells["designation"])
            previous = result.rows[-1].designation
            previous.raw_value = " ".join(filter(None, (previous.raw_value, continuation.raw_value)))
            previous.normalized_value = previous.raw_value
            previous.evidence.extend(continuation.evidence)
            previous_y = y
            continue
        # Require a readable item label and another observed cell. This suppresses
        # narrative lines below a table and avoids manufacturing blank rows.
        if not cells.get("designation") or len([field for field in cells if cells[field]]) < 2:
            continue
        if not (cells.get("article") or any(cells.get(field) for field in NUMERIC)):
            continue
        row = BOQRow(source_page=page.page_number, source_bbox=_evidence(page, line).source_bbox)
        for field in ("article", "designation", "unit", "quantity", "unit_price_ht", "total_ht"):
            if cells.get(field):
                setattr(row, price_field.get(field, field), _text_value(page, cells[field], numeric=field in NUMERIC))
        result.rows.append(row)
        previous_y = y
    if result.rows:
        evidence = [_evidence(page, line) for line in _lines(page) if abs(_line_y(line) - header_y) <= 1]
        result.source_evidence = evidence
        boxes = [row.source_bbox for row in result.rows if row.source_bbox]
        if boxes:
            result.table_bbox = BoundingBox(x1=min(box.x1 for box in boxes), y1=header_y,
                                            x2=max(box.x2 for box in boxes), y2=max(box.y2 for box in boxes))
    else:
        result.diagnostics.append("no_confident_rows_reconstructed")
    return validate_document(result)


def extract_boq_candidates(document, *, pages: set[int] | None = None) -> list[BOQDocument]:
    """Prefer the verified family; try generic layout only for other candidate pages."""
    from .detect import detect_male_municipal_v1
    from .extractor import extract_male_municipal_v1

    results = []
    for page in document.pages:
        if pages is not None and page.page_number not in pages:
            continue
        if detect_male_municipal_v1(page).matched:
            result = extract_male_municipal_v1(page, document_id=document.document_id)
        else:
            result = extract_generic_boq(page, document_id=document.document_id)
        if result.detected and result.rows:
            results.append(result)
    return results
