"""Pure, deterministic projection from the CDC TenderDocument contract."""
from __future__ import annotations

from collections import Counter
import json
from collections.abc import Mapping
from typing import Any

from app.cdc_analysis.schema import Evidence, Requirement, TenderDocument

from .models import (
    BOQSummary, CountFact, EvidenceReference, FactState, KeyFact,
    RequirementCounts, SourceCoverage, SummaryDiagnostic, TenderSummary,
)

IDENTITY_FIELDS = {
    "title": ("title", "tender_title", "project_title"),
    "reference": ("reference", "tender_reference", "consultation_reference"),
    "contracting_organization": ("contracting_organization", "organization", "buyer"),
    "procurement_type": ("procurement_type", "tender_type", "procurement_method"),
    "language": ("language", "document_language"),
    "document_identity": ("document_identity", "dossier_id", "document_id"),
}
DATE_FIELDS = {
    "publication": ("publication_date", "publication"),
    "submission_deadline": ("submission_deadline", "deadline"),
    "clarification_deadline": ("clarification_deadline",),
}
REQUIREMENT_FIELDS = {
    "execution_duration": {"execution_duration", "execution_deadline"},
    "offer_validity": {"offer_validity"},
    "provisional_guarantee": {"provisional_guarantee"},
    "final_performance_guarantee": {"final_guarantee", "performance_guarantee"},
    "retention": {"retention_guarantee", "retention"},
    "penalties": {"delay_penalty", "delay_penalty_cap", "penalty", "penalties"},
    "payment_terms": {"payment_term", "payment_terms"},
}


def _evidence_ref(item: Any) -> EvidenceReference:
    evidence = item if isinstance(item, Evidence) else Evidence.model_validate(item)
    return EvidenceReference(
        document_id=evidence.document_id, page=evidence.page, element_id=evidence.element_id,
        element_ids=list(evidence.source_element_ids) or [evidence.element_id],
        raw_text=evidence.raw_text, source_text_parts=list(evidence.source_text_parts),
        bbox=evidence.bbox, coordinate_space=evidence.coordinate_space,
    )


def _metadata_fact(metadata: Mapping[str, Any], aliases: tuple[str, ...]) -> KeyFact:
    for name in aliases:
        if name not in metadata:
            continue
        raw = metadata[name]
        value = raw.get("value") if isinstance(raw, Mapping) and "value" in raw else raw
        explicit_state = raw.get("state") if isinstance(raw, Mapping) else None
        try:
            state = FactState(explicit_state) if explicit_state else None
        except ValueError:
            state = None
        if state in (FactState.MISSING, FactState.NOT_APPLICABLE):
            return KeyFact(state=state, reason=raw.get("reason") if isinstance(raw, Mapping) else None)
        if value is None or value == "":
            return KeyFact(state=FactState.MISSING, reason="Structured metadata field has no value.")
        refs = [_evidence_ref(e) for e in raw.get("evidence", [])] if isinstance(raw, Mapping) else []
        return KeyFact(
            state=state or FactState.PRESENT, value=value,
            raw_text=raw.get("raw_text") if isinstance(raw, Mapping) else None,
            evidence=refs,
            reason=(raw.get("reason") if isinstance(raw, Mapping) else None)
                   or (None if refs else "Structured metadata has no source evidence reference."),
        )
    return KeyFact(state=FactState.MISSING, reason="No structured value was supplied.")


def _requirement_fact(items: list[Requirement]) -> KeyFact:
    if not items:
        return KeyFact(state=FactState.MISSING, reason="No matching structured requirement was found.")
    values = {json.dumps(item.normalized_value, sort_keys=True, default=str) for item in items}
    refs = [_evidence_ref(ev) for item in items for ev in item.source_evidence]
    refs = sorted({(ref.document_id, ref.page, ref.element_id): ref for ref in refs}.values(),
                  key=lambda ref: (ref.page, ref.element_id))
    ids = [item.id for item in items]
    raw = "\n".join(dict.fromkeys(item.text for item in items)) or None
    categories = {item.type for item in items}
    if len(categories) > 1:
        # Separate penalty components (for example daily rate and cap) are
        # complementary facts, not competing interpretations of one value.
        component_values = [{"type": item.type, "value": item.normalized_value}
                           for item in items]
        state = (FactState.NEEDS_REVIEW
                 if any(item.normalized_value is None or item.review_status == "needs_review"
                        or item.extraction_status != "extracted_value" for item in items)
                 else FactState.PRESENT)
        return KeyFact(state=state, value=component_values, evidence=refs,
                       candidate_ids=ids, raw_text=raw,
                       reason="One or more penalty components require review."
                       if state == FactState.NEEDS_REVIEW else None)
    if len(values) > 1:
        return KeyFact(state=FactState.AMBIGUOUS, evidence=refs, candidate_ids=ids, raw_text=raw,
                       reason="Multiple distinct candidate values were extracted.")
    item = items[0]
    if item.evidence_status == "ambiguous":
        state = FactState.AMBIGUOUS
    elif (item.normalized_value is None or item.extraction_status != "extracted_value"
          or item.review_status == "needs_review"):
        state = FactState.NEEDS_REVIEW
    else:
        state = FactState.PRESENT
    return KeyFact(state=state, value=item.normalized_value, raw_text=raw, evidence=refs,
                   candidate_ids=ids,
                   reason="Candidate has not been reviewed." if state == FactState.NEEDS_REVIEW else None)


def _collect_node_evidence(node: Any, output: list[Evidence]) -> None:
    output.extend(getattr(node, "source_evidence", []))
    for child_name in ("subsections", "articles", "clauses", "paragraphs"):
        for child in getattr(node, child_name, []):
            _collect_node_evidence(child, output)


def _all_evidence(document: TenderDocument) -> list[Evidence]:
    evidence = [*document.title_evidence, *document.furniture_evidence, *document.toc_evidence]
    for node in [*document.sections, *document.articles, *document.annexes, *document.paragraphs,
                 *document.requirements, *document.tables, *document.detected_special_documents,
                 *document.diagnostics]:
        _collect_node_evidence(node, evidence)
    return evidence


def _count_articles(document: TenderDocument) -> int:
    count = len(document.articles)

    def visit(section):
        nonlocal count
        count += len(section.articles)
        for child in section.subsections:
            visit(child)

    for section in document.sections:
        visit(section)
    for annex in document.annexes:
        count += len(annex.articles)
        for child in annex.subsections:
            visit(child)
    return count


def _count_sections(document: TenderDocument) -> int:
    def count(items):
        return sum(1 + count(item.subsections) for item in items)
    return count(document.sections) + sum(count(a.subsections) for a in document.annexes)


def _total_pages(metadata: Mapping[str, Any]) -> int | None:
    for key in ("total_pages", "page_count", "pages_count"):
        value = metadata.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    geometry = metadata.get("producer_page_geometry")
    if isinstance(geometry, Mapping):
        page_numbers = [int(k) for k in geometry if str(k).isdigit()]
        return len(page_numbers) if page_numbers else None
    return None


def build_tender_summary(tender_document: TenderDocument | Mapping[str, Any]) -> TenderSummary:
    """Build a stable summary from CDC structure, metadata and requirements.

    No document text is interpreted here. Absent values stay null; uncertain
    extracted candidates retain their states, IDs and source references.
    """
    document = (tender_document if isinstance(tender_document, TenderDocument)
                else TenderDocument.model_validate(tender_document))
    metadata = document.metadata
    requirements = list(document.requirements)
    identity = {name: _metadata_fact(metadata, aliases) for name, aliases in IDENTITY_FIELDS.items()}
    identity["title"] = (
        KeyFact(state=FactState.PRESENT, value=document.title,
                evidence=[_evidence_ref(e) for e in document.title_evidence])
        if document.title else identity["title"]
    )
    if identity["document_identity"].state == FactState.MISSING:
        identity["document_identity"] = KeyFact(
            state=FactState.PRESENT, value=document.document_id,
            reason="CDC document identity; no page-level source location applies.")

    dates = {name: _metadata_fact(metadata, aliases) for name, aliases in DATE_FIELDS.items()}
    financial = {}
    for name, categories in REQUIREMENT_FIELDS.items():
        fact = _requirement_fact([item for item in requirements if item.type.casefold() in categories])
        if name in {"execution_duration", "offer_validity"}:
            dates[name] = fact
        else:
            financial[name] = fact

    boq_docs = [item for item in document.detected_special_documents if item.document_type.casefold() == "boq"]
    boq_annexes = [item for item in document.annexes if item.annex_type.casefold() in {"boq", "price_schedule"}]
    boq_pages = sorted({page for item in boq_docs for page in range(item.page_start, item.page_end + 1)} |
                       {page for item in boq_annexes for page in range(item.page_start, item.page_end + 1)})
    boq_found = bool(boq_docs or boq_annexes)
    boq_refs = [_evidence_ref(e) for item in boq_docs for e in item.source_evidence]
    if not boq_refs:
        boq_refs = [_evidence_ref(e) for item in boq_annexes for e in item.source_evidence]
    boq = BOQSummary(
        detected=KeyFact(state=FactState.PRESENT if boq_found else FactState.MISSING,
                         value=True if boq_found else None, evidence=boq_refs,
                         reason=None if boq_found else "No BOQ annex/document was detected."),
        pages=boq_pages if boq_found else None,
    )

    category_counts = dict(sorted(Counter(item.type for item in requirements).items()))
    requirement_counts = RequirementCounts(
        by_category=category_counts,
        review_required=sum(item.review_status == "needs_review" for item in requirements),
    )
    structure = {
        "section_count": CountFact(state=FactState.PRESENT, value=_count_sections(document)),
        "article_count": CountFact(state=FactState.PRESENT, value=_count_articles(document)),
        "annex_count": CountFact(state=FactState.PRESENT, value=len(document.annexes)),
    }

    refs = {(ev.document_id, ev.page, ev.element_id): ev for ev in _all_evidence(document)}
    pages = sorted({ev.page for ev in refs.values()})
    total_pages = _total_pages(metadata)
    coverage = SourceCoverage(
        evidence_reference_count=len(refs), pages_with_evidence=pages,
        total_pages=total_pages, coverage_ratio=len(pages) / total_pages if total_pages else None,
    )

    fields = {"identity": identity, "dates": dates, "financial": financial}
    missing = sorted(f"{group}.{key}" for group, values in fields.items()
                     for key, fact in values.items() if fact.state == FactState.MISSING)
    ambiguous = sorted(f"{group}.{key}" for group, values in fields.items()
                       for key, fact in values.items() if fact.state == FactState.AMBIGUOUS)
    if boq.detected.state == FactState.MISSING:
        missing.append("boq.detected")
    uncertain = sorted(f"{group}.{key}" for group, values in fields.items()
                       for key, fact in values.items()
                       if fact.state in {FactState.AMBIGUOUS, FactState.NEEDS_REVIEW})
    review_items = [
        SummaryDiagnostic(code=f"requirement_{item.review_status}",
                          message=f"Requirement {item.id} requires review.",
                          evidence=[_evidence_ref(ev) for ev in item.source_evidence])
        for item in requirements if item.review_status == "needs_review"
    ]
    review_items.extend(
        SummaryDiagnostic(code=item.code, message=item.message,
                          evidence=[_evidence_ref(ev) for ev in item.source_evidence])
        for item in document.diagnostics
    )
    review_items.sort(key=lambda item: (item.code, item.message))
    return TenderSummary(
        document_id=document.document_id, identity=identity, dates=dates, financial=financial,
        structure=structure, boq=boq, requirements=requirement_counts,
        missing_or_ambiguous=sorted(missing + ambiguous), source_coverage=coverage,
        uncertain_fields=uncertain, review_items=review_items,
    )
