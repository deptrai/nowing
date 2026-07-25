"""Idempotently seed the labeled memory-recall corpus into one workspace.

Three properties this module has to hold, all of them learned the hard way in
the Story 3.9 review:

**Progress survives failure.** Writing the id map only after the whole loop
succeeds means one 5xx halfway through leaves already-created memories in the
workspace with no recorded id. The next "idempotent" ingest then cannot see
them and creates duplicates, which pollute the top-5 of every later search.
The map is therefore persisted incrementally.

**The map is per workspace.** A single per-suite path means pointing the suite
at a second workspace destroys the first workspace's ``memory_ref -> id``
record, permanently orphaning those rows.

**Labels and workspace cannot drift apart.** Each row records a content hash, so
editing a fixture's text after it was ingested is detected instead of silently
scoring against text that is no longer in the workspace.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ....core.config import set_suite_state
from ....core.registry import RunContext
from .dataset import load_dataset

CORPUS_MAP_FILENAME = "memory_recall_corpus_map.jsonl"

#: Reserved tag stamped on every seeded memory. The backend's
#: ``MemorySourceType`` enum has no "eval" member (document / chat_message /
#: scraper_run / manual / unknown), so a tag is the only way to tell eval
#: fixtures apart from user-authored memories — and the only way ``purge`` can
#: find them again.
EVAL_TAG = "nowing-eval:memory-recall"


def resolve_workspace_id(ctx: RunContext, workspace_id: int | None = None) -> int:
    """Resolve an explicit CLI override or the configured memory workspace.

    A memory workspace is a product tenant and must never be inferred from the
    harness's unrelated ``search_space_id``.
    """

    resolved = workspace_id if workspace_id is not None else ctx.config.memory_workspace_id
    if isinstance(resolved, bool) or not isinstance(resolved, int) or resolved <= 0:
        raise RuntimeError(
            "Memory recall requires a positive workspace id. Set "
            "NOWING_EVAL_WORKSPACE_ID or pass --workspace-id."
        )
    return resolved


def content_fingerprint(content: str) -> str:
    """Stable hash of a fixture's text, recorded so label drift is detectable."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def corpus_map_path(maps_dir: Path, *, workspace_id: int) -> Path:
    """Return the workspace-scoped idempotency-map path for the recall corpus."""

    stem, _, suffix = CORPUS_MAP_FILENAME.rpartition(".")
    return maps_dir / f"{stem}.w{workspace_id}.{suffix}"


def load_corpus_map(
    path: Path,
    *,
    workspace_id: int,
    corpus: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, int]:
    """Load a validated ``memory_ref -> backend memory_id`` map for one tenant.

    When ``corpus`` is supplied, each row's recorded content hash is compared
    against the current fixture text so a silently edited label is rejected
    rather than scored against stale workspace content.
    """

    if not path.is_file():
        return {}

    mapping: dict[str, int] = {}
    seen_ids: dict[int, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                memory_ref = row["memory_ref"]
                memory_id = row["memory_id"]
                row_workspace_id = row["workspace_id"]
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"Invalid memory corpus map row at {path}:{line_number}"
                ) from exc
            if (
                not isinstance(memory_ref, str)
                or not memory_ref
                or isinstance(memory_id, bool)
                or not isinstance(memory_id, int)
                or memory_id <= 0
                or isinstance(row_workspace_id, bool)
                or not isinstance(row_workspace_id, int)
            ):
                raise RuntimeError(f"Invalid memory corpus map row at {path}:{line_number}")
            if row_workspace_id != workspace_id:
                raise RuntimeError(
                    f"Memory corpus map {path} belongs to workspace {row_workspace_id}, "
                    f"not requested workspace {workspace_id}. The map path is "
                    "workspace-scoped, so this indicates a hand-edited or moved file."
                )
            if memory_ref in mapping:
                raise RuntimeError(f"Duplicate memory_ref {memory_ref!r} in corpus map {path}")
            if memory_id in seen_ids:
                # Two refs pointing at one backend row means the runner's
                # id -> ref inversion would silently drop one of them, and every
                # query whose relevant ref lost could never register a hit.
                raise RuntimeError(
                    f"Corpus map {path} maps memory_id {memory_id} to both "
                    f"{seen_ids[memory_id]!r} and {memory_ref!r}; ids must be unique"
                )
            if corpus is not None:
                entry = corpus.get(memory_ref)
                if entry is None:
                    raise RuntimeError(
                        f"Corpus map {path}:{line_number} references {memory_ref!r}, which is "
                        "not in the current dataset. Purge and re-ingest."
                    )
                recorded = row.get("content_sha256")
                expected = content_fingerprint(str(entry["content"]))
                if recorded is not None and recorded != expected:
                    raise RuntimeError(
                        f"Fixture {memory_ref!r} changed since it was ingested "
                        f"(map {path}:{line_number}). The workspace still holds the old "
                        "text, so scoring would be against stale content. Purge and "
                        "re-ingest this workspace."
                    )
            seen_ids[memory_id] = memory_ref
            mapping[memory_ref] = memory_id
    return mapping


def _map_row(
    memory_ref: str,
    memory_id: int,
    *,
    workspace_id: int,
    content: str | None,
) -> str:
    row: dict[str, Any] = {
        "memory_ref": memory_ref,
        "memory_id": memory_id,
        "workspace_id": workspace_id,
    }
    if content is not None:
        row["content_sha256"] = content_fingerprint(content)
    return json.dumps(row, sort_keys=True)


def _write_corpus_map(
    path: Path,
    mapping: Mapping[str, int],
    *,
    workspace_id: int,
    corpus: Mapping[str, Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp name: a fixed ``.tmp`` sibling lets two concurrent ingests
    # clobber each other's half-written file before either renames it.
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        for memory_ref, memory_id in sorted(mapping.items()):
            entry = corpus.get(memory_ref)
            handle.write(
                _map_row(
                    memory_ref,
                    memory_id,
                    workspace_id=workspace_id,
                    # A ref no longer present in the dataset (mid-purge of a
                    # stale map) keeps its id row but carries no hash.
                    content=None if entry is None else str(entry["content"]),
                )
                + "\n"
            )
    temp_path.replace(path)


def _created_memory_id(response: Mapping[str, Any], *, memory_ref: str) -> int:
    memory_id = response.get("id")
    if isinstance(memory_id, bool) or not isinstance(memory_id, int) or memory_id <= 0:
        raise RuntimeError(
            f"Memory create response for {memory_ref!r} did not contain a positive integer id: "
            f"{response!r}"
        )
    return memory_id


def _eval_tags(tags: Any) -> list[str]:
    existing = [str(tag) for tag in (tags or [])]
    return existing if EVAL_TAG in existing else [*existing, EVAL_TAG]


async def run_ingest(ctx: RunContext, *, workspace_id: int | None = None) -> Path:
    """Seed only unmapped labeled memories and persist their workspace-scoped ids."""

    resolved_workspace_id = resolve_workspace_id(ctx, workspace_id)
    dataset = load_dataset()
    map_path = corpus_map_path(ctx.maps_dir(), workspace_id=resolved_workspace_id)
    memory_ids = load_corpus_map(
        map_path, workspace_id=resolved_workspace_id, corpus=dataset.corpus
    )
    client = ctx.memories_client()

    def persist() -> None:
        _write_corpus_map(
            map_path,
            memory_ids,
            workspace_id=resolved_workspace_id,
            corpus=dataset.corpus,
        )

    try:
        for memory_ref, memory in dataset.corpus.items():
            if memory_ref in memory_ids:
                continue
            response = await client.create(
                resolved_workspace_id,
                memory["content"],
                type_=memory["type"],
                tags=_eval_tags(memory.get("tags")),
            )
            memory_ids[memory_ref] = _created_memory_id(response, memory_ref=memory_ref)
            # Persist as we go: an interrupted ingest must leave a map that
            # accounts for everything already created in the workspace.
            persist()
    finally:
        persist()

    ctx.suite_state.ingestion_maps["memory_recall"] = str(map_path)
    set_suite_state(ctx.config, ctx.suite, ctx.suite_state)
    return map_path


async def run_purge(ctx: RunContext, *, workspace_id: int | None = None) -> int:
    """Delete every memory this suite seeded into ``workspace_id``.

    Without this, a mistyped workspace id permanently contaminates a real tenant
    with fixture memories that are indistinguishable from user-authored ones
    (``teardown`` only removes the harness's SearchSpace). Returns the number of
    memories deleted.
    """

    resolved_workspace_id = resolve_workspace_id(ctx, workspace_id)
    map_path = corpus_map_path(ctx.maps_dir(), workspace_id=resolved_workspace_id)
    memory_ids = load_corpus_map(map_path, workspace_id=resolved_workspace_id)
    if not memory_ids:
        return 0

    dataset = load_dataset()
    client = ctx.memories_client()
    deleted = 0
    try:
        for memory_ref, memory_id in sorted(memory_ids.items()):
            await client.delete(memory_id)
            deleted += 1
            memory_ids.pop(memory_ref, None)
    finally:
        if memory_ids:
            _write_corpus_map(
                map_path,
                memory_ids,
                workspace_id=resolved_workspace_id,
                corpus=dataset.corpus,
            )
        elif map_path.exists():
            map_path.unlink()
    return deleted


__all__ = [
    "CORPUS_MAP_FILENAME",
    "EVAL_TAG",
    "content_fingerprint",
    "corpus_map_path",
    "load_corpus_map",
    "resolve_workspace_id",
    "run_ingest",
    "run_purge",
]
