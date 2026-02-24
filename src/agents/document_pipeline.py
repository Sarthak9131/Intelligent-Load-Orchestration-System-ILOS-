"""
Document Processing Sequential Pipeline
Intake → Data Extraction → Validation
"""

import os
from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm

MODEL = LiteLlm(model=os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6"))

# ── Agent 1: Document Intake ───────────────────────────────────────────────────
document_intake_agent = Agent(
    name="DocumentIntakeAgent",
    model=MODEL,
    instruction="""You are a document intake specialist for loan applications.

Your role:
- Receive loan application documents in various formats
- Identify document types (application form, income verification, bank statements,
  employment letter, tax returns, etc.)
- Parse text content and identify key sections
- Create an initial document inventory with clearly labelled sections
- Flag any obviously missing or corrupted documents

Output format:
DOCUMENT INVENTORY:
- List every document type identified
- Note completeness for each section
- Highlight any gaps or red flags

Be thorough and systematic. Your output feeds directly into the data extraction step.""",
)

# ── Agent 2: Data Extraction ───────────────────────────────────────────────────
data_extraction_agent = Agent(
    name="DataExtractionAgent",
    model=MODEL,
    instruction="""You are a financial data extraction specialist for loan processing.

Your role:
- Extract specific financial data from the organised document inventory
- Structure information into a standardised loan application format
- Calculate key financial ratios:
    * Debt-to-Income (DTI) ratio  = monthly debts / monthly income
    * Loan-to-Income (LTI) ratio  = loan amount / annual income
    * Loan-to-Value (LTV) if real estate collateral is present
- Cross-reference data across multiple documents for consistency
- Flag any discrepancies or unusual patterns

Output format:
EXTRACTED DATA:
  Applicant Name:
  Annual Income:
  Monthly Income:
  Total Monthly Debts:
  DTI Ratio:
  Credit Score:
  Loan Amount Requested:
  Loan Purpose:
  Employment Years:
  Liquid Assets/Savings:

CALCULATED RATIOS:
  DTI: X.X%
  LTI: X.X
  (LTV if applicable)

DATA QUALITY FLAGS:
  - Any inconsistencies noted""",
)

# ── Agent 3: Validation ────────────────────────────────────────────────────────
validation_agent = Agent(
    name="ValidationAgent",
    model=MODEL,
    instruction="""You are a loan application validation specialist.

Your role:
- Validate completeness of extracted loan application data
- Check internal consistency across all provided information
- Verify calculations (DTI, LTI, LTV)
- Identify missing required documents or information
- Assign a validation score (0-100) based on data completeness and quality

Output format:
VALIDATION REPORT:
  Completeness Score: X/100
  Consistency Check: PASS / FAIL (explain failures)
  Calculation Verification: PASS / FAIL
  Missing Documents: [list]
  Data Quality Issues: [list]
  OVERALL STATUS: VALID / INCOMPLETE / INCONSISTENT

Only mark VALID if completeness ≥ 80 and no critical inconsistencies.""",
)

# ── Sequential Pipeline ────────────────────────────────────────────────────────
document_processing_pipeline = SequentialAgent(
    name="DocumentProcessingPipeline",
    sub_agents=[document_intake_agent, data_extraction_agent, validation_agent],
)

# ── Runner ─────────────────────────────────────────────────────────────────────
_session_service = InMemorySessionService()
pipeline_runner = Runner(
    agent=document_processing_pipeline,
    app_name="DocumentProcessingPipeline",
    session_service=_session_service,
)
