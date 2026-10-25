"""Tests for the synthetic prior-authorization workflow example."""

import pytest
from pydantic import ValidationError

from examples.prior_authorization.schemas import (
    AuthorizationStatus,
    PriorAuthorizationRequest,
)
from examples.prior_authorization.workflow import PriorAuthorizationOrchestrator


def _request(**overrides):
    values = {
        "synthetic": True,
        "request_id": "SYN-PA-TEST-001",
        "member_id": "SYN-MEMBER-TEST-001",
        "procedure_code": "SYN-PROC-100",
        "diagnosis_code": "SYN-DX-200",
        "coverage_active": True,
        "procedure_covered": True,
        "criteria_met": True,
        "clinical_notes_present": True,
        "prescriber_info_present": True,
    }
    values.update(overrides)
    return PriorAuthorizationRequest(**values)


@pytest.mark.asyncio
async def test_prior_authorization_stub_approves_complete_synthetic_case(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    result = await PriorAuthorizationOrchestrator().process(_request())

    assert result.status == AuthorizationStatus.APPROVED
    assert result.reason_codes == ["SYNTHETIC_CHECKS_PASSED"]
    assert (tmp_path / "PA-SYN-PA-TEST-001.json").exists()


@pytest.mark.asyncio
async def test_incomplete_documentation_escalates_with_reason(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    result = await PriorAuthorizationOrchestrator().process(
        _request(clinical_notes_present=False)
    )

    assert result.status == AuthorizationStatus.NEEDS_HUMAN_REVIEW
    assert result.human_review_reason
    assert "DOCUMENTATION_INCOMPLETE" in result.reason_codes


@pytest.mark.asyncio
async def test_ineligible_coverage_is_denied(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    result = await PriorAuthorizationOrchestrator().process(
        _request(procedure_covered=False)
    )

    assert result.status == AuthorizationStatus.DENIED
    assert "COVERAGE_INELIGIBLE" in result.reason_codes


def test_real_data_is_rejected_by_synthetic_only_contract():
    with pytest.raises(ValidationError):
        _request(synthetic=False)
