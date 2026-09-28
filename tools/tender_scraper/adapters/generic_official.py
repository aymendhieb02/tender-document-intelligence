from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .base import SourceAdapter
from ..utils import same_domain, allowed_path
from ..validation.document import classify
PREFIXES=("tender","procurement","appel","consultation","marche","marches","cahier","publication","avis","ao")
class GenericOfficialAdapter(SourceAdapter):
 def discover_listing_pages(self, source): return [source["tender_url"]]
 def discover_tenders(self, source): return self.discover_listing_pages(source)
 def extract_candidate_documents(self, page_url, html):
  soup=BeautifulSoup(html,"html.parser"); out=[]
  for a in soup.find_all("a",href=True):
   href=urljoin(page_url,a["href"]); label=" ".join(a.stripped_strings); path=href.lower()
   if not same_domain(page_url,href): continue
   if not (path.endswith((".pdf",".doc",".docx",".zip")) or allowed_path(href,PREFIXES)): continue
   cls,reasons=classify(path,label)
   if cls=="UNKNOWN" and not allowed_path(href,PREFIXES): continue
   out.append({"document_url":href,"document_link_text":label,"classification":cls,"classification_reasons":";".join(reasons)})
  return out
