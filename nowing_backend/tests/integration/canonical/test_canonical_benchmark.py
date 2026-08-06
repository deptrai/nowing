"""Integration test for canonical dedup benchmark gates.

Loads the committed 30% overlap BDS and Jobs fixtures, runs the production
dedup pipeline, and asserts the hard precision/recall/F1 release gates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.canonical.eval.dedup_metrics import score_dedup
from app.services.bds_aggregator.dedupe import deduplicate as bds_deduplicate
from app.services.bds_aggregator.normalize import normalize_listing as bds_normalize
from app.services.jobs_aggregator.dedupe import deduplicate as jobs_deduplicate
from app.services.jobs_aggregator.normalize import normalize_listing as jobs_normalize

pytestmark = [pytest.mark.canonical, pytest.mark.integration]

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[4]
    / "nowing_evals"
    / "data"
    / "canonical"
    / "fixtures"
)

_GATES = {"precision": 0.95, "recall": 0.90, "f1": 0.92}


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _record_index_key(record: dict) -> tuple[str, str]:
    return str(record["source"]), str(record.get("source_id", record.get("id", "")))


def _bds_predicted_groups(records: list[dict], merged: list) -> list[list[dict]]:
    record_index = {_record_index_key(r): r for r in records}
    groups: list[list[dict]] = []
    for item in merged:
        group: list[dict] = []
        for source, source_id in item.source_ids.items():
            if source_id is None:
                continue
            key = (source, str(source_id))
            if key in record_index:
                group.append(record_index.pop(key))
        if group:
            groups.append(group)
    for record in record_index.values():
        groups.append([record])
    return groups


def _jobs_predicted_groups(records: list[dict], merged: list) -> list[list[dict]]:
    record_index = {_record_index_key(r): r for r in records}
    groups: list[list[dict]] = []
    for item in merged:
        group: list[dict] = []
        for source, source_id in item._source_record_ids.items():
            key = (source, str(source_id))
            if key in record_index:
                group.append(record_index.pop(key))
        if group:
            groups.append(group)
    for record in record_index.values():
        groups.append([record])
    return groups


def _score_fixture(domain: str, fixture: str) -> Any:
    fixture_path = _FIXTURE_DIR / f"{fixture}.jsonl"
    records = _load_jsonl(fixture_path)
    ground_truth = {r["record_id"]: r["canonical_entity_id"] for r in records}

    if domain == "bds":
        listings = [bds_normalize(r["source"], r) for r in records]
        merged = bds_deduplicate(listings)
        predicted_groups = _bds_predicted_groups(records, merged)
    else:
        listings = [jobs_normalize(r["source"], r) for r in records]
        merged = jobs_deduplicate(listings)
        predicted_groups = _jobs_predicted_groups(records, merged)

    return score_dedup(records, predicted_groups, ground_truth)


def test_bds_canonical_benchmark_gate():
    scores = _score_fixture("bds", "bds-overlap-30")
    assert scores.precision >= _GATES["precision"]
    assert scores.recall >= _GATES["recall"]
    assert scores.f1 >= _GATES["f1"]


def test_jobs_canonical_benchmark_gate():
    scores = _score_fixture("jobs", "jobs-overlap-30")
    assert scores.precision >= _GATES["precision"]
    assert scores.recall >= _GATES["recall"]
    assert scores.f1 >= _GATES["f1"]
