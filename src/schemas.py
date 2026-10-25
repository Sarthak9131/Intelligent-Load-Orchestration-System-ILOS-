"""Typed contracts exchanged by the loan-processing agents."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    """Base for strict agent contracts."""

    model_config = ConfigDict(extra="forbid")


class DecisionLabel(str, Enum):
    """Decision labels accepted from the final decision agent."""

    APPROVE = "approve"
    CONDITIONAL = "conditional"
    REJECT = "reject"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class RiskBand(str, Enum):
    """Qualitative risk band returned by assessment agents."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentIntakeInput(Contract):
    """Untrusted source material supplied to document intake."""

    application_text: str
    application_id: str


class DocumentIntakeOutput(Contract):
    """Documents and missing information identified at intake."""

    documents: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    data_quality_issues: list[str] = Field(default_factory=list)
    completeness_score: float = Field(ge=0, le=100)


class DataExtractionInput(Contract):
    """Input for extracting application fields from intake material."""

    application_text: str
    intake: DocumentIntakeOutput


class DataExtractionOutput(Contract):
    """Normalized financial and employment fields extracted from documents."""

    applicant_name: str | None = None
    annual_income: float | None = Field(default=None, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    monthly_debts: float | None = Field(default=None, ge=0)
    debt_to_income_ratio: float | None = Field(default=None, ge=0)
    loan_amount: float | None = Field(default=None, ge=0)
    loan_to_income_ratio: float | None = Field(default=None, ge=0)
    credit_score: int | None = Field(default=None, ge=300, le=850)
    employment_type: str | None = None
    employment_years: float | None = Field(default=None, ge=0)
    savings: float | None = Field(default=None, ge=0)
    loan_purpose: str | None = None
    evidence_notes: list[str] = Field(default_factory=list)


class ValidationInput(Contract):
    """Input for validating extracted data and document completeness."""

    extracted: DataExtractionOutput
    intake: DocumentIntakeOutput


class ValidationOutput(Contract):
    """Data quality and completeness validation result."""

    is_valid: bool
    completeness_score: float = Field(ge=0, le=100)
    missing_fields: list[str] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    requires_human_review: bool = False


class IncomeAnalysisInput(Contract):
    """Input for the income analysis agent."""

    application: dict[str, Any]
    validation: ValidationOutput


class IncomeAnalysisOutput(Contract):
    """Income stability and documentation assessment."""

    risk_score: float = Field(ge=0, le=100)
    risk_band: RiskBand
    stability_assessment: str
    documentation_quality: str
    risk_factors: list[str] = Field(default_factory=list)


class CreditAssessmentInput(Contract):
    """Input for the credit assessment agent."""

    application: dict[str, Any]


class CreditAssessmentOutput(Contract):
    """Credit history assessment."""

    credit_score: int = Field(ge=300, le=850)
    risk_score: float = Field(ge=0, le=100)
    risk_band: RiskBand
    assessment: str
    risk_factors: list[str] = Field(default_factory=list)


class EmploymentRiskInput(Contract):
    """Input for the employment risk agent."""

    application: dict[str, Any]


class EmploymentRiskOutput(Contract):
    """Employment stability assessment."""

    risk_score: float = Field(ge=0, le=100)
    risk_band: RiskBand
    assessment: str
    risk_factors: list[str] = Field(default_factory=list)


class CollateralEvaluationInput(Contract):
    """Input for the collateral evaluation agent."""

    application: dict[str, Any]


class CollateralEvaluationOutput(Contract):
    """Liquid asset coverage assessment."""

    risk_score: float = Field(ge=0, le=100)
    risk_band: RiskBand
    coverage_ratio: float = Field(ge=0)
    assessment: str
    risk_factors: list[str] = Field(default_factory=list)


class RiskAggregationInput(Contract):
    """Input for deterministic aggregation of specialist assessments."""

    income: IncomeAnalysisOutput
    credit: CreditAssessmentOutput
    employment: EmploymentRiskOutput
    collateral: CollateralEvaluationOutput


class RiskAggregationOutput(Contract):
    """Validated consolidated risk score."""

    risk_score: float = Field(ge=0, le=100)
    risk_band: RiskBand
    risk_factors: list[str] = Field(default_factory=list)


class RiskReviewInput(Contract):
    """Input for the risk analyst's recommendation."""

    application: dict[str, Any]
    assessment: RiskAggregationOutput


class RiskReviewOutput(Contract):
    """Risk analyst recommendation and conditions."""

    recommendation: DecisionLabel
    confidence: float = Field(ge=0, le=1)
    conditions: list[str] = Field(default_factory=list)
    reasoning: str


class ComplianceReviewInput(Contract):
    """Input for the compliance review agent."""

    application: dict[str, Any]
    recommendation: RiskReviewOutput


class ComplianceReviewOutput(Contract):
    """Compliance review with explicit status and issues."""

    passed: bool
    issues: list[str] = Field(default_factory=list)
    required_disclosures: list[str] = Field(default_factory=list)


class ReasonCode(Contract):
    """Ranked, machine-readable reason supporting a decision."""

    code: str
    rank: int = Field(ge=1)
    description: str


class FinalDecisionInput(Contract):
    """Input for the final underwriter agent."""

    application_id: str
    assessment: RiskAggregationOutput
    recommendation: RiskReviewOutput
    compliance: ComplianceReviewOutput


class FinalDecisionOutput(Contract):
    """Validated final decision and explainability fields."""

    decision: DecisionLabel
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[ReasonCode] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    human_review_reason: str | None = None

    @model_validator(mode="after")
    def validate_reason_order(self) -> "FinalDecisionOutput":
        ranks = [reason.rank for reason in self.reason_codes]
        if ranks != sorted(set(ranks)):
            raise ValueError("reason_codes must have unique, ascending ranks")
        if (
            self.decision == DecisionLabel.NEEDS_HUMAN_REVIEW
            and not self.human_review_reason
        ):
            raise ValueError("human_review_reason is required for review decisions")
        return self


class AgentErrorOutput(Contract):
    """Explicit failure shape used when an agent cannot satisfy its contract."""

    error: str
    attempts: int = Field(ge=1, le=2)
    requires_human_review: bool = True
