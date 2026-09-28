from urllib.parse import urljoin
from .base import SourceAdapter
from ..utils import same_domain, allowed_path, extract_links
from ..validation.document import classify
PREFIXES=("tender","procurement","appel","consultation","marche","marches","cahier","publication","avis","ao")
class GenericOfficialAdapter(SourceAdapter):
 def discover_listing_pages(self, source): return [source["tender_url"]]
 def discover_tenders(self, source): return self.discover_listing_pages(source)
 def extract_candidate_documents(self, page_url, html):
  out=[]
  for a in extract_links(html):
   if not a.get("href"):continue
   href=urljoin(page_url,a["href"]); label=a.get("text",""); path=href.lower()
   rel=a.get("rel","").lower(); query=__import__("urllib.parse",fromlist=["urlparse"]).urlparse(href).query.lower()
   if "next" in rel or label.lower() in ("next","suivant","›","»",">") or "page=" in query: continue
   if not same_domain(page_url,href): continue
   if not (path.endswith((".pdf",".doc",".docx",".zip")) or allowed_path(href,PREFIXES)): continue
   cls,reasons=classify(path,label)
   if cls=="UNKNOWN" and not allowed_path(href,PREFIXES): continue
   out.append({"document_url":href,"document_link_text":label,"classification":cls,"classification_reasons":";".join(reasons)})
  return out
