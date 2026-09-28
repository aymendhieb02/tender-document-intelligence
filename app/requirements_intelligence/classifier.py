"""Small deterministic rules over already-extracted CDC wording and evidence."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from app.cdc_analysis.schema import Article, Evidence, Paragraph, Requirement, TenderDocument

from .models import ConfidenceLevel, MandatoryStatus, RequirementCategory, TenderRequirement


@dataclass(frozen=True)
class _Source:
    text: str
    evidence: tuple[Evidence, ...]
    article_id: str | None = None
    requirement_id: str | None = None


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_CATEGORY_RULES: tuple[tuple[RequirementCategory, tuple[str, ...]], ...] = (
    (RequirementCategory.ELIGIBILITY, (r"eligib", r"admissib", r"recevab", r"qualification", r"اهلي", r"المترشح")),
    (RequirementCategory.EXPERIENCE, (r"experience", r"reference(?:s)?", r"marche(?:s)? similaire", r"خبرة", r"مراجع")),
    (RequirementCategory.PERSONNEL, (r"personnel", r"technicien", r"ingenieur", r"expert", r"equipe", r"personnel cle", r"موارد بشرية", r"مهندس")),
    (RequirementCategory.EQUIPMENT, (r"equipement", r"materiel", r"machine", r"parc", r"معدات", r"آلات")),
    (RequirementCategory.CERTIFICATION, (r"certification", r"certifie", r"agrement", r"homolog", r"اعتماد")),
    (RequirementCategory.INSURANCE, (r"assurance", r"assure", r"responsabilite civile", r"تأمين")),
    (RequirementCategory.GUARANTEE, (r"caution", r"cautionnement", r"garantie provisoire", r"garantie definitive", r"garantie bancaire", r"garantie financiere", r"ضمان(?: مالي| بنكي)?")),
    (RequirementCategory.WARRANTY, (r"delai de garantie", r"garantie decennale", r"warranty", r"service apres vente", r"garantie")),
    (RequirementCategory.PENALTY, (r"penalite", r"penalites", r"retard", r"غرامة", r"غرامات")),
    (RequirementCategory.PAYMENT, (r"paiement", r"reglement", r"factur", r"acompte", r"دفع", r"خلاص")),
    (RequirementCategory.DEADLINE, (r"delai", r"date limite", r"echeance", r"deadline", r"اجل", r"موعد")),
    (RequirementCategory.FINANCIAL, (r"financ", r"chiffre d.affaires", r"capital", r"prix", r"montant", r"مالي", r"رقم المعاملات")),
    (RequirementCategory.EVALUATION, (r"evaluation", r"notation", r"criteres?", r"classement", r"تقييم", r"معايير")),
    (RequirementCategory.SUBMISSION, (r"soumission", r"offre", r"depot", r"remettre", r"enveloppe", r"تقديم", r"العرض")),
    (RequirementCategory.EXECUTION, (r"execution", r"executer", r"travaux", r"prestation", r"livraison", r"تنفيذ", r"الأشغال")),
    (RequirementCategory.LEGAL, (r"legal", r"juridique", r"loi", r"reglementation", r"conforme aux textes", r"قانوني")),
    (RequirementCategory.TECHNICAL, (r"technique", r"specification", r"norme", r"performance", r"تقني", r"مواصفات")),
    (RequirementCategory.ADMINISTRATIVE, (r"administratif", r"administrative", r"registre", r"identification", r"اداري")),
)

_MANDATORY = re.compile(
    r"\b(?:doit|doivent|devra|devront|est tenu de|sont tenus de|obligatoire|exige|exigee|exiges|exigees|est requis|sont requis)\b"
    r"|\b(?:يجب|يلتزم|تلتزم|يتعين|يتوجب|إلزامي|الزامي|يشترط)\b",
    re.I,
)
_OPTIONAL = re.compile(
    r"\b(?:facultatif|facultative|facultatifs|facultatives|peut|peuvent|optionnel|optionnelle|le cas echeant)\b"
    r"|\b(?:يمكن|اختياري|اختيارية)\b",
    re.I,
)
_CONDITIONAL = re.compile(
    r"\b(?:si|lorsque|en cas de|dans le cas ou|sous reserve de|a condition que|pour les candidats qui|le cas echeant)\b"
    r"|\b(?:اذا|إذا|عند|في حالة|في حال|بشرط)\b",
    re.I,
)
_OBLIGATION_SIGNAL = re.compile(
    _MANDATORY.pattern + r"|" + _OPTIONAL.pattern + r"|"
    r"\b(?:fournir|joindre|presenter|produire|deposer|respecter|disposer de|assurer)\b"
    r"|\b(?:تقديم|إرفاق|ارفاق|احترام|توفير)\b",
    re.I,
)
_SUBJECT = re.compile(
    r"\b(?:le|la|les)?\s*(candidat(?:s)?|soumissionnaire(?:s)?|titulaire|entreprise|entrepreneur|prestataire)\b"
    r"|\b(المترشح|المتعهد|الشركة|صاحب الصفقة)\b", re.I,
)
_ACTION_RULES: tuple[tuple[str, str], ...] = (
    (r"\b(?:fournir|joindre|presenter|produire|deposer|remettre)\b|(?:تقديم|إرفاق|ارفاق)", "submit"),
    (r"\b(?:disposer de|posseder|justifier de|detenir)\b|(?:يتوفر على|يملك|توفير)", "possess_or_prove"),
    (r"\b(?:respecter|se conformer a|observer)\b|(?:احترام|الامتثال)", "comply"),
    (r"\b(?:executer|realiser|effectuer|achever)\b|(?:تنفيذ|إنجاز|انجاز)", "perform"),
    (r"\b(?:payer|regler|verser)\b|(?:دفع|خلاص)", "pay"),
    (r"\b(?:assurer|garantir|maintenir)\b|(?:ضمان|تأمين)", "ensure"),
)
_REQUIRED_DOCUMENT_CUE = re.compile(
    r"\bdocuments? requis\b|\bdocuments? obligatoires?\b|\bpieces? (?:a fournir|exigees?|obligatoires?)\b"
    r"|\battestation\b|\bcertificat\b|وثائق|شهادة", re.I)


def _category(text: str) -> RequirementCategory:
    normalized = _normalise(text)
    if _REQUIRED_DOCUMENT_CUE.search(normalized):
        return RequirementCategory.REQUIRED_DOCUMENT
    for category, patterns in _CATEGORY_RULES:
        if any(re.search(pattern, normalized, re.I) for pattern in patterns):
            return category
    return RequirementCategory.OTHER


def _mandatory_status(text: str) -> MandatoryStatus:
    normalized = _normalise(text)
    if _CONDITIONAL.search(normalized) and _MANDATORY.search(normalized):
        return MandatoryStatus.CONDITIONAL
    if _OPTIONAL.search(normalized):
        return MandatoryStatus.OPTIONAL
    if _MANDATORY.search(normalized):
        return MandatoryStatus.MANDATORY
    if _CONDITIONAL.search(normalized):
        return MandatoryStatus.CONDITIONAL
    return MandatoryStatus.UNCLEAR


def _action(text: str) -> str | None:
    normalized = _normalise(text)
    for pattern, action in _ACTION_RULES:
        if re.search(pattern, normalized, re.I):
            return action
    return None


def _condition(text: str) -> str | None:
    normalized = _normalise(text)
    match = _CONDITIONAL.search(normalized)
    if not match:
        return None
    start = text.casefold().find(match.group(0).casefold())
    if start < 0:
        # Accent folding preserves offsets for ordinary French prose.
        start = min(match.start(), len(text))
    end = min(len(text), start + 240)
    return text[start:end].strip()


def _from_requirement(source: Requirement) -> _Source:
    return _Source(source.text, tuple(source.source_evidence), source.source_article, source.id)


def _from_article(source: Article) -> _Source:
    return _Source("\n".join(part for part in (source.title, source.text) if part),
                   tuple(source.source_evidence), source.id)


def _from_paragraph(source: Paragraph, article_id: str | None = None) -> _Source:
    return _Source(source.text, tuple(source.source_evidence), article_id)


def _document_sources(document: TenderDocument) -> Iterable[_Source]:
    yield from (_from_requirement(item) for item in document.requirements)
    seen_articles: set[str] = set()

    def visit_article(article: Article) -> Iterable[_Source]:
        if article.id in seen_articles:
            return
        seen_articles.add(article.id)
        source = _from_article(article)
        if _OBLIGATION_SIGNAL.search(_normalise(source.text)):
            yield source
        for clause in article.clauses:
            if _OBLIGATION_SIGNAL.search(_normalise(clause.text)):
                yield _from_paragraph(clause, article.id)

    def visit_sections(sections) -> Iterable[_Source]:
        for section in sections:
            for article in section.articles:
                yield from visit_article(article)
            for paragraph in section.paragraphs:
                if _OBLIGATION_SIGNAL.search(_normalise(paragraph.text)):
                    yield _from_paragraph(paragraph)
            yield from visit_sections(section.subsections)

    for article in document.articles:
        yield from visit_article(article)
    yield from visit_sections(document.sections)
    for paragraph in document.paragraphs:
        if _OBLIGATION_SIGNAL.search(_normalise(paragraph.text)):
            yield _from_paragraph(paragraph)
    for annex in document.annexes:
        for article in annex.articles:
            yield from visit_article(article)
        for paragraph in annex.paragraphs:
            if _OBLIGATION_SIGNAL.search(_normalise(paragraph.text)):
                yield _from_paragraph(paragraph)
        yield from visit_sections(annex.subsections)


def classify_text(
    text: str,
    *,
    evidence: Iterable[Evidence],
    source_article_id: str | None = None,
    source_requirement_id: str | None = None,
) -> TenderRequirement:
    """Classify one CDC text item; supplied source evidence is copied without invention."""
    evidence_items = tuple(evidence)
    if not evidence_items:
        raise ValueError("Requirement classification needs existing source evidence")
    evidence_ids = tuple(dict.fromkeys(
        identifier
        for item in evidence_items
        for identifier in (item.element_id, *item.source_element_ids)
        if identifier
    ))
    category = _category(text)
    mandatory_status = _mandatory_status(text)
    action = _action(text)
    subject_match = _SUBJECT.search(text)
    responsible_party = subject_match.group(0).strip() if subject_match else None
    stable_seed = "|".join((source_article_id or "", source_requirement_id or "", category.value,
                            ",".join(evidence_ids), _normalise(text)))
    identifier = hashlib.sha256(stable_seed.encode("utf-8")).hexdigest()[:20]
    return TenderRequirement(
        id=f"req-{identifier}",
        category=category,
        title=category.value.replace("_", " ").title(),
        description=text,
        mandatory_status=mandatory_status,
        responsible_party=responsible_party,
        action=action,
        condition=_condition(text) if mandatory_status == MandatoryStatus.CONDITIONAL else None,
        source_requirement_id=source_requirement_id,
        source_article_id=source_article_id,
        evidence_ids=evidence_ids,
        evidence=evidence_items,
        page=evidence_items[0].page if evidence_items else None,
        confidence=(ConfidenceLevel.HIGH if mandatory_status == MandatoryStatus.MANDATORY
                    and category != RequirementCategory.OTHER else ConfidenceLevel.LOW),
    )


def classify_document(document: TenderDocument) -> list[TenderRequirement]:
    """Interpret CDC candidates/articles only; never reopen or reprocess source files."""
    output: list[TenderRequirement] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for source in _document_sources(document):
        if not source.text.strip() or not source.evidence:
            continue
        classified = classify_text(source.text, evidence=source.evidence,
                                    source_article_id=source.article_id,
                                    source_requirement_id=source.requirement_id)
        key = (classified.category.value, classified.evidence_ids)
        if key in seen:
            continue
        seen.add(key)
        output.append(classified)
    return output
