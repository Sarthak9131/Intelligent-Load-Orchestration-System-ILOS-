"""Generate a reproducible 50-case synthetic loan evaluation dataset."""

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_DATASET = Path(__file__).parent / "data" / "synthetic_loan_applications.jsonl"


def generate_records(seed: int = 20261025) -> list[dict[str, Any]]:
    """Return deterministic synthetic cases with rule-derived expected labels."""
    records = []
    for index in range(50):
        case_id = f"SYN-{index + 1:03d}"
        application = _application_for(index, seed)
        expected_outcome = label_application(application)
        records.append(
            {
                "case_id": case_id,
                "application": application,
                "expected_outcome": expected_outcome,
                "scenario_tags": _scenario_tags(index, application),
            }
        )
    return records


def label_application(application: dict[str, Any]) -> str:
    """Derive synthetic target labels from the published demonstration policy."""
    if application["missing_fields"] or application["conflicting_fields"]:
        return "conditional"
    income = application.get("annual_income") or 0
    debts = application.get("monthly_debts") or 0
    loan = application.get("loan_amount") or 0
    credit = application.get("credit_score") or 0
    dti = debts / (income / 12) if income > 0 else 1.0
    lti = loan / income if income > 0 else 10.0
    if credit <= 620 or dti >= 0.5 or lti >= 5:
        return "reject"
    if (
        credit < 700
        or dti >= 0.35
        or (
            application["employment_type"] == "self_employed"
            and application["employment_years"] < 2
        )
        or not application["documentation_complete"]
    ):
        return "conditional"
    return "approve"


def write_dataset(records: list[dict[str, Any]], destination: Path) -> None:
    """Write records as newline-delimited JSON, creating the target directory."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _application_for(index: int, seed: int) -> dict[str, Any]:
    offset = ((index * 17 + seed) % 7) * 1500
    is_approve = index < 15
    is_conditional = 15 <= index < 35
    if is_approve:
        application: dict[str, Any] = {
            "annual_income": 76000 + offset,
            "monthly_debts": 1050 + (index % 4) * 100,
            "loan_amount": 24000 + (index % 5) * 2500,
            "credit_score": 720 + (index % 7) * 12,
            "employment_type": "employed",
            "employment_years": 3 + index % 5,
            "savings": 15000 + index * 500,
            "loan_purpose": "synthetic home repair",
            "documentation_complete": True,
        }
    elif is_conditional:
        application = {
            "annual_income": 56000 + offset,
            "monthly_debts": 1450 + (index % 5) * 120,
            "loan_amount": 26000 + (index % 5) * 3200,
            "credit_score": 650 + (index % 5) * 10,
            "employment_type": "employed",
            "employment_years": 2 + index % 4,
            "savings": 6000 + index * 180,
            "loan_purpose": "synthetic equipment",
            "documentation_complete": index % 4 != 0,
        }
    else:
        application = {
            "annual_income": 38000 + offset,
            "monthly_debts": 2300 + (index % 4) * 180,
            "loan_amount": 42000 + (index % 5) * 4200,
            "credit_score": 560 + (index % 7) * 10,
            "employment_type": "employed",
            "employment_years": 1 + index % 4,
            "savings": 900 + index * 80,
            "loan_purpose": "synthetic debt consolidation",
            "documentation_complete": index % 3 != 0,
        }

    application.update(
        {
            "applicant_name": f"Synthetic Applicant {index + 1:03d}",
            "missing_fields": [],
            "conflicting_fields": [],
            "synthetic_data": True,
        }
    )

    if index == 0:
        application["monthly_debts"] = round(
            application["annual_income"] / 12 * 0.51, 2
        )
    if index in {4, 22, 23, 38, 47}:
        application["employment_type"] = "self_employed"
        application["employment_years"] = 4.0 if index == 4 else 1.5 + index % 2
    if index in {15, 19, 27, 35}:
        application["credit_score"] = 700
    if index == 16:
        application["annual_income"] = None
        application["missing_fields"] = ["annual_income"]
    elif index == 24:
        application["credit_score"] = None
        application["missing_fields"] = ["credit_score"]
    elif index == 42:
        application["monthly_debts"] = None
        application["missing_fields"] = ["monthly_debts"]
    if index in {2, 18, 31, 46}:
        application["conflicting_fields"] = ["annual_income"]
        application["secondary_reported_income"] = (
            application["annual_income"] * 1.4
            if application["annual_income"] is not None
            else 50000
        )
    return application


def _scenario_tags(index: int, application: dict[str, Any]) -> list[str]:
    tags = ["synthetic"]
    if application["missing_fields"]:
        tags.append("missing_fields")
    if application["conflicting_fields"]:
        tags.append("conflicting_data")
    if application["credit_score"] in {650, 660, 670, 680, 700}:
        tags.append("borderline_credit")
    if application["employment_type"] == "self_employed":
        tags.append("self_employed_income")
    if index >= 35:
        tags.append("high_risk")
    if index in {15, 19, 27, 35}:
        tags.append("credit_threshold_edge")
    income = application.get("annual_income") or 0
    if income and application.get("monthly_debts") is not None:
        dti = application["monthly_debts"] / (income / 12)
        if 0.47 <= dti <= 0.55:
            tags.append("borderline_dti")
    return tags


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261025)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()
    records = generate_records(args.seed)
    write_dataset(records, args.output)
    print(f"Wrote {len(records)} synthetic applications to {args.output}")


if __name__ == "__main__":
    main()
