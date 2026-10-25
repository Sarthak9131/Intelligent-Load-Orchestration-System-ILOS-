"""
Document Processing Sequential Pipeline
Intake → Data Extraction → Validation
"""

from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm

from ..agent_observability import after_agent, after_model, before_agent, on_model_error
from config.settings import LLM_MODEL
from ..schemas import (
    DataExtractionOutput,
    DocumentIntakeInput,
    DocumentIntakeOutput,
    ValidationOutput,
)

MODEL = LiteLlm(model=LLM_MODEL)

# ── Agent 1: Document Intake ───────────────────────────────────────────────────
document_intake_agent = Agent(
    name="DocumentIntakeAgent",
    model=MODEL,
    input_schema=DocumentIntakeInput,
    output_schema=DocumentIntakeOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are a document intake specialist for loan applications.

Your role:
- Receive loan application documents in various formats
- Identify document types (application form, income verification, bank statements,
  employment letter, tax returns, etc.)
- Parse text content and identify key sections
- Create an initial document inventory with clearly labelled sections
- Flag any obviously missing or corrupted documents

Return the following fields:
- documents: every document type identified
- missing_fields: known gaps
- data_quality_issues: inconsistent or incomplete information
- completeness_score: number from 0 to 100

Be thorough and systematic. Your output feeds directly into the data extraction step.
Return only a JSON object matching the configured output schema. Do not include
markdown fences or infer information that is not present.""",
)

# ── Agent 2: Data Extraction ───────────────────────────────────────────────────
data_extraction_agent = Agent(
    name="DataExtractionAgent",
    model=MODEL,
    output_schema=DataExtractionOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
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

Return the fields applicant_name, annual_income, monthly_income,
monthly_debts, debt_to_income_ratio, credit_score, loan_amount,
loan_to_income_ratio, employment_type, employment_years, savings,
loan_purpose, and evidence_notes. Ratios must be decimals, not percentages.
Use null when a field is unavailable.

Return only a JSON object matching the configured output schema. Use null for
unknown values and do not infer missing facts.""",
)

# ── Agent 3: Validation ────────────────────────────────────────────────────────
validation_agent = Agent(
    name="ValidationAgent",
    model=MODEL,
    output_schema=ValidationOutput,
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    after_model_callback=after_model,
    on_model_error_callback=on_model_error,
    instruction="""You are a loan application validation specialist.

Your role:
- Validate completeness of extracted loan application data
- Check internal consistency across all provided information
- Verify calculations (DTI, LTI, LTV)
- Identify missing required documents or information
- Assign a validation score (0-100) based on data completeness and quality

Return the fields is_valid, completeness_score, missing_fields,
inconsistencies, and requires_human_review. Set requires_human_review when
material fields are missing or conflicting.

Only mark VALID if completeness ≥ 80 and no critical inconsistencies. Return
only a JSON object matching the configured output schema.""",
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
