"""CDC domain: consumes document evidence; never opens PDFs or runs OCR."""

from .contract import DocumentInput, ElementInput, PageInput
from .pipeline import CDCAnalyzer
from .schema import TenderDocument

__all__ = ["CDCAnalyzer", "DocumentInput", "ElementInput", "PageInput", "TenderDocument"]
