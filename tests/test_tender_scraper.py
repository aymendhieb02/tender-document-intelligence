import csv
from pathlib import Path
import fitz
from tools.tender_scraper.adapters.generic_official import GenericOfficialAdapter
from tools.tender_scraper.cli import read_csv, sources_validate
from tools.tender_scraper.validation.document import classify, profile, quality
from tools.tender_scraper.utils import normalize_url, safe_name, sha256

def test_sources_registry_and_official_flags():
 rows=read_csv(Path("data/acquisition/sources.csv"))
 assert len(rows)>=4 and all(r["official"]=="true" for r in rows)

def test_relative_link_and_bounded_generic_extraction():
 html='<a href="../files/cahier.pdf">Télécharger le cahier des charges</a><a href="https://outside.test/cahier.pdf">outside</a>'
 out=GenericOfficialAdapter().extract_candidate_documents("https://example.tn/fr/appels-doffres",html)
 assert len(out)==1 and out[0]["document_url"]=="https://example.tn/files/cahier.pdf"
 assert normalize_url("https://example.tn/a/","../b.pdf")=="https://example.tn/b.pdf"

def test_candidate_classification_and_safe_filename():
 assert classify("cahier.pdf","download")[0]=="LIKELY_CDC"
 assert classify("avis.pdf","appel d'offres")[0]=="RELATED_TENDER_DOCUMENT"
 assert safe_name("..\Étude / CDC!!.pdf")=="etude-cdc-pdf"

def test_pdf_profile_hash_and_quality(tmp_path):
 p=tmp_path/"sample.pdf"
 doc=fitz.open();page=doc.new_page();page.insert_text((72,72),"Cahier des charges\nQuantité Prix Total "*10);doc.save(p);doc.close()
 assert p.read_bytes().startswith(b"%PDF-")
 assert len(sha256(p))==64
 prof=profile(p);assert prof["page_count"]==1 and prof["native_text_available"]
 assert quality(True,"LIKELY_CDC",prof)>quality(True,"UNKNOWN",prof)

def test_html_masquerading_as_pdf_rejected_by_signature(tmp_path):
 p=tmp_path/"fake.pdf";p.write_text("<html>403</html>")
 assert not p.read_bytes().startswith(b"%PDF-")
