"""Named, versioned question sets for the decision service (AD-J5)."""

from __future__ import annotations

from app.services.decision.questions import (
    content_filter,
    entity_match,
    intent_classify,
    subagent_routing,
)
from app.services.decision.questions.registry import QuestionRegistry, QuestionSet

_question_registry: QuestionRegistry | None = None


def get_question_registry() -> QuestionRegistry:
    """Process-wide registry with the built-in question sets loaded."""
    global _question_registry
    if _question_registry is None:
        registry = QuestionRegistry()
        registry.register(
            "subagent_routing",
            subagent_routing.QUESTIONS,
            version=subagent_routing.VERSION,
        )
        registry.register(
            "entity_match",
            entity_match.QUESTIONS,
            version=entity_match.VERSION,
        )
        registry.register(
            "content_filter",
            content_filter.QUESTIONS,
            version=content_filter.VERSION,
        )
        registry.register(
            "intent_classify",
            intent_classify.QUESTIONS,
            version=intent_classify.VERSION,
        )
        _question_registry = registry
    return _question_registry


__all__ = [
    "QuestionRegistry",
    "QuestionSet",
    "get_question_registry",
]
