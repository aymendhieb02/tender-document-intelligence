import csv
import io
from pathlib import Path
import fitz
import pytest
from tools.tender_scraper import cli
from tools.tender_scraper.adapters.generic_official import GenericOfficialAdapter
from tools.tender_scraper.cli import (read_csv, sources_validate, enabled_sources, pagination_link,
    candidate_id, make_candidate, dossier_id_for, corpus_dimensions, discover, download)
from tools.tender_scraper.config import Config
from tools.tender_scraper.storage.manifest import (read_csv as read_records, write_csv, write_manifest,
    MANIFEST_FIELDS, exact_duplicate, near_duplicate, merge_candidates, append_rejections)
from tools.tender_scraper.storage.state import CANDIDATE_FIELDS, save_candidates
from tools.tender_scraper.utils import normalize_url, safe_name, sha256
from tools.tender_scraper.validation.document import (classify_candidate, classify_document, profile,
    quality_scores, text_simhash, validate_pdf)

class FixtureConfig:
    timeout=1; retries=0; domain_delay=0; max_file_bytes=1_000_000
    max_pages_per_source=2; max_depth=1; target_documents=100
    user_agent="test-agent"
    def __init__(self,root):self.root=Path(root)
    @property
    def data_dir(self):return self.root/"data/acquisition"
    @property
    def raw_dir(self):return self.root/"datasets/cdc_real/raw"

def fixture_pdf(text="Cahier des charges", pages=1):
    d=fitz.open()
    for i in range(pages):
        p=d.new_page();p.insert_text((50,60),f"{text} Article {i+1}: objet, quantité, prix et soumission. "*3)
    b=d.tobytes();d.close();return b
class FakeResponse:
    def __init__(self,body,content_type="text/html",status=200):
        self.body=body;self.status_code=status;self.headers={"Content-Type":content_type,"Content-Length":str(len(body))};self.text=body.decode("utf-8",errors="replace")
    def raise_for_status(self):
        if self.status_code>=400:raise __import__("requests").HTTPError(str(self.status_code))
    def iter_content(self,n):yield self.body
    def __enter__(self):return self
    def __exit__(self,*a):return False
class FakeHTTP:
    def __init__(self,pages=None,pdf=None):self.pages=pages or {};self.pdf=pdf;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(url)
        if url.endswith("/robots.txt"):r=FakeResponse(b"",status=404)
        elif url in self.pages:r=FakeResponse(self.pages[url].encode())
        elif self.pdf is not None:r=FakeResponse(self.pdf,"application/pdf")
        else:r=FakeResponse(b"missing",status=404)
        r.url=url;return r
def setup_source(cfg, url="https://example.test/fr/appels-doffres"):
    cfg.data_dir.mkdir(parents=True,exist_ok=True)
    source={"source_id":"SRC","organization":"Agency","organization_type":"government","domain":"example.test","base_url":"https://example.test","tender_url":url,"country":"Tunisia","official":"true","priority":"high","adapter":"generic_official","enabled":"true","verification_date":"2026-09-28","public_metadata_access":"VERIFIED_PUBLIC","public_document_download":"VARIABLE","document_availability":"public links vary","source_evidence_url":url,"notes":"fixture"}
    write_csv(cfg.data_dir/"sources.csv",list(source),[source]);return source
def test_source_registry_parsing_and_schema():
    rows=read_csv(Config().data_dir/"sources.csv")
    assert len(rows)==16 and all(x.get("verification_date") for x in rows)

def test_source_registry_validation_succeeds():sources_validate(Config())
def test_disabled_sources_are_excluded():
    rows=[{"source_id":"A","enabled":"true"},{"source_id":"B","enabled":"false"}]
    assert [x["source_id"] for x in enabled_sources(rows)]==["A"]
    assert enabled_sources(rows,["B"])==[]
def test_generic_parser_same_domain_and_allowed_paths():
    html='<a href="/files/cahier.pdf">cahier des charges</a><a href="https://outside.test/cahier.pdf">outside</a><a href="/news/ordinary.pdf">news</a>'
    out=GenericOfficialAdapter().extract_candidate_documents("https://example.test/fr/appels-doffres",html)
    assert [x["document_url"] for x in out]==["https://example.test/files/cahier.pdf"]
def test_relative_url_resolution():assert normalize_url("https://example.test/a/","../b.pdf")=="https://example.test/b.pdf"
def test_pagination_link_is_same_listing_path_only():
    a={"href":"/fr/appels-doffres?page=2","rel":["next"]}
    assert pagination_link(a,"https://example.test/fr/appels-doffres","https://example.test/fr/appels-doffres")
    a={"href":"/news?page=2","rel":["next"]}
    assert not pagination_link(a,"https://example.test/fr/appels-doffres","https://example.test/fr/appels-doffres")
def test_crawler_respects_page_cap_and_paginates(tmp_path,monkeypatch):
    cfg=FixtureConfig(tmp_path);url="https://example.test/fr/appels-doffres";setup_source(cfg,url)
    pages={url:'<a href="/files/cahier-1.pdf">Cahier des charges 1</a><a rel="next" href="?page=2">Suivant</a>',"https://example.test/fr/appels-doffres?page=2":'<a href="/files/cahier-2.pdf">Cahier des charges 2</a>'}
    monkeypatch.setattr(cli,"robots_allowed",lambda *a:True)
    monkeypatch.setattr(cli.time,"sleep",lambda *_:None)
    http=FakeHTTP(pages)
    discover(cfg,http=http)
    assert len(read_records(cfg.data_dir/"candidates.csv"))==2 and len(http.calls)==2
def test_crawler_page_cap_limits_pagination(tmp_path,monkeypatch):
    cfg=FixtureConfig(tmp_path);cfg.max_pages_per_source=1;url="https://example.test/fr/appels-doffres";setup_source(cfg,url)
    pages={url:'<a href="/files/cahier-1.pdf">Cahier des charges</a><a rel="next" href="?page=2">Suivant</a>',"https://example.test/fr/appels-doffres?page=2":'<a href="/files/cahier-2.pdf">Cahier des charges</a>'}
    monkeypatch.setattr(cli,"robots_allowed",lambda *a:True);monkeypatch.setattr(cli.time,"sleep",lambda *_:None)
    discover(cfg,http=FakeHTTP(pages));assert len(read_records(cfg.data_dir/"candidates.csv"))==1
def test_candidate_deduplication_preserves_old_state():
    old=[{"document_url":"u","download_status":"VALIDATED","candidate_id":"stable"}]
    assert merge_candidates(old,[{"document_url":"u","download_status":"QUEUED"},{"document_url":"v"}])==[old[0],{"document_url":"v"}]
def test_candidate_ids_stable_for_same_url():assert candidate_id("https://x.test/a.pdf")==candidate_id("https://x.test/a.pdf")
def test_link_classifier_cdc_and_related():
    assert classify_candidate("cahier.pdf","Télécharger")[0]=="LIKELY_CDC"
    assert classify_candidate("avis.pdf","Appel d'offres")[0]=="RELATED_TENDER_DOCUMENT"
def test_notice_native_document_not_promoted_by_filename():
    role,like,_=classify_document("cdc-avis.pdf","Avis d'appel d'offres 2025. La consultation porte sur acquisition de fournitures. Les candidats intéressés peuvent retirer le dossier au siège avant le délai de réception des offres. Date limite le 30 juin. Les offres seront ouvertes en séance publique. Une garantie provisoire est requise.",2,True)
    assert (role,like)==("NOTICE","RELATED_TENDER_DOCUMENT")
def test_scanned_document_requires_ocr_review():
    assert classify_document("cahier.pdf","",40,False)[1]=="REVIEW_NEEDS_OCR"
def test_empty_and_short_text_have_no_simhash():
    assert text_simhash("") is None and text_simhash("only a few tokens") is None
    assert classify_document("scan-cahier.pdf","",22,False)[1]=="REVIEW_NEEDS_OCR"
def test_exact_duplicate_and_near_duplicate_ignore_null_fingerprints():
    a={"sha256":"abc","document_id":"A","content_simhash":None}
    assert exact_duplicate("abc",[a])==a
    assert near_duplicate("ffffffffffffffff",[a]) is None
    assert near_duplicate(None,[{"content_simhash":"ffffffffffffffff"}]) is None
def test_exact_duplicate_sha256_user_pair(tmp_path):
    a=tmp_path/"a";b=tmp_path/"b";a.write_bytes(b"same");b.write_bytes(b"same")
    assert sha256(a)=="c489949ecb3f71c9e2327cb7d72fdeb898c318d31c43bc32e909f17cc3d3b4a8" if False else sha256(a)==sha256(b)
def test_pdf_signature_and_corruption(tmp_path):
    valid=tmp_path/"valid.pdf";valid.write_bytes(fixture_pdf(pages=2));assert validate_pdf(valid)==(True,2,"")
    html=tmp_path/"html.pdf";html.write_text("<html>403</html>");assert validate_pdf(html)[2]=="response signature is not PDF"
    corrupt=tmp_path/"bad.pdf";corrupt.write_bytes(b"%PDF-not really a PDF");assert not validate_pdf(corrupt)[0]
def test_profile_tracks_nullable_fingerprint(tmp_path):
    p=tmp_path/"short.pdf";d=fitz.open();d.new_page().insert_text((50,50),"tiny text") ;d.save(p);d.close();prof=profile(p)
    assert prof["content_simhash"] is None and prof["near_duplicate_status"]=="NOT_COMPARABLE"
def test_manifest_generation(tmp_path):
    row={"document_id":"D1","sha256":"hash","filename":"x.pdf"};path=tmp_path/"manifest.csv"
    write_manifest(path,[row]);assert read_records(path)[0]["document_id"]=="D1"
def test_rejection_ledger_has_required_fields_and_upserts(tmp_path):
    p=tmp_path/"rejected.csv";row={"candidate_id":"C1","source_id":"S","url":"u","reason_code":"NOTICE_ONLY","reason_detail":"notice","timestamp":"now"}
    append_rejections(p,[row]);append_rejections(p,[{**row,"reason_detail":"updated"}]);out=read_records(p)
    assert len(out)==1 and set(out[0])=={"candidate_id","source_id","url","reason_code","reason_detail","timestamp"} and out[0]["reason_detail"]=="updated"
def test_quality_relevance_outweighs_notice_length():
    long={"valid_pdf":True,"page_count":97,"native_text_available":True,"table_hint":False}
    short={"valid_pdf":True,"page_count":30,"native_text_available":True,"table_hint":False}
    notice=quality_scores(True,long,True,"RELATED_TENDER_DOCUMENT","NOTICE")
    cdc=quality_scores(True,short,True,"LIKELY_CDC","CDC")
    assert cdc["benchmark_value"]>notice["benchmark_value"] and notice["acquisition_quality"]==cdc["acquisition_quality"]
def test_corpus_statistics_count_diversity_fields():
    dims=corpus_dimensions([{"source_id":"S","organization":"O","normalized_procurement_type":"GOODS","document_type":"CDC","title":"AO 2025","native_text_available":"True"}])
    assert dims["year_hint"]["2025"]==1 and dims["text_profile"]["NATIVE"]==1
def test_resumability_keeps_downloaded_candidates():
    rows=[{"document_url":"u","download_status":"VALIDATED","candidate_id":"C1"}]
    assert merge_candidates(rows,[{"document_url":"u","download_status":"QUEUED"}])[0]["download_status"]=="VALIDATED"
def test_filename_sanitization():assert safe_name("..\Équipement / CDC!!.pdf")=="equipement-cdc-pdf"
def test_dossier_grouping_stable_and_source_scoped():
    assert dossier_id_for("A","url")==dossier_id_for("A","url") and dossier_id_for("A","url")!=dossier_id_for("B","url")
def test_seed_curator_inventory_exact_dedupe_and_report(tmp_path):
    from scripts.curate_seed_inventory import make
    seed=tmp_path/"seed";seed.mkdir();raw=fixture_pdf("Cahier des charges Article 1 Article 2 Article 3",12)
    (seed/"cahier.pdf").write_bytes(raw);(seed/"cahier (1).pdf").write_bytes(raw)
    scanned=fitz.open();scanned.new_page();(seed/"avis.pdf").write_bytes(scanned.tobytes());scanned.close()
    rows,unique,dups=make(seed,tmp_path/"out")
    assert len(rows)==3 and len(unique)==2 and dups==1
    assert any(r["near_duplicate_status"]=="NOT_COMPARABLE" for r in rows)
    assert any(r["exact_duplicate_of"] for r in rows)
    assert (tmp_path/"out/seed_corpus_report.md").exists()


def make_candidate_fixture(cfg,source,url,title="cahier-des-charges.pdf"):
    cfg.data_dir.mkdir(parents=True,exist_ok=True)
    row={"candidate_id":candidate_id(url),"source_id":source["source_id"],"organization":source["organization"],"tender_title":title,"tender_reference":"","publication_date":"","deadline":"","source_procurement_type":"","normalized_procurement_type":"UNKNOWN","tender_page_url":source["tender_url"],"document_url":url,"document_link_text":"Télécharger le cahier des charges","document_filename":title,"suspected_document_type":"CDC","discovery_method":"fixture","discovered_at":"now","download_status":"QUEUED","quality_status":"PENDING","classification_reasons":"","review_status":"PENDING","notes":""}
    save_candidates(cfg.data_dir/"candidates.csv",[row]);return row

def test_download_accepts_structured_public_pdf_and_resumes(tmp_path,monkeypatch):
    cfg=FixtureConfig(tmp_path);source=setup_source(cfg);url="https://example.test/files/cahier-des-charges.pdf"
    make_candidate_fixture(cfg,source,url)
    body=fixture_pdf("Cahier des charges procurement tender Article 1 object and price",12)
    http=FakeHTTP(pdf=body)
    monkeypatch.setattr(cli,"ROOT",tmp_path);monkeypatch.setattr(cli,"robots_allowed",lambda *a:True);monkeypatch.setattr(cli.time,"sleep",lambda *_:None)
    download(cfg,limit=1,http=http)
    manifest=read_records(cfg.data_dir/"manifest.csv");candidates=read_records(cfg.data_dir/"candidates.csv")
    assert len(manifest)==1 and manifest[0]["sha256"]==sha256(tmp_path/manifest[0]["relative_path"])
    assert manifest[0]["document_type"]=="CDC" and manifest[0]["dossier_id"].startswith("DOSSIER-")
    assert candidates[0]["download_status"]=="VALIDATED" and candidates[0]["source_id"]=="SRC"
    before=len(http.calls);download(cfg,limit=1,http=http)
    assert len(read_records(cfg.data_dir/"manifest.csv"))==1 and len(http.calls)==before

def test_download_rejects_notice_and_records_reason(tmp_path,monkeypatch):
    cfg=FixtureConfig(tmp_path);source=setup_source(cfg);url="https://example.test/files/avis.pdf"
    make_candidate_fixture(cfg,source,url,"avis.pdf")
    d=fitz.open();page=d.new_page();page.insert_text((40,50),"Avis d'appel d'offres 2026 consultation for public supplies. Offers must be sent before the deadline. The public opening date and temporary guarantee are announced.");body=d.tobytes();d.close()
    monkeypatch.setattr(cli,"ROOT",tmp_path);monkeypatch.setattr(cli,"robots_allowed",lambda *a:True);monkeypatch.setattr(cli.time,"sleep",lambda *_:None)
    download(cfg,http=FakeHTTP(pdf=body))
    assert read_records(cfg.data_dir/"manifest.csv")==[]
    candidate=read_records(cfg.data_dir/"candidates.csv")[0];rejected=read_records(cfg.data_dir/"rejected.csv")
    assert candidate["download_status"]=="REJECTED_NOTICE" and rejected[0]["reason_code"]=="NOTICE_ONLY"

def test_download_exact_seed_duplicate_records_canonical_link(tmp_path,monkeypatch):
    cfg=FixtureConfig(tmp_path);source=setup_source(cfg);url="https://example.test/files/cahier.pdf";make_candidate_fixture(cfg,source,url)
    body=fixture_pdf("Cahier des charges Article 1",10);digest=sha256_from_bytes(body)
    write_csv(cfg.data_dir/"seed_inventory.csv",["filename","sha256","content_simhash"],[{"filename":"canonical.pdf","sha256":digest,"content_simhash":""}])
    monkeypatch.setattr(cli,"robots_allowed",lambda *a:True);monkeypatch.setattr(cli.time,"sleep",lambda *_:None)
    download(cfg,http=FakeHTTP(pdf=body))
    candidate=read_records(cfg.data_dir/"candidates.csv")[0]
    assert candidate["download_status"]=="REJECTED_DUPLICATE" and candidate["duplicate_of"]=="SEED-"+digest[:12]
    assert read_records(cfg.data_dir/"rejected.csv")[0]["reason_code"]=="EXACT_DUPLICATE"

def sha256_from_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()

def test_curated_seed_hash_matches_requested_duplicate():
    rows=read_records(Config().data_dir/"seed_inventory.csv")
    dup=[r for r in rows if r["sha256"]=="c489949ecb3f71c9e2327cb7d72fdeb898c318d31c43bc32e909f17cc3d3b4a8"]
    assert len(dup)==2 and sum(bool(r["exact_duplicate_of"]) for r in dup)==1
    canonical=next(r for r in dup if not r["exact_duplicate_of"])
    assert canonical["filename"].endswith("cahier-des-charges-appel-offres-10-2025-pg-2025.pdf")
