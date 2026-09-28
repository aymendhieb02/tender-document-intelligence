from __future__ import annotations

import re
from collections import defaultdict

from .adapter import adapt_page, element_value
from .detect import detect_male_municipal_v1, normalize_male_municipal_header
from .models import BOQDocument, BOQRow, BoundingBox, ParsedValue, SourceEvidence
from .normalize import normalize_header, parse_french_decimal
from .validate import validate_document, validate_row
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.document_intelligence.schemas import DocumentResult

MALE_MUNICIPAL_MAINTENANCE_BOQ_V1 = {
    "family": "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1",
    "version": 1,
    "expected_articles": ["01", "02", "03", "04", "05"],
    # Relative to page width, measured from reference PDF page 25 vector rules.
    "column_bands": {"article": (.119, .193), "designation": (.193, .501), "quantity": (.501, .560),
        "unit_price_ht": (.560, .632), "total_ht": (.632, .703), "unit_price_ttc": (.703, .775), "total_ttc": (.775, .847)},
    "table_bbox_points": (70.82, 213.67, 503.47, 600.17),
    "body_y_fraction": (243.91/841.92, 554.33/841.92),
    "row_bands_points": ((243.91, 303.22), (303.22, 362.26), (362.26, 421.32),
        (421.32, 480.38), (480.38, 554.33)),
    "geometry_status": "measured_from_reference_pdf_page_25",
}

ARTICLE_RE = re.compile(r"^\s*(0[1-5])\s*[.)-]?\s*$")
TOTAL_ALIASES = {
    "total_ht": ("total htva", "total ht va"),
    "vat": ("tva",),
    "total_ttc": ("total ttc",),
}
COLUMN_MAPPING = {"Article": "article", "Désignation": "designation", "Qté": "quantity",
    "Prix HTVA / Unité": "unit_price_ht", "Prix HTVA / Total": "total_ht",
    "Prix TTC / Unité": "unit_price_ttc", "Prix TTC / Total": "total_ttc"}


def _bbox(e):
    box = element_value(e, "bbox")
    return _as_bbox(box)


def _as_bbox(box):
    if box is None:
        return None
    if isinstance(box, dict):
        try: return BoundingBox.model_validate(box)
        except (TypeError, ValueError): return None
    try: return BoundingBox(x1=box.x1, y1=box.y1, x2=box.x2, y2=box.y2)
    except (AttributeError, TypeError, ValueError): return None


def _evidence(page, elems):
    # The public evidence contract keeps page geometry and original-source geometry distinct.
    boxes = [_as_bbox(element_value(e, "source_bbox")) or _bbox(e) for e in elems]
    boxes = [b for b in boxes if b is not None]
    bbox = BoundingBox(x1=min(b.x1 for b in boxes), y1=min(b.y1 for b in boxes),
        x2=max(b.x2 for b in boxes), y2=max(b.y2 for b in boxes)) if boxes else None
    return SourceEvidence(source_page=page.page_number, source_bbox=bbox,
        raw_text=" ".join(str(element_value(e, "text", "")) for e in elems),
        ocr_confidence=min((element_value(e, "confidence") for e in elems if element_value(e, "confidence") is not None), default=None),
        source=next((element_value(e, "source") for e in elems if element_value(e, "source")), None),
        element_ids=[str(element_value(e, "id")) for e in elems if element_value(e, "id") is not None])


def _text_value(page, elems, *, numeric=False):
    text = " ".join(str(element_value(e, "text", "")).strip() for e in elems).strip() or None
    evidence = [_evidence(page, elems)] if elems else []
    if numeric:
        result = parse_french_decimal(text)
    else:
        result = ParsedValue(raw_value=text, normalized_value=text, parse_status="PARSED" if text else "MISSING",
            value_origin="OBSERVED" if text else "MISSING", reason=None if text else "No value present")
    if text and result.parse_status != "MISSING":
        result.value_origin = "OBSERVED"
    result.evidence = evidence
    return result


def _center(e, page):
    box = _bbox(e)
    if box and page.width > 0: return (box.x1 + box.x2) / (2 * page.width)
    return None


def _y(e):
    box = _bbox(e)
    return (box.y1 + box.y2) / 2 if box else None


def _map_column(x: float | None) -> str | None:
    if x is None: return None
    for name, (left, right) in MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["column_bands"].items():
        if left <= x < right: return name
    return None


def extract_male_municipal_v1(page, *, document_id: str | None = None) -> BOQDocument:
    page = adapt_page(page)
    detection = detect_male_municipal_v1(page)
    result = BOQDocument(document_id=document_id or getattr(page, "document_id", None),
        extractor_family=MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["family"], detected=detection.matched,
        source_evidence=[_evidence(page, [e]) for e in page.elements if str(element_value(e, "text", "")).strip()])
    result.detection = detection.model_dump()
    if not detection.matched:
        result.diagnostics.append("template_not_matched")
        return result
    result.column_mapping = dict(COLUMN_MAPPING)
    table_spec = MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["table_bbox_points"]
    if page.width and page.height:
        result.table_bbox = BoundingBox(x1=page.width*table_spec[0]/595.2, y1=page.height*table_spec[1]/841.92,
            x2=page.width*table_spec[2]/595.2, y2=page.height*table_spec[3]/841.92)
    elems = [e for e in page.elements if str(element_value(e, "text", "")).strip()]
    positioned = [(e, _y(e)) for e in elems]
    article_marks = [(e, y, ARTICLE_RE.match(str(element_value(e, "text", "")))) for e, y in positioned]
    body_top = page.height * MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["body_y_fraction"][0]
    body_bottom = page.height * MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["body_y_fraction"][1]
    article_marks = [(e, y, m.group(1)) for e, y, m in article_marks if m and y is not None and body_top <= y <= body_bottom]
    # The five measured row bands keep text in its cell even when OCR misses an article label.
    article_by_band = {}
    for expected in MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["expected_articles"]:
        band_index = int(expected)-1
        y0, y1 = MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["row_bands_points"][band_index]
        top, bottom = page.height*y0/841.92, page.height*y1/841.92
        marks = [(e,y,a) for e,y,a in article_marks if a == expected and top <= y < bottom]
        if len(marks) > 1:
            result.diagnostics.append(f"duplicate_article_anchor:{expected}")
        article_by_band[expected] = (marks[0][0] if marks else None, top, bottom)
    has_numeric_body = any(_map_column(_center(e, page)) in {"quantity", "unit_price_ht", "total_ht", "unit_price_ttc", "total_ttc"}
        and parse_french_decimal(str(element_value(e, "text", ""))).parse_status in {"PARSED", "AMBIGUOUS"}
        and any(top <= (_y(e) or -1) < bottom for _, top, bottom in article_by_band.values())
        for e in elems)
    # Header/footer exclusion and cell rows use the measured horizontal table rules.
    for expected in MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["expected_articles"]:
        article_e, row_top, row_bottom = article_by_band[expected]
        row_elems = [e for e, ey in positioned if ey is not None and row_top <= ey < row_bottom]
        cells: dict[str, list] = defaultdict(list)
        for e in row_elems:
            col = _map_column(_center(e, page))
            if col:
                cells[col].append(e)
        row = BOQRow(source_page=page.page_number)
        row.article = _text_value(page, [article_e]) if article_e else ParsedValue(raw_value=None, parse_status="MISSING", reason="Article anchor not observed")
        # Article column sometimes has a designation cell that wraps across multiple fragments.
        unit_anchors = [e for e in cells["designation"] if "unit" in normalize_male_municipal_header(str(element_value(e, "text", ""))) or "unite" in normalize_male_municipal_header(str(element_value(e, "text", "")))]
        unit_ys = [_y(e) for e in unit_anchors if _y(e) is not None]
        unit_words = [e for e in cells["designation"] if e in unit_anchors or any(abs((_y(e) or 0)-uy) < max(5, page.height*.006) for uy in unit_ys)]
        designation_elems = [e for e in cells["designation"] if e not in unit_words]
        row.designation = _text_value(page, designation_elems)
        if unit_words:
            row.ancillary_evidence.append(_evidence(page, unit_words))
        row.quantity = _text_value(page, cells["quantity"], numeric=True)
        row.unit_price_ht = _text_value(page, cells["unit_price_ht"], numeric=True)
        row.total_ht = _text_value(page, cells["total_ht"], numeric=True)
        row.unit_price_ttc = _text_value(page, cells["unit_price_ttc"], numeric=True)
        row.total_ttc = _text_value(page, cells["total_ttc"], numeric=True)
        row.unit = ParsedValue(raw_value=None, parse_status="MISSING", reason="L’unité field is not mapped to UOM; semantics unverified")
        row.source_bbox = _evidence(page, row_elems).source_bbox
        validate_row(row)
        result.rows.append(row)
    # Blank template structure is known, so article labels can be supplied from the measured template spec only when no row values were observed.
    if not article_marks and not has_numeric_body:
        for row, article in zip(result.rows, MALE_MUNICIPAL_MAINTENANCE_BOQ_V1["expected_articles"]):
            row.article = ParsedValue(raw_value=None, normalized_value=article, parse_status="PARSED",
                value_origin="TEMPLATE_INFERRED", reason="Structural article slot supplied by verified template specification")
        result.diagnostics.append("empty_template_article_labels_inferred_from_format_spec")
    elif not article_marks:
        result.diagnostics.append("row_article_anchors_missing_with_numeric_body")
    line_groups = []
    for e in sorted(elems, key=lambda item: (_y(item) if _y(item) is not None else float("inf"), _center(item, page) or 0)):
        y = _y(e)
        target = next((group for group in reversed(line_groups) if y is not None and group[0][1] is not None and abs(group[0][1]-y) < max(5, page.height*.006)), None)
        if target is None: line_groups.append([(e, y)])
        else: target.append((e, y))
    for total_name, aliases in TOTAL_ALIASES.items():
        alias_norms = [normalize_header(a) for a in aliases]
        matched_group = None
        label_members = []
        for group in line_groups:
            group = sorted(group, key=lambda pair: _center(pair[0], page) or 0)
            combined = normalize_header(" ".join(str(element_value(e, "text", "")) for e, _ in group))
            if any(alias == combined or f" {alias} " in f" {combined} " for alias in alias_norms):
                matched_group = group
                # The labels are left-side group members; blank template value remains placeholder evidence.
                label_members = [e for e, _ in group if (_center(e, page) or 0) < .72]
                break
        value_elems = [e for e, _ in matched_group if (_center(e, page) or 0) >= .72] if matched_group else []
        value = _text_value(page, value_elems, numeric=True)
        if matched_group and not value_elems:
            value = ParsedValue(raw_value=" ".join(str(element_value(e, "text", "")) for e in label_members), parse_status="MISSING", reason="Total amount blank in reference template", evidence=[_evidence(page, label_members)])
        setattr(result.totals, total_name, value)
    # Simple label/value extraction for the metadata supported by the stated format.
    for e in elems:
        text = str(element_value(e, "text", ""))
        norm = normalize_male_municipal_header(text)
        if "lot" in norm and result.lot_number.parse_status == "MISSING":
            result.lot_number = _text_value(page, [e])
        if ("consultation" in norm or "procedure simplifiee" in norm) and result.consultation_reference.parse_status == "MISSING":
            result.consultation_reference = _text_value(page, [e])
        if "travaux de" in norm and result.project_title.parse_status == "MISSING":
            result.project_title = _text_value(page, [e])
    rate_match = next((re.search(r"(\d+(?:[,.]\d+)?)\s*%", str(element_value(e, "text", ""))) for e in elems if re.search(r"\d+(?:[,.]\d+)?\s*%", str(element_value(e, "text", "")))), None)
    if rate_match:
        rate = parse_french_decimal(rate_match.group(1))
        if rate.parse_status == "PARSED":
            result.totals.vat_rate = ParsedValue(raw_value=rate_match.group(0), normalized_value=rate.normalized_value,
                parse_status="PARSED", evidence=[_evidence(page, [next(e for e in elems if rate_match.group(0) in str(element_value(e, "text", "")))])])
    return validate_document(result)


def extract_male_municipal_from_document(document: "DocumentResult", *, page_number: int) -> BOQDocument:
    """Extract one explicitly selected page from the frozen public DI Contract 1.0."""
    matches = [page for page in document.pages if page.page_number == page_number]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one page numbered {page_number}; found {len(matches)}")
    return extract_male_municipal_v1(matches[0], document_id=document.document_id)
