"""ChainLens research latency + quality gate (Story 9.3).

Runs a small set of research queries in each requested mode, records e2e and
TTFB latency, and computes p50/p95 per mode. If a labeled reference file is
provided with ``--references``, the runner also computes token-overlap
``answer_recall`` and ``f1`` per mode so the quality of ``balanced`` can be
compared to ``quality`` before enabling State B (sync chat mode).

ponytail: Token overlap is a cheap, dependency-free quality proxy; replace
with a real evaluator (e.g. LLM-as-judge or ROUGE) once a labeled dataset
exists.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import yaml

from ....core.config import utc_iso_timestamp
from ....core.notifications import notify_gate_failure
from ....core.parse import iter_sse_events
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
    register,
)

logger = logging.getLogger(__name__)


_DESCRIPTION = (
    "ChainLens research latency by mode: p50/p95 e2e and TTFB. "
    "Quality gate for NFR-9 / State A->B transition."
)

_DEFAULT_QUERIES = [
    "What are the main causes of the 2008 financial crisis?",
    "How does photosynthesis convert light energy into chemical energy?",
    "Summarize the current consensus on climate change mitigation strategies.",
    "Explain the difference between tokamak and stellarator fusion reactor designs.",
    "What is the state of the art in retrieval-augmented generation as of 2025?",
]

_ALLOWED_MODES = frozenset({"speed", "balanced", "quality", "auto"})

# ChainLens may report resolved modes that map to Nowing schema names.
_RESOLVED_MODE_ALIASES = {
    "deep": "quality",
    "deep-reasoning": "quality",
}

_TERMINAL_RUN_STATUSES = {"success", "error", "cancelled", "completed", "failed", "timeout"}


@dataclass
class _ModeStats:
    e2e: list[float] = None  # type: ignore[assignment]
    ttfb: list[float] = None  # type: ignore[assignment]
    recall: list[float] = None  # type: ignore[assignment]
    f1: list[float] = None  # type: ignore[assignment]
    cost: list[float] = None  # type: ignore[assignment]
    n_total: int = 0
    n_failed: int = 0
    n_partial: int = 0
    n_engine_unavailable: int = 0
    n_degraded: int = 0
    fallback_hit_count: int = 0
    degradation_reasons: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.e2e = []
        self.ttfb = []
        self.recall = []
        self.f1 = []
        self.cost = []
        self.degradation_reasons = {}


@lru_cache(maxsize=1)
def _load_chainlens_gate() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load (top-level, thresholds) from this benchmark's gate.yaml."""
    gate_path = Path(__file__).parent / "gate.yaml"
    if not gate_path.is_file():
        return {}, {}
    data = yaml.safe_load(gate_path.read_text(encoding="utf-8")) or {}
    return data, data.get("thresholds") or {}


def _evaluate_chainlens_gate(metrics: dict[str, Any]) -> list[str]:
    """Return a list of threshold violations for the current metrics."""
    top, thresholds = _load_chainlens_gate()
    if not thresholds:
        return []

    violations: list[str] = []

    def _check(
        name: str,
        value: float | None,
        max_val: float | None = None,
        min_val: float | None = None,
    ) -> None:
        if value is None:
            return
        if max_val is not None and value > max_val:
            violations.append(f"{name} {value:.3f} exceeds max {max_val:.3f}")
        if min_val is not None and value < min_val:
            violations.append(f"{name} {value:.3f} is below min {min_val:.3f}")

    def _check_bucket(
        bucket: dict[str, Any],
        t: dict[str, Any],
        name: str,
    ) -> None:
        if bucket.get("n_total", 0) == 0:
            return
        _check(f"{name} p95 e2e (ms)", bucket.get("p95_e2e_ms"), t.get("max_p95_e2e_ms"))
        _check(f"{name} p95 TTFB (ms)", bucket.get("p95_ttfb_ms"), t.get("max_p95_ttfb_ms"))
        _check(
            f"{name} mean cost (micros)",
            bucket.get("mean_cost_micros"),
            t.get("max_mean_cost_micros"),
        )
        _check(f"{name} error rate", bucket.get("error_rate"), t.get("max_error_rate"))
        _check(
            f"{name} degraded rate",
            bucket.get("degraded_rate"),
            thresholds.get("max_degraded_rate"),
        )
        _check(
            f"{name} engine unavailable rate",
            bucket.get("engine_unavailable_rate"),
            thresholds.get("max_engine_unavailable_rate"),
        )

    overall = metrics.get("overall", {})
    _check_bucket(overall, thresholds, "overall")

    per_mode = metrics.get("per_mode") or metrics.get("modes") or {}
    per_mode_thresholds = thresholds.get("per_mode", {})
    for mode, vals in per_mode.items():
        _check_bucket(vals, per_mode_thresholds.get(mode, {}), f"mode {mode}")

    per_tier = metrics.get("per_tier", {})
    per_tier_thresholds = thresholds.get("per_tier", {})
    for tier, vals in per_tier.items():
        _check_bucket(vals, per_tier_thresholds.get(tier, {}), f"tier {tier or '(default)'}")

    per_mode_tier = metrics.get("per_mode_tier", {})
    per_mode_tier_thresholds = thresholds.get("per_mode_tier", {})
    for key, vals in per_mode_tier.items():
        _check_bucket(vals, per_mode_tier_thresholds.get(key, {}), f"mode:tier {key}")

    return violations


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


def _rate(num: int, denom: int) -> float | None:
    return num / denom if denom else None


def _resolve_bucket_mode(row: dict[str, Any], requested_modes: list[str]) -> str:
    """Map a result row to a metric bucket mode.

    Respects ``resolved_mode`` when it matches a requested mode or a known
    alias (e.g. ChainLens ``deep`` -> Nowing ``quality``). Unknown resolved
    modes fall back to the requested mode so the gate does not accrue an
    unexpected empty bucket.
    """
    requested = row.get("mode") or "balanced"
    resolved = row.get("resolved_mode")
    if not resolved:
        return requested
    if resolved in _RESOLVED_MODE_ALIASES:
        alias = _RESOLVED_MODE_ALIASES[resolved]
        if alias in requested_modes:
            return alias
    if resolved in requested_modes:
        return resolved
    if resolved in _ALLOWED_MODES:
        return resolved
    logger.warning(
        "Resolved mode %r is not in allowed set; using requested %r for query %r",
        resolved,
        requested,
        row.get("query"),
    )
    return requested


def _add_row_to_stats(stats: _ModeStats, row: dict[str, Any]) -> None:
    stats.n_total += 1
    if row.get("error"):
        stats.n_failed += 1
    if row.get("duration_ms") is not None:
        stats.e2e.append(float(row["duration_ms"]))
    if row.get("first_token_time_ms") is not None:
        stats.ttfb.append(float(row["first_token_time_ms"]))
    if not row.get("error") and row.get("cost_micros") is not None:
        # Errors have no meaningful cost; do not pull the mean down.
        stats.cost.append(float(row["cost_micros"]))
    if row.get("status") == "partial":
        stats.n_partial += 1
    if row.get("status") == "engine_unavailable":
        stats.n_engine_unavailable += 1
    if row.get("degraded"):
        stats.n_degraded += 1
    if row.get("degradation_reason"):
        reason = row["degradation_reason"]
        stats.degradation_reasons[reason] = stats.degradation_reasons.get(reason, 0) + 1
    stats.fallback_hit_count += row.get("fallback_hit_count") or 0


def _bucket_stats(stats: _ModeStats) -> dict[str, Any]:
    n = stats.n_total
    return {
        "p50_e2e_ms": _percentile(stats.e2e, 0.5),
        "p95_e2e_ms": _percentile(stats.e2e, 0.95),
        "p50_ttfb_ms": _percentile(stats.ttfb, 0.5),
        "p95_ttfb_ms": _percentile(stats.ttfb, 0.95),
        "samples_e2e": len(stats.e2e),
        "samples_ttfb": len(stats.ttfb),
        "mean_answer_recall": sum(stats.recall) / len(stats.recall) if stats.recall else None,
        "mean_f1": sum(stats.f1) / len(stats.f1) if stats.f1 else None,
        "samples_quality": len(stats.recall),
        "n_total": n,
        "n_failed": stats.n_failed,
        "error_rate": _rate(stats.n_failed, n),
        "sources_partial_rate": _rate(stats.n_partial, n),
        "engine_unavailable_rate": _rate(stats.n_engine_unavailable, n),
        "degraded_rate": _rate(stats.n_degraded, n),
        "degradation_reason_counts": dict(stats.degradation_reasons),
        "fallback_kb_hits": stats.fallback_hit_count,
        "mean_cost_micros": sum(stats.cost) / len(stats.cost) if stats.cost else None,
        "total_cost_micros": sum(stats.cost),
    }


class ChainlensLatencyBenchmark:
    suite: str = "research"
    name: str = "chainlens_latency"
    headline: bool = False
    description: str = _DESCRIPTION
    #: The benchmark hits a workspace-scoped research endpoint; it does not need
    #: a SearchSpace or a pinned chat model, so it must not require `setup`.
    requires_suite_setup: bool = False
    #: Ingest is a no-op; do not require auth for it.
    requires_auth_for_ingest: bool = False

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--modes",
            default="speed,balanced,quality",
            help="Comma-separated research modes to compare (Nowing schema: speed, balanced, quality, auto; use quality for ChainLens deep/deep-reasoning).",
        )
        parser.add_argument(
            "--workspace-id",
            type=int,
            default=None,
            help="Workspace tenant for the research endpoint; overrides NOWING_EVAL_WORKSPACE_ID.",
        )
        parser.add_argument(
            "--n",
            dest="sample_n",
            type=int,
            default=None,
            help="Cap the number of queries (default: all).",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=1,
            help="Number of parallel research calls.",
        )
        parser.add_argument(
            "--tier",
            default="",
            help="Tier label for the query set (e.g. short, long_context, multi_tool).",
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
            help="quick: first mode + first query. full: full mode x query matrix.",
        )
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=2.0,
            help="Seconds between run polls.",
        )
        parser.add_argument(
            "--poll-timeout",
            type=float,
            default=300.0,
            help="Max seconds to wait for an async run.",
        )
        parser.add_argument(
            "--sync-timeout",
            type=float,
            default=600.0,
            help="Max seconds to wait for a synchronous research call.",
        )
        parser.add_argument(
            "--references",
            type=Path,
            default=None,
            help="Optional JSONL/JSON file with {'query': ..., 'reference': ...} records for quality scoring.",
        )
        parser.add_argument(
            "--quality-latency-budget-ms",
            type=float,
            default=60_000.0,
            help="Max p95 e2e latency (ms) the quality mode may add before it is rejected.",
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
        # No ingest required; this is a live latency gate against the engine.
        return

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        requested_modes = [
            m.strip() for m in (opts.get("modes") or "balanced").split(",") if m.strip()
        ]
        unknown = [m for m in requested_modes if m not in _ALLOWED_MODES]
        if unknown:
            raise RuntimeError(f"Unknown --modes: {unknown}. Allowed: {sorted(_ALLOWED_MODES)}")
        if not requested_modes:
            raise RuntimeError("--modes must contain at least one mode.")

        sample_n = opts.get("sample_n")
        # argparse defaults are set, but 0 is a valid explicit value that we
        # validate below; don't let falsy values collapse back to defaults.
        concurrency = int(opts["concurrency"]) if "concurrency" in opts else 1
        poll_interval = float(opts["poll_interval"]) if "poll_interval" in opts else 2.0
        poll_timeout = float(opts["poll_timeout"]) if "poll_timeout" in opts else 300.0
        sync_timeout = float(opts["sync_timeout"]) if "sync_timeout" in opts else 600.0
        references_path: Path | None = opts.get("references")
        quality_latency_budget_ms = (
            float(opts["quality_latency_budget_ms"])
            if "quality_latency_budget_ms" in opts
            else 60_000.0
        )
        tier = str(opts.get("tier") or "")
        environment = str(opts.get("environment") or "local")
        profile = str(opts.get("profile") or "full")
        max_total_cost_micros = opts.get("max_total_cost_micros")
        fail_on_unratified = bool(opts.get("fail_on_unratified"))

        if sample_n is not None and sample_n < 1:
            raise RuntimeError("--n must be >= 1.")
        if concurrency < 1:
            raise RuntimeError("--concurrency must be >= 1.")
        if poll_interval <= 0:
            raise RuntimeError("--poll-interval must be > 0.")
        if poll_timeout <= 0:
            raise RuntimeError("--poll-timeout must be > 0.")
        if sync_timeout <= 0:
            raise RuntimeError("--sync-timeout must be > 0.")
        if quality_latency_budget_ms <= 0:
            raise RuntimeError("--quality-latency-budget-ms must be > 0.")

        workspace_id = opts.get("workspace_id") or ctx.config.memory_workspace_id
        if workspace_id is None:
            raise RuntimeError(
                "NOWING_EVAL_WORKSPACE_ID or --workspace-id is required for chainlens_latency."
            )

        queries = _DEFAULT_QUERIES[:sample_n] if sample_n else _DEFAULT_QUERIES
        if not queries:
            raise RuntimeError("No queries selected for chainlens_latency.")

        if profile == "quick":
            concurrency = 1
            queries = queries[:1]
            requested_modes = requested_modes[:1]

        references = self._load_references(references_path)

        # Pre-seed requested mode buckets so empty buckets are visible but not
        # incorrectly gated as passing with p95 = 0.
        by_mode: dict[str, _ModeStats] = {m: _ModeStats() for m in requested_modes}
        by_tier: dict[str, _ModeStats] = {}
        by_mode_tier: dict[str, _ModeStats] = {}
        overall_stats = _ModeStats()
        raw_rows: list[dict[str, Any]] = []

        sem = asyncio.Semaphore(concurrency)

        async def _run_one(query: str, mode: str) -> dict[str, Any]:
            async with sem:
                return await self._call_research(
                    ctx.http,
                    ctx.config.nowing_api_base,
                    workspace_id,
                    query,
                    mode,
                    poll_interval,
                    poll_timeout,
                    sync_timeout,
                )

        gathered = await asyncio.gather(
            *(_run_one(q, m) for m in requested_modes for q in queries),
            return_exceptions=True,
        )

        matrix_iter = ((q, m) for m in requested_modes for q in queries)
        for (query, mode), result in zip(matrix_iter, gathered, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "Research call failed for query %r mode %r: %s",
                    query,
                    mode,
                    result,
                )
                row = self._make_error_row(query, mode, result)
            else:
                row = result
            row["tier"] = tier
            row["environment"] = environment
            row["bucket_mode"] = _resolve_bucket_mode(row, requested_modes)

            mode_key = row["bucket_mode"]
            if mode_key not in by_mode:
                by_mode[mode_key] = _ModeStats()
            tier_key = row["tier"]
            if tier_key not in by_tier:
                by_tier[tier_key] = _ModeStats()
            mode_tier_key = f"{mode_key}:{tier_key}"
            if mode_tier_key not in by_mode_tier:
                by_mode_tier[mode_tier_key] = _ModeStats()

            _add_row_to_stats(by_mode[mode_key], row)
            _add_row_to_stats(by_tier[tier_key], row)
            _add_row_to_stats(by_mode_tier[mode_tier_key], row)
            _add_row_to_stats(overall_stats, row)

            recall, f1 = self._score_quality(row, references)
            if recall is not None:
                by_mode[mode_key].recall.append(recall)
                by_mode[mode_key].f1.append(f1)
                by_tier[tier_key].recall.append(recall)
                by_tier[tier_key].f1.append(f1)
                by_mode_tier[mode_tier_key].recall.append(recall)
                by_mode_tier[mode_tier_key].f1.append(f1)
                overall_stats.recall.append(recall)
                overall_stats.f1.append(f1)

            raw_rows.append(row)

        total_cost_micros = sum(r.get("cost_micros") or 0 for r in raw_rows)
        if max_total_cost_micros and total_cost_micros > max_total_cost_micros:
            raise RuntimeError(
                f"Run cost {total_cost_micros} micros exceeds cap {max_total_cost_micros}."
            )

        per_mode_buckets = {mode: _bucket_stats(stats) for mode, stats in by_mode.items()}
        per_tier_buckets = {tier: _bucket_stats(stats) for tier, stats in by_tier.items()}
        per_mode_tier_buckets = {key: _bucket_stats(stats) for key, stats in by_mode_tier.items()}
        overall_bucket = _bucket_stats(overall_stats)

        metrics: dict[str, Any] = {
            "overall": overall_bucket,
            "per_mode": per_mode_buckets,
            "per_tier": per_tier_buckets,
            "per_mode_tier": per_mode_tier_buckets,
            "recommendation": None,
        }

        # Revert balanced -> quality when quality mode beats balanced on quality
        # while staying inside the latency budget.
        if "balanced" in per_mode_buckets and "quality" in per_mode_buckets:
            b, q = per_mode_buckets["balanced"], per_mode_buckets["quality"]
            b_f1 = b.get("mean_f1") if b.get("mean_f1") is not None else b.get("mean_answer_recall")
            q_f1 = q.get("mean_f1") if q.get("mean_f1") is not None else q.get("mean_answer_recall")
            q_p95 = q.get("p95_e2e_ms", float("inf"))
            if (
                b_f1 is not None
                and q_f1 is not None
                and q_f1 > b_f1 * 1.01
                and q_p95 is not None
                and q_p95 <= quality_latency_budget_ms
            ):
                metrics["recommendation"] = "quality"
            else:
                metrics["recommendation"] = "balanced"

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        with raw_path.open("w", encoding="utf-8") as fh:
            for row in raw_rows:
                fh.write(json.dumps(row, default=str) + "\n")

        extra = {
            "workspace_id": workspace_id,
            "modes": requested_modes,
            "n_queries": len(queries),
            "concurrency": concurrency,
            "poll_interval": poll_interval,
            "poll_timeout": poll_timeout,
            "sync_timeout": sync_timeout,
            "references_path": str(references_path) if references_path else None,
            "quality_latency_budget_ms": quality_latency_budget_ms,
            "tier": tier,
            "environment": environment,
            "profile": profile,
            "total_cost_micros": total_cost_micros,
            "max_total_cost_micros": max_total_cost_micros,
            "fail_on_unratified": fail_on_unratified,
        }

        gate_violations = _evaluate_chainlens_gate(metrics)
        top, _ = _load_chainlens_gate()

        manifest_path = run_dir / "run_artifact.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "suite": self.suite,
                    "benchmark": self.name,
                    "raw_path": "raw.jsonl",
                    "metrics": metrics,
                    "extra": extra,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        if gate_violations:
            metrics["gate_violations"] = gate_violations
            run_artifact_str = str(manifest_path)
            try:
                await notify_gate_failure(
                    self.suite,
                    self.name,
                    run_timestamp,
                    gate_violations,
                    run_artifact_str,
                    extra,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send gate failure notification: %s", exc)
            if top.get("baseline_ratified"):
                raise RuntimeError(
                    f"ChainLens latency gate failed for {environment}: "
                    + "; ".join(gate_violations)
                )

        if fail_on_unratified and not top.get("baseline_ratified"):
            raise RuntimeError(
                "ChainLens latency gate is not ratified (baseline_ratified=false). "
                "Run with measured baseline and flip gate.yaml, or omit --fail-on-unratified."
            )

        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra=extra,
        )

    def _make_error_row(
        self,
        query: str,
        mode: str,
        exc: Exception,
    ) -> dict[str, Any]:
        """Turn a matrix exception into a row that the rest of the pipeline can aggregate."""
        return {
            "query": query,
            "mode": mode,
            "resolved_mode": None,
            "bucket_mode": mode,
            "duration_ms": None,
            "first_token_time_ms": None,
            "status": "error",
            "degraded": True,
            "degradation_reason": type(exc).__name__,
            "engine_reason": str(exc)[:200],
            "source_count": 0,
            "answer_length": 0,
            "answer": "",
            "sources": [],
            "cost_micros": None,
            "fallback_hit_count": 0,
            "error": str(exc)[:500],
        }

    def _load_references(self, path: Path | None) -> dict[str, str]:
        """Load optional query->reference mapping for quality scoring."""
        if path is None:
            return {}
        if not path.is_file():
            raise RuntimeError(f"References file not found: {path}")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Cannot read references file {path}: {exc}") from exc
        references: dict[str, str] = {}
        if not text.strip():
            return references

        def _add(item: Any) -> None:
            if isinstance(item, dict) and "query" in item and "reference" in item:
                key = str(item["query"]).strip().lower()
                references[key] = str(item["reference"])

        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    _add(item)
            elif isinstance(data, dict):
                for k, v in data.items():
                    _add({"query": k, "reference": v})
        except json.JSONDecodeError:
            for i, line in enumerate(text.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    _add(item)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Invalid JSON on references line {i}: {exc}") from exc
        return references

    def _score_quality(
        self,
        row: dict[str, Any],
        references: dict[str, str],
    ) -> tuple[float | None, float | None]:
        """Return (recall, f1) against the reference for this query, or (None, None)."""
        reference = references.get(str(row.get("query", "")).strip().lower())
        answer: str | None = row.get("answer")
        if not reference or not answer:
            return None, None

        def _tokens(text: str) -> set[str]:
            return set(re.findall(r"\b\w+\b", text.lower()))

        ref_tokens = _tokens(reference)
        ans_tokens = _tokens(answer)
        if not ref_tokens or not ans_tokens:
            return 0.0, 0.0
        overlap = ans_tokens & ref_tokens
        recall = len(overlap) / len(ref_tokens)
        precision = len(overlap) / len(ans_tokens)
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return recall, f1

    async def _call_research(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        workspace_id: int,
        query: str,
        mode: str,
        poll_interval: float,
        poll_timeout: float,
        sync_timeout: float,
    ) -> dict[str, Any]:
        url = f"{base_url}/api/v1/workspaces/{workspace_id}/scrapers/chainlens/research"
        # Default to sync so the call blocks and returns output when State B is on.
        # If State A is active the endpoint returns 202 and we tail/poll.
        resp = await http.post(
            url,
            params={"mode": "sync"},
            json={"query": query, "mode": mode},
            timeout=httpx.Timeout(sync_timeout, connect=10.0),
        )
        if resp.status_code == 202:
            body = resp.json()
            run_id = body.get("run_id") or resp.headers.get("x-run-id")
            if not run_id:
                raise RuntimeError("Async research call returned 202 but no run_id.")
            run_data = await self._poll_run(
                http,
                base_url,
                workspace_id,
                run_id,
                poll_interval,
                poll_timeout,
            )
            return self._parse_run(run_data, query, mode)

        resp.raise_for_status()

        # Sync success: the response body is a ResearchOutput.
        output = resp.json()
        return {
            "query": query,
            "mode": mode,
            "resolved_mode": output.get("resolved_mode"),
            "bucket_mode": _resolve_bucket_mode(
                {"mode": mode, "resolved_mode": output.get("resolved_mode"), "query": query},
                [mode],
            ),
            "duration_ms": output.get("duration_ms") or 0,
            "first_token_time_ms": output.get("first_token_time_ms"),
            "status": output.get("status"),
            "degraded": output.get("degraded") or False,
            "degradation_reason": output.get("degradation_reason"),
            "engine_reason": output.get("engine_reason"),
            "source_count": len(output.get("sources") or []),
            "answer_length": len(output.get("answer") or ""),
            "answer": output.get("answer") or "",
            "sources": output.get("sources") or [],
            "cost_micros": output.get("cost_micros") or 0,
            "fallback_hit_count": output.get("fallback_hit_count") or 0,
        }

    async def _poll_run(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        workspace_id: int,
        run_id: str,
        poll_interval: float,
        poll_timeout: float,
    ) -> dict[str, Any]:
        """Wait for an async run to finish, preferring SSE then falling back to summary poll."""
        finished = await self._tail_run_events(http, base_url, workspace_id, run_id, poll_timeout)
        if finished and finished.get("status") != "timeout":
            detail_url = f"{base_url}/api/v1/workspaces/{workspace_id}/scrapers/runs/{run_id}"
            resp = await http.get(detail_url, timeout=httpx.Timeout(poll_timeout, connect=10.0))
            if resp.status_code >= 400:
                raise RuntimeError(f"Run detail failed: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            if data.get("status") in ("running",):
                data["status"] = finished.get("status") or data.get("status")
            if finished.get("error") and not data.get("error"):
                data["error"] = finished["error"]
            return data

        logger.info("SSE tail unavailable for %s; falling back to summary poll.", run_id)
        return await self._poll_run_summary(
            http, base_url, workspace_id, run_id, poll_interval, poll_timeout
        )

    async def _tail_run_events(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        workspace_id: int,
        run_id: str,
        poll_timeout: float,
    ) -> dict[str, Any] | None:
        """Tail ``GET .../runs/{run_id}/events`` until ``run.finished`` or timeout."""
        url = f"{base_url}/api/v1/workspaces/{workspace_id}/scrapers/runs/{run_id}/events"
        started = time.perf_counter()
        try:
            async with http.stream(
                "GET",
                url,
                headers={"Accept": "text/event-stream"},
                timeout=httpx.Timeout(poll_timeout + 30.0, connect=10.0),
            ) as resp:
                if resp.status_code >= 400:
                    logger.debug("SSE endpoint returned %s for %s", resp.status_code, run_id)
                    return None
                content_type = resp.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    logger.debug("Non-SSE content-type %r for %s", content_type, run_id)
                    return None

                async for event in iter_sse_events(resp.aiter_lines()):
                    data_str = event.data.strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") == "run.finished":
                        return data
                    if time.perf_counter() - started > poll_timeout:
                        return {"status": "timeout"}
        except (httpx.HTTPError, TimeoutError, OSError) as exc:
            logger.debug("SSE tail failed for %s: %s", run_id, exc)
            return None
        return None

    async def _poll_run_summary(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        workspace_id: int,
        run_id: str,
        poll_interval: float,
        poll_timeout: float,
    ) -> dict[str, Any]:
        url = f"{base_url}/api/v1/workspaces/{workspace_id}/scrapers/runs/{run_id}"
        started = time.perf_counter()
        while True:
            resp = await http.get(url, timeout=httpx.Timeout(poll_timeout, connect=10.0))
            if resp.status_code >= 400:
                raise RuntimeError(f"Run poll failed: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            status = data.get("status")
            if status in _TERMINAL_RUN_STATUSES:
                return data
            if status not in ("running",):
                # Unknown or missing status should keep polling until a terminal
                # status is reported, rather than being treated as finished.
                logger.warning(
                    "Unexpected run status %r for %s; continuing to poll.", status, run_id
                )
            if time.perf_counter() - started > poll_timeout:
                logger.warning(
                    "Timed out polling run %s after %.1fs; recording partial result",
                    run_id,
                    poll_timeout,
                )
                data["status"] = "timeout"
                data["duration_ms"] = int((time.perf_counter() - started) * 1000)
                data.setdefault("error", f"Timed out polling run {run_id}")
                return data
            await asyncio.sleep(poll_interval)

    def _parse_run(self, run_data: dict[str, Any], query: str, mode: str) -> dict[str, Any]:
        output_text = run_data.get("output_text") or ""
        output: dict[str, Any] = {}
        if output_text:
            for line in output_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        output = parsed
                        break
                except json.JSONDecodeError:
                    continue
            if not output:
                logger.warning("Could not parse run output_text for query %r", query)

        run_status = run_data.get("status")
        degraded = output.get("degraded") or run_data.get("degraded") or False
        if run_status in ("error", "cancelled", "timeout", "failed"):
            degraded = True

        degradation_reason = output.get("degradation_reason") or run_data.get("degradation_reason")
        if degraded and not degradation_reason:
            degradation_reason = run_status or "unknown"

        return {
            "query": query,
            "mode": mode,
            "resolved_mode": output.get("resolved_mode"),
            "bucket_mode": _resolve_bucket_mode(
                {"mode": mode, "resolved_mode": output.get("resolved_mode"), "query": query},
                [mode],
            ),
            "duration_ms": run_data.get("duration_ms") or output.get("duration_ms") or 0,
            "first_token_time_ms": output.get("first_token_time_ms"),
            "status": output.get("status") or run_status or "partial",
            "degraded": degraded,
            "degradation_reason": degradation_reason,
            "engine_reason": output.get("engine_reason") or run_data.get("engine_reason"),
            "source_count": len(output.get("sources") or []),
            "answer_length": len(output.get("answer") or ""),
            "answer": output.get("answer") or "",
            "sources": output.get("sources") or [],
            "cost_micros": output.get("cost_micros") or run_data.get("cost_micros") or 0,
            "fallback_hit_count": output.get("fallback_hit_count")
            or run_data.get("fallback_hit_count")
            or 0,
        }

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="ChainLens latency + quality gate",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        per_mode = m.get("per_mode") or m.get("modes") or {}

        def _fmt(value: float | None) -> str:
            return f"{value:.0f}" if value is not None else "n/a"

        lines = ["| mode | p50 e2e | p95 e2e | p50 TTFB | p95 TTFB | recall | f1 | samples |"]
        lines.append("|---|---|---|---|---|---|---|---|")
        for mode, vals in sorted(per_mode.items()):
            lines.append(
                f"| {mode} | {_fmt(vals.get('p50_e2e_ms'))} | "
                f"{_fmt(vals.get('p95_e2e_ms'))} | "
                f"{_fmt(vals.get('p50_ttfb_ms'))} | "
                f"{_fmt(vals.get('p95_ttfb_ms'))} | "
                f"{vals.get('mean_answer_recall') or 'n/a'} | "
                f"{vals.get('mean_f1') or 'n/a'} | "
                f"{vals.get('samples_e2e', 0)} |"
            )

        if m.get("recommendation"):
            lines.append("")
            lines.append(f"**Recommended mode:** `{m['recommendation']}`")

        per_tier = m.get("per_tier", {})
        if per_tier:
            lines.append("")
            lines.append("### Per tier")
            lines.append("| tier | p50 e2e | p95 e2e | p50 TTFB | p95 TTFB | mean cost | samples |")
            lines.append("|---|---|---|---|---|---|---|")
            for tier, vals in sorted(per_tier.items()):
                tier_label = tier or "(default)"
                lines.append(
                    f"| {tier_label} | {_fmt(vals.get('p50_e2e_ms'))} | "
                    f"{_fmt(vals.get('p95_e2e_ms'))} | "
                    f"{_fmt(vals.get('p50_ttfb_ms'))} | "
                    f"{_fmt(vals.get('p95_ttfb_ms'))} | "
                    f"{_fmt(vals.get('mean_cost_micros'))} | "
                    f"{vals.get('samples_e2e', 0)} |"
                )

        per_mode_tier = m.get("per_mode_tier", {})
        if per_mode_tier:
            lines.append("")
            lines.append("### Per mode x tier")
            lines.append(
                "| mode:tier | p50 e2e | p95 e2e | p50 TTFB | p95 TTFB | mean cost | samples |"
            )
            lines.append("|---|---|---|---|---|---|---|")
            for key, vals in sorted(per_mode_tier.items()):
                lines.append(
                    f"| {key} | {_fmt(vals.get('p50_e2e_ms'))} | "
                    f"{_fmt(vals.get('p95_e2e_ms'))} | "
                    f"{_fmt(vals.get('p50_ttfb_ms'))} | "
                    f"{_fmt(vals.get('p95_ttfb_ms'))} | "
                    f"{_fmt(vals.get('mean_cost_micros'))} | "
                    f"{vals.get('samples_e2e', 0)} |"
                )

        gate_violations = m.get("gate_violations")
        if gate_violations:
            lines.append("")
            lines.append("### Gate violations")
            for v in gate_violations:
                lines.append(f"- {v}")

        # Local vs production parity delta when both environments are present.
        by_env: dict[str, RunArtifact] = {}
        for a in artifacts:
            env = a.extra.get("environment") or "local"
            if env not in by_env or a.run_timestamp > by_env[env].run_timestamp:
                by_env[env] = a
        if "local" in by_env and "production" in by_env:
            local_m = by_env["local"].metrics
            prod_m = by_env["production"].metrics

            def _delta(prod: float | None, local: float | None) -> str:
                if prod is None or local is None or local == 0:
                    return "n/a"
                return f"{(prod - local) / local:+.1%}"

            lines.append("")
            lines.append("### Local vs production parity")
            lines.append("| mode | metric | local | production | delta |")
            lines.append("|---|---|---|---|---|")
            local_modes = local_m.get("per_mode") or local_m.get("modes") or {}
            prod_modes = prod_m.get("per_mode") or prod_m.get("modes") or {}
            for mode in sorted(set(local_modes.keys()) | set(prod_modes.keys())):
                l_mode = local_modes.get(mode, {})
                p_mode = prod_modes.get(mode, {})
                for metric in ["p95_e2e_ms", "p95_ttfb_ms", "mean_cost_micros"]:
                    lines.append(
                        f"| {mode} | {metric} | {_fmt(l_mode.get(metric))} | "
                        f"{_fmt(p_mode.get(metric))} | "
                        f"{_delta(p_mode.get(metric), l_mode.get(metric))} |"
                    )

        return ReportSection(
            title="ChainLens research latency + quality by mode",
            headline=False,
            body_md="\n".join(lines),
            body_json=m,
        )


register(ChainlensLatencyBenchmark())

__all__ = ["ChainlensLatencyBenchmark"]
