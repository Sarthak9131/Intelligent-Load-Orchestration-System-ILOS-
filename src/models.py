"""
Data models for the Loan Processing Multi-Agent System.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ApplicationStatus(Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    REJECTED = "rejected"
    REQUIRES_INFO = "requires_additional_info"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LoanApplication:
    applicant_name: str
    loan_amount: float
    annual_income: float
    credit_score: int
    employment_years: float
    monthly_debts: float
    savings: float
    loan_purpose: str
    application_id: Optional[str] = None
    documentation_complete: bool = True

    @property
    def debt_to_income(self) -> float:
        monthly_income = self.annual_income / 12
        return self.monthly_debts / monthly_income if monthly_income else 0.0

    @property
    def loan_to_income(self) -> float:
        return self.loan_amount / self.annual_income if self.annual_income else 0.0


@dataclass
class RiskAssessment:
    overall_risk: RiskLevel
    risk_score: float  # 0-100; lower = better
    income_risk: str = ""
    credit_risk: str = ""
    employment_risk: str = ""
    collateral_risk: str = ""
    factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ProcessingResult:
    application_id: str
    status: ApplicationStatus
    decision: str
    processing_time: float
    timestamp: str
    risk_assessment: str = ""
    compliance_notes: str = ""
    loan_terms: Optional[dict] = None
    next_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "application_id": self.application_id,
            "status": self.status.value,
            "decision": self.decision,
            "processing_time_seconds": round(self.processing_time, 3),
            "timestamp": self.timestamp,
            "risk_assessment_summary": self.risk_assessment[:300] + "..."
            if len(self.risk_assessment) > 300
            else self.risk_assessment,
            "compliance_notes": self.compliance_notes[:300] + "..."
            if len(self.compliance_notes) > 300
            else self.compliance_notes,
            "loan_terms": self.loan_terms,
            "next_steps": self.next_steps,
        }
