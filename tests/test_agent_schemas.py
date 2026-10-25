"""Unit tests for ADK agent schema wiring and stub execution."""

import json

import pytest

from examples.prior_authorization import workflow as prior_auth
from src.agents import approval_workflow, document_pipeline, risk_team
from src.schemas import (
    CollateralEvaluationOutput,
    CreditAssessmentOutput,
    DataExtractionOutput,
    EmploymentRiskOutput,
    FinalDecisionOutput,
    IncomeAnalysisOutput,
    RiskAggregationOutput,
    RiskReviewOutput,
    ValidationOutput,
)
from src.stub_backend import StubAgentRunner


@pytest.mark.parametrize(
    ("agent", "schema"),
    [
        (document_pipeline.document_intake_agent, document_pipeline.DocumentIntakeOutput),
        (document_pipeline.data_extraction_agent, DataExtractionOutput),
        (document_pipeline.validation_agent, ValidationOutput),
        (risk_team.income_analysis_agent, IncomeAnalysisOutput),
        (risk_team.credit_assessment_agent, CreditAssessmentOutput),
        (risk_team.employment_risk_agent, EmploymentRiskOutput),
        (risk_team.collateral_evaluation_agent, CollateralEvaluationOutput),
        (risk_team.risk_aggregator_agent, RiskAggregationOutput),
        (approval_workflow.risk_analyst_agent, RiskReviewOutput),
        (approval_workflow.compliance_reviewer_agent, approval_workflow.ComplianceReviewOutput),
        (approval_workflow.final_underwriter_agent, FinalDecisionOutput),
        (prior_auth.intake_agent, prior_auth.IntakeOutput),
        (prior_auth.clinical_criteria_agent, prior_auth.ClinicalCriteriaOutput),
        (prior_auth.coverage_eligibility_agent, prior_auth.CoverageEligibilityOutput),
        (
            prior_auth.documentation_completeness_agent,
            prior_auth.DocumentationCompletenessOutput,
        ),
        (prior_auth.reviewer_agent, prior_auth.ReviewerOutput),
        (prior_auth.final_reviewer_agent, prior_auth.FinalAuthorizationDecision),
    ],
)
def test_each_adk_agent_has_a_typed_output_schema(agent, schema):
    assert agent.output_schema is schema


def test_stub_backend_returns_contract_validated_phase_outputs():
    application = {
        "annual_income": 80000,
        "monthly_debts": 1000,
        "loan_amount": 20000,
        "credit_score": 750,
        "employment_type": "employed",
        "employment_years": 5,
        "savings": 10000,
        "documentation_complete": True,
        "missing_fields": [],
        "conflicting_fields": [],
    }
    application_text = json.dumps(application)
    document_result = StubAgentRunner("documents")._response(
        json.dumps(
            {
                "application_id": "LA-20261025-ABC123",
                "application_text": application_text,
            }
        )
    )
    risk_result = StubAgentRunner("risk")._response(
        json.dumps(
            {
                "application_id": "LA-20261025-ABC123",
                "application_text": application_text,
                "document_validation": document_result.model_dump(mode="json"),
            }
        )
    )
    decision = StubAgentRunner("approval")._response(
        json.dumps(
            {
                "application_id": "LA-20261025-ABC123",
                "application_text": application_text,
                "document_validation": document_result.model_dump(mode="json"),
                "risk_assessment": risk_result.model_dump(mode="json"),
            }
        )
    )

    assert isinstance(document_result, ValidationOutput)
    assert isinstance(risk_result, RiskAggregationOutput)
    assert isinstance(decision, FinalDecisionOutput)
