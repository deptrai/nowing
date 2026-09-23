"""Content guardrails — one ``decide()`` runs the 3-Noul ``content_filter``
battery (``is_relevant`` / ``contains_prompt_injection`` /
``contains_sensitive``) and maps it to a ``PASS``/``DROP``/``MASK``
verdict (Story 39.4).

Fail-open everywhere: any ``DecisionError``/``InvalidDecisionAnswer`` or
unexpected exception yields ``PASS`` for that item (logged, never
propagated) so a dead backend silently disables filtering instead of
breaking search, ingest, or chat persistence. When the master or
``filter`` task flag is off, zero work happens — no state is built and
no paid call is made.

Verdict priority is ``DROP`` > ``MASK``: prompt injection always drops;
``is_relevant`` only applies on the ``rag`` surface where a real query
exists; ``contains_sensitive`` masks via ``redact_pii`` — Jev decides
*whether* content is sensitive, the existing regex masker does the
rewrite. If masking itself fails on a known-sensitive passage we DROP —
passing it through unmasked is the worst outcome.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

import app.config.decision as decision_config
from app.services.decision.gate import ConfidenceGate
from app.services.decision.questions import get_question_registry
from app.services.decision.service import get_decision_service
from app.services.decision.types import Answer
from app.services.pii.redact import redact_pii

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Per-call paid bound for search surfaces — docs beyond this pass through
# unguarded and are counted in ``FilterStats.skipped_cap``.
MAX_FILTER_CALLS = 20
# Ingest runs are bigger — one run may carry hundreds of chunks.
MAX_INGEST_FILTER_CALLS = 50
# Concurrent decide() calls inside one filter_passages batch.
FILTER_CONCURRENCY = 10
# Long passages are truncated before hitting the backend.
_MAX_PASSAGE_CHARS = 4000
# redact_pii context — BĐS/lead text profile is the closest existing fit.
_MASK_CONTEXT = "lead_enrichment"


class GuardrailAction(StrEnum):
    """What the caller should do with the checked passage."""

    PASS = "pass"
    DROP = "drop"
    MASK = "mask"


@dataclass(frozen=True)
class PassageVerdict:
    """Guardrail outcome for one passage.

    ``masked_text`` is populated only for ``MASK`` — it is the masked form
    of exactly the checked text, so callers with nested fields (e.g. a
    doc's ``chunks[]``) must mask each field separately rather than reuse
    it. ``error`` records the fail-open trigger when a decision/backend
    failure produced a ``PASS``.
    """

    action: GuardrailAction
    reasons: tuple[str, ...] = ()
    masked_text: str | None = None
    answers: Mapping[str, Answer] = field(default_factory=dict)
    error: str | None = None


_PASS_VERDICT = PassageVerdict(action=GuardrailAction.PASS)


@dataclass
class FilterStats:
    """Aggregate counters for one ``filter_passages`` run."""

    calls: int = 0
    dropped: int = 0
    masked: int = 0
    passed: int = 0
    errors: int = 0
    skipped_cap: int = 0


def _noul_yes(answer: Answer | None, threshold: float) -> bool:
    """True when a ``noul`` answer's ``value`` (P(yes)) >= threshold."""
    if answer is None or answer.kind != "noul":
        return False
    value = answer.value
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return False
    return float(value) >= threshold


async def check_passage(
    passage: str,
    *,
    query: str = "",
    surface: str = "rag",
    session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    client_id: str | None = None,
) -> PassageVerdict:
    """Run the ``content_filter`` battery on one passage → verdict.

    Never raises: empty passages, disabled flags, backend errors, and
    malformed answers all resolve to ``PASS``.
    """
    if not passage or not passage.strip():
        return _PASS_VERDICT
    if not (
        decision_config.decision_enabled()
        and decision_config.decision_task_enabled("filter")
    ):
        return _PASS_VERDICT

    try:
        qs = get_question_registry().get_set("content_filter")
        result = await get_decision_service().decide(
            {"query": query or "", "passage": passage[:_MAX_PASSAGE_CHARS]},
            qs.questions,
            task="filter",
            question_set=f"{qs.name}@{qs.version}",
            required_state_keys=qs.required_state_keys,
            session=session,
            workspace_id=workspace_id,
            user_id=user_id,
            client_id=client_id,
        )
        answers = result.answers
        gate = ConfidenceGate.for_task("filter")

        injection = answers.get("contains_prompt_injection")
        sensitive = answers.get("contains_sensitive")
        relevant = answers.get("is_relevant")

        reasons: list[str] = []
        action = GuardrailAction.PASS
        masked_text: str | None = None
        if _noul_yes(injection, gate.threshold):
            action = GuardrailAction.DROP
            reasons.append("prompt_injection")
        elif (
            surface == "rag"
            and bool(query and query.strip())
            and gate.passes_negative(relevant)
        ):
            action = GuardrailAction.DROP
            reasons.append("irrelevant")
        elif _noul_yes(sensitive, gate.threshold):
            try:
                masked_text = redact_pii(passage, context=_MASK_CONTEXT).text
            except Exception:
                masked_text = None
            # Content is known-sensitive — an unmasked pass-through is the
            # worst outcome, so any mask failure (raise or empty result)
            # drops instead of passing.
            if masked_text:
                action = GuardrailAction.MASK
                reasons.append("sensitive")
            else:
                action = GuardrailAction.DROP
                reasons.append("mask_failed")
    except Exception as exc:
        logger.warning(
            "[content_filter] surface=%s check failed — fail-open PASS",
            surface,
            exc_info=True,
        )
        return PassageVerdict(
            action=GuardrailAction.PASS,
            reasons=("error",),
            error=f"{type(exc).__name__}: {exc}",
        )

    logger.info(
        "[content_filter] surface=%s action=%s relevant=%s injection=%s "
        "sensitive=%s reasons=%s",
        surface,
        action.value,
        getattr(relevant, "value", None),
        getattr(injection, "value", None),
        getattr(sensitive, "value", None),
        ",".join(reasons) or "-",
    )
    return PassageVerdict(
        action=action,
        reasons=tuple(reasons),
        masked_text=masked_text,
        answers=answers,
    )


async def filter_passages[T](
    items: Sequence[tuple[T, str]],
    *,
    query: str = "",
    surface: str = "rag",
    max_calls: int = MAX_FILTER_CALLS,
    session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    client_id: str | None = None,
) -> tuple[list[tuple[T, PassageVerdict]], FilterStats]:
    """Check ``(item, text)`` pairs concurrently, preserving input order.

    At most ``max_calls`` non-empty texts are sent to the backend (first
    N in input order); the rest pass through unguarded and count toward
    ``skipped_cap``. Per-item failures are already absorbed by
    ``check_passage`` — they surface as ``PASS`` verdicts with ``error``
    set and increment ``errors``.
    """
    stats = FilterStats()
    results: list[tuple[T, PassageVerdict]] = []
    if not items:
        return results, stats
    if not (
        decision_config.decision_enabled()
        and decision_config.decision_task_enabled("filter")
    ):
        return [(item, _PASS_VERDICT) for item, _ in items], stats

    check_positions = [
        i for i, (_, text) in enumerate(items) if text and text.strip()
    ]
    stats.skipped_cap = max(0, len(check_positions) - max_calls)
    to_check = check_positions[: max(0, max_calls)]

    semaphore = asyncio.Semaphore(FILTER_CONCURRENCY)

    async def _one(pos: int) -> tuple[int, PassageVerdict]:
        _, text = items[pos]
        async with semaphore:
            verdict = await check_passage(
                text,
                query=query,
                surface=surface,
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                client_id=client_id,
            )
        return pos, verdict

    checked: dict[int, PassageVerdict] = {}
    for pos, verdict in await asyncio.gather(*(_one(p) for p in to_check)):
        checked[pos] = verdict
        stats.calls += 1
        if verdict.error is not None:
            stats.errors += 1
        if verdict.action is GuardrailAction.DROP:
            stats.dropped += 1
        elif verdict.action is GuardrailAction.MASK:
            stats.masked += 1
        else:
            stats.passed += 1

    for i, (item, _) in enumerate(items):
        results.append((item, checked.get(i, _PASS_VERDICT)))

    logger.info(
        "[content_filter] surface=%s calls=%d dropped=%d masked=%d passed=%d "
        "errors=%d skipped_cap=%d",
        surface,
        stats.calls,
        stats.dropped,
        stats.masked,
        stats.passed,
        stats.errors,
        stats.skipped_cap,
    )
    return results, stats


__all__ = [
    "FILTER_CONCURRENCY",
    "MAX_FILTER_CALLS",
    "MAX_INGEST_FILTER_CALLS",
    "FilterStats",
    "GuardrailAction",
    "PassageVerdict",
    "check_passage",
    "filter_passages",
]
