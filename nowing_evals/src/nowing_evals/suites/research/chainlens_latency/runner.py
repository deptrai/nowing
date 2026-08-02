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
from pathlib import Path
from typing import Any

import httpx

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

    def __post_init__(self) -> None:
        self.e2e = []
        self.ttfb = []
        self.recall = []
        self.f1 = []


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

        workspace_id = opts.get("workspace_id") or ctx.config.memory_workspace_id
        if workspace_id is None:
            raise RuntimeError(
                "NOWING_EVAL_WORKSPACE_ID or --workspace-id is required for chainlens_latency."
            )

        queries = _DEFAULT_QUERIES[:sample_n] if sample_n else _DEFAULT_QUERIES
        if not queries:
            raise RuntimeError("No queries selected for chainlens_latency.")

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
            by_mode[mode].e2e.append(row["duration_ms"])
            if row["first_token_time_ms"] is not None:
                by_mode[mode].ttfb.append(row["first_token_time_ms"])
            recall, f1 = self._score_quality(row, references)
            if recall is not None:
                by_mode[mode].recall.append(recall)
                by_mode[mode].f1.append(f1)
            raw_rows.append(row)

        metrics: dict[str, Any] = {"modes": {}, "recommendation": None}
        for mode, stats in by_mode.items():
            metrics["modes"][mode] = {
                "p50_e2e_ms": _percentile(stats.e2e, 0.5),
                "p95_e2e_ms": _percentile(stats.e2e, 0.95),
                "p50_ttfb_ms": _percentile(stats.ttfb, 0.5) if stats.ttfb else None,
                "p95_ttfb_ms": _percentile(stats.ttfb, 0.95) if stats.ttfb else None,
                "samples_e2e": len(stats.e2e),
                "samples_ttfb": len(stats.ttfb),
                "mean_answer_recall": sum(stats.recall) / len(stats.recall) if stats.recall else None,
                "mean_f1": sum(stats.f1) / len(stats.f1) if stats.f1 else None,
                "samples_quality": len(stats.recall),
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
            "source_count": len(output.get("sources") or []),
            "answer_length": len(output.get("answer") or ""),
            "answer": output.get("answer") or "",
            "sources": output.get("sources") or [],
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
            "source_count": len(output.get("sources") or []),
            "answer_length": len(output.get("answer") or ""),
            "answer": output.get("answer") or "",
            "sources": output.get("sources") or [],
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
        return ReportSection(
            title="ChainLens research latency + quality by mode",
            headline=False,
            body_md="\n".join(lines),
            body_json=m,
        )


register(ChainlensLatencyBenchmark())

__all__ = ["ChainlensLatencyBenchmark"]
