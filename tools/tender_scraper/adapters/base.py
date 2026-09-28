from abc import ABC, abstractmethod
class SourceAdapter(ABC):
 @abstractmethod
 def discover_listing_pages(self, source): ...
 @abstractmethod
 def discover_tenders(self, source): ...
 @abstractmethod
 def extract_candidate_documents(self, page_url, html): ...
 def resolve_download(self, page_url, href): return href
 def extract_metadata(self, title, page_url): return {"tender_title":title,"tender_page_url":page_url}
