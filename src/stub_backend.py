"""Deterministic local backend for tests, demos, and synthetic evaluation."""

import json
import math
import re
from types import SimpleNamespace
from typing import Any

from .schemas import (
    DecisionLabel,
    FinalDecisionOutput,
    ReasonCode,
    RiskAggregationOutput,
    RiskBand,
    ValidationOutput,
)


class StubAgentRunner:
    """Small ADK-compatible runner that never makes network requests."""

    def __init__(self, phase: str):
        self.phase = phase

    async def run_async(
        self,
        user_id: str,
        session_id: str,
        new_message: Any,
    ):
        """Yield one structured final response with estimated token metadata."""
        message = "".join(
            part.text
            for part in new_message.parts
            if getattr(part, "text", None) is not None
        )
        output = self._response(message)
        text = json.dumps(output.model_dump(mode="json"), sort_keys=True)
        event = SimpleNamespace(
            content=SimpleNamespace(
                parts=[SimpleNamespace(text=text)],
            ),
            is_final_response=lambda: True,
            usage_metadata=SimpleNamespace(
                prompt_token_count=_estimate_tokens(message),
                candidates_token_count=_estimate_tokens(text),
            ),
        )
        yield event

    def _response(self, message: str):
        """Create a schema-conforming result for the selected workflow phase."""
        payload = json.loads(message)
        if self.phase == "documents":
            app = _parse_application(payload.get("application_text", ""))
            missing = list(app.get("missing_fields", []))
            conflicts = list(app.get("conflicting_fields", []))
            document_complete = app.get("documentation_complete", True)
            completeness = max(
                0,
                100 - 15 * len(missing) - 20 * len(conflicts)
                - (0 if document_complete else 15),
            )
            return ValidationOutput(
                is_valid=not missing and not conflicts and document_complete,
                completeness_score=completeness,
                missing_fields=missing,
                inconsistencies=conflicts,
                requires_human_review=bool(missing or conflicts),
            )
        if self.phase == "risk":
            app = _parse_application(payload.get("application_text", ""))
            score = _risk_score(app)
            return RiskAggregationOutput(
                risk_score=score,
                risk_band=_risk_band(score),
                risk_factors=_risk_factors(app),
            )
        if self.phase == "approval":
            app = _parse_application(payload.get("application_text", ""))
            validation = payload.get("document_validation", {})
            return _decision(app, validation)
        raise ValueError(f"Unknown stub phase: {self.phase}")


def build_stub_runners() -> tuple[StubAgentRunner, StubAgentRunner, StubAgentRunner]:
    """Return document, risk, and approval runners with no external dependencies."""
    return (
        StubAgentRunner("documents"),
        StubAgentRunner("risk"),
        StubAgentRunner("approval"),
    )


def _parse_application(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return _parse_text_application(value)


def _parse_text_application(text: str) -> dict[str, Any]:
    def number(pattern: str, default: float | None = None) -> float | None:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            return default
        return float(match.group(1).replace(",", ""))

    employment_type = "self_employed" if re.search(
        r"self.employed|freelance|gig", text, re.IGNORECASE
    ) else "employed"
    application = {
        "annual_income": number(r"Annual Income:\s*\$?([\d,]+)"),
        "monthly_debts": number(r"Monthly Debts:\s*\$?([\d,]+)"),
        "loan_amount": number(r"Requested Loan Amount:\s*\$?([\d,]+)"),
        "credit_score": number(r"Credit Score:\s*(\d+)"),
        "employment_years": number(r"(\d+(?:\.\d+)?)\s+years?", 0.0),
        "savings": number(r"Liquid Savings:\s*\$?([\d,]+)"),
        "employment_type": employment_type,
        "documentation_complete": not bool(
            re.search(r"Documentation:\s*(Partial|Incomplete)", text, re.IGNORECASE)
        ),
        "missing_fields": [],
        "conflicting_fields": [],
    }
    application["missing_fields"] = [
        field
        for field in (
            "annual_income",
            "monthly_debts",
            "loan_amount",
            "credit_score",
        )
        if application[field] is None
    ]
    if re.search(r"\b(conflict|discrepancy|inconsistent)\b", text, re.IGNORECASE):
        application["conflicting_fields"] = ["application_data"]
    return application


def _risk_score(application: dict[str, Any]) -> float:
    income = _number(application.get("annual_income"))
    credit = _number(application.get("credit_score"))
    debts = _number(application.get("monthly_debts"))
    loan = _number(application.get("loan_amount"))
    monthly_income = income / 12 if income > 0 else 0
    dti = debts / monthly_income if monthly_income else 1.0
    lti = loan / income if income else 10.0

    score = max(0.0, 700 - credit) * 0.3
    score += max(0.0, dti - 0.3) * 40
    score += max(0.0, lti - 3) * 5
    if application.get("employment_type") == "self_employed":
        if _number(application.get("employment_years")) < 2:
            score += 10
    if not application.get("documentation_complete", True):
        score += 10
    if application.get("missing_fields") or application.get("conflicting_fields"):
        score += 20
    return round(min(100.0, score), 2)


def _risk_band(score: float) -> RiskBand:
    if score <= 30:
        return RiskBand.LOW
    if score <= 60:
        return RiskBand.MEDIUM
    if score <= 80:
        return RiskBand.HIGH
    return RiskBand.CRITICAL


def _risk_factors(application: dict[str, Any]) -> list[str]:
    factors = []
    credit = _number(application.get("credit_score"))
    income = _number(application.get("annual_income"))
    debts = _number(application.get("monthly_debts"))
    dti = debts / (income / 12) if income > 0 else 1.0
    if credit < 700:
        factors.append("credit_score_below_700")
    if dti >= 0.35:
        factors.append("debt_to_income_ratio_elevated")
    if application.get("employment_type") == "self_employed":
        factors.append("self_employed_income_requires_documentation")
    if application.get("missing_fields"):
        factors.append("application_fields_missing")
    if application.get("conflicting_fields"):
        factors.append("application_data_conflict")
    if not factors:
        factors.append("no_elevated_synthetic_risk_factors")
    return factors


def _decision(
    application: dict[str, Any],
    validation: dict[str, Any],
) -> FinalDecisionOutput:
    """Apply a demonstration rule that can disagree with dataset labels."""
    credit = _number(application.get("credit_score"))
    income = _number(application.get("annual_income"))
    debts = _number(application.get("monthly_debts"))
    loan = _number(application.get("loan_amount"))
    years = _number(application.get("employment_years"))
    dti = debts / (income / 12) if income > 0 else 1.0
    lti = loan / income if income > 0 else 10.0
    missing = list(application.get("missing_fields", []))
    conflicts = list(application.get("conflicting_fields", []))
    reasons: list[ReasonCode] = []
    conditions: list[str] = []

    if missing or conflicts or validation.get("requires_human_review", False):
        decision = DecisionLabel.NEEDS_HUMAN_REVIEW
        review_reason = "Missing or conflicting application evidence needs review."
        reasons.append(
            ReasonCode(
                code="INCOMPLETE_OR_CONFLICTING_DATA",
                rank=1,
                description="Required application evidence is missing or inconsistent.",
            )
        )
    elif credit <= 620 or dti >= 0.55 or lti >= 5:
        decision = DecisionLabel.REJECT
        review_reason = None
        if credit <= 620:
            reasons.append(
                ReasonCode(
                    code="LOW_CREDIT_SCORE",
                    rank=len(reasons) + 1,
                    description="The synthetic credit score is below the prototype threshold.",
                )
            )
        if dti >= 0.5:
            reasons.append(
                ReasonCode(
                    code="HIGH_DEBT_TO_INCOME",
                    rank=len(reasons) + 1,
                    description="The synthetic debt-to-income ratio exceeds the prototype threshold.",
                )
            )
        if lti >= 5:
            reasons.append(
                ReasonCode(
                    code="HIGH_LOAN_TO_INCOME",
                    rank=len(reasons) + 1,
                    description="The synthetic loan-to-income ratio exceeds the prototype threshold.",
                )
            )
    elif (
        credit < 680
        or dti >= 0.35
        or (
            application.get("employment_type") == "self_employed"
            and years < 2
        )
        or not application.get("documentation_complete", True)
    ):
        decision = DecisionLabel.CONDITIONAL
        review_reason = None
        reasons.append(
            ReasonCode(
                code="CONDITIONAL_EVIDENCE_OR_RISK",
                rank=1,
                description="One or more synthetic criteria require conditions.",
            )
        )
        conditions.append("Verify documentation and application details.")
    else:
        decision = DecisionLabel.APPROVE
        review_reason = None
        reasons.append(
            ReasonCode(
                code="SYNTHETIC_POLICY_CRITERIA_MET",
                rank=1,
                description="The synthetic application meets prototype thresholds.",
            )
        )

    confidence = 0.9
    if (
        abs(credit - 620) <= 10
        or abs(credit - 700) <= 10
        or abs(dti - 0.35) <= 0.03
        or abs(dti - 0.5) <= 0.03
    ):
        confidence = 0.55
    return FinalDecisionOutput(
        decision=decision,
        confidence=confidence,
        reason_codes=reasons,
        explanation=(
            f"Prototype decision {decision.value} based on synthetic input "
            "and fixed demonstration thresholds; not a lending recommendation."
        ),
        conditions=conditions,
        human_review_reason=review_reason,
    )


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)
