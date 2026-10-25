# Prototype Architecture

This repository is a learning prototype for agent orchestration. It does not
make real lending decisions, perform verified regulatory checks, or represent a
production loan platform.

## Request flow

```text
Application text
    |
    v
DocumentProcessingPipeline (sequential)
    DocumentIntake -> DataExtraction -> Validation
    |
    v
RiskAssessmentWorkflow
    Income, Credit, Employment, Collateral (parallel)
    -> RiskAggregator (sequential)
    |
    v
ApprovalWorkflow (sequential decision chain)
    RiskAnalyst -> ComplianceReviewer -> FinalUnderwriter
    |
    v
Pydantic-validated decision and JSON audit record
```

Document extraction is sequential because each step consumes prior context.
The four specialist risk analyses are independent and share the same input, so
they are represented as parallel tasks. Their outputs are then consolidated in
a dependent step. The authority handoff is a **sequential decision chain**, not
a separate handoff protocol: each reviewer runs after the previous reviewer.

## Reliability boundary

Agent contracts are defined with Pydantic models in `src/schemas.py`. Structured
outputs are validated at the orchestration boundary. Invalid output is retried
once (two total attempts); if it remains invalid, processing returns
`needs_human_review` rather than inferring a decision. Each phase records its
latency, available token usage, input hash, validated output, and errors in a
per-application JSON audit file.

The configured default is `anthropic/claude-sonnet-4-6`, used through LiteLLM.
The model identifier follows LiteLLM's Anthropic provider documentation:
[LiteLLM Anthropic provider](https://docs.litellm.ai/docs/providers/anthropic).
Set `LLM_MODEL` to an installed LiteLLM-supported provider/model identifier when
changing providers. Model calls require provider credentials.

## Important limitations

- The workflow uses LLM-generated assessments and prompts; it is not a
  validated credit-risk model or deterministic underwriting policy.
- A compliance agent response is not legal advice or proof of regulatory
  compliance.
- The in-memory ADK session service is process-local and is not durable.
- The audit log is a prototype artifact, not a tamper-evident or access-
  controlled compliance ledger.
- Evaluation on generated labels describes behavior on those synthetic cases
  only; it does not establish real-world accuracy, fairness, or suitability.
