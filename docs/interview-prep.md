# AI/ML Engineer Interview Workbook

This workbook uses the loan-processing project as the central case study. Study the sections in order and practice explaining the system without reading the code.

## 1. Your 90-second project explanation

> I built an asynchronous multi-agent loan-processing workflow. It accepts unstructured application information, runs document intake, extraction, and validation sequentially, then evaluates income, credit, employment, and collateral risk in parallel. A final sequential workflow performs risk analysis, compliance review, and underwriting. The design uses sequential execution when downstream steps depend on prior output, and parallel execution when analyses are independent. I track operational metrics and return an auditable decision object. For production, I would replace free-text contracts with validated structured outputs, make policy checks deterministic, add durable state and tracing, and introduce fairness, privacy, and model-quality monitoring.

Keep the last sentence ready. It shows engineering judgment instead of presenting an LLM demo as an automated authority.

## 2. Learn the project from the inside out

### Request flow

1. `main.py` creates an orchestrator and submits three sample applications.
2. `LoanProcessingOrchestrator.process_loan_application` creates an application ID and starts a timer.
3. The document pipeline runs intake -> extraction -> validation.
4. The risk team runs four independent analyses concurrently.
5. The approval workflow runs risk analyst -> compliance reviewer -> final underwriter.
6. `_parse_status` maps the final free-text response to an enum.
7. `_update_metrics` updates counts, rolling latency, and the dashboard.

### Important domain formulas

- Monthly income = annual income / 12
- DTI = monthly debt / monthly income
- LTI = requested loan amount / annual income
- Weighted risk score = `0.35 * income + 0.30 * credit + 0.25 * employment + 0.10 * collateral`

Be able to calculate Sarah Chen's DTI by hand: `2,850 / (165,000 / 12)`, approximately 20.7%.

### What each implementation layer demonstrates

- `src/models.py`: typed domain concepts, enums, derived features, serialization.
- `src/agents/document_pipeline.py`: sequential dependency management and extraction prompts.
- `src/agents/risk_team.py`: independent specialist analysis and aggregation design.
- `src/agents/approval_workflow.py`: authority boundaries, compliance gates, and explainability.
- `src/orchestrator.py`: workflow composition, IDs, timing, error boundary, and metrics.
- `tests/test_loan_processing.py`: unit tests for calculations, parsing, serialization, and metrics.

## 3. Fundamentals to learn from scratch

### Python and software engineering

Know functions, classes, dataclasses, enums, type hints, exceptions, context managers, imports, and dependency injection. Explain why `async def` is useful here: model calls are I/O-bound, so an event loop can make progress on other independent work while one call waits. It does not make CPU-heavy work faster.

Know the difference between:

- Unit tests: one function or class in isolation.
- Integration tests: multiple workflow components together.
- Contract tests: verify that an agent response matches the schema expected by the next component.
- Load tests: measure latency, throughput, concurrency, and failure behavior.

### Machine learning

Prepare these concepts with a lending example:

- Classification: predict default/no default.
- Regression: estimate loss amount or probability of default.
- Precision: of predicted risky cases, how many are truly risky.
- Recall: of all truly risky cases, how many are detected.
- Calibration: whether a predicted 10% default probability defaults about 10% of the time.
- Data leakage: using information unavailable at decision time.
- Class imbalance: default is usually rarer than repayment; accuracy alone is misleading.
- Train/validation/test split: fit, tune, and evaluate without contaminating the final estimate.
- Drift: changes in applicant population or economic conditions that reduce model validity.

For credit decisions, discuss threshold tradeoffs explicitly. A false negative can create financial loss; a false positive can deny access to credit. The right threshold depends on policy, cost, fairness, and regulatory constraints.

### LLM and agent systems

Know when to use an LLM and when not to. LLMs are useful for document understanding, classification of messy text, and generating explanations. Deterministic code should own arithmetic, policy thresholds, eligibility rules, authorization, and final enforcement.

Know these failure modes:

- Hallucinated or missing fields.
- Prompt injection inside uploaded documents.
- Non-deterministic wording that breaks downstream parsing.
- Context-window growth and irrelevant history.
- Provider outages, timeouts, rate limits, and partial results.
- Sensitive data leakage through prompts or logs.
- Correlated errors across multiple agents using the same model.

Mitigations include schema-constrained output, input sanitization, least-privilege tools, timeouts and retries with backoff, idempotency keys, redaction, human review, grounded retrieval, and trace-level evaluation.

## 4. Questions you should expect

### Architecture

**Why sequential and parallel execution?**

Extraction depends on organized documents, so that part is sequential. Income, credit, employment, and collateral use the same input and are independent, so parallel execution reduces wall-clock time from roughly the sum of call durations to the slowest call plus coordination overhead.

**How would you make this production-ready?**

Use durable workflow state instead of in-memory sessions, structured schemas between stages, deterministic policy services, a queue and worker model, bounded concurrency, deadlines, retries, circuit breakers, idempotency, audit events, encryption, access control, observability, and a manual-review path.

**What happens if one risk agent fails?**

Do not silently treat missing output as low risk. Return a typed partial result, retry safe failures, record the missing dimension, and route the application to manual review or a conservative policy outcome.

### ML and evaluation

**How would you evaluate this system?**

Separate component and end-to-end evaluation. For extraction, measure field-level precision, recall, and exact match. For risk models, measure AUROC or PR-AUC, calibration, false-positive/false-negative rates, and subgroup metrics. For the workflow, measure decision agreement with expert underwriters, latency, cost, abstention rate, audit completeness, and regression performance on a versioned golden set.

**How would you test fairness?**

Define protected groups according to applicable law and policy, exclude protected attributes from impermissible decision logic, inspect proxy features, compare approval/error/calibration metrics by group, test intersectional groups, document legitimate business reasons, and require compliance/legal review. Fairness is not proved by simply deleting a sensitive column.

**Would you let an LLM approve a loan?**

No, not as an uncontrolled authority. Use it for extraction and analyst assistance, while deterministic policy, validated risk models, compliance controls, and an accountable human or governed decision service control approval. The system should be able to abstain.

### Coding and debugging

Practice implementing:

- A robust amortized-loan-payment function with zero-interest and invalid-input tests.
- A typed `RiskAssessment` parser that rejects malformed scores.
- An async fan-out/fan-in function with bounded concurrency and per-task timeouts.
- A rolling metrics class that computes averages without mixing failed requests into successful latency.
- A redaction function for applicant names, account numbers, and raw document text in logs.

## 5. Project gaps to discuss honestly

These are not reasons to hide the project; they are strong improvement prompts.

1. `risk_aggregator_agent` is defined but is not included in `risk_assessment_team`, so the documented weighted consolidated score is not guaranteed to be produced.
2. The orchestrator infers status from free text. A phrase such as `not approved` can be misclassified, and arbitrary model wording can break the parser.
3. Compliance score is synthetic: `_update_metrics` always adds `97.5`, so it is not an observed compliance metric.
4. The documented settings for concurrency, timeout, and thresholds are not enforced by the orchestrator.
5. `InMemorySessionService` is unsuitable for restart recovery or multiple workers.
6. Exceptions are converted into a user-facing result, but there is no typed error category, retry policy, or manual-review event.
7. The current tests do not exercise real runner integration, parallel failure, malformed model output, prompt injection, or sensitive-data handling.
8. The README performance table contains claims that should be labeled as targets or benchmark results only after measurement.

A strong answer is: "I would fix the contract and policy boundary first, because a fast system that can produce an ambiguous or unauditable decision is not safe for lending."

## 6. Four-week preparation plan

### Week 1: Python and project fluency

Read one module per day. Trace one sample application on paper. Practice dataclasses, async/await, exceptions, pytest fixtures, mocking, and complexity analysis. Explain every function in `models.py` and `orchestrator.py` aloud.

### Week 2: ML and data

Study classification, metrics, calibration, feature engineering, leakage, imbalance, cross-validation, drift, and explainability. Design a tabular default-risk experiment: define the label and decision time, split by time, establish a logistic-regression baseline, compare a tree model, calibrate probabilities, and inspect subgroup metrics.

### Week 3: LLM production systems

Practice structured generation, retrieval grounding, prompt-injection defenses, token/cost estimation, caching, retries, rate limits, tracing, evaluation datasets, and human-in-the-loop design. Draw the failure paths for each project phase.

### Week 4: Optum-style interview practice

Prepare STAR stories for ownership, ambiguity, debugging, disagreement, model failure, and an ethical decision. Practice a 45-minute system design: "Design a compliant healthcare or financial document intelligence platform." End every design with privacy, reliability, monitoring, fairness, and rollback.

## 7. Daily practice loop

Spend 20 minutes on fundamentals, 20 minutes implementing or testing one small change, and 20 minutes explaining the tradeoffs aloud. Keep a notebook with: assumption, metric, failure mode, mitigation, and one follow-up experiment.

For this project, your first practical improvement should be to introduce a typed result schema for every agent and a deterministic aggregation/policy layer. That gives you a concrete before/after story for the interview.

## 8. Final checklist

- Explain the full request flow in 90 seconds.
- Calculate DTI, LTI, and the weighted risk score without a calculator.
- Explain async I/O versus parallel CPU work.
- Distinguish an LLM agent from a predictive ML model.
- Name at least five failure modes and their mitigations.
- Describe precision, recall, calibration, drift, and leakage.
- Explain why financial and healthcare data require least privilege, auditability, and human oversight.
- Acknowledge the project's gaps and propose a prioritized fix.
- Solve one Python problem while discussing complexity and tests.
- Give one concise STAR story for a difficult engineering decision.
