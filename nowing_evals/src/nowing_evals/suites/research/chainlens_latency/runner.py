"""ChainLens research latency gate (Story 9.3).

Runs a small set of research queries in each requested mode, records e2e and
TTFB latency, and computes p50/p95 per mode. The gate can be used to validate
that the default ``balanced`` mode meets the latency budget before enabling
State B (sync chat mode).

ponytail: This runner intentionally does not score answer quality; the
``chainlens_latency`` gate is a latency/NFR-9 gate. Quality gating lives in
separate suites once a labeled research dataset exists.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass
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
class _Latencies:
    e2e: list[float] = None  # type: ignore[assignment]
    ttfb: list[float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.e2e = []
        self.ttfb = []


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

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--modes",
            default="balanced,quality",
            help="Comma-separated research modes to compare.",
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

        workspace_id = ctx.config.memory_workspace_id
        if workspace_id is None:
            raise RuntimeError("NOWING_EVAL_WORKSPACE_ID is required for chainlens_latency.")

        queries = _DEFAULT_QUERIES[:sample_n] if sample_n else _DEFAULT_QUERIES
        if not queries:
            raise RuntimeError("No queries selected for chainlens_latency.")

        by_mode: dict[str, _Latencies] = {m: _Latencies() for m in modes}
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
            mode = row["mode"]
            by_mode[mode].e2e.append(row["duration_ms"])
            if row["first_token_time_ms"] is not None:
                by_mode[mode].ttfb.append(row["first_token_time_ms"])
            raw_rows.append(row)

        metrics: dict[str, Any] = {"modes": {}}
        for mode, lat in by_mode.items():
            metrics["modes"][mode] = {
                "p50_e2e_ms": _percentile(lat.e2e, 0.5),
                "p95_e2e_ms": _percentile(lat.e2e, 0.95),
                "p50_ttfb_ms": _percentile(lat.ttfb, 0.5) if lat.ttfb else None,
                "p95_ttfb_ms": _percentile(lat.ttfb, 0.95) if lat.ttfb else None,
                "samples_e2e": len(lat.e2e),
                "samples_ttfb": len(lat.ttfb),
            }

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
            timeout=httpx.Timeout(30.0, connect=10.0),
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
            resp = await http.get(url, timeout=httpx.Timeout(30.0))
            if resp.status_code >= 400:
                raise RuntimeError(f"Run poll failed: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            if data.get("status") not in ("running",):
                return data
            if time.perf_counter() - started > poll_timeout:
                raise RuntimeError(f"Timed out polling run {run_id}")
            await asyncio.sleep(poll_interval)

    def _parse_run(self, run_data: dict[str, Any], query: str, mode: str) -> dict[str, Any]:
        output_text = run_data.get("output_text") or ""
        output: dict[str, Any] = {}
        if output_text:
            try:
                output = json.loads(output_text.splitlines()[0])
            except Exception:
                logger.warning("Could not parse run output_text for query %r", query)
        return {
            "query": query,
            "mode": mode,
            "resolved_mode": output.get("resolved_mode"),
            "duration_ms": run_data.get("duration_ms") or output.get("duration_ms") or 0,
            "first_token_time_ms": output.get("first_token_time_ms"),
            "status": run_data.get("status"),
            "source_count": len(output.get("sources") or []),
            "answer_length": len(output.get("answer") or ""),
        }

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="ChainLens latency gate",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        lines = ["| mode | p50 e2e | p95 e2e | p50 ttfb | p95 ttfb | samples |"]
        lines.append("|---|---|---|---|---|---|")
        for mode, vals in m.get("modes", {}).items():
            lines.append(
                f"| {mode} | {vals.get('p50_e2e_ms', 0):.0f} | "
                f"{vals.get('p95_e2e_ms', 0):.0f} | "
                f"{vals.get('p50_ttfb_ms') or 'n/a'} | "
                f"{vals.get('p95_ttfb_ms') or 'n/a'} | "
                f"{vals.get('samples_e2e', 0)} |"
            )
        return ReportSection(
            title="ChainLens research latency by mode",
            headline=False,
            body_md="\n".join(lines),
            body_json=m,
        )


register(ChainlensLatencyBenchmark())

__all__ = ["ChainlensLatencyBenchmark"]
