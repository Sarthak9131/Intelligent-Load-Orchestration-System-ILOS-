# Practical AI/ML Engineer Interview Roadmap

This is a coached, project-based path from beginner foundations to senior-level interview readiness. The loan-processing repository is the lab, not proof that you already know every topic. Work in order, commit your own changes, and explain each decision aloud. We can review one lab at a time in this chat.

## How to work through it

- Plan for 5 sessions a week, 60-90 minutes per session. Extend the calendar if you need more time; pass the gates, not the dates.
- For each topic: learn the minimum concept, implement it, test edge cases, inspect results, then explain tradeoffs without notes.
- Keep a learning log with four fields: hypothesis, experiment, result, next decision.
- Use synthetic or approved de-identified data only. Never put real applicant, patient, claims, or member data in this repository or in an external model prompt.
- The project is a multi-agent LLM workflow, not a trained predictive ML model. Do not claim it predicts default or is production-grade.
- Optum roles vary. Use the specific job description to weight healthcare, NLP/LLM, tabular ML, cloud, or MLOps topics. Healthcare examples here are interview practice, not legal advice.

## Progression

| Level | Target capability | Exit evidence |
|---|---|---|
| 0. Programming foundations | Read, change, and test Python code | Small pure functions with useful tests and clear explanations |
| 1. Data and statistics | Inspect data and reason about uncertainty | Reproducible data-quality and exploratory analysis |
| 2. Applied ML | Train and evaluate honest baselines | Versioned experiment with leakage controls and threshold rationale |
| 3. LLM and agent engineering | Build constrained, evaluated model-assisted steps | Typed outputs, golden-set evaluation, and failure handling |
| 4. Production engineering | Operate the system reliably and securely | Observable workflow with bounded resources, recovery, and auditability |
| 5. Senior ownership | Make and defend cross-functional technical decisions | System design, risk register, rollout plan, and leadership stories |

Senior readiness is demonstrated by judgment, tradeoff reasoning, and ownership; finishing a calendar is not a seniority credential.

## Level 0: Programming foundations (Weeks 1-3)

### Week 1: Python basics and financial functions

Learn variables, numbers, strings, booleans, conditionals, functions, imports, exceptions, and how to run a test. Read `src/models.py` and trace the DTI calculation.

**Lab:** add a small pure function for a fixed-rate monthly loan payment. Handle zero interest and reject invalid principal, annual rate, or term. Write tests for a normal case, zero-interest case, invalid inputs, and a known hand-calculated result.

**Interview check:** explain function inputs, output, edge cases, and why a pure function is easy to test.

### Week 2: Collections, types, and domain models

Learn lists, dictionaries, sets, dataclasses, enums, optional values, and type hints. Trace `LoanApplication` and `ProcessingResult` from construction to serialization.

**Lab:** write a validation function for application fields. Distinguish missing data from a valid zero, and avoid silently converting invalid input into a plausible value.

**Interview check:** explain why a domain model should represent state and invariants rather than serve as an unvalidated bag of fields.

### Week 3: Tests, debugging, and async I/O

Learn pytest assertions and fixtures, mocks, stack traces, logging, `async`/`await`, and the difference between I/O-bound concurrency and CPU parallelism.

**Lab:** add orchestrator tests with stubbed agent runners. Cover a successful workflow, an agent exception, empty output, and status parsing. Identify which tests are unit, integration, and contract tests.

**Interview check:** describe what `await` yields control for, and why adding `async` does not accelerate CPU-heavy work.

**Gate:** you can run the suite in the selected environment, explain a failing test, and add a regression test before changing behavior.

## Level 1: Data and statistics (Weeks 4-5)

### Week 4: Tabular data and quality

Learn CSV/Parquet concepts, schema checks, missingness, duplicates, outliers, categorical versus numeric fields, and train-time versus inference-time transformations.

**Lab:** create a small synthetic application dataset with a documented schema. Profile ranges, missing values, duplicates, and invalid rows. Keep generated examples obviously synthetic and do not treat them as evidence of model quality.

**Interview check:** explain how malformed or missing values can change both a model prediction and downstream policy.

### Week 5: Probability and experimental reasoning

Learn distributions, sampling, conditional probability, confidence intervals, correlation versus causation, and selection bias. Understand why a historical lending dataset may reflect prior policies rather than ground truth fairness.

**Lab:** define the target label, prediction timestamp, observation window, and outcome window for a hypothetical default dataset. Draw which fields are available at decision time; mark any later events as leakage.

**Interview check:** explain why random splitting can be misleading when data has time or member-level grouping.

**Gate:** you can describe the data-generating process and label limitations before discussing an algorithm.

## Level 2: Applied machine learning (Weeks 6-9)

Use an approved public dataset or carefully generated synthetic data for learning. Record dataset provenance and limitations. Do not report synthetic-data scores as real-world performance.

### Week 6: Baselines and splits

Learn supervised classification, feature/label separation, chronological splits, cross-validation, and reproducible seeds.

**Lab:** build a preprocessing-plus-logistic-regression baseline for a clearly defined binary outcome. Fit preprocessing only on training data. Compare a trivial baseline to the model.

**Interview check:** justify the split strategy and state what population your test score estimates.

### Week 7: Metrics and decision thresholds

Learn confusion matrices, precision, recall, specificity, F1, ROC-AUC, PR-AUC, and threshold selection. Accuracy is not enough under class imbalance.

**Lab:** compare thresholds and quantify false positives and false negatives. State who is harmed by each error and how operating constraints affect the choice.

**Interview check:** explain why a good ranking metric does not determine a safe business threshold.

### Week 8: Feature engineering and model comparison

Learn leakage-safe pipelines, categorical encoding, scaling where appropriate, regularization, tree models, and error analysis.

**Lab:** compare logistic regression with one tree-based model using the same split and evaluation protocol. Inspect errors by important slices and preserve a baseline.

**Interview check:** explain the accuracy, latency, interpretability, and maintenance tradeoff between the models.

### Week 9: Calibration, fairness, and explainability

Learn probability calibration, subgroup evaluation, intersectional analysis, proxy variables, feature importance limitations, and local explanations. Fairness must be reviewed with domain experts and applicable policy.

**Lab:** check calibration and report performance/error rates across appropriate groups when lawful data and review are available. If group labels are unavailable, document that fairness could not be established; do not infer protected attributes.

**Interview check:** explain why deleting a protected feature alone does not eliminate proxy discrimination.

**Gate:** deliver a short model card with intended use, data limits, split design, metrics, threshold, subgroup analysis limits, failure modes, and human-review policy.

## Level 3: LLM and agent engineering (Weeks 10-12)

### Week 10: Structured extraction

Learn tokens, context limits, temperature, prompting, structured outputs, schema validation, and the distinction between an LLM and a predictive ML model.

**Lab:** define a typed schema for extracted application data, validate required fields and numeric bounds, and represent unknown values explicitly. Do not infer a missing fact from plausibility.

**Interview check:** identify which parts need an LLM and which should be deterministic code.

### Week 11: Evaluation and grounded generation

Learn golden datasets, annotation guidance, field-level exact match, precision/recall, semantic evaluation limits, regression tests, and retrieval grounding.

**Lab:** make a versioned set of synthetic document snippets with expected extracted fields. Evaluate field-level errors and create tests for ambiguous and contradictory evidence.

**Interview check:** explain how you would know a prompt change improved the system rather than just changed its style.

### Week 12: Agent boundaries and attacks

Learn tool permissions, prompt injection, untrusted document content, context isolation, citation/evidence provenance, abstention, and human escalation.

**Lab:** treat instructions inside uploaded text as untrusted data. Add an adversarial test document and ensure extracted values retain a source/evidence reference and cannot trigger tools or policy changes.

**Interview check:** walk through a prompt-injection attempt and explain defense in depth.

**Gate:** no agent output can directly authorize a decision; malformed, conflicting, or unsupported evidence yields an explicit abstain/review result.

## Level 4: Production engineering (Weeks 13-16)

### Week 13: Contracts and deterministic policy

Learn schema versioning, typed boundaries, idempotency, policy separation, and backwards compatibility.

**Lab:** replace free-text decision status parsing with a validated typed decision contract. Calculate weighted risk in deterministic code and test thresholds and boundary values.

**Interview check:** explain why model-generated numbers and policy decisions require independent validation.

### Week 14: Reliability and async orchestration

Learn deadlines, bounded concurrency, retries with exponential backoff and jitter, rate limits, circuit breakers, cancellation, partial failure, and at-least-once delivery.

**Lab:** fan out independent risk checks under a concurrency limit and deadline. Define which failures are retryable, how duplicates are handled, and when to route to manual review.

**Interview check:** explain why retries can worsen an outage and how idempotency prevents duplicate effects.

### Week 15: Observability and cost

Learn structured logs, traces, metrics, percentiles, SLOs, token/cost accounting, redaction, and alert design.

**Lab:** add correlation IDs and per-stage latency/error metrics. Separate successful processing time from failed requests and remove synthetic compliance claims. Never log raw sensitive documents.

**Interview check:** propose dashboards and alerts that tell an operator what action to take.

### Week 16: Security, privacy, and release process

Learn least privilege, encryption, secrets handling, retention, access auditing, dependency risks, threat modeling, deployment gates, rollback, and privacy-by-design. For healthcare contexts, be ready to discuss protected health information (PHI), approved data paths, and organizational compliance review; do not claim a demo is HIPAA-compliant.

**Lab:** write a threat model and data-flow diagram. Specify allowed data, storage, retention, access, model-provider boundary, audit fields, and incident response assumptions.

**Interview check:** explain how you would prevent PHI from entering an unauthorized model, log, or analytics sink.

**Gate:** production-readiness review covering privacy, model quality, reliability, cost, human oversight, and rollback.

## Level 5: Senior engineer practice (Weeks 17-20)

### Week 17: System design

Practice requirements clarification, traffic estimates, APIs, data stores, queues, workflow state, failure modes, privacy boundaries, and tradeoffs.

**Lab:** design a document-intelligence service for a healthcare workflow using synthetic/de-identified data. Include manual review, audit, deletion/retention policy, and a degraded mode.

### Week 18: MLOps and lifecycle ownership

Learn model registry concepts, data/model versions, reproducibility, offline/online skew, canary and shadow releases, drift monitoring, rollback, and retraining gates.

**Lab:** write a release checklist and rollback plan for a model and prompt update. Specify what evidence must pass before traffic increases.

### Week 19: Decision records and technical leadership

Learn ADRs, prioritization, incident reviews, stakeholder communication, risk acceptance, mentoring, and influencing without authority.

**Lab:** write a one-page ADR choosing between a single workflow agent and specialist agents. Include alternatives, cost/latency, correlated failure, operational burden, and a revisit trigger.

### Week 20: Interview simulation

Practice a 45-minute coding problem, 45-minute ML case study, 45-minute system design, and behavioral stories. Record yourself; review correctness, assumptions, communication, and tradeoffs.

**Lab:** present the project in 2 minutes, answer five levels of follow-up questions, and clearly separate what is implemented, what is measured, and what is proposed.

**Senior gate:** defend an end-to-end design, surface unknowns, quantify tradeoffs, plan rollout/rollback, communicate risk, and take ownership of operational outcomes.

## First lab: start here

Do this before studying more theory. Implement a pure monthly-payment function in a new module, for example `src/loan_math.py`, then add tests in the existing test suite.

Requirements:

- Inputs: principal, annual percentage rate as a decimal (for example `0.06`), and number of monthly payments.
- Reject non-positive principal, negative rate, and non-positive term with `ValueError`.
- At zero interest, payment is principal divided by the number of payments.
- At positive interest, use the standard fixed-payment amortization formula.
- Test a zero-rate case, a known positive-rate case, invalid input for each argument, and a result that is finite and positive.
- Keep the function independent of Google ADK and external APIs.

When you finish, share the function and tests. I’ll review correctness, test quality, edge cases, and how you explain it as an interview answer. Do not add a dependency for this exercise.

## Interview answer framework

For a technical question, answer in this order: clarify assumptions, state the approach, explain why it fits, name the main failure mode, describe how you would test/measure it, then give one tradeoff. For project questions, distinguish implemented behavior from intended design and measured results.

## Role-specific emphasis for Optum

Start with the exact job description. Depending on the team, prepare to connect your skills to healthcare data, claims or clinical workflows, NLP/LLMs, predictive modeling, cloud platforms, and production monitoring. Emphasize privacy, reliability, explainability, bias evaluation, and human oversight. The loan project is a regulated-workflow practice case; do not imply it processes healthcare records or meets healthcare compliance requirements.
