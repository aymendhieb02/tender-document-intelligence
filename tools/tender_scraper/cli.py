import argparse, csv, json, logging, os, re, time, urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from .config import Config, ROOT
from .adapters.generic_official import GenericOfficialAdapter
from .adapters.pm_tn import PresidencyAdapter
from .adapters.mtc_gov_tn import MtcAdapter
from .adapters.marchespublics import HaicopAdapter
from .adapters.tuneps import TunepsAdapter
from .validation.document import classify, profile, procurement, document_type, quality
from .utils import safe_name, sha256

LOG=logging.getLogger("tender_scraper")
FIELDS="candidate_id source_id organization tender_title tender_reference publication_date deadline source_procurement_type normalized_procurement_type tender_page_url document_url document_link_text document_filename suspected_document_type discovery_method discovered_at download_status quality_status classification_reasons sha256 relative_path page_count file_size_bytes native_text_available likely_scanned language_hint title_hint quality_score quality_tier review_status notes".split()
def read_csv(path):
 with open(path,encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(path, fields, rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with open(path,"w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def session(config):
 s=requests.Session(); s.headers.update({"User-Agent":config.user_agent,"Accept":"text/html,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,*/*;q=0.7"});return s
def robots_allowed(s,url,config):
 robots=urlparse(url)._replace(path="/robots.txt",query="",fragment="").geturl()
 try:
  r=s.get(robots,timeout=config.timeout); r.raise_for_status(); rp=urllib.robotparser.RobotFileParser();rp.parse(r.text.splitlines());return rp.can_fetch(config.user_agent,url)
 except requests.RequestException as exc:
  if getattr(getattr(exc,"response",None),"status_code",None) in (404,410):return True
  LOG.warning("robots.txt unavailable for %s; skipping URL conservatively",url);return False
def sources_validate(cfg):
 sources=read_csv(cfg.data_dir/"sources.csv"); errors=[]
 for row in sources:
  for key in ("source_id","organization","domain","base_url","tender_url","adapter"):
   if not row.get(key):errors.append(f"{row.get('source_id','?')}: missing {key}")
  if row.get("enabled")=="true" and row.get("official")!="true":errors.append(f"{row.get('source_id')}: enabled source not marked official")
 print(f"Sources: {len(sources)}; enabled: {sum(x.get('enabled')=='true' for x in sources)}")
 if errors: raise SystemExit("\n".join(errors))
def adapter_for(name):
 return {"pm_tn":PresidencyAdapter,"mtc_gov_tn":MtcAdapter,"marchespublics":HaicopAdapter,"tuneps":TunepsAdapter,"generic_official":GenericOfficialAdapter}.get(name,GenericOfficialAdapter)()
def discover(cfg, source_ids=None, limit=None):
 sources=[x for x in read_csv(cfg.data_dir/"sources.csv") if x["enabled"]=="true" and (not source_ids or x["source_id"] in source_ids)]
 s=session(cfg); rows=[]; seen=set(); n=0
 for src in sources:
  adapter=adapter_for(src["adapter"]); queue=[(src["tender_url"],0)]; visited=set(); count=0
  while queue and count<cfg.max_pages_per_source:
   url,depth=queue.pop(0)
   if url in visited or depth>cfg.max_depth:continue
   visited.add(url)
   if not robots_allowed(s,url,cfg):LOG.info("[ROBOTS_BLOCK] %s",url);continue
   try:r=s.get(url,timeout=cfg.timeout);r.raise_for_status()
   except requests.RequestException as e:LOG.warning("[DISCOVER_FAIL] %s %s",url,str(e)[:150]);continue
   if "html" not in r.headers.get("Content-Type","").lower(): continue
   count+=1
   for item in adapter.extract_candidate_documents(r.url,r.text):
    if item["document_url"] in seen:continue
    seen.add(item["document_url"]); cls=item["classification"]
    row={"candidate_id":"CAND-"+__import__("hashlib").sha256(item["document_url"].encode()).hexdigest()[:12].upper(),"source_id":src["source_id"],"organization":src["organization"],"tender_title":item["document_link_text"],"source_procurement_type":"","normalized_procurement_type":procurement(item["document_link_text"]),"tender_page_url":r.url,"document_url":item["document_url"],"document_link_text":item["document_link_text"],"document_filename":Path(urlparse(item["document_url"]).path).name,"suspected_document_type":("CDC" if cls=="LIKELY_CDC" else "UNKNOWN"),"discovery_method":"generic_html","discovered_at":datetime.now(timezone.utc).isoformat(),"download_status":"QUEUED","quality_status":"REVIEW" if cls!="LIKELY_CDC" else "PENDING","classification_reasons":item["classification_reasons"],"review_status":"PENDING","notes":""}
    rows.append(row); n+=1
    if limit and n>=limit:break
   if limit and n>=limit:break
   if depth<cfg.max_depth:
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    from .utils import same_domain,allowed_path
    for a in BeautifulSoup(r.text,"html.parser").find_all("a",href=True):
     u=urljoin(r.url,a["href"])
     if same_domain(r.url,u) and allowed_path(u,("tender","appel","consultation","marche","cahier","publication","avis","ao")) and u not in visited:queue.append((u,depth+1))
   time.sleep(cfg.domain_delay)
  LOG.info("[DISCOVER] %s pages=%d candidates=%d",src["source_id"],count,len(rows))
 old=read_csv(cfg.data_dir/"candidates.csv") if (cfg.data_dir/"candidates.csv").exists() else []
 byurl={x.get("document_url"):x for x in old};byurl.update({x["document_url"]:x for x in rows})
 write_csv(cfg.data_dir/"candidates.csv",FIELDS,list(byurl.values()));print(f"Discovered {len(rows)} new candidates; registry now has {len(byurl)}")
def download(cfg, limit=None, source_ids=None, dry_run=False):
 path=cfg.data_dir/"candidates.csv"; rows=read_csv(path) if path.exists() else [];s=session(cfg); existing={}
 manifest_path=cfg.data_dir/"manifest.csv"; manifest=read_csv(manifest_path) if manifest_path.exists() else []
 for m in manifest:
  existing[m.get("sha256")]=m
  if m.get("content_simhash"):existing["simhash:"+m["content_simhash"]]=m
 seed_path=cfg.data_dir/"seed_inventory.csv"
 if seed_path.exists():
  for seed in read_csv(seed_path):
   if seed.get("sha256"): existing[seed["sha256"]]={"document_id":"seed:"+seed.get("filename","")}
   if seed.get("content_simhash"): existing["simhash:"+seed["content_simhash"]]={"document_id":"seed:"+seed.get("filename","")}
 accepted=[]; changed=False
 for row in rows:
  if row.get("download_status") not in ("QUEUED","FAILED_TRANSIENT"):continue
  if source_ids and row.get("source_id") not in source_ids:continue
  if limit is not None and len(accepted)>=limit:break
  url=row["document_url"]
  if dry_run:print(f"[WOULD_DOWNLOAD] {row['candidate_id']} {url}");continue
  if not robots_allowed(s,url,cfg):row.update(download_status="ACCESS_RESTRICTED",quality_status="REJECT",notes="robots.txt disallows retrieval");changed=True;continue
  cfg.raw_dir.mkdir(parents=True,exist_ok=True);tmp=cfg.raw_dir/(row["candidate_id"]+".part")
  for attempt in range(cfg.retries+1):
   try:
    with s.get(url,stream=True,timeout=cfg.timeout,allow_redirects=True) as response:
     code=response.status_code
     if code in (403,404):row.update(download_status="ACCESS_RESTRICTED" if code==403 else "FAILED_PERMANENT",quality_status="REJECT",notes=f"HTTP {code}");break
     response.raise_for_status(); declared=response.headers.get("Content-Length")
     if declared and int(declared)>cfg.max_file_bytes:raise ValueError("Content-Length exceeds maximum file size")
     size=0; head=b""
     with open(tmp,"wb") as f:
      for chunk in response.iter_content(65536):
       if not chunk:continue
       size+=len(chunk)
       if size>cfg.max_file_bytes:raise ValueError("maximum file size exceeded")
       if len(head)<8:head+=chunk[:8-len(head)]
       f.write(chunk)
     if declared and size!=int(declared):raise ValueError("download size differs from Content-Length")
     if head[:5]!=b"%PDF-":raise ValueError("response is not a PDF (signature mismatch)")
     digest=sha256(tmp)
     if digest in existing:row.update(download_status="REJECTED_DUPLICATE",quality_status="REJECT",sha256=digest,notes="Exact SHA-256 duplicate of "+existing[digest].get("document_id","existing document"));tmp.unlink(missing_ok=True);break
     prof=profile(tmp)
     duplicate_of=next((v for k,v in existing.items() if k.startswith("simhash:") and (int(k[7:],16)^int(prof["content_simhash"],16)).bit_count()<=3),None)
     stem=safe_name(Path(urlparse(url).path).stem or row["tender_title"])
     fname=f"CDC-{len(manifest)+1:04d}__{safe_name(row['source_id'])}__{stem[:65]}.pdf"; dest=cfg.raw_dir/fname
     while dest.exists():dest=cfg.raw_dir/(dest.stem+"-"+digest[:8]+".pdf")
     os.replace(tmp,dest);prof=profile(dest);cls,_=classify(dest.name,row["document_link_text"],prof["title_hint"]);score=quality(True,cls,prof,duplicate=bool(duplicate_of))
     row.update(download_status="VALIDATED",quality_status="POSSIBLE_DUPLICATE" if duplicate_of else ("ACCEPT" if cls=="LIKELY_CDC" and prof["page_count"] else "REVIEW"),sha256=digest,content_simhash=prof["content_simhash"],relative_path=dest.relative_to(ROOT).as_posix(),page_count=prof["page_count"],file_size_bytes=size,native_text_available=prof["native_text_available"],likely_scanned=prof["likely_scanned"],language_hint=prof["language_hint"],title_hint=prof["title_hint"],quality_score=score,quality_tier="HIGH" if score>=75 else "MEDIUM" if score>=50 else "LOW",review_status="PENDING")
     if row["quality_status"]=="POSSIBLE_DUPLICATE":row["notes"]="Possible near-duplicate of "+duplicate_of.get("document_id","") if duplicate_of else "Possible near-duplicate"
     if row["quality_status"]=="ACCEPT":
      docid=f"CDC-{len(manifest)+1:04d}";row["document_id"]=docid;row["dossier_id"]="DOSSIER-"+__import__("hashlib").sha256((row["source_id"]+row["tender_page_url"]).encode()).hexdigest()[:12];row["document_type"]=document_type(prof["title_hint"]+" "+row["document_link_text"]);row["relative_path"]=dest.relative_to(ROOT).as_posix()
      metadata={"document_id":docid,"dossier_id":row["dossier_id"],"source":{"source_id":row["source_id"],"organization":row["organization"],"page_url":row["tender_page_url"],"download_url":url},"file":{"filename":fname,"original_filename":row["document_filename"],"sha256":digest,"pages":prof["page_count"],"size_bytes":size},"classification":{"document_type":row["document_type"],"procurement_type":row["normalized_procurement_type"]},"acquisition":{"method":"generic_html","timestamp":datetime.now(timezone.utc).isoformat()}}
      (ROOT/"datasets/cdc_real/metadata"/(docid+".json")).write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
      manifest.append({"document_id":docid,"dossier_id":row["dossier_id"],"sha256":digest,"filename":fname,"relative_path":row["relative_path"],"source_id":row["source_id"],"organization":row["organization"],"organization_type":next((x["organization_type"] for x in read_csv(cfg.data_dir/"sources.csv") if x["source_id"]==row["source_id"]),""),"source_page_url":row["tender_page_url"],"download_url":url,"title":prof["title_hint"] or row["tender_title"],"reference":"","publication_date":"","deadline":"","source_procurement_type":"","normalized_procurement_type":row["normalized_procurement_type"],"document_type":row["document_type"],"language_hint":prof["language_hint"],"page_count":prof["page_count"],"file_size_bytes":size,"native_text_available":prof["native_text_available"],"likely_scanned":prof["likely_scanned"],"quality_score":score,"quality_tier":row["quality_tier"],"downloaded_at":datetime.now(timezone.utc).isoformat(),"license_or_access_note":"Publicly linked document; source terms apply","review_status":"PENDING","notes":""});existing[digest]=manifest[-1];accepted.append(row)
     break
   except ValueError as e:row.update(download_status="REJECTED_INVALID",quality_status="REJECT",notes=str(e));tmp.unlink(missing_ok=True);break
   except requests.RequestException as e:
    tmp.unlink(missing_ok=True)
    if attempt>=cfg.retries:row.update(download_status="FAILED_TRANSIENT",quality_status="REVIEW",notes=str(e)[:200]);break
    time.sleep(min(2**attempt,8))
  changed=True
  write_csv(path,FIELDS,rows)
  manifest_fields=list(manifest[0].keys()) if manifest else "document_id dossier_id sha256 content_simhash filename relative_path source_id organization organization_type source_page_url download_url title reference publication_date deadline source_procurement_type normalized_procurement_type document_type language_hint page_count file_size_bytes native_text_available likely_scanned quality_score quality_tier downloaded_at license_or_access_note review_status notes".split()
  write_csv(manifest_path,manifest_fields,manifest)
  counts={}
  for item in rows:counts[item.get("download_status","")]=counts.get(item.get("download_status",""),0)+1
  (cfg.data_dir/"state.json").write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"candidate_status_counts":counts},indent=2),encoding="utf-8")
  time.sleep(cfg.domain_delay)
  if row.get("download_status")=="VALIDATED":LOG.info("[VALIDATE] %s pages=%s",row["candidate_id"],row.get("page_count"))
 if changed:
  write_csv(path,FIELDS,rows)
  manifest_fields=list(manifest[0].keys()) if manifest else "document_id dossier_id sha256 content_simhash filename relative_path source_id organization organization_type source_page_url download_url title reference publication_date deadline source_procurement_type normalized_procurement_type document_type language_hint page_count file_size_bytes native_text_available likely_scanned quality_score quality_tier downloaded_at license_or_access_note review_status notes".split()
  write_csv(manifest_path,manifest_fields,manifest)
  rejected=[dict(r,reason=r.get("notes",r.get("download_status","rejected"))) for r in rows if r.get("quality_status") in ("REJECT","POSSIBLE_DUPLICATE")]
  write_csv(cfg.data_dir/"rejected.csv",FIELDS+(["reason"] if "reason" not in FIELDS else []),rejected)
  counts={}
  for r in rows:counts[r.get("download_status","")]=counts.get(r.get("download_status",""),0)+1
  (cfg.data_dir/"state.json").write_text(json.dumps({"updated_at":datetime.now(timezone.utc).isoformat(),"candidate_status_counts":counts},indent=2),encoding="utf-8")
 print(f"Processed; accepted={len(accepted)} manifest={len(manifest)}")
def report(cfg):
 mp=cfg.data_dir/"manifest.csv"; rows=read_csv(mp) if mp.exists() else []
 dims={k:{} for k in ("source_id","organization","organization_type","normalized_procurement_type","document_type","language_hint","quality_tier")}
 for r in rows:
  for k in dims:
   v=r.get(k) or "UNKNOWN";dims[k][v]=dims[k].get(v,0)+1
 (cfg.data_dir/"corpus_stats.json").write_text(json.dumps({"total_documents":len(rows),"dimensions":dims},indent=2,ensure_ascii=False),encoding="utf-8")
 lines=["# Tunisian tender acquisition corpus report","",f"Documents in manifest: {len(rows)}","","## Diversity breakdown",""]
 for k,vals in dims.items():
  lines.extend([f"### {k}",""]+[f"- {name}: {count}" for name,count in sorted(vals.items())]+[""])
 if rows and len({x.get("organization") for x in rows})<3:lines.append("WARNING: fewer than three organizations represented.")
 if rows:
  total=len(rows)
  for dim in ("organization_type","normalized_procurement_type","source_id"):
   for value,count in dims[dim].items():
    if total and count/total>0.6:lines.append(f"WARNING: {dim}={value} represents {count/total:.0%} of the corpus.")
 (cfg.data_dir/"corpus_report.md").write_text("\n".join(lines),encoding="utf-8");print(f"Wrote report for {len(rows)} documents")
def main():
 p=argparse.ArgumentParser(prog="python -m tools.tender_scraper");sub=p.add_subparsers(dest="cmd",required=True);s=sub.add_parser("sources");s.add_subparsers(dest="source_cmd",required=True).add_parser("validate")
 for name in ("discover","download","run"):
  q=sub.add_parser(name);q.add_argument("--source",action="append");q.add_argument("--limit",type=int);q.add_argument("--dry-run",action="store_true")
 sub.add_parser("report");sub.add_parser("validate")
 a=p.parse_args();logging.basicConfig(level=logging.INFO,format="%(message)s");cfg=Config()
 if a.cmd=="sources":sources_validate(cfg)
 elif a.cmd=="discover":discover(cfg,a.source,a.limit)
 elif a.cmd=="download":download(cfg,a.limit,a.source,a.dry_run)
 elif a.cmd=="run":discover(cfg,a.source,a.limit);download(cfg,a.limit,a.source,a.dry_run);report(cfg)
 elif a.cmd=="validate":
  manifest=read_csv(cfg.data_dir/"manifest.csv") if (cfg.data_dir/"manifest.csv").exists() else []
  errors=[]
  for row in manifest:
   f=ROOT/row["relative_path"]
   try:
    if not f.read_bytes().startswith(b"%PDF-"): raise ValueError("bad signature")
    with __import__("fitz").open(f) as doc:
     if not len(doc): raise ValueError("empty PDF")
   except Exception as e: errors.append(f"{row.get('document_id')}: {e}")
  print(f"Validated {len(manifest)-len(errors)}/{len(manifest)} manifest PDFs")
  if errors: raise SystemExit("\n".join(errors))
 elif a.cmd=="report":report(cfg)
if __name__=="__main__":main()
