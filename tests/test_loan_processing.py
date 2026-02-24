"""
Unit tests for Loan Processing Multi-Agent System
Run: pytest tests/
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import ApplicationStatus, LoanApplication, ProcessingResult, RiskLevel
from src.orchestrator import _parse_status


# ── Model Tests ────────────────────────────────────────────────────────────────

class TestLoanApplication:
    def test_debt_to_income_calculation(self):
        app = LoanApplication(
            applicant_name="Test User",
            loan_amount=75000,
            annual_income=165000,
            credit_score=785,
            employment_years=5,
            monthly_debts=2850,
            savings=45000,
            loan_purpose="Home renovation",
        )
        expected_dti = 2850 / (165000 / 12)
        assert round(app.debt_to_income, 4) == round(expected_dti, 4)

    def test_loan_to_income_calculation(self):
        app = LoanApplication(
            applicant_name="Test User",
            loan_amount=75000,
            annual_income=165000,
            credit_score=785,
            employment_years=5,
            monthly_debts=2850,
            savings=45000,
            loan_purpose="Home renovation",
        )
        assert round(app.loan_to_income, 4) == round(75000 / 165000, 4)

    def test_zero_income_dti(self):
        app = LoanApplication(
            applicant_name="Test",
            loan_amount=10000,
            annual_income=0,
            credit_score=700,
            employment_years=1,
            monthly_debts=500,
            savings=1000,
            loan_purpose="Personal",
        )
        assert app.debt_to_income == 0.0


class TestProcessingResult:
    def test_to_dict_truncates_long_fields(self):
        result = ProcessingResult(
            application_id="LA-TEST-001",
            status=ApplicationStatus.APPROVED,
            decision="Approved " * 100,
            processing_time=1.5,
            timestamp="2025-01-15T14:30:00",
            risk_assessment="Low risk " * 50,
            compliance_notes="Compliant " * 50,
        )
        d = result.to_dict()
        assert d["status"] == "approved"
        assert len(d["risk_assessment_summary"]) <= 303  # 300 + "..."
        assert len(d["compliance_notes"]) <= 303


# ── Status Parser Tests ────────────────────────────────────────────────────────

class TestParseStatus:
    def test_approved(self):
        assert _parse_status("The loan is APPROVED.") == ApplicationStatus.APPROVED

    def test_rejected(self):
        assert _parse_status("Application REJECTED due to high risk.") == ApplicationStatus.REJECTED

    def test_denied(self):
        assert _parse_status("Request denied — insufficient income.") == ApplicationStatus.REJECTED

    def test_conditionally_approved(self):
        assert (
            _parse_status("CONDITIONALLY APPROVED pending documentation.")
            == ApplicationStatus.CONDITIONALLY_APPROVED
        )

    def test_requires_info(self):
        assert (
            _parse_status("Requires additional information before proceeding.")
            == ApplicationStatus.REQUIRES_INFO
        )

    def test_fallback_to_under_review(self):
        assert _parse_status("Pending senior review.") == ApplicationStatus.UNDER_REVIEW


# ── Orchestrator Metrics Tests ─────────────────────────────────────────────────

class TestOrchestratorMetrics:
    @pytest.fixture
    def orchestrator(self):
        with patch("src.orchestrator.pipeline_runner"), \
             patch("src.orchestrator.risk_runner"), \
             patch("src.orchestrator.approval_runner"):
            from src.orchestrator import LoanProcessingOrchestrator
            return LoanProcessingOrchestrator()

    def test_initial_metrics(self, orchestrator):
        m = orchestrator.processing_metrics
        assert m["total_applications"] == 0
        assert m["approved"] == 0
        assert m["rejected"] == 0

    def test_update_metrics_approved(self, orchestrator):
        result = ProcessingResult(
            application_id="LA-001",
            status=ApplicationStatus.APPROVED,
            decision="Approved",
            processing_time=2.0,
            timestamp="2025-01-15T14:30:00",
        )
        orchestrator._update_metrics(result)
        assert orchestrator.processing_metrics["approved"] == 1
        assert orchestrator.processing_metrics["total_applications"] == 1

    def test_update_metrics_rejected(self, orchestrator):
        result = ProcessingResult(
            application_id="LA-002",
            status=ApplicationStatus.REJECTED,
            decision="Rejected",
            processing_time=1.5,
            timestamp="2025-01-15T14:31:00",
        )
        orchestrator._update_metrics(result)
        assert orchestrator.processing_metrics["rejected"] == 1

    def test_dashboard_format(self, orchestrator):
        result = ProcessingResult(
            application_id="LA-001",
            status=ApplicationStatus.APPROVED,
            decision="Approved",
            processing_time=2.5,
            timestamp="2025-01-15T14:30:00",
        )
        orchestrator._update_metrics(result)
        dashboard = orchestrator.get_performance_dashboard()
        assert "total_applications_processed" in dashboard
        assert "approval_rate" in dashboard
        assert "average_processing_time" in dashboard
