# Synthetic Loan Evaluation

- Cases: 50
- Repeated runs per case: 3
- Mode: `stub`
- Model pricing reference: `anthropic/claude-sonnet-4-6`
- Labels are synthetic policy-derived targets, not historical outcomes.

## Classification metrics

- Decision accuracy: 0.9800
- Token cost estimate: $0.57656700

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| approve | 1.0000 | 1.0000 | 1.0000 | 15 |
| conditional | 0.9545 | 1.0000 | 0.9767 | 21 |
| reject | 1.0000 | 0.9286 | 0.9630 | 14 |

### Confusion matrix

| Actual \ Predicted | approve | conditional | reject |
|---|---:|---:|---:|
| approve | 15 | 0 | 0 |
| conditional | 0 | 21 | 0 |
| reject | 0 | 1 | 13 |

## Repeat consistency

- All repeats identical: 1.0000
- Mean pairwise decision agreement: 1.0000

## Average latency per phase

- approval_workflow: 0.000109s
- document_processing: 0.000181s
- risk_assessment: 0.000105s

## Failure-case analysis

- **SYN-001**: expected `reject`, predicted `conditional`. Likely reasons: The stub and synthetic reference label use different debt-to-income cutoffs.

## Limitations

- Synthetic cases and labels do not establish real-world model quality.
- The stub uses deterministic demonstration rules rather than an LLM.
- Repeated deterministic stub runs measure code-path consistency only.
- Token counts in stub mode are rough character-based estimates.
- The label policy and stub policy share broad criteria; scores are not independent evidence of model validity.
