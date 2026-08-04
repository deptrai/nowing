"""Validated, versioned fixtures for the memory-recall benchmark.

The labels deliberately live beside the suite rather than under ``data/`` so they
are reviewable and deterministic. Runtime data such as ingested-id maps and run
artifacts are written through :class:`~nowing_evals.core.registry.RunContext`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DATASET_DIR = Path(__file__).with_name("dataset")
_DEFAULT_QUERIES_PATH = _DATASET_DIR / "queries.jsonl"
_DEFAULT_CORPUS_PATH = _DATASET_DIR / "corpus.jsonl"

#: Mirrors ``MemoryType`` in ``nowing_backend/app/db.py``. Validated here so a
#: fixture that the create endpoint would reject with a 422 is caught at load
#: time, rather than half-way through seeding a live workspace.
VALID_MEMORY_TYPES = frozenset({"semantic", "episodic", "procedural", "working"})

#: Graded-relevance scales are small (CUREv1 uses 0/1/2). An unbounded grade
#: reaches ``2 ** grade`` in the nDCG gain and overflows.
MAX_GRADE = 3

#: ``str.isspace()`` is False for zero-width and other format characters, so
#: ``"\u200b".strip()`` leaves a truthy string that reads as non-empty text.
_INVISIBLE_CHARS = "\u200b\u200c\u200d\u2060\ufeff\u00ad"


@dataclass(frozen=True)
class Query:
    """One labeled recall query with graded relevance and known distractors."""

    query_id: str
    query: str
    qrels: dict[str, int]
    distractors: list[str]
    type: str
    tags: list[str]


@dataclass(frozen=True)
class Dataset:
    """The query labels and memory corpus used to seed a benchmark workspace."""

    queries: list[Query]
    corpus: dict[str, dict[str, Any]]


def _error(path: Path, line_number: int, message: str) -> ValueError:
    return ValueError(f"Invalid memory-recall dataset row at {path}:{line_number}: {message}")


def _iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Memory-recall dataset file does not exist: {path}")

    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise _error(path, line_number, f"invalid JSON ({exc.msg})") from exc
            if not isinstance(row, dict):
                raise _error(path, line_number, "row must be a JSON object")
            yield line_number, row


def _meaningful(value: str) -> str:
    """Strip whitespace *and* zero-width characters, so blanks cannot hide."""

    return value.strip().strip(_INVISIBLE_CHARS).strip()


def _required_string(row: Mapping[str, Any], *, field: str, path: Path, line_number: int) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not _meaningful(value):
        raise _error(path, line_number, f"{field!r} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, *, field: str, path: Path, line_number: int) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not _meaningful(item) for item in value
    ):
        raise _error(path, line_number, f"{field!r} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _load_corpus(path: Path) -> dict[str, dict[str, Any]]:
    corpus: dict[str, dict[str, Any]] = {}
    for line_number, row in _iter_jsonl(path):
        memory_ref = _required_string(row, field="memory_ref", path=path, line_number=line_number)
        if memory_ref in corpus:
            raise _error(path, line_number, f"duplicate memory_ref {memory_ref!r}")
        memory_type = _required_string(row, field="type", path=path, line_number=line_number)
        if memory_type not in VALID_MEMORY_TYPES:
            raise _error(
                path,
                line_number,
                f"type {memory_type!r} is not a backend MemoryType; expected one of "
                f"{', '.join(sorted(VALID_MEMORY_TYPES))} — the create endpoint would "
                "reject this row with a 422 part-way through ingest",
            )
        corpus[memory_ref] = {
            "content": _required_string(row, field="content", path=path, line_number=line_number),
            "type": memory_type,
            "tags": _string_list(row.get("tags"), field="tags", path=path, line_number=line_number),
        }
    if not corpus:
        raise ValueError(f"Memory-recall corpus is empty: {path}")
    return corpus


def _parse_qrels(row: Mapping[str, Any], *, path: Path, line_number: int) -> dict[str, int]:
    raw_qrels = row.get("relevant")
    if not isinstance(raw_qrels, list) or not raw_qrels:
        raise _error(path, line_number, "'relevant' must be a non-empty list")

    qrels: dict[str, int] = {}
    for qrel in raw_qrels:
        if not isinstance(qrel, Mapping):
            raise _error(path, line_number, "each relevant entry must be an object")
        memory_ref = _required_string(qrel, field="memory_ref", path=path, line_number=line_number)
        grade = qrel.get("grade")
        if isinstance(grade, bool) or not isinstance(grade, int) or grade < 0 or grade > MAX_GRADE:
            raise _error(
                path,
                line_number,
                f"grade for memory_ref {memory_ref!r} must be an integer in "
                f"[0, {MAX_GRADE}] — the nDCG gain is 2**grade, so unbounded grades "
                "overflow",
            )
        if memory_ref in qrels:
            raise _error(path, line_number, f"duplicate relevant memory_ref {memory_ref!r}")
        qrels[memory_ref] = grade

    if not any(grade > 0 for grade in qrels.values()):
        raise _error(path, line_number, "'relevant' must contain at least one positive grade")
    return qrels


def _load_queries(path: Path, *, corpus: Mapping[str, dict[str, Any]]) -> list[Query]:
    queries: list[Query] = []
    seen_query_ids: set[str] = set()
    for line_number, row in _iter_jsonl(path):
        query_id = _required_string(row, field="query_id", path=path, line_number=line_number)
        if query_id in seen_query_ids:
            raise _error(path, line_number, f"duplicate query_id {query_id!r}")
        seen_query_ids.add(query_id)

        qrels = _parse_qrels(row, path=path, line_number=line_number)
        distractors = _string_list(
            row.get("distractors"), field="distractors", path=path, line_number=line_number
        )
        if len(set(distractors)) != len(distractors):
            raise _error(path, line_number, "'distractors' cannot contain duplicates")
        overlap = set(qrels).intersection(distractors)
        if overlap:
            raise _error(
                path,
                line_number,
                f"distractors cannot also be relevant: {', '.join(sorted(overlap))}",
            )

        referenced = set(qrels).union(distractors)
        unknown_refs = sorted(referenced.difference(corpus))
        if unknown_refs:
            raise _error(
                path,
                line_number,
                f"references absent corpus memory_ref values: {', '.join(unknown_refs)}",
            )

        queries.append(
            Query(
                query_id=query_id,
                query=_required_string(row, field="query", path=path, line_number=line_number),
                qrels=qrels,
                distractors=distractors,
                type=_required_string(row, field="type", path=path, line_number=line_number),
                tags=_string_list(
                    row.get("tags"), field="tags", path=path, line_number=line_number
                ),
            )
        )
    if not queries:
        raise ValueError(f"Memory-recall query dataset is empty: {path}")
    return queries


def load_dataset(
    queries_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
) -> Dataset:
    """Load and validate the bundled labels or explicit JSONL fixture paths.

    Every query reference, including distractors, must resolve to a corpus row.
    This catches mislabeled fixtures before a run can seed or score a workspace.
    """

    resolved_corpus_path = Path(corpus_path) if corpus_path is not None else _DEFAULT_CORPUS_PATH
    resolved_queries_path = (
        Path(queries_path) if queries_path is not None else _DEFAULT_QUERIES_PATH
    )
    corpus = _load_corpus(resolved_corpus_path)
    return Dataset(queries=_load_queries(resolved_queries_path, corpus=corpus), corpus=corpus)


__all__ = ["MAX_GRADE", "VALID_MEMORY_TYPES", "Dataset", "Query", "load_dataset"]
