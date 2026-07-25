"""Workspace-scoped memory-recall benchmark runner."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ....core.config import utc_iso_timestamp
from ....core.metrics.retrieval import score_run
from ....core.registry import ReportSection, RunArtifact, RunContext
from .dataset import Query, load_dataset
from .ingest import corpus_map_path, load_corpus_map, resolve_workspace_id
from .oracle import (
    ORACLE_MODE_SCORE_THRESHOLD,
    clamp_top_k,
    judge_returned_items,
    resolve_oracle_mode,
    validate_min_similarity,
)

_DESCRIPTION = (
    "Versioned workspace-memory recall quality: recall@5, MRR, distractor noise, "
    "off-corpus rate, plus precision@k diagnostics."
)

GATE_CONFIG_PATH = Path(__file__).with_name("gate.yaml")


def _sample_queries(queries: Sequence[Query], sample_n: int | None) -> list[Query]:
    if sample_n is None:
        return list(queries)
    if sample_n < 1:
        raise ValueError("--n must be a positive integer")
    return list(queries[:sample_n])


async def _gather_with_limit(coroutines: Iterable, *, concurrency: int) -> list[Any]:
    """Run coroutines under a semaphore, returning exceptions instead of raising.

    ``return_exceptions=True`` matters: the default propagates the first failure
    *without* cancelling siblings, so the run aborts with no artifact while
    in-flight requests keep firing into an HTTP client that the CLI is already
    closing. Collecting failures instead lets the runner persist a partial
    artifact that the gate can then reject on ``n_failed_queries``.
    """

    if concurrency < 1:
        raise ValueError("--concurrency must be a positive integer")
    semaphore = asyncio.Semaphore(concurrency)

    async def limited(coroutine):
        async with semaphore:
            return await coroutine

    return await asyncio.gather(
        *(limited(coroutine) for coroutine in coroutines), return_exceptions=True
    )


def _memory_ref_for_item(item: Mapping[str, Any], *, memory_ids: Mapping[int, str]) -> str | None:
    """Resolve a returned backend memory id to the stable fixture reference.

    The ingest map is the only authority. A ``memory_ref`` echoed back by the
    backend is checked for membership rather than trusted, so a response cannot
    name itself into the labeled corpus.
    """

    direct_ref = item.get("memory_ref")
    if isinstance(direct_ref, str) and direct_ref in memory_ids.values():
        return direct_ref

    memory_id = item.get("id")
    if isinstance(memory_id, bool):
        return None
    if isinstance(memory_id, int):
        return memory_ids.get(memory_id)
    if isinstance(memory_id, float):
        # A JSON serialiser may render an integral id as 101.0.
        return memory_ids.get(int(memory_id)) if memory_id.is_integer() else None
    if isinstance(memory_id, str):
        # ``isdecimal`` not ``isdigit``: "²".isdigit() is True but int("²") raises.
        return memory_ids.get(int(memory_id)) if memory_id.strip().isdecimal() else None
    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce a persisted metric to a float without crashing the report.

    ``dict.get(key, default)`` only guards a *missing* key. A manifest carrying
    ``null``, a string or a nested object would otherwise raise mid-render and
    abort report generation for the whole suite.
    """

    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _safe_pair(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, list | tuple) or len(value) != 2:
        return None
    low, high = value
    if isinstance(low, bool) or isinstance(high, bool):
        return None
    if not isinstance(low, int | float) or not isinstance(high, int | float):
        return None
    return float(low), float(high)


def _metric_at(values: Any, k: int) -> float | None:
    if not isinstance(values, Mapping):
        return None
    value = values.get(str(k), values.get(k))
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _write_json_atomic(path: Path, payload: Any) -> None:
    """Serialise to ``path`` via a uniquely-named temp file, then rename.

    ``allow_nan=False`` because bare ``NaN``/``Infinity`` is not valid JSON for
    any non-Python consumer, and the temp name is unique so two concurrent runs
    cannot publish a spliced file.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


class MemoryRecallBenchmark:
    """Evaluate direct ``POST /memories/search`` quality against committed labels."""

    suite: str = "memory"
    name: str = "recall"
    headline: bool = False
    description: str = _DESCRIPTION
    #: Memory endpoints are workspace-scoped and touch neither a SearchSpace nor
    #: a chat model, so this suite must not require `setup` to have provisioned
    #: either (see core/config.py's note on keeping the two ids separate).
    requires_suite_setup: bool = False

    def gate_config_path(self) -> Path:
        """Where this benchmark keeps its ship thresholds.

        ``core.gate`` stays suite-agnostic; the suite owns its own config path.
        """

        return GATE_CONFIG_PATH

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--n", dest="sample_n", type=int, default=None)
        parser.add_argument("--top-k", type=int, default=5)
        parser.add_argument(
            "--min-similarity",
            type=float,
            default=0.3,
            help=(
                "Similarity floor, applied only when the response carries a usable "
                "score signal. The current backend serialises score=0.0 for every "
                "hit, so runs degrade to rank-only and record that in the artifact."
            ),
        )
        parser.add_argument("--concurrency", type=int, default=4)
        parser.add_argument(
            "--workspace-id",
            type=int,
            default=None,
            help="Workspace tenant for memory endpoints; overrides NOWING_EVAL_WORKSPACE_ID.",
        )

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import run_ingest

        await run_ingest(ctx, workspace_id=opts.get("workspace_id"))

    async def purge(self, ctx: RunContext, *, workspace_id: int | None = None) -> int:
        """Remove every fixture memory this suite seeded into ``workspace_id``."""

        from .ingest import run_purge

        return await run_purge(ctx, workspace_id=workspace_id)

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        effective_top_k = clamp_top_k(int(opts.get("top_k", 5)))
        # Validated before any network call, not per returned item — otherwise an
        # invalid value costs a full run before raising, or never raises at all
        # when every query comes back empty.
        min_similarity = validate_min_similarity(opts.get("min_similarity", 0.3))
        concurrency = int(opts.get("concurrency", 4))
        workspace_id = resolve_workspace_id(ctx, opts.get("workspace_id"))
        dataset = load_dataset()
        queries = _sample_queries(dataset.queries, opts.get("sample_n"))

        if not queries:
            raise RuntimeError("Memory-recall dataset did not provide any queries")

        corpus_map = load_corpus_map(
            corpus_map_path(ctx.maps_dir(), workspace_id=workspace_id),
            workspace_id=workspace_id,
            corpus=dataset.corpus,
        )
        missing_refs = sorted(set(dataset.corpus) - set(corpus_map))
        if missing_refs:
            # A map covering only part of the corpus scores against labels that
            # cannot possibly be satisfied. Only checking for an *empty* map lets
            # a 3-of-36 map run to completion and report a fake quality collapse.
            raise RuntimeError(
                "Memory-recall corpus is not fully ingested for workspace "
                f"{workspace_id}: {len(missing_refs)} of {len(dataset.corpus)} memories are "
                f"unmapped (first missing: {', '.join(missing_refs[:5])}). Run "
                "`python -m nowing_evals ingest memory recall` first."
            )
        id_to_ref = {memory_id: ref for ref, memory_id in corpus_map.items()}

        client = ctx.memories_client()

        async def search(query: Query) -> list[dict[str, Any]]:
            return await client.search(workspace_id, query.query, top_k=effective_top_k)

        search_results = await _gather_with_limit(
            (search(query) for query in queries), concurrency=concurrency
        )

        # The oracle mode is a property of the run, not of one query: deciding
        # per query silently blends two metric definitions in one aggregate.
        all_items = [
            item
            for result in search_results
            if not isinstance(result, BaseException)
            for item in result
        ]
        oracle_mode = resolve_oracle_mode(all_items)
        applied_min_similarity = (
            min_similarity if oracle_mode == ORACLE_MODE_SCORE_THRESHOLD else None
        )

        per_query_retrieved: dict[str, list[str]] = {}
        per_query_distractors: dict[str, list[str]] = {}
        per_query_off_corpus: dict[str, list[str]] = {}
        raw_rows: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []

        for query, result in zip(queries, search_results, strict=True):
            if isinstance(result, BaseException):
                failures.append(
                    {
                        "query_id": query.query_id,
                        "error": f"{type(result).__name__}: {result}",
                    }
                )
                raw_rows.append(
                    {
                        "query_id": query.query_id,
                        "query": query.query,
                        "error": f"{type(result).__name__}: {result}",
                        "oracle_mode": oracle_mode,
                    }
                )
                continue

            judged = judge_returned_items(
                result,
                top_k=effective_top_k,
                mode=oracle_mode,
                min_similarity=applied_min_similarity,
                resolve_ref=lambda item: _memory_ref_for_item(item, memory_ids=id_to_ref),
            )
            # AC-3: every returned slot stays in the scored set. Filtering
            # non-hits out here would shrink the precision/noise denominator and
            # drive both toward a perfect score.
            per_query_retrieved[query.query_id] = [row["scored_ref"] for row in judged]
            per_query_distractors[query.query_id] = list(query.distractors)
            per_query_off_corpus[query.query_id] = [
                row["scored_ref"] for row in judged if row["off_corpus"]
            ]
            raw_rows.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "query_type": query.type,
                    "tags": query.tags,
                    "qrels": query.qrels,
                    "distractors": query.distractors,
                    "returned_items": result,
                    "judged_slots": judged,
                    "scored_refs": per_query_retrieved[query.query_id],
                    "oracle_mode": oracle_mode,
                }
            )

        scores = score_run(
            per_query_retrieved=per_query_retrieved,
            per_query_qrels={query.query_id: query.qrels for query in queries},
            per_query_distractors=per_query_distractors,
            per_query_off_corpus=per_query_off_corpus,
            ks=(1, effective_top_k),
            ndcg_k=effective_top_k,
            primary_k=effective_top_k,
        )
        metrics = scores.to_dict()
        metrics.update(
            {
                "top_k": effective_top_k,
                "oracle_mode": oracle_mode,
                "min_similarity": applied_min_similarity,
                "requested_min_similarity": min_similarity,
                "n_failed_queries": len(failures),
                "n_requested_queries": len(queries),
            }
        )

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        with raw_path.open("w", encoding="utf-8") as handle:
            for row in raw_rows:
                handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")

        extra = {
            "workspace_id": workspace_id,
            "concurrency": concurrency,
            "sample_n": len(queries),
            "provider_model": getattr(ctx, "provider_model", None),
            "failures": failures,
        }
        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra=extra,
        )
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
        return artifact

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        if not artifacts:
            return ReportSection(
                title="Memory recall quality",
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )

        latest = max(artifacts, key=lambda artifact: artifact.run_timestamp)
        metrics = latest.metrics
        primary_k = _safe_int(metrics.get("primary_k"), 5) or 5
        ndcg_k = _safe_int(metrics.get("ndcg_k"), primary_k) or primary_k
        precision_at_primary = _metric_at(metrics.get("precision_at_k"), primary_k)
        recall_at_primary = _metric_at(metrics.get("recall_at_k"), primary_k)
        ci = _safe_pair(metrics.get("precision_at_5_ci"))
        micro = _safe_float(metrics.get("precision_at_primary_k_micro"))
        ci_text = (
            f" (pooled {micro:.3f}, Wilson 95% CI {ci[0]:.3f}–{ci[1]:.3f})"
            if ci is not None
            else " (CI unavailable)"
        )
        precision_text = (
            "not measured" if precision_at_primary is None else f"{precision_at_primary:.3f}"
        )
        recall_text = "not measured" if recall_at_primary is None else f"{recall_at_primary:.3f}"
        failed = _safe_int(metrics.get("n_failed_queries"))
        off_corpus_text = (
            f"{_safe_float(metrics.get('off_corpus_rate')):.3f}"
            if metrics.get("off_corpus_measured") is True
            else "not measured"
        )
        lines = [
            f"- Queries: {_safe_int(metrics.get('n_queries'))}"
            + (f" ({failed} failed)" if failed else ""),
            f"- Oracle mode: {metrics.get('oracle_mode', '?')} "
            f"(top_k={metrics.get('top_k', '?')}, "
            f"min_similarity={metrics.get('min_similarity', 'not applied')})",
            "",
            "Ship-gated:",
            f"- Recall@{primary_k}: {recall_text}",
            f"- MRR: {_safe_float(metrics.get('mrr')):.3f}",
            f"- Distractor noise rate: "
            f"{_safe_float(metrics.get('distractor_noise_rate')):.3f}",
            f"- Off-corpus rate: {off_corpus_text}",
            "",
            "Diagnostics:",
            f"- Precision@{primary_k} (macro): {precision_text}{ci_text}",
            f"- Complement noise rate (1 - precision@{primary_k}): "
            f"{_safe_float(metrics.get('noise_rate')):.3f}",
            f"- nDCG@{ndcg_k}: {_safe_float(metrics.get('ndcg_at_10')):.3f}",
        ]
        return ReportSection(
            title="Memory recall quality",
            headline=False,
            body_md="\n".join(lines),
            body_json=metrics,
        )


__all__ = ["GATE_CONFIG_PATH", "MemoryRecallBenchmark"]
