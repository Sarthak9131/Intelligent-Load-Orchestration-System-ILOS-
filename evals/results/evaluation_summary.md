# Synthetic Loan Evaluation

- Cases: 50
- Repeated runs per case: 3
- Mode: `stub`
- Model pricing reference: `anthropic/claude-sonnet-4-6`
- Labels are synthetic policy-derived targets, not historical outcomes.

## Classification metrics

- Decision accuracy: 0.7000
- Token cost estimate: $0.57386700

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| approve | 1.0000 | 0.8667 | 0.9286 | 15 |
| conditional | 0.5833 | 1.0000 | 0.7368 | 21 |
| reject | 1.0000 | 0.0714 | 0.1333 | 14 |

### Confusion matrix

| Actual \ Predicted | approve | conditional | reject |
|---|---:|---:|---:|
| approve | 13 | 2 | 0 |
| conditional | 0 | 21 | 0 |
| reject | 0 | 13 | 1 |

## Repeat consistency

- All repeats identical: 1.0000
- Mean pairwise decision agreement: 1.0000

## Average latency per phase

- approval_workflow: 0.000166s
- document_processing: 0.000247s
- risk_assessment: 0.000149s

## Failure-case analysis

- **SYN-001**: expected `reject`, predicted `conditional`. Likely reasons: The stub and synthetic reference label use different debt-to-income cutoffs.
- **SYN-016**: expected `approve`, predicted `conditional`. Likely reasons: The case is near a credit threshold.
- **SYN-028**: expected `approve`, predicted `conditional`. Likely reasons: The case is near a credit threshold.
- **SYN-036**: expected `reject`, predicted `conditional`. Likely reasons: The case is near a credit threshold.
- **SYN-037**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-038**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-039**: expected `reject`, predicted `conditional`. Likely reasons: Income stability evidence is limited for self-employment.
- **SYN-040**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-041**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-042**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-044**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-046**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-048**: expected `reject`, predicted `conditional`. Likely reasons: Income stability evidence is limited for self-employment.
- **SYN-049**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.
- **SYN-050**: expected `reject`, predicted `conditional`. Likely reasons: Rule ordering or mapping from human review to the conditional class.

## Limitations

- Synthetic cases and labels do not establish real-world model quality.
- The stub uses deterministic demonstration rules rather than an LLM.
- Repeated deterministic stub runs measure code-path consistency only.
- Token counts in stub mode are rough character-based estimates.
- The label policy and stub policy share broad criteria; scores are not independent evidence of model validity.
