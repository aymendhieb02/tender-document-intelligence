from __future__ import annotations

from typing import Any

def adapt_page(page: Any):
    """Validate the public PageResult shape without depending on OCR internals."""
    if all(hasattr(page, field) for field in ("page_number", "width", "height", "elements")):
        return page
    raise TypeError("page must implement the public PageResult contract")


def element_value(element: Any, name: str, default=None):
    if isinstance(element, dict):
        return element.get(name, default)
    return getattr(element, name, default)
