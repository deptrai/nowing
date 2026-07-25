"""ATDD red-phase scaffolds — Story 3.9 Memory Recall Eval-Gate.

Covers AC-4: ``precision_at_k`` and ``noise_rate`` metrics (noise = 1 - precision@k),
with ``precision@5`` reported alongside a Wilson 95% CI, without regressing the
existing recall@k / MRR / nDCG aggregation.

GREEN: metrics implemented in ``core/metrics/retrieval.py`` (Story 3.9 Step 1).
"""

from __future__ import annotations

import pytest


def test_precision_at_k_counts_relevant_in_top_k():
    """AC-4: precision@k = relevant hits in top_k / min(k, retrieved)."""
    from nowing_evals.core.metrics.retrieval import precision_at_k

    retrieved = ["a", "b", "c", "d"]
    relevant = ["b", "d", "z"]
    assert precision_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 2)  # b hit, a miss
    assert precision_at_k(retrieved, relevant, k=4) == pytest.approx(2 / 4)  # b,d hit


def test_precision_at_k_empty_retrieved_is_zero():
    """AC-4: no retrieved items => precision 0.0 (no division error)."""
    from nowing_evals.core.metrics.retrieval import precision_at_k

    assert precision_at_k([], ["a"], k=5) == 0.0


def test_noise_rate_is_one_minus_precision():
    """AC-4: noise_rate == 1 - precision@k over the same top_k."""
    from nowing_evals.core.metrics.retrieval import noise_rate, precision_at_k

    retrieved = ["a", "b", "c", "d", "e"]
    relevant = ["a", "b"]
    p = precision_at_k(retrieved, relevant, k=5)
    assert noise_rate(retrieved, relevant, k=5) == pytest.approx(1.0 - p)


def test_noise_rate_all_relevant_is_zero():
    """AC-4: a fully-relevant top_k has zero noise."""
    from nowing_evals.core.metrics.retrieval import noise_rate

    assert noise_rate(["a", "b"], ["a", "b"], k=2) == 0.0


def test_score_run_reports_precision_and_noise():
    """AC-4/AC-5: aggregated scores expose precision_at_k and noise_rate."""
    from nowing_evals.core.metrics.retrieval import score_run

    scores = score_run(
        per_query_retrieved={"q1": ["a", "b"], "q2": ["x", "y"]},
        per_query_qrels={"q1": {"a": 1}, "q2": {"z": 2}},
        ks=(1, 5),
        ndcg_k=5,
    )
    d = scores.to_dict()
    assert "precision_at_k" in d
    assert "noise_rate" in d
    # q1: 1 relevant of 2 retrieved => 0.5 ; q2: 0 of 2 => 0.0 ; mean precision@5 = 0.25
    assert d["precision_at_k"]["5"] == pytest.approx(0.25)
    assert d["noise_rate"] == pytest.approx(0.75)


def test_precision_at_5_reported_with_wilson_ci():
    """AC-4: precision@5 carries a Wilson 95% CI (low <= point <= high)."""
    from nowing_evals.core.metrics.retrieval import score_run

    scores = score_run(
        per_query_retrieved={"q1": ["a", "b", "c", "d", "e"]},
        per_query_qrels={"q1": {"a": 1, "b": 1, "c": 1}},
        ks=(5,),
        ndcg_k=5,
    )
    d = scores.to_dict()
    low, high = d["precision_at_5_ci"]
    assert 0.0 <= low <= d["precision_at_k"]["5"] <= high <= 1.0


def test_existing_recall_metrics_still_present():
    """AC-4 regression guard: recall@k / MRR / nDCG remain in the aggregate."""
    from nowing_evals.core.metrics.retrieval import score_run

    scores = score_run(
        per_query_retrieved={"q1": ["a", "b"]},
        per_query_qrels={"q1": {"a": 1}},
        ks=(1, 5),
        ndcg_k=5,
    )
    d = scores.to_dict()
    assert "recall_at_k" in d
    assert "mrr" in d
    assert "ndcg_at_10" in d


def test_new_metrics_exported_from_metrics_package():
    """AC-4: precision_at_k / noise_rate are re-exported from core.metrics."""
    from nowing_evals.core import metrics

    assert hasattr(metrics, "precision_at_k")
    assert hasattr(metrics, "noise_rate")
