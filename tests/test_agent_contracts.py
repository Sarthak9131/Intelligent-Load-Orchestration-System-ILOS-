"""Contract and retry tests for agent boundaries."""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import src.orchestrator as orchestration
from src.agent_observability import after_agent, before_agent
from src.models import ApplicationStatus
from src.orchestrator import (
    AgentContractError,
    ApplicationAuditTrail,
    LoanProcessingOrchestrator,
    _run_agent,
)
from src.schemas import (
    DecisionLabel,
    FinalDecisionOutput,
    ReasonCode,
    RiskAggregationOutput,
    RiskBand,
    ValidationOutput,
)


def test_schema_rejects_invalid_scores_and_extra_fields():
    with pytest.raises(ValidationError):
        ValidationOutput(is_valid=True, completeness_score=101)

    with pytest.raises(ValidationError):
        RiskAggregationOutput(risk_score=-1, risk_band=RiskBand.LOW)

    with pytest.raises(ValidationError):
        ValidationOutput(is_valid=True, completeness_score=90, unexpected=True)

    with pytest.raises(ValidationError):
        FinalDecisionOutput(
            decision=DecisionLabel.NEEDS_HUMAN_REVIEW,
            confidence=0.5,
            reason_codes=[
                ReasonCode(code="REVIEW", rank=1, description="Needs review.")
            ],
            explanation="Human review is required.",
        )


def test_agent_callback_appends_per_step_audit_event(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    context = SimpleNamespace(
        invocation_id="invocation-1",
        agent_name="IncomeAnalysisAgent",
        user_content="Synthetic input",
        session=SimpleNamespace(id="risk-LA-20261025-ABC123-attempt-1"),
        state={},
        output='{"applicant_name":"Alex Rivera","ssn":"123-45-6789"}',
        error=None,
    )

    before_agent(context)
    after_agent(context)

    audit_path = tmp_path / "LA-20261025-ABC123.json"
    event = json.loads(audit_path.read_text())["events"][0]
    assert event["agent_name"] == "IncomeAnalysisAgent"
    assert event["latency_ms"] >= 0
    assert event["input_hash"]
    assert "Alex Rivera" not in event["output"]
    assert "123-45-6789" not in event["output"]


@pytest.mark.asyncio
async def test_run_agent_retries_once_and_validates_output(monkeypatch, tmp_path):
    responses = iter(
        [
            ('{"is_valid": true, "completeness_score": 130}', {}),
            ('{"is_valid": true, "completeness_score": 85}', {"output_tokens": 4}),
        ]
    )
    calls = 0

    async def fake_collect_response(runner, session_id, message):
        nonlocal calls
        calls += 1
        return next(responses)

    monkeypatch.setattr("src.orchestrator._collect_response", fake_collect_response)
    audit = ApplicationAuditTrail("LA-TEST")
    result, latency, tokens = await _run_agent(
        runner=object(),
        session_id="doc-test",
        message="{}",
        application_id="LA-TEST",
        agent_name="ValidationAgent",
        output_schema=ValidationOutput,
        audit=audit,
        input_hash="input-hash",
    )

    assert calls == 2
    assert result.completeness_score == 85
    assert latency >= 0
    assert tokens == {"output_tokens": 4}
    assert audit.events[0]["errors"]
    assert audit.events[1]["output"]["is_valid"] is True


@pytest.mark.asyncio
async def test_run_agent_stops_after_two_invalid_responses(monkeypatch):
    calls = 0

    async def fake_collect_response(runner, session_id, message):
        nonlocal calls
        calls += 1
        return '{"is_valid": true, "completeness_score": 130}', {}

    monkeypatch.setattr("src.orchestrator._collect_response", fake_collect_response)
    with pytest.raises(AgentContractError) as error:
        await _run_agent(
            runner=object(),
            session_id="doc-test",
            message="{}",
            application_id="LA-TEST",
            agent_name="ValidationAgent",
            output_schema=ValidationOutput,
            audit=ApplicationAuditTrail("LA-TEST"),
            input_hash="input-hash",
        )

    assert calls == 2
    assert error.value.attempts == 2


@pytest.mark.asyncio
async def test_pipeline_returns_typed_decision_and_writes_audit(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    monkeypatch.setattr(orchestration, "pipeline_runner", object())
    monkeypatch.setattr(orchestration, "risk_runner", object())
    monkeypatch.setattr(orchestration, "approval_runner", object())

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
        if output_schema is ValidationOutput:
            output = ValidationOutput(is_valid=True, completeness_score=95)
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
                        description="The synthetic risk score is low.",
                    )
                ],
                explanation="Synthetic application meets the prototype criteria.",
            )
        audit.record(
            {
                "agent_name": agent_name,
                "latency_ms": 10,
                "token_usage": {"input_tokens": 3, "output_tokens": 2},
                "input_hash": input_hash,
                "output": output.model_dump(mode="json"),
                "errors": [],
            }
        )
        return output, 0.01, {"input_tokens": 3, "output_tokens": 2}

    monkeypatch.setattr(orchestration, "_run_agent", fake_run_agent)
    result = await LoanProcessingOrchestrator(llm_mode="adk").process_loan_application(
        "Synthetic application data."
    )

    assert result.status == ApplicationStatus.APPROVED
    assert result.reason_codes[0]["code"] == "LOW_RISK"
    assert result.phase_latencies["risk_assessment"] == 0.01
    saved = json.loads((tmp_path / f"{result.application_id}.json").read_text())
    assert [event["agent_name"] for event in saved["events"]][-1] == (
        "LoanProcessingOrchestrator"
    )


@pytest.mark.asyncio
async def test_schema_failure_routes_to_human_review(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    monkeypatch.setattr(orchestration, "pipeline_runner", object())
    monkeypatch.setattr(orchestration, "risk_runner", object())
    monkeypatch.setattr(orchestration, "approval_runner", object())

    async def fail_first_agent(*args, **kwargs):
        raise AgentContractError("DocumentProcessingPipeline", 2, "invalid output")

    monkeypatch.setattr(orchestration, "_run_agent", fail_first_agent)
    result = await LoanProcessingOrchestrator(llm_mode="adk").process_loan_application(
        "Synthetic application data."
    )

    assert result.status == ApplicationStatus.NEEDS_HUMAN_REVIEW
    assert "failed schema validation" in result.human_review_reason
    assert (tmp_path / f"{result.application_id}.json").exists()


@pytest.mark.parametrize(
    ("risk_score", "confidence", "expected_reason"),
    [
        (20, 0.5, "Decision confidence"),
        (30, 0.95, "Risk score is within five points"),
    ],
)
@pytest.mark.asyncio
async def test_low_confidence_and_borderline_scores_route_to_review(
    monkeypatch,
    tmp_path,
    risk_score,
    confidence,
    expected_reason,
):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    monkeypatch.setattr(orchestration, "pipeline_runner", object())
    monkeypatch.setattr(orchestration, "risk_runner", object())
    monkeypatch.setattr(orchestration, "approval_runner", object())

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
        if output_schema is ValidationOutput:
            output = ValidationOutput(is_valid=True, completeness_score=90)
        elif output_schema is RiskAggregationOutput:
            output = RiskAggregationOutput(
                risk_score=risk_score,
                risk_band=RiskBand.LOW,
            )
        else:
            output = FinalDecisionOutput(
                decision=DecisionLabel.APPROVE,
                confidence=confidence,
                reason_codes=[
                    ReasonCode(
                        code="TEST",
                        rank=1,
                        description="Test reason.",
                    )
                ],
                explanation="Test decision.",
            )
        audit.record({"agent_name": agent_name, "input_hash": input_hash})
        return output, 0.01, {}

    monkeypatch.setattr(orchestration, "_run_agent", fake_run_agent)
    result = await LoanProcessingOrchestrator(llm_mode="adk").process_loan_application(
        "Synthetic application."
    )

    assert result.status == ApplicationStatus.NEEDS_HUMAN_REVIEW
    assert expected_reason in result.human_review_reason
    assert result.reason_codes[0]["code"] == "HUMAN_REVIEW_REQUIRED"
