"""
Parallel Risk Assessment Team
Income · Credit · Employment · Collateral — all running simultaneously.
"""

import os
from google.adk.agents import Agent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm

MODEL = LiteLlm(model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6"))

# ── Agent 1: Income Analysis ───────────────────────────────────────────────────
income_analysis_agent = Agent(
    name="IncomeAnalysisAgent",
    model=MODEL,
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

Output:
INCOME ANALYSIS:
  Income Sources:
  Stability Assessment:
  Documentation Quality:
  Lending Capacity:
  Risk Factors:
  INCOME RISK SCORE: X/100
  INCOME RISK LEVEL: LOW / MEDIUM / HIGH / CRITICAL""",
)

# ── Agent 2: Credit Assessment ─────────────────────────────────────────────────
credit_assessment_agent = Agent(
    name="CreditAssessmentAgent",
    model=MODEL,
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

Output:
CREDIT ASSESSMENT:
  Credit Score:
  Payment History:
  Credit Utilisation:
  Delinquency History:
  Prediction:
  CREDIT RISK SCORE: X/100
  CREDIT RISK LEVEL: LOW / MEDIUM / HIGH / CRITICAL""",
)

# ── Agent 3: Employment Risk ───────────────────────────────────────────────────
employment_risk_agent = Agent(
    name="EmploymentRiskAgent",
    model=MODEL,
    instruction="""You are an employment stability and risk specialist.

Your expertise:
- Evaluate employment history and job tenure
- Assess industry and company risk factors
- Analyse career progression and income growth
- Review employment documentation
- Predict employment continuity

Output:
EMPLOYMENT ANALYSIS:
  Current Role & Tenure:
  Employment Type: (permanent / contract / self-employed)
  Industry Stability:
  Career Progression:
  Risk Factors:
  EMPLOYMENT RISK SCORE: X/100
  EMPLOYMENT RISK LEVEL: LOW / MEDIUM / HIGH / CRITICAL""",
)

# ── Agent 4: Collateral Evaluation ────────────────────────────────────────────
collateral_evaluation_agent = Agent(
    name="CollateralEvaluationAgent",
    model=MODEL,
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

Output:
COLLATERAL ASSESSMENT:
  Assets Identified:
  Liquid Asset Coverage:
  Asset Quality:
  LTV Ratio (if applicable):
  Risk Factors:
  COLLATERAL RISK SCORE: X/100
  COLLATERAL RISK LEVEL: LOW / MEDIUM / HIGH / CRITICAL""",
)

# ── Risk Aggregator (sequential, runs after parallel team) ────────────────────
risk_aggregator_agent = Agent(
    name="RiskAggregatorAgent",
    model=MODEL,
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

Output:
CONSOLIDATED RISK REPORT:
  Income Risk Score:     X/100
  Credit Risk Score:     X/100
  Employment Risk Score: X/100
  Collateral Risk Score: X/100
  WEIGHTED OVERALL SCORE: X/100
  OVERALL RISK LEVEL: LOW / MEDIUM / HIGH / CRITICAL
  Key Risk Factors:
  Mitigating Factors:
  Preliminary Recommendation: APPROVE / CONDITIONAL / REJECT""",
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

# ── Runner ─────────────────────────────────────────────────────────────────────
_session_service = InMemorySessionService()
risk_runner = Runner(
    agent=risk_assessment_team,
    app_name="RiskAssessmentTeam",
    session_service=_session_service,
)
