"""Region selection is independent of recognition and preprocessing."""
from typing import Protocol

import numpy as np

from app.services.table_regions import OCRRegion, build_ocr_regions


class RegionPolicy(Protocol):
    def regions(self, image: np.ndarray, mode: str) -> list[OCRRegion]: ...


class FullPageRegionPolicy:
    def regions(self, image: np.ndarray, mode: str = "fast") -> list[OCRRegion]:
        height, width = image.shape[:2]
        return [OCRRegion("full_page", image, coordinates=(0, 0, width, height))]


class InvoiceRegionPolicy:
    def regions(self, image: np.ndarray, mode: str) -> list[OCRRegion]:
        regions = build_ocr_regions(image)
        if mode in {"fast", "balanced"}:
            full_page = [region for region in regions if region.name == "full_page"]
            return full_page or regions[:1]
        return regions
