"""Deterministic executive summaries over structured tender evidence."""

from .builder import build_tender_summary
from .models import (
    FactState,
    KeyFact,
    TenderSummary,
)

__all__ = ["FactState", "KeyFact", "TenderSummary", "build_tender_summary"]
