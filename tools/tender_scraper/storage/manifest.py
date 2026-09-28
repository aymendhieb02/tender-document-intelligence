import csv
from pathlib import Path
from ..validation.document import text_simhash

MANIFEST_FIELDS="document_id dossier_id sha256 content_simhash filename relative_path source_id organization organization_type source_page_url download_url title reference publication_date deadline source_procurement_type normalized_procurement_type document_type cdc_likelihood language_hint page_count file_size_bytes native_text_available likely_scanned acquisition_quality benchmark_value acquisition_quality_tier downloaded_at license_or_access_note review_status near_duplicate_status notes".split()
REJECTED_FIELDS=["candidate_id","source_id","url","reason_code","reason_detail","timestamp"]
def read_csv(path):
    path=Path(path)
    if not path.exists(): return []
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write_csv(path,fields,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def exact_duplicate(sha256, records):
    if not sha256:return None
    return next((r for r in records if r.get("sha256")==sha256),None)
def near_duplicate(simhash, records, max_distance=3):
    if not simhash:return None
    for r in records:
        other=r.get("content_simhash")
        if other:
            try:
                if (int(simhash,16)^int(other,16)).bit_count()<=max_distance:return r
            except ValueError:continue
    return None
def append_rejections(path, new_rows):
    old=read_csv(path);by_key={(r.get("candidate_id"),r.get("reason_code")):r for r in old}
    by_key.update({(r.get("candidate_id"),r.get("reason_code")):r for r in new_rows})
    write_csv(path,REJECTED_FIELDS,list(by_key.values()))
def merge_candidates(existing, discovered):
    """Preserve prior statuses and IDs; append only previously unseen document URLs."""
    out=list(existing); known={r.get("document_url") for r in existing}
    for row in discovered:
        if row.get("document_url") not in known:out.append(row);known.add(row.get("document_url"))
    return out
def write_manifest(path, rows):
    write_csv(path,MANIFEST_FIELDS,rows)
