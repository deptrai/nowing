"""Unit tests for chat/regression benchmark helpers."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx

from nowing_evals.core.config import Config, SuiteState
from nowing_evals.core.registry import RunArtifact, RunContext
from nowing_evals.suites.chat.regression.runner import (
    ChatRegressionBenchmark,
    _build_mode_matrix,
    _Case,
    _CaseResult,
    _contains_hits,
    _load_cases,
    _one_case_per_tag,
)

_BASE = "http://test"


@pytest.fixture
def http() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_BASE)


def _sse_body(events: list[dict]) -> bytes:
    parts = [f"data: {json.dumps(ev)}\n\n" for ev in events]
    parts.append("data: [DONE]\n\n")
    return "".join(parts).encode("utf-8")


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
    mode: str = "balanced",
    tier: str = "short",
    environment: str = "local",
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
        mode=mode,
        tier=tier,
        environment=environment,
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
    from nowing_evals.suites.chat.regression.runner import _DEFAULT_DATASET

    dataset_path = tmp_path / "cases.jsonl"
    with dataset_path.open("w", encoding="utf-8") as fh:
        for row in _DEFAULT_DATASET:
            fh.write(json.dumps(row) + "\n")

    cases = _load_cases(dataset_path)
    assert len(cases) == len(_DEFAULT_DATASET)
    for case in cases:
        assert case.case_id
        assert case.query


@pytest.fixture
def isolated_config(tmp_path: Path) -> Config:
    return Config(
        nowing_api_base="https://api.nowing.net",
        openrouter_api_key=None,
        openrouter_base_url="https://openrouter.ai/api/v1",
        nowing_jwt=None,
        nowing_refresh_token=None,
        nowing_user_email=None,
        nowing_user_password=None,
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )


@pytest.mark.asyncio
async def test_ingest_writes_and_validates_custom_dataset(
    isolated_config: Config, tmp_path: Path
) -> None:
    bench = ChatRegressionBenchmark()
    assert bench.requires_auth_for_ingest is False

    dataset_path = tmp_path / "custom.jsonl"
    rows = [
        {
            "case_id": "c1",
            "query": "What is Q3?",
            "tags": ["budget"],
            "mentioned_document_ids": [1, 2],
        },
        {"case_id": "c2", "query": "Single values", "tags": "tag", "mentioned_document_ids": 5},
    ]
    with dataset_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    async with httpx.AsyncClient() as http:
        ctx = RunContext(
            suite="chat",
            benchmark="regression",
            config=isolated_config,
            suite_state=None,  # type: ignore[arg-type]
            http=http,
        )
        await bench.ingest(ctx, dataset=dataset_path)

    cases = _load_cases(ctx.benchmark_data_dir() / "cases.jsonl")
    assert {c.case_id for c in cases} == {"c1", "c2"}
    assert cases[0].mentioned_document_ids == [1, 2]
    assert cases[1].tags == ["tag"]
    assert cases[1].mentioned_document_ids == [5]


@pytest.mark.asyncio
async def test_ingest_rejects_invalid_list_types(isolated_config: Config, tmp_path: Path) -> None:
    bench = ChatRegressionBenchmark()
    dataset_path = tmp_path / "bad.jsonl"
    with dataset_path.open("w", encoding="utf-8") as fh:
        fh.write(
            json.dumps({"case_id": "b1", "query": "x", "mentioned_document_ids": "1,2"}) + "\n"
        )

    async with httpx.AsyncClient() as http:
        ctx = RunContext(
            suite="chat",
            benchmark="regression",
            config=isolated_config,
            suite_state=None,  # type: ignore[arg-type]
            http=http,
        )
        with pytest.raises(
            RuntimeError, match="Invalid type for 'mentioned_document_ids' in case 'b1'"
        ):
            await bench.ingest(ctx, dataset=dataset_path)


def test_load_cases_with_multi_turn_list() -> None:
    # Avoid relying on filesystem; write to a temp path manually.
    import tempfile

    row = {
        "case_id": "mt1",
        "query": "first",
        "tags": ["multi"],
        "turns": [
            {"query": "turn one", "expected_contains": ["one"]},
            {"query": "turn two", "expected_contains": ["two"]},
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
        path = Path(fh.name)

    try:
        cases = _load_cases(path)
        assert len(cases) == 1
        assert cases[0].case_id == "mt1"
        assert cases[0].query == "first"
        assert cases[0].turns is not None
        assert len(cases[0].turns) == 2
        assert cases[0].turns[1].query == "turn two"
        assert cases[0].turns[1].expected_contains == ["two"]
    finally:
        path.unlink()


def test_validate_case_row_rejects_bad_turns() -> None:
    from nowing_evals.suites.chat.regression.runner import _validate_case_row

    with pytest.raises(RuntimeError, match="'turns' must be a list"):
        _validate_case_row({"case_id": "b", "query": "q", "turns": "notalist"})


def test_report_section_per_tag_includes_citations_and_keyword_match() -> None:
    bench = ChatRegressionBenchmark()
    metrics = {
        "overall": {
            "samples": 2,
            "n_failed": 0,
            "error_rate": 0.0,
            "p95_e2e_ms": 120.0,
            "p95_ttfb_ms": 10.0,
            "p95_cost_micros": 50.0,
            "total_cost_micros": 100.0,
            "p95_citation_count": 3.0,
            "mean_total_tokens": 200.0,
            "contains_match_rate": 0.75,
        },
        "per_tag": {
            "budget": {
                "samples": 2,
                "error_rate": 0.0,
                "p95_e2e_ms": 120.0,
                "p95_cost_micros": 50.0,
                "p95_citation_count": 3.0,
                "contains_match_rate": 0.75,
            }
        },
    }
    artifact = RunArtifact(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        raw_path=Path("/tmp/raw.jsonl"),
        metrics=metrics,
    )
    section = bench.report_section([artifact])
    assert "p95 citations" in section.body_md
    assert "keyword match" in section.body_md
    assert "budget" in section.body_md


def test_aggregate_per_mode_tier_and_environment() -> None:
    bench = ChatRegressionBenchmark()
    results = [
        _make_result("a", mode="balanced", tier="short", latency_ms=1000, cost_micros=50),
        _make_result("b", mode="balanced", tier="long_context", latency_ms=2000, cost_micros=150),
        _make_result("c", mode="quality", tier="short", latency_ms=3000, cost_micros=100),
        _make_result("d", mode="quality", tier="long_context", error="boom", finished_normally=False),
    ]

    metrics = bench._aggregate(results)

    assert "per_mode" in metrics
    assert "per_tier" in metrics
    assert "per_mode_tier" in metrics
    assert metrics["per_mode"]["balanced"]["samples"] == 2
    assert metrics["per_mode"]["quality"]["n_failed"] == 1
    assert metrics["per_tier"]["short"]["samples"] == 2
    assert metrics["per_mode_tier"]["balanced:short"]["p95_e2e_ms"] == 1000.0
    assert metrics["per_mode_tier"]["quality:long_context"]["error_rate"] == 1.0


def _make_case(
    case_id: str,
    tags: list[str],
    tier: str = "short",
    modes: list[str] | None = None,
) -> _Case:
    return _Case(
        case_id=case_id,
        query=f"q-{case_id}",
        tags=tags,
        mentioned_document_ids=[],
        disabled_tools=[],
        expected_contains=[],
        tier=tier,
        modes=modes,
    )


def test_build_mode_matrix_full_and_quick() -> None:
    cases = [
        _make_case("c1", ["a"], tier="short", modes=["speed"]),
        _make_case("c2", ["b"], tier="long_context", modes=None),
    ]
    full = _build_mode_matrix(cases, ["balanced", "quality"], "full")
    assert len(full) == 3
    assert {m for _, m in full} == {"speed", "balanced", "quality"}

    quick = _build_mode_matrix(cases, ["balanced", "quality"], "quick")
    assert len(quick) == 2  # one case per unique tag (a, b)
    assert quick[0][0].case_id == "c1"
    assert quick[0][1] == "balanced"


def test_one_case_per_tag_preserves_order() -> None:
    cases = [
        _make_case("c1", ["a", "b"]),
        _make_case("c2", ["b"]),
        _make_case("c3", ["c"]),
    ]
    selected = _one_case_per_tag(cases)
    assert [c.case_id for c in selected] == ["c1", "c3"]


def test_report_section_local_prod_delta() -> None:
    bench = ChatRegressionBenchmark()
    local = RunArtifact(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:00Z",
        raw_path=Path("/tmp/raw.jsonl"),
        metrics={
            "overall": {"p95_e2e_ms": 1000.0, "p95_cost_micros": 100.0, "p95_citation_count": 2.0},
            "per_mode": {"balanced": {"p95_e2e_ms": 1000.0}},
        },
        extra={"environment": "local"},
    )
    prod = RunArtifact(
        suite="chat",
        benchmark="regression",
        run_timestamp="2026-08-04T00:00:01Z",
        raw_path=Path("/tmp/raw.jsonl"),
        metrics={
            "overall": {"p95_e2e_ms": 1200.0, "p95_cost_micros": 120.0, "p95_citation_count": 2.5},
            "per_mode": {"balanced": {"p95_e2e_ms": 1200.0}},
        },
        extra={"environment": "production"},
    )
    section = bench.report_section([local, prod])
    assert "Local vs production parity" in section.body_md
    assert "+20.0%" in section.body_md


@pytest.mark.asyncio
@respx.mock(base_url=_BASE)
async def test_run_executes_mode_matrix_and_tags_environment(
    respx_mock, http, isolated_config: Config, tmp_path: Path
) -> None:
    bench = ChatRegressionBenchmark()
    config = replace(isolated_config, nowing_api_base=_BASE)

    respx_mock.post("/api/v1/threads").mock(
        return_value=httpx.Response(200, json={"id": 7})
    )
    respx_mock.delete(url__regex=r"/api/v1/threads/.*").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )

    body = _sse_body(
        [
            {"type": "start", "messageId": "m1"},
            {"type": "text-start", "id": "t1"},
            {"type": "text-delta", "id": "t1", "delta": "Answer"},
            {"type": "text-end", "id": "t1"},
            {"type": "finish"},
        ]
    )
    respx_mock.post("/api/v1/new_chat").mock(
        return_value=httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "text/event-stream"},
        )
    )

    dataset_path = tmp_path / "cases.jsonl"
    rows = [
        {"case_id": "c1", "query": "q1", "tags": ["a"], "tier": "short"},
        {"case_id": "c2", "query": "q2", "tags": ["b"], "tier": "long_context"},
    ]
    with dataset_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    suite_state = SuiteState(
        search_space_id=0,
        chat_model_id=0,
        provider_model="",
        created_at="2026-08-04T00:00:00Z",
    )
    ctx = RunContext(
        suite="chat",
        benchmark="regression",
        config=config,
        suite_state=suite_state,
        http=http,
    )

    artifact = await bench.run(
        ctx,
        dataset=dataset_path,
        search_space_id=1,
        modes="speed,balanced",
        environment="production",
        concurrency=1,
    )

    assert artifact.extra["environment"] == "production"
    assert set(artifact.extra["modes"]) == {"speed", "balanced"}
    assert len(artifact.metrics["per_mode"]) == 2
    assert set(artifact.metrics["per_mode"].keys()) == {"speed", "balanced"}
    assert len(artifact.metrics["per_tier"]) == 2
    assert set(artifact.metrics["per_mode_tier"].keys()) == {
        "speed:short",
        "speed:long_context",
        "balanced:short",
        "balanced:long_context",
    }

    new_chat_calls = [c for c in respx_mock.calls if c.request.method == "POST" and "/new_chat" in str(c.request.url)]
    assert len(new_chat_calls) == 4  # 2 cases × 2 modes
