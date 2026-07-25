"""Acceptance tests for Story 3.9's validated memory-recall dataset (AC-2).

A note on fixture hygiene in this file: every "reject a bad row" test supplies
*all* the other required fields. Two tests here previously omitted
``distractors``, so the loader rejected them on the missing-distractors branch
and the behaviour they claimed to cover — empty query text, missing ``type`` —
was never actually exercised.
"""

from __future__ import annotations

import json

import pytest

from nowing_evals.suites.memory.recall.dataset import (
    MAX_GRADE,
    VALID_MEMORY_TYPES,
    load_dataset,
)

_CORPUS_ROWS = [
    {"memory_ref": "m1", "content": "we deploy weekly", "type": "semantic", "tags": []},
    {"memory_ref": "m2", "content": "unrelated memory", "type": "semantic", "tags": []},
]


def _corpus(tmp_path, rows=None):
    path = tmp_path / "corpus.jsonl"
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in (rows if rows is not None else _CORPUS_ROWS)),
        encoding="utf-8",
    )
    return path


def _queries(tmp_path, **overrides):
    row = {
        "query_id": "q1",
        "query": "what is the deploy cadence?",
        "relevant": [{"memory_ref": "m1", "grade": 2}],
        "distractors": ["m2"],
        "type": "factual",
        "tags": ["ops", "deploy"],
    }
    row.update(overrides)
    for key in [k for k, v in row.items() if v is _OMIT]:
        del row[key]
    path = tmp_path / "queries.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path


class _Omit:
    """Sentinel for "drop this key entirely" in a fixture override."""


_OMIT = _Omit()


def _load(tmp_path, **overrides):
    return load_dataset(
        queries_path=_queries(tmp_path, **overrides), corpus_path=_corpus(tmp_path)
    )


# --------------------------------------------------------------------------- #
# The bundled dataset
# --------------------------------------------------------------------------- #


def test_load_dataset_returns_queries_and_corpus():
    """AC-2: loader yields queries with graded qrels and a corpus of memories."""
    ds = load_dataset()  # loads the bundled versioned dataset by default
    assert len(ds.queries) > 0
    q = ds.queries[0]
    assert q.query_id
    assert q.query
    assert q.qrels  # {memory_ref: grade}, grade > 0 = relevant
    for ref in list(q.qrels) + list(q.distractors):
        assert ref in ds.corpus


def test_dataset_has_distractors_for_noise_measurement():
    """AC-2: queries carry distractors, and DEC-4 makes them load-bearing.

    ``distractor_noise_rate`` — the ship-gated noise signal — is computed from
    exactly these labels, so a dataset without them could not measure noise
    independently of precision.
    """
    ds = load_dataset()
    assert any(q.distractors for q in ds.queries)


def test_bundled_corpus_types_are_all_valid_backend_memory_types():
    """AC-2/AC-5: every fixture must be ingestable.

    Four committed rows used ``type: "policy"``, which the create endpoint
    rejects with a 422 — so ingest died part-way through and left the earlier
    memories orphaned in the workspace.
    """
    ds = load_dataset()
    invalid = {
        ref: entry["type"]
        for ref, entry in ds.corpus.items()
        if entry["type"] not in VALID_MEMORY_TYPES
    }
    assert not invalid, f"corpus rows carry non-MemoryType values: {invalid}"


def test_bundled_dataset_files_exist():
    """AC-2: the versioned dataset ships in-repo (queries + corpus JSONL)."""
    from pathlib import Path

    import nowing_evals.suites.memory.recall as recall_pkg

    base = Path(recall_pkg.__file__).parent / "dataset"
    assert (base / "queries.jsonl").exists()
    assert (base / "corpus.jsonl").exists()


# --------------------------------------------------------------------------- #
# AC-2 — the loader rejects malformed rows
# --------------------------------------------------------------------------- #


def test_loader_preserves_type_and_tags(tmp_path):
    """AC-2 (§6.1): each query row's ``type``/``tags`` fields survive loading."""
    ds = _load(tmp_path)
    q = ds.queries[0]
    assert q.type == "factual"
    assert q.tags == ["ops", "deploy"]


def test_loader_rejects_row_missing_query_text(tmp_path):
    """AC-2: malformed row (no query text) raises a clear validation error."""
    with pytest.raises(ValueError, match="'query'"):
        _load(tmp_path, query="")


def test_loader_rejects_whitespace_only_query(tmp_path):
    with pytest.raises(ValueError, match="'query'"):
        _load(tmp_path, query="   \t ")


def test_loader_rejects_zero_width_only_query(tmp_path):
    """``"\\u200b".isspace()`` is False, so ``.strip()`` leaves it truthy.

    The backend then skips embedding for a blank-ish query and the run records a
    silent quality failure instead of a fixture error.
    """
    with pytest.raises(ValueError, match="'query'"):
        _load(tmp_path, query="\u200b\u200b")


def test_loader_rejects_row_missing_type(tmp_path):
    """AC-2 (§6.1): ``type`` is a required row field, not an optional extra."""
    with pytest.raises(ValueError, match="'type'"):
        _load(tmp_path, type=_OMIT)


def test_loader_rejects_row_missing_distractors(tmp_path):
    with pytest.raises(ValueError, match="'distractors'"):
        _load(tmp_path, distractors=_OMIT)


def test_loader_rejects_empty_qrels(tmp_path):
    """AC-2: a query with no relevant memories is invalid."""
    with pytest.raises(ValueError, match="relevant"):
        _load(tmp_path, relevant=[])


def test_loader_rejects_all_zero_grades(tmp_path):
    with pytest.raises(ValueError, match="positive grade"):
        _load(tmp_path, relevant=[{"memory_ref": "m1", "grade": 0}])


def test_loader_rejects_negative_grade(tmp_path):
    """AC-2: qrels grades must be non-negative ints (graded relevance)."""
    with pytest.raises(ValueError, match="grade"):
        _load(tmp_path, relevant=[{"memory_ref": "m1", "grade": -1}])


def test_loader_rejects_grade_above_the_supported_scale(tmp_path):
    """AC-2 'unknown grade': shape alone is not enough.

    Any non-negative int used to be accepted, so ``grade: 1024`` loaded fine and
    then raised ``OverflowError`` inside the nDCG gain (``2 ** grade``) after
    every search had already been issued.
    """
    with pytest.raises(ValueError, match="grade"):
        _load(tmp_path, relevant=[{"memory_ref": "m1", "grade": MAX_GRADE + 1}])


def test_loader_rejects_non_integer_grade(tmp_path):
    with pytest.raises(ValueError, match="grade"):
        _load(tmp_path, relevant=[{"memory_ref": "m1", "grade": 1.5}])


def test_loader_rejects_distractor_that_is_also_relevant(tmp_path):
    with pytest.raises(ValueError, match="distractors cannot also be relevant"):
        _load(tmp_path, distractors=["m1"])


def test_loader_rejects_dangling_reference(tmp_path):
    with pytest.raises(ValueError, match="absent corpus"):
        _load(tmp_path, distractors=["nope"])


def test_loader_rejects_duplicate_query_ids(tmp_path):
    queries = tmp_path / "queries.jsonl"
    row = {
        "query_id": "q1",
        "query": "hi",
        "relevant": [{"memory_ref": "m1", "grade": 1}],
        "distractors": [],
        "type": "factual",
        "tags": [],
    }
    queries.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate query_id"):
        load_dataset(queries_path=queries, corpus_path=_corpus(tmp_path))


def test_loader_rejects_corpus_row_with_invalid_memory_type(tmp_path):
    """Catch a 422-bound fixture at load time, not part-way through ingest."""
    rows = [{"memory_ref": "m1", "content": "x", "type": "policy", "tags": []}]
    with pytest.raises(ValueError, match="MemoryType"):
        load_dataset(
            queries_path=_queries(tmp_path), corpus_path=_corpus(tmp_path, rows=rows)
        )


def test_loader_rejects_duplicate_corpus_refs(tmp_path):
    rows = [
        {"memory_ref": "m1", "content": "a", "type": "semantic", "tags": []},
        {"memory_ref": "m1", "content": "b", "type": "semantic", "tags": []},
    ]
    with pytest.raises(ValueError, match="duplicate memory_ref"):
        load_dataset(
            queries_path=_queries(tmp_path), corpus_path=_corpus(tmp_path, rows=rows)
        )


def test_loader_rejects_empty_files(tmp_path):
    empty = tmp_path / "queries.jsonl"
    empty.write_text("\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_dataset(queries_path=empty, corpus_path=_corpus(tmp_path))


def test_loader_reports_file_and_line_on_failure(tmp_path):
    """A fixture error must be locatable without bisecting the file."""
    queries = tmp_path / "queries.jsonl"
    queries.write_text(
        json.dumps(
            {
                "query_id": "q1",
                "query": "ok",
                "relevant": [{"memory_ref": "m1", "grade": 1}],
                "distractors": [],
                "type": "factual",
                "tags": [],
            }
        )
        + "\n"
        + "{ not json\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"queries\.jsonl:2"):
        load_dataset(queries_path=queries, corpus_path=_corpus(tmp_path))
