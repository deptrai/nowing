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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ....core.arms import ArmRequest, NowingArm
from ....core.clients import NewChatClient
from ....core.config import utc_iso_timestamp
from ....core.registry import (
    ReportSection,
    RunArtifact,
    RunContext,
    register,
)

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
class _Case:
    case_id: str
    query: str
    tags: list[str]
    mentioned_document_ids: list[int]
    disabled_tools: list[str]
    expected_contains: list[str]


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


def _validate_case_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise RuntimeError(f"Invalid case row: expected object, got {row!r}")
    case_id = row.get("case_id")
    if case_id is None:
        raise RuntimeError("Case row missing 'case_id'")
    query = row.get("query")
    if not isinstance(query, str) or not query.strip():
        raise RuntimeError(f"Case {case_id!r} missing or empty 'query'")
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

        if not cases:
            raise RuntimeError("No chat cases selected for the requested filters.")

        client = NewChatClient(ctx.http, ctx.config.nowing_api_base)
        arm = NowingArm(client=client, search_space_id=search_space_id)

        sem = asyncio.Semaphore(concurrency)

        async def _run_one(case: _Case) -> _CaseResult:
            async with sem:
                request = ArmRequest(
                    question_id=case.case_id,
                    prompt=case.query,
                    mentioned_document_ids=case.mentioned_document_ids or None,
                    options={"disabled_tools": case.disabled_tools} if case.disabled_tools else {},
                )
                try:
                    result = await asyncio.wait_for(arm.answer(request), timeout=timeout_s)
                except TimeoutError:
                    return _CaseResult(
                        case_id=case.case_id,
                        tags=case.tags,
                        query=case.query,
                        text="",
                        error="TimeoutError: turn exceeded timeout",
                        latency_ms=int(timeout_s * 1000),
                        ttfb_ms=None,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        cost_micros=0,
                        citation_count=0,
                        finished_normally=False,
                        expected_contains=case.expected_contains,
                        contains_hits=0,
                    )

                if result.error:
                    return _CaseResult(
                        case_id=case.case_id,
                        tags=case.tags,
                        query=case.query,
                        text=result.raw_text,
                        error=result.error,
                        latency_ms=result.latency_ms,
                        ttfb_ms=result.extra.get("ttfb_ms"),
                        prompt_tokens=result.input_tokens,
                        completion_tokens=result.output_tokens,
                        total_tokens=result.input_tokens + result.output_tokens,
                        cost_micros=result.cost_micros,
                        citation_count=len(result.citations),
                        finished_normally=result.extra.get("finished_normally", False),
                        expected_contains=case.expected_contains,
                        contains_hits=_contains_hits(result.raw_text, case.expected_contains),
                    )

                return _CaseResult(
                    case_id=case.case_id,
                    tags=case.tags,
                    query=case.query,
                    text=result.raw_text,
                    error=None,
                    latency_ms=result.latency_ms,
                    ttfb_ms=result.extra.get("ttfb_ms"),
                    prompt_tokens=result.input_tokens,
                    completion_tokens=result.output_tokens,
                    total_tokens=result.input_tokens + result.output_tokens,
                    cost_micros=result.cost_micros,
                    citation_count=len(result.citations),
                    finished_normally=result.extra.get("finished_normally", False),
                    expected_contains=case.expected_contains,
                    contains_hits=_contains_hits(result.raw_text, case.expected_contains),
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
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )

        metrics = self._aggregate(results)

        extra = {
            "search_space_id": search_space_id,
            "workspace_id": workspace_id,
            "n_cases": len(cases),
            "concurrency": concurrency,
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

    def _aggregate(self, results: list[_CaseResult]) -> dict[str, Any]:
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

        return {
            "overall": overall,
            "per_tag": {tag: _bucket(items) for tag, items in per_tag.items()},
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
