import re, hashlib
import fitz

POSITIVE=("cahier des charges","cahiers des charges","cahier","charges","cdc","dossier d'appel d'offres","cctp","ccap","cps","dao")
RELATED=("appel d'offres","consultation","bordereau des prix","soumission","devis estimatif")
def classify(name, link_text, context=""):
 text=" ".join((name,link_text,context)).lower(); reasons=[]
 for term in POSITIVE:
  if term in text: reasons.append("positive:"+term)
 if reasons: return "LIKELY_CDC", reasons
 for term in RELATED:
  if term in text: reasons.append("related:"+term)
 return ("RELATED_TENDER_DOCUMENT" if reasons else "UNKNOWN"), reasons
def profile(path):
 with fitz.open(path) as doc:
  n=len(doc); sample=" ".join(doc[i].get_text() for i in sorted(set([0,max(0,n//2),max(0,n-1)])))
  words=re.findall(r"[\wÀ-ÿ]+",sample);
  tokens=re.findall(r"[a-z0-9à-ÿ]+",sample.lower())
  bits=[0]*64
  for token in tokens:
   hv=int.from_bytes(hashlib.blake2b(token.encode(),digest_size=8).digest(),"big")
   for bit in range(64): bits[bit]+=1 if hv & (1<<bit) else -1
  fingerprint="".join("1" if x>=0 else "0" for x in bits)
  simhash=f"{int(fingerprint,2):016x}"
  return {"page_count":n,"content_simhash":simhash,"native_text_available":len(sample.strip())>80,"estimated_native_text_ratio":round(sum(len(doc[i].get_text().strip())>40 for i in range(n))/max(1,n),3),"likely_scanned":len(sample.strip())<80,"language_hint":"ar" if len(re.findall(r"[\u0600-\u06ff]",sample))>20 else ("fr" if len(words)>10 else "unknown"),"table_hint":bool(re.search(r"\b(quantité|prix|montant|lot|total)\b",sample,re.I)),"title_hint":(sample.splitlines()[0][:180] if sample.splitlines() else "")}
def procurement(text):
 t=text.lower()
 for k,v in [("maintenance","MAINTENANCE"),("informatique","IT"),("étude","STUDY"),("travaux","WORKS"),("fourniture","GOODS"),("service","SERVICES")]:
  if k in t:return v
 return "UNKNOWN"
def document_type(text):
 t=text.lower()
 for k,v in [("cctp","CCTP"),("ccap","CCAP"),("bordereau","BOQ"),("devis estimatif","DEVIS_ESTIMATIF"),("règlement","REGLEMENT"),("soumission","SOUMISSION"),("cahier des charges","CDC"),("dao","DAO")]:
  if k in t:return v
 return "UNKNOWN"
def quality(source_official, classification, prof, duplicate=False):
 score=20 if source_official else 0
 score += 30 if classification=="LIKELY_CDC" else (15 if classification=="RELATED_TENDER_DOCUMENT" else 0)
 score += 15 if prof.get("page_count",0)>=5 else 5 if prof.get("page_count",0)>0 else 0
 score += 15 if prof.get("native_text_available") else 8 if prof.get("likely_scanned") else 0
 score += 10 if prof.get("title_hint") else 0
 score += 10 if prof.get("table_hint") else 0
 score -= 50 if duplicate else 0
 return max(0,min(100,score))
