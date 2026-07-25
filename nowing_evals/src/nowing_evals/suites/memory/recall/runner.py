"""Memory-recall benchmark runner (Story 3.9, AC-1 / AC-3 / AC-5).

Scores the backend recall surface (``POST /workspaces/{id}/memories/search``)
against the bundled labeled dataset. Mirrors the CUREv1 single-arm retrieval
pattern (``suites/medical/cure/runner.py``): ``run()`` builds
``per_query_retrieved``, scores via ``core.metrics.retrieval.score_run``, and
persists ``raw.jsonl`` + ``run_artifact.json`` under
``data/memory/runs/<ts>/recall/``.

No LLM is in the loop — retrieval quality is measured directly, so the numbers
the gate blocks on reflect *recall*, not agent phrasing (story §9).

Two indirections are deliberate rather than incidental:

* ``load_dataset`` and ``MemoriesClient`` are resolved through their modules at
  call time, not bound at import. Binding them at import would make the runner
  untestable without a live server — a ``monkeypatch.setattr`` on the module
  attribute would never be seen by an already-bound local name.
* ``search`` is invoked according to its actual signature. The real client is
  workspace-scoped; a test double need not be.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import logging
from typing import Any

from ....core.config import utc_iso_timestamp
from ....core.metrics.retrieval import score_run
from ....core.registry import ReportSection, RunArtifact, RunContext
from .oracle import MAX_TOP_K, clamp_top_k, classify_results

logger = logging.getLogger(__name__)

_DESCRIPTION = "Memory recall quality (precision@5 + noise rate, Wilson 95% CI) vs labeled qrels."

DEFAULT_MIN_SIMILARITY = 0.30


# --------------------------------------------------------------------------- #
# Late-bound collaborators (see module docstring)
# --------------------------------------------------------------------------- #


def _load_dataset(**kwargs: Any):
    """Call ``dataset.load_dataset`` through the module so patches are honoured."""

    module = importlib.import_module(f"{__package__}.dataset")
    return module.load_dataset(**kwargs)


def _build_memories_client(ctx: Any):
    """Instantiate the memories client, preferring a patched package attribute.

    Tests replace ``suites.memory.recall.MemoriesClient`` with a fake, so the
    package attribute is the authoritative source. Falls back to the real client
    when nothing has been substituted.
    """

    package = importlib.import_module(__package__)
    client_cls = getattr(package, "MemoriesClient", None)
    if client_cls is None:  # pragma: no cover - defensive
        from ....core.clients import MemoriesClient as client_cls  # noqa: PLC0415, N813

    http = getattr(ctx, "http", None)
    config = getattr(ctx, "config", None)
    base = getattr(config, "nowing_api_base", "") if config is not None else ""
    return client_cls(http, base)


def _search_accepts_workspace(client: Any) -> bool:
    """Whether ``client.search`` takes a ``workspace_id`` parameter."""

    try:
        params = inspect.signature(client.search).parameters
    except (TypeError, ValueError):  # pragma: no cover - exotic callables
        return False
    return "workspace_id" in params


async def _gather_with_limit(coros, *, concurrency: int) -> list[Any]:
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _wrap(c):
        async with sem:
            return await c

    return await asyncio.gather(*(_wrap(c) for c in coros))


# --------------------------------------------------------------------------- #
# Hit -> dataset ref resolution
# --------------------------------------------------------------------------- #


def _resolve_refs(items: list[dict[str, Any]], *, id_to_ref: dict[str, str]) -> list[str]:
    """Map returned hits back to dataset ``memory_ref``s, preserving rank order.

    A hit may carry ``memory_ref`` directly (test doubles, or a future backend
    echo) or a backend ``id`` that the ingest corpus map resolves. An
    unresolvable hit keeps a synthetic ``unknown:<id>`` ref so it still occupies
    a slot and counts as noise, rather than silently vanishing from the
    denominator and flattering precision.
    """

    refs: list[str] = []
    for rank, item in enumerate(items, start=1):
        ref = item.get("memory_ref")
        if not ref:
            raw_id = item.get("id")
            ref = id_to_ref.get(str(raw_id)) if raw_id is not None else None
        if not ref:
            ref = f"unknown:{item.get('id', f'rank{rank}')}"
        refs.append(str(ref))
    return refs


def _id_to_ref_map(ctx: Any) -> dict[str, str]:
    """Invert the ingest ``memory_ref -> memory_id`` ledger into ``id -> ref``."""

    if not hasattr(ctx, "maps_dir"):
        return {}
    from .ingest import load_corpus_map  # noqa: PLC0415  (avoids import cycle at module load)

    try:
        ref_to_id = load_corpus_map(ctx.maps_dir())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read the memory-recall corpus map: %s", exc)
        return {}
    return {str(memory_id): ref for ref, memory_id in ref_to_id.items()}


class MemoryRecallBenchmark:
    suite: str = "memory"
    name: str = "recall"
    headline: bool = False
    description: str = _DESCRIPTION

    def add_run_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--n", dest="sample_n", type=int, default=None)
        parser.add_argument(
            "--top-k",
            dest="top_k",
            type=int,
            default=MAX_TOP_K,
            help=f"Hits to score per query (clamped to <= {MAX_TOP_K}, RS-2).",
        )
        parser.add_argument(
            "--min-similarity",
            dest="min_similarity",
            type=float,
            default=DEFAULT_MIN_SIMILARITY,
            help="Recall-hit similarity floor; ignored when the backend exposes no score.",
        )
        parser.add_argument("--concurrency", type=int, default=4)

    async def ingest(self, ctx: RunContext, **opts: Any) -> None:
        from .ingest import run_ingest  # noqa: PLC0415

        await run_ingest(ctx, workspace_id=opts.get("workspace_id"))

    async def run(self, ctx: RunContext, **opts: Any) -> RunArtifact:
        top_k = clamp_top_k(opts.get("top_k", MAX_TOP_K))
        raw_min_sim = opts.get("min_similarity")
        min_similarity = DEFAULT_MIN_SIMILARITY if raw_min_sim is None else float(raw_min_sim)
        sample_n = opts.get("sample_n")
        concurrency = int(opts.get("concurrency") or 4)

        dataset = _load_dataset()
        queries = list(dataset.queries)
        if sample_n is not None and sample_n > 0:
            queries = queries[:sample_n]
        if not queries:
            raise RuntimeError("Memory-recall dataset produced 0 queries.")

        workspace_id = getattr(ctx, "search_space_id", None)
        id_to_ref = _id_to_ref_map(ctx)
        client = _build_memories_client(ctx)
        scoped = _search_accepts_workspace(client) and workspace_id is not None

        async def _one(query) -> list[dict[str, Any]]:
            if scoped:
                return await client.search(
                    workspace_id=workspace_id, query=query.query, top_k=top_k
                )
            return await client.search(query.query, top_k=top_k)

        responses: list[list[dict[str, Any]]] = await _gather_with_limit(
            (_one(q) for q in queries), concurrency=concurrency
        )

        per_query_retrieved: dict[str, list[str]] = {}
        per_query_qrels: dict[str, dict[str, float]] = {}
        raw_rows: list[dict[str, Any]] = []
        similarity_enforced_any = False

        for query, items in zip(queries, responses, strict=False):
            # AC-3: the oracle decides which returned hits count at all, before
            # relevance is considered. Anything it rejects (past top_k, or below
            # the similarity floor when a real score exists) leaves the scored
            # list entirely.
            kept, enforced = classify_results(items, top_k=top_k, min_similarity=min_similarity)
            similarity_enforced_any = similarity_enforced_any or enforced
            scored_refs = _resolve_refs(kept, id_to_ref=id_to_ref)
            all_refs = _resolve_refs(list(items), id_to_ref=id_to_ref)
            relevant = set(query.relevant_refs)

            per_query_retrieved[query.query_id] = scored_refs
            per_query_qrels[query.query_id] = {
                ref: float(grade) for ref, grade in query.qrels.items()
            }
            raw_rows.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "type": query.type,
                    "tags": query.tags,
                    "returned_refs": all_refs,
                    "scored_refs": scored_refs,
                    "relevant_refs": sorted(relevant),
                    "distractors": query.distractors,
                    "hits": [ref for ref in scored_refs if ref in relevant],
                    "noise": [ref for ref in scored_refs if ref not in relevant],
                    "similarity_enforced": enforced,
                }
            )

        scores = score_run(
            per_query_retrieved=per_query_retrieved,
            per_query_qrels=per_query_qrels,
            ks=(1, 5),
            ndcg_k=10,
        )

        metrics = scores.to_dict()
        # §6.2: the config that produced these numbers travels with them, so the
        # gate can confirm it is reading a run scored the way it expects.
        metrics["top_k"] = top_k
        metrics["min_similarity"] = min_similarity

        run_timestamp = utc_iso_timestamp()
        run_dir = ctx.runs_dir(run_timestamp=run_timestamp)
        raw_path = run_dir / "raw.jsonl"
        with raw_path.open("w", encoding="utf-8") as fh:
            for row in raw_rows:
                fh.write(json.dumps(row) + "\n")

        artifact = RunArtifact(
            suite=self.suite,
            benchmark=self.name,
            run_timestamp=run_timestamp,
            raw_path=raw_path,
            metrics=metrics,
            extra={
                "n_queries": len(queries),
                "top_k": top_k,
                "min_similarity": min_similarity,
                # Records whether the similarity floor was actually applied: the
                # backend currently returns score=0.0 for every hit, so a run can
                # legitimately be rank-only. Without this the artifact would imply
                # a threshold that never fired.
                "similarity_enforced": similarity_enforced_any,
                "concurrency": concurrency,
                "corpus_map_entries": len(id_to_ref),
                "dataset_queries": len(dataset.queries),
                "dataset_corpus": len(dataset.corpus),
            },
        )
        manifest_path = run_dir / "run_artifact.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "suite": self.suite,
                    "benchmark": self.name,
                    "raw_path": "raw.jsonl",
                    "metrics": metrics,
                    "extra": artifact.extra,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return artifact

    def report_section(self, artifacts: list[RunArtifact]) -> ReportSection:
        title = "Memory recall — precision@5 / noise rate"
        if not artifacts:
            return ReportSection(
                title=title,
                headline=False,
                body_md="(no run artifacts found)",
                body_json={},
            )
        latest = max(artifacts, key=lambda a: a.run_timestamp)
        m = latest.metrics
        precision = m.get("precision_at_k", {}) or {}
        recall = m.get("recall_at_k", {}) or {}

        def _at(mapping: dict, k: int) -> float | None:
            value = mapping.get(str(k), mapping.get(k))
            return None if value is None else float(value)

        lines = [f"- n_queries: {m.get('n_queries', 0)}"]
        p5 = _at(precision, 5)
        ci = m.get("precision_at_5_ci") or [None, None]
        if p5 is not None:
            if ci[0] is not None and ci[1] is not None:
                lines.append(
                    f"- Precision@5: {p5:.3f} (Wilson 95% CI {float(ci[0]):.3f}–{float(ci[1]):.3f})"
                )
            else:
                lines.append(f"- Precision@5: {p5:.3f}")
        p1 = _at(precision, 1)
        if p1 is not None:
            lines.append(f"- Precision@1: {p1:.3f}")
        lines.append(f"- Noise rate: {float(m.get('noise_rate', 0.0)):.3f}")
        for k in (1, 5):
            v = _at(recall, k)
            if v is not None:
                lines.append(f"- Recall@{k}: {v:.3f}")
        lines.append(f"- MRR: {float(m.get('mrr', 0.0)):.3f}")
        lines.append(f"- nDCG@10: {float(m.get('ndcg_at_10', 0.0)):.3f}")
        lines.append(
            f"- Scored with top_k={m.get('top_k', '?')}, "
            f"min_similarity={m.get('min_similarity', '?')}"
        )
        if latest.extra.get("similarity_enforced") is False:
            lines.append(
                "- Note: similarity floor not applied (backend exposed no usable "
                "score); classification was rank-only."
            )
        return ReportSection(
            title=title,
            headline=False,
            body_md="\n".join(lines),
            body_json=m,
        )


__all__ = ["MemoryRecallBenchmark"]
