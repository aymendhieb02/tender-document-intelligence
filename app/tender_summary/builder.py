"""Pure, deterministic projection from the CDC TenderDocument contract."""
from __future__ import annotations

from collections import Counter
import json
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
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


def _apply_financial_facts(
    dates: dict[str, KeyFact],
    financial: dict[str, KeyFact],
    facts: Iterable[Mapping[str, Any]],
) -> None:
    date_targets = {
        "submission_deadline": "submission_deadline",
        "clarification_deadline": "clarification_deadline",
        "offer_validity": "offer_validity",
        "execution_period": "execution_duration",
        "payment_deadline": "payment_deadline",
    }
    financial_targets = {
        "provisional_guarantee": "provisional_guarantee",
        "guarantee_amount": "guarantee_amount",
        "retention": "retention",
        "penalty_rate": "penalties",
        "penalty_cap": "penalties",
        "vat_rate": "vat_rate",
        "payment_schedule": "payment_terms",
        "payment_component": "payment_terms",
        "warranty_period": "warranty_period",
        "money": "amounts",
    }
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for item in facts:
        category = str(item.get("category", ""))
        if category in date_targets:
            target = ("dates", date_targets[category])
        else:
            target = ("financial", financial_targets.get(category, category or "other"))
        grouped.setdefault(target, []).append(item)

    for (group, name), items in grouped.items():
        values = [item.get("normalized") for item in items]
        distinct = {json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values}
        categories = {str(item.get("category", "")) for item in items}
        values_by_category: dict[str, set[str]] = {}
        for item, value in zip(items, values):
            values_by_category.setdefault(str(item.get("category", "")), set()).add(
                json.dumps(value, ensure_ascii=False, sort_keys=True)
            )
        same_category_conflict = any(len(category_values) > 1 for category_values in values_by_category.values())
        has_unresolved = any(
            item.get("normalized") is None or item.get("status") in {"ambiguous", "conflict"}
            for item in items
        )
        if (same_category_conflict
                or any(item.get("status") in {"ambiguous", "conflict"} for item in items)):
            state = FactState.AMBIGUOUS
        elif has_unresolved:
            state = FactState.NEEDS_REVIEW
        else:
            state = FactState.PRESENT
        evidence_items = [
            _evidence_ref(evidence)
            for item in items for evidence in item.get("evidence", [])
        ]
        unique_evidence = {
            (item.document_id, item.page, item.element_id): item for item in evidence_items
        }
        refs = sorted(unique_evidence.values(), key=lambda item: (item.page, item.element_id))
        raw_text = "\n".join(dict.fromkeys(str(item.get("raw", "")) for item in items if item.get("raw"))) or None
        candidate_ids = list(dict.fromkeys(str(item["id"]) for item in items if item.get("id")))
        value: Any
        if len(distinct) == 1 and len(categories) == 1:
            value = values[0]
        else:
            value = [
                {"id": item.get("id"), "raw": item.get("raw"), "normalized": item.get("normalized"),
                 "status": item.get("status")}
                for item in items
            ]
        projected = KeyFact(
            state=state, value=value, raw_text=raw_text, evidence=refs,
            candidate_ids=candidate_ids,
            reason=("Conflicting or ambiguous normalized facts require review."
                    if state == FactState.AMBIGUOUS else
                    "Normalized fact is incomplete and requires review."
                    if state == FactState.NEEDS_REVIEW else None),
        )
        target = dates if group == "dates" else financial
        existing = target.get(name)
        if existing is None or existing.state == FactState.MISSING:
            target[name] = projected
            continue

        existing_locations = {
            (ref.document_id, ref.page, identifier)
            for ref in existing.evidence for identifier in (ref.element_ids or [ref.element_id])
        }
        projected_locations = {
            (ref.document_id, ref.page, identifier)
            for ref in projected.evidence for identifier in (ref.element_ids or [ref.element_id])
        }
        shares_evidence = bool(existing_locations & projected_locations)

        def numeric(value: Any) -> str | None:
            if isinstance(value, bool) or value is None or isinstance(value, (dict, list)):
                return None
            try:
                return format(Decimal(str(value)).normalize(), "f")
            except (InvalidOperation, ValueError):
                return None

        def equivalent(left: Any, right: Any) -> bool:
            if json.dumps(left, ensure_ascii=False, sort_keys=True) == json.dumps(
                right, ensure_ascii=False, sort_keys=True
            ):
                return True
            if shares_evidence:
                if isinstance(left, dict) and not isinstance(right, dict):
                    return "value" in left and numeric(left.get("value")) == numeric(right)
                if isinstance(right, dict) and not isinstance(left, dict):
                    return "value" in right and numeric(right.get("value")) == numeric(left)
            return False

        matches = existing.value is None or equivalent(existing.value, projected.value)
        if existing.state == FactState.NOT_APPLICABLE and projected.value is not None:
            matches = False
        combined_evidence = {
            (ref.document_id, ref.page, ref.element_id): ref
            for ref in [*existing.evidence, *projected.evidence]
        }
        combined_ids = list(dict.fromkeys([*existing.candidate_ids, *projected.candidate_ids]))
        combined_raw = "\n".join(dict.fromkeys(
            value for value in (existing.raw_text, projected.raw_text) if value
        )) or None
        if not matches:
            target[name] = KeyFact(
                state=FactState.AMBIGUOUS,
                value=[
                    {"source": "cdc_candidate", "value": existing.value,
                     "candidate_ids": existing.candidate_ids},
                    {"source": "financial_deadline", "value": projected.value,
                     "candidate_ids": projected.candidate_ids},
                ],
                raw_text=combined_raw,
                evidence=sorted(combined_evidence.values(), key=lambda ref: (ref.page, ref.element_id)),
                candidate_ids=combined_ids,
                reason="CDC candidate and financial/deadline normalization disagree; review both.",
            )
        else:
            conservative_state = (
                FactState.AMBIGUOUS
                if FactState.AMBIGUOUS in {existing.state, projected.state}
                else FactState.NEEDS_REVIEW
                if FactState.NEEDS_REVIEW in {existing.state, projected.state}
                else FactState.PRESENT
            )
            target[name] = KeyFact(
                state=conservative_state, value=projected.value, raw_text=combined_raw,
                evidence=sorted(combined_evidence.values(), key=lambda ref: (ref.page, ref.element_id)),
                candidate_ids=combined_ids,
                reason=("One or more matching source candidates still require review."
                        if conservative_state == FactState.NEEDS_REVIEW else projected.reason),
            )


def build_tender_summary(
    tender_document: TenderDocument | Mapping[str, Any], *,
    classified_requirements: Iterable[Mapping[str, Any]] | None = None,
    financial_deadline_facts: Iterable[Mapping[str, Any]] = (),
) -> TenderSummary:
    """Project CDC structure and explicitly supplied module outputs.

    This function does not parse source text. Absent values stay null;
    uncertain candidates retain their states, IDs and source references.
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

    _apply_financial_facts(dates, financial, financial_deadline_facts)

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

    classification_supplied = classified_requirements is not None
    classified = list(classified_requirements or [])
    category_counts = (
        dict(sorted(Counter(str(item.get("category", "OTHER")) for item in classified).items()))
        if classification_supplied else dict(sorted(Counter(item.type for item in requirements).items()))
    )
    requirement_counts = RequirementCounts(
        by_category=category_counts,
        review_required=(
            sum(str(item.get("review_status", "")).upper() == "NEEDS_REVIEW" for item in classified)
            if classification_supplied else sum(item.review_status == "needs_review" for item in requirements)
        ),
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
    if classified:
        review_items.extend(
            SummaryDiagnostic(
                code="requirement_needs_review",
                message=f"Requirement {item.get('id', 'unknown')} requires human review.",
                evidence=[_evidence_ref(ev) for ev in item.get("evidence", [])],
            )
            for item in classified if str(item.get("review_status", "")).upper() == "NEEDS_REVIEW"
        )
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
