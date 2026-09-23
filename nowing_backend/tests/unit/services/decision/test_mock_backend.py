"""MockBackend — deterministic answers that always pass strict validation."""

from __future__ import annotations

import pytest

from app.services.decision.backends.mock import MockBackend
from app.services.decision.types import (
    ChoiceQuestion,
    NoulQuestion,
    ScoreQuestion,
)
from app.services.decision.validation import validate_answer

QUESTIONS = {
    "pick": ChoiceQuestion(instructions="i", criteria={"a": "A", "b": "B", "c": "C"}),
    "rate": ScoreQuestion(instructions="i", criteria=["l0", "l1", "l2"]),
    "yes": NoulQuestion(instructions="i"),
}


@pytest.mark.unit
async def test_mock_backend_deterministic():
    backend = MockBackend()
    r1 = await backend.decide({"x": 1}, QUESTIONS)
    r2 = await backend.decide({"x": 2}, QUESTIONS)
    assert r1.answers == r2.answers
    assert r1.model == "mock"
    assert r1.latency_ms >= 0


@pytest.mark.unit
async def test_mock_backend_answers_pass_strict_validation():
    backend = MockBackend()
    result = await backend.decide({}, QUESTIONS)
    for qid, question in QUESTIONS.items():
        assert validate_answer(result.answers[qid], question)


@pytest.mark.unit
async def test_mock_backend_answer_values():
    backend = MockBackend()
    result = await backend.decide({}, QUESTIONS)

    pick = result.answers["pick"]
    assert pick.value == "a"  # deterministic: first option
    assert pick.probabilities["a"] == pytest.approx(0.9)

    rate = result.answers["rate"]
    assert rate.value == pytest.approx(2 * 0.9 + 1 * 0.05 + 0 * 0.05)

    yes = result.answers["yes"]
    assert yes.value == 0.9
    assert yes.confidence == 0.9
