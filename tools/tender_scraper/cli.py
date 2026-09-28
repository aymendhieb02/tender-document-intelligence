import argparse
import json
import logging
import os
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from .config import Config, ROOT
from .adapters.generic_official import GenericOfficialAdapter
from .adapters.pm_tn import PresidencyAdapter
from .adapters.mtc_gov_tn import MtcAdapter
from .adapters.marchespublics import HaicopAdapter
from .adapters.tuneps import TunepsAdapter
from .validation.document import classify_candidate, classify_document, profile, procurement, quality_scores, validate_pdf
from .utils import safe_name, sha256, same_domain, allowed_path, extract_links
from .storage.manifest import (MANIFEST_FIELDS, REJECTED_FIELDS, read_csv, write_csv,
    exact_duplicate, near_duplicate, append_rejections, merge_candidates, write_manifest)
from .storage.state import CANDIDATE_FIELDS, load_candidates, save_candidates

LOG=logging.getLogger("tender_scraper")
PAGE_TERMS=("tender","procurement","appel","consultation","marche","cahier","publication","avis","ao")
def session(config):
    s=requests.Session();s.headers.update({"User-Agent":config.user_agent,"Accept":"text/html,application/pdf,*/*;q=0.7"});return s
def robots_allowed(s,url,config):
    robots=urlparse(url)._replace(path="/robots.txt",query="",fragment="").geturl()
    try:
        r=s.get(robots,timeout=config.timeout)
        if r.status_code in (404,410):return True
        r.raise_for_status();rp=urllib.robotparser.RobotFileParser();rp.parse(r.text.splitlines())
        return rp.can_fetch(config.user_agent,url)
    except requests.RequestException as exc:
        LOG.warning("[ROBOTS_UNAVAILABLE] %s; skipping conservatively (%s)",url,type(exc).__name__);return False
def sources_validate(cfg):
    rows=read_csv(cfg.data_dir/"sources.csv");errors=[];ids=set()
    for r in rows:
        if r["source_id"] in ids:errors.append(f"duplicate source_id {r['source_id']}")
        ids.add(r["source_id"])
        for key in ("organization","domain","base_url","tender_url","adapter","verification_date","public_metadata_access","public_document_download","source_evidence_url"):
            if not r.get(key):errors.append(f"{r.get('source_id')}: missing {key}")
        if r.get("enabled")=="true" and r.get("official")!="true":errors.append(f"{r.get('source_id')}: enabled source is not marked official")
        host=urlparse(r.get("base_url","")).hostname or ""
        if host!=r.get("domain") and not host.endswith("."+r.get("domain","")):errors.append(f"{r.get('source_id')}: base host does not match domain")
    print(f"Sources: {len(rows)}; enabled: {sum(r.get('enabled')=='true' for r in rows)}; verified: {sum(bool(r.get('verification_date')) for r in rows)}")
    if errors:raise SystemExit("\n".join(errors))
def enabled_sources(rows, source_ids=None):
    return [r for r in rows if r.get("enabled")=="true" and (not source_ids or r.get("source_id") in source_ids)]
def dossier_id_for(source_id,page_url):
    import hashlib
    return "DOSSIER-"+hashlib.sha256((source_id+page_url).encode()).hexdigest()[:12]
def corpus_dimensions(rows):
    fields=("source_id","organization","organization_type","normalized_procurement_type","document_type","year_hint","language_hint","text_profile","acquisition_quality_tier")
    dims={field:{} for field in fields}
    for r in rows:
        year=next(iter(re.findall(r"20[0-9]{2}",r.get("title", ""))),"UNKNOWN")
        values={"year_hint":year,"text_profile":"NATIVE" if r.get("native_text_available")=="True" else ("SCANNED" if r.get("likely_scanned")=="True" else "UNKNOWN")}
        for f in fields:
            v=values.get(f) or r.get(f) or "UNKNOWN";dims[f][v]=dims[f].get(v,0)+1
    return dims
def adapter_for(name):
    return {"pm_tn":PresidencyAdapter,"mtc_gov_tn":MtcAdapter,"marchespublics":HaicopAdapter,"tuneps":TunepsAdapter,"generic_official":GenericOfficialAdapter}.get(name,GenericOfficialAdapter)()
def candidate_id(url):
    import hashlib
    return "CAND-"+hashlib.sha256(url.encode()).hexdigest()[:12].upper()
def make_candidate(src,page_url,item):
    name=Path(urlparse(item["document_url"]).path).name
    return {"candidate_id":candidate_id(item["document_url"]),"source_id":src["source_id"],"organization":src["organization"],"tender_title":item["document_link_text"],"tender_reference":"","publication_date":"","deadline":"","source_procurement_type":"","normalized_procurement_type":procurement(item["document_link_text"]),"tender_page_url":page_url,"document_url":item["document_url"],"document_link_text":item["document_link_text"],"document_filename":name,"suspected_document_type":"CDC" if item["classification"]=="LIKELY_CDC" else "UNKNOWN","discovery_method":"generic_html","discovered_at":datetime.now(timezone.utc).isoformat(),"download_status":"QUEUED","quality_status":"PENDING","classification_reasons":";".join(item["classification_reasons"]),"review_status":"PENDING","notes":""}
def pagination_link(anchor,page_url,source_url):
    href=urljoin(page_url,anchor.get("href",""))
    text=(" ".join(anchor.stripped_strings) if hasattr(anchor,"stripped_strings") else str(anchor.get("text",""))).lower()
    rel=anchor.get("rel",""); rel=(" ".join(rel) if isinstance(rel,(list,tuple)) else rel).lower()
    query=urlparse(href).query.lower()
    explicit=("next" in rel or text in ("next","suivant","›","»",">") or bool(re.search(r"(?:^|&)(?:page|paged|offset|start)=",query)))
    return explicit and same_domain(source_url,href) and urlparse(href).path==urlparse(source_url).path

def discover(cfg, source_ids=None, limit=None, http=None):
    sources=enabled_sources(read_csv(cfg.data_dir/"sources.csv"),source_ids)
    path=cfg.data_dir/"candidates.csv";old=load_candidates(path);old_by_url={r.get("document_url"):r for r in old};found=[];seen=set(old_by_url);s=http or session(cfg);total_new=0
    for src in sources:
        adapter=adapter_for(src["adapter"]);queue=[(src["tender_url"],0)];visited=set();page_count=0;new_count=0
        while queue and page_count<cfg.max_pages_per_source:
            url,depth=queue.pop(0)
            if url in visited or depth>cfg.max_depth:continue
            visited.add(url)
            if not robots_allowed(s,url,cfg):LOG.info("[ROBOTS_BLOCK] %s",url);continue
            try:r=s.get(url,timeout=cfg.timeout);r.raise_for_status()
            except requests.RequestException as e:LOG.warning("[DISCOVER_FAIL] %s %s",url,str(e)[:150]);continue
            if "html" not in r.headers.get("Content-Type","").lower():continue
            page_count+=1
            for item in adapter.extract_candidate_documents(r.url,r.text):
                u=item["document_url"]
                if u in seen:continue
                row=make_candidate(src,r.url,item);found.append(row);seen.add(u);new_count+=1;total_new+=1
                if limit is not None and total_new>=limit:break
            if limit is not None and total_new>=limit:break
            if depth<cfg.max_depth:
                for anchor in extract_links(r.text):
                    if not anchor.get("href"):continue
                    u=urljoin(r.url,anchor["href"])
                    path_part=urlparse(u).path.lower()
                    is_file=path_part.endswith((".pdf",".doc",".docx",".zip",".xls",".xlsx"))
                    listing=same_domain(r.url,u) and allowed_path(u,PAGE_TERMS) and not is_file
                    page=pagination_link(anchor,r.url,src["tender_url"])
                    if (listing or page) and not is_file and u not in visited:queue.append((u,depth+1))
            time.sleep(cfg.domain_delay)
        LOG.info("[DISCOVER] %s pages=%d new_candidates=%d",src["source_id"],page_count,new_count)
        if limit is not None and total_new>=limit:break
    merged=merge_candidates(old,found);save_candidates(path,merged)
    print(f"Discovered {len(found)} new candidates; registry now has {len(merged)}")

def source_by_id(cfg):return {r["source_id"]:r for r in read_csv(cfg.data_dir/"sources.csv")}
def reason_for(status, detail):
    if status=="ACCESS_RESTRICTED":return "ACCESS_RESTRICTED"
    if status=="REJECTED_DUPLICATE":return "EXACT_DUPLICATE"
    if status=="REJECTED_INVALID":return "HTML_NOT_PDF" if "signature" in detail.lower() else ("OVERSIZED" if "size" in detail.lower() else "INVALID_PDF")
    if status=="FAILED_PERMANENT":return "DOWNLOAD_FAILED"
    if status=="REJECTED_NOTICE":return "NOTICE_ONLY"
    if status=="REJECTED_NOT_PROCUREMENT":return "NOT_PROCUREMENT"
    if status=="POSSIBLE_DUPLICATE":return "OTHER"
    return "OTHER"
def rejection_row(row,code,detail):
    return {"candidate_id":row.get("candidate_id",""),"source_id":row.get("source_id",""),"url":row.get("document_url",""),"reason_code":code,"reason_detail":detail,"timestamp":datetime.now(timezone.utc).isoformat()}

def download(cfg, limit=None, source_ids=None, dry_run=False, http=None):
    path=cfg.data_dir/"candidates.csv";rows=load_candidates(path);manifest_path=cfg.data_dir/"manifest.csv";manifest=read_csv(manifest_path)
    source_map=source_by_id(cfg);s=http or session(cfg);accepted=0;processed=0;new_rejections=[];known=list(manifest)
    for seed in read_csv(cfg.data_dir/"seed_inventory.csv") if (cfg.data_dir/"seed_inventory.csv").exists() else []:
        if seed.get("sha256"):known.append({"sha256":seed["sha256"],"document_id":"SEED-"+seed.get("sha256","")[:12],"content_simhash":seed.get("content_simhash")})
    for row in rows:
        if row.get("download_status") not in ("QUEUED","FAILED_TRANSIENT"):continue
        if source_ids and row.get("source_id") not in source_ids:continue
        if limit is not None and processed>=limit:break
        if dry_run:print(f"[WOULD_DOWNLOAD] {row['candidate_id']} {row['document_url']}");continue
        processed+=1;url=row["document_url"];tmp=cfg.raw_dir/(row["candidate_id"]+".part");cfg.raw_dir.mkdir(parents=True,exist_ok=True)
        if not robots_allowed(s,url,cfg):row.update(download_status="ACCESS_RESTRICTED",quality_status="REJECT",notes="robots.txt disallows retrieval");new_rejections.append(rejection_row(row,"ACCESS_RESTRICTED",row["notes"]));save_candidates(path,rows);continue
        terminal=False
        for attempt in range(cfg.retries+1):
            try:
                with s.get(url,stream=True,timeout=cfg.timeout,allow_redirects=True) as response:
                    if response.status_code in (403,401):raise PermissionError(f"HTTP {response.status_code}")
                    if response.status_code==404:
                        row.update(download_status="FAILED_PERMANENT",quality_status="REJECT",notes="HTTP 404")
                        new_rejections.append(rejection_row(row,"DOWNLOAD_FAILED","HTTP 404"));terminal=True;break
                    response.raise_for_status();declared=response.headers.get("Content-Length")
                    if declared and int(declared)>cfg.max_file_bytes:raise OverflowError("Content-Length exceeds configured maximum")
                    size=0;head=b""
                    with tmp.open("wb") as f:
                        for chunk in response.iter_content(65536):
                            if not chunk:continue
                            size+=len(chunk)
                            if size>cfg.max_file_bytes:raise OverflowError("download exceeds configured maximum")
                            if len(head)<8:head+=chunk[:8-len(head)]
                            f.write(chunk)
                    if declared and size!=int(declared):raise ValueError("download size differs from Content-Length")
                    if head[:5]!=b"%PDF-":raise ValueError("response signature is not PDF; possible HTML error")
                valid,pages,invalid_reason=validate_pdf(tmp)
                if not valid:raise ValueError(invalid_reason)
                digest=sha256(tmp);duplicate=exact_duplicate(digest,known)
                if duplicate:
                    row.update(download_status="REJECTED_DUPLICATE",quality_status="REJECT",sha256=digest,duplicate_of=duplicate.get("document_id",""),notes="Exact SHA-256 duplicate; canonical record retained")
                    tmp.unlink(missing_ok=True);new_rejections.append(rejection_row(row,"EXACT_DUPLICATE",row["notes"]));terminal=True;break
                prof=profile(tmp);role,likelihood,reasons=classify_document(row["document_filename"],prof["sample_text"],prof["page_count"],prof["native_text_available"])
                src=source_map.get(row["source_id"],{});scores=quality_scores(src.get("official")=="true",{**prof,"valid_pdf":True},bool(row.get("tender_page_url") and url),likelihood,role)
                sim=prof["content_simhash"];near=near_duplicate(sim,known)
                dossier=dossier_id_for(row["source_id"],row["tender_page_url"])
                if likelihood=="REJECT":row.update(download_status="REJECTED_NOT_PROCUREMENT",quality_status="REJECT",document_role=role,cdc_likelihood=likelihood,notes=";".join(reasons));tmp.unlink(missing_ok=True);new_rejections.append(rejection_row(row,"NOT_PROCUREMENT",row["notes"]));terminal=True;break
                if role=="NOTICE" and likelihood=="RELATED_TENDER_DOCUMENT":row.update(download_status="REJECTED_NOTICE",quality_status="REJECT",document_role=role,cdc_likelihood=likelihood,notes=";".join(reasons));tmp.unlink(missing_ok=True);new_rejections.append(rejection_row(row,"NOTICE_ONLY",row["notes"]));terminal=True;break
                stem=safe_name(Path(urlparse(url).path).stem or row["tender_title"]);fname=f"CDC-{len(manifest)+1:04d}__{safe_name(row['source_id'])}__{stem[:65]}.pdf";dest=cfg.raw_dir/fname
                while dest.exists():dest=cfg.raw_dir/(dest.stem+"-"+digest[:8]+".pdf")
                os.replace(tmp,dest)
                status="POSSIBLE_DUPLICATE" if near else ("ACCEPT" if likelihood=="LIKELY_CDC" else "REVIEW")
                row.update(download_status="VALIDATED",quality_status=status,document_role=role,cdc_likelihood=likelihood,classification_reasons=";".join(reasons),sha256=digest,content_simhash=sim or "",near_duplicate_status="POSSIBLE_NEAR_DUPLICATE" if near else prof["near_duplicate_status"],duplicate_of=near.get("document_id","") if near else "",relative_path=dest.relative_to(ROOT).as_posix(),page_count=prof["page_count"],file_size_bytes=size,native_text_available=prof["native_text_available"],likely_scanned=prof["likely_scanned"],language_hint=prof["language_hint"],title_hint=prof["title_hint"],acquisition_quality=scores["acquisition_quality"],benchmark_value=scores["benchmark_value"],review_status="PENDING_HUMAN_REVIEW")
                if status=="ACCEPT":
                    docid=f"CDC-{len(manifest)+1:04d}";row["document_id"]=docid;row["dossier_id"]=dossier;row["document_type"]=role
                    record={"document_id":docid,"dossier_id":dossier,"sha256":digest,"content_simhash":sim or "","filename":fname,"relative_path":row["relative_path"],"source_id":row["source_id"],"organization":row["organization"],"organization_type":src.get("organization_type",""),"source_page_url":row["tender_page_url"],"download_url":url,"title":prof["title_hint"] or row["tender_title"],"reference":row.get("tender_reference",""),"publication_date":row.get("publication_date",""),"deadline":row.get("deadline",""),"source_procurement_type":row.get("source_procurement_type",""),"normalized_procurement_type":row.get("normalized_procurement_type","UNKNOWN"),"document_type":role,"cdc_likelihood":likelihood,"language_hint":prof["language_hint"],"page_count":prof["page_count"],"file_size_bytes":size,"native_text_available":prof["native_text_available"],"likely_scanned":prof["likely_scanned"],"acquisition_quality":scores["acquisition_quality"],"benchmark_value":scores["benchmark_value"],"acquisition_quality_tier":"HIGH" if scores["acquisition_quality"]>=80 else "MEDIUM" if scores["acquisition_quality"]>=60 else "LOW","downloaded_at":datetime.now(timezone.utc).isoformat(),"license_or_access_note":"Publicly linked document; source terms apply","review_status":"PENDING_HUMAN_REVIEW","near_duplicate_status":prof["near_duplicate_status"],"notes":""}
                    metadata_path=ROOT/"datasets/cdc_real/metadata"/(docid+".json");metadata_path.parent.mkdir(parents=True,exist_ok=True)
                    metadata_path.write_text(json.dumps({"document_id":docid,"dossier_id":dossier,"source":{"source_id":row["source_id"],"organization":row["organization"],"page_url":row["tender_page_url"],"download_url":url},"file":{"filename":fname,"original_filename":row["document_filename"],"sha256":digest,"pages":prof["page_count"],"size_bytes":size},"classification":{"document_type":role,"cdc_likelihood":likelihood,"procurement_type":row["normalized_procurement_type"]},"quality":scores,"acquisition":{"method":row["discovery_method"],"timestamp":datetime.now(timezone.utc).isoformat()}},ensure_ascii=False,indent=2),encoding="utf-8")
                    manifest.append(record);known.append(record);accepted+=1
                else:
                    known.append({"document_id":row["candidate_id"],"content_simhash":sim or "","sha256":digest})
                    if status=="POSSIBLE_DUPLICATE":new_rejections.append(rejection_row(row,"OTHER",row["notes"] or "Possible near duplicate; retained for human review"))
                terminal=True;break
            except PermissionError as exc:row.update(download_status="ACCESS_RESTRICTED",quality_status="REJECT",notes=str(exc));new_rejections.append(rejection_row(row,"ACCESS_RESTRICTED",str(exc)));tmp.unlink(missing_ok=True);terminal=True;break
            except OverflowError as exc:row.update(download_status="REJECTED_INVALID",quality_status="REJECT",notes=str(exc));new_rejections.append(rejection_row(row,"OVERSIZED",str(exc)));tmp.unlink(missing_ok=True);terminal=True;break
            except ValueError as exc:row.update(download_status="REJECTED_INVALID",quality_status="REJECT",notes=str(exc));new_rejections.append(rejection_row(row,"HTML_NOT_PDF" if "signature" in str(exc) else "INVALID_PDF",str(exc)));tmp.unlink(missing_ok=True);terminal=True;break
            except requests.RequestException as exc:
                tmp.unlink(missing_ok=True)
                if attempt>=cfg.retries:row.update(download_status="FAILED_TRANSIENT",quality_status="REVIEW",notes=str(exc)[:200]);new_rejections.append(rejection_row(row,"DOWNLOAD_FAILED",str(exc)[:200]));terminal=True;break
                time.sleep(min(2**attempt,8))
        if not terminal and row.get("download_status")=="QUEUED":row.update(download_status="FAILED_TRANSIENT",quality_status="REVIEW",notes="download interrupted")
        save_candidates(path,rows);write_manifest(manifest_path,manifest);append_rejections(cfg.data_dir/"rejected.csv",new_rejections)
        new_rejections.clear();time.sleep(cfg.domain_delay)
        if row.get("download_status")=="VALIDATED":LOG.info("[VALIDATE] %s pages=%s role=%s",row["candidate_id"],row.get("page_count"),row.get("document_role"))
    print(f"Processed={processed}; accepted={accepted}; manifest={len(manifest)}")
def report(cfg):
    rows=read_csv(cfg.data_dir/"manifest.csv");dims=corpus_dimensions(rows)
    (cfg.data_dir/"corpus_stats.json").write_text(json.dumps({"total_documents":len(rows),"dimensions":dims},indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Acquired corpus diversity report","",f"Manifest documents: {len(rows)}","","## Concentration distributions",""]
    total=max(1,len(rows))
    for field,counts in dims.items():
        lines.append(f"### {field}")
        lines.extend([f"- {k}: {v} ({v/total:.0%})" for k,v in sorted(counts.items())]);lines.append("")
        if counts:
            key,count=max(counts.items(),key=lambda x:x[1])
            if count/total>0.60:lines.append(f"WARNING: {count/total:.0%} of corpus is {key} in {field}.")
    (cfg.data_dir/"corpus_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8");print(f"Wrote report for {len(rows)} documents")

def main():
    p=argparse.ArgumentParser(prog="python -m tools.tender_scraper");sub=p.add_subparsers(dest="cmd",required=True);s=sub.add_parser("sources");s.add_subparsers(dest="source_cmd",required=True).add_parser("validate")
    for name in ("discover","download","run"):
        q=sub.add_parser(name);q.add_argument("--source",action="append");q.add_argument("--limit",type=int);q.add_argument("--dry-run",action="store_true")
    sub.add_parser("report");sub.add_parser("validate");a=p.parse_args();logging.basicConfig(level=logging.INFO,format="%(message)s");cfg=Config()
    if a.cmd=="sources":sources_validate(cfg)
    elif a.cmd=="discover":discover(cfg,a.source,a.limit)
    elif a.cmd=="download":download(cfg,a.limit,a.source,a.dry_run)
    elif a.cmd=="run":discover(cfg,a.source,a.limit);download(cfg,a.limit,a.source,a.dry_run);report(cfg)
    elif a.cmd=="validate":
        rows=read_csv(cfg.data_dir/"manifest.csv");errors=[]
        for row in rows:
            f=ROOT/row["relative_path"]
            try:
                if not f.read_bytes().startswith(b"%PDF-"):raise ValueError("bad signature")
                with __import__("fitz").open(f) as doc:
                    if not len(doc):raise ValueError("empty PDF")
            except Exception as exc:errors.append(f"{row.get('document_id')}: {exc}")
        print(f"Validated {len(rows)-len(errors)}/{len(rows)} manifest PDFs")
        if errors:raise SystemExit("\n".join(errors))
    elif a.cmd=="report":report(cfg)
if __name__=="__main__":main()
