"""Labeled memory-recall dataset + validating loader (Story 3.9, AC-2).

Two JSONL files, both versioned in-repo next to this module under ``dataset/``
(NOT under the gitignored ``data/``, which holds ingested/run outputs only):

* ``queries.jsonl`` — one row per query, schema per story §6.1::

      {"query_id": "q001", "query": "...",
       "relevant": [{"memory_ref": "m_x", "grade": 2}],
       "distractors": ["m_y"], "type": "semantic", "tags": ["pricing"]}

* ``corpus.jsonl`` — one row per seedable memory::

      {"memory_ref": "m_x", "content": "...", "type": "semantic", "tags": []}

``grade > 0`` means relevant. Graded relevance is honoured by nDCG; recall and
precision flatten anything > 0 to a binary hit.

Every row is validated on load — a malformed dataset must fail loudly at load
time rather than silently scoring a partial corpus (a quietly-dropped qrel
inflates precision, which is exactly what this eval-gate exists to catch).

Note on layout: this module is ``dataset.py`` while the JSONL files live in a
sibling directory also named ``dataset/``. That directory deliberately has no
``__init__.py`` — Python's import machinery resolves a real module ahead of a
namespace-package directory, so ``import ...recall.dataset`` reaches this file.
``_bundled_dir()`` locates the data by path, never by import.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Typed rows
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Query:
    """One labeled query with graded qrels and explicit distractors."""

    query_id: str
    query: str
    qrels: dict[str, int]
    distractors: list[str] = field(default_factory=list)
    type: str = "semantic"
    tags: list[str] = field(default_factory=list)

    @property
    def relevant_refs(self) -> list[str]:
        """Refs with ``grade > 0`` (binary relevance view)."""

        return [ref for ref, grade in self.qrels.items() if grade > 0]


@dataclass(frozen=True)
class Dataset:
    """Loaded dataset: queries plus the corpus of memories to seed."""

    queries: list[Query]
    corpus: dict[str, dict[str, Any]]


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #


def _bundled_dir() -> Path:
    return Path(__file__).parent / "dataset"


def default_queries_path() -> Path:
    return _bundled_dir() / "queries.jsonl"


def default_corpus_path() -> Path:
    return _bundled_dir() / "corpus.jsonl"


# --------------------------------------------------------------------------- #
# Row parsing / validation
# --------------------------------------------------------------------------- #


def _iter_rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise ValueError(f"Dataset file not found: {path}")
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{lineno}: invalid JSON — {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{lineno}: row must be a JSON object")
            rows.append((lineno, row))
    if not rows:
        raise ValueError(f"{path.name}: dataset is empty")
    return rows


def _require_str(row: dict[str, Any], key: str, *, where: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: '{key}' is required and must be a non-empty string")
    return value


def _require_tags(row: dict[str, Any], *, where: str) -> list[str]:
    raw = row.get("tags", [])
    if not isinstance(raw, list) or not all(isinstance(t, str) for t in raw):
        raise ValueError(f"{where}: 'tags' must be a list of strings")
    return list(raw)


def _parse_qrels(row: dict[str, Any], *, where: str) -> dict[str, int]:
    raw = row.get("relevant")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{where}: 'relevant' must be a non-empty list of {{memory_ref, grade}}")
    qrels: dict[str, int] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: each 'relevant' entry must be an object")
        ref = _require_str(entry, "memory_ref", where=where)
        grade = entry.get("grade", 1)
        # bool is an int subclass — reject it explicitly, a boolean grade is a
        # schema error, not "grade 1".
        if isinstance(grade, bool) or not isinstance(grade, int):
            raise ValueError(f"{where}: grade for {ref!r} must be an int, got {grade!r}")
        if grade < 0:
            raise ValueError(f"{where}: grade for {ref!r} must be >= 0, got {grade}")
        qrels[ref] = grade
    if not any(g > 0 for g in qrels.values()):
        raise ValueError(f"{where}: needs at least one relevant memory with grade > 0")
    return qrels


def _parse_query_row(row: dict[str, Any], *, where: str) -> Query:
    query_id = _require_str(row, "query_id", where=where)
    query = _require_str(row, "query", where=where)
    qrels = _parse_qrels(row, where=where)
    # 'type' is a required row field per §6.1, not an optional extra: the report
    # and gate slice metrics by it, so a row without it is a schema violation.
    type_ = _require_str(row, "type", where=where)
    tags = _require_tags(row, where=where)

    raw_distractors = row.get("distractors", [])
    if not isinstance(raw_distractors, list) or not all(
        isinstance(d, str) for d in raw_distractors
    ):
        raise ValueError(f"{where}: 'distractors' must be a list of memory_ref strings")
    distractors = list(raw_distractors)

    overlap = set(distractors) & set(qrels)
    if overlap:
        raise ValueError(
            f"{where}: memory_ref(s) {sorted(overlap)} appear as both relevant and distractor"
        )

    return Query(
        query_id=query_id,
        query=query,
        qrels=qrels,
        distractors=distractors,
        type=type_,
        tags=tags,
    )


def _parse_corpus_row(row: dict[str, Any], *, where: str) -> tuple[str, dict[str, Any]]:
    ref = _require_str(row, "memory_ref", where=where)
    content = _require_str(row, "content", where=where)
    type_ = _require_str(row, "type", where=where)
    tags = _require_tags(row, where=where)
    return ref, {"content": content, "type": type_, "tags": tags}


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #


def load_dataset(
    *,
    queries_path: Path | str | None = None,
    corpus_path: Path | str | None = None,
) -> Dataset:
    """Load + validate the labeled recall dataset.

    Both paths default to the bundled versioned dataset. Raises ``ValueError``
    with a ``file:line`` prefix on any malformed row, and on any qrel or
    distractor ref that does not resolve in the corpus (an unresolvable ref
    would silently vanish from scoring).
    """

    q_path = Path(queries_path) if queries_path is not None else default_queries_path()
    c_path = Path(corpus_path) if corpus_path is not None else default_corpus_path()

    queries: list[Query] = []
    seen_ids: set[str] = set()
    for lineno, row in _iter_rows(q_path):
        parsed = _parse_query_row(row, where=f"{q_path.name}:{lineno}")
        if parsed.query_id in seen_ids:
            raise ValueError(f"{q_path.name}:{lineno}: duplicate query_id {parsed.query_id!r}")
        seen_ids.add(parsed.query_id)
        queries.append(parsed)

    corpus: dict[str, dict[str, Any]] = {}
    for lineno, row in _iter_rows(c_path):
        ref, memory = _parse_corpus_row(row, where=f"{c_path.name}:{lineno}")
        if ref in corpus:
            raise ValueError(f"{c_path.name}:{lineno}: duplicate memory_ref {ref!r}")
        corpus[ref] = memory

    for q in queries:
        missing = [ref for ref in list(q.qrels) + q.distractors if ref not in corpus]
        if missing:
            raise ValueError(
                f"{q_path.name}: query {q.query_id!r} references memory_ref(s) "
                f"{sorted(missing)} absent from {c_path.name}"
            )

    return Dataset(queries=queries, corpus=corpus)


__all__ = [
    "Dataset",
    "Query",
    "default_corpus_path",
    "default_queries_path",
    "load_dataset",
]
