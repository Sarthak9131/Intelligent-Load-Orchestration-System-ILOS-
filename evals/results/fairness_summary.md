# Paired Synthetic Fairness Check

- Mode: `stub`
- Paired comparisons: 20
- Decision disagreement rate: 0.0000
- Proxies changed one at a time: applicant_name, zip_code

## Limitations

- This is a small synthetic proxy perturbation test, not a legal fairness assessment.
- Equal decisions for names or ZIP codes do not establish fairness across protected groups.
- The test does not measure disparate impact, calibration, error rates, or intersectional effects.
- The stub ignores ZIP codes and name masking removes names, so stub results do not predict live-model behavior.
