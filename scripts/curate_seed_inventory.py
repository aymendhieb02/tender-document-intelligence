import argparse
import csv
import hashlib
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import fitz
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.tender_scraper.validation.document import classify_document, profile, procurement, quality_scores

FIELDS = ["filename", "size_bytes", "sha256", "valid_pdf", "page_count", "native_text_available", "likely_scanned", "language_hint", "document_role", "document_role_reasons", "cdc_likelihood", "review_status", "exact_duplicate_of", "content_simhash", "near_duplicate_status", "title_hint", "organization", "year_hint", "procurement_type", "acquisition_quality", "benchmark_value", "notes"]
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def count(rows, field):
    return Counter(r.get(field) or "UNKNOWN" for r in rows)
def make(seed_dir, output_dir):
    seed_dir=Path(seed_dir).resolve(); rows=[]
    for path in sorted(seed_dir.rglob("*")):
        if not path.is_file(): continue
        row={"filename":path.relative_to(seed_dir).as_posix(),"size_bytes":path.stat().st_size,"sha256":digest(path),"valid_pdf":False,"page_count":"","native_text_available":False,"likely_scanned":False,"language_hint":"UNKNOWN","document_role":"UNKNOWN","document_role_reasons":"","cdc_likelihood":"REVIEW","review_status":"REVIEW_NEEDS_OCR","exact_duplicate_of":"","content_simhash":"","near_duplicate_status":"NOT_COMPARABLE","title_hint":"","organization":"UNKNOWN","year_hint":"UNKNOWN","procurement_type":"UNKNOWN","acquisition_quality":0,"benchmark_value":0,"notes":""}
        if path.suffix.lower()==".pdf":
            try:
                prof=profile(path); row.update(valid_pdf=True,page_count=prof["page_count"],native_text_available=prof["native_text_available"],likely_scanned=prof["likely_scanned"],language_hint=prof["language_hint"],content_simhash=prof["content_simhash"] or "",near_duplicate_status=prof["near_duplicate_status"],title_hint=prof["title_hint"].replace("\ufffd","").strip())
                row["document_role"],row["cdc_likelihood"],reasons=classify_document(path.name,prof["sample_text"],prof["page_count"],prof["native_text_available"])
                row["document_role_reasons"]="; ".join(reasons)
                if not prof["native_text_available"]: row["review_status"]="REVIEW_NEEDS_OCR"
                elif row["cdc_likelihood"]=="LIKELY_CDC": row["review_status"]="PENDING_HUMAN_REVIEW"
                elif row["document_role"]=="NOTICE": row["review_status"]="EXCLUDED_NOTICE"
                elif row["cdc_likelihood"]=="RELATED_TENDER_DOCUMENT": row["review_status"]="PENDING_HUMAN_REVIEW"
                else: row["review_status"]="REVIEW"
                folder=path.relative_to(seed_dir).parent.as_posix()
                if "Présidence du Gouvernement" in folder:row["organization"]="Présidence du Gouvernement"
                year=re.search(r"20[0-9]{2}",path.name)
                if year:row["year_hint"]=year.group(0)
                row["procurement_type"]=procurement(prof["sample_text"])
                scores=quality_scores(False, {**prof,"valid_pdf":row["valid_pdf"]}, False, row["cdc_likelihood"], row["document_role"])
                row["acquisition_quality"]=scores["acquisition_quality"]
                row["benchmark_value"]=scores["benchmark_value"]
                row["notes"]="Folder-based organization is a grouping hint only; source page URL and download provenance were not supplied."
            except Exception as exc:row["notes"]="PDF parse error: "+str(exc)[:180];row["review_status"]="REJECT_INVALID_PDF"
        else:row["document_role"]="OTHER";row["cdc_likelihood"]="REJECT";row["review_status"]="REJECT_NON_PDF";row["near_duplicate_status"]="NOT_COMPARABLE"
        rows.append(row)
    groups=defaultdict(list)
    for r in rows:
        if r["valid_pdf"]:groups[r["sha256"]].append(r)
    duplicate_count=0
    for group in groups.values():
        if len(group)<2:continue
        canonical=sorted(group,key=lambda r:(bool(re.search(r"\s*\(\d+\)(?=\.pdf$)",r["filename"],re.I)),r["filename"]))[0]
        for r in group:
            if r is canonical:continue
            r["exact_duplicate_of"]=canonical["filename"];r["near_duplicate_status"]="EXACT_DUPLICATE";r["review_status"]="DUPLICATE_HISTORY";duplicate_count+=1
    comparable=[r for r in rows if r["valid_pdf"] and r["content_simhash"] and not r["exact_duplicate_of"]]
    for i,a in enumerate(comparable):
        near=[]
        for b in comparable[i+1:]:
            if a["sha256"]!=b["sha256"] and (int(a["content_simhash"],16)^int(b["content_simhash"],16)).bit_count()<=3:
                near.append(b["filename"]);b["near_duplicate_status"]="POSSIBLE_NEAR_DUPLICATE"
        if near:a["near_duplicate_status"]="POSSIBLE_NEAR_DUPLICATE"
    unique=[r for r in rows if r["valid_pdf"] and not r["exact_duplicate_of"]]
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    with (output_dir/"seed_inventory.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    write_report(rows,unique,duplicate_count,output_dir/"seed_corpus_report.md")
    rejected=[]
    stamp=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    for r in rows:
        if r["exact_duplicate_of"]: code="EXACT_DUPLICATE"; detail=f"duplicate seed file; canonical={r['exact_duplicate_of']}"
        elif r["cdc_likelihood"]=="REJECT": code="NOT_PROCUREMENT"; detail="seed document is not a procurement dossier"
        elif r["document_role"]=="NOTICE" and r["cdc_likelihood"]=="RELATED_TENDER_DOCUMENT": code="NOTICE_ONLY"; detail="notice retained in history but excluded from CDC corpus"
        elif not r["valid_pdf"]: code="INVALID_PDF"; detail=r["notes"]
        else: continue
        rejected.append({"candidate_id":"SEED-"+r["sha256"][:12],"source_id":"UNKNOWN","url":"","reason_code":code,"reason_detail":f"{r['filename']}: {detail}","timestamp":stamp})
    prior=[]; ledger=output_dir/"rejected.csv"
    if ledger.exists():
        with ledger.open(encoding="utf-8-sig",newline="") as f:prior=list(csv.DictReader(f))
    combined={(x["candidate_id"],x["reason_code"]):x for x in prior}
    combined.update({(x["candidate_id"],x["reason_code"]):x for x in rejected})
    with ledger.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["candidate_id","source_id","url","reason_code","reason_detail","timestamp"]);w.writeheader();w.writerows(combined.values())
    return rows,unique,duplicate_count

def write_report(rows,unique,duplicates,path):
    valid=[r for r in rows if r["valid_pdf"]]
    likely=sum(r["cdc_likelihood"]=="LIKELY_CDC" for r in unique)
    related=sum(r["cdc_likelihood"]=="RELATED_TENDER_DOCUMENT" for r in unique)
    notice=sum(r["document_role"]=="NOTICE" for r in unique)
    review=sum(r["review_status"] in ("PENDING_HUMAN_REVIEW","REVIEW_NEEDS_OCR","REVIEW") for r in unique)
    native=sum(r["native_text_available"] for r in unique); scanned=sum(r["likely_scanned"] for r in unique);unknown=max(0,len(unique)-native-scanned)
    lang=count(unique,"language_hint")
    lines=["# Seed corpus curation report","",f"Generated: {date.today().isoformat()}","","## Inventory and likely relevance","",f"- TOTAL FILES: {len(rows)}",f"- VALID PDFs: {len(valid)}",f"- EXACT DUPLICATE FILES: {duplicates}",f"- Unique valid documents after exact deduplication: {len(unique)}",f"- LIKELY CDC: {likely}",f"- RELATED TENDER DOCUMENT: {related}",f"- NOTICE: {notice}",f"- OTHER roles: {sum(r['document_role']=='OTHER' for r in unique)}",f"- REVIEW NEEDED (all pending/review rows): {review}",f"- REVIEW_NEEDS_OCR: {sum(r['cdc_likelihood']=='REVIEW_NEEDS_OCR' for r in unique)}","", "A `LIKELY_CDC` is a deterministic screening result, not a human approval or benchmark label. Duplicate rows remain in the inventory and do not count twice in the distributions below.","","## Text profile","",f"- NATIVE: {native}",f"- SCANNED / no usable sampled text: {scanned}",f"- UNKNOWN: {unknown}",f"- FRENCH: {lang['FRENCH']}",f"- ARABIC: {lang['ARABIC']}",f"- BILINGUAL: {lang['BILINGUAL']}",f"- UNKNOWN language: {lang['UNKNOWN']}","","## Page count distribution",""]
    bins=(("1",lambda n:n==1),("2–5",lambda n:2<=n<=5),("6–20",lambda n:6<=n<=20),("21–50",lambda n:21<=n<=50),("51–100",lambda n:51<=n<=100),("101+",lambda n:n>100))
    for label,fn in bins:lines.append(f"- {label}: {sum(1 for r in unique if r['page_count'] and fn(int(r['page_count'])))}")
    lines += ["", "## Organization distribution", ""]
    for k,v in sorted(count(unique,"organization").items()):lines.append(f"- {k}: {v}")
    lines += ["", "## Document role distribution", ""]
    for k,v in sorted(count(unique,"document_role").items()):lines.append(f"- {k}: {v}")
    lines += ["", "## Diversity distributions", ""]
    for field in ("procurement_type","document_role","year_hint","language_hint"):
        lines.append(f"### {field.replace('_',' ').title()}")
        for k,v in sorted(count(unique,field).items()):lines.append(f"- {k}: {v}")
        lines.append("")
    def warn_concentration(field,label,values):
        vals=Counter(values); total=max(1,len(values)); dominant=max(vals.items(),key=lambda x:x[1]) if vals else ("UNKNOWN",0)
        if dominant[1]/total>0.60:lines.append(f"WARNING: {dominant[1]/total:.0%} of the seed corpus is concentrated in one {label} ({dominant[0]}).")
    for field,label in (("organization","organization"),("procurement_type","procurement category"),("document_role","document family"),("year_hint","year"),("language_hint","language")):
        warn_concentration(field,label,[r.get(field) or "UNKNOWN" for r in unique])
    warn_concentration("text_profile","native/scanned profile",["NATIVE" if r["native_text_available"] else ("SCANNED" if r["likely_scanned"] else "UNKNOWN") for r in unique])
    lines += ["", "A small first-pages native-text sample was used; no OCR was run. Categories remain UNKNOWN where that sample did not support a value. Organization grouping from the directory name is a grouping hint, not a verified source URL. See inventory notes and reasons for row-level provenance limitations.",""]
    path.write_text("\n".join(lines),encoding="utf-8")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Inventory and conservatively curate an extracted seed PDF directory.")
    parser.add_argument("--seed-dir",required=True,help="Existing extracted seed directory (read-only).")
    parser.add_argument("--output-dir",default="data/acquisition",help="Repository acquisition metadata output directory.")
    args=parser.parse_args(); rows,unique,duplicates=make(args.seed_dir,args.output_dir)
    print(f"files={len(rows)} valid={sum(r['valid_pdf'] for r in rows)} duplicates={duplicates} likely_cdc={sum(r['cdc_likelihood']=='LIKELY_CDC' for r in unique)}")
