"""Intent classification service — gate-pass payload, fail-open paths (39.5).

MockBackend cannot drive label coverage: a choice answer always picks
the first criteria key ("search") at 0.9, so non-search labels and
below-gate confidence need a stub backend returning caller-chosen
answers (pattern: tests/unit/services/entity_resolution _StubBackend).
"""

from __future__ import annotations

import pytest

import app.config.decision as decision_config
import app.services.intent_classification.service as ic
from app.services.decision.errors import DecisionError
from app.services.decision.questions import get_question_registry
from app.services.decision.questions.intent_classify import INTENT_OPTIONS
from app.services.decision.service import DecisionService
from app.services.decision.types import Answer, BackendResult, DecisionResult
from app.services.intent_classification import classify_intent

pytestmark = pytest.mark.unit

_TASK_FLAGS = ("ROUTING", "FILTER", "ENTITY", "INTENT", "VOICE")


class _StubBackend:
    """In-memory backend — canned BackendResult, callable, or raises."""

    name = "stub"

    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc
        self.calls = 0
        self.last_state: dict | None = None

    async def decide(self, state, questions, *, model=None, timeout=None):
        self.calls += 1
        self.last_state = state
        if self._exc is not None:
            raise self._exc
        if callable(self._result):
            return self._result(state, questions)
        return self._result


@pytest.fixture
def _enabled(monkeypatch):
    """Enable master + all per-task flags; fallback + env knobs pinned."""
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")
    for task in _TASK_FLAGS:
        monkeypatch.setenv(f"DECISION_{task}_ENABLED", "true")
    # Pin env-tunable knobs so host .env can't leak into assertions.
    monkeypatch.delenv("DECISION_INTENT_THRESHOLD", raising=False)


def _patch_service(monkeypatch, backend) -> DecisionService:
    service = DecisionService(backend)
    monkeypatch.setattr(ic, "get_decision_service", lambda: service)
    return service


def _choice_answer(chosen: str, confidence: float = 0.9) -> Answer:
    """Valid choice answer: ``confidence`` tops the distribution (argmax
    on ``chosen``, sums to 1) so the answer is self-consistent."""
    options = list(INTENT_OPTIONS)
    rest = (1.0 - confidence) / (len(options) - 1)
    probs = {o: (confidence if o == chosen else rest) for o in options}
    return Answer(
        kind="choice", value=chosen, confidence=confidence, probabilities=probs
    )


def _result(answers: dict[str, Answer]) -> BackendResult:
    return BackendResult(answers=answers, model="stub-1", latency_ms=1.0)


async def test_gate_pass_returns_payload(_enabled, monkeypatch):
    backend = _StubBackend(_result({"intent": _choice_answer("action", 0.9)}))
    _patch_service(monkeypatch, backend)
    out = await classify_intent("Tạo báo cáo doanh thu tháng này")
    assert out == {
        "label": "action",
        "confidence": 0.9,
        "model": "stub-1",
        "backend": "stub",
    }
    assert backend.calls == 1
    assert backend.last_state == {"user_message": "Tạo báo cáo doanh thu tháng này"}


async def test_below_gate_returns_none(_enabled, monkeypatch):
    backend = _StubBackend(_result({"intent": _choice_answer("search", 0.3)}))
    _patch_service(monkeypatch, backend)
    assert await classify_intent("Tìm quán phở") is None
    assert backend.calls == 1  # paid call ran; gate rejected the answer


async def test_threshold_env_override(_enabled, monkeypatch):
    monkeypatch.setenv("DECISION_INTENT_THRESHOLD", "0.2")
    backend = _StubBackend(_result({"intent": _choice_answer("search", 0.3)}))
    _patch_service(monkeypatch, backend)
    out = await classify_intent("Tìm quán phở")
    assert out is not None and out["label"] == "search"


async def test_master_flag_off_short_circuits(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "false")
    monkeypatch.setenv("DECISION_INTENT_ENABLED", "true")
    backend = _StubBackend(_result({"intent": _choice_answer("search")}))
    _patch_service(monkeypatch, backend)
    assert await classify_intent("Tìm quán phở") is None
    assert backend.calls == 0  # no paid call when disabled


async def test_task_flag_off_short_circuits(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_INTENT_ENABLED", "false")
    backend = _StubBackend(_result({"intent": _choice_answer("search")}))
    _patch_service(monkeypatch, backend)
    assert await classify_intent("Tìm quán phở") is None
    assert backend.calls == 0


async def test_backend_error_returns_none(_enabled, monkeypatch):
    backend = _StubBackend(exc=DecisionError("down", code="timeout"))
    _patch_service(monkeypatch, backend)
    assert await classify_intent("Tìm quán phở") is None


async def test_unexpected_error_returns_none(_enabled, monkeypatch):
    backend = _StubBackend(exc=RuntimeError("boom"))
    _patch_service(monkeypatch, backend)
    assert await classify_intent("Tìm quán phở") is None


async def test_malformed_answer_returns_none(_enabled, monkeypatch):
    """A choice id outside the offered set fails strict validation."""
    bad = Answer(
        kind="choice",
        value="not_an_intent",
        confidence=0.9,
        probabilities=dict.fromkeys(INTENT_OPTIONS, 0.125),
    )
    backend = _StubBackend(_result({"intent": bad}))
    _patch_service(monkeypatch, backend)
    assert await classify_intent("Tìm quán phở") is None


async def test_missing_answer_returns_none(_enabled, monkeypatch):
    backend = _StubBackend(_result({}))
    _patch_service(monkeypatch, backend)
    assert await classify_intent("Tìm quán phở") is None


@pytest.mark.parametrize("message", ["", "   ", " \n\t "])
async def test_empty_or_whitespace_skips_paid_call(_enabled, monkeypatch, message):
    backend = _StubBackend(_result({"intent": _choice_answer("search")}))
    _patch_service(monkeypatch, backend)
    assert await classify_intent(message) is None
    assert backend.calls == 0


async def test_decide_called_with_registered_set(_enabled, monkeypatch):
    """Spy on decide() kwargs: registry set verbatim, task, state keys."""
    calls: list[dict] = []

    class _SpyService:
        async def decide(self, state, questions, **kwargs):
            calls.append({"state": state, "questions": questions, **kwargs})
            return DecisionResult(
                answers={"intent": _choice_answer("recommendation", 0.9)},
                model="spy-model",
                backend="spy",
                latency_ms=1.0,
            )

    monkeypatch.setattr(ic, "get_decision_service", lambda: _SpyService())
    out = await classify_intent("Gợi ý món ăn tối nay")
    assert out is not None and out["label"] == "recommendation"

    assert len(calls) == 1
    call = calls[0]
    assert call["state"] == {"user_message": "Gợi ý món ăn tối nay"}
    assert call["task"] == "intent"
    assert call["question_set"] == "intent_classify@1.0.0"
    assert call["required_state_keys"] == ("user_message",)
    # model/timeout left unset -> service pins (jev-1.13.0, timeout config)
    assert call.get("model") is None
    assert call.get("timeout") is None
    # The registered set is passed verbatim — equal contents, but a COPY:
    # get_set() returns the registry's dict by reference and a downstream
    # mutation must not corrupt the singleton.
    registered = get_question_registry().get_set("intent_classify")
    assert call["questions"] == registered.questions
    assert call["questions"] is not registered.questions
    assert set(call["questions"]) == {"intent"}
