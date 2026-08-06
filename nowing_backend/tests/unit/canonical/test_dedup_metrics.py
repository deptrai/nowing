"""Unit tests for canonical dedup pairwise metrics."""

from __future__ import annotations

import pytest

from app.canonical.eval.dedup_metrics import DedupScores, score_dedup

pytestmark = [pytest.mark.unit, pytest.mark.canonical]


def _record(record_id: str, entity_id: str) -> dict:
    return {"record_id": record_id, "canonical_entity_id": entity_id}


def test_perfect_dedup_scores_one():
    listings = [
        _record("a:1", "e1"),
        _record("b:1", "e1"),
        _record("c:1", "e2"),
    ]
    predicted_groups = [
        [_record("a:1", "e1"), _record("b:1", "e1")],
        [_record("c:1", "e2")],
    ]
    ground_truth = {r["record_id"]: r["canonical_entity_id"] for r in listings}
    scores = score_dedup(listings, predicted_groups, ground_truth)
    assert scores.precision == 1.0
    assert scores.recall == 1.0
    assert scores.f1 == 1.0
    assert scores.true_positives == 1
    assert scores.false_positives == 0
    assert scores.false_negatives == 0


def test_false_positive_split_entity():
    listings = [
        _record("a:1", "e1"),
        _record("b:1", "e2"),
    ]
    predicted_groups = [[listings[0], listings[1]]]
    ground_truth = {"a:1": "e1", "b:1": "e2"}
    scores = score_dedup(listings, predicted_groups, ground_truth)
    assert scores.precision == 0.0
    # No same-entity pairs exist, so there is nothing to recall.
    assert scores.recall == 1.0
    assert scores.f1 == 0.0
    assert scores.true_positives == 0
    assert scores.false_positives == 1
    assert scores.false_negatives == 0


def test_false_negative_missed_merge():
    listings = [
        _record("a:1", "e1"),
        _record("b:1", "e1"),
    ]
    predicted_groups = [[listings[0]], [listings[1]]]
    ground_truth = {"a:1": "e1", "b:1": "e1"}
    scores = score_dedup(listings, predicted_groups, ground_truth)
    assert scores.precision == 1.0
    assert scores.recall == 0.0
    assert scores.f1 == 0.0
    assert scores.true_positives == 0
    assert scores.false_positives == 0
    assert scores.false_negatives == 1


def test_mixed_two_entities_two_groups():
    listings = [
        _record("a:1", "e1"),
        _record("a:2", "e1"),
        _record("b:1", "e2"),
        _record("b:2", "e2"),
    ]
    predicted_groups = [
        [_record("a:1", "e1"), _record("a:2", "e1"), _record("b:1", "e2")],
        [_record("b:2", "e2")],
    ]
    ground_truth = {r["record_id"]: r["canonical_entity_id"] for r in listings}
    scores = score_dedup(listings, predicted_groups, ground_truth)
    assert scores.true_positives == 1  # a:1/a:2
    assert scores.false_positives == 2  # a:1/b:1, a:2/b:1
    assert scores.false_negatives == 1  # b:1/b:2
    assert pytest.approx(scores.precision, rel=1e-9) == 1 / 3
    assert pytest.approx(scores.recall, rel=1e-9) == 1 / 2
    assert scores.f1 == pytest.approx(2 * (1 / 3) * (1 / 2) / ((1 / 3) + (1 / 2)))


def test_gate_passed_requires_all_thresholds():
    passed = DedupScores(
        precision=0.95,
        recall=0.90,
        f1=0.92,
        true_positives=0,
        false_positives=0,
        false_negatives=0,
        n_same_entity_pairs=0,
        n_predicted_pairs=0,
        n_records=0,
        n_entities=0,
    )
    assert passed.passed is True

    failed_precision = DedupScores(
        precision=0.94,
        recall=0.90,
        f1=0.92,
        true_positives=0,
        false_positives=0,
        false_negatives=0,
        n_same_entity_pairs=0,
        n_predicted_pairs=0,
        n_records=0,
        n_entities=0,
    )
    assert failed_precision.passed is False


def test_missing_ground_truth_raises():
    listings = [_record("a:1", "e1")]
    with pytest.raises(ValueError, match="Missing ground truth"):
        score_dedup(listings, [[listings[0]]], {})


def test_record_in_multiple_predicted_groups_raises():
    listings = [_record("a:1", "e1")]
    with pytest.raises(ValueError, match="multiple predicted groups"):
        score_dedup(listings, [[listings[0]], [listings[0]]], {"a:1": "e1"})
