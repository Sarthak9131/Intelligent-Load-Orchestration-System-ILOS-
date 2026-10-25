"""Tests for synthetic dataset generation and stub evaluation."""

import pytest

from evals.generate_dataset import generate_records
from evals.run_eval import evaluate


def test_generator_creates_fifty_labeled_edge_cases():
    records = generate_records()
    tags = {tag for record in records for tag in record["scenario_tags"]}

    assert len(records) == 50
    assert {record["expected_outcome"] for record in records} == {
        "approve",
        "conditional",
        "reject",
    }
    assert {
        "missing_fields",
        "conflicting_data",
        "borderline_credit",
        "self_employed_income",
    }.issubset(tags)
    assert all("expected_outcome" not in record["application"] for record in records)


@pytest.mark.asyncio
async def test_stub_evaluation_reports_metrics_latency_and_cost(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    records = generate_records()[:4]

    summary, case_runs = await evaluate(records, repeats=3, llm_mode="stub")

    assert summary["dataset_size"] == 4
    assert summary["repeats_per_application"] == 3
    assert set(summary["metrics"]["per_class"]) == {
        "approve",
        "conditional",
        "reject",
    }
    assert set(summary["average_latency_seconds_by_phase"]) == {
        "approval_workflow",
        "document_processing",
        "risk_assessment",
    }
    assert summary["token_usage"]["input_tokens"] > 0
    assert summary["token_cost_estimate_usd"] >= 0
    assert summary["repeat_consistency"]["all_repeats_identical_rate"] == 1
    assert summary["average_total_latency_seconds"] > 0
    assert len(case_runs) == 4
    assert summary["misclassified_applications"][0]["case_id"] == "SYN-001"
    assert "borderline_dti" in summary["misclassified_applications"][0]["scenario_tags"]
