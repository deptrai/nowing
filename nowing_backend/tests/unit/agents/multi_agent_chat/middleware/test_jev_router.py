"""Unit tests for the Jev pre-router middleware (DecisionService rewire).

Covers the story-39.2 I/O matrix: routing decisions now go through
``DecisionService.decide()`` with the ``subagent_routing`` registry set,
confidence-gated hints, once-per-user-message dedup (both directions),
telemetry session wiring, and absolute fail-open behaviour.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import app.config.decision as decision_config
import app.db
from app.agents.chat.multi_agent_chat.main_agent.middleware import jev_router
from app.agents.chat.multi_agent_chat.main_agent.middleware.jev_router import (
    JevRouterMiddleware,
    build_jev_router_mw,
)
from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.services.decision.errors import DecisionError, InvalidDecisionAnswer
from app.services.decision.questions.subagent_routing import SUBAGENT_OPTIONS
from app.services.decision.service import DecisionService
from app.services.decision.types import Answer, BackendResult, DecisionResult

_DESCRIPTORS = [
    {"name": "batdongsan", "description": "descriptor text — NOT the criteria"},
    {"name": "chainlens", "description": "descriptor text"},
]


class _StubService:
    """In-memory DecisionService stand-in — records calls, returns or raises."""

    def __init__(self, result: DecisionResult | None = None, exc=None):
        self._result = result
        self._exc = exc
        self.calls: list[dict[str, Any]] = []

    async def decide(self, state, questions, **kwargs):
        self.calls.append({"state": state, "questions": questions, **kwargs})
        if self._exc is not None:
            raise self._exc
        return self._result


class _FakeSession:
    def __init__(self, *, commit_exc=None, commit_sleep: float = 0.0):
        self.commits = 0
        self._commit_exc = commit_exc
        self._commit_sleep = commit_sleep

    async def commit(self):
        self.commits += 1
        if self._commit_sleep:
            await asyncio.sleep(self._commit_sleep)
        if self._commit_exc is not None:
            raise self._commit_exc


class _FakeSessionMaker:
    """Callable returning an async context manager yielding a fake session."""

    def __init__(self, *, commit_exc=None, commit_sleep: float = 0.0):
        self._commit_exc = commit_exc
        self._commit_sleep = commit_sleep
        self.sessions: list[_FakeSession] = []

    def __call__(self):
        session = _FakeSession(
            commit_exc=self._commit_exc, commit_sleep=self._commit_sleep
        )
        self.sessions.append(session)

        @contextlib.asynccontextmanager
        async def _cm():
            yield session

        return _cm()


def _result(value: str = "batdongsan", confidence: float = 0.9) -> DecisionResult:
    return DecisionResult(
        answers={
            "subagent": Answer(kind="choice", value=value, confidence=confidence)
        },
        model="jev-1.13.0",
        backend="stub",
        latency_ms=1.0,
    )


def _make_mw(
    service: _StubService,
    monkeypatch: pytest.MonkeyPatch,
    descriptors=_DESCRIPTORS,
    **kwargs,
) -> JevRouterMiddleware:
    monkeypatch.setattr(jev_router, "get_decision_service", lambda: service)
    return JevRouterMiddleware(subagent_descriptors=descriptors, **kwargs)


def _state(*messages) -> dict[str, Any]:
    return {"messages": list(messages)}


# ---------------------------------------------------------------------------
# ROUTED / NONE_NEEDED — verbatim hints
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_routed_injects_verbatim_hint(monkeypatch):
    service = _StubService(_result(value="batdongsan", confidence=0.9))
    mw = _make_mw(service, monkeypatch)

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None
    (msg,) = out["messages"]
    assert isinstance(msg, SystemMessage)
    assert msg.content == (
        "<jev_routing_hint>\n"
        "Jev pre-classification suggests routing to `batdongsan` "
        '(confidence=90%). Use `task(subagent_type="batdongsan", ...)` '
        "if this matches the user's intent. You may override if the "
        "suggestion is wrong.\n"
        "</jev_routing_hint>"
    )


@pytest.mark.unit
async def test_routed_decide_call_contract(monkeypatch):
    """decide() is called with the registry set + pinned-model contract."""
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    await mw.abefore_model(
        _state(HumanMessage(content="  Tìm chung cư Q7  ")), MagicMock()
    )

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["state"] == {"user_message": "Tìm chung cư Q7"}
    assert call["task"] == "routing"
    assert call["question_set"] == "subagent_routing@1.0.0"
    assert call["required_state_keys"] == ("user_message",)
    assert call["model"] is None
    assert call["timeout"] is None


@pytest.mark.unit
async def test_none_needed_injects_verbatim_hint(monkeypatch):
    service = _StubService(_result(value="none_needed", confidence=0.8))
    mw = _make_mw(service, monkeypatch)

    out = await mw.abefore_model(
        _state(HumanMessage(content="Kể chuyện cười đi")), MagicMock()
    )

    assert out is not None
    (msg,) = out["messages"]
    assert msg.content == (
        "<jev_routing_hint>\n"
        "Jev pre-classification: this message likely needs no specialist "
        "(confidence=80%). Consider answering directly without a `task()` "
        "call.\n"
        "</jev_routing_hint>"
    )


@pytest.mark.unit
async def test_last_human_found_before_trailing_tool_messages(monkeypatch):
    """The last HumanMessage need not be trailing — tool/AI messages may
    follow it in a react loop and classification still targets it."""
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    state = _state(
        HumanMessage(content="Tìm chung cư Q7"),
        AIMessage(content="", tool_calls=[{"name": "task", "args": {}, "id": "1"}]),
    )
    out = await mw.abefore_model(state, MagicMock())

    assert out is not None
    assert service.calls[0]["state"] == {"user_message": "Tìm chung cư Q7"}


# ---------------------------------------------------------------------------
# BELOW_THRESHOLD / DECIDE_RAISES / MALFORMED / ANY_EXCEPTION — fail-open
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_below_threshold_skips_hint_and_dedups(monkeypatch):
    service = _StubService(_result(value="batdongsan", confidence=0.5))
    mw = _make_mw(service, monkeypatch)
    state = _state(HumanMessage(content="Tìm chung cư Q7"))

    assert await mw.abefore_model(state, MagicMock()) is None
    # Second model call in the same react loop must not re-pay.
    assert await mw.abefore_model(state, MagicMock()) is None
    assert len(service.calls) == 1
    assert mw._last_classified == "Tìm chung cư Q7"


@pytest.mark.unit
async def test_decide_decision_error_returns_none_and_dedups(monkeypatch):
    service = _StubService(
        exc=DecisionError("backend down", code="backend_unavailable")
    )
    mw = _make_mw(service, monkeypatch)
    state = _state(HumanMessage(content="Tìm chung cư Q7"))

    assert await mw.abefore_model(state, MagicMock()) is None
    assert await mw.abefore_model(state, MagicMock()) is None
    assert len(service.calls) == 1


@pytest.mark.unit
async def test_decide_invalid_answer_returns_none(monkeypatch):
    service = _StubService(exc=InvalidDecisionAnswer("bad probs"))
    mw = _make_mw(service, monkeypatch)

    assert (
        await mw.abefore_model(
            _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
        )
        is None
    )


@pytest.mark.unit
async def test_unexpected_exception_returns_none(monkeypatch):
    """Non-DecisionError failures (DB/UUID/KeyError bugs) are caught by the
    generic handler — the hook must never kill a turn."""
    service = _StubService(exc=RuntimeError("sqlalchemy exploded"))
    mw = _make_mw(service, monkeypatch)

    assert (
        await mw.abefore_model(
            _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
        )
        is None
    )


# ---------------------------------------------------------------------------
# NO_FRESH_MSG — trigger conditions
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_no_human_message_skips_decide(monkeypatch):
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    out = await mw.abefore_model(_state(AIMessage(content="hello")), MagicMock())

    assert out is None
    assert service.calls == []


@pytest.mark.unit
async def test_short_message_skips_decide(monkeypatch):
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    for text in ("hi", "   ", ""):
        out = await mw.abefore_model(
            _state(HumanMessage(content=text)), MagicMock()
        )
        assert out is None
    assert service.calls == []


@pytest.mark.unit
async def test_multimodal_text_blocks_classified(monkeypatch):
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    out = await mw.abefore_model(
        _state(
            HumanMessage(
                content=[
                    {"type": "text", "text": "Tìm"},
                    {"type": "image_url", "image_url": {"url": "data:..."}},
                    {"type": "text", "text": "chung cư"},
                ]
            )
        ),
        MagicMock(),
    )

    assert out is not None
    assert service.calls[0]["state"] == {"user_message": "Tìm chung cư"}


# ---------------------------------------------------------------------------
# DEDUP_SAME_TURN / NEW_TURN — scoped marker scan + _last_classified
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_marker_after_last_human_blocks_reclassify(monkeypatch):
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    state = _state(
        HumanMessage(content="Tìm chung cư Q7"),
        SystemMessage(content="<jev_routing_hint>\nold\n</jev_routing_hint>"),
        AIMessage(content="routed"),
    )
    out = await mw.abefore_model(state, MagicMock())

    assert out is None
    assert service.calls == []


@pytest.mark.unit
async def test_marker_before_new_human_reclassifies(monkeypatch):
    """A checkpointed marker from an OLDER turn must not block a fresh
    HumanMessage (the pre-39.2 scan-all bug made the router fire once
    per thread forever)."""
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    first = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )
    assert first is not None

    state = _state(
        HumanMessage(content="Tìm chung cư Q7"),
        first["messages"][0],  # the injected marker, now mid-history
        AIMessage(content="đã route"),
        HumanMessage(content="Thời tiết Sài Gòn hôm nay"),
    )
    second = await mw.abefore_model(state, MagicMock())

    assert second is not None
    assert len(service.calls) == 2
    assert service.calls[1]["state"] == {"user_message": "Thời tiết Sài Gòn hôm nay"}


@pytest.mark.unit
async def test_same_text_repeated_dedups(monkeypatch):
    """Same user text seen again (same message) never re-classifies."""
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    state = _state(HumanMessage(content="Tìm chung cư Q7"))
    assert await mw.abefore_model(state, MagicMock()) is not None
    # Marker dropped (e.g. context editing) — _last_classified still dedups.
    assert await mw.abefore_model(state, MagicMock()) is None
    assert len(service.calls) == 1


# ---------------------------------------------------------------------------
# FLAGS_OFF — builder gating
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_builder_returns_none_when_flag_off():
    flags = AgentFeatureFlags(enable_jev_router=False)
    assert build_jev_router_mw(flags, _DESCRIPTORS) is None


@pytest.mark.unit
def test_builder_returns_none_on_kill_switch():
    flags = AgentFeatureFlags(
        disable_new_agent_stack=True, enable_jev_router=True
    )
    assert build_jev_router_mw(flags, _DESCRIPTORS) is None


@pytest.mark.unit
def test_builder_returns_mw_without_typesafe_api_key(monkeypatch):
    """No TYPESAFE_API_KEY gate: the decision layer owns fallback
    (missing_api_key → llm_json) and non-Jev backends need no key."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    flags = AgentFeatureFlags(enable_jev_router=True)

    mw = build_jev_router_mw(flags, _DESCRIPTORS)

    assert isinstance(mw, JevRouterMiddleware)


# ---------------------------------------------------------------------------
# STALE_ROSTER — registry ∩ live descriptors, registry descriptions kept
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_criteria_intersect_live_roster_and_keep_registry_descriptions():
    mw = JevRouterMiddleware(subagent_descriptors=_DESCRIPTORS)

    question = mw._questions["subagent"]
    assert set(question.criteria) == {"batdongsan", "chainlens", "none_needed"}
    # Values are the eval-tuned registry descriptions, NOT descriptor text.
    assert question.criteria["batdongsan"] == SUBAGENT_OPTIONS["batdongsan"]
    assert question.criteria["none_needed"] == SUBAGENT_OPTIONS["none_needed"]
    # Instructions preserved through dataclasses.replace.
    assert question.instructions


@pytest.mark.unit
def test_empty_roster_falls_back_to_full_registry():
    for descriptors in (None, []):
        mw = JevRouterMiddleware(subagent_descriptors=descriptors)
        question = mw._questions["subagent"]
        assert set(question.criteria) == set(SUBAGENT_OPTIONS)


@pytest.mark.unit
def test_roster_names_outside_registry_are_dropped():
    """Connector agents absent from the registry never enter the criteria
    when at least one roster name does intersect."""
    mw = JevRouterMiddleware(
        subagent_descriptors=[
            {"name": "amazon", "description": "not in registry"},
            {"name": "batdongsan", "description": "x"},
        ]
    )
    assert set(mw._questions["subagent"].criteria) == {
        "batdongsan",
        "none_needed",
    }


@pytest.mark.unit
def test_disjoint_roster_falls_back_to_full_registry():
    """A roster with zero registry overlap must not collapse criteria to
    {none_needed} — a confident answer would actively suppress live
    subagents."""
    mw = JevRouterMiddleware(
        subagent_descriptors=[{"name": "amazon", "description": "x"}]
    )
    assert set(mw._questions["subagent"].criteria) == set(SUBAGENT_OPTIONS)


@pytest.mark.unit
async def test_ctor_failure_disables_middleware(monkeypatch):
    """A question-build failure must not propagate through the ctor —
    the middleware disables itself instead of killing the agent build."""
    monkeypatch.setattr(
        jev_router,
        "get_question_registry",
        lambda: (_ for _ in ()).throw(KeyError("registry broken")),
    )
    mw = JevRouterMiddleware(subagent_descriptors=_DESCRIPTORS)
    assert mw._questions is None

    service = _StubService(_result())
    monkeypatch.setattr(jev_router, "get_decision_service", lambda: service)
    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )
    assert out is None
    assert service.calls == []


# ---------------------------------------------------------------------------
# TELEMETRY — session + ids wiring, unconditional commit
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_session_opened_and_committed_with_ids(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_ROUTING_ENABLED", "true")
    maker = _FakeSessionMaker()
    monkeypatch.setattr(app.db, "async_session_maker", maker)
    service = _StubService(_result())
    uid = str(uuid4())
    mw = _make_mw(
        service,
        monkeypatch,
        workspace_id=7,
        user_id=uid,
        client_id="web-chat",
    )

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None
    assert len(maker.sessions) == 1
    call = service.calls[0]
    assert call["session"] is maker.sessions[0]
    assert call["workspace_id"] == 7
    assert call["user_id"].hex == uid.replace("-", "")
    assert call["client_id"] == "web-chat"
    assert maker.sessions[0].commits == 1


@pytest.mark.unit
async def test_session_committed_even_when_decide_raises(monkeypatch):
    """The InvalidDecisionAnswer leg still wrote a usage row inside
    decide()'s finally — our commit must run regardless."""
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_ROUTING_ENABLED", "true")
    maker = _FakeSessionMaker()
    monkeypatch.setattr(app.db, "async_session_maker", maker)
    service = _StubService(exc=InvalidDecisionAnswer("bad"))
    mw = _make_mw(service, monkeypatch, workspace_id=7, user_id=str(uuid4()))

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is None
    assert maker.sessions[0].commits == 1


@pytest.mark.unit
async def test_commit_failure_still_returns_hint(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_ROUTING_ENABLED", "true")
    maker = _FakeSessionMaker(commit_exc=RuntimeError("db gone"))
    monkeypatch.setattr(app.db, "async_session_maker", maker)
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch, workspace_id=7, user_id=str(uuid4()))

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None


@pytest.mark.unit
async def test_no_session_without_ids(monkeypatch):
    """Session opens only when workspace_id + user_id are both usable."""
    maker = _FakeSessionMaker()
    monkeypatch.setattr(app.db, "async_session_maker", maker)
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)  # no ids at all

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None
    assert maker.sessions == []
    assert service.calls[0]["session"] is None


# ---------------------------------------------------------------------------
# UUID_BAD — guarded conversion, hint unaffected
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_non_uuid_user_id_passes_none_and_still_hints(monkeypatch):
    maker = _FakeSessionMaker()
    monkeypatch.setattr(app.db, "async_session_maker", maker)
    service = _StubService(_result())
    mw = _make_mw(
        service, monkeypatch, workspace_id=7, user_id="not-a-uuid"
    )

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None
    call = service.calls[0]
    assert call["user_id"] is None
    assert call["session"] is None  # incomplete ids → no session opened
    assert maker.sessions == []


# ---------------------------------------------------------------------------
# Empty newest HumanMessage — must not fall back to an older one
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_empty_newest_human_does_not_classify_older(monkeypatch):
    """The backward scan breaks on the FIRST HumanMessage regardless of
    content — an empty newest message means 'nothing to classify', not
    'classify the previous one'."""
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    state = _state(
        HumanMessage(content="Tìm chung cư Q7"),
        AIMessage(content="ok"),
        HumanMessage(content=""),
    )
    out = await mw.abefore_model(state, MagicMock())

    assert out is None
    assert service.calls == []


# ---------------------------------------------------------------------------
# Dedup key — message id preferred over text
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_same_text_different_message_id_reclassifies(monkeypatch):
    """A genuinely NEW HumanMessage (new id) with identical text is not
    suppressed — the dedup key is msg.id, not the text."""
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)

    first = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7", id="m1")), MagicMock()
    )
    second = await mw.abefore_model(
        _state(
            HumanMessage(content="Tìm chung cư Q7", id="m1"),
            first["messages"][0],
            AIMessage(content="đã route"),
            HumanMessage(content="Tìm chung cư Q7", id="m2"),
        ),
        MagicMock(),
    )

    assert first is not None
    assert second is not None
    assert len(service.calls) == 2


@pytest.mark.unit
async def test_same_message_id_dedups(monkeypatch):
    service = _StubService(exc=DecisionError("down", code="timeout"))
    mw = _make_mw(service, monkeypatch)
    state = _state(HumanMessage(content="Tìm chung cư Q7", id="m1"))

    assert await mw.abefore_model(state, MagicMock()) is None
    assert await mw.abefore_model(state, MagicMock()) is None
    assert len(service.calls) == 1


@pytest.mark.unit
async def test_marker_found_sets_dedup_key(monkeypatch):
    """Finding a marker records the dedup key — if context editing later
    evicts the marker, the message still isn't re-classified."""
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch)
    human = HumanMessage(content="Tìm chung cư Q7", id="m1")

    with_marker = _state(
        human, SystemMessage(content="<jev_routing_hint>\nx\n</jev_routing_hint>")
    )
    assert await mw.abefore_model(with_marker, MagicMock()) is None
    assert mw._last_classified == "m1"

    # Marker gone — dedup key still prevents re-payment.
    assert await mw.abefore_model(_state(human), MagicMock()) is None
    assert service.calls == []


# ---------------------------------------------------------------------------
# Decision-disabled — no session checkout
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [("DECISION_ENABLED", "false"), ("DECISION_ROUTING_ENABLED", "false")],
)
async def test_no_session_checkout_when_decision_layer_off(
    monkeypatch, env_name, env_value
):
    """With the decision layer disabled, decide() raises `disabled`
    before doing work — checking out a DB session would be pure waste."""
    monkeypatch.setenv(env_name, env_value)
    maker = _FakeSessionMaker()
    monkeypatch.setattr(app.db, "async_session_maker", maker)
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch, workspace_id=7, user_id=str(uuid4()))

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None  # stub service answers regardless of flags
    assert maker.sessions == []
    assert service.calls[0]["session"] is None


# ---------------------------------------------------------------------------
# Commit bounded by a fixed budget — wedged DB must not stall the hook
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_wedged_commit_times_out_and_still_hints(monkeypatch):
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_ROUTING_ENABLED", "true")
    monkeypatch.setattr(jev_router, "_COMMIT_TIMEOUT_SECONDS", 0.05)
    maker = _FakeSessionMaker(commit_sleep=5.0)
    monkeypatch.setattr(app.db, "async_session_maker", maker)
    service = _StubService(_result())
    mw = _make_mw(service, monkeypatch, workspace_id=7, user_id=str(uuid4()))

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None


# ---------------------------------------------------------------------------
# End-to-end — real DecisionService + strict validation, stub backend
# ---------------------------------------------------------------------------


class _StubBackend:
    """In-memory decision backend returning a canned BackendResult."""

    def __init__(self, result: BackendResult, name: str = "stub"):
        self.name = name
        self._result = result
        self.calls: list[dict[str, Any]] = []

    async def decide(self, state, questions, *, model=None, timeout=None):
        self.calls.append({"model": model, "timeout": timeout})
        return self._result


@pytest.mark.unit
async def test_end_to_end_through_real_decision_service(monkeypatch):
    """Exercise the middleware through a REAL DecisionService.decide():
    flag gating, the model pin, and strict answer validation all run
    for real against a stub backend."""
    monkeypatch.setenv("DECISION_ENABLED", "true")
    monkeypatch.setenv("DECISION_ROUTING_ENABLED", "true")
    monkeypatch.setattr(decision_config, "DECISION_FALLBACK_BACKEND", "none")

    mw = JevRouterMiddleware(subagent_descriptors=_DESCRIPTORS)
    criteria = mw._questions["subagent"].criteria
    # A structurally valid choice answer over the ACTUAL criteria —
    # keys match exactly, sum to 1, chosen value is the argmax.
    probabilities = dict.fromkeys(criteria, 0.0)
    probabilities.update(
        {"batdongsan": 0.9, "chainlens": 0.05, "none_needed": 0.05}
    )
    backend = _StubBackend(
        BackendResult(
            answers={
                "subagent": Answer(
                    kind="choice",
                    value="batdongsan",
                    confidence=0.9,
                    probabilities=probabilities,
                )
            },
            model="jev-1.13.0",
            latency_ms=1.0,
            input_tokens=10,
            output_tokens=2,
        )
    )
    monkeypatch.setattr(
        jev_router, "get_decision_service", lambda: DecisionService(backend)
    )

    out = await mw.abefore_model(
        _state(HumanMessage(content="Tìm chung cư Q7")), MagicMock()
    )

    assert out is not None
    assert "`batdongsan`" in out["messages"][0].content
    # The service applied its model pin (AD-J3), not a caller override.
    assert backend.calls[0]["model"] == decision_config.DECISION_JEV_MODEL
