import hashlib, re, unicodedata
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
