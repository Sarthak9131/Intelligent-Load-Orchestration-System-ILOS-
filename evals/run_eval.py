"""Run the synthetic loan evaluation and write JSON and Markdown results."""

import argparse
import asyncio
import json
import os
import tempfile
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from config.settings import LLM_MODEL
from evals.generate_dataset import (
    DEFAULT_DATASET,
    generate_records,
    write_dataset,
)
from src.models import ApplicationStatus
from src.orchestrator import LoanProcessingOrchestrator


DEFAULT_RESULTS = Path(__file__).parent / "results"
CLASS_LABELS = ("approve", "conditional", "reject")


async def evaluate(
    dataset: list[dict[str, Any]],
    repeats: int,
    llm_mode: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run each case repeatedly and derive classification and operational metrics."""
    orchestrator = LoanProcessingOrchestrator(llm_mode=llm_mode)
    case_runs = []
    latencies: dict[str, list[float]] = {}
    input_tokens = 0
    output_tokens = 0
    review_count = 0
    total_latencies = []

    for case in dataset:
        predictions = []
        for _ in range(repeats):
            result = await orchestrator.process_loan_application(
                json.dumps(case["application"], sort_keys=True)
            )
            prediction = _metric_label(result.status)
            predictions.append(prediction)
            review_count += result.status == ApplicationStatus.NEEDS_HUMAN_REVIEW
            total_latencies.append(result.processing_time)
            input_tokens += result.token_usage.get("input_tokens", 0)
            output_tokens += result.token_usage.get("output_tokens", 0)
            for phase, seconds in result.phase_latencies.items():
                latencies.setdefault(phase, []).append(seconds)
        case_runs.append(
            {
                "case_id": case["case_id"],
                "expected": case["expected_outcome"],
                "predictions": predictions,
                "predicted": _majority_label(predictions),
                "scenario_tags": case["scenario_tags"],
                "application": case["application"],
            }
        )

    input_cost_per_token, output_cost_per_token = _model_rates(LLM_MODEL)
    cost_estimate = (
        input_tokens * input_cost_per_token + output_tokens * output_cost_per_token
    )
    scores = _classification_metrics(case_runs)
    consistency = _consistency_metrics(case_runs)
    failure_cases = _failure_analysis(case_runs)
    summary = {
        "schema_version": 1,
        "dataset": str(DEFAULT_DATASET),
        "dataset_size": len(dataset),
        "repeats_per_application": repeats,
        "llm_mode": llm_mode,
        "model": LLM_MODEL,
        "label_definition": (
            "Expected outcomes are generated from the rule in generate_dataset.py. "
            "They are synthetic labels, not historical loan outcomes."
        ),
        "review_mapping": (
            "NEEDS_HUMAN_REVIEW is mapped to conditional for the three-class "
            "classification metrics; the separate review count is reported."
        ),
        "metrics": scores,
        "repeat_consistency": consistency,
        "human_review_decisions": review_count,
        "average_latency_seconds_by_phase": {
            phase: _mean(values) for phase, values in sorted(latencies.items())
        },
        "average_total_latency_seconds": _mean(total_latencies),
        "token_usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "source": "Character-based estimates in stub mode; provider usage metadata in ADK mode when available.",
        },
        "token_cost_estimate_usd": round(cost_estimate, 8),
        "token_cost_pricing": {
            "source": "LiteLLM runtime model-cost metadata",
            "input_cost_per_million_tokens_usd": input_cost_per_token * 1_000_000,
            "output_cost_per_million_tokens_usd": output_cost_per_token * 1_000_000,
        },
        "misclassified_applications": failure_cases,
        "limitations": [
            "Synthetic cases and labels do not establish real-world model quality.",
            "The stub uses deterministic demonstration rules rather than an LLM.",
            "Repeated deterministic stub runs measure code-path consistency only.",
            "Token counts in stub mode are rough character-based estimates.",
            "The label policy and stub policy share broad criteria; scores are not "
            "independent evidence of model validity.",
        ],
    }
    return summary, case_runs


def _classification_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = {
        actual: {predicted: 0 for predicted in CLASS_LABELS}
        for actual in CLASS_LABELS
    }
    correct = 0
    for case in cases:
        expected = case["expected"]
        predicted = case["predicted"]
        matrix[expected][predicted] += 1
        correct += expected == predicted

    per_class = {}
    for label in CLASS_LABELS:
        true_positive = matrix[label][label]
        false_positive = sum(
            matrix[other][label] for other in CLASS_LABELS if other != label
        )
        false_negative = sum(
            matrix[label][other] for other in CLASS_LABELS if other != label
        )
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": _ratio(2 * precision * recall, precision + recall),
            "support": sum(matrix[label].values()),
        }
    return {
        "accuracy": _ratio(correct, len(cases)),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "class_order": list(CLASS_LABELS),
    }


def _consistency_metrics(cases: list[dict[str, Any]]) -> dict[str, float]:
    per_case = []
    for case in cases:
        pairs = list(combinations(case["predictions"], 2))
        per_case.append(
            sum(first == second for first, second in pairs) / max(1, len(pairs))
        )
    return {
        "all_repeats_identical_rate": _ratio(
            sum(len(set(case["predictions"])) == 1 for case in cases),
            len(cases),
        ),
        "mean_pairwise_decision_agreement": _mean(per_case),
    }


def _failure_analysis(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for case in cases:
        if case["predicted"] == case["expected"]:
            continue
        application = case["application"]
        tags = case["scenario_tags"]
        likely_reasons = []
        if "missing_fields" in tags:
            likely_reasons.append("Required values are absent, so the stub abstained.")
        if "conflicting_data" in tags:
            likely_reasons.append("Conflicting synthetic values triggered conservative review.")
        if "borderline_credit" in tags or "credit_threshold_edge" in tags:
            likely_reasons.append("The case is near a credit threshold.")
        if "borderline_dti" in tags:
            likely_reasons.append(
                "The stub and synthetic reference label use different debt-to-income cutoffs."
            )
        if "self_employed_income" in tags:
            likely_reasons.append("Income stability evidence is limited for self-employment.")
        if not likely_reasons:
            likely_reasons.append(
                "Rule ordering or mapping from human review to the conditional class."
            )
        failures.append(
            {
                "case_id": case["case_id"],
                "expected": case["expected"],
                "predicted": case["predicted"],
                "scenario_tags": tags,
                "likely_reasons": likely_reasons,
                "missing_fields": application["missing_fields"],
                "conflicting_fields": application["conflicting_fields"],
            }
        )
    return failures


def _metric_label(status: ApplicationStatus) -> str:
    if status == ApplicationStatus.APPROVED:
        return "approve"
    if status == ApplicationStatus.REJECTED:
        return "reject"
    if status in (
        ApplicationStatus.CONDITIONALLY_APPROVED,
        ApplicationStatus.NEEDS_HUMAN_REVIEW,
        ApplicationStatus.REQUIRES_INFO,
        ApplicationStatus.UNDER_REVIEW,
    ):
        return "conditional"
    raise ValueError(f"Unsupported application status: {status.value}")


def _majority_label(predictions: list[str]) -> str:
    counts = Counter(predictions)
    return sorted(counts, key=lambda label: (-counts[label], label))[0]


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return numerator / denominator if denominator else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _model_rates(model: str) -> tuple[float, float]:
    """Read provider token rates from LiteLLM's installed model-cost registry."""
    import litellm

    details = litellm.get_model_info(model)
    input_rate = details.get("input_cost_per_token")
    output_rate = details.get("output_cost_per_token")
    if input_rate is None or output_rate is None:
        raise ValueError(
            f"LiteLLM has no token pricing metadata for {model!r}; "
            "configure a model with known pricing before estimating cost."
        )
    return float(input_rate), float(output_rate)


def _read_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    if not dataset_path.exists():
        records = generate_records()
        write_dataset(records, dataset_path)
        return records
    return [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _render_markdown(summary: dict[str, Any]) -> str:
    metrics = summary["metrics"]
    lines = [
        "# Synthetic Loan Evaluation",
        "",
        f"- Cases: {summary['dataset_size']}",
        f"- Repeated runs per case: {summary['repeats_per_application']}",
        f"- Mode: `{summary['llm_mode']}`",
        f"- Model pricing reference: `{summary['model']}`",
        "- Labels are synthetic policy-derived targets, not historical outcomes.",
        "",
        "## Classification metrics",
        "",
        f"- Decision accuracy: {metrics['accuracy']:.4f}",
        f"- Token cost estimate: ${summary['token_cost_estimate_usd']:.8f}",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in CLASS_LABELS:
        item = metrics["per_class"][label]
        lines.append(
            f"| {label} | {item['precision']:.4f} | {item['recall']:.4f} | "
            f"{item['f1']:.4f} | {item['support']} |"
        )
    lines.extend(["", "### Confusion matrix", "", "| Actual \\ Predicted | " + " | ".join(CLASS_LABELS) + " |", "|---|" + "---:|" * len(CLASS_LABELS)])
    for label in CLASS_LABELS:
        lines.append(
            f"| {label} | "
            + " | ".join(str(metrics["confusion_matrix"][label][pred]) for pred in CLASS_LABELS)
            + " |"
        )
    lines.extend(
        [
            "",
            "## Repeat consistency",
            "",
            f"- All repeats identical: "
            f"{summary['repeat_consistency']['all_repeats_identical_rate']:.4f}",
            f"- Mean pairwise decision agreement: "
            f"{summary['repeat_consistency']['mean_pairwise_decision_agreement']:.4f}",
            "",
            "## Average latency per phase",
            "",
        ]
    )
    if summary["average_latency_seconds_by_phase"]:
        for phase, seconds in summary["average_latency_seconds_by_phase"].items():
            lines.append(f"- {phase}: {seconds:.6f}s")
    else:
        lines.append("- No phase latency measurements were recorded.")
    lines.extend(
        [
            "",
            "## Failure-case analysis",
            "",
        ]
    )
    if summary["misclassified_applications"]:
        for failure in summary["misclassified_applications"]:
            lines.append(
                f"- **{failure['case_id']}**: expected `{failure['expected']}`, "
                f"predicted `{failure['predicted']}`. "
                f"Likely reasons: {'; '.join(failure['likely_reasons'])}"
            )
    else:
        lines.append("- No cases were misclassified in this run.")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in summary["limitations"])
    lines.append("")
    return "\n".join(lines)


def _write_results(
    summary: dict[str, Any],
    case_runs: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation_results.json").write_text(
        json.dumps(
            {
                **summary,
                "case_predictions": [
                    {
                        key: value
                        for key, value in case.items()
                        if key != "application"
                    }
                    for case in case_runs
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (output_dir / "evaluation_summary.md").write_text(
        _render_markdown(summary),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--mode", choices=("stub", "adk"), default="stub")
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error("--repeats must be at least 2 for consistency measurement.")

    dataset = _read_dataset(args.dataset)
    if len(dataset) != 50:
        parser.error(f"Expected 50 evaluation cases, found {len(dataset)}.")
    previous_audit_dir = os.environ.get("AUDIT_DIR")
    with tempfile.TemporaryDirectory(prefix="loan-eval-audit-") as audit_dir:
        os.environ["AUDIT_DIR"] = audit_dir
        try:
            summary, case_runs = asyncio.run(
                evaluate(dataset, args.repeats, args.mode)
            )
        finally:
            if previous_audit_dir is None:
                os.environ.pop("AUDIT_DIR", None)
            else:
                os.environ["AUDIT_DIR"] = previous_audit_dir
    summary["dataset"] = str(args.dataset)
    _write_results(summary, case_runs, args.output_dir)
    print(json.dumps({key: summary[key] for key in ("metrics", "repeat_consistency")}, indent=2))
    print(f"Results written to {args.output_dir}")


if __name__ == "__main__":
    main()
