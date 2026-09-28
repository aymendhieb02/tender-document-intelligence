from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from .models import ParsedValue


def normalize_header(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def parse_french_decimal(raw: str | None) -> ParsedValue:
    if raw is None or not raw.strip():
        return ParsedValue(raw_value=raw, parse_status="MISSING", reason="No value present")
    text = raw.strip().replace("DT", "").replace("dt", "").replace("TND", "").strip()
    text = text.replace("\u00a0", " ").replace("\u202f", " ").replace("'", "")
    if not text or all(ch in ".…·_� \t-" for ch in text):
        return ParsedValue(raw_value=raw, parse_status="MISSING", value_origin="OBSERVED", reason="Blank template placeholder")
    if not re.fullmatch(r"[+-]?[\d., ]+", text):
        return ParsedValue(raw_value=raw, parse_status="INVALID", value_origin="OBSERVED", reason="Contains unsupported characters")
    compact = re.sub(r"\s+", "", text)
    if not compact or not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)*", compact):
        return ParsedValue(raw_value=raw, parse_status="INVALID", value_origin="OBSERVED", reason="Malformed numeric notation")
    comma, dot = compact.count(","), compact.count(".")
    if comma and dot:
        dec_sep = "," if compact.rfind(",") > compact.rfind(".") else "."
        grouping = "." if dec_sep == "," else ","
        integer, fractional = compact.rsplit(dec_sep, 1)
        groups = integer.lstrip("+-").split(grouping)
        if any(len(part) != 3 for part in groups[1:]) or not fractional.isdigit():
            return ParsedValue(raw_value=raw, parse_status="AMBIGUOUS", value_origin="OBSERVED", reason="Separators do not form an unambiguous grouped number")
        canonical = integer.replace(grouping, "") + "." + fractional
    elif comma or dot:
        sep = "," if comma else "."
        count = compact.count(sep)
        parts = compact.split(sep)
        # A three-digit suffix can mean either decimal precision or grouping.
        if count == 1 and len(parts[1]) == 3 and sep == ".":
            return ParsedValue(raw_value=raw, parse_status="AMBIGUOUS", value_origin="OBSERVED", reason="Single separator with three following digits may be decimal or thousands grouping")
        if count == 1 and sep == ",":
            canonical = parts[0] + "." + parts[1]
            try:
                return ParsedValue(raw_value=raw, normalized_value=Decimal(canonical), parse_status="PARSED", value_origin="OBSERVED")
            except InvalidOperation:
                return ParsedValue(raw_value=raw, parse_status="INVALID", value_origin="OBSERVED", reason="Not a valid Decimal")
        if count > 1:
            if sep == ",":
                return ParsedValue(raw_value=raw, parse_status="AMBIGUOUS", value_origin="OBSERVED", reason="Repeated comma separators are not valid grouping in French notation")
            if any(len(part) != 3 for part in parts[1:]):
                return ParsedValue(raw_value=raw, parse_status="AMBIGUOUS", value_origin="OBSERVED", reason="Repeated separators are not consistent thousands groups")
            canonical = "".join(parts)
        else:
            canonical = parts[0] + "." + parts[1]
    else:
        canonical = compact
    try:
        value = Decimal(canonical)
    except InvalidOperation:
        return ParsedValue(raw_value=raw, parse_status="INVALID", value_origin="OBSERVED", reason="Not a valid Decimal")
    return ParsedValue(raw_value=raw, normalized_value=value, parse_status="PARSED", value_origin="OBSERVED")
