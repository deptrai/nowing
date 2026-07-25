"""ATDD red-phase scaffolds — Story 3.9 Memory Recall Eval-Gate.

Covers:
- AC-1: the ``memory/recall`` benchmark is registered and CLI-discoverable.
- AC-3: the "recall hit" oracle (within top_k <= 5 AND score >= threshold; RS-2).
- AC-5: a run persists a scored RunArtifact and ``report_section`` renders it.

RED PHASE: skipped tests; imports of not-yet-existing suite code live inside test
bodies so collection stays clean (only skips, 0 errors).
"""

from __future__ import annotations

from pathlib import Path

from nowing_evals.core.registry import RunArtifact

RED = "ATDD red-phase (Story 3.9): memory-recall suite not implemented yet"


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
    from nowing_evals.suites.memory.recall import MemoryRecallBenchmark

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


# --------------------------------------------------------------------------- #
# AC-3 — recall-hit oracle (RS-2: top_k <= 5)
# --------------------------------------------------------------------------- #


def test_recall_hit_within_top_k_and_above_threshold():
    """AC-3: an item in top_k with score >= min_similarity is a hit."""
    from nowing_evals.suites.memory.recall.oracle import is_recall_hit

    item = {"id": 1, "score": 0.9}
    assert is_recall_hit(item, rank=1, top_k=5, min_similarity=0.3) is True


def test_recall_hit_beyond_top_k_is_noise():
    """AC-3: an item ranked past top_k is never a hit (RS-2 clamps to <= 5)."""
    from nowing_evals.suites.memory.recall.oracle import is_recall_hit

    item = {"id": 1, "score": 0.99}
    assert is_recall_hit(item, rank=6, top_k=5, min_similarity=0.3) is False


def test_recall_hit_below_similarity_threshold_is_noise():
    """AC-3: an item below the similarity threshold is noise even if top-ranked."""
    from nowing_evals.suites.memory.recall.oracle import is_recall_hit

    item = {"id": 1, "score": 0.1}
    assert is_recall_hit(item, rank=1, top_k=5, min_similarity=0.3) is False


def test_recall_hit_without_score_falls_back_to_top_k_membership():
    """AC-3/§9 risk: if ``/memories/search`` omits a similarity score, the oracle
    degrades to rank-only (top_k membership) classification instead of raising
    or silently always-failing.
    """
    from nowing_evals.suites.memory.recall.oracle import is_recall_hit

    item = {"id": 1}  # no "score" key at all
    assert is_recall_hit(item, rank=3, top_k=5, min_similarity=0.3) is True


def test_recall_hit_without_score_beyond_top_k_is_noise():
    """AC-3/§9 risk: the no-score fallback still respects the top_k rank clamp."""
    from nowing_evals.suites.memory.recall.oracle import is_recall_hit

    item = {"id": 1}
    assert is_recall_hit(item, rank=6, top_k=5, min_similarity=0.3) is False


# --------------------------------------------------------------------------- #
# AC-5 — RunArtifact + report_section
# --------------------------------------------------------------------------- #


def test_report_section_renders_precision_and_noise():
    """AC-5: report_section surfaces precision@5 (+CI) and noise rate."""
    from nowing_evals.suites.memory.recall import MemoryRecallBenchmark

    artifact = RunArtifact(
        suite="memory",
        benchmark="recall",
        run_timestamp="2026-07-25T00:00:00Z",
        raw_path=Path("raw.jsonl"),
        metrics={
            "precision_at_k": {"1": 0.9, "5": 0.82},
            "precision_at_5_ci": [0.71, 0.9],
            "noise_rate": 0.18,
            "recall_at_k": {"5": 0.75},
            "mrr": 0.8,
            "ndcg_at_10": 0.77,
            "n_queries": 40,
        },
    )
    section = MemoryRecallBenchmark().report_section([artifact])
    body = section.body_md.lower()
    assert "precision" in body
    assert "noise" in body


async def test_run_persists_artifact_with_quality_metrics(tmp_path, monkeypatch):
    """AC-5/§6.2: a run scores /memories/search results and persists a metrics
    artifact whose ``metrics`` dict carries the full RetrievalScores shape plus
    the runner-level ``top_k``/``min_similarity`` config that were used to score it.

    Injects a fake ``MemoriesClient.search`` (no live server) so this stays a
    unit test of the runner's wiring, not an integration test.
    """
    from nowing_evals.suites.memory.recall import MemoryRecallBenchmark
    from nowing_evals.suites.memory.recall.dataset import Dataset, Query

    fake_dataset = Dataset(
        queries=[
            Query(
                query_id="q1",
                query="where do I keep my passport",
                qrels={"m1": 2},
                distractors=["m2"],
                type="fact",
                tags=["personal"],
            )
        ],
        corpus={
            "m1": {"content": "passport is in the desk drawer", "type": "fact", "tags": []},
            "m2": {"content": "unrelated note", "type": "fact", "tags": []},
        },
    )

    class FakeMemoriesClient:
        async def search(self, query: str, *, top_k: int) -> list[dict]:
            assert query
            return [
                {"memory_ref": "m1", "score": 0.92},
                {"memory_ref": "m2", "score": 0.20},
            ][:top_k]

    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.dataset.load_dataset",
        lambda **_kw: fake_dataset,
    )
    monkeypatch.setattr(
        "nowing_evals.suites.memory.recall.MemoriesClient",
        lambda *_a, **_kw: FakeMemoriesClient(),
    )

    bench = MemoryRecallBenchmark()

    class FakeRunContext:
        suite = "memory"
        benchmark = "recall"

        def runs_dir(self, *, run_timestamp: str):
            path = tmp_path / run_timestamp / "recall"
            path.mkdir(parents=True, exist_ok=True)
            return path

    artifact = await bench.run(FakeRunContext(), top_k=5, min_similarity=0.3)

    required = {
        "precision_at_k",
        "noise_rate",
        "precision_at_5_ci",
        "recall_at_k",
        "mrr",
        "ndcg_at_10",
        "n_queries",
        "top_k",
        "min_similarity",
    }
    assert required <= artifact.metrics.keys()
    assert artifact.metrics["n_queries"] == 1
    assert artifact.metrics["top_k"] == 5
    assert artifact.metrics["min_similarity"] == 0.3
