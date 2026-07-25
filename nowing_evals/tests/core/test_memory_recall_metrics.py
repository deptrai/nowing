"""Metric acceptance tests — Story 3.9 Memory Recall Eval-Gate (AC-3, AC-4).

Covers the precision / noise family and the invariants the ship gate depends
on, without regressing the existing recall@k / MRR / nDCG aggregation.
"""

from __future__ import annotations

import pytest

from nowing_evals.core.metrics.retrieval import (
    distractor_rate,
    noise_rate,
    off_corpus_rate,
    precision_at_k,
    score_run,
)


def test_precision_at_k_counts_relevant_in_top_k():
    """AC-4: precision@k = relevant hits in top_k / min(k, retrieved)."""
    retrieved = ["a", "b", "c", "d"]
    relevant = ["b", "d", "z"]
    assert precision_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 2)  # b hit, a miss
    assert precision_at_k(retrieved, relevant, k=4) == pytest.approx(2 / 4)  # b,d hit


def test_precision_at_k_empty_retrieved_is_zero():
    """AC-4: no retrieved items => precision 0.0 (no division error)."""
    assert precision_at_k([], ["a"], k=5) == 0.0


def test_noise_rate_is_one_minus_precision():
    """AC-4: noise_rate == 1 - precision@k over the same top_k."""
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = ["a", "b"]
    p = precision_at_k(retrieved, relevant, k=5)
    assert noise_rate(retrieved, relevant, k=5) == pytest.approx(1.0 - p)


def test_noise_rate_all_relevant_is_zero():
    """AC-4: a fully-relevant top_k has zero noise."""
    assert noise_rate(["a", "b"], ["a", "b"], k=2) == 0.0


# --------------------------------------------------------------------------- #
# DEC-4 — distractor-hit rate is the gated noise signal
# --------------------------------------------------------------------------- #


def test_distractor_rate_counts_labeled_distractors_only():
    """DEC-4: only ids the dataset labels as must-not-recall count."""
    retrieved = ["m1", "d1", "junk", "d2", "other"]
    assert distractor_rate(retrieved, ["d1", "d2"], k=5) == pytest.approx(2 / 5)


def test_distractor_rate_is_independent_of_precision():
    """DEC-4: this is why noise is gated here and not on 1 - precision.

    ``1 - precision`` is algebraically determined by precision, so gating on
    both applies a single constraint while appearing to apply two. Two runs can
    share an identical precision and differ entirely in distractor noise.
    """
    relevant = ["m1"]
    distractors = ["d1", "d2", "d3", "d4"]
    all_distractors = ["m1", "d1", "d2", "d3", "d4"]
    no_distractors = ["m1", "x1", "x2", "x3", "x4"]

    assert precision_at_k(all_distractors, relevant, k=5) == pytest.approx(
        precision_at_k(no_distractors, relevant, k=5)
    )
    assert distractor_rate(all_distractors, distractors, k=5) == pytest.approx(4 / 5)
    assert distractor_rate(no_distractors, distractors, k=5) == 0.0


def test_off_corpus_rate_counts_marked_slots():
    """Results the labels cannot judge must count against the run."""
    retrieved = ["m1", "__off_corpus__#2", "__off_corpus__#3", "m2", "m3"]
    marked = ["__off_corpus__#2", "__off_corpus__#3"]
    assert off_corpus_rate(retrieved, marked, k=5) == pytest.approx(2 / 5)


def test_empty_retrieved_is_not_scored_as_noise():
    """An outage must not be indistinguishable from a precision regression.

    Returning nothing is a recall failure, which ``recall_at_k`` reports. Also
    counting it as maximal noise would make the two failure modes produce the
    same gate verdict for different reasons.
    """
    assert distractor_rate([], ["d1"], k=5) == 0.0
    assert off_corpus_rate([], ["x"], k=5) == 0.0


# --------------------------------------------------------------------------- #
# AC-4/AC-5 — aggregation
# --------------------------------------------------------------------------- #


def test_score_run_reports_precision_and_noise():
    """AC-4/AC-5: aggregated scores expose precision_at_k and noise_rate."""
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


def test_score_run_aggregates_distractor_and_off_corpus_rates():
    """DEC-4: the gated noise signals are aggregated per query then averaged."""
    scores = score_run(
        per_query_retrieved={"q1": ["m1", "d1", "__off_corpus__#3"]},
        per_query_qrels={"q1": {"m1": 2}},
        per_query_distractors={"q1": ["d1"]},
        per_query_off_corpus={"q1": ["__off_corpus__#3"]},
        ks=(1, 5),
        ndcg_k=5,
    )
    d = scores.to_dict()
    assert d["distractor_noise_rate"] == pytest.approx(1 / 3)
    assert d["off_corpus_rate"] == pytest.approx(1 / 3)
    assert d["off_corpus_measured"] is True


def test_off_corpus_is_flagged_as_unmeasured_when_not_supplied():
    """A consumer must be able to tell "clean" from "never looked"."""
    scores = score_run(
        per_query_retrieved={"q1": ["a"]},
        per_query_qrels={"q1": {"a": 1}},
        ks=(1, 5),
    )
    d = scores.to_dict()
    assert d["off_corpus_rate"] == 0.0
    assert d["off_corpus_measured"] is False


def test_primary_k_is_always_present_in_the_breakdown():
    """A gate reading precision_at_k[primary_k] can never find it missing.

    Requesting ``ks=(1, 10)`` used to emit noise/CI at a hardcoded k=5 while the
    precision breakdown had no "5" key at all, so the gate rejected a
    structurally valid artifact as "precision@5 is missing".
    """
    scores = score_run(
        per_query_retrieved={"q1": ["a", "b"]},
        per_query_qrels={"q1": {"a": 1}},
        ks=(1, 10),
        primary_k=5,
    )
    d = scores.to_dict()
    assert "5" in d["precision_at_k"]
    assert "5" in d["recall_at_k"]
    assert d["primary_k"] == 5


def test_noise_window_follows_primary_k():
    """A run pinned to top_k=3 must not label its numbers as if k were 5."""
    scores = score_run(
        per_query_retrieved={"q1": ["a", "x", "y"]},
        per_query_qrels={"q1": {"a": 1}},
        ks=(1, 3),
        primary_k=3,
    )
    d = scores.to_dict()
    assert d["primary_k"] == 3
    assert d["noise_rate"] == pytest.approx(2 / 3)


def test_wilson_ci_brackets_the_estimator_it_reports():
    """AC-4: the published CI must contain the point estimate it belongs to.

    ``precision_at_k`` is a macro mean of per-query proportions; the Wilson
    interval is computed over pooled judged slots. Those are different
    estimators, so the interval is published next to
    ``precision_at_primary_k_micro`` — the number it actually brackets. Pairing
    it with the macro mean can put the point estimate outside its own interval.
    """
    scores = score_run(
        per_query_retrieved={
            **{f"q{i}": ["rel"] for i in range(10)},
            "qbad": ["n1", "n2", "n3", "n4", "n5"],
        },
        per_query_qrels={
            **{f"q{i}": {"rel": 2} for i in range(10)},
            "qbad": {"rel": 2},
        },
        ks=(1, 5),
    )
    d = scores.to_dict()
    low, high = d["precision_at_5_ci"]
    micro = d["precision_at_primary_k_micro"]
    assert 0.0 <= low <= micro <= high <= 1.0
    assert d["precision_at_primary_k_ci"] == d["precision_at_5_ci"]


def test_zero_query_run_reports_no_evidence_not_clean():
    """A run with nothing judged must not look like a clean run."""
    scores = score_run(
        per_query_retrieved={},
        per_query_qrels={},
        ks=(1, 5),
    )
    d = scores.to_dict()
    assert d["n_queries"] == 0
    assert d["precision_at_5_ci"] == (0.0, 1.0)  # maximally uncertain


def test_absurd_grade_is_rejected_rather_than_overflowing():
    """``2 ** grade`` in the nDCG gain overflows for an unbounded grade."""
    with pytest.raises(ValueError, match="grade"):
        score_run(
            per_query_retrieved={"q1": ["a"]},
            per_query_qrels={"q1": {"a": 1024}},
            ks=(1,),
        )


def test_existing_recall_metrics_still_present():
    """AC-4 regression guard: recall@k / MRR / nDCG remain in the aggregate."""
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
    # nDCG is reported at the k that was actually requested, so a suite capped
    # at top_k=5 does not publish nDCG@5 under an "@10" label unqualified.
    assert d["ndcg_k"] == 5
    assert "5" in d["ndcg_at_k"]


def test_new_metrics_exported_from_metrics_package():
    """AC-4: the precision / noise family is re-exported from core.metrics."""
    from nowing_evals.core import metrics

    for name in ("precision_at_k", "noise_rate", "distractor_rate", "off_corpus_rate"):
        assert hasattr(metrics, name), name
