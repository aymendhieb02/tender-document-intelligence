"""Deterministic financial and temporal value normalization for tender evidence.

The functions in this module consume text already supplied by the caller. They
do not perform OCR, classify document structure, or infer values absent from
the source. Each fact carries the exact source span used to normalize it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any


@dataclass(frozen=True)
class Fact:
    category: str
    raw: str
    normalized: dict[str, Any] | None
    status: str = "normalized"
    conflict_group: str | None = None

    def as_dict(self) -> dict[str, Any]:
        def safe(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, dict):
                return {key: safe(item) for key, item in value.items()}
            if isinstance(value, list):
                return [safe(item) for item in value]
            return value
        return {"category": self.category, "raw": self.raw,
                "normalized": safe(self.normalized), "status": self.status,
                "conflict_group": self.conflict_group}


_FR_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "decembre": 12,
}
_AR_MONTHS = {
    "يناير": 1, "فيفري": 2, "فبراير": 2, "مارس": 3, "أفريل": 4,
    "ابريل": 4, "ماي": 5, "مايو": 5, "جوان": 6, "يونيو": 6,
    "جويلية": 7, "يوليو": 7, "أوت": 8, "اغسطس": 8,
    "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11,
    "ديسمبر": 12,
}
_SMALL_FR = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
             "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
             "dix": 10, "onze": 11, "douze": 12, "treize": 13,
             "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20,
             "trente": 30, "quarante": 40, "cinquante": 50,
             "soixante": 60, "cent": 100}


def _fold_with_offsets(text: str) -> tuple[str, list[int]]:
    """Normalize for matching while retaining each folded character's source offset."""
    digits = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    output: list[str] = []
    offsets: list[int] = []
    for index, original in enumerate(text):
        normalized = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", original).translate(digits))
        chars = []
        for char in normalized:
            if unicodedata.combining(char) and not (
                    "ARABIC" in unicodedata.name(char, "") and "HAMZA" in unicodedata.name(char, "")):
                continue
            chars.append(char)
        for char in unicodedata.normalize("NFC", "".join(chars)).casefold():
            if char.isspace():
                if output and output[-1] != " ":
                    output.append(" ")
                    offsets.append(index)
            else:
                output.append(char)
                offsets.append(index)
    if output and output[-1] == " ":
        output.pop()
        offsets.pop()
    return "".join(output), offsets


def _fold(text: str) -> str:
    return _fold_with_offsets(text)[0]


def _raw_span(text: str, offsets: list[int], start: int, end: int) -> str:
    return text[offsets[start]:offsets[end - 1] + 1] if start < end else ""


def _decimal(token: str) -> Decimal | None:
    token = token.strip().replace("\u202f", " ").replace("\u00a0", " ")
    token = re.sub(r"\s", "", token)
    # A comma followed by one or two digits is a decimal separator; otherwise
    # punctuation is treated as a thousands separator only when unambiguous.
    if "," in token and "." in token:
        token = token.replace(",", "") if token.rfind(".") > token.rfind(",") else token.replace(".", "").replace(",", ".")
    elif "," in token:
        tail = token.rsplit(",", 1)[-1]
        head = token.rsplit(",", 1)[0]
        token = token.replace(",", ".") if len(tail) <= 2 or head.lstrip("0") == "" else token.replace(",", "")
    elif token.count(".") > 1:
        token = token.replace(".", "")
    try:
        return Decimal(token)
    except (InvalidOperation, ValueError):
        return None


def _written_fr_number(text: str) -> Decimal | None:
    folded = _fold(text).replace("-", " ")
    folded = re.sub(r"\b(et|le|la|l)\b", " ", folded)
    words = folded.split()
    if not words or any(word not in _SMALL_FR and word not in ("soixante", "dix") for word in words):
        return None
    # Corpus-evidenced small quantities and common tens; reject complex forms
    # instead of guessing when composition is unclear.
    if len(words) == 1:
        return Decimal(_SMALL_FR[words[0]])
    if len(words) == 2 and words[0] in ("vingt", "trente", "quarante", "cinquante", "soixante"):
        if words[1] in _SMALL_FR and 1 <= _SMALL_FR[words[1]] <= 19:
            return Decimal(_SMALL_FR[words[0]] + _SMALL_FR[words[1]])
    if words == ["quatre", "vingt"]:
        return Decimal(80)
    if "cent" in words and len(words) <= 3:
        idx=words.index("cent")
        tail=_written_fr_number(" ".join(words[idx+1:])) if words[idx+1:] else Decimal(0)
        head=_written_fr_number(" ".join(words[:idx])) if words[:idx] else Decimal(1)
        if head is not None and tail is not None:
            return head * Decimal(100) + tail
    return None


def _number(token: str) -> Decimal | None:
    value = _decimal(token)
    if value is not None:
        return value
    return _written_fr_number(token)


def _money(text: str) -> list[Fact]:
    folded, offsets = _fold_with_offsets(text)
    cur = r"(?:t\s*n\s*d|dt|d\.\s*t\.?|dinars?(?:\s+tunisiens?)?|dinar tunisien|دينار(?:\s+تونسي)?|د\.?ت\.?)"
    out = []
    pattern = re.compile(rf"(?P<num>\d[\d\s.,\u00a0\u202f]*\d|\d+)\s*(?P<cur>{cur})|(?P<cur2>{cur})\s*(?P<num2>\d[\d\s.,\u00a0\u202f]*\d|\d+)", re.I)
    for match in pattern.finditer(folded):
        token = match.group("num") or match.group("num2")
        amount = _decimal(token)
        if amount is None:
            continue
        raw = _raw_span(text, offsets, match.start(), match.end())
        start = max(0, match.start() - 90)
        near = folded[start:min(len(folded),match.end()+30)]
        tax = "TTC" if re.search(r"\bttc\b|toutes taxes comprises", near) else "HT" if re.search(r"\bht\b|hors taxes", near) else None
        guarantee_context = re.search(r"caution|garantie|cautionnement|ضمان|الضمان", near)
        provisional = guarantee_context and re.search(r"provisoire|الضمان المؤقت|ضمان مؤقت|مؤقت", near)
        out.append(Fact("provisional_guarantee" if provisional else "guarantee_amount" if guarantee_context else "money",
                        raw, {"amount": amount, "currency": "TND", "tax_basis": tax}))
    return out


def _percentages(text: str) -> list[Fact]:
    folded, offsets = _fold_with_offsets(text)
    out: list[Fact] = []
    pattern = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>%|‰|pour\s+mille|pour\s+cent|percent|per\s+mille)", re.I)
    for m in pattern.finditer(folded):
        value = _decimal(m.group("num"))
        unit = "PER_MILLE" if m.group("unit") in ("‰", "pour mille", "per mille") else "PERCENT"
        before = folded[max(0, m.start()-90):m.start()]
        after = folded[m.end():min(len(folded),m.end()+75)]
        penalty = bool(re.search(r"penalit|retard|غرام|خطية", before))
        cap = penalty and bool(re.search(r"plafonn|maximum|maximal|ne peut depasser|ne depass|limite|cap|سقف|depasser|تتجاوز|تجاوز", before))
        retention = bool(re.search(r"retenue|retention|احتفاظ", before[-20:]) or re.search(r"retenue|retention|احتفاظ", after[:15]))
        payment_context = bool(re.search(r"paiement|versement|payment|صرف|الدفع", before))
        period = "DAY" if re.search(r"jour|daily|per day|par jour|يوم", after) or re.search(r"jour|يوم", before[-35:]) else None
        period = "HOUR" if re.search(r"heure|hour|ساعة", after) or re.search(r"heure|ساعة", before[-35:]) else period
        basis = "CONTRACT_AMOUNT" if re.search(r"montant.{0,25}(?:contrat|marche)|contract amount|المبلغ", before+" "+after) else None
        category = ("penalty_cap" if cap else "penalty_rate" if penalty else
                    "retention" if retention else "payment_component" if payment_context else
                    "vat_rate" if re.search(r"\btva\b|ضريبة القيمة المضافة",before+" "+after) else "percentage")
        if category in ("retention", "payment_component"):
            basis = "PAYMENT_AMOUNT"
        raw = _raw_span(text, offsets, m.start(), m.end())
        out.append(Fact(category, raw, {"value": value, "unit": unit,
                    "period": period, "basis": basis}))
    # Written French percent with paired digits, e.g. deux pour cent (2%).
    written = re.compile(r"(?P<words>(?:vingt|trente|quarante|cinquante|soixante|\w+)(?:[- ](?:et[- ])?\w+)?)\s+pour\s+cent\s*\(\s*(?P<num>\d+(?:[.,]\d+)?)\s*%\s*\)", re.I)
    for m in written.finditer(folded):
        if any(f.raw == _raw_span(text, offsets, m.start(), m.end()) for f in out):
            continue
        v = _decimal(m.group("num"))
        if v is not None:
            out.append(Fact("percentage", _raw_span(text, offsets, m.start(), m.end()), {"value": v, "unit": "PERCENT", "period": None, "basis": None}))
    # Formula multipliers in delay clauses are ratios, not percentages.
    formula = re.compile(r"(?:penalit|retard|خطية|غرام)[^\n.;]{0,180}?(?:x|×|\*)\s*(?P<n>\d+(?:[.,]\d+)?)", re.I)
    for m in formula.finditer(folded):
        value = _decimal(m.group("n"))
        if value is None: continue
        clause=folded[m.start():m.end()]
        period="DAY" if re.search(r"jour|يوم",clause) else "HOUR" if re.search(r"heure|ساعة",clause) else None
        if not any(f.category=="penalty_rate" and f.normalized and f.normalized.get("value")==value for f in out):
            out.append(Fact("penalty_rate",_raw_span(text, offsets, m.start(), m.end()),{"value":value,"unit":"DECIMAL_RATE","period":period,"basis":"CONTRACT_AMOUNT"}))
    return out


def _dates(text: str) -> list[Fact]:
    folded, offsets = _fold_with_offsets(text)
    out: list[Fact] = []
    iso = re.compile(r"\b(?P<y>20\d{2})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})\b")
    named = re.compile(r"(?P<d>\d{1,2})\s+(?P<month>[\w\u0600-\u06ff]+)\s+(?P<y>20\d{2})", re.I)
    for pattern, is_iso in ((iso, True), (named, False)):
        for m in pattern.finditer(folded):
            try:
                if is_iso:
                    y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
                else:
                    y, d = int(m.group("y")), int(m.group("d"))
                    mo = _FR_MONTHS.get(m.group("month"), _AR_MONTHS.get(m.group("month")))
                    if mo is None:
                        continue
                day = date(y, mo, d).isoformat()
            except ValueError:
                continue
            tail = folded[m.end():m.end()+55]
            tm = re.search(r"\b(?P<h>\d{1,2})\s*(?:h|:|ساعة)\s*(?P<mi>\d{2})?", tail)
            norm: dict[str, Any] = {"date": day}
            if tm:
                h, minute = int(tm.group("h")), int(tm.group("mi") or 0)
                if h < 24 and minute < 60:
                    norm["time"] = f"{h:02d}:{minute:02d}"
            if not tm:
                arabic_hours={"الحادية عشرة":11,"العاشرة":10,"الثانية عشرة":12,"التاسعة":9,"الثامنة":8,"السابعة":7}
                for phrase,hour in arabic_hours.items():
                    ordinal=re.search(phrase,tail)
                    if ordinal:
                        norm["time"]=f"{hour:02d}:00"
                        break
            preceding=folded[max(0,m.start()-90):m.start()]
            preceding=re.split(r"[.;!?\n]",preceding)[-1]
            deadline_context=preceding+" "+tail
            kind=("site_visit_deadline" if re.search(r"visite.{0,30}(?:lieu|site)|visite des lieux|زيارة",deadline_context) else
                  "clarification_deadline" if re.search(r"clarification|eclaircissement|question|استفسار",deadline_context) else
                  "submission_deadline" if re.search(r"date limite|reception des offres|آخر أجل|قبول العروض|الساعة", deadline_context) else "date")
            out.append(Fact(kind,
                            _raw_span(text, offsets, m.start(), min(len(offsets), m.end() + (tm.end() if tm else 0))), norm))
    # Numeric day/month dates are accepted only if the ordering is unambiguous.
    numeric = re.compile(r"\b(?P<a>\d{1,2})[./](?P<b>\d{1,2})[./](?P<y>20\d{2})\b")
    for m in numeric.finditer(folded):
        a,b,y = int(m.group("a")),int(m.group("b")),int(m.group("y"))
        if a <= 12 and b <= 12:
            out.append(Fact("date", _raw_span(text, offsets, m.start(), m.end()), None, "ambiguous"))
            continue
        d,mo=(a,b) if a>12 else (b,a)
        try: value=date(y,mo,d).isoformat()
        except ValueError: continue
        out.append(Fact("date",_raw_span(text, offsets, m.start(), m.end()),{"date":value}))
    return out


def _durations(text: str) -> list[Fact]:
    folded, offsets = _fold_with_offsets(text)
    units = r"jours?|j(?:ours?)?\.?|أيام|يوما|يوم|semaines?|mois|شهر|أشهر|ans?|annees?|سنة|سنوات"
    number = r"\d+(?:[.,]\d+)?|(?:un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt|trente|quarante|cinquante|soixante|cent)(?:[- ](?:et[- ])?(?:un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt|trente|quarante|cinquante|soixante|cent))?(?:\s*\(\s*\d+(?:[.,]\d+)?\s*\))?"
    pat = re.compile(rf"(?P<n>{number})\s*(?P<u>{units})", re.I)
    out = []
    for m in pat.finditer(folded):
        number_text=m.group("n")
        pair=re.search(r"\(\s*(\d+(?:[.,]\d+)?)\s*\)",number_text)
        word_text=re.sub(r"\s*\([^)]*\)","",number_text).strip()
        val = _number(pair.group(1)) if pair else _number(word_text)
        if val is None: continue
        u = m.group("u")
        unit = "DAY" if re.match(r"jour|j\b|يوم|أيام",u) else "WEEK" if u.startswith("semaine") else "MONTH" if re.match(r"mois|شهر|أشهر",u) else "YEAR"
        before=folded[max(0,m.start()-95):m.start()]
        before=re.split(r"[.;!?\n]",before)[-1]
        after=folded[m.end():min(len(folded),m.end()+55)]
        category=("offer_validity" if re.search(r"validite|valable|صلوحي",before) or re.search(r"offre.{0,30}pendant",before) else
                  "warranty_period" if re.search(r"garantie|warranty|ضمان",before) else
                  "payment_deadline" if re.search(r"paiement|facture|payment|الدفع",before+" "+after) and re.search(r"delai|jours|أجل|يوما",before+" "+after) else
                  "execution_period" if re.search(r"execution|execut|achevement|delai|مدة|أجل",before) else "duration")
        out.append(Fact(category,_raw_span(text, offsets, m.start(), m.end()),{"value":val,"unit":unit}))
    return out


def _schedules(text: str) -> list[Fact]:
    folded, offsets = _fold_with_offsets(text)
    terms=((r"trimestriellement|chaque trimestre|tous les trimestres|كل ثلاثة أشهر", "QUARTERLY"),
           (r"mensuellement|chaque mois|tous les mois|شهريا", "MONTHLY"),
           (r"annuellement|chaque année|tous les ans|سنويا", "ANNUAL"),
           (r"semestriellement|chaque semestre|كل ستة أشهر", "SEMIANNUAL"))
    out=[]
    payment = bool(re.search(r"paiement|versement|facture|payment|الدفع|صرف",folded))
    for pat,period in terms:
        for m in re.finditer(pat,folded):
            clause=folded[max(0,m.start()-100):min(len(folded),m.end()+100)]
            if not payment: continue
            norm={"frequency":period,"timing":"IN_ARREARS" if re.search(r"terme echu|apres echeance|à terme échu",clause) else None}
            out.append(Fact("payment_schedule",_raw_span(text, offsets, m.start(), m.end()),norm))
    return out


def normalize_financial_deadlines(text: str) -> list[Fact]:
    """Return deterministic facts found in *text*, preserving each matched span.

    Conflicting deadlines (two different unqualified submission dates) are
    retained and tagged with one conflict group; callers must not choose one.
    """
    if not isinstance(text,str) or not text.strip(): return []
    facts=_money(text)+_percentages(text)+_dates(text)+_durations(text)+_schedules(text)
    date_facts=[f for f in facts if f.category=="submission_deadline" and f.normalized]
    distinct={f.normalized.get("date") for f in date_facts}
    if len(distinct)>1:
        group="submission_deadline_conflict"
        facts=[Fact(f.category,f.raw,f.normalized,"conflict" if f in date_facts else f.status,
                    group if f in date_facts else f.conflict_group) for f in facts]
    # Exact duplicate spans can arise from overlapping detectors; preserve the
    # first category match while allowing compound rate and cap facts together.
    seen=set(); unique=[]
    for fact in facts:
        key=(fact.category,fact.raw,fact.normalized and tuple(sorted((k,str(v)) for k,v in fact.normalized.items())))
        if key not in seen: seen.add(key); unique.append(fact)
    return unique
