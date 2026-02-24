"""
Approval Workflow — Sequential Authority Chain
Risk Analyst → Compliance Reviewer → Final Underwriter
"""

import os
from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm

MODEL = LiteLlm(model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6"))

# ── Agent 1: Risk Analyst ──────────────────────────────────────────────────────
risk_analyst_agent = Agent(
    name="RiskAnalystAgent",
    model=MODEL,
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

Output:
RISK ANALYST DECISION:
  Preliminary Recommendation: APPROVE / CONDITIONAL / REJECT
  Suggested Interest Rate Adjustment:
  Conditions (if any):
  Reasoning:
  Additional Information Needed (if any):""",
)

# ── Agent 2: Compliance Reviewer ──────────────────────────────────────────────
compliance_reviewer_agent = Agent(
    name="ComplianceReviewerAgent",
    model=MODEL,
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

Output:
COMPLIANCE REVIEW:
  ECOA Check:         PASS / FAIL
  FCRA Check:         PASS / FAIL
  TILA Requirements:  PASS / FAIL (required disclosures noted)
  BSA/AML Check:      PASS / FAIL
  Policy Limits:      PASS / FAIL
  Audit Trail:        COMPLETE / INCOMPLETE
  COMPLIANCE STATUS:  APPROVED / CONDITIONAL / BLOCKED
  Issues to Resolve (if any):
  Required Disclosures:""",
)

# ── Agent 3: Final Underwriter ────────────────────────────────────────────────
final_underwriter_agent = Agent(
    name="FinalUnderwriterAgent",
    model=MODEL,
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

Output:
═══════════════════════════════════════════
FINAL UNDERWRITING DECISION
Application ID: [from context]
Date: [today]
═══════════════════════════════════════════
DECISION: APPROVED / CONDITIONALLY APPROVED / REJECTED

LOAN TERMS (if approved):
  Principal Amount:   $X,XXX
  Annual Percentage Rate (APR): X.XX%
  Term:               XX months
  Estimated Monthly Payment: $X,XXX.XX
  Conditions:         [none / list]

REASONING:
  [concise explanation referencing risk score and compliance]

NEXT STEPS:
  1.
  2.
  3.

Underwriter Authority: Final Decision
═══════════════════════════════════════════""",
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
