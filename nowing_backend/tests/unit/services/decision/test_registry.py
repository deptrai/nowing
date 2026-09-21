"""QuestionRegistry — loads the 4 ported question sets, versioned, KeyError."""

from __future__ import annotations

import pytest

from app.services.decision.questions import get_question_registry
from app.services.decision.questions.subagent_routing import SUBAGENT_OPTIONS
from app.services.decision.types import (
    ChoiceQuestion,
    NoulQuestion,
    ScoreQuestion,
)


@pytest.mark.unit
def test_registry_loads_all_question_sets():
    registry = get_question_registry()
    assert set(registry.names()) == {
        "subagent_routing",
        "entity_match",
        "content_filter",
        "intent_classify",
    }


@pytest.mark.unit
def test_registry_get_returns_typed_question_dicts():
    registry = get_question_registry()

    routing = registry.get("subagent_routing")
    assert isinstance(routing["subagent"], ChoiceQuestion)
    assert "none_needed" in routing["subagent"].criteria
    assert len(routing["subagent"].criteria) == 16

    entity = registry.get("entity_match")
    assert isinstance(entity["is_same"], ScoreQuestion)
    assert len(entity["is_same"].criteria) == 3

    content = registry.get("content_filter")
    assert set(content) == {
        "is_relevant",
        "contains_prompt_injection",
        "contains_sensitive",
    }
    assert all(isinstance(q, NoulQuestion) for q in content.values())

    intent = registry.get("intent_classify")
    assert isinstance(intent["intent"], ChoiceQuestion)
    assert intent["intent"].criteria["search"].startswith("Tìm")


@pytest.mark.unit
def test_registry_question_sets_are_versioned():
    registry = get_question_registry()
    for name in registry.names():
        assert registry.version(name) == "1.0.0"
        assert registry.get_set(name).questions == registry.get(name)


@pytest.mark.unit
def test_registry_get_returns_independent_copy():
    """Mutating the returned dict must not corrupt the registry singleton."""
    registry = get_question_registry()
    questions = registry.get("subagent_routing")
    questions.clear()
    assert "subagent" in registry.get("subagent_routing")


@pytest.mark.unit
def test_registry_unknown_name_raises_keyerror_with_available():
    registry = get_question_registry()
    with pytest.raises(KeyError) as exc_info:
        registry.get("does_not_exist")
    message = str(exc_info.value)
    assert "does_not_exist" in message
    assert "subagent_routing" in message


@pytest.mark.unit
def test_subagent_options_match_eval_roster():
    """Sanity: the ported roster keeps all 16 eval options incl. none_needed."""
    assert SUBAGENT_OPTIONS["none_needed"].startswith("Simple chat")
    assert SUBAGENT_OPTIONS["batdongsan"].startswith("Real estate")
