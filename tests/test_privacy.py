"""Tests for PII masking before prompts and audit logging."""

import json

import pytest

import src.orchestrator as orchestration
from src.models import ApplicationStatus
from src.privacy import (
    REDACTED_ADDRESS,
    REDACTED_DOB,
    REDACTED_EMAIL,
    REDACTED_NAME,
    REDACTED_PHONE,
    REDACTED_SSN,
    mask_pii,
    mask_sensitive_data,
)
from src.orchestrator import LoanProcessingOrchestrator
from src.schemas import (
    DecisionLabel,
    FinalDecisionOutput,
    ReasonCode,
    RiskAggregationOutput,
    RiskBand,
    ValidationOutput,
)


def test_masks_json_identifiers():
    raw = json.dumps(
        {
            "applicant_name": "Alex Rivera",
            "ssn": "123-45-6789",
            "date_of_birth": "04/15/1985",
            "address": "123 Example Street",
            "phone": "(555) 123-4567",
            "email": "alex@example.test",
        }
    )

    masked = mask_pii(raw)

    for secret in (
        "Alex Rivera",
        "123-45-6789",
        "04/15/1985",
        "123 Example Street",
        "(555) 123-4567",
        "alex@example.test",
    ):
        assert secret not in masked
    assert REDACTED_NAME in masked
    assert REDACTED_SSN in masked
    assert REDACTED_DOB in masked
    assert REDACTED_ADDRESS in masked
    assert REDACTED_PHONE in masked
    assert REDACTED_EMAIL in masked


def test_masks_labeled_pii_and_known_name_references():
    raw = (
        "Applicant Name: Alex Rivera\n"
        "SSN: 123-45-6789\n"
        "DOB: 04/15/1985\n"
        "Address: 123 Example Street\n"
        "Phone: 555-123-4567\n"
        "Email: alex@example.test\n"
        "Alex Rivera submitted the application."
    )

    masked = mask_pii(raw)

    assert "Alex Rivera" not in masked
    assert "123-45-6789" not in masked
    assert "04/15/1985" not in masked
    assert "123 Example Street" not in masked
    assert "555-123-4567" not in masked
    assert "alex@example.test" not in masked
    assert masked.count(REDACTED_NAME) >= 2


def test_masks_sensitive_fields_in_nested_log_payload():
    payload = {
        "agent": {
            "applicant_name": "Alex Rivera",
            "details": [{"email": "alex@example.test"}],
        }
    }

    masked = mask_sensitive_data(payload)

    assert masked["agent"]["applicant_name"] == REDACTED_NAME
    assert masked["agent"]["details"][0]["email"] == REDACTED_EMAIL


@pytest.mark.asyncio
async def test_orchestrator_masks_input_before_invocation_and_audit(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    monkeypatch.setattr(orchestration, "pipeline_runner", object())
    monkeypatch.setattr(orchestration, "risk_runner", object())
    monkeypatch.setattr(orchestration, "approval_runner", object())
    prompts = []

    async def fake_run_agent(
        runner,
        session_id,
        message,
        application_id,
        agent_name,
        output_schema,
        audit,
        input_hash,
    ):
        prompts.append(message)
        if output_schema is ValidationOutput:
            output = ValidationOutput(is_valid=True, completeness_score=90)
        elif output_schema is RiskAggregationOutput:
            output = RiskAggregationOutput(risk_score=20, risk_band=RiskBand.LOW)
        else:
            output = FinalDecisionOutput(
                decision=DecisionLabel.APPROVE,
                confidence=0.95,
                reason_codes=[
                    ReasonCode(
                        code="LOW_RISK",
                        rank=1,
                        description="Synthetic criteria were met.",
                    )
                ],
                explanation="Synthetic case reviewed.",
            )
        audit.record(
            {
                "agent_name": agent_name,
                "input_hash": input_hash,
                "output": output.model_dump(mode="json"),
                "errors": [],
            }
        )
        return output, 0.01, {}

    monkeypatch.setattr(orchestration, "_run_agent", fake_run_agent)
    result = await LoanProcessingOrchestrator(llm_mode="adk").process_loan_application(
        json.dumps(
            {
                "applicant_name": "Alex Rivera",
                "ssn": "123-45-6789",
                "date_of_birth": "04/15/1985",
                "address": "123 Example Street",
                "phone": "(555) 123-4567",
                "email": "alex@example.test",
            }
        )
    )

    prompt_text = "\n".join(prompts)
    audit_text = (tmp_path / f"{result.application_id}.json").read_text()
    for secret in (
        "Alex Rivera",
        "123-45-6789",
        "04/15/1985",
        "123 Example Street",
        "(555) 123-4567",
        "alex@example.test",
    ):
        assert secret not in prompt_text
        assert secret not in audit_text
    assert result.status == ApplicationStatus.APPROVED
