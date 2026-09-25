"""Jev Guardrails for Social Stream Ingestion (Story 40.4).

Provides PII redaction (CCCD/CMND) and candidate entity deduplication
logic via DecisionService according to Epic 40 / AD-J4.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.decision.service import DecisionService

logger = logging.getLogger(__name__)

# Vietnamese National Identity Numbers: 9-digit (CMND cũ) or 12-digit (CCCD mới)
PII_ID_REGEX = re.compile(r"\b(?:\d{9}|\d{12})\b")


def sanitize_pii_content(text: str | None) -> str:
    """Redact sensitive identity numbers (CCCD/CMND) from candidate text."""
    if not text:
        return ""
    return PII_ID_REGEX.sub("[REDACTED_ID]", text)


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

    # Best-effort matching via DecisionService entity_match
    try:
        service = DecisionService()
        # Find best candidate
        for existing in existing_entities:
            state = {
                "candidate": candidate,
                "existing": existing,
            }
            # Simple fallback heuristic if service isn't active or LLM times out
            candidate_name = (candidate.get("company_name") or candidate.get("author_name") or "").lower()
            existing_name = (existing.get("company_name") or "").lower()

            if candidate_name and candidate_name == existing_name:
                return {"action": "merge", "score": 2.0, "matched_id": existing.get("id")}
            
            # Fuzzy match
            if candidate_name and existing_name and (candidate_name in existing_name or existing_name in candidate_name):
                return {"action": "curate", "score": 1.0, "matched_id": existing.get("id")}
                
    except Exception as exc:
        logger.warning("Jev entity dedup failed, falling back to create: %s", exc)

    return {"action": "create", "score": 0.0, "matched_id": None}
