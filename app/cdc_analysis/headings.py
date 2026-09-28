"""All language-dependent matching lives here; packs are replaceable."""
from dataclasses import dataclass
import re
import unicodedata


def normalize(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                            if not unicodedata.combining(c)).split())


@dataclass(frozen=True)
class LanguagePack:
    article: str = r"^(?:article|art\.)\s*(?:n[°ºo]\s*)?(?P<number>\d+(?:[.\-]\d+)*|premier|unique|\d+er)\b\s*[:.\-–—]?\s*(?P<title>.*)$"
    annex: str = r"^(?:annexe?s?|annex|appendix)\s*(?:n[°ºo]\s*)?(?P<number>\d+|[IVXLCDM]+)\b\s*[:.\-–—]?\s*(?P<title>.*)$"
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
                         ("article", "annex", "section", "subsection")}

    def detect(self, text: str, kind: str = "text", level: int | None = None) -> Heading | None:
        for name, pattern in self.patterns.items():
            match = pattern.match(text.strip())
            if match:
                number, title = match.group("number", "title")
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
