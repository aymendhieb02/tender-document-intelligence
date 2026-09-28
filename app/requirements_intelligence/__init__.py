"""Deterministic semantics over CDC output; this package never reads documents."""

from .classifier import classify_document, classify_text
from .models import (
    ConfidenceLevel,
    MandatoryStatus,
    RequirementCategory,
    RequirementReviewStatus,
    TenderRequirement,
)

__all__ = [
    "ConfidenceLevel",
    "MandatoryStatus",
    "RequirementCategory",
    "RequirementReviewStatus",
    "TenderRequirement",
    "classify_document",
    "classify_text",
]
