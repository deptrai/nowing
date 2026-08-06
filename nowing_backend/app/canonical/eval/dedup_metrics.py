"""Pairwise precision/recall/F1 for canonical deduplication.

ponytail: O(n²) per predicted/ground-truth group.  The fixtures are small
synthetic sets (<=200 records), so the straightforward quadratic scan is
smaller and less error-prone than a union-find or sparse matrix approach.
For n > 10k, switch to an inverted index over ground-truth entity pairs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Any


@dataclass(frozen=True)
class DedupScores:
    """Pairwise dedup quality metrics."""

    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    n_same_entity_pairs: int
    n_predicted_pairs: int
    n_records: int
    n_entities: int

    @property
    def passed(self) -> bool:
        """Hard release gates from Story 13.2e."""
        return (
            self.precision >= 0.95
            and self.recall >= 0.90
            and self.f1 >= 0.92
        )


def _record_id(record: dict[str, Any]) -> str:
    """Resolve a stable record identifier from a raw listing dict."""
    if "record_id" in record:
        return str(record["record_id"])
    source = str(record.get("source", ""))
    source_id = record.get("source_id")
    if source_id is None:
        raise ValueError("record has no 'record_id' or 'source_id' field")
    return f"{source}:{source_id}"


def score_dedup(
    listings: list[dict],
    predicted_groups: list[list[dict]],
    ground_truth: dict[str, str],
) -> DedupScores:
    """Return pairwise P/R/F1 for a deduplication result.

    * A true positive (TP) is a pair of raw records that are in the same
      predicted group and share the same ground-truth entity.
    * A false positive (FP) is a pair in the same predicted group but
      different ground-truth entities.
    * A false negative (FN) is a pair in the same ground-truth entity but
      different predicted groups.
    """
    all_ids = {_record_id(record) for record in listings}

    missing_ground_truth = all_ids - set(ground_truth)
    if missing_ground_truth:
        raise ValueError(f"Missing ground truth for {len(missing_ground_truth)} records")

    entity_of: dict[str, str] = {rid: ground_truth[rid] for rid in all_ids}

    predicted_index: dict[str, int] = {}
    for group_index, group in enumerate(predicted_groups):
        for record in group:
            rid = _record_id(record)
            if rid in predicted_index:
                raise ValueError(f"Record {rid} appears in multiple predicted groups")
            predicted_index[rid] = group_index

    missing_prediction = all_ids - set(predicted_index)
    if missing_prediction:
        raise ValueError(f"Not all records assigned to a predicted group: {missing_prediction}")

    true_positives = 0
    false_positives = 0
    predicted_pairs = 0
    for group in predicted_groups:
        ids = [_record_id(record) for record in group]
        for left, right in combinations(ids, 2):
            predicted_pairs += 1
            if entity_of[left] == entity_of[right]:
                true_positives += 1
            else:
                false_positives += 1

    entity_records: dict[str, list[str]] = defaultdict(list)
    for rid in all_ids:
        entity_records[entity_of[rid]].append(rid)

    n_same_entity_pairs = 0
    false_negatives = 0
    for records in entity_records.values():
        k = len(records)
        n_same_entity_pairs += k * (k - 1) // 2
        for left, right in combinations(records, 2):
            if predicted_index[left] != predicted_index[right]:
                false_negatives += 1

    predicted_total = true_positives + false_positives
    ground_truth_total = true_positives + false_negatives
    precision = true_positives / predicted_total if predicted_total else 1.0
    recall = true_positives / ground_truth_total if ground_truth_total else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return DedupScores(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        n_same_entity_pairs=n_same_entity_pairs,
        n_predicted_pairs=predicted_pairs,
        n_records=len(all_ids),
        n_entities=len(entity_records),
    )
