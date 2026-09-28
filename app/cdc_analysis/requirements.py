"""Evidence-preserving, topic-gated normalizers for explicit tender wording."""
import re
from collections.abc import Iterable

from .headings import normalize
from .schema import Article, Annex, Requirement, Section


def _evidence_for(article: Article, pattern: re.Pattern):
    matches = [e for e in article.source_evidence
               if pattern.search(" ".join(e.source_text_parts) or e.raw_text)]
    return matches or article.source_evidence


def _requirements(article: Article, section_id: str, annex_id: str | None = None) -> list[Requirement]:
    context = normalize((article.title or "") + "\n" + article.text)
    original = (article.title or "") + "\n" + article.text
    found: list[tuple[str, re.Match | None, object, str | None, re.Pattern]] = []

    def add(category: str, pattern: str, value=None, unit=None, evidence_pattern=None):
        compiled = re.compile(pattern, re.I)
        match = compiled.search(context)
        if match:
            found.append((category, match, value(match) if callable(value) else value, unit,
                          re.compile(evidence_pattern or pattern, re.I)))

    if re.search(r"validite.{0,80}offre|offre.{0,80}validite", context):
        add("offer_validity", r"\b(\d{1,3})\s*(jours?|days?)\b",
            lambda m: {"value": int(m.group(1)), "unit": "days", "context": "offer_validity"},
            evidence_pattern=r"validite|lie.*offre")
    if re.search(r"caution provisoire|garantie provisoire", context):
        found.append(("provisional_guarantee", None, None, None,
                      re.compile(r"caution provisoire|garantie provisoire", re.I)))
    if re.search(r"cautionnement definitif|caution definitive|garantie definitive", context):
        add("final_guarantee", r"(?:cautionnement|caution|garantie)\s+definit\w*.{0,180}?\b(\d+(?:[,.]\d+)?)\s*%",
            lambda m: {"value": float(m.group(1).replace(",", ".")), "unit": "percent",
                       "basis": "market_amount", "context": "final_guarantee"},
            unit="percent", evidence_pattern=r"cautionnement|caution definitive|garantie definitive")
        if not any(category == "final_guarantee" for category, *_ in found):
            found.append(("final_guarantee", None, None, None,
                          re.compile(r"cautionnement definitif|caution definitive|garantie definitive", re.I)))
    if re.search(r"modalites de paiement|paiement des sommes", context):
        for percentage in re.finditer(r"\b(\d{1,3})\s*%", context):
            line_start = context.rfind("\n", 0, percentage.start()) + 1
            line_end = context.find("\n", percentage.end())
            if line_end < 0:
                line_end = len(context)
            near = context[max(line_start, percentage.start()-60):min(line_end, percentage.end()+60)]
            is_retention = bool(re.search(r"retenue de garantie", near))
            raw_pattern = re.compile(r"\b" + re.escape(percentage.group(1)) + r"\s*%", re.I)
            category = "retention_guarantee" if is_retention else "payment_term"
            found.append((category, percentage,
                          {"value": int(percentage.group(1)), "unit": "percent",
                           "basis": "payment_amount", "context": category}, "percent", raw_pattern))
        if re.search(r"45\s*jours", context):
            found.append(("payment_term", re.search(r"45\s*jours", context),
                          {"value": 45, "unit": "days", "context": "payment_deadline"}, "days",
                          re.compile(r"45\s*jours", re.I)))
    if re.search(r"delai d.execution|delai d execution|travaux.*termin", context):
        found.append(("execution_deadline", None, None, None,
                      re.compile(r"delai d.execution|travaux.*termin", re.I)))
    if re.search(r"penalite.{0,80}journaliere|penalites de retard", context):
        ratio = re.search(r"\b(\d+)\s*/\s*(\d+)\b", context)
        cap = re.search(r"plafonne\w*.{0,80}?\b(\d+(?:[,.]\d+)?)\s*%", context)
        if ratio:
            found.append(("delay_penalty", ratio,
                          {"numerator": int(ratio.group(1)), "denominator": int(ratio.group(2)),
                           "unit": "per_day", "basis": "contract_amount"}, "ratio",
                          re.compile(re.escape(ratio.group(0)), re.I)))
        if cap:
            found.append(("delay_penalty_cap", cap,
                          {"value": float(cap.group(1).replace(",", ".")), "unit": "percent",
                           "basis": "contract_amount", "context": "delay_penalty_cap"}, "percent",
                          re.compile(re.escape(cap.group(0)), re.I)))
    if re.search(r"delai de garantie", context):
        year = re.search(r"\b(?:un|une)\s*\(?(?:0?1)\)?\s*an\b|\b1\s*an\b|\bone year\b", context)
        val = {"value": 1, "unit": "year", "context": "guarantee_period"} if year else None
        found.append(("guarantee_period", year, val, "year" if val else None,
                      re.compile(r"delai de garantie|1\s*an|un\s*\(01\)\s*an", re.I)))
    if re.search(r"variation du volume|augmenter ou diminuer", context):
        percentage = re.search(r"maximum.{0,60}?\b(\d+(?:[,.]\d+)?)\s*%", context)
        val = ({"value": float(percentage.group(1).replace(",", ".")), "unit": "percent",
                "basis": "order_volume", "context": "order_volume_variation"} if percentage else None)
        found.append(("order_volume_variation", percentage, val, "percent" if val else None,
                      re.compile(r"augmenter ou diminuer|maximum.{0,60}?\d+\s*%", re.I)))
    if re.search(r"prix.*hors taxes|tva|taxes comprises", context):
        found.append(("vat_pricing_condition", None, None, None,
                      re.compile(r"hors taxes|TVA|taxes comprises", re.I)))
    if re.search(r"methodologie de depouillement|criteres.*(?:offres|evaluation)", context):
        found.append(("evaluation_methodology", None, None, None,
                      re.compile(r"methodologie de depouillement|criteres", re.I)))
    if re.search(r"presentation des offres", context):
        found.append(("submission_documents", None, None, None,
                      re.compile(r"pieces administratives|offre financiere|annexe", re.I)))

    output = []
    seen = set()
    for category, match, normalized_value, unit, raw_pattern in found:
        evidence = _evidence_for(article, raw_pattern)
        # Prefer the actual numeric phrase when it is present in an article row;
        # keep matching context rows too so a number is never detached from meaning.
        if isinstance(normalized_value, dict):
            numeric = normalized_value.get("value")
            if numeric is None:
                numeric = normalized_value.get("numerator")
            if numeric is not None:
                numeric_pattern = re.compile(r"(?<!\d)" + re.escape(str(numeric)) + r"(?!\d)")
                numeric_evidence = [e for e in article.source_evidence if numeric_pattern.search(
                    " ".join(e.source_text_parts) or e.raw_text)]
                if numeric_evidence:
                    evidence = list({(e.page, e.element_id): e for e in numeric_evidence + evidence}.values())
        if not evidence:
            continue
        key = (category, tuple(e.element_id for e in evidence))
        if key in seen:
            continue
        seen.add(key)
        # Preserve the full original article wording; normalized fields remain contextual.
        output.append(Requirement(id=f"requirement-{category}-{article.id}-{len(output)+1}",
            type=category, text=article.title + "\n" + article.text if article.title else article.text,
            normalized_value=normalized_value, unit=unit,
            source_page=evidence[0].page, source_bbox=evidence[0].bbox,
            source_section=section_id, source_article=article.id, source_annex=annex_id,
            source_evidence=evidence, evidence_status="probable" if normalized_value is None else "detected",
            extraction_status="candidate_only" if normalized_value is None else "extracted_value",
            reviewed_business_interpretation=None,
            review_status="needs_review"))
    return output


def enrich_requirements(sections: Iterable[Section], annexes: Iterable[Annex]) -> list[Requirement]:
    result = []
    def visit(items: Iterable[Section], parent_id: str | None = None):
        for section in items:
            for article in section.articles:
                result.extend(_requirements(article, section.id))
            visit(section.subsections, section.id)
    visit(sections)
    for annex in annexes:
        for article in annex.articles:
            result.extend(_requirements(article, annex.source_section or "", annex.id))
        visit(annex.subsections, annex.source_section)
    return result
