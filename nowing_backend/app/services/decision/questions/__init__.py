"""Named, versioned question sets for the decision service (AD-J5)."""

from __future__ import annotations

from app.services.decision.questions import (
    content_filter,
    entity_match,
    entity_match_fanout,
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
            required_state_keys=subagent_routing.REQUIRED_STATE_KEYS,
        )
        registry.register(
            "entity_match",
            entity_match.QUESTIONS,
            version=entity_match.VERSION,
            required_state_keys=entity_match.REQUIRED_STATE_KEYS,
        )
        registry.register(
            "entity_match_fanout",
            entity_match_fanout.QUESTIONS,
            version=entity_match_fanout.VERSION,
            required_state_keys=entity_match_fanout.REQUIRED_STATE_KEYS,
        )
        registry.register(
            "content_filter",
            content_filter.QUESTIONS,
            version=content_filter.VERSION,
            required_state_keys=content_filter.REQUIRED_STATE_KEYS,
        )
        registry.register(
            "intent_classify",
            intent_classify.QUESTIONS,
            version=intent_classify.VERSION,
            required_state_keys=intent_classify.REQUIRED_STATE_KEYS,
        )
        _question_registry = registry
    return _question_registry


__all__ = [
    "QuestionRegistry",
    "QuestionSet",
    "get_question_registry",
]
