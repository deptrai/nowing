"""Chat regression benchmark.

Runs a dataset of user queries against ``/api/v1/new_chat`` and records
per-turn latency, token usage, cost, citations, and finish status.

Designed as a deploy gate: it does not require a reference answer;
instead it detects drift in error rate, latency, cost, and citation
behaviour against gate thresholds.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ....core.arms import ArmRequest, ArmResult, NowingArm
from ....core.clients import NewChatClient
from ....core.config import utc_iso_timestamp
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
    register,
)
from .operational import summarize_operational

logger = logging.getLogger(__name__)


_DESCRIPTION = (
    "Chat response regression: per-turn latency, token/cost, citations, "
    "finish status, and optional keyword checks."
)

_DEFAULT_DATASET: list[dict[str, Any]] = [
    {
        "case_id": "chat-mem-001",
        "query": "What are the key facts we have stored about our competitor AlphaCorp?",
        "tags": ["memory", "factual"],
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["AlphaCorp"],
    },
    {
        "case_id": "chat-doc-001",
        "query": "Summarize the main clauses of the NDA document.",
        "tags": ["document"],
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["NDA", "confidential"],
    },
    {
        "case_id": "chat-research-001",
        "query": "What is the state of RAG evaluation in 2025?",
        "tags": ["deep-research"],
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["RAG", "2025"],
    },
    {
        "case_id": "chat-multi-001",
        "query": "Find the latest revenue numbers for Apple and compare them to Samsung.",
        "tags": ["multi-tool", "factual"],
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["Apple", "Samsung"],
    },
    {
        "case_id": "chat-creative-001",
        "query": "Draft a one-paragraph welcome message for a new workspace member.",
        "tags": ["creative"],
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["welcome"],
    },
]


@dataclass
class _Turn:
    query: str
    expected_contains: list[str]


@dataclass
class _Case:
    case_id: str
    query: str
    tags: list[str]
    mentioned_document_ids: list[int]
    disabled_tools: list[str]
    expected_contains: list[str]
    turns: list[_Turn] | None = None


@dataclass
class _CaseResult:
    case_id: str
    tags: list[str]
    query: str
    text: str
    error: str | None
    latency_ms: int
    ttfb_ms: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_micros: int
    citation_count: int
    finished_normally: bool
    expected_contains: list[str]
    contains_hits: int
    raw_events: list[dict[str, Any]] | None = None
    call_details: list[dict[str, Any]] | None = None
    error_code: str | None = None
    operational: dict[str, Any] | None = None


def _aggregate_operational(
    cases: list[_CaseResult],
    *,
    overall: dict[str, Any] | None = None,
    concurrency: int = 1,
    threads: int = 1,
) -> dict[str, Any]:
    """Sum per-case operational summaries across a list of results."""
    n = len(cases)
    if not n:
        return {"samples": 0}

    total_attempts = 0
    total_successes = 0
    total_failures = 0
    total_drops = 0
    scrape_attempts = 0
    scrape_successes = 0
    scrape_failures = 0
    error_reason_counts: dict[str, int] = {}
    degradation_reasons: dict[str, int] = {}
    tool_stats: dict[str, dict[str, int]] = {}
    fallback_kb_hits = 0
    n_error_frames = 0
    n_terminal_info = 0
    n_terminal_errors = 0
    engine_unavailable_count = 0

    for c in cases:
        op = c.operational or {}
        total_attempts += op.get("total_tool_attempts", 0)
        total_successes += op.get("total_tool_successes", 0)
        total_failures += op.get("total_tool_failures", 0)
        total_drops += op.get("total_tool_drops", 0)
        scrape_attempts += op.get("scrape_attempts", 0)
        scrape_successes += op.get("scrape_successes", 0)
        scrape_failures += op.get("scrape_failures", 0)
        fallback_kb_hits += op.get("fallback_kb_hits", 0)
        n_error_frames += op.get("n_error_frames", 0)
        n_terminal_info += op.get("n_terminal_info", 0)
        n_terminal_errors += op.get("n_terminal_errors", 0)
        engine_unavailable_count += op.get("engine_unavailable_count", 0)

        for reason, count in op.get("error_reason_counts", {}).items():
            error_reason_counts[reason] = error_reason_counts.get(reason, 0) + count
        for reason, count in op.get("degradation_reasons", {}).items():
            degradation_reasons[reason] = degradation_reasons.get(reason, 0) + count

        for name, stats in op.get("tool_stats", {}).items():
            entry = tool_stats.setdefault(
                name,
                {"attempts": 0, "successes": 0, "failures": 0, "drops": 0},
            )
            entry["attempts"] += stats.get("attempts", 0)
            entry["successes"] += stats.get("successes", 0)
            entry["failures"] += stats.get("failures", 0)
            entry["drops"] += stats.get("drops", 0)

    def _rate(num: int, denom: int) -> float | None:
        return num / denom if denom else None

    for _name, entry in tool_stats.items():
        attempts = entry["attempts"]
        entry["success_rate"] = _rate(entry["successes"], attempts)
        entry["drop_rate"] = _rate(entry["drops"], attempts)

    under_load = concurrency > 1 or threads > 1
    p95_latency_under_load_ms = None
    error_rate_under_load = None
    rate_limited_rate_under_load = None
    engine_unavailable_rate_under_load = None
    if under_load and overall:
        p95_latency_under_load_ms = overall.get("p95_e2e_ms")
        error_rate_under_load = overall.get("error_rate")
        rate_limited_rate_under_load = _rate(error_reason_counts.get("rate_limit", 0), n)
        engine_unavailable_rate_under_load = _rate(engine_unavailable_count, n)

    return {
        "samples": n,
        "scrape_attempts": scrape_attempts,
        "scrape_successes": scrape_successes,
        "scrape_failures": scrape_failures,
        "scrape_success_rate": _rate(scrape_successes, scrape_attempts),
        "scrape_failure_rate": _rate(scrape_failures, scrape_attempts),
        "total_tool_attempts": total_attempts,
        "total_tool_successes": total_successes,
        "total_tool_failures": total_failures,
        "total_tool_drops": total_drops,
        "tool_drop_rate": _rate(total_drops, total_attempts),
        "tool_success_rate": _rate(total_successes, total_attempts),
        "tool_stats": tool_stats,
        "captcha_rate": _rate(error_reason_counts.get("captcha", 0), n),
        "rate_limited_rate": _rate(error_reason_counts.get("rate_limit", 0), n),
        "timeout_rate": _rate(error_reason_counts.get("timeout", 0), n),
        "server_error_rate": _rate(error_reason_counts.get("server_error", 0), n),
        "parse_error_rate": _rate(error_reason_counts.get("parse_error", 0), n),
        "engine_unavailable_rate": _rate(engine_unavailable_count, n),
        "n_error_frames": n_error_frames,
        "n_terminal_info": n_terminal_info,
        "n_terminal_errors": n_terminal_errors,
        "error_reason_counts": error_reason_counts,
        "degradation_reasons": degradation_reasons,
        "fallback_kb_hits": fallback_kb_hits,
        "p95_latency_under_load_ms": p95_latency_under_load_ms,
        "error_rate_under_load": error_rate_under_load,
        "rate_limited_rate_under_load": rate_limited_rate_under_load,
        "engine_unavailable_rate_under_load": engine_unavailable_rate_under_load,
        "concurrency": concurrency,
        "threads": threads,
    }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    idx = (n - 1) * p
    low = int(idx)
    high = low + 1
    if high >= n:
        return s[-1]
    weight = idx - low
    return s[low] * (1 - weight) + s[high] * weight


def _cases_path(ctx: RunContext) -> Path:
    return ctx.benchmark_data_dir() / "cases.jsonl"


def _list_of_str(value: Any, field: str, case_id: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value  # type: ignore[return-value]
    raise RuntimeError(
        f"Invalid type for '{field}' in case {case_id!r}: expected list of strings, got {value!r}"
    )


def _list_of_int(value: Any, field: str, case_id: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list) and all(isinstance(v, int) for v in value):
        return value  # type: ignore[return-value]
    raise RuntimeError(
        f"Invalid type for '{field}' in case {case_id!r}: expected list of integers, got {value!r}"
    )


def _validate_turn(value: Any, case_id: Any, index: int) -> _Turn:
    if not isinstance(value, dict):
        raise RuntimeError(
            f"Invalid turn {index} in case {case_id!r}: expected object, got {value!r}"
        )
    query = value.get("query")
    if not isinstance(query, str) or not query.strip():
        raise RuntimeError(f"Turn {index} in case {case_id!r} missing or empty 'query'")
    return _Turn(
        query=query,
        expected_contains=_list_of_str(
            value.get("expected_contains"), "expected_contains", case_id
        ),
    )


def _validate_case_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise RuntimeError(f"Invalid case row: expected object, got {row!r}")
    case_id = row.get("case_id")
    if case_id is None:
        raise RuntimeError("Case row missing 'case_id'")
    query = row.get("query")
    if not isinstance(query, str) or not query.strip():
        raise RuntimeError(f"Case {case_id!r} missing or empty 'query'")
    turns_value = row.get("turns")
    turns: list[_Turn] | None = None
    if turns_value is not None:
        if not isinstance(turns_value, list):
            raise RuntimeError(f"Case {case_id!r} 'turns' must be a list, got {turns_value!r}")
        turns = [_validate_turn(t, case_id, i) for i, t in enumerate(turns_value)]
    return {
        "case_id": str(case_id),
        "query": query,
        "tags": _list_of_str(row.get("tags"), "tags", case_id),
        "mentioned_document_ids": _list_of_int(
            row.get("mentioned_document_ids"), "mentioned_document_ids", case_id
        ),
        "disabled_tools": _list_of_str(row.get("disabled_tools"), "disabled_tools", case_id),
        "expected_contains": _list_of_str(
            row.get("expected_contains"), "expected_contains", case_id
        ),
        "turns": turns,
    }


def _load_cases(path: Path) -> list[_Case]:
    cases: list[_Case] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = _validate_case_row(json.loads(line))
            cases.append(
                _Case(
                    case_id=row["case_id"],
                    query=row["query"],
                    tags=row["tags"],
                    mentioned_document_ids=row["mentioned_document_ids"],
                    disabled_tools=row["disabled_tools"],
                    expected_contains=row["expected_contains"],
                    turns=row["turns"],
                )
            )
    return cases


def _contains_hits(text: str, expected: list[str]) -> int:
    lower = text.lower()
    return sum(1 for term in expected if term.lower() in lower)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _context_drift(turn_snapshots: list[dict[str, Any]]) -> float | None:
    """Compare first vs last turn keyword match ratio.

    A positive value means the last turn matched fewer keywords relative to
    its own expectations than the first turn — i.e. context appears to drift.
    """
    if not turn_snapshots:
        return None
    first = turn_snapshots[0]
    last = turn_snapshots[-1]
    first_total = first.get("expected_count") or 0
    last_total = last.get("expected_count") or 0
    if not first_total or not last_total:
        return None
    first_ratio = first.get("contains_hits", 0) / first_total
    last_ratio = last.get("contains_hits", 0) / last_total
    return first_ratio - last_ratio


def _per_turn_metrics(
    turn_snapshots: list[dict[str, Any]],
    turns: list[_Turn],
) -> dict[str, Any]:
    """Per-turn stability metrics for multi-turn cases."""
    n_turns = len(turns)
    n_failed_turns = sum(1 for t in turn_snapshots if t.get("error"))
    return {
        "turns": turn_snapshots,
        "n_turns": n_turns,
        "n_failed_turns": n_failed_turns,
        "turn_error_rate": n_failed_turns / n_turns if n_turns else None,
        "context_drift_score": _context_drift(turn_snapshots),
    }


class ChatRegressionBenchmark:
    suite: str = "chat"
    name: str = "regression"
    headline: bool = False
    description: str = _DESCRIPTION
    requires_suite_setup: bool = False
    requires_auth_for_ingest: bool = False

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--search-space-id",
            type=int,
            default=None,
            help="SearchSpace used for thread creation.",
        )
        parser.add_argument(
            "--workspace-id",
            type=int,
            default=None,
            help="Workspace id for audit/reporting only.",
        )
        parser.add_argument(
            "--dataset",
            type=Path,
            default=None,
            help="JSONL dataset (default: data/chat/regression/cases.jsonl).",
        )
        parser.add_argument(
            "--n",
            dest="sample_n",
            type=int,
            default=None,
            help="Cap the number of cases.",
        )
        parser.add_argument("--concurrency", type=int, default=1)
        parser.add_argument(
            "--threads",
            type=int,
            default=1,
            help="Number of parallel chat threads to open per case for stress testing.",
        )
        parser.add_argument(
            "--tags",
            default=None,
            help="Comma-separated tag filter (e.g. memory,document).",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=300.0,
            help="Per-turn timeout in seconds.",
        )
        parser.add_argument(
            "--backend-build-id",
            type=str,
            default=None,
            help="Deployed backend build/commit identifier this run evaluates.",
        )

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        # ponytail: sync pathlib calls are fine here — ingest only touches small
        # local JSONL files and the project already uses this pattern elsewhere.
        dataset_path: Path | None = opts.get("dataset")
        target = _cases_path(ctx)

        if dataset_path:
            if not dataset_path.is_file():  # noqa: ASYNC240
                raise RuntimeError(f"Dataset not found: {dataset_path}")
            text = dataset_path.read_text(encoding="utf-8")  # noqa: ASYNC240
            # Validate that every non-empty line is a JSON object with at least case_id and query.
            with target.open("w", encoding="utf-8") as fh:
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    row = _validate_case_row(json.loads(line))
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            logger.info("Installed %d cases from %s", len(_load_cases(target)), dataset_path)
            return

        # No dataset provided: write the default sample dataset.
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            for row in _DEFAULT_DATASET:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("Wrote default %d sample cases to %s", len(_DEFAULT_DATASET), target)

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        search_space_id = opts.get("search_space_id") or ctx.search_space_id
        if not search_space_id:
            raise RuntimeError("--search-space-id or a suite setup with a SearchSpace is required.")
        workspace_id = opts.get("workspace_id")
        sample_n = opts.get("sample_n")
        concurrency = max(1, int(opts.get("concurrency") or 1))
        threads = max(1, int(opts.get("threads") or 1))
        tags_filter = opts.get("tags")
        timeout_s = float(opts.get("timeout") or 300.0)
        build_id = opts.get("backend_build_id")

        dataset_path = opts.get("dataset") or _cases_path(ctx)
        if not dataset_path.is_file():
            raise RuntimeError(
                f"Dataset not found: {dataset_path}. Run "
                f"`python -m nowing_evals ingest chat regression` first."
            )

        all_cases = _load_cases(dataset_path)
        cases = all_cases
        if tags_filter:
            wanted = {t.strip() for t in tags_filter.split(",") if t.strip()}
            cases = [c for c in cases if wanted.intersection(c.tags)]
        if sample_n:
            cases = cases[:sample_n]

        # Stress mode: run the same case in multiple parallel chat threads.
        if threads > 1:
            cases = [replace(c, case_id=f"{c.case_id}:t{i}") for c in cases for i in range(threads)]

        if not cases:
            raise RuntimeError("No chat cases selected for the requested filters.")

        client = NewChatClient(ctx.http, ctx.config.nowing_api_base)
        arm = NowingArm(client=client, search_space_id=search_space_id)

        sem = asyncio.Semaphore(concurrency)

        async def _run_one(case: _Case) -> _CaseResult:
            async with sem:
                turns = (
                    list(case.turns)
                    if case.turns
                    else [_Turn(query=case.query, expected_contains=case.expected_contains)]
                )
                final_expected = turns[-1].expected_contains
                thread_id: int | None = None
                turn_results: list[ArmResult] = []
                turn_snapshots: list[dict[str, Any]] = []

                def _build_operational(last_text: str) -> tuple[dict[str, Any], list[dict], list]:
                    raw_events = [ev for r in turn_results for ev in r.extra.get("raw_events", [])]
                    call_details: list[dict[str, Any]] = []
                    for r in turn_results:
                        cd = r.extra.get("call_details")
                        if isinstance(cd, list):
                            call_details.extend(cd)
                    operational = summarize_operational(raw_events, call_details, last_text)
                    operational.update(_per_turn_metrics(turn_snapshots, turns))
                    return operational, raw_events, call_details

                def _make_error_result(
                    error_text: str,
                    error_code: str | None = None,
                    last_text: str = "",
                    last_result: ArmResult | None = None,
                    extra_latency_ms: int = 0,
                ) -> _CaseResult:
                    latencies = [r.latency_ms for r in turn_results]
                    ttfbs = [
                        r.extra.get("ttfb_ms")
                        for r in turn_results
                        if r.extra.get("ttfb_ms") is not None
                    ]
                    prompt_tokens = sum(r.input_tokens for r in turn_results)
                    completion_tokens = sum(r.output_tokens for r in turn_results)
                    cost = sum(r.cost_micros for r in turn_results)
                    operational, raw_events, call_details = _build_operational(last_text)
                    return _CaseResult(
                        case_id=case.case_id,
                        tags=case.tags,
                        query=case.query,
                        text=last_text,
                        error=error_text,
                        error_code=error_code,
                        latency_ms=sum(latencies) + extra_latency_ms,
                        ttfb_ms=min(ttfbs) if ttfbs else None,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                        cost_micros=cost,
                        citation_count=len(last_result.citations) if last_result else 0,
                        finished_normally=False,
                        expected_contains=final_expected,
                        contains_hits=_contains_hits(last_text, final_expected),
                        raw_events=raw_events,
                        call_details=call_details or None,
                        operational=operational,
                    )

                try:
                    for i, turn in enumerate(turns):
                        options: dict[str, Any] = (
                            {"disabled_tools": case.disabled_tools} if case.disabled_tools else {}
                        )
                        if thread_id is not None:
                            options["thread_id"] = thread_id
                        request = ArmRequest(
                            question_id=f"{case.case_id}:turn{i}",
                            prompt=turn.query,
                            mentioned_document_ids=case.mentioned_document_ids or None,
                            options=options,
                        )
                        try:
                            result = await asyncio.wait_for(arm.answer(request), timeout=timeout_s)
                        except TimeoutError:
                            turn_snapshots.append(
                                {
                                    "query": turn.query,
                                    "latency_ms": int(timeout_s * 1000),
                                    "ttfb_ms": None,
                                    "citation_count": 0,
                                    "contains_hits": 0,
                                    "expected_count": len(turn.expected_contains),
                                    "error": "TimeoutError: turn exceeded timeout",
                                    "error_code": "TimeoutError",
                                }
                            )
                            return _make_error_result(
                                "TimeoutError: turn exceeded timeout",
                                error_code="TimeoutError",
                                last_text=turn_results[-1].raw_text if turn_results else "",
                                last_result=turn_results[-1] if turn_results else None,
                                extra_latency_ms=int(timeout_s * 1000),
                            )

                        if result.error:
                            turn_snapshots.append(
                                {
                                    "query": turn.query,
                                    "latency_ms": result.latency_ms,
                                    "ttfb_ms": result.extra.get("ttfb_ms"),
                                    "citation_count": len(result.citations),
                                    "contains_hits": _contains_hits(
                                        result.raw_text, turn.expected_contains
                                    ),
                                    "expected_count": len(turn.expected_contains),
                                    "error": result.error,
                                    "error_code": result.extra.get("error_code"),
                                }
                            )
                            return _make_error_result(
                                result.error,
                                error_code=result.extra.get("error_code"),
                                last_text=result.raw_text,
                                last_result=result,
                                extra_latency_ms=result.latency_ms,
                            )

                        turn_results.append(result)
                        thread_id = result.extra.get("thread_id")
                        turn_snapshots.append(
                            {
                                "query": turn.query,
                                "latency_ms": result.latency_ms,
                                "ttfb_ms": result.extra.get("ttfb_ms"),
                                "citation_count": len(result.citations),
                                "contains_hits": _contains_hits(
                                    result.raw_text, turn.expected_contains
                                ),
                                "expected_count": len(turn.expected_contains),
                                "error": None,
                                "error_code": None,
                            }
                        )
                finally:
                    if thread_id is not None and hasattr(arm, "delete_thread"):
                        try:
                            await arm.delete_thread(thread_id)
                        except Exception as exc:  # noqa: BLE001
                            logger.debug("Failed to delete thread %s: %s", thread_id, exc)

                if not turn_results:
                    return _make_error_result("No turns produced a result")

                final = turn_results[-1]
                prompt_tokens = sum(r.input_tokens for r in turn_results)
                completion_tokens = sum(r.output_tokens for r in turn_results)
                cost = sum(r.cost_micros for r in turn_results)
                ttfbs = [
                    r.extra.get("ttfb_ms")
                    for r in turn_results
                    if r.extra.get("ttfb_ms") is not None
                ]
                operational, raw_events, call_details = _build_operational(final.raw_text)
                return _CaseResult(
                    case_id=case.case_id,
                    tags=case.tags,
                    query=case.query,
                    text=final.raw_text,
                    error=None,
                    error_code=None,
                    latency_ms=sum(r.latency_ms for r in turn_results),
                    ttfb_ms=min(ttfbs) if ttfbs else None,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    cost_micros=cost,
                    citation_count=len(final.citations),
                    finished_normally=all(
                        r.extra.get("finished_normally", False) for r in turn_results
                    ),
                    expected_contains=final_expected,
                    contains_hits=_contains_hits(final.raw_text, final_expected),
                    raw_events=raw_events,
                    call_details=call_details or None,
                    operational=operational,
                )

        results = await asyncio.gather(*(_run_one(c) for c in cases))

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        with raw_path.open("w", encoding="utf-8") as fh:
            for r in results:
                fh.write(
                    json.dumps(
                        {
                            "case_id": r.case_id,
                            "tags": r.tags,
                            "query": r.query,
                            "text": r.text,
                            "error": r.error,
                            "latency_ms": r.latency_ms,
                            "ttfb_ms": r.ttfb_ms,
                            "prompt_tokens": r.prompt_tokens,
                            "completion_tokens": r.completion_tokens,
                            "total_tokens": r.total_tokens,
                            "cost_micros": r.cost_micros,
                            "citation_count": r.citation_count,
                            "finished_normally": r.finished_normally,
                            "expected_contains": r.expected_contains,
                            "contains_hits": r.contains_hits,
                            "error_code": r.error_code,
                            "n_raw_events": len(r.raw_events) if r.raw_events else 0,
                            "operational": r.operational,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )

        metrics = self._aggregate(results, concurrency=concurrency, threads=threads)

        extra = {
            "search_space_id": search_space_id,
            "workspace_id": workspace_id,
            "n_cases": len(cases),
            "concurrency": concurrency,
            "threads": threads,
            "timeout_s": timeout_s,
            "tags_filter": tags_filter,
            "build_id": build_id,
            "dataset_path": str(dataset_path),
        }

        _write_json_atomic(
            run_dir / "run_artifact.json",
            {
                "suite": self.suite,
                "benchmark": self.name,
                "raw_path": "raw.jsonl",
                "metrics": metrics,
                "extra": extra,
            },
        )

        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra=extra,
        )

    def _aggregate(
        self,
        results: list[_CaseResult],
        *,
        concurrency: int = 1,
        threads: int = 1,
    ) -> dict[str, Any]:
        def _bucket(cases: list[_CaseResult]) -> dict[str, Any]:
            n = len(cases)
            if not n:
                return {"samples": 0}
            latencies = [float(c.latency_ms) for c in cases]
            ttfbs = [float(c.ttfb_ms) for c in cases if c.ttfb_ms is not None]
            costs = [float(c.cost_micros) for c in cases]
            citations = [float(c.citation_count) for c in cases]
            tokens = [float(c.total_tokens) for c in cases]
            errors = [c for c in cases if c.error or not c.finished_normally]
            with_contains = [c for c in cases if c.expected_contains]
            contains_hits = [c for c in with_contains if c.contains_hits > 0]
            return {
                "samples": n,
                "n_failed": len(errors),
                "error_rate": len(errors) / n,
                "p50_e2e_ms": _percentile(latencies, 0.5),
                "p95_e2e_ms": _percentile(latencies, 0.95),
                "p50_ttfb_ms": _percentile(ttfbs, 0.5) if ttfbs else None,
                "p95_ttfb_ms": _percentile(ttfbs, 0.95) if ttfbs else None,
                "p50_cost_micros": _percentile(costs, 0.5),
                "p95_cost_micros": _percentile(costs, 0.95),
                "total_cost_micros": sum(costs),
                "p50_citation_count": _percentile(citations, 0.5),
                "p95_citation_count": _percentile(citations, 0.95),
                "mean_total_tokens": sum(tokens) / n,
                "contains_match_rate": (
                    len(contains_hits) / len(with_contains) if with_contains else None
                ),
            }

        overall = _bucket(results)
        per_tag: dict[str, list[_CaseResult]] = {}
        for r in results:
            for tag in r.tags:
                per_tag.setdefault(tag, []).append(r)

        per_tag_buckets = {tag: _bucket(items) for tag, items in per_tag.items()}

        operational = _aggregate_operational(
            results,
            overall=overall,
            concurrency=concurrency,
            threads=threads,
        )

        return {
            "overall": overall,
            "operational": operational,
            "per_tag": per_tag_buckets,
            "per_tag_operational": {
                tag: _aggregate_operational(
                    items,
                    overall=per_tag_buckets[tag],
                    concurrency=concurrency,
                    threads=threads,
                )
                for tag, items in per_tag.items()
            },
        }

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="Chat regression",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        overall = m.get("overall", {})
        lines = [
            f"- Cases: {overall.get('samples', '?')} "
            f"(failed: {overall.get('n_failed', '?')}, "
            f"error rate: {overall.get('error_rate', 0):.2%})",
            f"- p95 e2e: {overall.get('p95_e2e_ms', 0):.0f} ms",
            f"- p95 TTFB: {overall.get('p95_ttfb_ms') or 'n/a'} ms",
            f"- p95 cost: {overall.get('p95_cost_micros', 0):.0f} micros "
            f"(total: {overall.get('total_cost_micros', 0):.0f})",
            f"- p95 citations: {overall.get('p95_citation_count', 0):.1f}",
            f"- mean tokens: {overall.get('mean_total_tokens', 0):.1f}",
        ]
        if overall.get("contains_match_rate") is not None:
            lines.append(f"- keyword match rate: {overall['contains_match_rate']:.2%}")

        operational = m.get("operational", {})
        if operational.get("samples"):
            lines.append("")
            lines.append("### Operational / Stability")
            lines.append(
                f"- scrape: {operational.get('scrape_successes', 0)}/{operational.get('scrape_attempts', 0)} "
                f"success ({operational.get('scrape_success_rate') or 0:.2%})"
            )
            lines.append(
                f"- tool drop rate: {operational.get('tool_drop_rate') or 0:.2%} "
                f"({operational.get('total_tool_drops', 0)} / {operational.get('total_tool_attempts', 0)})"
            )
            lines.append(
                f"- engine unavailable rate: {operational.get('engine_unavailable_rate') or 0:.2%}"
            )
            lines.append(f"- fallback KB hits: {operational.get('fallback_kb_hits', 0)}")
            reasons = operational.get("error_reason_counts", {})
            if reasons:
                lines.append(
                    "- failure reasons: "
                    + ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items()))
                )
            tool_stats = operational.get("tool_stats", {})
            if tool_stats:
                lines.append("")
                lines.append("| tool | attempts | successes | failures | drops |")
                lines.append("|---|---|---|---|---|")
                for name, vals in sorted(tool_stats.items()):
                    lines.append(
                        f"| {name} | {vals.get('attempts', 0)} | "
                        f"{vals.get('successes', 0)} | {vals.get('failures', 0)} | {vals.get('drops', 0)} |"
                    )

        per_tag = m.get("per_tag", {})
        if per_tag:
            lines.append("")
            lines.append(
                "| tag | samples | error rate | p95 e2e | p95 cost | p95 citations | keyword match |"
            )
            lines.append("|---|---|---|---|---|---|---|")
            for tag, vals in sorted(per_tag.items()):
                match_rate = vals.get("contains_match_rate")
                match_str = f"{match_rate:.2%}" if match_rate is not None else "n/a"
                lines.append(
                    f"| {tag} | {vals.get('samples', 0)} | "
                    f"{vals.get('error_rate', 0):.2%} | "
                    f"{vals.get('p95_e2e_ms', 0):.0f} | "
                    f"{vals.get('p95_cost_micros', 0):.0f} | "
                    f"{vals.get('p95_citation_count', 0):.1f} | "
                    f"{match_str} |"
                )
        return ReportSection(
            title="Chat regression",
            headline=False,
            body_md="\n".join(lines),
            body_json=m,
        )


register(ChatRegressionBenchmark())

__all__ = ["ChatRegressionBenchmark"]
