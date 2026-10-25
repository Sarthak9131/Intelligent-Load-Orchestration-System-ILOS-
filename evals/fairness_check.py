"""Run paired synthetic name and ZIP-code decision consistency checks."""

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from evals.generate_dataset import DEFAULT_DATASET, generate_records
from src.orchestrator import LoanProcessingOrchestrator

DEFAULT_OUTPUT = Path(__file__).parent / "results" / "fairness_check.json"
LIMITATIONS = [
    "This is a small synthetic proxy perturbation test, not a legal fairness assessment.",
    "Equal decisions for names or ZIP codes do not establish fairness across protected groups.",
    "The test does not measure disparate impact, calibration, error rates, or intersectional effects.",
    "The stub ignores ZIP codes and name masking removes names, so stub results do not predict live-model behavior.",
]


def build_pairs(
    records: list[dict[str, Any]],
    pair_count: int,
) -> list[dict[str, Any]]:
    """Create pairs that differ in exactly one synthetic proxy attribute."""
    pairs = []
    for index, record in enumerate(records[:pair_count]):
        base = dict(record["application"])
        base.setdefault("zip_code", f"{10000 + index:05d}")
        for proxy, changed_value in (
            ("applicant_name", f"Synthetic Alternate {index + 1:03d}"),
            ("zip_code", f"{90000 + index:05d}"),
        ):
            control = dict(base)
            variant = dict(base)
            variant[proxy] = changed_value
            pairs.append(
                {
                    "pair_id": f"{record['case_id']}-{proxy}",
                    "proxy": proxy,
                    "control": control,
                    "variant": variant,
                }
            )
    return pairs


async def evaluate_fairness(
    pairs: list[dict[str, Any]],
    llm_mode: str = "stub",
) -> dict[str, Any]:
    """Measure exact decision disagreement within each paired example."""
    orchestrator = LoanProcessingOrchestrator(llm_mode=llm_mode)
    comparisons = []
    for pair in pairs:
        control_result = await orchestrator.process_loan_application(
            json.dumps(pair["control"], sort_keys=True)
        )
        variant_result = await orchestrator.process_loan_application(
            json.dumps(pair["variant"], sort_keys=True)
        )
        control = control_result.status.value
        variant = variant_result.status.value
        comparisons.append(
            {
                "pair_id": pair["pair_id"],
                "proxy": pair["proxy"],
                "control_decision": control,
                "variant_decision": variant,
                "disagreement": control != variant,
            }
        )
    disagreements = sum(item["disagreement"] for item in comparisons)
    return {
        "schema_version": 1,
        "llm_mode": llm_mode,
        "pair_count": len(comparisons),
        "decision_disagreements": disagreements,
        "decision_disagreement_rate": (
            disagreements / len(comparisons) if comparisons else 0.0
        ),
        "proxies_tested": sorted({item["proxy"] for item in comparisons}),
        "comparisons": comparisons,
        "limitations": LIMITATIONS,
    }


def _write_report(result: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_path = destination.with_name("fairness_summary.md")
    lines = [
        "# Paired Synthetic Fairness Check",
        "",
        f"- Mode: `{result['llm_mode']}`",
        f"- Paired comparisons: {result['pair_count']}",
        (
            f"- Decision disagreement rate: "
            f"{result['decision_disagreement_rate']:.4f}"
        ),
        f"- Proxies changed one at a time: {', '.join(result['proxies_tested'])}",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in result["limitations"])
    lines.append("")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pairs", type=int, default=10)
    parser.add_argument("--mode", choices=("stub", "adk"), default="stub")
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("--pairs must be a positive integer.")
    if args.dataset.exists():
        records = [
            json.loads(line)
            for line in args.dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        records = generate_records()
    if args.pairs > len(records):
        parser.error(f"Requested {args.pairs} pairs from {len(records)} available cases.")

    previous_audit_dir = os.environ.get("AUDIT_DIR")
    with tempfile.TemporaryDirectory(prefix="loan-fairness-audit-") as audit_dir:
        os.environ["AUDIT_DIR"] = audit_dir
        try:
            report = asyncio.run(
                evaluate_fairness(build_pairs(records, args.pairs), args.mode)
            )
        finally:
            if previous_audit_dir is None:
                os.environ.pop("AUDIT_DIR", None)
            else:
                os.environ["AUDIT_DIR"] = previous_audit_dir
    _write_report(report, args.output)
    print(json.dumps(
        {
            "pair_count": report["pair_count"],
            "decision_disagreement_rate": report["decision_disagreement_rate"],
        },
        indent=2,
    ))
    print(f"Fairness results written to {args.output}")


if __name__ == "__main__":
    main()
