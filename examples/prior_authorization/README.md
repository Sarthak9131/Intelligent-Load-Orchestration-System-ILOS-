# Synthetic Prior-Authorization Scenario

This example reuses the prototype's orchestration patterns:

1. Validate a synthetic request with a typed intake contract.
2. Run clinical-criteria, coverage-eligibility, and documentation checks in
   parallel.
3. Pass their results through a sequential reviewer chain.
4. Route incomplete or ambiguous evidence to `needs_human_review` with a reason.

Run the local stub (no API key required) from the repository root:

```powershell
python -m examples.prior_authorization.demo
```

The sample uses only generated identifiers and synthetic flags. **No real PHI
is used. This project and example are not HIPAA-certified or intended for real
clinical, coverage, or treatment decisions.**
