"""Seed the labeled recall corpus into a workspace (Story 3.9, Step 5).

Mirrors ``suites/medical/cure/ingest.py``: create the corpus rows through the
real API, then persist a ``memory_ref -> memory_id`` map under
``data/memory/maps/`` so the runner can resolve search hits (which come back as
integer ids) into dataset refs.

Idempotency matters here in a way it does not for CUREv1. The memory API has no
"skip duplicate" behaviour of its own — ``POST /memories`` always creates a new
row — so re-running ingest naively would duplicate all 46 corpus memories into
the workspace. A duplicated corpus does not just waste rows: two identical
memories compete for the same top-5 slots, which depresses precision@5 and
inflates noise for reasons that have nothing to do with retrieval quality. So
the map is the idempotency ledger: a ref already present in it is not re-created.

Ingest is deliberately sequential. The corpus is small (tens of rows), each
create triggers a synchronous embedding call server-side, and a burst of
concurrent writes against the auto-extract path is exactly the kind of load this
gate is not trying to measure.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ....core.registry import RunContext
from .dataset import load_dataset

logger = logging.getLogger(__name__)

_MAP_FILENAME = "memory_recall_corpus_map.jsonl"


def corpus_map_path(ctx: RunContext) -> Path:
    return ctx.maps_dir() / _MAP_FILENAME


def load_corpus_map(maps_dir: Path) -> dict[str, int]:
    """Read ``memory_ref -> memory_id``. Missing/corrupt rows are skipped.

    A malformed line is skipped rather than fatal: the map is a cache we can
    rebuild, and one bad row should not block a run that can still resolve the
    rest. The runner separately fails loudly if the map is empty.
    """

    path = maps_dir / _MAP_FILENAME
    out: dict[str, int] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                out[str(row["memory_ref"])] = int(row["memory_id"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
    return out


async def run_ingest(
    ctx: RunContext,
    *,
    workspace_id: int | None = None,
    queries_path: Path | str | None = None,
    corpus_path: Path | str | None = None,
) -> dict[str, int]:
    """Seed every corpus memory not already mapped; return the full map.

    ``workspace_id`` defaults to the suite's pinned search space id (the evals
    harness pins one id per suite at setup time and workspaces and search spaces
    share an id space in this deployment).
    """

    ws_id = workspace_id if workspace_id is not None else ctx.search_space_id
    dataset = load_dataset(queries_path=queries_path, corpus_path=corpus_path)

    maps_dir = ctx.maps_dir()
    existing = load_corpus_map(maps_dir)
    todo = [ref for ref in dataset.corpus if ref not in existing]

    if not todo:
        logger.info(
            "Memory recall corpus already seeded (%d refs mapped); nothing to do",
            len(existing),
        )
        return existing

    logger.info(
        "Seeding %d/%d memory-recall corpus rows into workspace %d",
        len(todo),
        len(dataset.corpus),
        ws_id,
    )

    client = ctx.memories_client()
    created: dict[str, int] = {}
    for ref in todo:
        memory: dict[str, Any] = dataset.corpus[ref]
        row = await client.create(
            workspace_id=ws_id,
            content=memory["content"],
            type_=memory.get("type", "semantic"),
            tags=list(memory.get("tags") or []),
            # Corpus rows are hand-labeled ground truth, not model output.
            source_type="manual",
            confidence=1.0,
        )
        memory_id = row.get("id")
        if memory_id is None:
            raise RuntimeError(f"POST /memories returned no id for ref {ref!r}: {row!r}")
        created[ref] = int(memory_id)

    # Append-only: never rewrite the file, so a crash mid-ingest leaves the
    # already-created ids mapped and the next run resumes instead of duplicating.
    with (maps_dir / _MAP_FILENAME).open("a", encoding="utf-8") as fh:
        for ref, memory_id in created.items():
            fh.write(json.dumps({"memory_ref": ref, "memory_id": memory_id}) + "\n")

    merged = {**existing, **created}
    logger.info("Seeded %d new memories; %d refs mapped total", len(created), len(merged))
    return merged


__all__ = ["corpus_map_path", "load_corpus_map", "run_ingest"]
