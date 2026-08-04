"""Retrieval metrics: Recall@k, MRR, nDCG@k, Precision@k, noise rates.

Used by CUREv1's runner to score the Nowing arm against the benchmark's
qrels. ``corpus_id`` is the canonical CUREv1 passage id (string); the runner
maps Nowing ``chunk_id`` → ``document_id`` → ``corpus_id`` before calling
these.

Graded relevance (CUREv1 uses 0/1/2 grades) is honoured by ``ndcg_at_k``;
``recall_at_k`` and ``mrr`` flatten anything > 0 to "relevant".

Story 3.9 (memory recall eval-gate) added the precision / noise family. Three
distinct "noise" signals exist on purpose — collapsing them hides real failure
modes:

``noise_rate``
    ``1 - precision@primary_k``, macro-averaged per query. This is AC-4's
    definition. It is *algebraically determined* by ``precision_at_k`` and
    therefore useless as an independent gate condition — it is reported as a
    diagnostic only.
``distractor_noise_rate``
    Share of judged slots occupied by **labeled distractors** (memories the
    dataset asserts must NOT be recalled for that query). Independent of
    precision: a query can score 0 precision with 0 distractors returned.
    This is the ship-gated noise signal (Story 3.9 DEC-4).
``off_corpus_rate``
    Share of judged slots the caller marked as resolving to *no* labeled
    memory — pre-existing tenant memories, duplicates from a failed ingest,
    anything auto-extracted. Without this, a workspace full of foreign
    memories that outrank the labeled one scores perfectly, because the
    foreign items are simply absent from the qrels.

Confidence intervals: ``precision_at_k`` is a **macro** mean of per-query
proportions, while ``precision_at_primary_k_ci`` is a Wilson interval over
**pooled** (micro) judged slots. Those are two different estimators, so the
macro point estimate can legitimately fall outside the micro interval. The
interval is therefore published alongside ``precision_at_primary_k_micro``,
the estimator it actually brackets. Do not pair the CI with the macro number.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .mc_accuracy import wilson_ci

# ``2**grade`` in the DCG gain would overflow for absurd grades. Graded
# relevance scales are small by construction (CUREv1 uses 0/1/2); anything
# beyond this is a malformed fixture, not a legitimate grade.
_MAX_GRADE = 16


@dataclass(frozen=True)
class RetrievalScores:
    """Aggregated retrieval scores.

    ``ndcg_at_10`` keeps its legacy name for CUREv1 report compatibility; it
    actually holds nDCG at whatever ``ndcg_k`` the run requested. Read
    ``ndcg_k`` to label it honestly.
    """

    recall_at_k: dict[int, float]
    mrr: float
    ndcg_at_10: float
    n_queries: int
    precision_at_k: dict[int, float]
    noise_rate: float
    precision_at_5_ci: tuple[float, float]
    primary_k: int = 5
    ndcg_k: int = 10
    precision_at_primary_k_micro: float = 0.0
    distractor_noise_rate: float = 0.0
    off_corpus_rate: float = 0.0
    off_corpus_measured: bool = False

    def to_dict(self) -> dict:
        return {
            "recall_at_k": {str(k): v for k, v in self.recall_at_k.items()},
            "mrr": self.mrr,
            "ndcg_at_10": self.ndcg_at_10,
            "ndcg_at_k": {str(self.ndcg_k): self.ndcg_at_10},
            "ndcg_k": self.ndcg_k,
            "n_queries": self.n_queries,
            "precision_at_k": {str(k): v for k, v in self.precision_at_k.items()},
            "primary_k": self.primary_k,
            "precision_at_primary_k_micro": self.precision_at_primary_k_micro,
            # ``precision_at_5_ci`` is the §6.2 contract key and is kept as an
            # alias; the interval is computed at ``primary_k``, which equals 5
            # for any RS-2-compliant run. Read the ``primary_k`` variant when
            # a run pins a narrower window.
            "precision_at_5_ci": self.precision_at_5_ci,
            "precision_at_primary_k_ci": self.precision_at_5_ci,
            "noise_rate": self.noise_rate,
            "distractor_noise_rate": self.distractor_noise_rate,
            "off_corpus_rate": self.off_corpus_rate,
            "off_corpus_measured": self.off_corpus_measured,
        }


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of ``relevant`` documents found in ``retrieved[:k]``."""

    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    top_k = list(retrieved)[:k]
    hits = sum(1 for doc in top_k if doc in relevant_set)
    return hits / len(relevant_set)


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of ``retrieved[:k]`` that are in ``relevant``.

    Divides by ``min(k, len(retrieved))``, not ``k`` — a short results list
    isn't penalised for not having ``k`` items. Empty ``retrieved`` is 0.0
    (no division error).

    IMPORTANT for callers: ``retrieved`` must be the **full** ordered result
    set the system returned, including items you consider noise. Filtering
    non-hits out before calling shrinks the denominator and inflates the
    score toward 1.0 — see the module docstring.
    """

    top_k = list(retrieved)[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant)
    hits = sum(1 for doc in top_k if doc in relevant_set)
    return hits / len(top_k)


def noise_rate(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of ``retrieved[:k]`` that are NOT relevant (``1 - precision_at_k``).

    Diagnostic only. Because this is the exact complement of
    ``precision_at_k`` over the same window, gating on both this and
    precision applies one constraint while appearing to apply two. Gate on
    ``distractor_rate`` instead.
    """

    return 1.0 - precision_at_k(retrieved, relevant, k)


def slot_share(retrieved: Sequence[str], marked: Iterable[str], k: int) -> float:
    """Fraction of the ``retrieved[:k]`` slots occupied by a ``marked`` id.

    The shared shape behind ``distractor_rate`` and ``off_corpus_rate``. Empty
    ``retrieved`` is 0.0 — "nothing returned" is a recall failure, which
    ``recall_at_k`` already reports; double-counting it as noise would make an
    outage indistinguishable from a precision regression.
    """

    top_k = list(retrieved)[:k]
    if not top_k:
        return 0.0
    marked_set = set(marked)
    if not marked_set:
        return 0.0
    hits = sum(1 for doc in top_k if doc in marked_set)
    return hits / len(top_k)


def distractor_rate(retrieved: Sequence[str], distractors: Iterable[str], k: int) -> float:
    """Fraction of ``retrieved[:k]`` that are **labeled** distractors.

    Independent of precision: a result set can contain zero relevant items and
    zero distractors (all junk), or all relevant items and zero distractors.
    """

    return slot_share(retrieved, distractors, k)


def off_corpus_rate(retrieved: Sequence[str], off_corpus: Iterable[str], k: int) -> float:
    """Fraction of ``retrieved[:k]`` the caller marked as off-corpus.

    Catches results the labels cannot speak to at all: memories that already
    existed in the tenant, duplicates left behind by a failed ingest, or rows
    written by another eval. Those must count against the run rather than be
    silently dropped, or a polluted workspace scores perfectly.

    The caller marks the slots because only it can resolve a returned item back
    to a labeled memory; passing a global "known refs" set here would
    misclassify the synthetic placeholder ids a caller substitutes for
    below-threshold or duplicate slots.
    """

    return slot_share(retrieved, off_corpus, k)


def mrr(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """Reciprocal rank of the first relevant doc, 0 if none found."""

    relevant_set = set(relevant)
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant_set:
            return 1.0 / rank
    return 0.0


def _dcg_at_k(grades: Sequence[float], k: int) -> float:
    s = 0.0
    for i, grade in enumerate(grades[:k], start=1):
        if not math.isfinite(grade) or grade > _MAX_GRADE:
            raise ValueError(
                f"relevance grade {grade!r} exceeds the supported maximum {_MAX_GRADE}; "
                "graded-relevance scales are small (e.g. 0/1/2) — check the fixture"
            )
        # Standard log-base-2 discount; gain = 2^grade - 1 for graded relevance.
        s += (2.0**grade - 1.0) / math.log2(i + 1)
    return s


def ndcg_at_k(
    retrieved: Sequence[str],
    qrels: Mapping[str, float],
    k: int,
) -> float:
    """nDCG@k against graded ``qrels`` (``{doc_id: grade}``).

    Unjudged documents in ``retrieved`` contribute zero gain. The
    ideal ordering is ``qrels`` sorted by grade descending.
    """

    if not qrels:
        return 0.0
    grades = [float(qrels.get(doc, 0.0)) for doc in retrieved]
    dcg = _dcg_at_k(grades, k)
    ideal = sorted(qrels.values(), reverse=True)
    idcg = _dcg_at_k([float(g) for g in ideal], k)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def score_run(
    *,
    per_query_retrieved: Mapping[str, Sequence[str]],
    per_query_qrels: Mapping[str, Mapping[str, float]],
    ks: Sequence[int] = (1, 5, 10, 32),
    ndcg_k: int = 10,
    per_query_distractors: Mapping[str, Sequence[str]] | None = None,
    per_query_off_corpus: Mapping[str, Sequence[str]] | None = None,
    primary_k: int = 5,
) -> RetrievalScores:
    """Aggregate Recall@k, MRR, nDCG@k, precision and noise across a run.

    ``per_query_retrieved`` maps ``query_id -> ordered list of doc ids``. It
    must contain every id the system returned within the judged window,
    including ones the caller believes are noise.
    ``per_query_qrels`` maps ``query_id -> {doc_id: grade}`` (grade > 0
    is relevant).

    ``per_query_distractors`` supplies the labeled must-not-recall ids used by
    ``distractor_noise_rate``. ``per_query_off_corpus`` supplies the ids the
    caller resolved to no labeled memory, used by ``off_corpus_rate``; when
    omitted, ``off_corpus_rate`` is 0.0 and ``off_corpus_measured`` is False so
    a consumer can tell "clean" from "not measured".

    ``primary_k`` is the window for ``noise_rate`` / ``distractor_noise_rate``
    / ``off_corpus_rate`` and the pooled precision CI. It is always included
    in the ``precision_at_k`` / ``recall_at_k`` breakdown so a gate reading
    ``precision_at_k[primary_k]`` can never find it missing.

    Queries present in retrieved but not in qrels are skipped. Queries
    in qrels but missing from retrieved contribute zeros.
    """

    if primary_k < 1:
        raise ValueError(f"primary_k must be >= 1, got {primary_k}")
    effective_ks = sorted({*ks, primary_k})
    distractors_by_query = per_query_distractors or {}
    off_corpus_by_query = per_query_off_corpus
    off_corpus_measured = off_corpus_by_query is not None

    qids = set(per_query_qrels.keys()) & set(per_query_retrieved.keys())
    if not qids:
        # No judged queries: report zeros with the maximally-uncertain CI.
        # Callers gating on any noise metric MUST also require
        # ``n_queries > 0``; a zero-query run is "no evidence", not "clean".
        return RetrievalScores(
            recall_at_k={k: 0.0 for k in effective_ks},
            mrr=0.0,
            ndcg_at_10=0.0,
            n_queries=0,
            precision_at_k={k: 0.0 for k in effective_ks},
            noise_rate=0.0,
            precision_at_5_ci=wilson_ci(0, 0),
            primary_k=primary_k,
            ndcg_k=ndcg_k,
            precision_at_primary_k_micro=0.0,
            distractor_noise_rate=0.0,
            off_corpus_rate=0.0,
            off_corpus_measured=off_corpus_measured,
        )

    recall_totals = {k: 0.0 for k in effective_ks}
    precision_totals = {k: 0.0 for k in effective_ks}
    mrr_total = 0.0
    ndcg_total = 0.0
    noise_total = 0.0
    distractor_total = 0.0
    off_corpus_total = 0.0
    # Pooled Bernoulli counts over primary-k slots, for the precision CI.
    pooled_hits = 0
    pooled_slots = 0
    for qid in qids:
        retrieved = list(per_query_retrieved[qid])
        qrels = per_query_qrels[qid]
        relevant_docs = [d for d, g in qrels.items() if g > 0]
        for k in effective_ks:
            recall_totals[k] += recall_at_k(retrieved, relevant_docs, k)
            precision_totals[k] += precision_at_k(retrieved, relevant_docs, k)
        mrr_total += mrr(retrieved, relevant_docs)
        ndcg_total += ndcg_at_k(retrieved, qrels, ndcg_k)
        noise_total += noise_rate(retrieved, relevant_docs, primary_k)
        distractor_total += distractor_rate(retrieved, distractors_by_query.get(qid, ()), primary_k)
        if off_corpus_by_query is not None:
            off_corpus_total += off_corpus_rate(
                retrieved, off_corpus_by_query.get(qid, ()), primary_k
            )
        window = retrieved[:primary_k]
        relevant_set = set(relevant_docs)
        pooled_slots += len(window)
        pooled_hits += sum(1 for doc in window if doc in relevant_set)

    n = len(qids)
    return RetrievalScores(
        recall_at_k={k: v / n for k, v in recall_totals.items()},
        mrr=mrr_total / n,
        ndcg_at_10=ndcg_total / n,
        n_queries=n,
        precision_at_k={k: v / n for k, v in precision_totals.items()},
        noise_rate=noise_total / n,
        precision_at_5_ci=wilson_ci(pooled_hits, pooled_slots),
        primary_k=primary_k,
        ndcg_k=ndcg_k,
        precision_at_primary_k_micro=(pooled_hits / pooled_slots) if pooled_slots else 0.0,
        distractor_noise_rate=distractor_total / n,
        off_corpus_rate=(off_corpus_total / n) if off_corpus_measured else 0.0,
        off_corpus_measured=off_corpus_measured,
    )


__all__ = [
    "RetrievalScores",
    "distractor_rate",
    "mrr",
    "ndcg_at_k",
    "noise_rate",
    "off_corpus_rate",
    "precision_at_k",
    "recall_at_k",
    "score_run",
    "slot_share",
]
