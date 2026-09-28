"""All language-dependent matching lives here; packs are replaceable."""
from dataclasses import dataclass
import re
import unicodedata

from .contract import ElementInput, ElementPart


def normalize(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                            if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class LanguagePack:
    article: str = r"^(?:article|art\.)\s*(?:n[°ºo]\s*)?(?P<number>\d+(?:[.\-]\d+)*|premier|unique|\d+er)\b\s*[:.\-–—]?\s*(?P<title>.*)$"
    arabic_article: str = r"^الفصل\s*(?P<number>[\d٠-٩۰-۹]+|الأول|الاول|األول|االول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر)\s*[:：.\-–—]?\s*(?P<title>.*)$"
    annex: str = r"^(?:annexe?s?|annex|appendix)\s*(?:n[°ºo]\s*)?(?P<number>\d+|[IVXLCDM]+)\b\s*[:.\-–—]?\s*(?P<title>.*)$"
    part: str = r"^(?:partie|part)\s+(?P<number>[IVXLCDM]+|\d+)\b\s*[:.\-–—]?\s*(?P<title>.*)$"
    lot: str = r"^(?:(?:[IVXLCDM]+|\d+)\s*[.\-–—:]\s*)?lot\s*(?:n[°ºo]\s*)?(?P<number>[\d٠-٩۰-۹]+)\b\s*[:.\-–—]?\s*(?P<title>.*)$"
    section: str = r"^(?P<number>[A-Z]|[IVXLCDM]+)\s*[.\-–—:]\s*(?P<title>.*)$"
    subsection: str = r"^(?P<number>\d+(?:\.\d+)*)(?P<dot>\.)?\s+[-–—:]?\s*(?P<title>\S.*)$"
    clause: str = r"^(?P<number>\d+(?:\.\d+)*|[a-z])[.)]\s+"
    toc_title: str = r"^(sommaire|table des matieres|table of contents|contents|الفهرس)$"
    toc_entry: str = r"^(?P<title>.+?)(?:\s*\.{2,}\s*|\s{2,})(?P<page>\d+)\s*$"
    document_title: str = r"^(cahier des charges|tender document|كراس الشروط)\b"
    classifications: tuple[tuple[str, str], ...] = (
        ("boq", r"bordereau des prix.*devis|devis (?:quantitatif|estimatif)|bill of quantities|\bboq\b"),
        ("price_schedule", r"bordereau des prix|price schedule"),
        ("submission_form", r"\bsoumission\b|acte d.engagement|submission form"),
        ("guarantee_form", r"modele.*(?:caution|garantie)|engagements? de cautions?.*solidaires?|guarantee form"),
        ("administrative_declaration", r"declaration.*(?:honneur|administrative)"),
        ("financial_declaration", r"declaration.*financi|financial declaration"),
        ("technical_sheet", r"fiche technique|technical sheet"),
        ("technical_capacity_form", r"engagement pour la capacite technique|technical capacity"),
        ("information_sheet", r"fiche de renseignement|information sheet"),
        ("technical_specification", r"specifications? techniques?|technical specification"),
    )
    requirements: tuple[tuple[str, str], ...] = (
        ("deadline", r"date limite|delai.*(?:depot|soumission)|submission deadline"),
        ("document_required", r"(?:doit|doivent|devra|devront|obligatoire).*(?:fournir|joindre|document|attestation)|pieces.*(?:exigees|fournir)"),
        ("execution_duration", r"delai d.execution|execution duration"),
        ("validity_period", r"validite des offres|offer validity"),
        ("guarantee", r"cautionnement|garantie provisoire|garantie definitive"),
        ("retention", r"retenue de garantie"),
        ("penalty", r"penalite|penalties"),
        ("payment_term", r"modalites de paiement|delai de paiement|payment terms"),
        ("eligibility_requirement", r"conditions d.eligibilite|admis a participer"),
        ("technical_requirement", r"doit etre conforme|doivent etre conformes|must comply"),
        ("tax", r"\btva\b|\bvat\b"),
        ("evaluation_criterion", r"criteres d.evaluation|evaluation criteria"),
        ("submission_condition", r"offres.*(?:pli ferme|sous pli)|submission conditions"),
        ("buyer", r"^(?:maitre d.ouvrage|acheteur public|contracting authority)\s*:"),
        ("reference_number", r"^(?:appel d.offres|consultation|tender)\s*(?:n[°o]|reference)"),
        ("project_subject", r"^objet\s*:"),
        ("lot", r"^lot\s*(?:n[°o]\s*)?\d+"),
    )


@dataclass(frozen=True)
class Heading:
    kind: str
    number: str | None
    title: str | None
    level: int
    patterned: bool = True


class HeadingDetector:
    def __init__(self, pack: LanguagePack):
        self.pack = pack
        self.patterns = {k: re.compile(getattr(pack, k), re.I) for k in
                         ("arabic_article", "article", "annex", "part", "lot", "section", "subsection")}

    @staticmethod
    def _vertical_overlap(left: ElementInput, right: ElementInput) -> float:
        if not left.bbox or not right.bbox:
            return 0.0
        overlap = max(0.0, min(left.bbox[3], right.bbox[3]) - max(left.bbox[1], right.bbox[1]))
        return overlap / max(1.0, min(left.bbox[3] - left.bbox[1], right.bbox[3] - right.bbox[1]))

    @staticmethod
    def _composite(elements: list[ElementInput], ordered: list[ElementInput], *, rtl: bool = False) -> ElementInput:
        parts = []
        for element in ordered:
            parts.extend(element.parts or [ElementPart(id=element.id, text=element.text, bbox=element.bbox,
                                                       source_type=element.source_type,
                                                       confidence=element.confidence)])
        if rtl:
            parts.sort(key=lambda part: part.bbox[0] if part.bbox else 0, reverse=True)
        boxes = [e.bbox for e in ordered if e.bbox]
        bbox = ((min(b[0] for b in boxes), min(b[1] for b in boxes),
                 max(b[2] for b in boxes), max(b[3] for b in boxes)) if boxes else None)
        source_types = {part.source_type for part in parts}
        confidences = {part.confidence for part in parts}
        text = (" ".join(part.text.strip() for part in parts if part.text.strip()) if rtl else
                " ".join(e.text.strip() for e in ordered if e.text.strip()))
        return ElementInput(id=ordered[0].id, text=text,
                            kind="text", bbox=bbox,
                            source_type=next(iter(source_types)) if len(source_types) == 1 else None,
                            confidence=next(iter(confidences)) if len(confidences) == 1 else None,
                            parts=parts)

    def compose_structural_lines(self, elements: list[ElementInput]) -> list[ElementInput]:
        """Join only visually aligned tokens that form a strong structural cue.

        Document Intelligence can return one native-PDF word per element. This
        narrowly composes Arabic chapter/article cues, Partie/Lot headings, and
        the conventional Cahier des Clauses title line while keeping every raw
        producer element in ``ElementInput.parts`` for provenance.
        """
        positioned = [(i, e) for i, e in enumerate(elements) if e.bbox and e.text.strip()
                      and e.kind not in ("table", "header", "footer", "toc")]
        rows: list[list[tuple[int, ElementInput]]] = []
        for item in sorted(positioned, key=lambda pair: ((pair[1].bbox[1] + pair[1].bbox[3]) / 2, pair[0])):
            if rows and self._vertical_overlap(rows[-1][0][1], item[1]) >= 0.55:
                rows[-1].append(item)
            else:
                rows.append([item])

        replacements: dict[int, ElementInput] = {}
        consumed: set[int] = set()
        previous_part_row = False
        for row in rows:
            follows_part = previous_part_row
            previous_part_row = False
            indexes = sorted(i for i, _ in row)
            if indexes != list(range(indexes[0], indexes[-1] + 1)):
                continue
            row_elements = [e for _, e in row]
            is_arabic = any("الفصل" in e.text or any("الفصل" in part.text for part in e.parts)
                            for e in row_elements)
            ordered = sorted(row_elements, key=lambda e: e.bbox[0], reverse=is_arabic)
            row_parts = [part for element in ordered for part in
                         (element.parts or [ElementPart(id=element.id, text=element.text,
                                                       bbox=element.bbox, source_type=element.source_type,
                                                       confidence=element.confidence)])]
            if is_arabic:
                row_parts.sort(key=lambda part: part.bbox[0] if part.bbox else 0, reverse=True)
            text = (" ".join(part.text.strip() for part in row_parts if part.text.strip()) if is_arabic else
                    " ".join(e.text.strip() for e in ordered if e.text.strip()))
            normalized = normalize(text)
            heading = self.detect(text)
            is_part_heading = bool(heading and heading.kind == "part")
            part_title_line = follows_part and normalized.startswith("cahier des clauses") and len(text) <= 180
            arabic_article_line = is_arabic and heading is not None and heading.kind == "article"
            if not (arabic_article_line or (heading and heading.kind in ("part", "lot")) or part_title_line):
                previous_part_row = is_part_heading
                continue
            composite = self._composite(row_elements, ordered, rtl=is_arabic)
            replacements[indexes[0]] = composite
            consumed.update(indexes[1:])
            previous_part_row = is_part_heading

        output = []
        for index, element in enumerate(elements):
            if index in replacements:
                output.append(replacements[index])
            elif index not in consumed:
                output.append(element)
        return output

    def detect(self, text: str, kind: str = "text", level: int | None = None) -> Heading | None:
        for name, pattern in self.patterns.items():
            match = pattern.match(text.strip())
            if match:
                number, title = match.group("number", "title")
                if name == "arabic_article":
                    number = normalize_arabic_number(number)
                    name = "article"
                elif name == "lot":
                    number = normalize_arabic_number(number)
                    if re.match(r"^(?:dt|tnd|dinars?|€|\$)\b", title.strip(), re.I):
                        continue
                elif name == "part":
                    number = number.upper()
                    return Heading("part", number, title.strip() or None, 1)
                if name == "subsection" and "." not in number and not match.group("dot"):
                    continue
                # Sentence references are not standalone headings without layout confirmation.
                if name in ("article", "annex") and kind != "heading" and (
                    len(text) > 180 or re.match(r"^(?:du|de la|ci-dessus|ci-dessous|est|sera|s.applique)\b", title, re.I)
                ):
                    return None
                if name == "annex" and kind != "heading" and re.match(
                        r"^[),;]|^(?:fixe|fix\w*|au titre|est|sera|doit|devient|selon)\b", title, re.I):
                    return None
                depth = number.count(".") + 2 if name == "subsection" else 1
                return Heading(name, number, title.strip() or None, level or depth)
        if kind == "heading" or level is not None:
            return Heading("section", None, text.strip() or None, level or 1, False)
        return None


def classify(text: str, pack: LanguagePack) -> str:
    text = normalize(text)
    return next((name for name, pattern in pack.classifications if re.search(pattern, text)), "unknown")


def normalize_arabic_number(value: str) -> str:
    """Normalize Unicode decimal digits and source-evidenced Arabic ordinals."""
    value = value.strip()
    if value and all(char.isdecimal() for char in value):
        return "".join(str(unicodedata.decimal(char)) for char in value)
    plain = "".join(char for char in unicodedata.normalize("NFKD", value)
                    if not unicodedata.combining(char)).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    ordinals = {"الاول": "1", "االول": "1", "الثاني": "2", "الثالث": "3", "الرابع": "4",
                "الخامس": "5", "السادس": "6", "السابع": "7", "الثامن": "8", "التاسع": "9", "العاشر": "10"}
    return ordinals.get(plain, value)
