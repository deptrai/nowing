"""Entity resolution helpers — two-stage dedup via ``DecisionService`` (Story 39.3).

Stage 1 (caller-owned heuristic) narrows N entities → K candidate pairs.
Stage 2 (this module) issues ONE ``decide()`` per anchor asking which of
its heuristic-surviving candidates it matches — Jev never re-scores pairs
the heuristic already rejected. Pairwise ``Score`` matching covers 1:1
verification contexts (e.g. corporate registry verification).

Everything is advisory: ``DecisionError``/``InvalidDecisionAnswer``
propagate to the caller, which keeps its existing behavior. Inside
``refine_entity_groups`` a per-anchor failure skips that anchor and
``MAX_CONSECUTIVE_ERRORS`` consecutive failures abort the remaining
anchors so a dead backend is not paid 2 legs per remaining anchor.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from app.services.decision.errors import DecisionError
from app.services.decision.gate import ConfidenceGate
from app.services.decision.questions import get_question_registry
from app.services.decision.questions.entity_match_fanout import (
    NO_MATCH_DESCRIPTION,
    NO_MATCH_ID,
)
from app.services.decision.service import get_decision_service
from app.services.decision.types import Answer

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# jev-ultrafast's action-space bound: one Choice criteria set may carry at
# most this many candidate ids (+ ``no_match``).
MAX_CANDIDATES_PER_ANCHOR = 250
# Per-run paid-call bound: anchors beyond this keep the heuristic result.
MAX_DECISION_CALLS_PER_RUN = 50
# Consecutive ``DecisionError`` abort — a dead backend must not be paid
# once (let alone twice via the fallback leg) per remaining anchor.
MAX_CONSECUTIVE_ERRORS = 3

# entity_match rubric bands: >= 1.5 same entity, < 0.5 different.
_AUTO_MERGE_SCORE = 1.5
_SEPARATE_SCORE = 0.5


class EntityVerdict(StrEnum):
    """Tri-state outcome of a pairwise entity match."""

    AUTO_MERGE = "auto_merge"
    REVIEW = "review"
    SEPARATE = "separate"


@dataclass(frozen=True)
class EntityMatchResult:
    """Pairwise verdict plus the raw answer for callers that log it."""

    verdict: EntityVerdict
    answer: Answer | None


@dataclass
class RefineStats:
    """What the fan-out stage did — logged by the caller per run.

    Gate failures and explicit ``no_match`` both count as ``no_match``
    here; the per-call ``[entity_match]`` log line carries ``passes``
    so the two remain distinguishable at decision granularity.
    """

    calls: int = 0
    confirmed: int = 0
    no_match: int = 0
    errors: int = 0
    skipped_cap: int = 0
    aborted: bool = False


async def score_entity_pair(
    entity_a: dict[str, Any],
    entity_b: dict[str, Any],
    *,
    session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    client_id: str | None = None,
    anchor_id: str | None = None,
) -> EntityMatchResult:
    """Score whether two entity dicts describe the same real-world entity.

    Uses the registered ``entity_match`` Score set (0=different,
    1=uncertain, 2=same). Verdict bands apply to the score only when the
    answer clears the ``entity`` confidence gate; a gate failure is
    ``REVIEW`` — an unreliable answer is definitionally uncertain.

    Raises ``DecisionError``/``InvalidDecisionAnswer`` — callers fall
    back to their existing behavior.
    """
    qs = get_question_registry().get_set("entity_match")
    result = await get_decision_service().decide(
        {"entity_a": entity_a, "entity_b": entity_b},
        qs.questions,
        task="entity",
        question_set=f"{qs.name}@{qs.version}",
        required_state_keys=qs.required_state_keys,
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
        client_id=client_id,
    )
    answer = result.answers.get("is_same")
    gate = ConfidenceGate.for_task("entity")
    if not gate.passes(answer):
        verdict = EntityVerdict.REVIEW
    else:
        score = float(answer.value)
        if score >= _AUTO_MERGE_SCORE:
            verdict = EntityVerdict.AUTO_MERGE
        elif score < _SEPARATE_SCORE:
            verdict = EntityVerdict.SEPARATE
        else:
            verdict = EntityVerdict.REVIEW
    logger.info(
        "[entity_match] pairwise anchor=%s score=%s confidence=%s verdict=%s",
        anchor_id,
        getattr(answer, "value", None),
        getattr(answer, "confidence", None),
        verdict.value,
    )
    return EntityMatchResult(verdict=verdict, answer=answer)


async def confirm_entity_match(
    anchor: dict[str, Any],
    candidates: Mapping[str, dict[str, Any]],
    *,
    descriptions: Mapping[str, str] | None = None,
    session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    client_id: str | None = None,
    anchor_id: str | None = None,
) -> str | None:
    """One ``decide()``: which candidate id matches ``anchor``, or ``None``.

    ``candidates`` maps candidate id → entity dict (the state Jev sees),
    capped at ``MAX_CANDIDATES_PER_ANCHOR`` entries — callers should pass
    them ordered by relevance (``refine_entity_groups`` truncates the
    head). ``descriptions`` optionally maps id → short criteria text;
    missing entries fall back to the id itself. ``no_match`` is always
    appended last so ``MockBackend`` (which answers the first option)
    yields a deterministic confirmed match in tests.

    Returns ``None`` for ``no_match``, a gate failure, or an answer whose
    value is not a candidate id. Raises ``DecisionError``/
    ``InvalidDecisionAnswer`` — callers fall back.
    """
    if not candidates:
        return None
    if NO_MATCH_ID in candidates:
        raise DecisionError(
            f"candidate id {NO_MATCH_ID!r} collides with the no-match "
            "sentinel",
            code="invalid_request",
        )
    if len(candidates) > MAX_CANDIDATES_PER_ANCHOR:
        candidates = dict(
            list(candidates.items())[:MAX_CANDIDATES_PER_ANCHOR]
        )
    qs = get_question_registry().get_set("entity_match_fanout")
    template = qs.questions["match_decision"]
    descriptions = descriptions or {}
    criteria = {cid: descriptions.get(cid, cid) for cid in candidates}
    criteria[NO_MATCH_ID] = NO_MATCH_DESCRIPTION
    question = dataclasses.replace(template, criteria=criteria)
    result = await get_decision_service().decide(
        {"anchor": anchor, "candidates": dict(candidates)},
        {"match_decision": question},
        task="entity",
        question_set=f"{qs.name}@{qs.version}",
        required_state_keys=qs.required_state_keys,
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
        client_id=client_id,
    )
    answer = result.answers.get("match_decision")
    chosen = str(answer.value) if answer is not None else NO_MATCH_ID
    gate = ConfidenceGate.for_task("entity")
    passes = gate.passes(answer)
    confirmed = passes and chosen in candidates
    logger.info(
        "[entity_match] fanout anchor=%s chosen=%s confidence=%s "
        "passes=%s action=%s",
        anchor_id,
        chosen,
        getattr(answer, "confidence", None),
        passes,
        "merge" if confirmed else "separate",
    )
    return chosen if confirmed else None


async def refine_entity_groups[T](
    items: Sequence[T],
    candidate_pairs: Mapping[int, Sequence[int]],
    *,
    id_of: Callable[[T], str],
    state_of: Callable[[T], dict[str, Any]],
    describe: Callable[[T], str],
    merge_group: Callable[[list[T]], T],
    session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    client_id: str | None = None,
    max_calls: int = MAX_DECISION_CALLS_PER_RUN,
    max_seconds: float | None = None,
) -> tuple[list[T], RefineStats]:
    """Stage-2 executor: per-anchor Jev confirm → union-find → merge.

    ``candidate_pairs`` maps anchor index → surviving candidate indices
    (each unordered pair appears under exactly one anchor). Anchors run
    in descending candidate-count order, capped at ``max_calls``; the
    remainder keeps the heuristic result. A ``DecisionError`` skips that
    anchor; ``MAX_CONSECUTIVE_ERRORS`` in a row aborts the rest.
    ``max_seconds`` bounds wall-clock: once exceeded the remaining
    anchors keep the heuristic result and ``stats.aborted`` is set
    (``None`` = no deadline).
    Confirmed edges are unioned, then each multi-item component is
    reduced through ``merge_group``. Single pass — merged entities are
    not re-evaluated.

    Unexpected (non-``DecisionError``) exceptions propagate — the
    caller's outer fail-open wrapper decides whether to keep input.
    """
    stats = RefineStats()
    entities = list(items)
    if len(entities) < 2 or not candidate_pairs:
        return entities, stats

    anchors = sorted(
        (i for i, cands in candidate_pairs.items() if cands),
        key=lambda i: (-len(candidate_pairs[i]), i),
    )
    if len(anchors) > max_calls:
        stats.skipped_cap = len(anchors) - max_calls
        anchors = anchors[: max(0, max_calls)]

    id_to_idx = {id_of(item): idx for idx, item in enumerate(entities)}
    parent = list(range(len(entities)))

    def _find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def _union(i: int, j: int) -> None:
        ri, rj = _find(i), _find(j)
        if ri != rj:
            parent[ri] = rj

    deadline = None if max_seconds is None else time.monotonic() + max_seconds
    consecutive_errors = 0
    for pos, anchor_idx in enumerate(anchors):
        if deadline is not None and time.monotonic() >= deadline:
            stats.aborted = True
            logger.warning(
                "[entity_match] wall-clock deadline %.1fs exceeded — "
                "aborting %d remaining anchors",
                max_seconds,
                len(anchors) - pos,
            )
            break
        cand_indices = list(candidate_pairs[anchor_idx])[
            :MAX_CANDIDATES_PER_ANCHOR
        ]
        cand_entities = {id_of(entities[j]): entities[j] for j in cand_indices}
        descriptions = {cid: describe(item) for cid, item in cand_entities.items()}
        try:
            chosen = await confirm_entity_match(
                state_of(entities[anchor_idx]),
                {cid: state_of(item) for cid, item in cand_entities.items()},
                descriptions=descriptions,
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                client_id=client_id,
                anchor_id=id_of(entities[anchor_idx]),
            )
        except DecisionError:
            stats.calls += 1
            stats.errors += 1
            consecutive_errors += 1
            logger.warning(
                "[entity_match] decide failed for anchor %s — skipping",
                id_of(entities[anchor_idx]),
                exc_info=True,
            )
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                stats.aborted = True
                logger.warning(
                    "[entity_match] %d consecutive decision errors — "
                    "aborting %d remaining anchors",
                    consecutive_errors,
                    len(anchors) - pos - 1,
                )
                break
            continue
        stats.calls += 1
        consecutive_errors = 0
        if chosen is None:
            stats.no_match += 1
            continue
        chosen_idx = id_to_idx.get(chosen)
        if chosen_idx is None:
            stats.no_match += 1
            continue
        _union(anchor_idx, chosen_idx)
        stats.confirmed += 1

    if stats.confirmed == 0:
        return entities, stats

    components: dict[int, list[T]] = {}
    for idx, item in enumerate(entities):
        components.setdefault(_find(idx), []).append(item)

    merged: list[T] = []
    for idx in range(len(entities)):
        root = _find(idx)
        if idx != root:
            continue
        group = components[root]
        merged.append(group[0] if len(group) == 1 else merge_group(group))
    return merged, stats


__all__ = [
    "MAX_CANDIDATES_PER_ANCHOR",
    "MAX_CONSECUTIVE_ERRORS",
    "MAX_DECISION_CALLS_PER_RUN",
    "EntityMatchResult",
    "EntityVerdict",
    "RefineStats",
    "confirm_entity_match",
    "refine_entity_groups",
    "score_entity_pair",
]
