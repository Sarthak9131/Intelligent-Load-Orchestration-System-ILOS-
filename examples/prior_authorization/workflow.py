"""Synthetic prior-authorization orchestration using ADK-style patterns."""

import asyncio
import hashlib
import time
from typing import Any

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from config.settings import LLM_MODEL
from src.agent_observability import after_agent, after_model, before_agent, on_model_error
from src.orchestrator import (
    AgentContractError,
    ApplicationAuditTrail,
    _run_agent,
)
from src.privacy import mask_pii

from .schemas import (
    AuthorizationStatus,
    CheckStatus,
    ClinicalCriteriaInput,
    ClinicalCriteriaOutput,
    CoverageEligibilityInput,
    CoverageEligibilityOutput,
    DocumentationCompletenessInput,
    DocumentationCompletenessOutput,
    FinalAuthorizationDecision,
    IntakeOutput,
    PriorAuthorizationRequest,
    ReviewerInput,
    ReviewerOutput,
)

MODEL = LiteLlm(model=LLM_MODEL)
_CALLBACKS = {
    "before_agent_callback": before_agent,
    "after_agent_callback": after_agent,
    "after_model_callback": after_model,
    "on_model_error_callback": on_model_error,
}


intake_agent = Agent(
    name="PriorAuthorizationIntakeAgent",
    model=MODEL,
    input_schema=PriorAuthorizationRequest,
    output_schema=IntakeOutput,
    instruction="""Normalize the synthetic request and identify missing data.
Return only JSON matching the output schema. Do not invent clinical facts.""",
    **_CALLBACKS,
)

clinical_criteria_agent = Agent(
    name="ClinicalCriteriaCheckAgent",
    model=MODEL,
    output_schema=ClinicalCriteriaOutput,
    instruction="""Evaluate only the synthetic criteria flags supplied in the
request. If criteria are absent or ambiguous, return insufficient. Do not
provide real medical advice. Return only JSON matching the output schema.""",
    **_CALLBACKS,
)

coverage_eligibility_agent = Agent(
    name="CoverageEligibilityCheckAgent",
    model=MODEL,
    output_schema=CoverageEligibilityOutput,
    instruction="""Evaluate only the synthetic coverage flags supplied in the
request. Unknown coverage must be insufficient. Return only JSON matching the
output schema.""",
    **_CALLBACKS,
)

documentation_completeness_agent = Agent(
    name="DocumentationCompletenessCheckAgent",
    model=MODEL,
    output_schema=DocumentationCompletenessOutput,
    instruction="""Check whether the synthetic clinical notes and prescriber
information flags are present. Return missing items explicitly. Return only
JSON matching the output schema.""",
    **_CALLBACKS,
)

parallel_checks = ParallelAgent(
    name="PriorAuthorizationParallelChecks",
    sub_agents=[
        clinical_criteria_agent,
        coverage_eligibility_agent,
        documentation_completeness_agent,
    ],
)

reviewer_agent = Agent(
    name="PriorAuthorizationReviewerAgent",
    model=MODEL,
    output_schema=ReviewerOutput,
    instruction="""Review the independent synthetic check results. Escalate
unknown or incomplete evidence to a human reviewer. Do not make a medical
judgment beyond the supplied synthetic flags. Return only JSON.""",
    **_CALLBACKS,
)

final_reviewer_agent = Agent(
    name="PriorAuthorizationFinalReviewerAgent",
    model=MODEL,
    output_schema=FinalAuthorizationDecision,
    instruction="""Issue a synthetic workflow result based on the prior
reviewer. If human review is required, provide a specific human_review_reason.
This is a prototype and not a coverage determination. Return only JSON.""",
    **_CALLBACKS,
)

reviewer_chain = SequentialAgent(
    name="PriorAuthorizationReviewerChain",
    sub_agents=[reviewer_agent, final_reviewer_agent],
)

prior_authorization_workflow = SequentialAgent(
    name="PriorAuthorizationWorkflow",
    sub_agents=[intake_agent, parallel_checks, reviewer_chain],
)


class PriorAuthorizationOrchestrator:
    """Run the synthetic scenario with a no-key stub or configured ADK model."""

    def __init__(self, mode: str = "stub") -> None:
        if mode not in {"stub", "adk"}:
            raise ValueError("mode must be either 'stub' or 'adk'.")
        self.mode = mode

    async def process(
        self,
        request: PriorAuthorizationRequest,
    ) -> FinalAuthorizationDecision:
        """Validate a synthetic request and run checks plus reviewer escalation."""
        validated_request = PriorAuthorizationRequest.model_validate(request)
        application_id = f"PA-{validated_request.request_id}"
        audit = ApplicationAuditTrail(application_id)
        masked_input = mask_pii(validated_request.model_dump_json())
        input_hash = hashlib.sha256(masked_input.encode("utf-8")).hexdigest()
        try:
            if self.mode == "stub":
                return await self._process_stub(
                    validated_request,
                    audit,
                    input_hash,
                )
            session_service = InMemorySessionService()
            runner = Runner(
                agent=prior_authorization_workflow,
                app_name="PriorAuthorizationWorkflow",
                session_service=session_service,
            )
            result, latency, tokens = await _run_agent(
                runner,
                f"prior-auth-{application_id}",
                masked_input,
                application_id,
                "PriorAuthorizationWorkflow",
                FinalAuthorizationDecision,
                audit,
                input_hash,
            )
            audit.record(
                {
                    "agent_name": "PriorAuthorizationWorkflow",
                    "latency_ms": round(latency * 1000, 3),
                    "token_usage": tokens,
                    "input_hash": input_hash,
                    "output": result.model_dump(mode="json"),
                    "errors": [],
                }
            )
            return result
        except AgentContractError as exc:
            reason = (
                f"{exc.agent_name} output failed validation after "
                f"{exc.attempts} attempts: {exc}"
            )
            audit.record(
                {
                    "agent_name": exc.agent_name,
                    "latency_ms": round(exc.latency * 1000, 3),
                    "token_usage": exc.token_usage,
                    "input_hash": input_hash,
                    "output": None,
                    "errors": [reason],
                }
            )
            return FinalAuthorizationDecision(
                request_id=validated_request.request_id,
                status=AuthorizationStatus.NEEDS_HUMAN_REVIEW,
                reason_codes=["AGENT_CONTRACT_FAILURE"],
                explanation="Automated review failed; route to a human reviewer.",
                human_review_reason=reason,
            )
        finally:
            audit.save()

    async def _process_stub(
        self,
        request: PriorAuthorizationRequest,
        audit: ApplicationAuditTrail,
        input_hash: str,
    ) -> FinalAuthorizationDecision:
        started = time.perf_counter()
        intake = _intake(request)
        _record(audit, "PriorAuthorizationIntakeAgent", intake, input_hash, started)

        clinical_input = ClinicalCriteriaInput(
            criteria_met=request.criteria_met,
            procedure_code=request.procedure_code,
            diagnosis_code=request.diagnosis_code,
        )
        coverage_input = CoverageEligibilityInput(
            coverage_active=request.coverage_active,
            procedure_covered=request.procedure_covered,
        )
        documentation_input = DocumentationCompletenessInput(
            clinical_notes_present=request.clinical_notes_present,
            prescriber_info_present=request.prescriber_info_present,
        )
        checks_started = time.perf_counter()
        clinical, coverage, documentation = await asyncio.gather(
            _check_clinical(clinical_input),
            _check_coverage(coverage_input),
            _check_documentation(documentation_input),
        )
        check_results = (
            ("ClinicalCriteriaCheckAgent", clinical),
            ("CoverageEligibilityCheckAgent", coverage),
            ("DocumentationCompletenessCheckAgent", documentation),
        )
        for agent_name, output in check_results:
            _record(
                audit,
                agent_name,
                output,
                input_hash,
                checks_started,
            )

        review_input = ReviewerInput(
            request_id=request.request_id,
            clinical=clinical,
            coverage=coverage,
            documentation=documentation,
        )
        reviewer_started = time.perf_counter()
        reviewer_result = _review(review_input)
        _record(
            audit,
            "PriorAuthorizationReviewerAgent",
            reviewer_result,
            input_hash,
            reviewer_started,
        )
        final_result = _final_review(request.request_id, reviewer_result)
        _record(
            audit,
            "PriorAuthorizationFinalReviewerAgent",
            final_result,
            input_hash,
            reviewer_started,
        )
        return final_result


def _intake(request: PriorAuthorizationRequest) -> IntakeOutput:
    missing = [
        field
        for field in (
            "coverage_active",
            "procedure_covered",
            "criteria_met",
            "clinical_notes_present",
            "prescriber_info_present",
        )
        if getattr(request, field) is None
    ]
    return IntakeOutput(
        request_id=request.request_id,
        complete=not missing,
        missing_fields=missing,
    )


async def _check_clinical(
    request: ClinicalCriteriaInput,
) -> ClinicalCriteriaOutput:
    if request.criteria_met is None:
        return ClinicalCriteriaOutput(
            status=CheckStatus.INSUFFICIENT,
            rationale="Synthetic clinical criteria were not supplied.",
        )
    return ClinicalCriteriaOutput(
        status=CheckStatus.PASS if request.criteria_met else CheckStatus.FAIL,
        rationale=(
            "Synthetic criteria flag is met."
            if request.criteria_met
            else "Synthetic criteria flag is not met."
        ),
    )


async def _check_coverage(
    request: CoverageEligibilityInput,
) -> CoverageEligibilityOutput:
    if request.coverage_active is None or request.procedure_covered is None:
        return CoverageEligibilityOutput(
            status=CheckStatus.INSUFFICIENT,
            rationale="Synthetic coverage information is incomplete.",
        )
    eligible = request.coverage_active and request.procedure_covered
    return CoverageEligibilityOutput(
        status=CheckStatus.PASS if eligible else CheckStatus.FAIL,
        rationale=(
            "Synthetic coverage flags are active and covered."
            if eligible
            else "Synthetic coverage flags indicate ineligibility."
        ),
    )


async def _check_documentation(
    request: DocumentationCompletenessInput,
) -> DocumentationCompletenessOutput:
    missing = [
        label
        for label, present in (
            ("clinical_notes", request.clinical_notes_present),
            ("prescriber_information", request.prescriber_info_present),
        )
        if present is not True
    ]
    status = CheckStatus.PASS if not missing else (
        CheckStatus.INSUFFICIENT
        if None in (
            request.clinical_notes_present,
            request.prescriber_info_present,
        )
        else CheckStatus.FAIL
    )
    return DocumentationCompletenessOutput(status=status, missing_items=missing)


def _review(request: ReviewerInput) -> ReviewerOutput:
    checks = (request.clinical.status, request.coverage.status, request.documentation.status)
    reason_codes = []
    if CheckStatus.INSUFFICIENT in checks:
        reason_codes.append("INSUFFICIENT_EVIDENCE")
    if request.documentation.status == CheckStatus.FAIL:
        reason_codes.append("DOCUMENTATION_INCOMPLETE")
    if request.clinical.status == CheckStatus.FAIL:
        reason_codes.append("CLINICAL_CRITERIA_NOT_MET")
    if request.coverage.status == CheckStatus.FAIL:
        reason_codes.append("COVERAGE_INELIGIBLE")
    if not reason_codes:
        reason_codes.append("SYNTHETIC_CHECKS_PASSED")

    if (
        CheckStatus.INSUFFICIENT in checks
        or request.documentation.status == CheckStatus.FAIL
    ):
        recommendation = AuthorizationStatus.NEEDS_HUMAN_REVIEW
        escalation_reason = (
            "A human reviewer must resolve incomplete or insufficient evidence."
        )
    elif CheckStatus.FAIL in checks:
        recommendation = AuthorizationStatus.DENIED
        escalation_reason = None
    else:
        recommendation = AuthorizationStatus.APPROVED
        escalation_reason = None
    return ReviewerOutput(
        recommendation=recommendation,
        reason_codes=reason_codes,
        explanation="Reviewer chain summarized the synthetic parallel checks.",
        escalation_reason=escalation_reason,
    )


def _final_review(
    request_id: str,
    reviewer: ReviewerOutput,
) -> FinalAuthorizationDecision:
    human_reason = (
        reviewer.escalation_reason
        if reviewer.recommendation == AuthorizationStatus.NEEDS_HUMAN_REVIEW
        else None
    )
    return FinalAuthorizationDecision(
        request_id=request_id,
        status=reviewer.recommendation,
        reason_codes=reviewer.reason_codes,
        explanation=(
            f"Synthetic prior-authorization result: "
            f"{reviewer.recommendation.value}. {reviewer.explanation}"
        ),
        human_review_reason=human_reason,
    )


def _record(
    audit: ApplicationAuditTrail,
    agent_name: str,
    output: Any,
    input_hash: str,
    started: float,
) -> None:
    audit.record(
        {
            "agent_name": agent_name,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "token_usage": {},
            "input_hash": input_hash,
            "output": output.model_dump(mode="json"),
            "errors": [],
        }
    )
