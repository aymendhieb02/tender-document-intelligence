"""Single-pass deterministic composition for Tender Intelligence API V2."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable

from app.cdc_analysis.financial_deadline import Fact, normalize_financial_deadlines
from app.cdc_analysis.schema import Article, Evidence, Paragraph, Requirement, Section, TenderDocument
from app.requirements_intelligence import TenderRequirement, classify_document
from app.tender_dossier import (
    Evidence as DossierEvidence,
    FactObservation,
    GroupingStatus,
    ProcessedTenderDocument,
    build_tender_dossier,
)
from app.tender_summary import build_tender_summary


@dataclass(frozen=True)
class SourcedFinancialFact:
    id: str
    fact: Fact
    evidence: tuple[Evidence, ...]
    evidence_scope: str
    source_requirement_id: str | None = None
    source_article_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            **self.fact.as_dict(),
            "evidence": [item.model_dump(mode="json") for item in self.evidence],
            "evidence_scope": self.evidence_scope,
            "source_requirement_id": self.source_requirement_id,
            "source_article_id": self.source_article_id,
        }


@dataclass(frozen=True)
class _TextSource:
    text: str
    evidence: tuple[Evidence, ...]
    requirement_id: str | None = None
    article_id: str | None = None


def _evidence_key(item: Evidence) -> tuple[Any, ...]:
    return (item.document_id, item.page, item.element_id, item.line_index, item.raw_text)


def _add_text_source(
    output: list[_TextSource], text: str, evidence: Iterable[Evidence], *,
    requirement_id: str | None = None, article_id: str | None = None,
) -> None:
    evidence_items_list: list[Evidence] = []
    seen_evidence: set[tuple[Any, ...]] = set()
    for item in evidence:
        key = _evidence_key(item)
        if key not in seen_evidence:
            seen_evidence.add(key)
            evidence_items_list.append(item)
    evidence_items = tuple(evidence_items_list)
    if text.strip() and evidence_items:
        output.append(_TextSource(text, evidence_items, requirement_id, article_id))


def _article_sources(article: Article, output: list[_TextSource], seen: set[int]) -> None:
    if id(article) in seen:
        return
    seen.add(id(article))
    _add_text_source(output, article.text, article.source_evidence, article_id=article.id)
    for clause in article.clauses:
        _paragraph_source(clause, output, seen, article_id=article.id)


def _paragraph_source(
    paragraph: Paragraph, output: list[_TextSource], seen: set[int], *, article_id: str | None = None,
) -> None:
    if id(paragraph) in seen:
        return
    seen.add(id(paragraph))
    _add_text_source(output, paragraph.text, paragraph.source_evidence, article_id=article_id)


def _section_sources(section: Section, output: list[_TextSource], seen: set[int]) -> None:
    if id(section) in seen:
        return
    seen.add(id(section))
    for article in section.articles:
        _article_sources(article, output, seen)
    for paragraph in section.paragraphs:
        _paragraph_source(paragraph, output, seen)
    for child in section.subsections:
        _section_sources(child, output, seen)


def _financial_text_sources(document: TenderDocument) -> list[_TextSource]:
    sources: list[_TextSource] = []
    seen: set[int] = set()
    for requirement in document.requirements:
        _add_text_source(sources, requirement.text, requirement.source_evidence,
                         requirement_id=requirement.id, article_id=requirement.source_article)
    for article in document.articles:
        _article_sources(article, sources, seen)
    for section in document.sections:
        _section_sources(section, sources, seen)
    for paragraph in document.paragraphs:
        _paragraph_source(paragraph, sources, seen)
    for annex in document.annexes:
        for article in annex.articles:
            _article_sources(article, sources, seen)
        for paragraph in annex.paragraphs:
            _paragraph_source(paragraph, sources, seen)
        for section in annex.subsections:
            _section_sources(section, sources, seen)

    unique: dict[tuple[Any, ...], _TextSource] = {}
    for source in sources:
        key = (source.text, tuple(_evidence_key(item) for item in source.evidence),
               source.requirement_id, source.article_id)
        unique.setdefault(key, source)
    return list(unique.values())


def _matching_evidence(raw: str, source: _TextSource) -> tuple[tuple[Evidence, ...], str]:
    folded_raw = raw.casefold()
    matched = tuple(item for item in source.evidence if folded_raw in item.raw_text.casefold())
    if matched:
        return matched, "matched_source_element"
    # Some structural candidates join adjacent source elements. Keep their
    # bounded source evidence rather than inventing a narrower page location.
    return source.evidence, "candidate_context"


def _stable_fact_id(document_id: str, fact: Fact, evidence: tuple[Evidence, ...]) -> str:
    normalized = json.dumps(fact.as_dict()["normalized"], ensure_ascii=False, sort_keys=True)
    locations = "|".join(
        f"{item.document_id}:{item.page}:{item.element_id}:{item.line_index}:{item.raw_text}"
        for item in evidence
    )
    seed = "|".join((document_id, fact.category, fact.raw, normalized, locations))
    return "fin-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _financial_facts(document: TenderDocument) -> tuple[list[SourcedFinancialFact], list[str]]:
    diagnostics: list[str] = []
    collected: dict[str, SourcedFinancialFact] = {}
    for source in _financial_text_sources(document):
        for fact in normalize_financial_deadlines(source.text):
            evidence, scope = _matching_evidence(fact.raw, source)
            item = SourcedFinancialFact(
                _stable_fact_id(document.document_id, fact, evidence), fact, evidence, scope,
                source.requirement_id, source.article_id,
            )
            collected.setdefault(item.id, item)
            if scope == "candidate_context":
                diagnostics.append("financial_fact_uses_candidate_context_evidence")

    facts = list(collected.values())
    deadlines: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(facts):
        if item.fact.category == "submission_deadline" and item.fact.normalized:
            deadlines[str(item.fact.normalized.get("date"))].append(index)
    if len(deadlines) > 1:
        group_seed = "|".join((document.document_id, *sorted(deadlines)))
        group = "submission-deadline-" + hashlib.sha256(group_seed.encode("utf-8")).hexdigest()[:12]
        for index in (index for group_indices in deadlines.values() for index in group_indices):
            prior = facts[index]
            facts[index] = SourcedFinancialFact(
                prior.id, Fact(prior.fact.category, prior.fact.raw, prior.fact.normalized,
                               "conflict", group), prior.evidence, prior.evidence_scope,
                prior.source_requirement_id, prior.source_article_id,
            )
    return facts, sorted(set(diagnostics))


def _requirements_with_value_refs(
    requirements: list[TenderRequirement], facts: list[SourcedFinancialFact],
) -> list[TenderRequirement]:
    output = []
    for requirement in requirements:
        evidence_ids = set(requirement.evidence_ids)
        related = tuple(
            item.id for item in facts
            if evidence_ids.intersection(
                identifier
                for evidence in item.evidence
                for identifier in (evidence.element_id, *evidence.source_element_ids)
            )
        )
        output.append(requirement.model_copy(update={"related_value_refs": related}))
    return output


def _dossier_payload(
    document: TenderDocument, *, document_result: Any, filename: str,
    requirements: list[TenderRequirement], facts: list[SourcedFinancialFact], summary: Any,
) -> tuple[dict[str, Any], str]:
    financial_payload = [item.as_dict() for item in facts]
    analyzer_output = {
        "tender_document": document.model_dump(mode="json"),
        "requirements": [item.model_dump(mode="json") for item in requirements],
        "financial_deadline_facts": financial_payload,
        "summary": summary.model_dump(mode="json"),
    }
    text_parts = [source.text for source in _financial_text_sources(document)]
    text_parts.extend(item.raw_text for item in document.title_evidence)
    text = "\n".join(dict.fromkeys(part for part in text_parts if part))
    source = ProcessedTenderDocument(
        document_id=document.document_id,
        filename=filename,
        document_result=document_result,
        analyzer_output=analyzer_output,
        metadata=dict(document.metadata),
        facts=tuple(
            FactObservation(
                "submission_deadline", item.fact.normalized["date"],
                DossierEvidence(
                    evidence.document_id, "submission_deadline", item.fact.normalized["date"],
                    text=item.fact.raw, page=evidence.page, bbox=evidence.bbox,
                    confidence=None, element_id=evidence.element_id,
                ),
            )
            for item in facts
            if item.fact.category == "submission_deadline" and item.fact.normalized
            for evidence in item.evidence
        ),
        text_for_classification=text,
    )
    dossier = build_tender_dossier(f"dossier-{document.document_id}", [source], title=document.title)
    attached = dossier.documents[0]
    data = {
        "dossier_id": dossier.dossier_id,
        "title": dossier.title,
        "reference": dossier.reference,
        "documents": [{
            "document_id": attached.document_id,
            "filename": attached.filename,
            "role": attached.role.role.value,
            "role_status": attached.role.status.value,
            "confidence": attached.role.confidence,
            "role_candidates": [
                {"role": role.value, "confidence": confidence}
                for role, confidence in attached.role.candidates
            ],
            "reasons": list(attached.role.reasons),
        }],
        "relationships": dossier.relationships,
        "conflicts": [
            {
                "fact_key": item.fact_key,
                "values": list(item.values),
                "message": item.message,
                "observations": [
                    {
                        "document_id": evidence.document_id,
                        "field": evidence.field,
                        "value": evidence.value,
                        "text": evidence.text,
                        "page": evidence.page,
                        "bbox": evidence.bbox,
                        "element_id": evidence.element_id,
                    }
                    for evidence in item.observations
                ],
            }
            for item in dossier.conflicts
        ],
        "diagnostics": [
            {"code": item.code, "message": item.message, "document_ids": list(item.document_ids)}
            for item in dossier.diagnostics
        ],
        "grouping": {
            "status": GroupingStatus.REVIEW.value,
            "reason": "Single-document endpoint cannot establish cross-document dossier membership.",
        },
    }
    return data, "single_document_dossier_grouping_not_evaluated"


def compose_tender_modules(
    document: TenderDocument, *, document_result: Any, filename: str,
) -> dict[str, Any]:
    """Run accepted V2 modules over one already processed CDC result."""
    facts, financial_diagnostics = _financial_facts(document)
    requirements = _requirements_with_value_refs(classify_document(document), facts)
    requirement_payload = [item.model_dump(mode="json") for item in requirements]
    financial_payload = [item.as_dict() for item in facts]
    summary = build_tender_summary(
        document,
        classified_requirements=requirement_payload,
        financial_deadline_facts=financial_payload,
    )
    dossier, dossier_reason = _dossier_payload(
        document, document_result=document_result, filename=filename,
        requirements=requirements, facts=facts, summary=summary,
    )
    return {
        "requirements": requirements,
        "financial_facts": facts,
        "financial_diagnostics": financial_diagnostics,
        "summary": summary,
        "dossier": dossier,
        "dossier_reason": dossier_reason,
    }
