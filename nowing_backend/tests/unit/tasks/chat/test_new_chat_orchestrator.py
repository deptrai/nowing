"""Unit tests for ``stream_new_chat`` orchestrator (Stories 18.2 and 18.4).

These tests drive the orchestrator with heavy monkeypatching of DB, LLM,
and streaming seams. They assert that:

* ``set_request_tenant_context`` is called with workspace + client_id + agent_id.
* An ``agent_id`` triggers loading of the registry ``AgentConfig`` and the
  resulting runtime ``AgentConfig`` passed to ``build_main_agent_for_thread``
  carries the registry's ``system_instructions``.
* ``platform_metadata`` is forwarded into ``build_new_chat_input_state``.
* When ``agent_id`` is absent the default Nowing agent config is used.
* Admin-injected ``system_instructions`` are clamped and sanitized.
* An explicit empty ``enabled_tools`` list is fail-closed.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.chat.runtime.llm_config import AgentConfig as RuntimeAgentConfig
from app.db import AgentConfig as RegistryAgentConfig
from app.tasks.chat.streaming.flows.new_chat.input_state import (
    NewChatInputState,
)
from app.tasks.chat.streaming.flows.new_chat.orchestrator import (
    _MAX_INSTRUCTIONS_LEN,
    stream_new_chat,
)

pytestmark = pytest.mark.unit

_TEST_CLIENT_ID = "bdsai.vn"
_TEST_AGENT_SLUG = "bdsai-listing-assistant"
_TEST_AGENT_NAME = "BDS Listing Assistant"
_TEST_USER_ID = "user-1"
_TEST_LISTING_ID = 42
_TEST_PLATFORM_METADATA = {"source": "bdsai", "listing_id": _TEST_LISTING_ID}
_OVERSIZE_INSTRUCTIONS_LEN = _MAX_INSTRUCTIONS_LEN + 1_000


class _FakeScalarResult:
    """Fake ``sqlalchemy.engine.Result.scalars()`` return."""

    def __init__(self, first: Any, all_rows: list[Any] | None = None) -> None:
        self._first = first
        self._all = all_rows or []

    def first(self) -> Any:
        return self._first

    def all(self) -> list[Any]:
        return list(self._all)


class _FakeResult:
    """Fake ``sqlalchemy.engine.Result``."""

    def __init__(self, first: Any, all_rows: list[Any] | None = None) -> None:
        self._first = first
        self._all = all_rows or []

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._first, self._all)


class _FakeSession:
    """Minimal async session stand-in for the orchestrator unit tests."""

    def __init__(self, *, registry_agent: Any = None) -> None:
        self.registry_agent = registry_agent
        self.committed = False
        self.closed = False
        self.expunged = False

    async def get(self, _model: Any, _pk: Any) -> Any:
        return SimpleNamespace(research_thread_id=1)

    async def execute(self, _stmt: Any, *_args: Any, **_kwargs: Any) -> _FakeResult:
        return _FakeResult(self.registry_agent)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    async def close(self) -> None:
        self.closed = True

    def expunge_all(self) -> None:
        self.expunged = True

    @contextlib.asynccontextmanager
    async def begin_nested(self) -> AsyncGenerator[_FakeSession, None]:
        yield self


def _default_runtime_config() -> RuntimeAgentConfig:
    return RuntimeAgentConfig(
        provider="openai",
        model_name="gpt-4o-mini",
        api_key="sk-test",
        system_instructions=None,
        use_default_system_instructions=True,
        citations_enabled=True,
    )


def _registry_agent() -> RegistryAgentConfig:
    return RegistryAgentConfig(
        client_id=_TEST_CLIENT_ID,
        slug=_TEST_AGENT_SLUG,
        name=_TEST_AGENT_NAME,
        system_instructions="You are a BDS listing assistant.",
        model_name="gpt-4o",
        citations_enabled=False,
        enabled_tools=["search_knowledge_base", "ls"],
        disabled_tools=["deep_research"],
        is_active=True,
    )


def _run_sync(coro: Any) -> Any:
    """Run an async coroutine from a synchronous test."""
    return asyncio.run(coro)


def _run_first_yield(gen: AsyncGenerator[str, None]) -> str:
    """Advance ``stream_new_chat`` to its first yield, then close it.

    This is enough to exercise the validation + auto-pin + LLM bundle +
    agent build + input-state assembly blocks without needing a full
    streaming run.
    """
    return _run_sync(_first_yield_then_close(gen))


async def _first_yield_then_close(gen: AsyncGenerator[str, None]) -> str:
    try:
        chunk = await anext(gen)
    finally:
        await gen.aclose()
    return chunk


def _patch_session_maker(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: _FakeSession,
) -> None:
    """Patch the orchestrator's async session factory to return ``fake_session``."""
    import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

    async def _fake_session_maker(*_args: Any, **_kwargs: Any) -> _FakeSession:
        return fake_session

    monkeypatch.setattr(_orchestrator, "async_session_maker", _fake_session_maker)


def _patch_tenant_and_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch tenant context and LLM bundle helpers."""
    import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

    monkeypatch.setattr(_orchestrator, "set_request_tenant_context", AsyncMock())
    monkeypatch.setattr(
        _orchestrator,
        "resolve_initial_auto_pin",
        AsyncMock(return_value=SimpleNamespace(error=None, llm_config_id=1)),
    )
    monkeypatch.setattr(
        _orchestrator,
        "load_llm_bundle",
        AsyncMock(
            return_value=(MagicMock(name="llm"), _default_runtime_config(), None)
        ),
    )
    monkeypatch.setattr(
        _orchestrator, "check_image_input_capability", lambda **_kw: None
    )
    monkeypatch.setattr(_orchestrator, "needs_credit_quota", lambda _cfg, _user: False)
    monkeypatch.setattr(
        _orchestrator, "setup_connector_service", AsyncMock(return_value=MagicMock())
    )
    monkeypatch.setattr(
        _orchestrator, "get_chat_checkpointer", AsyncMock(return_value=MagicMock())
    )


def _patch_agent_build_and_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch agent build and input-state assembly."""
    import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

    monkeypatch.setattr(_orchestrator, "build_main_agent_for_thread", AsyncMock())
    monkeypatch.setattr(
        _orchestrator,
        "build_new_chat_input_state",
        AsyncMock(
            return_value=NewChatInputState(
                input_state={"messages": []}, accepted_folder_ids=[]
            )
        ),
    )


def _patch_streaming_and_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch streaming frame and background task helpers."""
    import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

    monkeypatch.setattr(
        _orchestrator,
        "iter_initial_frames",
        lambda *_a, **_k: [b'data: {"type":"start"}\n\n'],
    )
    monkeypatch.setattr(_orchestrator, "spawn_persist_user_task", MagicMock())
    monkeypatch.setattr(_orchestrator, "spawn_set_ai_responding_bg", MagicMock())
    monkeypatch.setattr(_orchestrator, "log_file_contract", MagicMock())
    monkeypatch.setattr(_orchestrator, "log_system_snapshot", MagicMock())
    monkeypatch.setattr(_orchestrator, "set_agent_mode", MagicMock())
    monkeypatch.setattr(_orchestrator, "end_turn", MagicMock())
    monkeypatch.setattr(_orchestrator, "close_chat_request_span", MagicMock())
    monkeypatch.setattr(
        _orchestrator, "close_session_and_clear_ai_responding", AsyncMock()
    )
    monkeypatch.setattr(_orchestrator, "finalize_assistant_message", AsyncMock())
    monkeypatch.setattr(
        _orchestrator,
        "open_chat_request_span",
        MagicMock(return_value=(contextlib.nullcontext(), MagicMock())),
    )
    monkeypatch.setattr(_orchestrator, "_perf_log", MagicMock())
    monkeypatch.setattr(_orchestrator, "ot", MagicMock())


def _patch_token_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch token tracking service."""
    import app.services.token_tracking_service as _tts

    monkeypatch.setattr(_tts, "start_turn", lambda: MagicMock(name="accumulator"))


@pytest.fixture
def _patch_orchestrator_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the orchestrator's production dependencies for unit tests.

    Each test gets its own fake session so shared mutable state does not leak
    between tests.
    """
    fake_session = _FakeSession(registry_agent=_registry_agent())
    _patch_session_maker(monkeypatch, fake_session)
    _patch_tenant_and_llm(monkeypatch)
    _patch_agent_build_and_input(monkeypatch)
    _patch_streaming_and_logging(monkeypatch)
    _patch_token_tracking(monkeypatch)


class TestStreamNewChatAgentAndMetadata:
    def test_forwards_platform_metadata_to_input_state(
        self,
        _patch_orchestrator_deps,
    ) -> None:
        """AC-3: platform_metadata reaches build_new_chat_input_state."""
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=101,
            user_id=_TEST_USER_ID,
            client_id=_TEST_CLIENT_ID,
            agent_id=_TEST_AGENT_SLUG,
            platform_metadata=_TEST_PLATFORM_METADATA,
        )

        _run_first_yield(gen)

        _orchestrator.set_request_tenant_context.assert_called_once()
        _call = _orchestrator.set_request_tenant_context.call_args
        assert _call.kwargs.get("client_id") == _TEST_CLIENT_ID
        assert _call.kwargs.get("agent_id") == _TEST_AGENT_SLUG

        _orchestrator.build_new_chat_input_state.assert_called_once()
        input_kwargs = _orchestrator.build_new_chat_input_state.call_args.kwargs
        assert input_kwargs.get("platform_metadata") == _TEST_PLATFORM_METADATA
        assert input_kwargs.get("client_id") == _TEST_CLIENT_ID

    def test_merges_registry_agent_config_override(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-1: a pre-resolved registry AgentConfig is merged into the runtime
        AgentConfig so build_main_agent_for_thread sees the custom system
        instructions and registry model/citations settings.
        """
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        registry = _registry_agent()

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=101,
            user_id=_TEST_USER_ID,
            client_id=_TEST_CLIENT_ID,
            agent_id=_TEST_AGENT_SLUG,
            platform_metadata={"source": "bdsai"},
            agent_config_override=registry,
        )

        _run_first_yield(gen)

        _orchestrator.build_main_agent_for_thread.assert_called_once()
        agent_config = _orchestrator.build_main_agent_for_thread.call_args.kwargs.get(
            "agent_config"
        )
        assert agent_config is not None
        assert agent_config.system_instructions == registry.system_instructions
        assert agent_config.use_default_system_instructions is True
        assert agent_config.citations_enabled == registry.citations_enabled
        assert agent_config.model_name == registry.model_name

        kwargs = _orchestrator.build_main_agent_for_thread.call_args.kwargs
        assert kwargs.get("enabled_tools") == registry.enabled_tools
        assert kwargs.get("disabled_tools") == registry.disabled_tools

    def test_loads_registry_agent_config_from_db(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-1: when no override is supplied, stream_new_chat queries the
        agent_configs registry by client_id + agent_id and merges the row.
        """
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        registry = _registry_agent()

        # Make the fake session return the registry row on any execute(...).
        session = _run_sync(_orchestrator.async_session_maker())
        session.registry_agent = registry

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=102,
            user_id=_TEST_USER_ID,
            client_id=_TEST_CLIENT_ID,
            agent_id=_TEST_AGENT_SLUG,
            platform_metadata={"source": "bdsai"},
        )

        _run_first_yield(gen)

        _orchestrator.build_main_agent_for_thread.assert_called_once()
        agent_config = _orchestrator.build_main_agent_for_thread.call_args.kwargs.get(
            "agent_config"
        )
        assert agent_config is not None
        assert agent_config.system_instructions == registry.system_instructions
        assert agent_config.model_name == registry.model_name

        kwargs = _orchestrator.build_main_agent_for_thread.call_args.kwargs
        assert kwargs.get("enabled_tools") == registry.enabled_tools
        assert kwargs.get("disabled_tools") == registry.disabled_tools

    def test_falls_back_to_default_agent_when_agent_id_is_absent(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-4: with no agent_id/client_id the default Nowing chat agent is
        preserved and platform_metadata/client_id default to None in the
        input state.
        """
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=103,
            user_id=_TEST_USER_ID,
            platform_metadata=None,
        )

        _run_first_yield(gen)

        _orchestrator.set_request_tenant_context.assert_called_once()
        tenant_kwargs = _orchestrator.set_request_tenant_context.call_args.kwargs
        assert tenant_kwargs.get("client_id") is None
        assert tenant_kwargs.get("agent_id") is None

        _orchestrator.build_main_agent_for_thread.assert_called_once()
        agent_config = _orchestrator.build_main_agent_for_thread.call_args.kwargs.get(
            "agent_config"
        )
        assert agent_config is not None
        assert agent_config.system_instructions is None
        assert agent_config.use_default_system_instructions is True

        _orchestrator.build_new_chat_input_state.assert_called_once()
        input_kwargs = _orchestrator.build_new_chat_input_state.call_args.kwargs
        assert input_kwargs.get("client_id") is None
        assert input_kwargs.get("platform_metadata") is None

    def test_fails_closed_on_missing_or_inactive_agent(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-1/AC-5: an agent_id with no active registry row emits a 404-style
        SSE error frame and done marker.
        """
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        session = _run_sync(_orchestrator.async_session_maker())
        session.registry_agent = None  # No agent found

        async def _collect(gen: AsyncGenerator[str, None]) -> list[str]:
            chunks: list[str] = []
            async for chunk in gen:
                chunks.append(chunk)
            return chunks

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=104,
            user_id=_TEST_USER_ID,
            client_id=_TEST_CLIENT_ID,
            agent_id="missing-agent",
            platform_metadata={"source": "bdsai"},
        )

        chunks = _run_sync(_collect(gen))
        assert chunks, "expected at least an error SSE frame and done marker"
        payload = "".join(chunks)
        assert "AGENT_NOT_FOUND" in payload or "agent not found" in payload.lower()

    def test_empty_enabled_tools_is_fail_closed(self, _patch_orchestrator_deps) -> None:
        """AC-2: an explicit empty enabled_tools list means no tools."""
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        registry = _registry_agent()
        registry.enabled_tools = []
        registry.disabled_tools = []

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=105,
            user_id=_TEST_USER_ID,
            client_id=_TEST_CLIENT_ID,
            agent_id=_TEST_AGENT_SLUG,
            platform_metadata={"source": "bdsai"},
            agent_config_override=registry,
        )

        _run_first_yield(gen)

        kwargs = _orchestrator.build_main_agent_for_thread.call_args.kwargs
        assert kwargs.get("enabled_tools") == []
        assert kwargs.get("disabled_tools") == []

    def test_system_instructions_are_clamped_and_sanitized(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-1/AC-4: instructions are capped at _MAX_INSTRUCTIONS_LEN and
        Jinja-like markers are stripped.
        """
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        registry = _registry_agent()
        registry.system_instructions = (
            "Use {{secret}}. Today is {resolved_today}. "
            + "x" * _OVERSIZE_INSTRUCTIONS_LEN
        )

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=106,
            user_id=_TEST_USER_ID,
            client_id=_TEST_CLIENT_ID,
            agent_id=_TEST_AGENT_SLUG,
            agent_config_override=registry,
        )

        _run_first_yield(gen)

        agent_config = _orchestrator.build_main_agent_for_thread.call_args.kwargs.get(
            "agent_config"
        )
        assert agent_config is not None
        assert len(agent_config.system_instructions) <= _MAX_INSTRUCTIONS_LEN
        assert "{{secret}}" not in agent_config.system_instructions
        assert (
            "{" not in agent_config.system_instructions
            or "{resolved_today}" in agent_config.system_instructions
        )
