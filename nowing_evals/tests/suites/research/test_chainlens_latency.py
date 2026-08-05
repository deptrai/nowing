"""Unit tests for research/chainlens_latency benchmark."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx

from nowing_evals.core.config import Config, SuiteState
from nowing_evals.core.registry import RunArtifact, RunContext
from nowing_evals.suites.research.chainlens_latency.runner import (
    ChainlensLatencyBenchmark,
    _add_row_to_stats,
    _bucket_stats,
    _evaluate_chainlens_gate,
    _ModeStats,
    _percentile,
    _resolve_bucket_mode,
)

_BASE = "http://test"


@pytest.fixture
def http() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_BASE)


def _test_config(isolated_config: Config) -> Config:
    return replace(isolated_config, nowing_api_base=_BASE, memory_workspace_id=42)


def _run_context(config: Config, http_client: httpx.AsyncClient) -> RunContext:
    return RunContext(
        suite="research",
        benchmark="chainlens_latency",
        config=config,
        suite_state=SuiteState(
            search_space_id=0,
            chat_model_id=0,
            provider_model="",
            created_at="2026-08-04T00:00:00Z",
        ),
        http=http_client,
    )


def _research_output(
    *,
    resolved_mode: str | None = "balanced",
    duration_ms: int = 1200,
    first_token_time_ms: int | None = 300,
    cost_micros: int = 5000,
    status: str = "complete",
    answer: str = "An answer.",
) -> dict:
    return {
        "resolved_mode": resolved_mode,
        "duration_ms": duration_ms,
        "first_token_time_ms": first_token_time_ms,
        "status": status,
        "degraded": status != "complete",
        "degradation_reason": None,
        "engine_reason": None,
        "sources": [],
        "answer": answer,
        "cost_micros": cost_micros,
        "fallback_hit_count": 0,
    }


def _run_detail(run_id: str, output: dict | None = None, status: str = "success") -> dict:
    output_text = json.dumps(output) if output else ""
    return {
        "id": run_id,
        "run_id": run_id,
        "capability": "chainlens.research",
        "origin": "api",
        "status": status,
        "item_count": 0,
        "char_count": len(output_text),
        "duration_ms": output.get("duration_ms") if output else 0,
        "cost_micros": output.get("cost_micros") if output else 0,
        "error": None,
        "created_at": "2026-08-04T00:00:00Z",
        "thread_id": None,
        "input": None,
        "output_text": output_text,
        "progress": [],
    }


def test_requires_auth_for_ingest_is_false() -> None:
    bench = ChainlensLatencyBenchmark()
    assert bench.requires_auth_for_ingest is False
    assert bench.requires_suite_setup is False


def test_percentile_empty_returns_none() -> None:
    assert _percentile([], 0.5) is None
    assert _percentile([], 0.95) is None


def test_percentile_linear_interpolation() -> None:
    values = [10.0, 20.0, 30.0]
    assert _percentile(values, 0.5) == 20.0
    assert _percentile(values, 0.95) == 29.0


def test_resolve_bucket_mode() -> None:
    assert _resolve_bucket_mode({"mode": "speed"}, ["speed", "balanced"]) == "speed"
    assert (
        _resolve_bucket_mode({"mode": "quality", "resolved_mode": "deep"}, ["quality"]) == "quality"
    )
    assert (
        _resolve_bucket_mode({"mode": "speed", "resolved_mode": "balanced"}, ["speed", "balanced"])
        == "balanced"
    )
    assert (
        _resolve_bucket_mode(
            {"mode": "auto", "resolved_mode": "auto"}, ["speed", "balanced", "quality", "auto"]
        )
        == "auto"
    )
    assert (
        _resolve_bucket_mode({"mode": "speed", "resolved_mode": "unknown"}, ["speed", "balanced"])
        == "speed"
    )


def test_load_references_normalizes_and_validates(tmp_path: Path) -> None:
    bench = ChainlensLatencyBenchmark()

    missing = tmp_path / "missing.jsonl"
    with pytest.raises(RuntimeError, match="not found"):
        bench._load_references(missing)

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not json")
    with pytest.raises(RuntimeError, match="Invalid JSON"):
        bench._load_references(bad_json)

    jsonl = tmp_path / "refs.jsonl"
    jsonl.write_text(
        json.dumps({"query": "  Apple ", "reference": "Apple is a fruit."})
        + "\n"
        + json.dumps({"query": "Banana", "reference": "Banana is yellow."})
        + "\n"
    )
    refs = bench._load_references(jsonl)
    assert refs["apple"] == "Apple is a fruit."
    assert refs["banana"] == "Banana is yellow."

    json_dict = tmp_path / "refs.json"
    json_dict.write_text(
        json.dumps({"  Apple ": "Apple is a fruit.", "Banana": "Banana is yellow."})
    )
    refs2 = bench._load_references(json_dict)
    assert refs2["apple"] == "Apple is a fruit."


def test_score_quality_matches_normalized_reference(tmp_path: Path) -> None:
    bench = ChainlensLatencyBenchmark()
    refs_path = tmp_path / "refs.json"
    refs_path.write_text(json.dumps({"  Photosynthesis ": "Photosynthesis converts light."}))
    refs = bench._load_references(refs_path)

    row = {
        "query": "photosynthesis",
        "answer": "Photosynthesis converts light energy into chemical energy.",
    }
    recall, f1 = bench._score_quality(row, refs)
    assert recall is not None
    assert f1 is not None


def test_add_row_to_stats_and_bucket_stats() -> None:
    stats = _ModeStats()
    _add_row_to_stats(
        stats,
        {
            "duration_ms": 1000,
            "first_token_time_ms": 200,
            "status": "complete",
            "degraded": False,
            "degradation_reason": None,
            "cost_micros": 1000,
            "fallback_hit_count": 0,
        },
    )
    _add_row_to_stats(
        stats,
        {
            "duration_ms": 2000,
            "first_token_time_ms": 300,
            "status": "error",
            "degraded": True,
            "degradation_reason": "boom",
            "error": "timeout",
            "cost_micros": None,
            "fallback_hit_count": 0,
        },
    )
    bucket = _bucket_stats(stats)
    assert bucket["n_total"] == 2
    assert bucket["n_failed"] == 1
    assert bucket["error_rate"] == 0.5
    assert bucket["degraded_rate"] == 0.5
    assert bucket["samples_e2e"] == 2
    assert bucket["mean_cost_micros"] == 1000.0
    assert bucket["p95_e2e_ms"] == 1950.0


def test_percentile_empty_bucket_does_not_gate() -> None:
    """H2 + M18: empty buckets must not produce p95 = 0.0 and pass the gate."""
    # Build an empty speed bucket and a populated balanced bucket.
    stats = _ModeStats()
    _add_row_to_stats(
        stats,
        {
            "duration_ms": 1000,
            "first_token_time_ms": 100,
            "status": "complete",
            "degraded": False,
            "degradation_reason": None,
            "cost_micros": 1000,
            "fallback_hit_count": 0,
        },
    )
    metrics = {
        "overall": _bucket_stats(stats),
        "per_mode": {
            "speed": _bucket_stats(_ModeStats()),
            "balanced": _bucket_stats(stats),
        },
        "per_tier": {},
        "per_mode_tier": {},
    }
    # The gate should only see the populated balanced bucket.
    violations = _evaluate_chainlens_gate(metrics)
    assert not any("speed" in v for v in violations)


def test_evaluate_gate_flags_high_latency_and_cost() -> None:
    stats = _ModeStats()
    _add_row_to_stats(
        stats,
        {
            "duration_ms": 100_000,
            "first_token_time_ms": 10_000,
            "status": "complete",
            "degraded": False,
            "degradation_reason": None,
            "cost_micros": 1_000_000,
            "fallback_hit_count": 0,
        },
    )
    metrics = {
        "overall": _bucket_stats(stats),
        "per_mode": {"balanced": _bucket_stats(stats)},
        "per_tier": {},
        "per_mode_tier": {},
    }
    violations = _evaluate_chainlens_gate(metrics)
    assert any("p95 e2e" in v for v in violations)
    assert any("TTFB" in v for v in violations)
    assert any("mean cost" in v for v in violations)


def test_evaluate_gate_per_tier() -> None:
    stats = _ModeStats()
    _add_row_to_stats(
        stats,
        {
            "duration_ms": 100_000,
            "first_token_time_ms": None,
            "status": "complete",
            "degraded": False,
            "degradation_reason": None,
            "cost_micros": 1000,
            "fallback_hit_count": 0,
        },
    )
    metrics = {
        "overall": _bucket_stats(stats),
        "per_mode": {},
        "per_tier": {"short": _bucket_stats(stats)},
        "per_mode_tier": {},
    }
    violations = _evaluate_chainlens_gate(metrics)
    assert any("tier short p95 e2e" in v for v in violations)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_sync_success(respx_mock, isolated_config: Config, http, tmp_path: Path) -> None:
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(
        return_value=httpx.Response(200, json=_research_output(resolved_mode="balanced"))
    )

    artifact = await bench.run(
        ctx,
        modes="balanced",
        sample_n=1,
        workspace_id=42,
        concurrency=1,
    )

    assert artifact.extra["modes"] == ["balanced"]
    per_mode = artifact.metrics["per_mode"]["balanced"]
    assert per_mode["n_total"] == 1
    assert per_mode["p95_e2e_ms"] == 1200
    assert per_mode["mean_cost_micros"] == 5000
    assert artifact.metrics["per_tier"][""]["n_total"] == 1
    assert artifact.metrics["per_mode_tier"]["balanced:"]["n_total"] == 1


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_async_sse_and_detail(
    respx_mock, isolated_config: Config, http, tmp_path: Path
) -> None:
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    run_id = "run_123e4567-e89b-12d3-a456-426614174000"
    output = _research_output(resolved_mode="balanced")
    detail = _run_detail(run_id, output, status="success")

    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(
        return_value=httpx.Response(
            202,
            json={"run_id": run_id, "status": "running"},
            headers={"X-Run-Id": run_id},
        )
    )
    sse_body = (
        f"data: {json.dumps({'type': 'run.finished', 'run_id': run_id, 'status': 'success'})}\n\n"
    )
    respx_mock.get(f"/api/v1/workspaces/42/scrapers/runs/{run_id}/events").mock(
        return_value=httpx.Response(
            200,
            content=sse_body.encode("utf-8"),
            headers={"Content-Type": "text/event-stream"},
        )
    )
    respx_mock.get(f"/api/v1/workspaces/42/scrapers/runs/{run_id}").mock(
        return_value=httpx.Response(200, json=detail)
    )

    artifact = await bench.run(
        ctx,
        modes="balanced",
        sample_n=1,
        workspace_id=42,
        concurrency=1,
    )

    assert artifact.metrics["per_mode"]["balanced"]["n_total"] == 1


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_continues_on_one_error(
    respx_mock, isolated_config: Config, http, tmp_path: Path
) -> None:
    """H1: one failing cell must not abort the whole matrix."""
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    responses = [
        httpx.Response(500, json={"detail": "boom"}),
        httpx.Response(200, json=_research_output(resolved_mode="balanced", duration_ms=900)),
    ]
    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(side_effect=responses)

    artifact = await bench.run(
        ctx,
        modes="balanced",
        sample_n=2,
        workspace_id=42,
        concurrency=1,
    )

    per_mode = artifact.metrics["per_mode"]["balanced"]
    assert per_mode["n_total"] == 2
    assert per_mode["n_failed"] == 1
    assert per_mode["error_rate"] == 0.5
    assert per_mode["samples_e2e"] == 1


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_resolved_mode_divergence_creates_empty_bucket(
    respx_mock, isolated_config: Config, http, tmp_path: Path
) -> None:
    """H2: a resolved mode outside the requested set must not leave an empty bucket that passes."""
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    responses = [
        # speed resolves to balanced -> speed bucket stays empty
        httpx.Response(200, json=_research_output(resolved_mode="balanced", duration_ms=900)),
        httpx.Response(200, json=_research_output(resolved_mode="balanced", duration_ms=1100)),
    ]
    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(side_effect=responses)

    artifact = await bench.run(
        ctx,
        modes="speed,balanced",
        sample_n=1,
        workspace_id=42,
        concurrency=1,
    )

    per_mode = artifact.metrics["per_mode"]
    assert per_mode["speed"]["n_total"] == 0
    assert per_mode["speed"]["p95_e2e_ms"] is None
    assert per_mode["balanced"]["n_total"] == 2

    violations = _evaluate_chainlens_gate(artifact.metrics)
    assert not any("speed" in v for v in violations)


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_per_tier_aggregation(
    respx_mock, isolated_config: Config, http, tmp_path: Path
) -> None:
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(
        return_value=httpx.Response(200, json=_research_output(resolved_mode="balanced"))
    )

    artifact = await bench.run(
        ctx,
        modes="balanced",
        sample_n=1,
        workspace_id=42,
        tier="short",
        concurrency=1,
    )

    assert artifact.metrics["per_tier"]["short"]["n_total"] == 1
    assert artifact.metrics["per_mode_tier"]["balanced:short"]["n_total"] == 1


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_cost_cap_aborts(
    respx_mock, isolated_config: Config, http, tmp_path: Path
) -> None:
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(
        return_value=httpx.Response(200, json=_research_output(cost_micros=60_000))
    )

    with pytest.raises(RuntimeError, match="exceeds cap"):
        await bench.run(
            ctx,
            modes="balanced",
            sample_n=2,
            workspace_id=42,
            max_total_cost_micros=100_000,
            concurrency=1,
        )


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_fail_on_unratified_raises(
    respx_mock, isolated_config: Config, http, tmp_path: Path
) -> None:
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(
        return_value=httpx.Response(
            200, json=_research_output(duration_ms=1, first_token_time_ms=1, cost_micros=1)
        )
    )

    with pytest.raises(RuntimeError, match="not ratified"):
        await bench.run(
            ctx,
            modes="balanced",
            sample_n=1,
            workspace_id=42,
            fail_on_unratified=True,
            concurrency=1,
        )


@pytest.mark.asyncio
async def test_run_validates_args(isolated_config: Config, http, tmp_path: Path) -> None:
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    with pytest.raises(RuntimeError, match="--n must be >= 1"):
        await bench.run(ctx, modes="balanced", sample_n=0)
    with pytest.raises(RuntimeError, match="--concurrency must be >= 1"):
        await bench.run(ctx, modes="balanced", concurrency=0)
    with pytest.raises(RuntimeError, match="--poll-timeout must be > 0"):
        await bench.run(ctx, modes="balanced", poll_timeout=0)
    with pytest.raises(RuntimeError, match="--sync-timeout must be > 0"):
        await bench.run(ctx, modes="balanced", sync_timeout=0)
    with pytest.raises(RuntimeError, match="Unknown --modes"):
        await bench.run(ctx, modes="fast")


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_poll_run_summary_exits_only_on_terminal(
    respx_mock, isolated_config: Config, http, tmp_path: Path
) -> None:
    """L8: an unknown/pending status must not be treated as terminal."""
    bench = ChainlensLatencyBenchmark()
    run_id = "run_123e4567-e89b-12d3-a456-426614174000"
    detail_pending = _run_detail(run_id, None, status="pending")
    detail_success = _run_detail(run_id, _research_output(), status="success")

    respx_mock.get(f"/api/v1/workspaces/42/scrapers/runs/{run_id}").mock(
        side_effect=[
            httpx.Response(200, json=detail_pending),
            httpx.Response(200, json=detail_success),
        ]
    )

    result = await bench._poll_run_summary(
        http, _BASE, 42, run_id, poll_interval=0.01, poll_timeout=5.0
    )
    assert result["status"] == "success"


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_gate_failure_sends_notification(
    respx_mock, isolated_config: Config, http, tmp_path: Path, monkeypatch
) -> None:
    """M4: a gate failure must call the notification channel."""
    config = _test_config(isolated_config)
    ctx = _run_context(config, http)
    bench = ChainlensLatencyBenchmark()

    respx_mock.post("/api/v1/workspaces/42/scrapers/chainlens/research").mock(
        return_value=httpx.Response(
            200, json=_research_output(duration_ms=100_000, first_token_time_ms=1, cost_micros=1)
        )
    )

    calls = []

    async def fake_notify(*args, **kwargs):
        calls.append((args, kwargs))
        return False

    monkeypatch.setattr(
        "nowing_evals.suites.research.chainlens_latency.runner.notify_gate_failure", fake_notify
    )

    artifact = await bench.run(
        ctx,
        modes="balanced",
        sample_n=1,
        workspace_id=42,
        concurrency=1,
    )

    assert calls
    assert artifact.metrics["gate_violations"]


def test_report_section_renders_per_tier_and_none() -> None:
    bench = ChainlensLatencyBenchmark()
    metrics = {
        "per_mode": {
            "balanced": {
                "p50_e2e_ms": 1000.0,
                "p95_e2e_ms": 1200.0,
                "p50_ttfb_ms": None,
                "p95_ttfb_ms": 300.0,
                "mean_answer_recall": None,
                "mean_f1": 0.5,
                "samples_e2e": 1,
            },
        },
        "per_tier": {
            "short": {
                "p50_e2e_ms": 1000.0,
                "p95_e2e_ms": 1200.0,
                "p50_ttfb_ms": None,
                "p95_ttfb_ms": 300.0,
                "mean_cost_micros": 0.0,
                "samples_e2e": 1,
            },
        },
        "per_mode_tier": {
            "balanced:short": {
                "p50_e2e_ms": 1000.0,
                "p95_e2e_ms": 1200.0,
                "p50_ttfb_ms": None,
                "p95_ttfb_ms": 300.0,
                "mean_cost_micros": 0.0,
                "samples_e2e": 1,
            },
        },
        "overall": {
            "samples_e2e": 1,
        },
    }
    artifact = RunArtifact(
        suite="research",
        benchmark="chainlens_latency",
        run_timestamp="2026-08-04T00:00:00Z",
        raw_path=Path("raw.jsonl"),
        metrics=metrics,
        extra={"environment": "local"},
    )
    section = bench.report_section([artifact])
    assert "n/a" in section.body_md
    assert "Per tier" in section.body_md
    assert "Per mode x tier" in section.body_md
