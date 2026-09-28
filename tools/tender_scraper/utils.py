import hashlib, re, unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag
from pathlib import Path

def sha256(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
 return h.hexdigest()
def safe_name(value, limit=100):
 s=unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode().lower()
 s=re.sub(r"[^a-z0-9]+","-",s).strip("-")[:limit].strip("-")
 return s or "document"
def normalize_url(base, href): return urldefrag(urljoin(base,href))[0]
def same_domain(a,b): return urlparse(a).hostname == urlparse(b).hostname
def allowed_path(url, prefixes):
 path=urlparse(url).path.lower()
 return any(x in path for x in prefixes)

class _LinkParser(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.links=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="a":self.current={"attrs":dict(attrs),"text":[]}
    def handle_data(self,data):
        if self.current is not None:self.current["text"].append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="a" and self.current is not None:
            self.links.append({**self.current["attrs"],"text":" ".join(" ".join(self.current["text"]).split())});self.current=None
def extract_links(html):
    parser=_LinkParser();parser.feed(html);parser.close();return parser.links
