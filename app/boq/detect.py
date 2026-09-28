from __future__ import annotations

from pydantic import BaseModel

from .adapter import adapt_page, element_value
from .normalize import normalize_header

ANCHOR_TERMS = {
    "annexe_05": ("annexe 05", "annexe n 05", "annexe no 05"),
    "bordereau_prix": ("bordereau des prix", "bordereau prix", "borderau des prix"),
    "devis_estimatif": ("devis estimatif",),
    "prix_htva": ("prix htva", "prix ht va", "prix h7va"),
    "prix_ttc": ("prix ttc",),
}
REQUIRED = {"annexe_05", "bordereau_prix", "devis_estimatif", "prix_htva", "prix_ttc"}


class DetectionResult(BaseModel):
    matched: bool
    score: int
    anchors_found: dict[str, bool]
    anchors_missing: list[str]
    evidence: dict[str, list[str]]


def normalize_male_municipal_header(value: str) -> str:
    """Normalize generic header text plus OCR confusions specific to this printed template."""
    normalized = normalize_header(value)
    return normalized.replace("h7va", "htva").replace("totai", "total")


def detect_male_municipal_v1(page) -> DetectionResult:
    page = adapt_page(page)
    raw_texts = [str(element_value(e, "text", "")) for e in page.elements]
    combined = normalize_male_municipal_header(" ".join(raw_texts))
    normalized = [(raw, normalize_male_municipal_header(raw)) for raw in raw_texts]
    found, evidence = {}, {}
    for key, aliases in ANCHOR_TERMS.items():
        aliases_norm = [normalize_male_municipal_header(a) for a in aliases]
        hits = [raw for raw, text in normalized if any(alias in text for alias in aliases_norm)]
        if any(alias in combined for alias in aliases_norm) and not hits:
            hits = [" ".join(raw_texts)]
        found[key], evidence[key] = bool(hits), hits
    return DetectionResult(matched=all(found.get(key, False) for key in REQUIRED), score=sum(found.values()),
        anchors_found=found, anchors_missing=[key for key, value in found.items() if not value], evidence=evidence)
