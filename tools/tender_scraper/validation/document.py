import hashlib
import re
import unicodedata
from pathlib import Path
import fitz

SIMHASH_MIN_CHARS = 80
SIMHASH_MIN_TOKENS = 15
ROLE_TERMS = {
    "CCAP": ("cahier des clauses administratives",),
    "CCTP": ("cahier des clauses techniques",),
    "REGLEMENT": ("règlement de consultation", "reglement de consultation"),
    "BOQ": ("bordereau des prix", "bordereau quantitatif"),
    "DEVIS_ESTIMATIF": ("devis estimatif", "détail estimatif"),
    "SOUMISSION": ("acte de soumission", "soumission du soumissionnaire"),
    "ANNEX": ("annexe", "annex"),
    "DAO": ("dossier d'appel d'offres", "dossier d’appel d’offres"),
    "CDC": ("cahier des charges", "cahiers des charges", "كراس الشروط"),
}
NOTICE_TERMS = ("avis d'appel d'offres", "avis d’appel d’offres", "avis de consultation", "avis d appel d offres")

def normalized_text(value):
    value = unicodedata.normalize("NFKC", value or "").replace("\ufffd", " ").lower()
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", value, flags=re.UNICODE).strip()

def text_simhash(value):
    normalized = normalized_text(value)
    tokens = re.findall(r"[\w\u0600-\u06ff]+", normalized, flags=re.UNICODE)
    if len(normalized) < SIMHASH_MIN_CHARS or len(tokens) < SIMHASH_MIN_TOKENS:
        return None
    weights = [0] * 64
    for token in tokens:
        hv = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64): weights[bit] += 1 if hv & (1 << bit) else -1
    return f"{sum((1 << i) for i, weight in enumerate(weights) if weight >= 0):016x}"

def validate_pdf(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size<5 or path.open("rb").read(5)!=b"%PDF-":
        return False, 0, "response signature is not PDF"
    try:
        with fitz.open(path) as doc:
            pages=len(doc)
            if pages<1:return False,0,"PDF has no pages"
        return True,pages,""
    except Exception as exc:return False,0,"PDF parser rejected file: "+str(exc)[:120]

def profile(path):
    ok,_,reason=validate_pdf(path)
    if not ok:raise ValueError(reason)
    with fitz.open(path) as doc:
        n = len(doc)
        sample_pages = sorted(set([*range(min(5, n)), max(0, n // 2), max(0, n - 1)]))
        sample = "\n".join(doc[i].get_text("text") for i in sample_pages)
        normalized = normalized_text(sample)
        chars_per_page = [len(normalized_text(doc[i].get_text("text"))) for i in range(n)]
        native_pages = sum(x > 40 for x in chars_per_page)
        arabic = len(re.findall(r"[\u0600-\u06ff]", sample))
        words = set(re.findall(r"[a-zA-ZÀ-ÿ]+", sample.lower()))
        french_terms = {"le","la","les","des","pour","appel","offres","cahier","soumission","article","marché","quantité","montant","présidence"}
        french_hits = len(words & french_terms)
        simhash = text_simhash(sample)
        language = "BILINGUAL" if arabic>100 and french_hits>=5 else ("ARABIC" if arabic>100 and french_hits<5 else ("FRENCH" if french_hits>=5 else "UNKNOWN"))
        return {"page_count":n,"sample_text":sample,"content_simhash":simhash,"near_duplicate_status":"COMPARABLE" if simhash else "NOT_COMPARABLE","native_text_available":len(normalized)>=SIMHASH_MIN_CHARS,"estimated_native_text_ratio":round(native_pages/max(1,n),3),"likely_scanned":native_pages==0,"language_hint":language,"table_hint":bool(re.search(r"\b(quantité|prix|montant|lot|total)\b",sample,re.I)),"title_hint":next((x.strip()[:180] for x in sample.splitlines() if x.strip()),""),"sample_chars":len(normalized)}

def classify_document(filename, sample_text, page_count, native_text_available=True):
    text = normalized_text(sample_text)
    name = normalized_text(filename)
    if not native_text_available or len(text) < SIMHASH_MIN_CHARS:
        role = next((r for r, terms in ROLE_TERMS.items() if any(normalized_text(t) in name for t in terms)), "UNKNOWN")
        return role, "REVIEW_NEEDS_OCR", ["native text below documented sample threshold; filename used only as review hint"]
    head = text[:2200]
    article_count = len(re.findall(r"\barticle\b", text)) + len(re.findall(r"الفصل", text))
    structural = article_count >= 3 and page_count >= 8
    notice = any(normalized_text(t) in head for t in NOTICE_TERMS)
    role = next((r for r, terms in ROLE_TERMS.items() if any(normalized_text(t) in text for t in terms)), None)
    if any(x in head for x in ("cession d une participation", "appel a manifestation d interet")):
        return "NOTICE", "REJECT", ["sale or expression-of-interest notice, not a procurement dossier"]
    template = any(x in text[:2500] for x in ("cahier de charge type", "cahiers de charge type")) or "type" in name
    if template:
        return "CDC", "REVIEW", ["generic/template cahier rather than a clearly identifiable live tender"]
    if notice and structural and page_count >= 8:
        return "CDC", "LIKELY_CDC", [f"notice cover followed by substantial article structure ({article_count} article mentions in sample)"]
    if notice and page_count >= 8 and article_count:
        return role or "NOTICE", "REVIEW", [f"long notice package has limited article structure ({article_count}); inspect before CDC use"]
    if notice:
        return "NOTICE", "RELATED_TENDER_DOCUMENT", ["notice wording without enough evidence of an attached cahier dossier"]
    if role in ("CCAP", "CCTP", "REGLEMENT", "BOQ", "DEVIS_ESTIMATIF", "SOUMISSION", "DAO"):
        return role, "LIKELY_CDC", ["specific document-family terminology in sampled native text"]
    if role=="ANNEX" and ("annex" in name or "annexe" in name or any(x in head[:500] for x in ("annexe", "annex"))):
        return "ANNEX", "RELATED_TENDER_DOCUMENT", ["annex label appears in filename or document opening"]
    explicit_cover_cdc = any(normalized_text(t) in head[:500] for t in ("cahier des charges", "cahiers des charges", "كراس الشروط"))
    if role == "CDC" and explicit_cover_cdc and page_count >= 8:
        return "CDC", "LIKELY_CDC", ["explicit cahier cover and substantial multi-page document"]
    if role == "CDC" and structural:
        return "CDC", "LIKELY_CDC", [f"cahier terminology and article structure ({article_count} headings in sample)"]
    if role == "CDC":
        return "CDC", "REVIEW", ["cahier terminology but insufficient sampled structure"]
    if any(x in text for x in ("appel d offres", "consultation", "soumission", "marché public")):
        return "OTHER", "RELATED_TENDER_DOCUMENT", ["procurement terminology; document role is unclear"]
    if any(x in text for x in ("cession d une participation", "appel a manifestation d interet")):
        return "NOTICE", "REJECT", ["not a procurement tender dossier"]
    return "UNKNOWN", "REVIEW", ["no decisive role evidence in sampled native text"]

def classify_candidate(name, link_text, context=""):
    text = normalized_text(" ".join((name, link_text, context)))
    if any(normalized_text(x) in text for x in ("cahier des charges","cahier de charge","cahier","cctp","ccap","dossier d appel d offres","dao","cps")):
        return "LIKELY_CDC", ["CDC or tender-dossier wording in filename/link context; PDF content must validate it"]
    if any(normalized_text(x) in text for x in ("avis d appel d offres","appel d offres","consultation","bordereau des prix","soumission","devis estimatif")):
        return "RELATED_TENDER_DOCUMENT", ["tender wording in filename/link context"]
    return "UNKNOWN", []

def classify(name, link_text, context=""):
    return classify_candidate(name, link_text, context)

def procurement(text):
    t = normalized_text(text)
    for k,v in (("maintenance","MAINTENANCE"),("informatique","IT"),("étude","STUDY"),("travaux","WORKS"),("fourniture","GOODS"),("acquisition","GOODS"),("service","SERVICES")):
        if normalized_text(k) in t:return v
    return "UNKNOWN"

def document_type(text):
    role, _, _ = classify_document("", text, 30, True)
    return role

def quality_scores(source_official, profile_data, provenance_complete=True, cdc_likelihood="REVIEW", document_role="UNKNOWN"):
    acquisition = (25 if source_official else 0) + (30 if profile_data.get("valid_pdf", True) else 0)
    acquisition += 20 if provenance_complete else 0
    acquisition += 20 if profile_data.get("page_count", 0) > 0 else 0
    acquisition += 5 if profile_data.get("page_count", 0) >= 2 else 0
    relevance = {"LIKELY_CDC": 55, "RELATED_TENDER_DOCUMENT": 20, "REVIEW": 8, "REVIEW_NEEDS_OCR": 8, "REJECT": 0}.get(cdc_likelihood, 0)
    benchmark = relevance + (10 if profile_data.get("page_count", 0) >= 8 else 5 if profile_data.get("page_count", 0) >= 3 else 0)
    benchmark += 10 if profile_data.get("table_hint") else 0
    benchmark += 10 if document_role in ("CDC", "CCAP", "CCTP", "DAO", "BOQ", "REGLEMENT", "ANNEX") else 0
    benchmark += 5 if profile_data.get("native_text_available") or profile_data.get("likely_scanned") else 0
    return {"acquisition_quality": min(100, acquisition), "benchmark_value": min(100, benchmark)}

def quality(source_official, classification, prof, duplicate=False):
    scores = quality_scores(source_official, prof, True, classification)
    if duplicate:
        scores["benchmark_value"] = max(0, scores["benchmark_value"] - 30)
    return scores["benchmark_value"]
