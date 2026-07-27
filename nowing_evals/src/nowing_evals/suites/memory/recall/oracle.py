"""Recall-hit classification for the memory-recall benchmark (AC-3, RS-2).

Two things this module is careful about, both from the Story 3.9 review:

**The oracle classifies, it does not filter.** AC-3 says a memory is a hit iff
it is inside ``top_k`` *and* clears the similarity threshold, and that
"everything else in the returned set is noise". Callers must therefore keep
non-hits in the scored result set — dropping them shrinks the precision/noise
denominator and drives both toward a perfect score. See
:func:`judge_returned_items`, which returns one entry per returned slot.

**The score signal is decided once per run, not per query.** Story 3.14
(Task 1) replaced the backend's fake ``score=0.0`` placeholder with real,
distinct RRF similarities, so a live run now normally carries a usable
signal. The degraded path is still reachable — a stale deployment, or a
corpus that genuinely ties on every score — and it must remain an explicit,
recorded, run-level fact rather than a per-query heuristic that silently
flips definitions, and never one that reads "every score is 0.0" as "every
result is a hit".
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

_MAX_TOP_K = 5

#: Every returned slot is judged on rank alone; no usable similarity signal.
ORACLE_MODE_RANK_ONLY = "rank_only"
#: The response carries a usable similarity score, so the threshold applies.
ORACLE_MODE_SCORE_THRESHOLD = "score_threshold"

#: Placeholder ref substituted for a returned item that is inside ``top_k`` but
#: fails the similarity threshold. It occupies a denominator slot (AC-3: it is
#: noise) while being unable to match any qrel or distractor label.
BELOW_THRESHOLD_REF = "__below_threshold__"


def clamp_top_k(top_k: int) -> int:
    """Validate a requested result depth and clamp it to the RS-2 maximum."""

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    return min(top_k, _MAX_TOP_K)


def validate_min_similarity(min_similarity: float) -> float:
    """Validate a similarity threshold up front, before any network call."""

    if isinstance(min_similarity, bool):
        raise ValueError("min_similarity must be a finite number between 0 and 1")
    try:
        threshold = float(min_similarity)
    except (TypeError, ValueError) as exc:
        raise ValueError("min_similarity must be a finite number between 0 and 1") from exc
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("min_similarity must be a finite number between 0 and 1")
    return threshold


def _numeric_score(item: Mapping[str, Any]) -> float | None:
    score = item.get("score")
    if score is None or isinstance(score, bool):
        return None
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def resolve_oracle_mode(all_returned_items: Sequence[Mapping[str, Any]]) -> str:
    """Decide the oracle mode once for a whole run.

    ``score_threshold`` requires a usable similarity signal, which means at
    least two distinct finite scores across the run. A response where every
    score is identical (a stale deployment still serialising a constant
    ``0.0``, or a corpus that genuinely ties) carries no ordering information
    beyond rank, so the run degrades to ``rank_only`` — recorded in the
    artifact so the gate can verify which definition produced the numbers.

    Note the safety direction: under ``rank_only`` every slot inside ``top_k``
    is *judged*, not *awarded*. Relevance still comes from the qrels, so a
    degraded run cannot inflate its own score.
    """

    scores = [
        score for score in (_numeric_score(item) for item in all_returned_items) if score is not None
    ]
    if len(set(scores)) < 2:
        return ORACLE_MODE_RANK_ONLY
    return ORACLE_MODE_SCORE_THRESHOLD


def is_recall_hit(
    item: Mapping[str, Any],
    *,
    rank: int,
    top_k: int = _MAX_TOP_K,
    mode: str = ORACLE_MODE_RANK_ONLY,
    min_similarity: float | None = None,
) -> bool:
    """Return whether an ordered search result qualifies as an oracle hit.

    Ranks are one-based. Beyond ``top_k`` is never a hit (RS-2). Under
    ``score_threshold`` an item must additionally carry a finite score at or
    above ``min_similarity``; a missing or unusable score is *not* a hit in
    that mode, because silently accepting it would defeat the threshold.
    """

    effective_top_k = clamp_top_k(top_k)
    if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
        raise ValueError("rank must be a positive integer")
    if rank > effective_top_k:
        return False
    if mode == ORACLE_MODE_RANK_ONLY:
        return True
    if mode != ORACLE_MODE_SCORE_THRESHOLD:
        raise ValueError(f"unsupported oracle mode {mode!r}")
    threshold = validate_min_similarity(0.0 if min_similarity is None else min_similarity)
    score = _numeric_score(item)
    if score is None:
        return False
    return score >= threshold


def judge_returned_items(
    items: Sequence[Mapping[str, Any]],
    *,
    top_k: int,
    mode: str,
    min_similarity: float | None,
    resolve_ref,
) -> list[dict[str, Any]]:
    """Judge every returned slot inside ``top_k`` and keep them all.

    Returns one entry per judged slot, in rank order, each carrying:

    ``rank``
        one-based position in the response
    ``scored_ref``
        the ref used for scoring. The resolved corpus ref for a hit; a
        distinct synthetic ref otherwise, so the slot still counts in the
        precision/noise denominator without being able to match a label.
    ``memory_ref``
        the resolved corpus ref, or ``None`` when the item maps to no labeled
        memory (which ``off_corpus_rate`` then counts).
    ``hit``
        whether the oracle classified the slot as a hit
    ``off_corpus``
        whether the item resolved to no labeled memory

    Duplicates are preserved as separate slots: a response that returns the
    same memory three times wasted three slots, and collapsing them would
    reward that.
    """

    effective_top_k = clamp_top_k(top_k)
    judged: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for rank, item in enumerate(items[:effective_top_k], start=1):
        hit = is_recall_hit(
            item, rank=rank, top_k=effective_top_k, mode=mode, min_similarity=min_similarity
        )
        memory_ref = resolve_ref(item)
        off_corpus = memory_ref is None
        if not hit:
            scored_ref = f"{BELOW_THRESHOLD_REF}#{rank}"
        elif off_corpus:
            scored_ref = f"__off_corpus__#{rank}"
        elif memory_ref in seen_refs:
            # A repeat of an already-credited memory still burns a slot, so it
            # must not be credited twice as a relevant hit.
            scored_ref = f"__duplicate__#{rank}"
        else:
            scored_ref = memory_ref
            seen_refs.add(memory_ref)
        judged.append(
            {
                "rank": rank,
                "scored_ref": scored_ref,
                "memory_ref": memory_ref,
                "hit": hit,
                "off_corpus": off_corpus,
            }
        )
    return judged


__all__ = [
    "BELOW_THRESHOLD_REF",
    "ORACLE_MODE_RANK_ONLY",
    "ORACLE_MODE_SCORE_THRESHOLD",
    "clamp_top_k",
    "is_recall_hit",
    "judge_returned_items",
    "resolve_oracle_mode",
    "validate_min_similarity",
]
