"""Acceptance tests for Story 3.9's registered memory-recall suite."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nowing_evals.core.registry import RunArtifact
from nowing_evals.suites.memory.recall import MemoryRecallBenchmark
from nowing_evals.suites.memory.recall.dataset import Dataset, Query
from nowing_evals.suites.memory.recall.ingest import content_fingerprint
from nowing_evals.suites.memory.recall.oracle import (
    ORACLE_MODE_RANK_ONLY,
    ORACLE_MODE_SCORE_THRESHOLD,
    is_recall_hit,
    judge_returned_items,
    resolve_oracle_mode,
)


def _is_file_sync(path: Path) -> bool:
    return path.is_file()


def _sha256_file_sync(path: Path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


_UV_LOCK_PATH = next(
    (p / "uv.lock" for p in Path(__file__).resolve().parents if _is_file_sync(p / "uv.lock")),
    Path(__file__).resolve().parents[3] / "uv.lock",
)
_UV_LOCK_HASH = _sha256_file_sync(_UV_LOCK_PATH) if _is_file_sync(_UV_LOCK_PATH) else None

# --------------------------------------------------------------------------- #
# AC-1 — registration + CLI discovery
# --------------------------------------------------------------------------- #


def test_suite_registered_after_discovery():
    """AC-1: auto-discovery registers benchmark ('memory', 'recall')."""
    from nowing_evals.core import registry
    from nowing_evals.suites import discover_suites

    discover_suites()
    assert ("memory", "recall") in dict(registry.snapshot())


def test_benchmark_identity_fields():
    """AC-1: benchmark exposes the protocol fields the registry/CLI rely on."""
    bench = MemoryRecallBenchmark()
    assert bench.suite == "memory"
    assert bench.name == "recall"
    assert isinstance(bench.description, str) and bench.description


def test_suite_listed_in_registry_suites():
    """AC-1: 'memory' shows up in the registry's suite list => CLI `suites list`."""
    from nowing_evals.core import registry
    from nowing_evals.suites import discover_suites

    discover_suites()
    assert "memory" in registry.list_suites()


def test_benchmark_declares_its_own_gate_config():
    """``core.gate`` must not hardcode a path into one leaf suite."""
    path = MemoryRecallBenchmark().gate_config_path()
    assert path.is_file()
    assert path.name == "gate.yaml"


def test_benchmark_does_not_require_searchspace_setup():
    """Memory endpoints are workspace-scoped and touch no SearchSpace/chat model.

    Requiring `setup` would force this suite to provision an unrelated
    SearchSpace and pin an OpenRouter model it never calls, undoing the
    decoupling ``Config.memory_workspace_id`` exists to express.
    """
    assert MemoryRecallBenchmark().requires_suite_setup is False


# --------------------------------------------------------------------------- #
# AC-3 — recall-hit oracle (RS-2: top_k <= 5)
# --------------------------------------------------------------------------- #


def test_recall_hit_within_top_k_and_above_threshold():
    """AC-3: an item in top_k with score >= min_similarity is a hit."""
    item = {"id": 1, "score": 0.9}
    assert (
        is_recall_hit(item, rank=1, top_k=5, mode=ORACLE_MODE_SCORE_THRESHOLD, min_similarity=0.3)
        is True
    )


def test_recall_hit_beyond_top_k_is_noise():
    """AC-3: an item ranked past top_k is never a hit (RS-2 clamps to <= 5)."""
    item = {"id": 1, "score": 0.99}
    assert (
        is_recall_hit(item, rank=6, top_k=5, mode=ORACLE_MODE_SCORE_THRESHOLD, min_similarity=0.3)
        is False
    )


def test_recall_hit_below_similarity_threshold_is_noise():
    """AC-3: an item below the similarity threshold is noise even if top-ranked."""
    item = {"id": 1, "score": 0.1}
    assert (
        is_recall_hit(item, rank=1, top_k=5, mode=ORACLE_MODE_SCORE_THRESHOLD, min_similarity=0.3)
        is False
    )


def test_score_threshold_mode_does_not_accept_a_missing_score():
    """Fail-closed: an unusable score under score_threshold is not a hit.

    Accepting it would silently defeat the threshold for exactly the items whose
    similarity could not be established.
    """
    assert (
        is_recall_hit(
            {"id": 1}, rank=1, top_k=5, mode=ORACLE_MODE_SCORE_THRESHOLD, min_similarity=0.3
        )
        is False
    )


def test_rank_only_mode_judges_on_position():
    """AC-3/§9: with no usable score signal the oracle degrades to top_k membership."""
    assert is_recall_hit({"id": 1}, rank=3, top_k=5, mode=ORACLE_MODE_RANK_ONLY) is True
    assert is_recall_hit({"id": 1}, rank=6, top_k=5, mode=ORACLE_MODE_RANK_ONLY) is False


def test_constant_scores_resolve_to_rank_only_for_the_whole_run():
    """DEC-3: the backend serialises score=0.0 for every hit.

    That carries no ordering information, so the run degrades to rank-only —
    decided once, run-level, and recorded. Deciding per query would blend two
    metric definitions inside one aggregate.
    """
    assert resolve_oracle_mode([{"score": 0.0}, {"score": 0.0}]) == ORACLE_MODE_RANK_ONLY
    assert resolve_oracle_mode([{"score": 0.7}, {"score": 0.7}]) == ORACLE_MODE_RANK_ONLY
    assert resolve_oracle_mode([]) == ORACLE_MODE_RANK_ONLY
    assert resolve_oracle_mode([{"score": 0.9}, {"score": 0.2}]) == ORACLE_MODE_SCORE_THRESHOLD


def test_all_zero_scores_are_never_treated_as_all_hits():
    """The safety direction must not invert.

    If real scores ever arrive and every one is below the floor, that means
    "nothing matched well" — it must not be read as "everything is a hit".
    """
    items = [{"id": 1, "score": 0.0}, {"id": 2, "score": 0.0}]
    mode = resolve_oracle_mode(items)
    judged = judge_returned_items(
        items, top_k=5, mode=mode, min_similarity=None, resolve_ref=lambda _i: None
    )
    # Every slot is still judged and counted, and none is credited as relevant.
    assert len(judged) == 2
    assert all(row["off_corpus"] for row in judged)


def test_judge_returned_items_keeps_every_slot_in_the_denominator():
    """AC-3: 'everything else in the returned set is noise'.

    Dropping non-hits shrinks the precision/noise denominator and drives both
    toward a perfect score, which is the failure the gate exists to catch.
    """
    items = [
        {"id": 101, "score": 0.9},  # hit
        {"id": 102, "score": 0.1},  # below threshold
        {"id": 999, "score": 0.9},  # off corpus
        {"id": 101, "score": 0.8},  # duplicate of the first
    ]
    refs = {101: "m1", 102: "d1"}
    judged = judge_returned_items(
        items,
        top_k=5,
        mode=ORACLE_MODE_SCORE_THRESHOLD,
        min_similarity=0.3,
        resolve_ref=lambda item: refs.get(item["id"]),
    )
    assert len(judged) == 4, "every returned slot must remain in the scored set"
    scored = [row["scored_ref"] for row in judged]
    assert scored[0] == "m1"
    assert scored[1].startswith("__below_threshold__")
    assert scored[2].startswith("__off_corpus__")
    assert scored[3].startswith("__duplicate__")
    assert len(set(scored)) == 4, "placeholders must be distinct so they cannot match labels"


# --------------------------------------------------------------------------- #
# AC-5 — RunArtifact + report_section
# --------------------------------------------------------------------------- #


def test_report_section_renders_gated_and_diagnostic_metrics():
    """AC-5: report_section surfaces the ship-gated metrics and the diagnostics."""
    artifact = RunArtifact(
        suite="memory",
        benchmark="recall",
        run_timestamp="2026-07-25T00-00-00Z",
        raw_path=Path("raw.jsonl"),
        metrics={
            "precision_at_k": {"1": 0.9, "5": 0.2},
            "precision_at_primary_k_micro": 0.2,
            "precision_at_5_ci": [0.11, 0.34],
            "noise_rate": 0.8,
            "distractor_noise_rate": 0.05,
            "off_corpus_rate": 0.0,
            "off_corpus_measured": True,
            "recall_at_k": {"5": 0.95},
            "mrr": 0.88,
            "ndcg_at_10": 0.77,
            "ndcg_k": 5,
            "primary_k": 5,
            "n_queries": 36,
            "n_failed_queries": 0,
            "top_k": 5,
            "oracle_mode": "rank_only",
        },
    )
    body = MemoryRecallBenchmark().report_section([artifact]).body_md.lower()
    assert "recall@5" in body
    assert "mrr" in body
    assert "distractor noise" in body
    assert "off-corpus" in body
    assert "precision@5" in body


@pytest.mark.parametrize(
    "metrics",
    [
        {"precision_at_5_ci": None},
        {"precision_at_5_ci": [0.7]},
        {"precision_at_5_ci": "0.8"},
        {"precision_at_k": [0.9, 0.8]},
        {"precision_at_k": {"5": {}}},
        {"n_queries": "many", "mrr": None, "noise_rate": None},
    ],
)
def test_report_section_survives_malformed_metrics(metrics):
    """A present-but-malformed value must not abort the whole suite's report.

    ``dict.get(key, default)`` only guards a *missing* key, so ``null`` or a
    one-element CI used to raise mid-render.
    """
    artifact = RunArtifact(
        suite="memory",
        benchmark="recall",
        run_timestamp="2026-07-25T00-00-00Z",
        raw_path=Path("raw.jsonl"),
        metrics={"n_queries": 3, **metrics},
    )
    section = MemoryRecallBenchmark().report_section([artifact])
    assert section.body_md


def test_report_section_distinguishes_missing_from_zero():
    """A missing precision must not render as a measured 0.000."""
    artifact = RunArtifact(
        suite="memory",
        benchmark="recall",
        run_timestamp="2026-07-25T00-00-00Z",
        raw_path=Path("raw.jsonl"),
        metrics={"n_queries": 3},
    )
    body = MemoryRecallBenchmark().report_section([artifact]).body_md
    assert "not measured" in body


# --------------------------------------------------------------------------- #
# AC-5 — the runner end to end (hermetic)
# --------------------------------------------------------------------------- #


def _fake_dataset() -> Dataset:
    return Dataset(
        queries=[
            Query(
                query_id="q1",
                query="where do I keep my passport",
                qrels={"m1": 2},
                distractors=["d1"],
                type="factual",
                tags=["personal"],
            )
        ],
        corpus={
            "m1": {"content": "passport is in the desk drawer", "type": "semantic", "tags": []},
            "d1": {"content": "unrelated note", "type": "semantic", "tags": []},
        },
    )


class _FakeConfig:
    memory_workspace_id = 42


def _fake_ctx(tmp_path: Path, dataset: Dataset, client, *, map_rows=None):
    rows = (
        map_rows
        if map_rows is not None
        else [
            {"memory_ref": "m1", "memory_id": 101, "workspace_id": 42},
            {"memory_ref": "d1", "memory_id": 102, "workspace_id": 42},
        ]
    )
    for row in rows:
        entry = dataset.corpus.get(row["memory_ref"])
        if entry is not None:
            row.setdefault("content_sha256", content_fingerprint(entry["content"]))

    class FakeRunContext:
        suite = "memory"
        benchmark = "recall"
        config = _FakeConfig()

        def memories_client(self):
            return client

        def maps_dir(self):
            path = tmp_path / "maps"
            path.mkdir(parents=True, exist_ok=True)
            (path / "memory_recall_corpus_map.w42.jsonl").write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            return path

        def runs_dir(self, *, run_timestamp: str):
            path = tmp_path / run_timestamp / "recall"
            path.mkdir(parents=True, exist_ok=True)
            return path

    return FakeRunContext()


async def test_run_persists_artifact_with_quality_metrics(tmp_path, monkeypatch):
    """AC-5: run scores ranked results and persists raw + manifest artifacts.

    The fake mirrors the workspace-scoped ``MemoriesClient.search`` contract, so
    this is a hermetic test of runner wiring rather than a live-server test.
    """
    dataset = _fake_dataset()

    class FakeMemoriesClient:
        async def search(self, workspace_id: int, query: str, *, top_k: int) -> list[dict]:
            assert workspace_id == 42
            assert query
            return [{"id": 101, "score": 0.0}, {"id": 102, "score": 0.0}][:top_k]

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )

    artifact = await MemoryRecallBenchmark().run(
        _fake_ctx(tmp_path, dataset, FakeMemoriesClient()),
        top_k=5,
        min_similarity=0.3,
        backend_build_id="test-build",
    )

    required = {
        "precision_at_k",
        "noise_rate",
        "distractor_noise_rate",
        "off_corpus_rate",
        "off_corpus_measured",
        "precision_at_5_ci",
        "precision_at_primary_k_micro",
        "recall_at_k",
        "mrr",
        "ndcg_at_10",
        "n_queries",
        "n_failed_queries",
        "primary_k",
        "top_k",
        "oracle_mode",
    }
    assert required <= artifact.metrics.keys()
    assert artifact.metrics["n_queries"] == 1
    assert artifact.metrics["top_k"] == 5
    assert artifact.metrics["oracle_mode"] == "rank_only"
    # Constant 0.0 scores mean the threshold was never applied — say so rather
    # than reporting a floor that had no effect.
    assert artifact.metrics["min_similarity"] is None
    assert artifact.metrics["requested_min_similarity"] == 0.3
    assert artifact.raw_path.is_file()
    assert artifact.raw_path.with_name("run_artifact.json").is_file()


async def test_run_scores_noise_over_the_full_returned_set(tmp_path, monkeypatch):
    """AC-3 regression guard — the review's headline finding.

    One relevant memory plus four labeled distractors used to score
    precision@5 = 1.0 / noise = 0.0, because the four non-hits were filtered out
    of the denominator before scoring.
    """
    dataset = Dataset(
        queries=[
            Query(
                query_id="q1",
                query="q",
                qrels={"m1": 2},
                distractors=["d1", "d2", "d3", "d4"],
                type="factual",
                tags=[],
            )
        ],
        corpus={
            ref: {"content": f"content {ref}", "type": "semantic", "tags": []}
            for ref in ("m1", "d1", "d2", "d3", "d4")
        },
    )

    class FakeMemoriesClient:
        async def search(self, workspace_id, query, *, top_k):
            return [
                {"id": 101, "score": 0.0},
                {"id": 102, "score": 0.0},
                {"id": 103, "score": 0.0},
                {"id": 104, "score": 0.0},
                {"id": 105, "score": 0.0},
            ][:top_k]

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )
    rows = [
        {"memory_ref": ref, "memory_id": 101 + i, "workspace_id": 42}
        for i, ref in enumerate(("m1", "d1", "d2", "d3", "d4"))
    ]

    artifact = await MemoryRecallBenchmark().run(
        _fake_ctx(tmp_path, dataset, FakeMemoriesClient(), map_rows=rows),
        top_k=5,
        backend_build_id="test-build",
    )
    metrics = artifact.metrics
    assert metrics["recall_at_k"]["5"] == pytest.approx(1.0), "the memory was found"
    assert metrics["precision_at_k"]["5"] == pytest.approx(0.2), "4 of 5 slots were noise"
    assert metrics["distractor_noise_rate"] == pytest.approx(0.8)
    assert metrics["off_corpus_rate"] == pytest.approx(0.0)


async def test_run_counts_unmappable_results_as_off_corpus(tmp_path, monkeypatch):
    """A polluted workspace must not score perfectly.

    Memories that resolve to no labeled ref used to be dropped from the scored
    list entirely, so foreign rows outranking the labeled one were invisible.
    """
    dataset = _fake_dataset()

    class FakeMemoriesClient:
        async def search(self, workspace_id, query, *, top_k):
            return [
                {"id": 901, "score": 0.0},
                {"id": 902, "score": 0.0},
                {"id": 903, "score": 0.0},
                {"id": 904, "score": 0.0},
                {"id": 101, "score": 0.0},
            ][:top_k]

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )
    artifact = await MemoryRecallBenchmark().run(
        _fake_ctx(tmp_path, dataset, FakeMemoriesClient()),
        top_k=5,
        backend_build_id="test-build",
    )
    assert artifact.metrics["off_corpus_rate"] == pytest.approx(0.8)
    assert artifact.metrics["off_corpus_measured"] is True


async def test_run_records_failed_queries_instead_of_aborting(tmp_path, monkeypatch):
    """One failing query must not destroy the whole run.

    ``asyncio.gather`` without ``return_exceptions`` propagates the first error
    without cancelling siblings, so no artifact is written and the surviving
    requests fire into a closing client.
    """
    dataset = Dataset(
        queries=[
            Query(query_id="q1", query="a", qrels={"m1": 2}, distractors=[], type="f", tags=[]),
            Query(query_id="q2", query="b", qrels={"m1": 2}, distractors=[], type="f", tags=[]),
        ],
        corpus={"m1": {"content": "c", "type": "semantic", "tags": []}},
    )

    class FlakyClient:
        def __init__(self):
            self.calls = 0

        async def search(self, workspace_id, query, *, top_k):
            self.calls += 1
            if query == "a":
                raise RuntimeError("boom")
            return [{"id": 101, "score": 0.0}]

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )
    rows = [{"memory_ref": "m1", "memory_id": 101, "workspace_id": 42}]
    artifact = await MemoryRecallBenchmark().run(
        _fake_ctx(tmp_path, dataset, FlakyClient(), map_rows=rows),
        top_k=5,
        backend_build_id="test-build",
    )
    assert artifact.metrics["n_failed_queries"] == 1
    assert artifact.metrics["n_queries"] == 1  # only the successful query was judged
    assert artifact.extra["failures"][0]["query_id"] == "q1"


async def test_run_refuses_a_partially_ingested_corpus(tmp_path, monkeypatch):
    """A map covering 1 of 2 memories must not run against unsatisfiable labels.

    Only checking for an *empty* map let a partial ingest score a fake quality
    collapse instead of reporting the real problem.
    """
    dataset = _fake_dataset()

    class FakeMemoriesClient:
        async def search(self, workspace_id, query, *, top_k):
            return []

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )
    rows = [{"memory_ref": "m1", "memory_id": 101, "workspace_id": 42}]
    with pytest.raises(RuntimeError, match="not fully ingested"):
        await MemoryRecallBenchmark().run(
            _fake_ctx(tmp_path, dataset, FakeMemoriesClient(), map_rows=rows),
            top_k=5,
            backend_build_id="test-build",
        )


async def test_run_rejects_invalid_min_similarity_before_calling_the_api(tmp_path, monkeypatch):
    """Validating per returned item costs a whole run before raising."""
    dataset = _fake_dataset()

    class ExplodingClient:
        async def search(self, *_a, **_kw):
            raise AssertionError("must not reach the network")

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )
    with pytest.raises(ValueError, match="min_similarity"):
        await MemoryRecallBenchmark().run(
            _fake_ctx(tmp_path, dataset, ExplodingClient()),
            top_k=5,
            min_similarity=5.0,
            backend_build_id="test-build",
        )


# --------------------------------------------------------------------------- #
# D10 — pre-auth backend_build_id gate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("backend_build_id", [None, "", "   ", 123])
def test_validate_run_options_rejects_missing_or_blank_build_id(backend_build_id):
    """The CLI's pre-auth hook and run()'s own defensive re-check share this."""
    with pytest.raises(ValueError, match="backend-build-id"):
        MemoryRecallBenchmark().validate_run_options(backend_build_id=backend_build_id)


def test_validate_run_options_accepts_nonblank_build_id():
    MemoryRecallBenchmark().validate_run_options(backend_build_id="sha-abc123")  # no raise


async def test_run_rejects_blank_build_id_before_touching_the_client(tmp_path, monkeypatch):
    """Runner-level defense (D10): even a direct ``run()`` call without going
    through the CLI must not reach the network without a build id."""
    dataset = _fake_dataset()

    class ExplodingClient:
        async def search(self, *_a, **_kw):
            raise AssertionError("must not reach the network")

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )
    with pytest.raises(ValueError, match="backend-build-id"):
        await MemoryRecallBenchmark().run(_fake_ctx(tmp_path, dataset, ExplodingClient()), top_k=5)


async def test_run_records_backend_build_id_in_artifact_extra(tmp_path, monkeypatch):
    """The artifact must name the exact backend build it evaluated (D10)."""
    dataset = _fake_dataset()

    class FakeMemoriesClient:
        async def search(self, workspace_id: int, query: str, *, top_k: int) -> list[dict]:
            return [{"id": 101, "score": 0.0}][:top_k]

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )

    artifact = await MemoryRecallBenchmark().run(
        _fake_ctx(tmp_path, dataset, FakeMemoriesClient()),
        top_k=5,
        backend_build_id="sha-abc123",
    )

    assert artifact.extra["backend_build_id"] == "sha-abc123"


async def test_run_provenance_hashes_uv_lock_and_counts_raw_rows(tmp_path, monkeypatch):
    """C2/C13: provenance records the uv.lock hash and exact raw row count."""
    dataset = _fake_dataset()

    class FakeMemoriesClient:
        async def search(self, workspace_id: int, query: str, *, top_k: int) -> list[dict]:
            return [{"id": 101, "score": 0.0}][:top_k]

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner.load_dataset", lambda **_kw: dataset
    )

    artifact = await MemoryRecallBenchmark().run(
        _fake_ctx(tmp_path, dataset, FakeMemoriesClient()),
        top_k=5,
        backend_build_id="sha-abc123",
    )

    provenance = artifact.extra["provenance"]
    if _UV_LOCK_HASH is not None:
        assert provenance["uv_lock_hash"] == _UV_LOCK_HASH
    assert provenance["raw_row_count"] == 1
    raw_path = artifact.raw_path
    assert _is_file_sync(raw_path)
    assert provenance["raw_hash"] == _sha256_file_sync(raw_path)


async def test_verify_backend_build_id_marks_git_fallback_unverified(monkeypatch):
    """C3: only a /health match sets verified=True; git fallback stays unverified."""
    import httpx

    from nowing_evals.suites.memory.recall.runner import (
        _verify_backend_build_id,
    )

    class _ExplodingResponse:
        def raise_for_status(self):
            raise RuntimeError("no health endpoint")

    async def _exploding_get(*_args, **_kwargs):
        return _ExplodingResponse()

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.runner._git_head_build_id",
        lambda: "sha-git-123",
    )

    client = httpx.AsyncClient()
    client.get = _exploding_get  # type: ignore[method-assign]

    ctx = type(
        "FakeRunContext",
        (),
        {
            "config": type("C", (), {"nowing_api_base": "http://test"})(),
            "http": client,
        },
    )()

    result = await _verify_backend_build_id(ctx, "sha-git-123")
    assert result["actual"] == "sha-git-123"
    assert result["source"] == "git_filesystem"
    assert result["verified"] is False
    await client.aclose()


async def test_verify_backend_build_id_marks_health_match_verified():
    """C3: a matching /health build_id sets verified=True."""
    import httpx

    from nowing_evals.suites.memory.recall.runner import _verify_backend_build_id

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"build_id": " sha-health-123 "}

    async def _fake_get(*_args, **_kwargs):
        return _FakeResponse()

    client = httpx.AsyncClient()
    client.get = _fake_get  # type: ignore[method-assign]

    ctx = type(
        "FakeRunContext",
        (),
        {
            "config": type("C", (), {"nowing_api_base": "http://test"})(),
            "http": client,
        },
    )()

    result = await _verify_backend_build_id(ctx, "sha-health-123")
    assert result["actual"] == "sha-health-123"
    assert result["source"] == "health_endpoint"
    assert result["verified"] is True
    await client.aclose()
