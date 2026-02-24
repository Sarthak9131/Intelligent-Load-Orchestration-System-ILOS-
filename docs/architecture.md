# Architecture Deep Dive

## Why Multi-Agent?

A single LLM call trying to intake documents, extract financials, assess four risk dimensions, check compliance, AND make a final underwriting decision will produce lower-quality output than specialists each doing one job extremely well.

Multi-agent systems mirror how real loan departments work:
- **Document team** — organises the application package
- **Risk analysts** — each owns one domain (income, credit, employment, collateral)
- **Compliance** — mandatory regulatory checkpoint
- **Underwriter** — final authority with full context

## Sequential vs Parallel Decision Guide

| Use Sequential when... | Use Parallel when... |
|------------------------|----------------------|
| Step B needs Step A's output | Steps are independent |
| Order matters for quality | Speed matters |
| Authority chain required | Same input, different lenses |
| Audit trail needed per step | Results aggregated at end |

## State Transfer Between Agents

Each agent in a `SequentialAgent` receives the **full conversation history** from all previous agents. This means the `FinalUnderwriterAgent` has complete access to:
1. The raw application data
2. The document processing output
3. The risk assessment from all four parallel agents
4. The risk analyst's recommendation
5. The compliance reviewer's approval

This rich context enables high-quality final decisions without information loss.

## Risk Scoring Model

```
Weighted Risk Score = 
    Income Score    × 0.35   (ability to pay — most important)
  + Credit Score    × 0.30   (willingness to pay — historical behaviour)  
  + Employment Score× 0.25   (income stability)
  + Collateral Score× 0.10   (safety net if default)

Decision thresholds:
  0–30   → APPROVE (standard terms)
  31–60  → CONDITIONALLY APPROVE
  61–80  → CONDITIONALLY APPROVE (enhanced monitoring) or REJECT if DTI > 43%
  81–100 → REJECT
```

## Compliance Checkpoints

Every application is automatically verified against:
- **ECOA** — Equal Credit Opportunity Act (no discrimination)
- **FCRA** — Fair Credit Reporting Act (proper credit report usage)
- **TILA** — Truth in Lending Act (rate and fee disclosures)
- **BSA/AML** — Bank Secrecy Act anti-money laundering
- **Internal policy** — DTI ≤ 43%, LTI ≤ 5×
