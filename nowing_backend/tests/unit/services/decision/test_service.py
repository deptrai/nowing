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

    def __init__(
        self,
        result: BackendResult | None = None,
        exc=None,
        delay=0.0,
        name="stub",
    ):
        self.name = name
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
    """Enable master + all per-task flags — isolated from ambient env.

    Fallback is pinned off: a failing primary must never reach the real
    llm_json backend (a paid network call) unless a test wires one up
    via ``_patch_fallback`` or the config attr.
    """
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")
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
async def test_decide_backend_decision_error_passes_through(_enabled, monkeypatch):
    # fallback off: the primary's DecisionError propagates unwrapped
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")
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
async def test_decide_thread_id_reaches_record_token_usage(
    _enabled, monkeypatch
):
    """thread_id is a first-class TokenUsage field — the usage row must
    be joinable back to the chat thread that paid for the decision."""
    recorded = _patch_record(monkeypatch)
    service = DecisionService(_StubBackend(_result()))
    await service.decide(
        {},
        {"q": NOUL_Q},
        session=object(),
        workspace_id=1,
        user_id=UUID(int=1),
        thread_id=7,
    )
    assert recorded["thread_id"] == 7


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
def test_build_backend_llm_json(_enabled, monkeypatch):
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "llm_json")
    service = DecisionService()
    assert service._get_backend().name == "llm_json"


@pytest.mark.unit
def test_get_decision_service_singleton(monkeypatch):
    monkeypatch.setattr(service_module, "_decision_service", None)
    assert get_decision_service() is get_decision_service()


# ---------------------------------------------------------------------------
# Fallback chain (story 39.1b) — primary → DECISION_FALLBACK_BACKEND
# ---------------------------------------------------------------------------


def _patch_fallback(monkeypatch, backend) -> None:
    """Route the service's fallback resolution to an in-memory backend."""
    monkeypatch.setattr(
        service_module, "_build_fallback_backend", lambda primary_name: backend
    )


def _llm_result() -> BackendResult:
    """What the llm_json leg returns — model/backend reflect that leg."""
    return BackendResult(
        answers={"q": Answer(kind="noul", value=0.6, confidence=0.6)},
        model=decision_config.DECISION_LLM_MODEL,
        latency_ms=4.2,
        input_tokens=50,
        output_tokens=5,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "code", ["timeout", "backend_error", "backend_unavailable", "missing_api_key"]
)
async def test_decide_fallback_on_retryable_codes(_enabled, monkeypatch, code):
    primary = _StubBackend(exc=DecisionError("primary down", code=code))
    fallback = _StubBackend(_llm_result(), name="llm_json")
    _patch_fallback(monkeypatch, fallback)
    service = DecisionService(primary)

    result = await service.decide({"s": 1}, {"q": NOUL_Q})

    assert result.backend == "llm_json"
    assert result.model == decision_config.DECISION_LLM_MODEL
    assert result.answers["q"].value == 0.6
    # the fallback leg is pinned to the LLM model, not the Jev pin
    assert fallback.calls[0]["model"] == decision_config.DECISION_LLM_MODEL
    # and inherits the same clamped timeout as the primary leg
    assert fallback.calls[0]["timeout"] == decision_config.DECISION_TIMEOUT_SECONDS


@pytest.mark.unit
async def test_decide_fallback_inherits_clamped_timeout(_enabled, monkeypatch):
    primary = _StubBackend(exc=DecisionError("down", code="timeout"))
    fallback = _StubBackend(_llm_result(), name="llm_json")
    _patch_fallback(monkeypatch, fallback)
    service = DecisionService(primary)
    await service.decide({}, {"q": NOUL_Q}, timeout=2.0)
    assert primary.calls[0]["timeout"] == 2.0
    assert fallback.calls[0]["timeout"] == 2.0


@pytest.mark.unit
async def test_decide_no_fallback_when_primary_succeeds(_enabled, monkeypatch):
    fallback = _StubBackend(_llm_result(), name="llm_json")
    _patch_fallback(monkeypatch, fallback)
    service = DecisionService(_StubBackend(_result()))
    result = await service.decide({}, {"q": NOUL_Q})
    assert result.backend == "stub"
    assert fallback.calls == []


@pytest.mark.unit
async def test_decide_construction_failure_falls_back(_enabled, monkeypatch):
    """An unrecognized DECISION_BACKEND (backend_unavailable at build
    time) may still be served by the fallback leg."""
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "bogus")
    fallback = _StubBackend(_llm_result(), name="llm_json")
    _patch_fallback(monkeypatch, fallback)
    service = DecisionService()

    result = await service.decide({}, {"q": NOUL_Q})

    assert result.backend == "llm_json"
    assert result.model == decision_config.DECISION_LLM_MODEL
    assert fallback.calls[0]["model"] == decision_config.DECISION_LLM_MODEL


@pytest.mark.unit
async def test_decide_mock_primary_never_falls_back(_enabled, monkeypatch):
    """A deterministic/offline mock primary must not trigger a paid call."""
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "llm_json")

    import litellm

    litellm_calls: list[dict] = []

    async def _spy(**kwargs):
        litellm_calls.append(kwargs)
        raise AssertionError("litellm must not be called")

    monkeypatch.setattr(litellm, "acompletion", _spy)
    primary = _StubBackend(exc=DecisionError("down", code="timeout"), name="mock")
    service = DecisionService(primary)
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q})
    assert exc_info.value.code == "timeout"
    assert litellm_calls == []


@pytest.mark.unit
async def test_decide_fallback_logs_primary_code(_enabled, monkeypatch, caplog):
    primary = _StubBackend(exc=DecisionError("primary down", code="timeout"))
    _patch_fallback(monkeypatch, _StubBackend(_llm_result(), name="llm_json"))
    service = DecisionService(primary)
    with caplog.at_level("WARNING", logger="app.services.decision.service"):
        await service.decide({}, {"q": NOUL_Q})
    assert "timeout" in caplog.text
    assert "llm_json" in caplog.text


@pytest.mark.unit
async def test_decide_fallback_leg_failure_propagates(_enabled, monkeypatch, caplog):
    """Both legs fail → the fallback leg's DecisionError reaches the caller."""
    primary = _StubBackend(exc=DecisionError("primary down", code="timeout"))
    fallback = _StubBackend(
        exc=DecisionError("llm also down", code="backend_error"), name="llm_json"
    )
    _patch_fallback(monkeypatch, fallback)
    service = DecisionService(primary)
    with (
        caplog.at_level("WARNING", logger="app.services.decision.service"),
        pytest.raises(DecisionError) as exc_info,
    ):
        await service.decide({}, {"q": NOUL_Q})
    assert exc_info.value.code == "backend_error"
    assert "llm also down" in str(exc_info.value)
    # the failed fallback leg is surfaced — its spend is otherwise invisible
    assert "llm_json" in caplog.text
    assert "backend_error" in caplog.text


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc",
    [
        InvalidDecisionAnswer("malformed answer"),
        DecisionError("caller error", code="invalid_request"),
        DecisionError("bad model", code="invalid_model"),
        DecisionError("off", code="disabled"),
    ],
)
async def test_decide_no_fallback_on_non_retryable(_enabled, monkeypatch, exc):
    """InvalidDecisionAnswer / caller errors never pay for a second leg."""
    primary = _StubBackend(exc=exc)
    fallback = _StubBackend(_llm_result(), name="llm_json")
    _patch_fallback(monkeypatch, fallback)
    service = DecisionService(primary)
    with pytest.raises(DecisionError):
        await service.decide({}, {"q": NOUL_Q})
    assert fallback.calls == []


@pytest.mark.unit
async def test_decide_no_fallback_when_configured_none(_enabled, monkeypatch):
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")
    primary = _StubBackend(exc=DecisionError("down", code="timeout"))
    service = DecisionService(primary)
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q})
    assert exc_info.value.code == "timeout"


@pytest.mark.unit
async def test_decide_fallback_records_winning_leg(_enabled, monkeypatch):
    """Telemetry describes the leg that actually answered, not the primary."""
    recorded = _patch_record(monkeypatch)
    primary = _StubBackend(exc=DecisionError("down", code="missing_api_key"))
    _patch_fallback(monkeypatch, _StubBackend(_llm_result(), name="llm_json"))
    service = DecisionService(primary)
    await service.decide(
        {},
        {"q": NOUL_Q},
        session=object(),
        workspace_id=1,
        user_id=UUID(int=1),
    )
    assert recorded["call_details"]["backend"] == "llm_json"
    assert recorded["call_details"]["model"] == decision_config.DECISION_LLM_MODEL
    assert recorded["prompt_tokens"] == 50
    assert recorded["completion_tokens"] == 5


@pytest.mark.unit
async def test_decide_model_pin_is_per_backend(_enabled):
    """A model valid for Jev is invalid when the active backend is llm_json."""
    backend = _StubBackend(_llm_result(), name="llm_json")
    service = DecisionService(backend)
    with pytest.raises(DecisionError) as exc_info:
        await service.decide(
            {}, {"q": NOUL_Q}, model=decision_config.DECISION_JEV_MODEL
        )
    assert exc_info.value.code == "invalid_model"
    assert backend.calls == []

    await service.decide({}, {"q": NOUL_Q}, model=decision_config.DECISION_LLM_MODEL)
    assert backend.calls[0]["model"] == decision_config.DECISION_LLM_MODEL


@pytest.mark.unit
async def test_decide_llm_json_primary_end_to_end(_enabled, monkeypatch):
    """DECISION_BACKEND=llm_json → one fake acompletion → validated result."""
    import json

    import litellm

    payload = {
        "answers": [
            {
                "question_id": "q",
                "answer": 0.7,
                "confidence": 0.7,
                "probabilities": None,
            }
        ]
    }
    calls: list[dict] = []

    class _FakeResponse:
        choices = [
            type(
                "C", (), {"message": type("M", (), {"content": json.dumps(payload)})()}
            )()
        ]
        model = decision_config.DECISION_LLM_MODEL
        usage = None

    async def _fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(litellm, "acompletion", _fake_acompletion)
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "llm_json")
    service = DecisionService()

    result = await service.decide({"user_message": "xin chào"}, {"q": NOUL_Q})

    assert len(calls) == 1
    assert calls[0]["model"] == decision_config.DECISION_LLM_MODEL
    assert result.backend == "llm_json"
    assert result.model == decision_config.DECISION_LLM_MODEL
    assert result.answers["q"].value == 0.7


@pytest.mark.unit
def test_build_fallback_backend_llm_json(_enabled, monkeypatch):
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "llm_json")
    fallback = service_module._build_fallback_backend("jev")
    assert fallback is not None and fallback.name == "llm_json"


@pytest.mark.unit
def test_build_fallback_backend_none(_enabled, monkeypatch):
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")
    assert service_module._build_fallback_backend("jev") is None


@pytest.mark.unit
def test_build_fallback_backend_skips_self_retry(_enabled, monkeypatch):
    """llm_json → llm_json is not a chain — litellm already retries."""
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "llm_json")
    assert service_module._build_fallback_backend("llm_json") is None


@pytest.mark.unit
def test_build_fallback_backend_skips_mock(_enabled, monkeypatch):
    """mock → llm_json is not allowed — offline tests must not pay."""
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "llm_json")
    assert service_module._build_fallback_backend("mock") is None


@pytest.mark.unit
async def test_decide_fallback_builder_failure_reraises_primary(_enabled, monkeypatch):
    """A raise inside the fallback builder must not mask the primary error."""
    primary = _StubBackend(exc=DecisionError("primary down", code="timeout"))

    def _boom(primary_name):
        raise RuntimeError("builder exploded")

    monkeypatch.setattr(service_module, "_build_fallback_backend", _boom)
    service = DecisionService(primary)
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q})
    assert exc_info.value.code == "timeout"


# ---------------------------------------------------------------------------
# required_state_keys — pre-call state validation (spec-39-1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_decide_missing_required_state_keys_rejected(_enabled):
    """Missing keys raise invalid_request BEFORE the backend is called —
    a malformed call never reaches a paid leg."""
    backend = _StubBackend(_result())
    service = DecisionService(backend)
    with pytest.raises(DecisionError) as exc_info:
        await service.decide(
            {"user_message": "xin chào"},
            {"q": NOUL_Q},
            required_state_keys=("user_message", "query", "passage"),
        )
    assert exc_info.value.code == "invalid_request"
    assert "passage" in str(exc_info.value)
    assert "query" in str(exc_info.value)
    assert "user_message" not in str(exc_info.value)
    assert backend.calls == []


@pytest.mark.unit
async def test_decide_missing_state_keys_skips_backend_resolution(
    _enabled, monkeypatch
):
    """The check precedes backend construction — even a bad
    DECISION_BACKEND can't mask the invalid_request."""
    monkeypatch.setattr(decision_config, "DECISION_BACKEND", "bogus")
    service = DecisionService()
    with pytest.raises(DecisionError) as exc_info:
        await service.decide({}, {"q": NOUL_Q}, required_state_keys=("missing",))
    assert exc_info.value.code == "invalid_request"


@pytest.mark.unit
async def test_decide_required_state_keys_present(_enabled):
    backend = _StubBackend(_result())
    service = DecisionService(backend)
    result = await service.decide(
        {"user_message": "xin chào", "extra": 1},
        {"q": NOUL_Q},
        required_state_keys=("user_message",),
    )
    assert result.answers["q"].value == 0.8
    assert len(backend.calls) == 1


# ---------------------------------------------------------------------------
# Per-leg telemetry — failed legs stay visible (spec-39-1b)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_decide_fallback_win_records_legs(_enabled, monkeypatch):
    """A winning fallback leg exposes the failed primary leg."""
    recorded = _patch_record(monkeypatch)
    primary = _StubBackend(exc=DecisionError("down", code="timeout"), name="jev")
    _patch_fallback(monkeypatch, _StubBackend(_llm_result(), name="llm_json"))
    service = DecisionService(primary)
    await service.decide(
        {},
        {"q": NOUL_Q},
        session=object(),
        workspace_id=1,
        user_id=UUID(int=1),
    )
    legs = recorded["call_details"]["legs"]
    assert len(legs) == 2
    assert legs[0]["backend"] == "jev"
    assert legs[0]["outcome"] == "timeout"
    assert legs[1]["backend"] == "llm_json"
    assert legs[1]["outcome"] == "ok"
    assert legs[1]["model"] == decision_config.DECISION_LLM_MODEL


@pytest.mark.unit
async def test_decide_both_legs_fail_records_failed_attempt(_enabled, monkeypatch):
    """When the fallback leg also fails, the attempt is still persisted —
    visible in telemetry without fabricated token spend."""
    recorded = _patch_record(monkeypatch)
    primary = _StubBackend(
        exc=DecisionError("primary down", code="timeout"), name="jev"
    )
    fallback = _StubBackend(
        exc=DecisionError("llm down", code="backend_error"), name="llm_json"
    )
    _patch_fallback(monkeypatch, fallback)
    service = DecisionService(primary)
    with pytest.raises(DecisionError) as exc_info:
        await service.decide(
            {},
            {"q": NOUL_Q},
            session=object(),
            workspace_id=1,
            user_id=UUID(int=1),
        )
    assert exc_info.value.code == "backend_error"
    details = recorded["call_details"]
    assert details["failed"] is True
    assert details["error_code"] == "backend_error"
    assert details["backend"] == "llm_json"
    assert details["model"] == decision_config.DECISION_LLM_MODEL
    assert [leg["outcome"] for leg in details["legs"]] == [
        "timeout",
        "backend_error",
    ]
    # no fabricated spend — the failed leg reported no tokens
    assert recorded["prompt_tokens"] == 0
    assert recorded["completion_tokens"] == 0
    assert recorded["total_tokens"] == 0


@pytest.mark.unit
async def test_decide_single_leg_success_has_no_legs_key(_enabled, monkeypatch):
    """A single-leg success stays terse — no per-leg trace."""
    recorded = _patch_record(monkeypatch)
    service = DecisionService(_StubBackend(_result()))
    await service.decide(
        {},
        {"q": NOUL_Q},
        session=object(),
        workspace_id=1,
        user_id=UUID(int=1),
    )
    assert "legs" not in recorded["call_details"]
