"""Provisional consumer contract, deliberately independent of the OCR producer."""
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ElementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    text: str = ""
    kind: Literal["text", "heading", "table", "header", "footer", "toc"] = "text"
    bbox: tuple[float, float, float, float] | None = None
    heading_level: int | None = Field(default=None, ge=1)
    font_size: float | None = None
    bold: bool | None = None
    table_id: str | None = None
    parts: list["ElementPart"] = Field(default_factory=list)


class ElementPart(BaseModel):
    id: str
    text: str
    bbox: tuple[float, float, float, float] | None = None


class PageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1)
    width: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)
    coordinate_space: str | None = None
    elements: list[ElementInput] = Field(default_factory=list)


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    pages: list[PageInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_order(self):
        numbers = [p.page_number for p in self.pages]
        if numbers != sorted(set(numbers)):
            raise ValueError("Pages must be unique and in source order")
        for page in self.pages:
            ids = [e.id for e in page.elements]
            if len(set(ids)) != len(ids):
                raise ValueError("Element IDs must be unique within each page")
        return self


class DocumentResultAdapter(Protocol):
    def adapt(self, document_result: Any) -> DocumentInput:
        """Map the producer's result to this contract without PDF extraction."""
        ...
