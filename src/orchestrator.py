"""Orchestration and reliability boundaries for loan-processing agents.""" 

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from google.adk.runners import Runner
from google.genai.errors import APIError as GoogleAPIError
from litellm.exceptions import APIError as LiteLLMAPIError
from pydantic import BaseModel, ValidationError

from config.settings import AUDIT_DIR, LLM_MODE, MAX_AGENT_ATTEMPTS

from .agents.approval_workflow import approval_runner
from .agents.document_pipeline import pipeline_runner
from .agents.risk_team import risk_runner
from .models import ApplicationStatus, ProcessingResult
from .privacy import mask_pii, mask_sensitive_data
from .schemas import (
    DecisionLabel,
    DocumentIntakeInput,
    FinalDecisionOutput,
    ReasonCode,
    RiskAggregationOutput,
    ValidationOutput,
)
from .stub_backend import StubAgentRunner

logger = logging.getLogger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class AgentContractError(RuntimeError):
    """Raised after an agent fails to return output matching its contract."""

    def __init__(
        self,
        agent_name: str,
        attempts: int,
        error: str,
        latency: float = 0.0,
        token_usage: dict[str, int] | None = None,
    ):
        super().__init__(error)
        self.agent_name = agent_name
        self.attempts = attempts
        self.latency = latency
        self.token_usage = token_usage or {}


class ApplicationAuditTrail:
    """Collect structured events and persist one JSON audit record per application."""

    def __init__(self, application_id: str):
        self.application_id = application_id
        self.events: list[dict[str, Any]] = []

    def record(self, event: dict[str, Any]) -> None:
        """Append an event and emit it as a structured JSON log line."""
        record = mask_sensitive_data({"application_id": self.application_id, **event})
        self.events.append(record)
        logger.info("%s", json.dumps(record, sort_keys=True, default=str))

    def save(self) -> Path:
        """Persist the application audit as JSON."""
        audit_dir = Path(os.getenv("AUDIT_DIR", AUDIT_DIR))
        audit_dir.mkdir(parents=True, exist_ok=True)
        destination = audit_dir / f"{self.application_id}.json"
        temporary = destination.with_suffix(".json.tmp")
        if destination.exists():
            payload = json.loads(destination.read_text(encoding="utf-8"))
            payload["events"].extend(self.events)
        else:
            payload = {
                "application_id": self.application_id,
                "created_at": datetime.now(UTC).isoformat(),
                "events": self.events,
            }
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(destination)
        return destination


class LoanProcessingOrchestrator:
    """Run document, risk, and sequential approval phases with typed boundaries."""

    def __init__(self, llm_mode: str | None = None) -> None:
        mode = (llm_mode or os.getenv("LLM_MODE") or LLM_MODE).lower()
        self.pipeline_runner: Runner | StubAgentRunner
        self.risk_runner: Runner | StubAgentRunner
        self.approval_runner: Runner | StubAgentRunner
        if mode == "stub":
            from .stub_backend import build_stub_runners

            (
                self.pipeline_runner,
                self.risk_runner,
                self.approval_runner,
            ) = build_stub_runners()
        elif mode == "adk":
            self.pipeline_runner = pipeline_runner
            self.risk_runner = risk_runner
            self.approval_runner = approval_runner
        else:
            raise ValueError("LLM_MODE must be either 'stub' or 'adk'.")
        self.llm_mode = mode
        self.processing_metrics: dict[str, float | int] = {
            "total_applications": 0,
            "approved": 0,
            "rejected": 0,
            "conditional": 0,
            "needs_human_review": 0,
            "average_processing_time": 0.0,
        }

    async def process_loan_application(self, application_data: str) -> ProcessingResult:
        """Run every workflow phase; validation failures explicitly require review."""
        start_time = time.perf_counter()
        application_id = (
            f"LA-{datetime.now(UTC).strftime('%Y%m%d')}-"
            f"{uuid.uuid4().hex[:6].upper()}"
        )
        audit = ApplicationAuditTrail(application_id)
        phase_latencies: dict[str, float] = {}
        token_usage: dict[str, int] = {}
        masked_application_data = mask_pii(application_data)
        input_hash = hashlib.sha256(masked_application_data.encode("utf-8")).hexdigest()

        try:
            intake_input = DocumentIntakeInput(
                application_text=masked_application_data,
                application_id=application_id,
            )
            document_result, latency, tokens = await _run_agent(
                self.pipeline_runner,
                f"doc-{application_id}",
                intake_input.model_dump_json(),
                application_id,
                "DocumentProcessingPipeline",
                ValidationOutput,
                audit,
                input_hash,
            )
            phase_latencies["document_processing"] = latency
            _add_tokens(token_usage, tokens)

            risk_result, latency, tokens = await _run_agent(
                self.risk_runner,
                f"risk-{application_id}",
                json.dumps(
                    {
                        "application_id": application_id,
                        "application_text": masked_application_data,
                        "document_validation": document_result.model_dump(mode="json"),
                    }
                ),
                application_id,
                "RiskAssessmentWorkflow",
                RiskAggregationOutput,
                audit,
                input_hash,
            )
            phase_latencies["risk_assessment"] = latency
            _add_tokens(token_usage, tokens)

            approval_result, latency, tokens = await _run_agent(
                self.approval_runner,
                f"approval-{application_id}",
                json.dumps(
                    {
                        "application_id": application_id,
                        "application_text": masked_application_data,
                        "document_validation": document_result.model_dump(mode="json"),
                        "risk_assessment": risk_result.model_dump(mode="json"),
                    }
                ),
                application_id,
                "ApprovalWorkflow",
                FinalDecisionOutput,
                audit,
                input_hash,
            )
            phase_latencies["approval_workflow"] = latency
            _add_tokens(token_usage, tokens)

            review_reason = None
            if document_result.requires_human_review:
                review_reason = (
                    "Document validation identified missing or inconsistent information."
                )
            elif approval_result.confidence < 0.7:
                review_reason = (
                    "Decision confidence is below the prototype review threshold."
                )
            else:
                review_reason = _borderline_risk_reason(risk_result.risk_score)
            if review_reason:
                approval_result = _review_decision(approval_result, review_reason)

            result = ProcessingResult(
                application_id=application_id,
                status=_status_for_decision(approval_result.decision.value),
                decision=mask_pii(approval_result.explanation),
                processing_time=time.perf_counter() - start_time,
                timestamp=datetime.now(UTC).isoformat(),
                risk_assessment=risk_result.model_dump_json(),
                compliance_notes="Compliance status must be verified by an accountable reviewer.",
                reason_codes=[
                    mask_sensitive_data(reason.model_dump(mode="json"))
                    for reason in approval_result.reason_codes
                ],
                explanation=mask_pii(approval_result.explanation),
                confidence=approval_result.confidence,
                human_review_reason=approval_result.human_review_reason,
                phase_latencies=phase_latencies,
                token_usage=token_usage,
            )
            audit.record(
                {
                    "agent_name": "LoanProcessingOrchestrator",
                    "input_hash": input_hash,
                    "output": result.to_dict(),
                    "errors": [],
                }
            )
            self._update_metrics(result)
            return result
        except AgentContractError as exc:
            reason = (
                f"{exc.agent_name} output failed schema validation after "
                f"{exc.attempts} attempts: {exc}"
            )
            audit.record(
                {
                    "agent_name": exc.agent_name,
                    "latency_ms": round(exc.latency * 1000, 3),
                    "token_usage": exc.token_usage,
                    "input_hash": input_hash,
                    "output": None,
                    "errors": [mask_pii(reason)],
                }
            )
            phase_latencies[exc.agent_name] = exc.latency
            _add_tokens(token_usage, exc.token_usage)
            result = _human_review_result(
                application_id,
                reason,
                time.perf_counter() - start_time,
                phase_latencies,
                token_usage,
            )
            self._update_metrics(result)
            return result
        finally:
            audit.save()

    def get_performance_dashboard(self) -> dict[str, Any]:
        """Return observed in-process processing counts and latency."""
        total = int(self.processing_metrics["total_applications"])
        return {
            "total_applications_processed": total,
            "approval_rate": _percentage(self.processing_metrics["approved"], total),
            "rejection_rate": _percentage(self.processing_metrics["rejected"], total),
            "conditional_approval_rate": _percentage(
                self.processing_metrics["conditional"], total
            ),
            "human_review_rate": _percentage(
                self.processing_metrics["needs_human_review"], total
            ),
            "average_processing_time": (
                f"{self.processing_metrics['average_processing_time']:.2f}s"
            ),
        }

    def _update_metrics(self, result: ProcessingResult) -> None:
        metrics = self.processing_metrics
        metrics["total_applications"] += 1
        total = int(metrics["total_applications"])
        if result.status == ApplicationStatus.APPROVED:
            metrics["approved"] += 1
        elif result.status == ApplicationStatus.REJECTED:
            metrics["rejected"] += 1
        elif result.status == ApplicationStatus.CONDITIONALLY_APPROVED:
            metrics["conditional"] += 1
        elif result.status == ApplicationStatus.NEEDS_HUMAN_REVIEW:
            metrics["needs_human_review"] += 1
        metrics["average_processing_time"] = (
            float(metrics["average_processing_time"]) * (total - 1)
            + result.processing_time
        ) / total


async def _run_agent(
    runner: Any,
    session_id: str,
    message: str,
    application_id: str,
    agent_name: str,
    output_schema: type[SchemaT],
    audit: ApplicationAuditTrail,
    input_hash: str,
) -> tuple[SchemaT, float, dict[str, int]]:
    """Invoke an ADK runner and retry at most once when its output is invalid."""
    last_error = "No response received."
    elapsed = 0.0
    tokens: dict[str, int] = {}
    for attempt in range(1, MAX_AGENT_ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            response, attempt_tokens = await _collect_response(
                runner,
                f"{session_id}-attempt-{attempt}",
                message
                if attempt == 1
                else (
                    f"{message}\n\nYour previous response did not match the required "
                    f"JSON schema. Correct the response and return only JSON:\n"
                    f"{json.dumps(output_schema.model_json_schema())}"
                ),
            )
            elapsed += time.perf_counter() - started
            _add_tokens(tokens, attempt_tokens)
            parsed = output_schema.model_validate_json(response)
            audit.record(
                {
                    "agent_name": agent_name,
                    "latency_ms": round(elapsed * 1000, 3),
                    "token_usage": tokens,
                    "input_hash": input_hash,
                    "output": parsed.model_dump(mode="json"),
                    "errors": [],
                    "attempt": attempt,
                }
            )
            return parsed, elapsed, tokens
        except (
            ValidationError,
            ValueError,
            RuntimeError,
            OSError,
            GoogleAPIError,
            LiteLLMAPIError,
        ) as exc:
            elapsed += time.perf_counter() - started
            last_error = _safe_error_summary(exc)
            audit.record(
                {
                    "agent_name": agent_name,
                    "latency_ms": round(elapsed * 1000, 3),
                    "token_usage": tokens,
                    "input_hash": input_hash,
                    "output": None,
                    "errors": [last_error],
                    "attempt": attempt,
                }
            )
        if attempt < MAX_AGENT_ATTEMPTS:
            await asyncio.sleep(0)
    raise AgentContractError(
        agent_name,
        MAX_AGENT_ATTEMPTS,
        last_error,
        elapsed,
        tokens,
    )


async def _collect_response(
    runner: Any,
    session_id: str,
    message: str,
) -> tuple[str, dict[str, int]]:
    """Collect final ADK text and usage metadata from a single attempt."""
    from google.genai import types as genai_types

    response = ""
    tokens = {"input_tokens": 0, "output_tokens": 0}
    async for event in runner.run_async(
        user_id="system",
        session_id=session_id,
        new_message=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message)],
        ),
    ):
        usage = getattr(event, "usage_metadata", None)
        if usage is None:
            llm_response = getattr(event, "llm_response", None)
            usage = getattr(llm_response, "usage_metadata", None)
        if usage is not None:
            tokens["input_tokens"] += int(
                getattr(usage, "prompt_token_count", 0) or 0
            )
            tokens["output_tokens"] += int(
                getattr(usage, "candidates_token_count", 0) or 0
            )
        if event.is_final_response() and event.content and event.content.parts:
            response = "".join(
                part.text for part in event.content.parts if getattr(part, "text", None)
            )
    if not response:
        raise RuntimeError("Agent returned no final text response.")
    return response, tokens


def _safe_error_summary(error: Exception) -> str:
    """Summarize errors without embedding untrusted input values in audit logs."""
    if isinstance(error, ValidationError):
        details = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in error.errors(include_input=False)
        ]
        return json.dumps(details, sort_keys=True)
    return mask_pii(f"{type(error).__name__}: {error}")


def _add_tokens(target: dict[str, int], source: dict[str, int]) -> None:
    """Add token counts without assuming providers expose usage metadata."""
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def _review_decision(decision: FinalDecisionOutput, reason: str) -> FinalDecisionOutput:
    """Convert a decision to an explicit abstention while retaining explanation."""
    ranked_reasons = [
        ReasonCode(
            code="HUMAN_REVIEW_REQUIRED",
            rank=1,
            description=reason,
        )
    ]
    ranked_reasons.extend(
        item.model_copy(update={"rank": rank})
        for rank, item in enumerate(decision.reason_codes, start=2)
    )
    return decision.model_copy(
        update={
            "decision": DecisionLabel.NEEDS_HUMAN_REVIEW,
            "reason_codes": ranked_reasons,
            "human_review_reason": reason,
            "explanation": f"{decision.explanation} Human review required: {reason}",
        }
    )


def _borderline_risk_reason(risk_score: float) -> str | None:
    """Route scores near prototype risk-band cutoffs to a human reviewer."""
    for threshold in (30.0, 60.0, 80.0):
        if abs(risk_score - threshold) <= 5.0:
            return f"Risk score is within five points of the {threshold:g} cutoff."
    return None


def _human_review_result(
    application_id: str,
    reason: str,
    processing_time: float,
    phase_latencies: dict[str, float],
    token_usage: dict[str, int],
) -> ProcessingResult:
    """Create a clear failure result for an application requiring human review."""
    return ProcessingResult(
        application_id=application_id,
        status=ApplicationStatus.NEEDS_HUMAN_REVIEW,
        decision=f"Automated processing could not safely complete. {reason}",
        processing_time=processing_time,
        timestamp=datetime.now(UTC).isoformat(),
        human_review_reason=reason,
        reason_codes=[
            {
                "code": "AGENT_CONTRACT_FAILURE",
                "rank": 1,
                "description": mask_pii(reason),
            }
        ],
        explanation=mask_pii(
            f"Automated processing could not safely complete. {reason}"
        ),
        phase_latencies=phase_latencies,
        token_usage=token_usage,
        next_steps=["Route this application to an authorized human reviewer."],
    )


def _status_for_decision(decision: str) -> ApplicationStatus:
    """Map a validated decision label to the public application status."""
    return {
        "approve": ApplicationStatus.APPROVED,
        "conditional": ApplicationStatus.CONDITIONALLY_APPROVED,
        "reject": ApplicationStatus.REJECTED,
        "needs_human_review": ApplicationStatus.NEEDS_HUMAN_REVIEW,
    }[decision]


def _percentage(value: float, total: int) -> str:
    """Format an observed metric or mark it unavailable when no data exists."""
    return f"{float(value) / total * 100:.1f}%" if total else "N/A"


def _parse_status(text: str) -> ApplicationStatus:
    """Map legacy free-text decisions to status for backward compatibility."""
    text_lower = text.lower()
    if "needs_human_review" in text_lower or "human review" in text_lower:
        return ApplicationStatus.NEEDS_HUMAN_REVIEW
    if "conditionally approved" in text_lower or "conditional approval" in text_lower:
        return ApplicationStatus.CONDITIONALLY_APPROVED
    if "rejected" in text_lower or "denied" in text_lower or "not approved" in text_lower:
        return ApplicationStatus.REJECTED
    if "approved" in text_lower:
        return ApplicationStatus.APPROVED
    if "additional information" in text_lower or "requires info" in text_lower:
        return ApplicationStatus.REQUIRES_INFO
    return ApplicationStatus.UNDER_REVIEW
