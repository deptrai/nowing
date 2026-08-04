"""Unit tests for chat/regression benchmark helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nowing_evals.suites.chat.regression.runner import (
    ChatRegressionBenchmark,
    _CaseResult,
    _contains_hits,
)


def test_contains_hits_counts_substring_matches() -> None:
    text = "The Q3 budget is under review."
    assert _contains_hits(text, ["Q3", "budget"]) == 2
    assert _contains_hits(text, ["Q4"]) == 0
    assert _contains_hits("", ["Q3"]) == 0


def test_contains_hits_is_case_insensitive() -> None:
    assert _contains_hits("The NDA is confidential.", ["nda"]) == 1


def _make_result(
    case_id: str,
    latency_ms: int = 1000,
    ttfb_ms: int | None = 100,
    cost_micros: int = 50,
    citation_count: int = 2,
    total_tokens: int = 100,
    error: str | None = None,
    finished_normally: bool = True,
    text: str = "Answer is B.",
    expected_contains: list[str] | None = None,
    tags: list[str] | None = None,
) -> _CaseResult:
    return _CaseResult(
        case_id=case_id,
        tags=tags or ["memory"],
        query="q",
        text=text,
        error=error,
        latency_ms=latency_ms,
        ttfb_ms=ttfb_ms,
        prompt_tokens=total_tokens // 2,
        completion_tokens=total_tokens // 2,
        total_tokens=total_tokens,
        cost_micros=cost_micros,
        citation_count=citation_count,
        finished_normally=finished_normally,
        expected_contains=expected_contains or [],
        contains_hits=_contains_hits(text, expected_contains or []),
    )


def test_aggregate_overall_and_per_tag() -> None:
    bench = ChatRegressionBenchmark()
    results = [
        _make_result(
            "a",
            tags=["memory"],
            latency_ms=1000,
            cost_micros=50,
            text="Answer is B budget.",
            expected_contains=["budget"],
        ),
        _make_result(
            "b",
            tags=["memory"],
            latency_ms=2000,
            cost_micros=150,
            text="Answer is Q3.",
            expected_contains=["Q3"],
        ),
        _make_result(
            "c",
            tags=["document"],
            latency_ms=3000,
            cost_micros=100,
            text="No keyword.",
            expected_contains=["missing"],
        ),
        _make_result("d", tags=["document"], error="boom", finished_normally=False),
    ]

    metrics = bench._aggregate(results)

    overall = metrics["overall"]
    assert overall["samples"] == 4
    assert overall["n_failed"] == 1
    assert overall["error_rate"] == 0.25
    assert overall["p95_e2e_ms"] == pytest.approx(2850.0)
    assert overall["p95_cost_micros"] == pytest.approx(142.5)
    assert overall["contains_match_rate"] == pytest.approx(2 / 3)

    per_tag = metrics["per_tag"]
    assert "memory" in per_tag
    assert "document" in per_tag
    assert per_tag["document"]["n_failed"] == 1


def test_sample_dataset_is_valid_jsonl(tmp_path: Path) -> None:
    """The default sample dataset must be parseable by _load_cases."""
    from nowing_evals.suites.chat.regression.runner import _DEFAULT_DATASET, _load_cases

    dataset_path = tmp_path / "cases.jsonl"
    with dataset_path.open("w", encoding="utf-8") as fh:
        for row in _DEFAULT_DATASET:
            fh.write(json.dumps(row) + "\n")

    cases = _load_cases(dataset_path)
    assert len(cases) == len(_DEFAULT_DATASET)
    for case in cases:
        assert case.case_id
        assert case.query
