"""ATDD red-phase scaffolds — Story 3.9 Memory Recall Eval-Gate.

Covers AC-2: the labeled memory-recall dataset (queries + graded qrels + distractors)
loads through a typed loader that validates every row and rejects malformed input.

RED PHASE: skipped tests; imports of the not-yet-existing loader live inside test
bodies so collection stays clean (only skips, 0 errors).
"""

from __future__ import annotations

import pytest

RED = "ATDD red-phase (Story 3.9): memory-recall dataset + loader not implemented yet"


def test_load_dataset_returns_queries_and_corpus():
    """AC-2: loader yields queries with graded qrels and a corpus of memories."""
    from nowing_evals.suites.memory.recall.dataset import load_dataset

    ds = load_dataset()  # loads the bundled versioned dataset by default
    assert len(ds.queries) > 0
    q = ds.queries[0]
    assert q.query_id
    assert q.query
    assert q.qrels  # {memory_ref: grade}, grade > 0 = relevant
    # every relevant + distractor ref must resolve in the corpus
    for ref in list(q.qrels) + list(q.distractors):
        assert ref in ds.corpus


def test_dataset_has_distractors_for_noise_measurement():
    """AC-2: at least some queries carry distractors so noise-rate is measurable."""
    from nowing_evals.suites.memory.recall.dataset import load_dataset

    ds = load_dataset()
    assert any(q.distractors for q in ds.queries)


def test_loader_rejects_row_missing_query_text(tmp_path):
    """AC-2: malformed row (no query text) raises a clear validation error."""
    from nowing_evals.suites.memory.recall.dataset import load_dataset

    bad = tmp_path / "queries.jsonl"
    bad.write_text(
        '{"query_id": "q1", "query": "", "relevant": [{"memory_ref": "m1", "grade": 1}]}\n'
    )
    with pytest.raises(ValueError):
        load_dataset(queries_path=bad)


def test_loader_rejects_empty_qrels(tmp_path):
    """AC-2: a query with no relevant memories is invalid."""
    from nowing_evals.suites.memory.recall.dataset import load_dataset

    bad = tmp_path / "queries.jsonl"
    bad.write_text('{"query_id": "q1", "query": "hello", "relevant": []}\n')
    with pytest.raises(ValueError):
        load_dataset(queries_path=bad)


def test_loader_rejects_unknown_grade(tmp_path):
    """AC-2: qrels grades must be non-negative ints (graded relevance)."""
    from nowing_evals.suites.memory.recall.dataset import load_dataset

    bad = tmp_path / "queries.jsonl"
    bad.write_text(
        '{"query_id": "q1", "query": "hi", "relevant": [{"memory_ref": "m1", "grade": -1}]}\n'
    )
    with pytest.raises(ValueError):
        load_dataset(queries_path=bad)


def test_loader_preserves_type_and_tags(tmp_path):
    """AC-2 (§6.1): each query row's ``type``/``tags`` fields survive loading.

    The dataset schema carries ``type`` (query category, e.g. "factual") and
    ``tags`` (list[str]) per row so the report/gate can slice metrics later.
    A loader that silently drops them would pass every other test in this
    file while still violating the row schema.
    """
    from nowing_evals.suites.memory.recall.dataset import load_dataset

    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        '{"query_id": "q1", "query": "what is the deploy cadence?", '
        '"relevant": [{"memory_ref": "m1", "grade": 2}], "distractors": ["m2"], '
        '"type": "factual", "tags": ["ops", "deploy"]}\n'
    )
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        '{"memory_ref": "m1", "content": "we deploy weekly", "type": "note", "tags": []}\n'
        '{"memory_ref": "m2", "content": "unrelated memory", "type": "note", "tags": []}\n'
    )

    ds = load_dataset(queries_path=queries, corpus_path=corpus)
    q = ds.queries[0]
    assert q.type == "factual"
    assert q.tags == ["ops", "deploy"]


def test_loader_rejects_row_missing_type(tmp_path):
    """AC-2 (§6.1): ``type`` is a required row field, not an optional extra."""
    from nowing_evals.suites.memory.recall.dataset import load_dataset

    bad = tmp_path / "queries.jsonl"
    bad.write_text(
        '{"query_id": "q1", "query": "hi", '
        '"relevant": [{"memory_ref": "m1", "grade": 1}], "tags": []}\n'
    )
    with pytest.raises(ValueError):
        load_dataset(queries_path=bad)


def test_bundled_dataset_files_exist():
    """AC-2: the versioned dataset ships in-repo (queries + corpus JSONL)."""
    from pathlib import Path

    import nowing_evals.suites.memory.recall as recall_pkg

    base = Path(recall_pkg.__file__).parent / "dataset"
    assert (base / "queries.jsonl").exists()
    assert (base / "corpus.jsonl").exists()
