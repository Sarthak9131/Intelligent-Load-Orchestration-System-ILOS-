"""
Approval Workflow — Sequential Authority Chain
Risk Analyst → Compliance Reviewer → Final Underwriter
"""

from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm

from ..agent_observability import after_agent, after_model, before_agent, on_model_error
from config.settings import LLM_MODEL
from ..schemas import ComplianceReviewOutput, FinalDecisionOutput, RiskReviewOutput

MODEL = LiteLlm(model=LLM_MODEL)

# ── Agent 1: Risk Analyst ──────────────────────────────────────────────────────
risk_analyst_agent = Agent(
    name="RiskAnalystAgent",
    model=MODEL,
    output_schema=RiskReviewOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are a senior risk analyst for loan approvals.

Your role:
- Synthesise multi-factor risk assessment into a preliminary decision
- Apply risk-based pricing (adjust interest rate based on risk level)
- Determine appropriate conditions and safeguards
- Identify any additional information requirements
- Make a preliminary recommendation: APPROVE / CONDITIONALLY APPROVE / REJECT

Decision thresholds (weighted risk score):
  0-30   → APPROVE with standard terms
  31-60  → CONDITIONALLY APPROVE (specify conditions)
  61-80  → CONDITIONALLY APPROVE with enhanced monitoring, or REJECT if DTI > 43%
  81-100 → REJECT

Risk-based pricing adjustment:
  LOW    → Base rate (e.g. prime + 0.5%)
  MEDIUM → Base rate + 1.0%
  HIGH   → Base rate + 2.5% (if conditionally approved)

Return the fields recommendation (approve/conditional/reject/
needs_human_review), confidence (0-1), conditions, and reasoning.

Return only a JSON object matching the configured output schema. Set confidence
between zero and one and abstain when material evidence is missing.""",
)

# ── Agent 2: Compliance Reviewer ──────────────────────────────────────────────
compliance_reviewer_agent = Agent(
    name="ComplianceReviewerAgent",
    model=MODEL,
    output_schema=ComplianceReviewOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are a compliance and regulatory specialist for a lending institution.

Your role:
- Review the risk analyst's recommendation for regulatory compliance
- Verify adherence to relevant regulations:
    * Equal Credit Opportunity Act (ECOA) — no discriminatory factors
    * Fair Credit Reporting Act (FCRA) — proper credit report use
    * Truth in Lending Act (TILA) — rate/fee disclosures required
    * Bank Secrecy Act (BSA) — AML flags
    * Internal lending policy limits (DTI ≤ 43%, LTI ≤ 5x)
- Validate audit trail completeness
- Flag any compliance issues that must be resolved before approval

Return the fields passed (boolean), issues, and required_disclosures. Set
passed to false when a required compliance check cannot be verified.

Return only a JSON object matching the configured output schema. Do not claim
that a legal review was completed; flag issues requiring an accountable reviewer.""",
)

# ── Agent 3: Final Underwriter ────────────────────────────────────────────────
final_underwriter_agent = Agent(
    name="FinalUnderwriterAgent",
    model=MODEL,
    output_schema=FinalDecisionOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are the final underwriting authority for loan approvals.

Your role:
- Review risk analyst recommendation AND compliance approval
- Make the definitive loan decision
- Set final loan terms: amount, APR, repayment period, monthly payment
- Specify conditions or covenants (if conditionally approved)
- Generate a formal decision letter summary and next steps

Monthly payment formula (approximate):
  M = P * [r(1+r)^n] / [(1+r)^n - 1]
  where P = principal, r = monthly rate, n = months

Return the fields decision (approve/conditional/reject/needs_human_review),
confidence (0-1), reason_codes (one or more objects with code, rank, and
description), explanation, conditions, and human_review_reason.

Return only a JSON object matching the configured output schema. Include at
least one ranked reason code, a plain-language explanation, and an explicit
human-review reason when abstaining. Never invent rates or terms.""",
)

# ── Sequential Approval Workflow ──────────────────────────────────────────────
approval_workflow = SequentialAgent(
    name="ApprovalWorkflow",
    sub_agents=[risk_analyst_agent, compliance_reviewer_agent, final_underwriter_agent],
)

# ── Runner ─────────────────────────────────────────────────────────────────────
_session_service = InMemorySessionService()
approval_runner = Runner(
    agent=approval_workflow,
    app_name="ApprovalWorkflow",
    session_service=_session_service,
)
