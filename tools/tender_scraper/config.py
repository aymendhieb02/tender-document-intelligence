from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
@dataclass(frozen=True)
class Config:
    timeout: int = 20
    retries: int = 2
    domain_delay: float = 1.5
    max_file_bytes: int = 50_000_000
    max_pages_per_source: int = 40
    max_depth: int = 2
    target_documents: int = 100
    user_agent: str = "TunisianTenderResearchBot/1.0 (public dataset; contact: dataset-maintainer)"
    @property
    def data_dir(self): return ROOT / "data" / "acquisition"
    @property
    def raw_dir(self): return ROOT / "datasets" / "cdc_real" / "raw"
