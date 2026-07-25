"""Recall-hit oracle (Story 3.9, AC-3 / RS-2).

A returned memory counts as a **hit** iff it sits within ``top_k <= 5`` *and*
its similarity score clears ``min_similarity``. Everything else in the returned
set is **noise**. ``top_k`` is clamped to <= 5 for the gate (RS-2).

Degenerate-score handling (story §9 risk row, verified against the backend)
--------------------------------------------------------------------------
``POST /workspaces/{id}/memories/search`` declares ``score: float`` on every
hit (``app/schemas/memory.py`` -> ``MemorySearchHit``) but the route currently
populates it with a **hardcoded 0.0** for every result
(``app/routes/memories_routes.py`` -> ``search_memory``); the RRF fusion score
computed inside ``MemoryHybridSearch`` is not propagated to the response.

So the score field is *present but carries no signal*. A naive
``score >= min_similarity`` check against the configured 0.30 floor would
classify **every** result as noise, driving precision@5 to 0.0 and making the
gate fail unconditionally — a gate that always fails measures nothing.

The oracle therefore distinguishes two modes:

* **scored mode** — the response carries a real signal (at least one non-zero
  score): apply the full ``rank <= top_k AND score >= min_similarity`` rule.
* **rank-only mode** — no usable signal (scores absent, or uniformly 0.0):
  degrade to ``rank <= top_k`` membership, which is exactly the ordering the
  backend *does* express reliably.

``is_recall_hit`` judges a single item and treats a *missing* score as
rank-only. ``classify_results`` judges a whole response and is what the runner
uses, because uniform-0.0 degeneracy is only detectable across the result set.
Mode selection is recorded in the RunArtifact so a report never silently
implies a similarity threshold was enforced when it was not.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

#: RS-2 hard clamp — the gate never scores beyond the top 5 slots.
MAX_TOP_K = 5


def clamp_top_k(top_k: int) -> int:
    """Clamp ``top_k`` into ``1..MAX_TOP_K`` (RS-2)."""

    return max(1, min(int(top_k), MAX_TOP_K))


def _raw_score(item: Any) -> float | None:
    """Extract a numeric score, or ``None`` when the item carries no score."""

    if not isinstance(item, dict):
        return None
    if "score" not in item:
        return None
    value = item["score"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def scores_are_informative(items: Sequence[Any]) -> bool:
    """Whether a result set's scores carry usable signal.

    ``False`` when no item exposes a numeric score, or when every exposed score
    is 0.0 — the placeholder the backend currently emits. See the module
    docstring: treating that as a real similarity of zero would make every
    result noise.
    """

    scores = [s for s in (_raw_score(i) for i in items) if s is not None]
    if not scores:
        return False
    return any(s > 0.0 for s in scores)


def is_recall_hit(
    item: Any,
    *,
    rank: int,
    top_k: int = MAX_TOP_K,
    min_similarity: float = 0.0,
) -> bool:
    """Classify one returned memory as hit (``True``) or noise (``False``).

    ``rank`` is 1-based position in the ranked response. An item beyond
    ``top_k`` is never a hit, regardless of score. An item with no score field
    falls back to rank-only membership rather than raising or always-failing.
    """

    if rank < 1 or rank > clamp_top_k(top_k):
        return False
    score = _raw_score(item)
    if score is None:
        # No signal for this item — rank membership is all we can honour.
        return True
    return score >= min_similarity


def classify_results(
    items: Sequence[Any],
    *,
    top_k: int = MAX_TOP_K,
    min_similarity: float = 0.0,
) -> tuple[list[Any], bool]:
    """Return ``(hits_within_top_k, similarity_enforced)`` for one response.

    ``similarity_enforced`` is ``False`` when the oracle degraded to rank-only
    because the response carried no usable score signal. The runner records it
    so the artifact never implies a threshold that was not applied.
    """

    effective_k = clamp_top_k(top_k)
    ranked = list(items)[:effective_k]
    enforced = scores_are_informative(ranked)
    threshold = min_similarity if enforced else 0.0
    hits = [
        item
        for rank, item in enumerate(ranked, start=1)
        if is_recall_hit(item, rank=rank, top_k=effective_k, min_similarity=threshold)
    ]
    return hits, enforced


__all__ = [
    "MAX_TOP_K",
    "clamp_top_k",
    "classify_results",
    "is_recall_hit",
    "scores_are_informative",
]
