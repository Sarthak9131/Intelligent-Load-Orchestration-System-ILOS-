"""Tests for proxy-only paired synthetic fairness checks."""

import pytest

from evals.fairness_check import build_pairs, evaluate_fairness
from evals.generate_dataset import generate_records


def test_pairs_differ_only_in_the_declared_proxy():
    pairs = build_pairs(generate_records()[:1], pair_count=1)

    assert len(pairs) == 2
    for pair in pairs:
        changed_fields = {
            key
            for key in pair["control"]
            if pair["control"][key] != pair["variant"][key]
        }
        assert changed_fields == {pair["proxy"]}


@pytest.mark.asyncio
async def test_stub_fairness_check_reports_disagreement_rate(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path))
    pairs = build_pairs(generate_records()[:2], pair_count=2)

    result = await evaluate_fairness(pairs, llm_mode="stub")

    assert result["pair_count"] == 4
    assert result["decision_disagreement_rate"] == 0
    assert result["proxies_tested"] == ["applicant_name", "zip_code"]
    assert result["limitations"]
