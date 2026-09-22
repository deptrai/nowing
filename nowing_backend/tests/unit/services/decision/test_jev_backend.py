"""JevBackend — SDK mapping, error taxonomy, timeout ceiling, missing key."""

from __future__ import annotations

import asyncio

import pytest

from app.services.decision.backends.jev import JevBackend
from app.services.decision.errors import DecisionError
from app.services.decision.types import (
    ChoiceQuestion,
    NoulQuestion,
    ScoreQuestion,
)
from app.services.decision.validation import validate_answer


class _FakeUsage:
    input_tokens = 123
    output_tokens = 7


class _FakeAnswer:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeResponse:
    def __init__(self, answers, model="jev-1.13.0"):
        self.answers = answers
        self.model = model
        self.usage = _FakeUsage()


class _FakeClient:
    """Stands in for AsyncTypeSafeClient — injected as ``backend._client``."""

    def __init__(self, response=None, exc=None, delay=0.0):
        self._response = response
        self._exc = exc
        self._delay = delay
        self.calls: list[dict] = []

    async def system_one(self, state, questions, model=None, timeout=None):
        self.calls.append(
            {"state": state, "questions": questions, "model": model, "timeout": timeout}
        )
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc is not None:
            raise self._exc
        return self._response


QUESTIONS = {
    "pick": ChoiceQuestion(instructions="i", criteria={"a": "A", "b": "B"}),
    "rate": ScoreQuestion(instructions="i", criteria=["l0", "l1", "l2"]),
    "yes": NoulQuestion(instructions="i"),
}


@pytest.mark.unit
async def test_jev_backend_missing_api_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    backend = JevBackend()
    with pytest.raises(DecisionError) as exc_info:
        await backend.decide({}, {"yes": NoulQuestion(instructions="i")})
    assert exc_info.value.code == "missing_api_key"


@pytest.mark.unit
async def test_jev_backend_maps_response_to_answers():
    backend = JevBackend(api_key="test-key")
    response = _FakeResponse(
        {
            "pick": _FakeAnswer(
                type="choice",
                choice="b",
                confidence=0.9,
                probabilities={"a": 0.1, "b": 0.9},
            ),
            "rate": _FakeAnswer(
                type="score",
                score=1.85,
                confidence=0.8,
                probabilities={0: 0.05, 1: 0.05, 2: 0.9},
            ),
            "yes": _FakeAnswer(type="noul", noul=0.7),
        }
    )
    client = _FakeClient(response=response)
    backend._client = client

    result = await backend.decide(
        {"user_message": "xin chào"},
        QUESTIONS,
        model="jev-1.13.0",
        timeout=5.0,
    )

    assert result.model == "jev-1.13.0"
    assert result.input_tokens == 123
    assert result.output_tokens == 7
    assert result.latency_ms >= 0

    pick = result.answers["pick"]
    assert pick.kind == "choice" and pick.value == "b"
    assert pick.probabilities == {"a": 0.1, "b": 0.9}

    rate = result.answers["rate"]
    # int level keys normalized to strings
    assert rate.probabilities == {"0": 0.05, "1": 0.05, "2": 0.9}
    assert rate.value == 1.85

    yes = result.answers["yes"]
    assert yes.kind == "noul" and yes.value == 0.7
    # noul doubles as its own confidence for ConfidenceGate uniformity
    assert yes.confidence == 0.7

    # mapped answers survive strict validation end-to-end
    for qid, question in QUESTIONS.items():
        validate_answer(result.answers[qid], question)

    # pinned model + timeout forwarded to the SDK call
    assert client.calls[0]["model"] == "jev-1.13.0"
    assert client.calls[0]["timeout"] == 5.0


@pytest.mark.unit
async def test_jev_backend_sdk_error_becomes_decision_error():
    backend = JevBackend(api_key="test-key")
    backend._client = _FakeClient(exc=RuntimeError("529 overloaded"))
    with pytest.raises(DecisionError):
        await backend.decide({}, {"yes": NoulQuestion(instructions="i")}, timeout=5.0)


@pytest.mark.unit
async def test_jev_backend_timeout_becomes_decision_error():
    backend = JevBackend(api_key="test-key")
    backend._client = _FakeClient(delay=5.0)
    with pytest.raises(DecisionError):
        await backend.decide({}, {"yes": NoulQuestion(instructions="i")}, timeout=0.01)
