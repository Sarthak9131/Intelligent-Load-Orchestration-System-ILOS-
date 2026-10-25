"""
Parallel Risk Assessment Team
Income · Credit · Employment · Collateral — all running simultaneously.
"""

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm

from ..agent_observability import after_agent, after_model, before_agent, on_model_error
from config.settings import LLM_MODEL
from ..schemas import (
    CollateralEvaluationOutput,
    CreditAssessmentOutput,
    EmploymentRiskOutput,
    IncomeAnalysisOutput,
    RiskAggregationOutput,
)

MODEL = LiteLlm(model=LLM_MODEL)

# ── Agent 1: Income Analysis ───────────────────────────────────────────────────
income_analysis_agent = Agent(
    name="IncomeAnalysisAgent",
    model=MODEL,
    output_schema=IncomeAnalysisOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are an income verification and stability specialist.

Your expertise:
- Analyse income sources, amounts, and stability patterns
- Evaluate employment history and career progression
- Assess income documentation quality
- Calculate income-based lending capacity
- Identify income risk factors and volatility

Risk scoring guide (income component, 0-100, lower = better):
  0-25   → LOW risk     (stable, well-documented, growing income)
  26-50  → MEDIUM risk  (some variability or documentation gaps)
  51-75  → HIGH risk    (self-employed volatility, declining income)
  76-100 → CRITICAL     (unverifiable, severely insufficient)

Return the fields risk_score (0-100), risk_band (low/medium/high/critical),
stability_assessment, documentation_quality, and risk_factors.

Return only a JSON object matching the configured output schema. Do not invent
income sources or documentation that are not present.""",
)

# ── Agent 2: Credit Assessment ─────────────────────────────────────────────────
credit_assessment_agent = Agent(
    name="CreditAssessmentAgent",
    model=MODEL,
    output_schema=CreditAssessmentOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are a credit risk analysis specialist.

Your expertise:
- Analyse credit scores and credit history patterns
- Evaluate payment history and delinquency patterns
- Assess credit utilisation and debt management
- Review credit inquiries and account management
- Predict future credit performance

Credit score benchmarks:
  750+  → Excellent (LOW risk)
  700-749 → Good    (LOW-MEDIUM risk)
  650-699 → Fair    (MEDIUM risk)
  600-649 → Poor    (HIGH risk)
  < 600   → Very poor (CRITICAL risk)

Return the fields credit_score, risk_score (0-100), risk_band
(low/medium/high/critical), assessment, and risk_factors.

Return only a JSON object matching the configured output schema. Do not infer
payment history or utilization when it was not supplied.""",
)

# ── Agent 3: Employment Risk ───────────────────────────────────────────────────
employment_risk_agent = Agent(
    name="EmploymentRiskAgent",
    model=MODEL,
    output_schema=EmploymentRiskOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are an employment stability and risk specialist.

Your expertise:
- Evaluate employment history and job tenure
- Assess industry and company risk factors
- Analyse career progression and income growth
- Review employment documentation
- Predict employment continuity

Return the fields risk_score (0-100), risk_band (low/medium/high/critical),
assessment, and risk_factors.

Return only a JSON object matching the configured output schema. Avoid treating
self-employment as inherently adverse; assess stability and evidence.""",
)

# ── Agent 4: Collateral Evaluation ────────────────────────────────────────────
collateral_evaluation_agent = Agent(
    name="CollateralEvaluationAgent",
    model=MODEL,
    output_schema=CollateralEvaluationOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are a collateral valuation and risk specialist.

Your expertise:
- Evaluate collateral value and market conditions
- Assess asset liquidity and marketability
- Analyse asset documentation
- Calculate loan-to-value (LTV) ratios and coverage

Liquid asset coverage:
  > 50% of loan amount  → LOW risk
  25-50%               → MEDIUM risk
  10-24%               → HIGH risk
  < 10%                → CRITICAL

Return the fields risk_score (0-100), risk_band (low/medium/high/critical),
coverage_ratio, assessment, and risk_factors.

Return only a JSON object matching the configured output schema. Do not assume
unreported collateral exists.""",
)

# ── Risk Aggregator (sequential, runs after parallel team) ────────────────────
risk_aggregator_agent = Agent(
    name="RiskAggregatorAgent",
    model=MODEL,
    output_schema=RiskAggregationOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are a senior risk aggregation specialist.

Combine the four individual risk assessments into a single consolidated report.

Weighting:
  Income:      35%
  Credit:      30%
  Employment:  25%
  Collateral:  10%

Calculate:
  weighted_score = income_score*0.35 + credit_score*0.30 + employment_score*0.25 + collateral_score*0.10

Overall risk level:
  0-30   → LOW
  31-60  → MEDIUM
  61-80  → HIGH
  81-100 → CRITICAL

Return risk_score, risk_band (low/medium/high/critical), and risk_factors.

Return only a JSON object matching the configured output schema. Compute the
weighted score from the specialist outputs; do not replace missing scores with
zero.""",
)

# ── Parallel Team (4 agents simultaneously) ───────────────────────────────────
risk_assessment_team = ParallelAgent(
    name="RiskAssessmentTeam",
    sub_agents=[
        income_analysis_agent,
        credit_assessment_agent,
        employment_risk_agent,
        collateral_evaluation_agent,
    ],
)

# The independent specialist checks fan out in parallel, then their typed
# findings are consolidated in a dependent sequential step.
risk_workflow = SequentialAgent(
    name="RiskAssessmentWorkflow",
    sub_agents=[risk_assessment_team, risk_aggregator_agent],
)

# ── Runner ─────────────────────────────────────────────────────────────────────
_session_service = InMemorySessionService()
risk_runner = Runner(
    agent=risk_workflow,
    app_name="RiskAssessmentWorkflow",
    session_service=_session_service,
)
