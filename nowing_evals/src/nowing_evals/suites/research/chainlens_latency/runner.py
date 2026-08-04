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


@dataclass
class _ModeStats:
    e2e: list[float] = None  # type: ignore[assignment]
    ttfb: list[float] = None  # type: ignore[assignment]
    recall: list[float] = None  # type: ignore[assignment]
    f1: list[float] = None  # type: ignore[assignment]
    cost: list[float] = None  # type: ignore[assignment]
    n_total: int = 0
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

    def _check(name: str, value: float | None, max_val: float | None = None) -> None:
        if value is None:
            return
        if max_val is not None and value > max_val:
            violations.append(f"{name} {value:.3f} exceeds max {max_val:.3f}")

    per_mode_thresholds = thresholds.get("per_mode", {})
    for mode, vals in metrics.get("modes", {}).items():
        t = per_mode_thresholds.get(mode, {})
        _check(f"mode {mode} p95 e2e (ms)", vals.get("p95_e2e_ms"), t.get("max_p95_e2e_ms"))
        _check(
            f"mode {mode} degraded rate", vals.get("degraded_rate"), thresholds.get("max_degraded_rate")
        )
        _check(
            f"mode {mode} engine unavailable rate",
            vals.get("engine_unavailable_rate"),
            thresholds.get("max_engine_unavailable_rate"),
        )

    return violations


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


class ChainlensLatencyBenchmark:
    suite: str = "research"
    name: str = "chainlens_latency"
    headline: bool = False
    description: str = _DESCRIPTION
    #: The benchmark hits a workspace-scoped research endpoint; it does not need
    #: a SearchSpace or a pinned chat model, so it must not require `setup`.
    requires_suite_setup: bool = False

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--modes",
            default="speed,balanced,quality",
            help="Comma-separated research modes to compare (Nowing schema: speed, balanced, quality; use quality for ChainLens deep/deep-reasoning).",
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
        parser.add_argument("--concurrency", type=int, default=1)
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
            help="quick: first mode + first query. full: full mode × query matrix.",
        )
        parser.add_argument(
            "--poll-interval", type=float, default=2.0, help="Seconds between run polls."
        )
        parser.add_argument(
            "--poll-timeout",
            type=float,
            default=300.0,
            help="Max seconds to wait for an async run.",
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

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        # No ingest required; this is a live latency gate against the engine.
        return

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        modes = [
            m.strip() for m in (opts.get("modes") or "balanced,quality").split(",") if m.strip()
        ]
        sample_n = opts.get("sample_n")
        concurrency = max(1, int(opts.get("concurrency") or 1))
        poll_interval = float(opts.get("poll_interval") or 2.0)
        poll_timeout = float(opts.get("poll_timeout") or 300.0)
        references_path: Path | None = opts.get("references")
        quality_latency_budget_ms = float(opts.get("quality_latency_budget_ms") or 60_000.0)
        tier = str(opts.get("tier") or "")
        environment = str(opts.get("environment") or "local")
        profile = str(opts.get("profile") or "full")

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
            modes = modes[:1]

        references = self._load_references(references_path)

        by_mode: dict[str, _ModeStats] = {m: _ModeStats() for m in modes}
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
                )

        results = await asyncio.gather(*(_run_one(q, m) for m in modes for q in queries))

        for row in results:
            row["tier"] = tier
            row["environment"] = environment
            mode_requested = row["mode"]
            resolved_mode = row.get("resolved_mode")
            mode = resolved_mode or mode_requested
            if resolved_mode and resolved_mode != mode_requested:
                logger.warning(
                    "Run resolved to %r instead of requested %r for query %r",
                    resolved_mode,
                    mode_requested,
                    row["query"],
                )
            if mode not in by_mode:
                by_mode[mode] = _ModeStats()
            stats = by_mode[mode]
            stats.n_total += 1
            stats.e2e.append(row["duration_ms"])
            if row["first_token_time_ms"] is not None:
                stats.ttfb.append(row["first_token_time_ms"])
            recall, f1 = self._score_quality(row, references)
            if recall is not None:
                stats.recall.append(recall)
                stats.f1.append(f1)
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
            if row.get("cost_micros"):
                stats.cost.append(float(row["cost_micros"]))
            raw_rows.append(row)

        def _rate(num: int, denom: int) -> float | None:
            return num / denom if denom else None

        metrics: dict[str, Any] = {"modes": {}, "recommendation": None}
        for mode, stats in by_mode.items():
            n = stats.n_total
            metrics["modes"][mode] = {
                "p50_e2e_ms": _percentile(stats.e2e, 0.5),
                "p95_e2e_ms": _percentile(stats.e2e, 0.95),
                "p50_ttfb_ms": _percentile(stats.ttfb, 0.5) if stats.ttfb else None,
                "p95_ttfb_ms": _percentile(stats.ttfb, 0.95) if stats.ttfb else None,
                "samples_e2e": len(stats.e2e),
                "samples_ttfb": len(stats.ttfb),
                "mean_answer_recall": sum(stats.recall) / len(stats.recall)
                if stats.recall
                else None,
                "mean_f1": sum(stats.f1) / len(stats.f1) if stats.f1 else None,
                "samples_quality": len(stats.recall),
                "n_total": n,
                "sources_partial_rate": _rate(stats.n_partial, n),
                "engine_unavailable_rate": _rate(stats.n_engine_unavailable, n),
                "degraded_rate": _rate(stats.n_degraded, n),
                "degradation_reason_counts": dict(stats.degradation_reasons),
                "fallback_kb_hits": stats.fallback_hit_count,
                "mean_cost_micros": sum(stats.cost) / len(stats.cost) if stats.cost else None,
            }

        # Revert balanced -> quality when quality mode beats balanced on quality
        # while staying inside the latency budget.
        if "balanced" in metrics["modes"] and "quality" in metrics["modes"]:
            b, q = metrics["modes"]["balanced"], metrics["modes"]["quality"]
            b_f1 = b.get("mean_f1") if b.get("mean_f1") is not None else b.get("mean_answer_recall")
            q_f1 = q.get("mean_f1") if q.get("mean_f1") is not None else q.get("mean_answer_recall")
            q_p95 = q.get("p95_e2e_ms", float("inf"))
            if (
                b_f1 is not None
                and q_f1 is not None
                and q_f1 > b_f1 * 1.01
                and q_p95 <= quality_latency_budget_ms
            ):
                metrics["recommendation"] = "quality"
            else:
                metrics["recommendation"] = "balanced"

        gate_violations = _evaluate_chainlens_gate(metrics)
        if gate_violations:
            metrics["gate_violations"] = gate_violations
            top, _ = _load_chainlens_gate()
            if top.get("baseline_ratified"):
                raise RuntimeError(
                    f"ChainLens latency gate failed for {environment}: " + "; ".join(gate_violations)
                )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        with raw_path.open("w", encoding="utf-8") as fh:
            for row in raw_rows:
                fh.write(json.dumps(row, default=str) + "\n")

        extra = {
            "workspace_id": workspace_id,
            "modes": modes,
            "n_queries": len(queries),
            "concurrency": concurrency,
            "poll_interval": poll_interval,
            "poll_timeout": poll_timeout,
            "references_path": str(references_path) if references_path else None,
            "quality_latency_budget_ms": quality_latency_budget_ms,
            "tier": tier,
            "environment": environment,
            "profile": profile,
        }
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
        return RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra=extra,
        )

    def _load_references(self, path: Path | None) -> dict[str, str]:
        """Load optional query->reference mapping for quality scoring."""
        if path is None:
            return {}
        text = path.read_text(encoding="utf-8")
        references: dict[str, str] = {}
        if not text.strip():
            return references
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "query" in item and "reference" in item:
                        references[item["query"]] = item["reference"]
            elif isinstance(data, dict):
                references = data
        except json.JSONDecodeError:
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and "query" in item and "reference" in item:
                        references[item["query"]] = item["reference"]
                except json.JSONDecodeError:
                    continue
        return references

    def _score_quality(
        self, row: dict[str, Any], references: dict[str, str]
    ) -> tuple[float | None, float | None]:
        """Return (recall, f1) against the reference for this query, or (None, None)."""
        reference = references.get(row["query"])
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
    ) -> dict[str, Any]:
        url = f"{base_url}/api/v1/workspaces/{workspace_id}/scrapers/chainlens/research"
        # Default to sync so the call blocks and returns output when State B is on.
        # If State A is active the endpoint returns 202 and we poll.
        resp = await http.post(
            url,
            params={"mode": "sync"},
            json={"query": query, "mode": mode},
            timeout=httpx.Timeout(poll_timeout, connect=10.0),
        )
        if resp.status_code == 202:
            body = resp.json()
            run_id = body["run_id"]
            run_data = await self._poll_run(
                http,
                base_url,
                workspace_id,
                run_id,
                poll_interval,
                poll_timeout,
            )
            return self._parse_run(run_data, query, mode)

        if resp.status_code >= 400:
            raise RuntimeError(f"Research call failed: {resp.status_code} {resp.text[:200]}")

        # Sync success: the response body is a ResearchOutput.
        output = resp.json()
        return {
            "query": query,
            "mode": mode,
            "resolved_mode": output.get("resolved_mode"),
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
        url = f"{base_url}/api/v1/workspaces/{workspace_id}/scrapers/runs/{run_id}"
        started = time.perf_counter()
        while True:
            resp = await http.get(url, timeout=httpx.Timeout(poll_timeout, connect=10.0))
            if resp.status_code >= 400:
                raise RuntimeError(f"Run poll failed: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            if data.get("status") not in ("running",):
                return data
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
        return {
            "query": query,
            "mode": mode,
            "resolved_mode": output.get("resolved_mode"),
            "duration_ms": run_data.get("duration_ms") or output.get("duration_ms") or 0,
            "first_token_time_ms": output.get("first_token_time_ms"),
            "status": run_data.get("status") or output.get("status"),
            "degraded": output.get("degraded") or run_data.get("degraded") or False,
            "degradation_reason": output.get("degradation_reason")
            or run_data.get("degradation_reason"),
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
        lines = ["| mode | p50 e2e | p95 e2e | p50 ttfb | p95 ttfb | recall | f1 | samples |"]
        lines.append("|---|---|---|---|---|---|---|---|")
        for mode, vals in m.get("modes", {}).items():
            lines.append(
                f"| {mode} | {vals.get('p50_e2e_ms', 0):.0f} | "
                f"{vals.get('p95_e2e_ms', 0):.0f} | "
                f"{vals.get('p50_ttfb_ms') or 'n/a'} | "
                f"{vals.get('p95_ttfb_ms') or 'n/a'} | "
                f"{vals.get('mean_answer_recall') or 'n/a'} | "
                f"{vals.get('mean_f1') or 'n/a'} | "
                f"{vals.get('samples_e2e', 0)} |"
            )
        if m.get("recommendation"):
            lines.append("")
            lines.append(f"**Recommended mode:** `{m['recommendation']}`")

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
            for mode in sorted(
                set(local_m.get("modes", {}).keys()) | set(prod_m.get("modes", {}).keys())
            ):
                l_mode = local_m.get("modes", {}).get(mode, {})
                p_mode = prod_m.get("modes", {}).get(mode, {})
                for metric in ["p95_e2e_ms", "p95_ttfb_ms", "mean_cost_micros"]:
                    lines.append(
                        f"| {mode} | {metric} | {l_mode.get(metric) or 'n/a'} | "
                        f"{p_mode.get(metric) or 'n/a'} | "
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
