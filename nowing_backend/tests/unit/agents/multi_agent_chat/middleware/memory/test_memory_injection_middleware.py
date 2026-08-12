"""TDD tests for Story 3.14 Task 2: MemoryInjectionMiddleware rewrite.

Covers the D4 private-owner/last-message/transcript guards and the D8
single-attempt failure-telemetry precedence (query/embedding/session-enter/
search terminal-first; display-name pending/recoverable; session-exit/render
override pending; cancellation propagates untouched).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.chat.multi_agent_chat.main_agent.middleware.memory import (
    middleware as mw_module,
)
from app.agents.chat.multi_agent_chat.main_agent.middleware.memory.middleware import (
    MemoryInjectionMiddleware,
)
from app.agents.chat.shared.middleware.compaction import PROTECTED_SYSTEM_PREFIXES
from app.db import ChatVisibility
from app.services.memory.search import ScoredMemory
from app.services.memory.vector import VectorValidationError

pytestmark = [pytest.mark.unit, pytest.mark.memory]


class _FakeMemory:
    def __init__(
        self,
        content: str = "Some fact.",
        type_: str = "semantic",
        created_at: str = "2026-07-26",
    ):
        self.content = content
        self.type = type_
        self.created_at = created_at


def _hit(content: str = "Some fact.") -> ScoredMemory:
    return ScoredMemory(memory=_FakeMemory(content), score=1.0, similarity=1.0)


class _FakeResult:
    def __init__(self, value: str | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> str | None:
        return self._value


class _FakeSavepoint:
    async def __aenter__(self) -> _FakeSavepoint:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _FakeSession:
    def __init__(
        self,
        *,
        display_name: str | None = None,
        display_name_exc: Exception | None = None,
    ):
        self.display_name = display_name
        self.display_name_exc = display_name_exc
        self.execute_calls = 0

    def begin_nested(self) -> _FakeSavepoint:
        return _FakeSavepoint()

    async def execute(self, _stmt: Any) -> _FakeResult:
        self.execute_calls += 1
        if self.display_name_exc is not None:
            raise self.display_name_exc
        return _FakeResult(self.display_name)


def _install_session(monkeypatch, session, *, enter_exc=None, exit_exc=None) -> None:
    @contextlib.asynccontextmanager
    async def _fake_shielded_session():
        if enter_exc is not None:
            raise enter_exc
        try:
            yield session
        finally:
            if exit_exc is not None:
                raise exit_exc

    monkeypatch.setattr(mw_module, "shielded_async_session", _fake_shielded_session)


def _install_search(
    monkeypatch, *, hits: list[ScoredMemory] | None = None, exc: Exception | None = None
):
    calls: list[dict[str, Any]] = []

    async def _fake_search(self, **kwargs: Any) -> list[ScoredMemory]:
        calls.append(kwargs)
        if exc is not None:
            raise exc
        return hits if hits is not None else []

    monkeypatch.setattr(mw_module.MemoryHybridSearch, "search", _fake_search)
    return calls


def _install_embedding(
    monkeypatch,
    *,
    embed_exc: Exception | None = None,
    validate_exc: Exception | None = None,
) -> None:
    def _fake_embed_texts(texts: list[str]) -> list[list[float]]:
        if embed_exc is not None:
            raise embed_exc
        return [[0.1, 0.2, 0.3]]

    def _fake_validate_single(result: Any) -> Any:
        return result[0]

    def _fake_validate_vector(value: Any, *, dimension: int) -> Any:
        if validate_exc is not None:
            raise validate_exc
        return value

    monkeypatch.setattr(mw_module, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(
        mw_module, "validate_single_embedding_result", _fake_validate_single
    )
    monkeypatch.setattr(mw_module, "validate_embedding_vector", _fake_validate_vector)


def _install_failure_recorder(monkeypatch) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []

    def _fake_record(*, scope: str, stage: str, reason: str) -> None:
        calls.append({"scope": scope, "stage": stage, "reason": reason})

    monkeypatch.setattr(mw_module, "record_memory_injection_failure", _fake_record)
    return calls


def _mw(
    *,
    user_id: str | None = "11111111-1111-1111-1111-111111111111",
    visibility: ChatVisibility = ChatVisibility.PRIVATE,
) -> MemoryInjectionMiddleware:
    return MemoryInjectionMiddleware(
        user_id=user_id, workspace_id=1, thread_visibility=visibility
    )


# --- _build_transcript_query (D4) -------------------------------------------


def test_build_transcript_query_matches_golden_example() -> None:
    messages = [
        HumanMessage(content="Where is the launch checklist?"),
        AIMessage(content="It is in the release folder."),
        HumanMessage(content="Summarize the remaining blockers."),
    ]
    query = mw_module._build_transcript_query(messages)
    assert query == (
        "human: Where is the launch checklist?\n"
        "\n"
        "assistant: It is in the release folder.\n"
        "\n"
        "human: Summarize the remaining blockers."
    )


def test_build_transcript_query_returns_none_when_nothing_usable() -> None:
    messages = [HumanMessage(content="   "), AIMessage(content="")]
    assert mw_module._build_transcript_query(messages) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("line1\r\nline2", "line1\nline2"),
        ("line1\rline2", "line1\nline2"),
        ("line1\nline2", "line1\nline2"),
        ("line1\vline2", "line1\nline2"),
        ("line1\fline2", "line1\nline2"),
        ("line1\u2028line2", "line1\nline2"),
        ("line1\u2029line2", "line1\nline2"),
    ],
)
def test_build_transcript_query_normalizes_line_terminators(
    raw: str, expected: str
) -> None:
    query = mw_module._build_transcript_query([HumanMessage(content=raw)])
    assert query == f"human: {expected}"


def test_build_transcript_query_skips_protected_system_and_empty_messages() -> None:
    messages = [
        SystemMessage(content=f"{PROTECTED_SYSTEM_PREFIXES[0]}\nsome tree"),
        HumanMessage(content="   "),
        AIMessage(content=""),
        HumanMessage(content="Real question."),
    ]
    assert mw_module._build_transcript_query(messages) == "human: Real question."


def test_build_transcript_query_truncates_boundary_record_with_trailing_space_marker() -> (
    None
):
    old_text = "OLD" * 2000
    messages = [
        HumanMessage(content=old_text),
        HumanMessage(content="Recent short question."),
    ]
    query = mw_module._build_transcript_query(messages)
    assert query is not None
    assert query.startswith("human: [...truncated...] ")
    assert query.endswith("human: Recent short question.")
    assert len(query) <= mw_module._MEMORY_QUERY_MAX_CHARS


# --- Guards (D4): zero telemetry, zero work ---------------------------------


@pytest.mark.asyncio
async def test_private_no_user_id_returns_none_with_zero_telemetry(monkeypatch) -> None:
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw(user_id=None)
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == []


@pytest.mark.asyncio
async def test_empty_messages_returns_none(monkeypatch) -> None:
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": []}, None)
    assert result is None
    assert failures == []


@pytest.mark.asyncio
async def test_last_message_not_human_returns_none(monkeypatch) -> None:
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    messages = [HumanMessage(content="hi"), AIMessage(content="hello")]
    result = await mw.abefore_agent({"messages": messages}, None)
    assert result is None
    assert failures == []


@pytest.mark.asyncio
async def test_entirely_unusable_transcript_returns_none_zero_telemetry(
    monkeypatch,
) -> None:
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="   ")]}, None)
    assert result is None
    assert failures == []


@pytest.mark.asyncio
async def test_team_scope_bypasses_private_owner_guard(monkeypatch) -> None:
    _install_embedding(monkeypatch)
    _install_search(monkeypatch, hits=[])
    _install_session(monkeypatch, _FakeSession())
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw(user_id=None, visibility=ChatVisibility.SEARCH_SPACE)
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == []


@pytest.mark.asyncio
async def test_team_scope_never_looks_up_display_name(monkeypatch) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name="Should Not Be Used")
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[_hit("Team fact.")])
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw(user_id=None, visibility=ChatVisibility.SEARCH_SPACE)
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is not None
    assert session.execute_calls == 0
    assert "<user_name>" not in result["messages"][1].content
    assert failures == []


# --- Terminal failures: embedding / session-enter / search -----------------


@pytest.mark.asyncio
async def test_embedding_provider_error_records_failure_once(monkeypatch) -> None:
    _install_embedding(monkeypatch, embed_exc=RuntimeError("boom"))
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [
        {"scope": "user", "stage": "embedding", "reason": "provider_error"}
    ]


@pytest.mark.asyncio
async def test_embedding_validation_error_uses_its_reason(monkeypatch) -> None:
    _install_embedding(monkeypatch, validate_exc=VectorValidationError("zero_norm"))
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [{"scope": "user", "stage": "embedding", "reason": "zero_norm"}]


@pytest.mark.asyncio
async def test_session_enter_error_records_failure(monkeypatch) -> None:
    _install_embedding(monkeypatch)
    _install_session(
        monkeypatch, _FakeSession(), enter_exc=RuntimeError("pool exhausted")
    )
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [{"scope": "user", "stage": "session", "reason": "enter_error"}]


@pytest.mark.asyncio
async def test_search_error_is_terminal_and_skips_display_name_lookup(
    monkeypatch,
) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name="Ada")
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, exc=RuntimeError("db exploded"))
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [{"scope": "user", "stage": "search", "reason": "query_error"}]
    assert session.execute_calls == 0


@pytest.mark.asyncio
async def test_session_exit_error_after_search_failure_is_not_double_recorded(
    monkeypatch,
) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession()
    _install_session(monkeypatch, session, exit_exc=RuntimeError("close failed"))
    _install_search(monkeypatch, exc=RuntimeError("db exploded"))
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [{"scope": "user", "stage": "search", "reason": "query_error"}]


@pytest.mark.asyncio
async def test_cancellation_during_search_propagates_untouched(monkeypatch) -> None:
    _install_embedding(monkeypatch)
    _install_session(monkeypatch, _FakeSession())
    _install_search(monkeypatch, exc=asyncio.CancelledError())
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    with pytest.raises(asyncio.CancelledError):
        await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert failures == []


# --- Display-name pending/recoverable + precedence overrides (D8) ----------


@pytest.mark.asyncio
async def test_display_name_lookup_failure_is_pending_and_flushed_when_nothing_later_fails(
    monkeypatch,
) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name_exc=RuntimeError("boom"))
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[_hit("A fact.")])
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is not None
    assert "<user_name>" not in result["messages"][1].content
    assert failures == [
        {"scope": "user", "stage": "display_name", "reason": "lookup_error"}
    ]


@pytest.mark.asyncio
async def test_display_name_failure_plus_zero_hits_still_flushes_pending(
    monkeypatch,
) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name_exc=RuntimeError("boom"))
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[])
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [
        {"scope": "user", "stage": "display_name", "reason": "lookup_error"}
    ]


@pytest.mark.asyncio
async def test_zero_hits_and_no_display_name_is_a_true_noop(monkeypatch) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name=None)
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[])
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == []


@pytest.mark.asyncio
async def test_session_exit_error_overrides_pending_display_name_failure(
    monkeypatch,
) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name_exc=RuntimeError("name lookup failed"))
    _install_session(monkeypatch, session, exit_exc=RuntimeError("close failed"))
    _install_search(monkeypatch, hits=[_hit()])
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [{"scope": "user", "stage": "session", "reason": "exit_error"}]


@pytest.mark.asyncio
async def test_render_error_overrides_pending_display_name_failure(monkeypatch) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name_exc=RuntimeError("boom"))
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[_hit("A fact.")])
    failures = _install_failure_recorder(monkeypatch)

    def _boom_render(*_args: Any, **_kwargs: Any) -> str:
        raise mw_module.MemoryRenderError("compose_error")

    monkeypatch.setattr(mw_module, "render_bounded_memory_injection", _boom_render)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [{"scope": "user", "stage": "render", "reason": "compose_error"}]


# --- Successful injection ----------------------------------------------------


@pytest.mark.asyncio
async def test_successful_injection_inserts_system_message_and_passes_correct_search_args(
    monkeypatch,
) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name="Ada Lovelace")
    _install_session(monkeypatch, session)
    calls = _install_search(monkeypatch, hits=[_hit("Prefers concise answers.")])
    failures = _install_failure_recorder(monkeypatch)
    mw = _mw()
    messages = [
        HumanMessage(content="hi"),
        AIMessage(content="hello"),
        HumanMessage(content="What do you know about me?"),
    ]
    result = await mw.abefore_agent({"messages": messages}, None)
    assert result is not None
    new_messages = result["messages"]
    assert len(new_messages) == 4
    assert isinstance(new_messages[1], SystemMessage)
    assert "<user_memory>" in new_messages[1].content
    assert "<user_name>Ada</user_name>" in new_messages[1].content
    assert failures == []

    assert len(calls) == 1
    assert calls[0]["user_id"] == mw.user_id
    assert calls[0]["top_k"] == mw_module._MEMORY_INJECTION_TOP_K
    assert calls[0]["query"]


@pytest.mark.asyncio
async def test_single_message_thread_inserts_system_message_at_index_zero(
    monkeypatch,
) -> None:
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name=None)
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[_hit("Fact.")])
    _install_failure_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is not None
    assert isinstance(result["messages"][0], SystemMessage)


@pytest.mark.asyncio
async def test_transcript_query_render_error_records_query_failure(monkeypatch) -> None:
    failures = _install_failure_recorder(monkeypatch)
    _install_embedding(monkeypatch)

    def _boom(messages: list[Any]) -> str | None:
        raise RuntimeError("unexpected normalization failure")

    monkeypatch.setattr(mw_module, "_build_transcript_query", _boom)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is None
    assert failures == [{"scope": "user", "stage": "query", "reason": "render_error"}]


# --- Story 3.17 AC3: truncation counter --------------------------------------


def _install_truncation_recorder(monkeypatch) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []

    def _fake_record(*, scope: str) -> None:
        calls.append({"scope": scope})

    monkeypatch.setattr(mw_module, "record_memory_injection_truncated", _fake_record)
    return calls


@pytest.mark.asyncio
async def test_truncation_counter_emitted_when_memory_overflows(monkeypatch) -> None:
    """AC3: memory_injection_truncated counter fires when the renderer truncates."""
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name="Ada")
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[_hit("W" * 20_000)])
    _install_failure_recorder(monkeypatch)
    truncations = _install_truncation_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is not None
    assert truncations == [{"scope": "user"}]


@pytest.mark.asyncio
async def test_truncation_counter_not_emitted_when_no_truncation(monkeypatch) -> None:
    """AC3: counter stays at zero when the rendered output fits without truncation."""
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name="Ada")
    _install_session(monkeypatch, session)
    _install_search(monkeypatch, hits=[_hit("Short fact.")])
    _install_failure_recorder(monkeypatch)
    truncations = _install_truncation_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is not None
    assert truncations == []


@pytest.mark.asyncio
async def test_truncation_counter_emitted_for_team_scope(monkeypatch) -> None:
    """AC3: truncation counter also fires for shared/team memory injection."""
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name=None)
    _install_session(monkeypatch, session)
    _install_search(
        monkeypatch,
        hits=[_hit("W" * 20_000)],
    )
    _install_failure_recorder(monkeypatch)
    truncations = _install_truncation_recorder(monkeypatch)
    mw = _mw(visibility=ChatVisibility.SEARCH_SPACE)
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is not None
    assert truncations == [{"scope": "team"}]


@pytest.mark.asyncio
async def test_truncation_counter_boundary_exactly_max_chars(monkeypatch) -> None:
    """AC3: counter fires when content is just over the 8,000-char budget."""
    _install_embedding(monkeypatch)
    session = _FakeSession(display_name="Ada")
    _install_session(monkeypatch, session)
    # Build content that forces the renderer into Rule 9 but by the smallest
    # margin possible, exercising the `len(result) > max_chars` guard.
    _install_search(monkeypatch, hits=[_hit("W" * 8_001)])
    _install_failure_recorder(monkeypatch)
    truncations = _install_truncation_recorder(monkeypatch)
    mw = _mw()
    result = await mw.abefore_agent({"messages": [HumanMessage(content="hi")]}, None)
    assert result is not None
    assert result["messages"][1].content is not None
    assert len(result["messages"][1].content) <= 8_000
    assert truncations == [{"scope": "user"}]
