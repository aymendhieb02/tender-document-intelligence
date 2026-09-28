"""Public, evidence-linked contract for requirement semantics."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.cdc_analysis.schema import Evidence


class RequirementCategory(StrEnum):
    ADMINISTRATIVE = "ADMINISTRATIVE"
    ELIGIBILITY = "ELIGIBILITY"
    LEGAL = "LEGAL"
    TECHNICAL = "TECHNICAL"
    FINANCIAL = "FINANCIAL"
    SUBMISSION = "SUBMISSION"
    EXECUTION = "EXECUTION"
    PAYMENT = "PAYMENT"
    GUARANTEE = "GUARANTEE"
    PENALTY = "PENALTY"
    DEADLINE = "DEADLINE"
    REQUIRED_DOCUMENT = "REQUIRED_DOCUMENT"
    EXPERIENCE = "EXPERIENCE"
    PERSONNEL = "PERSONNEL"
    EQUIPMENT = "EQUIPMENT"
    CERTIFICATION = "CERTIFICATION"
    INSURANCE = "INSURANCE"
    WARRANTY = "WARRANTY"
    EVALUATION = "EVALUATION"
    OTHER = "OTHER"


class MandatoryStatus(StrEnum):
    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"
    UNCLEAR = "UNCLEAR"


class RequirementReviewStatus(StrEnum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"


class TenderRequirement(BaseModel):
    """A semantic interpretation that keeps the CDC source evidence intact."""

    model_config = ConfigDict(frozen=True)

    id: str
    category: RequirementCategory
    title: str
    description: str
    mandatory_status: MandatoryStatus
    responsible_party: str | None = None
    action: str | None = None
    condition: str | None = None
    related_value_refs: tuple[str, ...] = ()
    source_requirement_id: str | None = None
    source_article_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    page: int | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    review_status: RequirementReviewStatus = RequirementReviewStatus.NEEDS_REVIEW
