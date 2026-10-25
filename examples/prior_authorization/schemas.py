"""Pydantic contracts for the synthetic prior-authorization example."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriorAuthorizationContract(BaseModel):
    """Strict base contract for the example workflow."""

    model_config = ConfigDict(extra="forbid")


class CheckStatus(str, Enum):
    """Possible statuses for a synthetic authorization check."""

    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT = "insufficient"


class AuthorizationStatus(str, Enum):
    """Final synthetic authorization result."""

    APPROVED = "approved"
    DENIED = "denied"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class PriorAuthorizationRequest(PriorAuthorizationContract):
    """Synthetic input only; real member or patient data is rejected."""

    synthetic: Literal[True]
    request_id: str = Field(min_length=1)
    member_id: str = Field(pattern=r"^SYN-[A-Z0-9-]+$")
    procedure_code: str = Field(min_length=1)
    diagnosis_code: str = Field(min_length=1)
    coverage_active: bool | None
    procedure_covered: bool | None
    criteria_met: bool | None
    clinical_notes_present: bool | None
    prescriber_info_present: bool | None


class IntakeOutput(PriorAuthorizationContract):
    """Validated synthetic request summary."""

    request_id: str
    complete: bool
    missing_fields: list[str] = Field(default_factory=list)


class ClinicalCriteriaInput(PriorAuthorizationContract):
    """Input for the clinical criteria check."""

    criteria_met: bool | None
    procedure_code: str
    diagnosis_code: str


class ClinicalCriteriaOutput(PriorAuthorizationContract):
    """Synthetic clinical criteria result."""

    status: CheckStatus
    rationale: str


class CoverageEligibilityInput(PriorAuthorizationContract):
    """Input for the coverage eligibility check."""

    coverage_active: bool | None
    procedure_covered: bool | None


class CoverageEligibilityOutput(PriorAuthorizationContract):
    """Synthetic coverage eligibility result."""

    status: CheckStatus
    rationale: str


class DocumentationCompletenessInput(PriorAuthorizationContract):
    """Input for the documentation completeness check."""

    clinical_notes_present: bool | None
    prescriber_info_present: bool | None


class DocumentationCompletenessOutput(PriorAuthorizationContract):
    """Synthetic documentation completeness result."""

    status: CheckStatus
    missing_items: list[str] = Field(default_factory=list)


class ReviewerInput(PriorAuthorizationContract):
    """Input combining all independent synthetic checks."""

    request_id: str
    clinical: ClinicalCriteriaOutput
    coverage: CoverageEligibilityOutput
    documentation: DocumentationCompletenessOutput


class ReviewerOutput(PriorAuthorizationContract):
    """First reviewer assessment with human-escalation reasoning."""

    recommendation: AuthorizationStatus
    reason_codes: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    escalation_reason: str | None = None


class FinalAuthorizationDecision(PriorAuthorizationContract):
    """Final reviewer-chain outcome with a clear escalation path."""

    request_id: str
    status: AuthorizationStatus
    reason_codes: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    human_review_reason: str | None = None

    @model_validator(mode="after")
    def require_human_reason(self) -> "FinalAuthorizationDecision":
        if (
            self.status == AuthorizationStatus.NEEDS_HUMAN_REVIEW
            and not self.human_review_reason
        ):
            raise ValueError("human_review_reason is required when escalating")
        return self
