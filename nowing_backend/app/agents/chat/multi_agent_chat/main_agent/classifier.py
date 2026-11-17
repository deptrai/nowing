"""Inbound & research intent classifier (AI-39.9).

Upgrades research intent detection to prefer the DecisionService intent
question set ('intent_classify@1.0.0') via classify_intent when enabled,
falling back to regex keywords on disabled, below-gate, or error.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import decision as decision_config
from app.services.auto_reply_agent import InboundIntentClassifier
from app.services.intent_classification import classify_intent

logger = logging.getLogger(__name__)

_RESEARCH_PATTERNS = [
    re.compile(
        r"\b(nghiên cứu|research|tìm hiểu sâu|phân tích chi tiết|khảo sát|tổng quan ngành|báo cáo thị trường|due diligence)\b",
        re.IGNORECASE,
    ),
]


def _is_researchy(text: str) -> bool:
    """Keyword/regex fallback for deep research intent detection."""
    if not text or not isinstance(text, str):
        return False
    return any(p.search(text) for p in _RESEARCH_PATTERNS)


async def is_researchy(
    text: str,
    *,
    session: AsyncSession | None = None,
    workspace_id: int | None = None,
    user_id: UUID | None = None,
    client_id: str | None = None,
) -> bool:
    """Classify whether user input has deep-research intent (AI-39.9).

    Prefers the DecisionService intent question set ('intent_classify')
    via classify_intent when DECISION_ENABLED and DECISION_INTENT_ENABLED are active.
    Falls back to regex keywords on below-gate, disabled, or error.
    """
    if not text or not isinstance(text, str):
        return False

    if decision_config.decision_enabled() and decision_config.decision_task_enabled(
        "intent"
    ):
        try:
            payload = await classify_intent(
                text,
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                client_id=client_id,
            )
            if payload is not None:
                label = payload.get("label")
                if label in ("search", "comparison"):
                    return True
                if label in ("chitchat", "action", "complaint", "feedback"):
                    return False
        except Exception:
            logger.warning(
                "[is_researchy] Jev intent check failed; falling back to regex",
                exc_info=True,
            )

    return _is_researchy(text)


__all__ = [
    "InboundIntentClassifier",
    "_is_researchy",
    "is_researchy",
]
