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
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

from ....core.arms import ArmRequest, ArmResult, NowingArm
from ....core.clients import NewChatClient
from ....core.config import utc_iso_timestamp
from ....core.notifications import notify_gate_failure
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
    register,
)
from .operational import _classify_error_text, summarize_operational

logger = logging.getLogger(__name__)


COST_CAP_EXCEEDED_MSG = "Run cost {cost} micros exceeds cap {cap}."


_DESCRIPTION = (
    "Chat response regression: per-turn latency, token/cost, citations, "
    "finish status, and optional keyword checks."
)

_DEFAULT_DATASET: list[dict[str, Any]] = [
    {
        "case_id": "chat-mem-001",
        "query": "What are the key facts we have stored about our competitor AlphaCorp?",
        "tags": ["memory", "factual"],
        "tier": "short",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["AlphaCorp"],
    },
    {
        "case_id": "chat-doc-001",
        "query": "Summarize the main clauses of the NDA document.",
        "tags": ["document"],
        "tier": "long_context",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["NDA", "confidential"],
    },
    {
        "case_id": "chat-research-001",
        "query": "What is the state of RAG evaluation in 2025?",
        "tags": ["deep-research"],
        "tier": "multi_tool",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["RAG", "2025"],
    },
    {
        "case_id": "chat-multi-001",
        "query": "Find the latest revenue numbers for Apple and compare them to Samsung.",
        "tags": ["multi-tool", "factual"],
        "tier": "multi_tool",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["Apple", "Samsung"],
    },
    {
        "case_id": "chat-creative-001",
        "query": "Draft a one-paragraph welcome message for a new workspace member.",
        "tags": ["creative"],
        "tier": "short",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["welcome"],
    },
    {
        "case_id": "chat-lead-dispatch-001",
        "query": "Tìm kiếm 5 nhà máy may mặc ở Bình Dương kèm số điện thoại liên hệ.",
        "tags": ["lead-gen", "orchestrator"],
        "tier": "multi_tool",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["Bình Dương"],
    },
    {
        "case_id": "chat-wide-table-001",
        "query": "Khảo sát và lập bảng so sánh 5 dự án căn hộ chung cư nổi bật tại TP Thủ Đức năm 2026.",
        "tags": ["wide-research", "deep-research"],
        "tier": "multi_tool",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["Thủ Đức"],
    },
    {
        "case_id": "chat-speed-latency-001",
        "query": "Nowing là gì và hỗ trợ những định dạng tài liệu nào?",
        "tags": ["speed", "factual"],
        "tier": "short",
        "mentioned_document_ids": [],
        "disabled_tools": [],
        "expected_contains": ["Nowing"],
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
    tier: str = ""
    modes: list[str] | None = None
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
    mode: str = ""
    tier: str = ""
    environment: str = ""
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
    scrape_drops = 0
    error_reason_counts: dict[str, int] = {}
    degradation_reasons: dict[str, int] = {}
    tool_stats: dict[str, dict[str, int]] = {}
    fallback_kb_hits = 0
    n_error_frames = 0
    n_terminal_info = 0
    n_terminal_errors = 0
    engine_unavailable_count = 0
    n_turns = 0
    n_failed_turns = 0
    context_drift_scores: list[float] = []

    for c in cases:
        op = c.operational or {}
        total_attempts += op.get("total_tool_attempts", 0)
        total_successes += op.get("total_tool_successes", 0)
        total_failures += op.get("total_tool_failures", 0)
        total_drops += op.get("total_tool_drops", 0)
        scrape_attempts += op.get("scrape_attempts", 0)
        scrape_successes += op.get("scrape_successes", 0)
        scrape_failures += op.get("scrape_failures", 0)
        scrape_drops += op.get("scrape_drops", 0)
        fallback_kb_hits += op.get("fallback_kb_hits", 0)
        n_error_frames += op.get("n_error_frames", 0)
        n_terminal_info += op.get("n_terminal_info", 0)
        n_terminal_errors += op.get("n_terminal_errors", 0)
        engine_unavailable_count += op.get("engine_unavailable_count", 0)

        nt = op.get("n_turns") or 0
        nfr = op.get("n_failed_turns") or 0
        n_turns += nt
        n_failed_turns += nfr
        cds = op.get("context_drift_score")
        if cds is not None:
            context_drift_scores.append(float(cds))

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
        "n_turns": n_turns,
        "n_failed_turns": n_failed_turns,
        "turn_error_rate": _rate(n_failed_turns, n_turns),
        "context_drift_score": (
            sum(context_drift_scores) / len(context_drift_scores) if context_drift_scores else None
        ),
        "scrape_attempts": scrape_attempts,
        "scrape_successes": scrape_successes,
        "scrape_failures": scrape_failures,
        "scrape_drops": scrape_drops,
        "scrape_success_rate": _rate(scrape_successes, scrape_attempts),
        "scrape_failure_rate": _rate(scrape_failures, scrape_attempts),
        "scrape_drop_rate": _rate(scrape_drops, scrape_attempts),
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


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
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


def _turn_to_dict(turn: _Turn) -> dict[str, Any]:
    return {"query": turn.query, "expected_contains": turn.expected_contains}


def _case_row_to_json(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    turns = payload.get("turns")
    if turns:
        payload["turns"] = [_turn_to_dict(cast(_Turn, t)) for t in turns]
    return payload


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
    modes_value = row.get("modes")
    modes: list[str] | None = None
    if modes_value is not None:
        if isinstance(modes_value, str):
            modes = [m.strip() for m in modes_value.split(",") if m.strip()]
        elif isinstance(modes_value, list) and all(isinstance(v, str) for v in modes_value):
            modes = modes_value  # type: ignore[assignment]
        else:
            raise RuntimeError(
                f"Case {case_id!r} 'modes' must be a string or list of strings, got {modes_value!r}"
            )

    tier = str(row.get("tier") or "")

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
        "tier": tier,
        "modes": modes,
        "turns": turns,
    }


def _load_cases(path: Path) -> list[_Case]:
    cases: list[_Case] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = _validate_case_row(json.loads(line))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Malformed JSONL at {path}:{line_no}: {exc}") from exc
            cases.append(
                _Case(
                    case_id=row["case_id"],
                    query=row["query"],
                    tags=row["tags"],
                    mentioned_document_ids=row["mentioned_document_ids"],
                    disabled_tools=row["disabled_tools"],
                    expected_contains=row["expected_contains"],
                    tier=row["tier"],
                    modes=row["modes"],
                    turns=row["turns"],
                )
            )
    return cases


def _contains_hits(text: str, expected: list[str]) -> int:
    """Count expected terms using whole-word boundaries to avoid substring matches.

    ponytail: this is a stop-gap until the LLM-judge suite (4-8d) replaces
    keyword matching. `\b` works for the ASCII alphanumerics we benchmark with.
    """
    return sum(
        1 for term in expected if re.search(r"\b" + re.escape(term.lower()) + r"\b", text.lower())
    )


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


def _one_case_per_tag(cases: list[_Case]) -> list[_Case]:
    """Pick the first case for every unique tag, preserving original order.

    A case is selected if it introduces at least one tag we have not seen yet;
    once selected, all of its tags are marked as covered."""
    seen: set[str] = set()
    selected: list[_Case] = []
    for c in cases:
        if any(tag not in seen for tag in c.tags):
            selected.append(c)
            for tag in c.tags:
                seen.add(tag)
    return selected


def _build_mode_matrix(
    cases: list[_Case],
    requested_modes: list[str],
    profile: str,
) -> list[tuple[_Case, str]]:
    """Expand cases into the (case, mode) pairs to run."""
    if profile == "quick":
        quick_mode = requested_modes[0]
        selected = _one_case_per_tag(cases)
        return [(c, quick_mode) for c in selected]

    matrix: list[tuple[_Case, str]] = []
    for c in cases:
        case_modes = c.modes if c.modes is not None else requested_modes
        for m in case_modes:
            matrix.append((c, m))
    return matrix


def _per_turn_metrics(
    turn_snapshots: list[dict[str, Any]],
    turns: list[_Turn],
) -> dict[str, Any]:
    """Per-turn stability metrics for multi-turn cases."""
    n_turns = len(turn_snapshots)
    n_failed_turns = sum(1 for t in turn_snapshots if t.get("error"))
    return {
        "turns": turn_snapshots,
        "n_turns": n_turns,
        "n_failed_turns": n_failed_turns,
        "turn_error_rate": n_failed_turns / n_turns if n_turns else None,
        "context_drift_score": _context_drift(turn_snapshots),
    }


@lru_cache(maxsize=1)
def _load_chat_gate() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load (top-level, thresholds) from this benchmark's gate.yaml."""
    gate_path = Path(__file__).parent / "gate.yaml"
    if not gate_path.is_file():
        return {}, {}
    data = yaml.safe_load(gate_path.read_text(encoding="utf-8")) or {}
    return data, data.get("thresholds") or {}


def _evaluate_chat_gate(metrics: dict[str, Any]) -> list[str]:
    """Return a list of threshold violations for the current metrics."""
    top, thresholds = _load_chat_gate()
    if not thresholds:
        return []

    violations: list[str] = []

    def _check(
        name: str, value: float | None, max_val: float | None = None, min_val: float | None = None
    ) -> None:
        if value is None:
            return
        if max_val is not None and value > max_val:
            violations.append(f"{name} {value:.3f} exceeds max {max_val:.3f}")
        if min_val is not None and value < min_val:
            violations.append(f"{name} {value:.3f} is below min {min_val:.3f}")

    overall = metrics.get("overall", {})
    _check("overall error rate", overall.get("error_rate"), thresholds.get("max_error_rate"))
    _check("overall p95 e2e (ms)", overall.get("p95_e2e_ms"), thresholds.get("max_p95_e2e_ms"))
    _check("overall p95 ttfb (ms)", overall.get("p95_ttfb_ms"), thresholds.get("max_p95_ttfb_ms"))
    _check(
        "overall p95 cost (micros)",
        overall.get("p95_cost_micros"),
        thresholds.get("max_p95_cost_micros"),
    )
    _check(
        "overall contains match rate",
        overall.get("contains_match_rate"),
        min_val=thresholds.get("min_contains_match_rate"),
    )

    per_mode_thresholds = thresholds.get("per_mode", {})
    for mode, vals in metrics.get("per_mode", {}).items():
        t = per_mode_thresholds.get(mode, {})
        _check(f"mode {mode} p95 e2e (ms)", vals.get("p95_e2e_ms"), t.get("max_p95_e2e_ms"))
        _check(
            f"mode {mode} p95 cost (micros)",
            vals.get("p95_cost_micros"),
            t.get("max_p95_cost_micros"),
        )

    per_tier_thresholds = thresholds.get("per_tier", {})
    for tier, vals in metrics.get("per_tier", {}).items():
        t = per_tier_thresholds.get(tier, {})
        _check(f"tier {tier} p95 e2e (ms)", vals.get("p95_e2e_ms"), t.get("max_p95_e2e_ms"))

    # Story 4.8f operational / stability thresholds.
    operational = metrics.get("operational", {})
    _check(
        "scrape drop rate",
        operational.get("scrape_drop_rate"),
        thresholds.get("max_scrape_drop_rate"),
    )
    _check(
        "rate limited rate",
        operational.get("rate_limited_rate"),
        thresholds.get("max_rate_limited_rate"),
    )
    _check(
        "tool drop rate", operational.get("tool_drop_rate"), thresholds.get("max_tool_drop_rate")
    )
    _check(
        "turn error rate", operational.get("turn_error_rate"), thresholds.get("max_turn_error_rate")
    )
    _check(
        "engine unavailable rate",
        operational.get("engine_unavailable_rate"),
        thresholds.get("max_engine_unavailable_rate"),
    )

    return violations


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
            "--modes",
            default="balanced",
            help="Comma-separated chat modes to benchmark (e.g. speed,balanced,quality,auto).",
        )
        parser.add_argument(
            "--tier",
            default=None,
            help="Comma-separated tier filter (e.g. short,long_context,multi_tool).",
        )
        parser.add_argument(
            "--environment",
            default="local",
            help="Environment label for local vs production parity (local or production).",
        )
        parser.add_argument(
            "--profile",
            default="full",
            choices=["quick", "full"],
            help="quick: one case per tag, one mode, concurrency 1. full: full mode × tier matrix.",
        )
        parser.add_argument(
            "--tags",
            default=None,
            help="Comma-separated tag filter (e.g. memory,document).",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=600.0,
            help="Per-turn timeout in seconds.",
        )
        # ponytail: deep-research (tier multi_tool) can exceed the old 300s default
        # when ChainLens runs synchronously in benchmark / local mode. 600s is the
        # longest practical single-turn ceiling before we should switch to State A.
        parser.add_argument(
            "--backend-build-id",
            type=str,
            default=None,
            help="Deployed backend build/commit identifier this run evaluates.",
        )
        parser.add_argument(
            "--max-total-cost-micros",
            type=int,
            default=None,
            help="Abort if the total run cost exceeds this cap.",
        )
        parser.add_argument(
            "--fail-on-unratified",
            action="store_true",
            help="Fail the run if gate.yaml baseline_ratified is false.",
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
                for line_no, line in enumerate(text.splitlines(), start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = _validate_case_row(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            f"Malformed JSONL at {dataset_path}:{line_no}: {exc}"
                        ) from exc
                    fh.write(json.dumps(_case_row_to_json(row), ensure_ascii=False) + "\n")
            logger.info("Installed %d cases from %s", len(_load_cases(target)), dataset_path)
            return

        # No dataset provided: write the default sample dataset.
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as fh:
            for row in _DEFAULT_DATASET:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("Wrote default %d sample cases to %s", len(_DEFAULT_DATASET), target)

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        # Precedence: explicit CLI flag > suite state > env default.
        # Use ``is None`` so ``0`` is honored as an explicit value (e.g. --n 0).
        # ``ctx.search_space_id`` defaults to 0 when the suite has not been set
        # up, so treat 0 the same as None for the suite-state fallback.
        search_space_id = opts.get("search_space_id")
        if search_space_id is None:
            search_space_id = ctx.search_space_id or None
        if search_space_id is None:
            search_space_id = ctx.config.chat_eval_search_space_id
        if not search_space_id:
            raise RuntimeError("--search-space-id or a suite setup with a SearchSpace is required.")
        workspace_id = opts.get("workspace_id")
        if workspace_id is None:
            workspace_id = ctx.config.chat_eval_workspace_id
        sample_n = opts.get("sample_n")
        if sample_n is None:
            sample_n = ctx.config.chat_eval_max_cases
        concurrency = max(1, int(opts.get("concurrency") or 1))
        threads = max(1, int(opts.get("threads") or 1))
        tags_filter = opts.get("tags")
        tier_filter = opts.get("tier")
        environment = str(opts.get("environment") or "local")
        profile = str(opts.get("profile") or "full")
        valid_modes = {"speed", "balanced", "quality", "auto"}
        requested_modes = [
            m.strip() for m in (opts.get("modes") or "balanced").split(",") if m.strip()
        ]
        if not requested_modes:
            raise RuntimeError("--modes must contain at least one mode.")
        bad_modes = [m for m in requested_modes if m not in valid_modes]
        if bad_modes:
            raise RuntimeError(
                f"Invalid --modes: {bad_modes}. Allowed values are: {', '.join(sorted(valid_modes))}."
            )
        if sample_n is not None and sample_n < 1:
            raise RuntimeError("--n must be >= 1.")
        timeout_raw = opts.get("timeout")
        if timeout_raw is None:
            timeout_s = 600.0
        else:
            timeout_s = float(timeout_raw)
            if timeout_s <= 0:
                raise RuntimeError("--timeout must be > 0.")
        build_id = opts.get("backend_build_id")
        max_total_cost_micros = opts.get("max_total_cost_micros")
        if max_total_cost_micros is not None and max_total_cost_micros < 0:
            raise RuntimeError("--max-total-cost-micros must be >= 0.")
        fail_on_unratified = bool(opts.get("fail_on_unratified"))

        if profile == "quick":
            concurrency = 1
            threads = 1

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
            if wanted:
                cases = [c for c in cases if wanted.intersection(c.tags)]
        if tier_filter:
            wanted_tiers = {t.strip() for t in tier_filter.split(",") if t.strip()}
            if wanted_tiers:
                cases = [c for c in cases if c.tier in wanted_tiers]
        if sample_n is not None:
            cases = cases[:sample_n]

        matrix = _build_mode_matrix(cases, requested_modes, profile)

        # Stress mode: run the same case in multiple parallel chat threads.
        if threads > 1 and profile == "full":
            matrix = [
                (replace(c, case_id=f"{c.case_id}:t{i}"), m)
                for c, m in matrix
                for i in range(threads)
            ]

        if not matrix:
            raise RuntimeError("No chat cases selected for the requested filters.")

        client = NewChatClient(ctx.http, ctx.config.nowing_api_base)
        arm = NowingArm(
            client=client,
            search_space_id=search_space_id,
            workspace_id=workspace_id if workspace_id is not None else search_space_id,
        )

        sem = asyncio.Semaphore(concurrency)

        async def _run_one(case: _Case, mode: str) -> _CaseResult:
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

                def _build_operational(
                    last_text: str,
                    error_text: str | None = None,
                    error_code: str | None = None,
                ) -> tuple[dict[str, Any], list[dict], list]:
                    raw_events = [ev for r in turn_results for ev in r.extra.get("raw_events", [])]
                    # Client-side errors (timeout, HTTP) do not emit an SSE error
                    # frame, so synthesize one if needed (M10).
                    has_sse_error = any(ev.get("type") == "error" for ev in raw_events)
                    if error_text and not has_sse_error:
                        raw_events.append(
                            {
                                "type": "error",
                                "errorText": error_text,
                                "errorCode": error_code,
                            }
                        )
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
                    operational, raw_events, call_details = _build_operational(
                        last_text, error_text, error_code
                    )
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
                        mode=mode,
                        tier=case.tier,
                        environment=environment,
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
                        options["mode"] = mode
                        if workspace_id is not None:
                            options["workspace_id"] = workspace_id
                        # The runner manages thread lifecycle for multi-turn reuse (H3).
                        options["delete_thread"] = False
                        request = ArmRequest(
                            question_id=f"{case.case_id}:{mode}:turn{i}",
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
                            error_code = result.extra.get("error_code")
                            if not error_code:
                                error_code = _classify_error_text(result.error, None) or "other"
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
                                    "error_code": error_code,
                                }
                            )
                            thread_id = result.extra.get("thread_id")
                            return _make_error_result(
                                result.error,
                                error_code=error_code,
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
                    if thread_id is not None:
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
                    mode=mode,
                    tier=case.tier,
                    environment=environment,
                    raw_events=raw_events,
                    call_details=call_details or None,
                    operational=operational,
                )

        # Track running cost so we can abort early as soon as the cap is
        # exceeded instead of burning the full matrix.
        accumulated_cost_micros = 0
        cost_cap_exceeded = False
        cost_cap_cancelled = asyncio.Event()

        async def _run_one_guarded(case: _Case, mode: str) -> _CaseResult:
            nonlocal accumulated_cost_micros, cost_cap_exceeded
            if cost_cap_cancelled.is_set():
                return _CaseResult(
                    case_id=case.case_id,
                    tags=case.tags,
                    query=case.query,
                    text="",
                    error="Cost cap cancelled",
                    error_code="CostCapCancelled",
                    latency_ms=0,
                    ttfb_ms=None,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    cost_micros=0,
                    citation_count=0,
                    finished_normally=False,
                    expected_contains=case.expected_contains,
                    contains_hits=0,
                    mode=mode,
                    tier=case.tier,
                    environment=environment,
                )
            result = await _run_one(case, mode)
            if max_total_cost_micros is not None:
                accumulated_cost_micros += result.cost_micros
                if not cost_cap_exceeded and accumulated_cost_micros > max_total_cost_micros:
                    cost_cap_exceeded = True
                    cost_cap_cancelled.set()
                    logger.warning(
                        "Cost cap of %d micros exceeded at %d micros; cancelling remaining cases.",
                        max_total_cost_micros,
                        accumulated_cost_micros,
                    )
            return result

        raw_results = await asyncio.gather(
            *(_run_one_guarded(c, m) for c, m in matrix),
            return_exceptions=True,
        )
        results: list[_CaseResult] = []
        for r in raw_results:
            if isinstance(r, Exception):
                logger.exception("Unexpected failure in chat regression task: %s", r)
                results.append(
                    _CaseResult(
                        case_id="unknown",
                        tags=[],
                        query="",
                        text="",
                        error=f"{type(r).__name__}: {r}",
                        latency_ms=0,
                        ttfb_ms=None,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost_micros=0,
                        citation_count=0,
                        finished_normally=False,
                        expected_contains=[],
                        contains_hits=0,
                    )
                )
            else:
                results.append(r)

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
                            "mode": r.mode,
                            "tier": r.tier,
                            "environment": r.environment,
                            "error_code": r.error_code,
                            "raw_events": r.raw_events,
                            "call_details": r.call_details,
                            "n_raw_events": len(r.raw_events) if r.raw_events else 0,
                            "operational": r.operational,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )

        total_cost_micros = sum(r.cost_micros for r in results)
        if not cost_cap_exceeded:
            cost_cap_exceeded = (
                max_total_cost_micros is not None and total_cost_micros > max_total_cost_micros
            )

        metrics = self._aggregate(results, concurrency=concurrency, threads=threads)

        gate_violations = _evaluate_chat_gate(metrics)
        top, _ = _load_chat_gate()
        extra = {
            "search_space_id": search_space_id,
            "workspace_id": workspace_id,
            "n_cases": len(cases),
            "n_matrix_rows": len(matrix),
            "concurrency": concurrency,
            "threads": threads,
            "modes": requested_modes,
            "tier_filter": tier_filter,
            "environment": environment,
            "profile": profile,
            "timeout_s": timeout_s,
            "tags_filter": tags_filter,
            "build_id": build_id,
            "dataset_path": str(dataset_path),
        }

        run_artifact_path = run_dir / "run_artifact.json"
        if cost_cap_exceeded:
            cap_str = str(max_total_cost_micros) if max_total_cost_micros is not None else "unknown"
            cost_cap_reason = COST_CAP_EXCEEDED_MSG.format(cost=total_cost_micros, cap=cap_str)
        else:
            cost_cap_reason = None
        unratified_reason = None
        if fail_on_unratified and not top.get("baseline_ratified"):
            unratified_reason = "Chat regression gate is not ratified (baseline_ratified=false)."
        stored_violations: list[str] = list(gate_violations)
        if cost_cap_reason:
            stored_violations.append(cost_cap_reason)
        if unratified_reason:
            stored_violations.append(unratified_reason)
        if stored_violations:
            metrics["gate_violations"] = stored_violations

        run_artifact_str = str(run_artifact_path)
        notifications_sent = False

        # Notify on any failure condition, then write the artifact and raise.
        # The artifact is written in a ``finally`` block so the post-mortem
        # data (including the final ``notifications_sent`` flag) is always
        # available, even when the gate fails.
        failing_reasons: list[str] = list(gate_violations)
        if cost_cap_reason:
            failing_reasons.append(cost_cap_reason)
        if unratified_reason:
            failing_reasons.append(unratified_reason)

        # Avoid false-positive alerts on dry-runs: only notify when the gate
        # will actually fail (baseline ratified + threshold violations, cost
        # cap breach, or explicit --fail-on-unratified).
        notify_reasons: list[str] = []
        if cost_cap_reason:
            notify_reasons.append(cost_cap_reason)
        if gate_violations and top.get("baseline_ratified"):
            notify_reasons.extend(gate_violations)
        if unratified_reason:
            notify_reasons.append(unratified_reason)

        try:
            if notify_reasons:
                try:
                    notifications_sent = await notify_gate_failure(
                        self.suite,
                        self.name,
                        run_timestamp,
                        notify_reasons,
                        run_artifact_str,
                        extra,
                        slack_url=ctx.config.slack_webhook_url,
                        telegram_bot_token=ctx.config.telegram_bot_token,
                        telegram_chat_id=ctx.config.telegram_chat_id,
                        prefix=ctx.config.artifact_url_prefix,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to send gate failure notification: %s", exc)

            if cost_cap_exceeded:
                raise RuntimeError(cost_cap_reason)

            if gate_violations:
                if top.get("baseline_ratified"):
                    raise RuntimeError(
                        f"Chat regression gate failed for {environment}: "
                        + "; ".join(gate_violations)
                    )
                logger.warning(
                    "Chat regression gate violations detected but baseline is not ratified "
                    "(baseline_ratified=false): %s",
                    "; ".join(gate_violations),
                )

            if fail_on_unratified and not top.get("baseline_ratified"):
                raise RuntimeError(
                    "Chat regression gate is not ratified (baseline_ratified=false). "
                    "Run with measured baseline and flip gate.yaml, or omit --fail-on-unratified."
                )
        finally:
            _write_json_atomic(
                run_artifact_path,
                {
                    "suite": self.suite,
                    "benchmark": self.name,
                    "raw_path": "raw.jsonl",
                    "metrics": metrics,
                    "extra": extra,
                    "notifications_sent": notifications_sent,
                },
            )

        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra=extra,
            notifications_sent=notifications_sent,
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

        def _group_results(
            results: list[_CaseResult],
        ) -> dict[str, dict[str, list[_CaseResult]]]:
            per_tag: dict[str, list[_CaseResult]] = {}
            per_mode: dict[str, list[_CaseResult]] = {}
            per_tier: dict[str, list[_CaseResult]] = {}
            per_mode_tier: dict[str, list[_CaseResult]] = {}
            for r in results:
                for tag in r.tags:
                    per_tag.setdefault(tag, []).append(r)
                per_mode.setdefault(r.mode, []).append(r)
                if r.tier:
                    per_tier.setdefault(r.tier, []).append(r)
                    per_mode_tier.setdefault(f"{r.mode}:{r.tier}", []).append(r)
            return {
                "per_tag": per_tag,
                "per_mode": per_mode,
                "per_tier": per_tier,
                "per_mode_tier": per_mode_tier,
            }

        groups = _group_results(results)
        per_tag_buckets = {tag: _bucket(items) for tag, items in groups["per_tag"].items()}
        per_mode_buckets = {mode: _bucket(items) for mode, items in groups["per_mode"].items()}
        per_tier_buckets = {tier: _bucket(items) for tier, items in groups["per_tier"].items()}
        per_mode_tier_buckets = {
            key: _bucket(items) for key, items in groups["per_mode_tier"].items()
        }

        operational = _aggregate_operational(
            results,
            overall=overall,
            concurrency=concurrency,
            threads=threads,
        )

        def _op_for(items: list[_CaseResult], bucket: dict[str, Any]) -> dict[str, Any]:
            return _aggregate_operational(
                items,
                overall=bucket,
                concurrency=concurrency,
                threads=threads,
            )

        return {
            "overall": overall,
            "operational": operational,
            "per_tag": per_tag_buckets,
            "per_tag_operational": {
                tag: _op_for(items, per_tag_buckets[tag])
                for tag, items in groups["per_tag"].items()
            },
            "per_mode": per_mode_buckets,
            "per_mode_operational": {
                mode: _op_for(items, per_mode_buckets[mode])
                for mode, items in groups["per_mode"].items()
            },
            "per_tier": per_tier_buckets,
            "per_tier_operational": {
                tier: _op_for(items, per_tier_buckets[tier])
                for tier, items in groups["per_tier"].items()
            },
            "per_mode_tier": per_mode_tier_buckets,
            "per_mode_tier_operational": {
                key: _op_for(items, per_mode_tier_buckets[key])
                for key, items in groups["per_mode_tier"].items()
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
            f"- p95 TTFB: {overall.get('p95_ttfb_ms') if overall.get('p95_ttfb_ms') is not None else 'n/a'} ms",
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

        def _bucket_row(vals: dict[str, Any]) -> str:
            match_rate = vals.get("contains_match_rate")
            match_str = f"{match_rate:.2%}" if match_rate is not None else "n/a"
            p50_e2e = vals.get("p50_e2e_ms")
            p50_e2e_str = f"{p50_e2e:.0f}" if p50_e2e is not None else "n/a"
            p95_e2e = vals.get("p95_e2e_ms")
            p95_e2e_str = f"{p95_e2e:.0f}" if p95_e2e is not None else "n/a"
            p50_ttfb = vals.get("p50_ttfb_ms")
            p50_ttfb_str = f"{p50_ttfb:.0f}" if p50_ttfb is not None else "n/a"
            p95_ttfb = vals.get("p95_ttfb_ms")
            p95_ttfb_str = f"{p95_ttfb:.0f}" if p95_ttfb is not None else "n/a"
            return (
                f"{vals.get('samples', 0)} | "
                f"{vals.get('error_rate', 0):.2%} | "
                f"{p50_e2e_str} | "
                f"{p95_e2e_str} | "
                f"{p50_ttfb_str} | "
                f"{p95_ttfb_str} | "
                f"{vals.get('p95_cost_micros', 0):.0f} | "
                f"{vals.get('p95_citation_count', 0):.1f} | "
                f"{match_str}"
            )

        def _op_row(vals: dict[str, Any]) -> str:
            scrape_attempts = vals.get("scrape_attempts", 0)
            scrape_successes = vals.get("scrape_successes", 0)
            scrape_success_rate = vals.get("scrape_success_rate")
            scrape_sr_str = (
                f"{scrape_success_rate:.2%}" if scrape_success_rate is not None else "n/a"
            )
            tool_drop_rate = vals.get("tool_drop_rate")
            tool_drop_str = f"{tool_drop_rate:.2%}" if tool_drop_rate is not None else "n/a"
            engine_unavailable_rate = vals.get("engine_unavailable_rate")
            eu_str = (
                f"{engine_unavailable_rate:.2%}" if engine_unavailable_rate is not None else "n/a"
            )
            reasons = vals.get("error_reason_counts", {})
            reasons_str = (
                ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items())) if reasons else "n/a"
            )
            return (
                f"{vals.get('samples', 0)} | "
                f"{scrape_successes}/{scrape_attempts} ({scrape_sr_str}) | "
                f"{tool_drop_str} | "
                f"{eu_str} | "
                f"{reasons_str}"
            )

        per_tag = m.get("per_tag", {})
        if per_tag:
            lines.append("")
            lines.append(
                "| tag | samples | error rate | p50 e2e | p95 e2e | p50 TTFB | p95 TTFB | p95 cost | p95 citations | keyword match |"
            )
            lines.append("|---|---|---|---|---|---|---|---|---|---|")
            for tag, vals in sorted(per_tag.items()):
                lines.append(f"| {tag} | {_bucket_row(vals)} |")

        per_tag_operational = m.get("per_tag_operational", {})
        if per_tag_operational:
            lines.append("")
            lines.append("### Operational / Stability per tag")
            lines.append(
                "| tag | samples | scrape success | tool drop rate | engine unavailable | failure reasons |"
            )
            lines.append("|---|---|---|---|---|---|")
            for tag, vals in sorted(per_tag_operational.items()):
                lines.append(f"| {tag} | {_op_row(vals)} |")

        per_mode = m.get("per_mode", {})
        if per_mode:
            lines.append("")
            lines.append("### Per mode")
            lines.append(
                "| mode | samples | error rate | p50 e2e | p95 e2e | p50 TTFB | p95 TTFB | p95 cost | p95 citations | keyword match |"
            )
            lines.append("|---|---|---|---|---|---|---|---|---|---|")
            for mode, vals in sorted(per_mode.items()):
                lines.append(f"| {mode} | {_bucket_row(vals)} |")

        per_tier = m.get("per_tier", {})
        if per_tier:
            lines.append("")
            lines.append("### Per tier")
            lines.append(
                "| tier | samples | error rate | p50 e2e | p95 e2e | p50 TTFB | p95 TTFB | p95 cost | p95 citations | keyword match |"
            )
            lines.append("|---|---|---|---|---|---|---|---|---|---|")
            for tier, vals in sorted(per_tier.items()):
                lines.append(f"| {tier} | {_bucket_row(vals)} |")

        per_mode_tier = m.get("per_mode_tier", {})
        if per_mode_tier:
            lines.append("")
            lines.append("### Per mode × tier")
            lines.append(
                "| mode:tier | samples | error rate | p50 e2e | p95 e2e | p50 TTFB | p95 TTFB | p95 cost | p95 citations | keyword match |"
            )
            lines.append("|---|---|---|---|---|---|---|---|---|---|")
            for key, vals in sorted(per_mode_tier.items()):
                lines.append(f"| {key} | {_bucket_row(vals)} |")

        # Local vs production parity delta when both environments are present.
        by_env: dict[str, RunArtifact] = {}
        for a in artifacts:
            env = a.extra.get("environment") or "local"
            if env not in by_env or a.run_timestamp > by_env[env].run_timestamp:
                by_env[env] = a
        if "local" in by_env and "production" in by_env:
            local_m = by_env["local"].metrics
            prod_m = by_env["production"].metrics
            local_overall = local_m.get("overall", {})
            prod_overall = prod_m.get("overall", {})

            def _delta(prod: float | None, local: float | None) -> str:
                if prod is None or local is None or local == 0:
                    return "n/a"
                return f"{(prod - local) / local:+.1%}"

            lines.append("")
            lines.append("### Local vs production parity")
            lines.append("| metric | local | production | delta |")
            lines.append("|---|---|---|---|")
            lines.append(
                f"| p95 e2e | {local_overall.get('p95_e2e_ms', 0):.0f} | "
                f"{prod_overall.get('p95_e2e_ms', 0):.0f} | "
                f"{_delta(prod_overall.get('p95_e2e_ms'), local_overall.get('p95_e2e_ms'))} |"
            )
            lines.append(
                f"| p95 cost | {local_overall.get('p95_cost_micros', 0):.0f} | "
                f"{prod_overall.get('p95_cost_micros', 0):.0f} | "
                f"{_delta(prod_overall.get('p95_cost_micros'), local_overall.get('p95_cost_micros'))} |"
            )
            lines.append(
                f"| p95 citations | {local_overall.get('p95_citation_count', 0):.1f} | "
                f"{prod_overall.get('p95_citation_count', 0):.1f} | "
                f"{_delta(prod_overall.get('p95_citation_count'), local_overall.get('p95_citation_count'))} |"
            )

            for mode in sorted(
                set(local_m.get("per_mode", {}).keys()) | set(prod_m.get("per_mode", {}).keys())
            ):
                l_mode = local_m.get("per_mode", {}).get(mode, {})
                p_mode = prod_m.get("per_mode", {}).get(mode, {})
                lines.append("")
                lines.append(f"**Mode `{mode}` local vs production**")
                lines.append("| metric | local | production | delta |")
                lines.append("|---|---|---|---|")
                for metric in ["p95_e2e_ms", "p95_cost_micros", "p95_citation_count"]:
                    lines.append(
                        f"| {metric} | {l_mode.get(metric, 0):.0f} | "
                        f"{p_mode.get(metric, 0):.0f} | "
                        f"{_delta(p_mode.get(metric), l_mode.get(metric))} |"
                    )

        return ReportSection(
            title="Chat regression",
            headline=False,
            body_md="\n".join(lines),
            body_json=m,
        )


register(ChatRegressionBenchmark())

__all__ = ["ChatRegressionBenchmark"]
