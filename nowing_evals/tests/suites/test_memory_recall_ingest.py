"""Ingest / purge tests for the memory-recall suite (AC-2, AC-5).

These cover the properties that make seeding a live tenant safe: progress
survives failure, the map is scoped per workspace, and label drift is detected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nowing_evals.suites.memory.recall import MemoryRecallBenchmark
from nowing_evals.suites.memory.recall.dataset import Dataset
from nowing_evals.suites.memory.recall.ingest import (
    EVAL_TAG,
    content_fingerprint,
    corpus_map_path,
    load_corpus_map,
    resolve_workspace_id,
    run_ingest,
    run_purge,
)


def _dataset(refs=("m1", "m2", "m3")) -> Dataset:
    return Dataset(
        queries=[],
        corpus={
            ref: {"content": f"content of {ref}", "type": "semantic", "tags": ["fixture"]}
            for ref in refs
        },
    )


class _FakeConfig:
    memory_workspace_id = 42


class _Ctx:
    suite = "memory"
    benchmark = "recall"

    def __init__(self, tmp_path: Path, client, *, workspace_id: int | None = 42):
        self._tmp = tmp_path
        self._client = client
        self.config = _FakeConfig()
        self.config.memory_workspace_id = workspace_id
        self.suite_state = type("S", (), {"ingestion_maps": {}})()

    def memories_client(self):
        return self._client

    def maps_dir(self) -> Path:
        path = self._tmp / "maps"
        path.mkdir(parents=True, exist_ok=True)
        return path


class RecordingClient:
    """Creates memories, optionally failing on the nth call."""

    def __init__(self, *, fail_on: int | None = None):
        self.created: list[dict] = []
        self.deleted: list[int] = []
        self._fail_on = fail_on

    async def create(self, workspace_id, content, *, type_="semantic", tags=None):
        if self._fail_on is not None and len(self.created) + 1 == self._fail_on:
            raise RuntimeError("backend exploded")
        memory_id = 100 + len(self.created)
        self.created.append(
            {
                "workspace_id": workspace_id,
                "content": content,
                "type": type_,
                "tags": list(tags or []),
            }
        )
        return {"id": memory_id}

    async def delete(self, memory_id):
        self.deleted.append(memory_id)


@pytest.fixture(autouse=True)
def _no_state_writes(monkeypatch):
    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.ingest.set_suite_state",
        lambda *_a, **_kw: None,
    )


def _patch_dataset(monkeypatch, dataset: Dataset) -> None:
    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.ingest.load_dataset", lambda **_kw: dataset
    )


# --------------------------------------------------------------------------- #
# Workspace resolution
# --------------------------------------------------------------------------- #


def test_workspace_id_is_never_inferred(tmp_path):
    """A memory workspace is a product tenant, not the harness SearchSpace."""
    ctx = _Ctx(tmp_path, RecordingClient(), workspace_id=None)
    with pytest.raises(RuntimeError, match="workspace id"):
        resolve_workspace_id(ctx)


@pytest.mark.parametrize("bad", [0, -1, True, "7"])
def test_workspace_id_rejects_invalid_values(tmp_path, bad):
    ctx = _Ctx(tmp_path, RecordingClient(), workspace_id=None)
    with pytest.raises(RuntimeError):
        resolve_workspace_id(ctx, bad)


def test_map_path_is_scoped_per_workspace(tmp_path):
    """Pointing the suite at a second workspace must not destroy the first map.

    A single per-suite path meant following the "re-run ingest with the requested
    workspace" advice permanently orphaned the other workspace's rows.
    """
    a = corpus_map_path(tmp_path, workspace_id=42)
    b = corpus_map_path(tmp_path, workspace_id=43)
    assert a != b
    assert "42" in a.name and "43" in b.name


# --------------------------------------------------------------------------- #
# Ingest
# --------------------------------------------------------------------------- #


async def test_ingest_seeds_corpus_and_records_ids(tmp_path, monkeypatch):
    dataset = _dataset()
    _patch_dataset(monkeypatch, dataset)
    client = RecordingClient()
    ctx = _Ctx(tmp_path, client)

    map_path = await run_ingest(ctx)

    assert len(client.created) == 3
    mapping = load_corpus_map(map_path, workspace_id=42, corpus=dataset.corpus)
    assert set(mapping) == set(dataset.corpus)


async def test_benchmark_ingest_does_not_require_backend_build_id(tmp_path, monkeypatch):
    """D10's pre-auth gate is a ``run``-only requirement (AC-7): ingest seeds a
    tenant's fixtures and has no per-run backend to pin down, so it must stay
    callable through the benchmark's own ``ingest()`` with no build id at all."""
    dataset = _dataset()
    _patch_dataset(monkeypatch, dataset)
    client = RecordingClient()
    ctx = _Ctx(tmp_path, client)

    await MemoryRecallBenchmark().ingest(ctx)  # no backend_build_id, no raise

    assert len(client.created) == 3


async def test_ingest_stamps_the_reserved_eval_tag(tmp_path, monkeypatch):
    """Fixtures must be distinguishable from user-authored memories.

    The backend's ``MemorySourceType`` has no "eval" member, so a reserved tag is
    the only marker available — and the only way ``purge`` can find them again.
    """
    dataset = _dataset(("m1",))
    _patch_dataset(monkeypatch, dataset)
    client = RecordingClient()

    await run_ingest(_Ctx(tmp_path, client))

    assert EVAL_TAG in client.created[0]["tags"]


async def test_ingest_is_idempotent(tmp_path, monkeypatch):
    dataset = _dataset()
    _patch_dataset(monkeypatch, dataset)
    client = RecordingClient()
    ctx = _Ctx(tmp_path, client)

    await run_ingest(ctx)
    await run_ingest(ctx)

    assert len(client.created) == 3, "already-mapped memories must not be recreated"


async def test_partial_ingest_persists_progress(tmp_path, monkeypatch):
    """The headline ingest fix.

    Writing the map only after the whole loop succeeds meant a mid-loop failure
    left already-created memories unrecorded, so the next "idempotent" ingest
    recreated them — and the duplicates then polluted every later search.
    """
    dataset = _dataset(("m1", "m2", "m3"))
    _patch_dataset(monkeypatch, dataset)
    client = RecordingClient(fail_on=3)
    ctx = _Ctx(tmp_path, client)

    with pytest.raises(RuntimeError, match="exploded"):
        await run_ingest(ctx)

    map_path = corpus_map_path(ctx.maps_dir(), workspace_id=42)
    mapping = load_corpus_map(map_path, workspace_id=42, corpus=dataset.corpus)
    assert len(mapping) == 2, "the two successful creates must be recorded"

    # Resuming creates only what is genuinely missing — no duplicates.
    resumed = RecordingClient()
    await run_ingest(_Ctx(tmp_path, resumed))
    assert len(resumed.created) == 1


# --------------------------------------------------------------------------- #
# Map validation
# --------------------------------------------------------------------------- #


def _write_map(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


def test_map_rejects_duplicate_memory_ids(tmp_path):
    """Two refs sharing one backend id silently collapse in the runner's inversion.

    The query whose relevant ref lost the collision could then never register a
    hit, understating recall for a reason invisible in the metrics.
    """
    path = tmp_path / "map.jsonl"
    _write_map(
        path,
        [
            {"memory_ref": "m1", "memory_id": 101, "workspace_id": 42},
            {"memory_ref": "m2", "memory_id": 101, "workspace_id": 42},
        ],
    )
    with pytest.raises(RuntimeError, match="ids must be unique"):
        load_corpus_map(path, workspace_id=42)


def test_map_rejects_foreign_workspace(tmp_path):
    path = tmp_path / "map.jsonl"
    _write_map(path, [{"memory_ref": "m1", "memory_id": 101, "workspace_id": 99}])
    with pytest.raises(RuntimeError, match="belongs to workspace 99"):
        load_corpus_map(path, workspace_id=42)


def test_map_detects_fixture_content_drift(tmp_path):
    """Editing a fixture after ingest must not silently score against stale text."""
    dataset = _dataset(("m1",))
    path = tmp_path / "map.jsonl"
    _write_map(
        path,
        [
            {
                "memory_ref": "m1",
                "memory_id": 101,
                "workspace_id": 42,
                "content_sha256": content_fingerprint("something else entirely"),
            }
        ],
    )
    with pytest.raises(RuntimeError, match="changed since it was ingested"):
        load_corpus_map(path, workspace_id=42, corpus=dataset.corpus)


def test_map_accepts_matching_content_hash(tmp_path):
    dataset = _dataset(("m1",))
    path = tmp_path / "map.jsonl"
    _write_map(
        path,
        [
            {
                "memory_ref": "m1",
                "memory_id": 101,
                "workspace_id": 42,
                "content_sha256": content_fingerprint(dataset.corpus["m1"]["content"]),
            }
        ],
    )
    assert load_corpus_map(path, workspace_id=42, corpus=dataset.corpus) == {"m1": 101}


def test_map_rejects_ref_absent_from_the_dataset(tmp_path):
    dataset = _dataset(("m1",))
    path = tmp_path / "map.jsonl"
    _write_map(path, [{"memory_ref": "gone", "memory_id": 101, "workspace_id": 42}])
    with pytest.raises(RuntimeError, match="not in the current dataset"):
        load_corpus_map(path, workspace_id=42, corpus=dataset.corpus)


def test_missing_map_is_an_empty_map(tmp_path):
    assert load_corpus_map(tmp_path / "nope.jsonl", workspace_id=42) == {}


# --------------------------------------------------------------------------- #
# Purge
# --------------------------------------------------------------------------- #


async def test_purge_removes_seeded_memories_and_clears_the_map(tmp_path, monkeypatch):
    """A mistyped workspace id must be recoverable.

    ``teardown`` only deletes the harness SearchSpace, so without this the
    fixtures stay in the product tenant forever.
    """
    dataset = _dataset()
    _patch_dataset(monkeypatch, dataset)
    client = RecordingClient()
    ctx = _Ctx(tmp_path, client)
    await run_ingest(ctx)

    deleted = await run_purge(ctx)

    assert deleted == 3
    assert sorted(client.deleted) == [100, 101, 102]
    assert not corpus_map_path(ctx.maps_dir(), workspace_id=42).exists()


async def test_purge_without_a_map_is_a_no_op(tmp_path, monkeypatch):
    _patch_dataset(monkeypatch, _dataset())
    client = RecordingClient()
    assert await run_purge(_Ctx(tmp_path, client)) == 0
    assert client.deleted == []
