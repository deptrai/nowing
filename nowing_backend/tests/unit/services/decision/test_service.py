"""DecisionService — flag gating, validation, error taxonomy, telemetry."""

from __future__ import annotations

import asyncio
import dataclasses
from uuid import UUID

import pytest

import app.config.decision as decision_config
import app.services.decision.service as service_module
from app.services.decision.backends.mock import MockBackend
from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.questions import get_question_registry
from app.services.decision.service import (
    DecisionService,
    get_decision_service,
)
from app.services.decision.types import (
    Answer,
    BackendResult,
    NoulQuestion,
)

NOUL_Q = NoulQuestion(instructions="i")

_TASK_FLAGS = ("ROUTING", "FILTER", "ENTITY", "INTENT", "VOICE")


class _StubBackend:
    """In-memory backend — returns a canned BackendResult or raises."""

    name = "stub"

    def __init__(self, result: BackendResult | None = None, exc=None, delay=0.0):
        self._result = result
        self._exc = exc
        self._delay = delay
        self.calls: list[dict] = []

    async def decide(self, state, questions, *, model=None, timeout=None):
        self.calls.append({"model": model, "timeout": timeout})
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc is not None:
            raise self._exc
        return self._result


def _result(**overrides) -> BackendResult:
    base = BackendResult(
        answers={"q": Answer(kind="noul", value=0.8, confidence=0.8)},
        model="jev-1.13.0",
        latency_ms=12.3,
        input_tokens=10,
        output_tokens=2,
    )
    return dataclasses.replace(base, **overrides)


@pytest.fixture
def _enabled(monkeypatch):
    """Enable master + all per-task flags — isolated from ambient env."""
    monkeypatch.setenv("DECISION_ENABLED", "true")
    for task in _TASK_FLAGS:
        monkeypatch.setenv(f"DECISION_{task}_ENABLED", "true")


@pytest.mark.unit
async def test_decide_disabled_raises_decision_error(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "false")
    service = DecisionService(_StubBackend(_result()))
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q})
    assert exc_info.value.code == "disabled"


@pytest.mark.unit
async def test_decide_disabled_never_builds_backend(monkeypatch):
    """DECISION_ENABLED=false must short-circuit before backend resolution
    — a bad DECISION_BACKEND can't break the disabled contract."""
    monkeypatch.setenv("DECISION_ENABLED", "false")
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "llm_json")
    service = DecisionService()
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q})
    assert exc_info.value.code == "disabled"


@pytest.mark.unit
async def test_decide_per_task_flag_disabled(_enabled, monkeypatch):
    monkeypatch.setenv("DECISION_ROUTING_ENABLED", "false")
    service = DecisionService(_StubBackend(_result()))
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q}, task="routing")
    assert exc_info.value.code == "disabled"


@pytest.mark.unit
async def test_decide_unknown_task_fails_closed(_enabled):
    service = DecisionService(_StubBackend(_result()))
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q}, task="bogus_task")
    assert exc_info.value.code == "disabled"


@pytest.mark.unit
async def test_decide_empty_questions_rejected(_enabled):
    service = DecisionService(_StubBackend(_result()))
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {})
    assert exc_info.value.code == "invalid_request"


@pytest.mark.unit
async def test_decide_model_override_rejected(_enabled):
    """AD-J3: callers may not unpin the model (e.g. to jev-latest)."""
    service = DecisionService(_StubBackend(_result()))
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q}, model="jev-latest")
    assert exc_info.value.code == "invalid_model"


@pytest.mark.unit
async def test_decide_model_matching_pin_allowed(_enabled):
    backend = _StubBackend(_result())
    service = DecisionService(backend)
    await service.decide({}, {"q": NOUL_Q}, model=decision_config.DECISION_JEV_MODEL)
    assert backend.calls[0]["model"] == "jev-1.13.0"


@pytest.mark.unit
async def test_decide_timeout_clamped(_enabled):
    """Caller timeouts are clamped to [0.1, DECISION_TIMEOUT_SECONDS]."""
    ceiling = decision_config.DECISION_TIMEOUT_SECONDS
    backend = _StubBackend(_result())
    service = DecisionService(backend)

    await service.decide({}, {"q": NOUL_Q}, timeout=0)
    assert backend.calls[-1]["timeout"] == 0.1

    await service.decide({}, {"q": NOUL_Q}, timeout=-5)
    assert backend.calls[-1]["timeout"] == 0.1

    await service.decide({}, {"q": NOUL_Q}, timeout=ceiling + 100)
    assert backend.calls[-1]["timeout"] == ceiling

    await service.decide({}, {"q": NOUL_Q}, timeout=2.0)
    assert backend.calls[-1]["timeout"] == 2.0


@pytest.mark.unit
async def test_decide_service_level_timeout(_enabled):
    """The port enforces the ceiling even when a backend ignores the
    timeout argument entirely."""
    backend = _StubBackend(_result(), delay=5.0)
    service = DecisionService(backend)
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q}, timeout=0.1)
    assert exc_info.value.code == "timeout"


@pytest.mark.unit
async def test_decide_happy_path(_enabled):
    backend = _StubBackend(_result())
    service = DecisionService(backend)
    result = await service.decide({"user_message": "xin chào"}, {"q": NOUL_Q})
    assert result.backend == "stub"
    assert result.model == "jev-1.13.0"
    assert result.answers["q"].value == 0.8
    assert result.input_tokens == 10
    assert result.output_tokens == 2
    assert result.latency_ms == 12.3
    # pinned model + default timeout forwarded to the backend (AD-J3)
    assert backend.calls[0]["model"] == "jev-1.13.0"
    assert backend.calls[0]["timeout"] == decision_config.DECISION_TIMEOUT_SECONDS


@pytest.mark.unit
async def test_decide_backend_error_propagates_as_decision_error(_enabled):
    service = DecisionService(_StubBackend(exc=RuntimeError("boom")))
    with pytest.raises(DecisionError):
        await service.decide({}, {"q": NOUL_Q})


@pytest.mark.unit
async def test_decide_backend_decision_error_passes_through(_enabled):
    service = DecisionService(
        _StubBackend(exc=DecisionError("no key", code="missing_api_key"))
    )
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q})
    assert exc_info.value.code == "missing_api_key"


@pytest.mark.unit
async def test_decide_missing_answer_raises_invalid(_enabled):
    service = DecisionService(_StubBackend(_result(answers={})))
    with pytest.raises(InvalidDecisionAnswer):
        await service.decide({}, {"q": NOUL_Q})


@pytest.mark.unit
async def test_decide_malformed_answer_raises_invalid(_enabled):
    bad = Answer(kind="noul", value=1.5, confidence=0.9)
    service = DecisionService(_StubBackend(_result(answers={"q": bad})))
    with pytest.raises(InvalidDecisionAnswer):
        await service.decide({}, {"q": NOUL_Q})


@pytest.mark.unit
async def test_decide_non_dict_answers_raises_invalid(_enabled):
    service = DecisionService(_StubBackend(_result(answers=["not", "a", "dict"])))
    with pytest.raises(InvalidDecisionAnswer):
        await service.decide({}, {"q": NOUL_Q})


def _patch_record(monkeypatch) -> dict:
    recorded: dict = {}

    async def _fake_record(session, **kwargs):
        recorded["session"] = session
        recorded.update(kwargs)

    monkeypatch.setattr(
        "app.services.token_tracking_service.record_token_usage", _fake_record
    )
    return recorded


@pytest.mark.unit
async def test_decide_records_token_usage(_enabled, monkeypatch):
    recorded = _patch_record(monkeypatch)
    service = DecisionService(_StubBackend(_result()))
    session = object()
    await service.decide(
        {},
        {"q": NOUL_Q},
        task="intent",
        question_set="intent_classify@1.0.0",
        session=session,
        workspace_id=42,
        user_id=UUID(int=1),
        client_id="web",
    )
    assert recorded["session"] is session
    assert recorded["usage_type"] == "decision"
    assert recorded["workspace_id"] == 42
    assert recorded["user_id"] == UUID(int=1)
    assert recorded["prompt_tokens"] == 10
    assert recorded["completion_tokens"] == 2
    assert recorded["total_tokens"] == 12
    assert recorded["e2e_ms"] == 12
    assert recorded["client_id"] == "web"
    assert recorded["call_details"]["backend"] == "stub"
    assert recorded["call_details"]["model"] == "jev-1.13.0"
    assert recorded["call_details"]["task"] == "intent"
    assert recorded["call_details"]["question_set"] == "intent_classify@1.0.0"
    assert recorded["call_details"]["latency_ms"] == 12.3
    # requested question ids, not just answered ones
    assert recorded["call_details"]["questions"] == ["q"]


@pytest.mark.unit
async def test_decide_taskless_records_generic(_enabled, monkeypatch):
    recorded = _patch_record(monkeypatch)
    service = DecisionService(_StubBackend(_result()))
    await service.decide(
        {},
        {"q": NOUL_Q},
        session=object(),
        workspace_id=1,
        user_id=UUID(int=1),
    )
    assert recorded["call_details"]["task"] == "generic"
    assert recorded["call_details"]["question_set"] is None


@pytest.mark.unit
async def test_decide_records_usage_on_invalid_answer(_enabled, monkeypatch):
    """Tokens were still consumed when validation rejects the answer —
    telemetry must fire on the InvalidDecisionAnswer path too (AD-J7)."""
    recorded = _patch_record(monkeypatch)
    bad = Answer(kind="noul", value=1.5, confidence=0.9)
    service = DecisionService(_StubBackend(_result(answers={"q": bad})))
    with pytest.raises(InvalidDecisionAnswer):
        await service.decide(
            {},
            {"q": NOUL_Q},
            session=object(),
            workspace_id=1,
            user_id=UUID(int=1),
        )
    assert recorded["usage_type"] == "decision"
    assert recorded["prompt_tokens"] == 10


@pytest.mark.unit
async def test_decide_skips_telemetry_without_session(_enabled, monkeypatch):
    called = False

    async def _fake_record(session, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.services.token_tracking_service.record_token_usage", _fake_record
    )
    service = DecisionService(_StubBackend(_result()))
    await service.decide({}, {"q": NOUL_Q})
    assert not called


@pytest.mark.unit
async def test_decide_telemetry_failure_is_fail_open(_enabled, monkeypatch):
    async def _boom(session, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("app.services.token_tracking_service.record_token_usage", _boom)
    service = DecisionService(_StubBackend(_result()))
    result = await service.decide(
        {},
        {"q": NOUL_Q},
        session=object(),
        workspace_id=1,
        user_id=UUID(int=1),
    )
    assert result.answers["q"].value == 0.8


@pytest.mark.unit
async def test_decide_mock_backend_end_to_end(_enabled):
    service = DecisionService(MockBackend())
    registry = get_question_registry()
    result = await service.decide(
        {"user_message": "Tìm căn hộ 2PN Quận 7"},
        registry.get("subagent_routing"),
        task="routing",
    )
    assert result.backend == "mock"
    assert (
        result.answers["subagent"].value
        in registry.get("subagent_routing")["subagent"].criteria
    )


@pytest.mark.unit
def test_build_backend_mock(_enabled, monkeypatch):
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "mock")
    service = DecisionService()
    assert service._get_backend().name == "mock"


@pytest.mark.unit
def test_build_backend_mock_logs_warning(_enabled, monkeypatch, caplog):
    """Mock in prod is loud, not silent."""
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "mock")
    with caplog.at_level("WARNING", logger="app.services.decision.service"):
        DecisionService()._get_backend()
    assert "mock" in caplog.text


@pytest.mark.unit
def test_build_backend_jev(_enabled, monkeypatch):
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "jev")
    service = DecisionService()
    assert service._get_backend().name == "jev"


@pytest.mark.unit
def test_build_backend_llm_json_unavailable(_enabled, monkeypatch):
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "llm_json")
    service = DecisionService()
    with pytest.raises(DecisionError) as exc_info:
        service._get_backend()
    assert exc_info.value.code == "backend_unavailable"


@pytest.mark.unit
def test_get_decision_service_singleton(monkeypatch):
    monkeypatch.setattr(service_module, "_decision_service", None)
    assert get_decision_service() is get_decision_service()
