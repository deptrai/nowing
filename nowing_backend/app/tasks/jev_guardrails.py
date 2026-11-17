"""Jev Guardrails for Social Stream Ingestion (Story 40.4).

Provides PII redaction (CCCD/CMND) and candidate entity deduplication
logic via DecisionService according to Epic 40 / AD-J4.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

from app.config.decision import decision_enabled, decision_task_enabled
from app.services.decision.gate import ConfidenceGate
from app.services.decision.questions import get_question_registry
from app.services.decision.questions.entity_match_fanout import (
    NO_MATCH_DESCRIPTION,
    NO_MATCH_ID,
)
from app.services.decision.service import get_decision_service

logger = logging.getLogger(__name__)

# Vietnamese National Identity Numbers: 9-digit (CMND cũ) or 12-digit (CCCD mới)
PII_ID_REGEX = re.compile(r"\b(?:\d{9}|\d{12})\b")


def sanitize_pii_content(text: str | None) -> str:
    """Redact sensitive identity numbers (CCCD/CMND) from candidate text."""
    if not text:
        return ""
    return PII_ID_REGEX.sub("[REDACTED_ID]", text)


def _heuristic_dedup(
    candidate: dict[str, Any],
    existing_entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fallback name/substring heuristic if DecisionService is unavailable."""
    candidate_name = (
        candidate.get("company_name") or candidate.get("author_name") or ""
    ).lower()
    for existing in existing_entities:
        existing_name = (existing.get("company_name") or "").lower()
        if candidate_name and candidate_name == existing_name:
            return {
                "action": "merge",
                "score": 2.0,
                "matched_id": existing.get("id"),
            }
        if (
            candidate_name
            and existing_name
            and (candidate_name in existing_name or existing_name in candidate_name)
        ):
            return {
                "action": "curate",
                "score": 1.0,
                "matched_id": existing.get("id"),
            }
    return {"action": "create", "score": 0.0, "matched_id": None}


async def evaluate_entity_dedup(
    candidate: dict[str, Any],
    existing_entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score candidate against existing entities using DecisionService.

    Returns:
        dict with:
            - 'action': 'merge' (>= 1.5), 'curate' (0.5 - 1.5), or 'create' (< 0.5)
            - 'score': float
            - 'matched_id': int | None
    """
    if not existing_entities:
        return {"action": "create", "score": 0.0, "matched_id": None}

    # Best-effort matching via DecisionService entity_match_fanout
    try:
        if not (decision_enabled() and decision_task_enabled("entity")):
            return _heuristic_dedup(candidate, existing_entities)

        candidates = {
            str(e.get("id", idx)): e for idx, e in enumerate(existing_entities)
        }
        if NO_MATCH_ID in candidates:
            return _heuristic_dedup(candidate, existing_entities)

        qs = get_question_registry().get_set("entity_match_fanout")
        template = qs.questions["match_decision"]
        criteria = {
            cid: e.get("company_name") or str(cid) for cid, e in candidates.items()
        }
        criteria[NO_MATCH_ID] = NO_MATCH_DESCRIPTION
        question = dataclasses.replace(template, criteria=criteria)

        result = await get_decision_service().decide(
            {"anchor": candidate, "candidates": candidates},
            {"match_decision": question},
            task="entity",
            question_set=f"{qs.name}@{qs.version}",
            required_state_keys=qs.required_state_keys,
        )
        answer = result.answers.get("match_decision")
        chosen = str(answer.value) if answer is not None else NO_MATCH_ID
        gate = ConfidenceGate.for_task("entity")

        if gate.passes(answer) and chosen in candidates:
            matched_entity = candidates[chosen]
            return {
                "action": "merge",
                "score": 2.0,
                "matched_id": matched_entity.get("id"),
            }
        return {"action": "create", "score": 0.0, "matched_id": None}
    except Exception as exc:
        logger.warning("Jev entity dedup failed, falling back to heuristic: %s", exc)
        return _heuristic_dedup(candidate, existing_entities)
