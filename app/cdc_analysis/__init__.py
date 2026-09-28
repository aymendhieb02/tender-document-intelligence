"""CDC domain: consumes document evidence; never opens PDFs or runs OCR."""

from .contract import DocumentInput, ElementInput, PageInput
from .pipeline import CDCAnalyzer
from .schema import TenderDocument
from .financial_deadline import Fact, normalize_financial_deadlines

CDC_ANALYZER_VERSION = "CDC_ANALYZER_V2"

__all__ = ["CDC_ANALYZER_VERSION", "CDCAnalyzer", "DocumentInput", "ElementInput", "PageInput",
           "TenderDocument", "Fact", "normalize_financial_deadlines"]
