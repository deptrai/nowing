"""Tests for the chat/quality LLM-as-judge benchmark (Story 4.8d)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from nowing_evals.core.arms.base import ArmResult
from nowing_evals.core.config import Config, SuiteState
from nowing_evals.core.registry import RunContext
from nowing_evals.suites.chat.quality.prompt import build_judge_prompt, parse_judge_scores
from nowing_evals.suites.chat.quality.runner import (
    ChatQualityBenchmark,
    _aggregate_scores,
    _evaluate_gate,
    _validate_case_row,
)

_BASE = "http://test"


@pytest.fixture
def http() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_BASE)


def _test_config(isolated_config: Config) -> Config:
    return replace(
        isolated_config,
        nowing_api_base=_BASE,
        openrouter_api_key="fake-key",
        openrouter_base_url="http://router.test",
    )


def _run_context(
    config: Config,
    http_client: httpx.AsyncClient,
    search_space_id: int = 7,
) -> RunContext:
    return RunContext(
        suite="chat",
        benchmark="quality",
        config=config,
        suite_state=SuiteState(
            search_space_id=search_space_id,
            chat_model_id=1,
            provider_model="openai/gpt-5",
            created_at="2026-08-04T00-00-00Z",
        ),
        http=http_client,
    )


@pytest.mark.asyncio
async def test_ingest_writes_and_validates_custom_dataset(
    isolated_config: Config, tmp_path: Path
) -> None:
    bench = ChatQualityBenchmark()
    assert bench.requires_auth_for_ingest is False
    dataset_path = tmp_path / "custom.jsonl"
    with dataset_path.open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "case_id": "c1",
                    "query": "q1",
                    "reference_answer": "ref1",
                    "rubric": "r1",
                    "tags": ["memory"],
                }
            )
            + "\n"
        )

    async with httpx.AsyncClient() as http:
        ctx = _run_context(_test_config(isolated_config), http)
        await bench.ingest(ctx, dataset=dataset_path)

    written = ctx.benchmark_data_dir() / "cases.jsonl"
    assert written.is_file()
    cases = [json.loads(line) for line in written.read_text(encoding="utf-8").splitlines()]
    assert cases[0]["case_id"] == "c1"


@pytest.mark.asyncio
async def test_ingest_rejects_missing_required_fields(
    isolated_config: Config, tmp_path: Path
) -> None:
    bench = ChatQualityBenchmark()
    dataset_path = tmp_path / "bad.jsonl"
    with dataset_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"case_id": "c1", "query": "q1"}) + "\n")

    async with httpx.AsyncClient() as http:
        ctx = _run_context(_test_config(isolated_config), http)
        with pytest.raises(RuntimeError, match="reference_answer"):
            await bench.ingest(ctx, dataset=dataset_path)


def test_validate_case_row_rejects_invalid_mode() -> None:
    with pytest.raises(RuntimeError, match="mode"):
        _validate_case_row(
            {
                "case_id": "c1",
                "query": "q1",
                "reference_answer": "r",
                "rubric": "rb",
                "mode": "fast",
            }
        )


def test_build_judge_prompt_contains_inputs() -> None:
    prompt = build_judge_prompt(
        query="q",
        reference_answer="ref",
        rubric="rubric",
        answer="ans",
    )
    assert "q" in prompt
    assert "ref" in prompt
    assert "rubric" in prompt
    assert "ans" in prompt


def test_parse_judge_scores_parses_json() -> None:
    text = json.dumps(
        {
            "correctness": 4,
            "citation_faithfulness": 5,
            "completeness": 3,
            "harmfulness": 1,
            "rationale": "ok",
        }
    )
    scores = parse_judge_scores(text)
    assert scores["correctness"] == 4.0
    assert scores["citation_faithfulness"] == 5.0
    assert scores["completeness"] == 3.0
    assert scores["harmfulness"] == 1.0


def test_parse_judge_scores_clamps_out_of_range() -> None:
    text = json.dumps(
        {
            "correctness": 99,
            "citation_faithfulness": -1,
            "completeness": "abc",
            "harmfulness": True,
        }
    )
    scores = parse_judge_scores(text)
    assert scores["correctness"] == 0.0
    assert scores["citation_faithfulness"] == 0.0
    assert scores["completeness"] == 0.0
    # bool True is clamped to 5.0, False to 0.0.
    assert scores["harmfulness"] == 5.0


def test_parse_judge_scores_fallback_regex() -> None:
    text = (
        "Some explanation. correctness: 3, citation_faithfulness: 4, "
        "completeness: 2, harmfulness: 1"
    )
    scores = parse_judge_scores(text)
    assert scores["correctness"] == 3.0
    assert scores["citation_faithfulness"] == 4.0
    assert scores["completeness"] == 2.0
    assert scores["harmfulness"] == 1.0


def test_aggregate_scores_overall_and_per_tag() -> None:
    results = [
        SimpleNamespace(
            case_id="c1",
            scores={
                "correctness": 4.0,
                "citation_faithfulness": 5.0,
                "completeness": 3.0,
                "harmfulness": 1.0,
            },
            answer_error=None,
            answer_cost_micros=10,
            answer_latency_ms=100,
            judge_cost_micros=20,
            judge_latency_ms=200,
            tags=["memory"],
        ),
        SimpleNamespace(
            case_id="c2",
            scores={
                "correctness": 2.0,
                "citation_faithfulness": 3.0,
                "completeness": 4.0,
                "harmfulness": 2.0,
            },
            answer_error=None,
            answer_cost_micros=10,
            answer_latency_ms=150,
            judge_cost_micros=20,
            judge_latency_ms=300,
            tags=["document"],
        ),
    ]
    metrics = _aggregate_scores(results)  # type: ignore[arg-type]
    overall = metrics["overall"]
    assert overall["samples"] == 2
    assert overall["mean_correctness"] == 3.0
    assert overall["mean_completeness"] == 3.5
    assert overall["total_cost_micros"] == 60
    assert "p95_judge_latency_ms" in overall

    per_tag = metrics["per_tag"]
    assert per_tag["memory"]["mean_correctness"] == 4.0
    assert per_tag["document"]["mean_correctness"] == 2.0


def test_evaluate_gate_thresholds(tmp_path: Path) -> None:
    gate_path = tmp_path / "gate.yaml"
    gate_path.write_text(
        "baseline_ratified: true\nthresholds:\n  min_mean_correctness: 3.5\n",
        encoding="utf-8",
    )
    metrics = {
        "overall": {
            "mean_correctness": 3.0,
            "mean_citation_faithfulness": 5.0,
            "mean_completeness": 5.0,
            "mean_harmfulness": 1.0,
            "answer_error_rate": 0.0,
        }
    }
    violations = _evaluate_gate(metrics, gate_path)
    assert any("correctness" in v for v in violations)


def test_evaluate_gate_no_violations(tmp_path: Path) -> None:
    gate_path = tmp_path / "gate.yaml"
    gate_path.write_text(
        "baseline_ratified: true\nthresholds:\n  min_mean_correctness: 3.0\n",
        encoding="utf-8",
    )
    metrics = {
        "overall": {
            "mean_correctness": 4.0,
            "mean_citation_faithfulness": 4.0,
            "mean_completeness": 4.0,
            "mean_harmfulness": 1.0,
            "answer_error_rate": 0.0,
        }
    }
    assert _evaluate_gate(metrics, gate_path) == []


@pytest.mark.asyncio
async def test_run_uses_mocks_and_aggregates(
    isolated_config: Config, tmp_path: Path, monkeypatch
) -> None:
    """Run chat/quality with stubbed Nowing arm and judge provider."""
    bench = ChatQualityBenchmark()
    dataset_path = tmp_path / "cases.jsonl"
    with dataset_path.open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "case_id": "c1",
                    "query": "What is the capital of France?",
                    "reference_answer": "Paris",
                    "rubric": "Must answer Paris.",
                    "tags": ["geography"],
                    "mode": "balanced",
                }
            )
            + "\n"
        )

    class FakeArm:
        def __init__(self, *, client, search_space_id, workspace_id=None, **kwargs):
            pass

        async def answer(self, request):
            return ArmResult(
                arm="nowing",
                question_id=request.question_id,
                raw_text="The capital of France is Paris.",
                latency_ms=1000,
                cost_micros=50,
            )

    class FakeProvider:
        def __init__(self, *, api_key, base_url, model, timeout_s=None):
            self.model = model

        async def complete(self, **kwargs):
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "correctness": 5,
                        "citation_faithfulness": 4,
                        "completeness": 5,
                        "harmfulness": 1,
                        "rationale": "correct",
                    }
                ),
                cost_micros=25,
                latency_ms=500,
            )

    monkeypatch.setattr("nowing_evals.suites.chat.quality.runner.NowingArm", FakeArm)
    monkeypatch.setattr(
        "nowing_evals.suites.chat.quality.runner.OpenRouterChatProvider", FakeProvider
    )

    config = _test_config(isolated_config)
    async with httpx.AsyncClient() as http:
        ctx = _run_context(config, http)
        await bench.ingest(ctx, dataset=dataset_path)
        artifact = await bench.run(ctx, search_space_id=7)

    assert artifact.suite == "chat"
    assert artifact.benchmark == "quality"
    assert artifact.raw_path.is_file()
    overall = artifact.metrics["overall"]
    assert overall["mean_correctness"] == 5.0
    assert overall["mean_citation_faithfulness"] == 4.0
    assert overall["total_cost_micros"] == 75
    assert artifact.metrics["per_tag"]["geography"]["mean_correctness"] == 5.0

    section = bench.report_section([artifact])
    assert "Chat quality" in section.title
    assert "5.00" in section.body_md


@pytest.mark.asyncio
async def test_run_validates_args(isolated_config: Config, http, tmp_path: Path) -> None:
    bench = ChatQualityBenchmark()
    dataset_path = tmp_path / "cases.jsonl"
    with dataset_path.open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "case_id": "c1",
                    "query": "q",
                    "reference_answer": "r",
                    "rubric": "rb",
                }
            )
            + "\n"
        )

    ctx = _run_context(_test_config(isolated_config), http, search_space_id=0)
    with pytest.raises(RuntimeError, match="--search-space-id"):
        await bench.run(ctx, dataset=dataset_path)
