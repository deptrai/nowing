"""Red-phase unit tests for Story 18.2 ``stream_new_chat`` orchestrator.

These tests drive the not-yet-extended orchestrator with heavy
monkeypatching of DB, LLM, and streaming seams.  They assert that:

* ``set_request_tenant_context`` is called with workspace + client_id + agent_id.
* An ``agent_id`` triggers loading of the registry ``AgentConfig`` and the
  resulting runtime ``AgentConfig`` passed to ``build_main_agent_for_thread``
  carries the registry's ``system_instructions``.
* ``platform_metadata`` is forwarded into ``build_new_chat_input_state``.
* When ``agent_id`` is absent the default Nowing agent config is used.

The tests will fail until 18.2 adds the ``platform_metadata``,
``agent_config_override`` parameters and the AgentConfig merge logic.
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
    stream_new_chat,
)

pytestmark = pytest.mark.unit


class _FakeScalarResult:
    def __init__(self, first: Any, all_rows: list[Any] | None = None) -> None:
        self._first = first
        self._all = all_rows or []

    def first(self) -> Any:
        return self._first

    def all(self) -> list[Any]:
        return list(self._all)


class _FakeResult:
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
        client_id="bdsai.vn",
        slug="bdsai-listing-assistant",
        name="BDS Listing Assistant",
        system_instructions="You are a BDS listing assistant.",
        model_name="gpt-4o",
        citations_enabled=False,
        enabled_tools=["search_knowledge_base", "ls"],
        disabled_tools=["deep_research"],
        is_active=True,
    )


@pytest.fixture
def _patch_orchestrator_deps(monkeypatch: pytest.MonkeyPatch):
    """Patch the orchestrator's production dependencies so we can run just far
    enough to capture the key call sites: tenant context, AgentConfig merge,
    and input-state assembly."""

    import app.services.token_tracking_service as _tts
    import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

    # The orchestrator calls ``async_session_maker()`` once per turn and uses
    # that same session for registry lookup. A single shared fake session lets
    # tests pre-seed ``registry_agent`` before consuming the generator.
    _shared_fake_session = _FakeSession()
    _shared_fake_session.registry_agent = _registry_agent()

    async def _fake_session_maker(*_args: Any, **_kwargs: Any) -> _FakeSession:
        return _shared_fake_session

    monkeypatch.setattr(_orchestrator, "async_session_maker", _fake_session_maker)
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
    monkeypatch.setattr(_tts, "start_turn", lambda: MagicMock(name="accumulator"))


def _run_first_yield(gen: AsyncGenerator[str, None]) -> str:
    """Advance ``stream_new_chat`` to its first yield, then close it.

    This is enough to exercise the validation + auto-pin + LLM bundle +
    agent build + input-state assembly blocks without needing a full
    streaming run.
    """
    return asyncio.get_event_loop().run_until_complete(_first_yield_then_close(gen))


async def _first_yield_then_close(gen: AsyncGenerator[str, None]) -> str:
    try:
        chunk = await anext(gen)
    finally:
        await gen.aclose()
    return chunk


class TestStreamNewChatAgentAndMetadata:
    def test_forwards_platform_metadata_to_input_state(
        self, _patch_orchestrator_deps, monkeypatch
    ) -> None:
        """AC-3: platform_metadata reaches build_new_chat_input_state."""
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        platform_metadata = {"source": "bdsai", "listing_id": 42}

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=101,
            user_id="user-1",
            client_id="bdsai.vn",
            agent_id="bdsai-listing-assistant",
            platform_metadata=platform_metadata,
        )

        _run_first_yield(gen)

        _orchestrator.set_request_tenant_context.assert_called_once()
        _call = _orchestrator.set_request_tenant_context.call_args
        assert _call.kwargs.get("client_id") == "bdsai.vn"
        assert _call.kwargs.get("agent_id") == "bdsai-listing-assistant"

        _orchestrator.build_new_chat_input_state.assert_called_once()
        input_kwargs = _orchestrator.build_new_chat_input_state.call_args.kwargs
        assert input_kwargs.get("platform_metadata") == platform_metadata
        assert input_kwargs.get("client_id") == "bdsai.vn"

    def test_merges_registry_agent_config_override(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-1: a pre-resolved registry AgentConfig is merged into the runtime
        AgentConfig so build_main_agent_for_thread sees the custom system
        instructions and registry model/citations settings."""
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        registry = _registry_agent()

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=101,
            user_id="user-1",
            client_id="bdsai.vn",
            agent_id="bdsai-listing-assistant",
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

    def test_loads_registry_agent_config_from_db(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-1: when no override is supplied, stream_new_chat queries the
        agent_configs registry by client_id + agent_id and merges the row."""
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        registry = _registry_agent()

        # Make the fake session return the registry row on any execute(...).
        # The 18.2 implementation will issue ``select(AgentConfig).where(...)``.
        session = asyncio.get_event_loop().run_until_complete(
            _orchestrator.async_session_maker()
        )
        session.registry_agent = registry

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=102,
            user_id="user-1",
            client_id="bdsai.vn",
            agent_id="bdsai-listing-assistant",
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

    def test_falls_back_to_default_agent_when_agent_id_is_absent(
        self, _patch_orchestrator_deps
    ) -> None:
        """AC-4: with no agent_id/client_id the default Nowing chat agent is
        preserved and platform_metadata/client_id default to None in the
        input state."""
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        gen = stream_new_chat(
            user_query="hello",
            workspace_id=1,
            chat_id=103,
            user_id="user-1",
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
        SSE error frame and done marker."""
        import app.tasks.chat.streaming.flows.new_chat.orchestrator as _orchestrator

        session = asyncio.get_event_loop().run_until_complete(
            _orchestrator.async_session_maker()
        )
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
            user_id="user-1",
            client_id="bdsai.vn",
            agent_id="missing-agent",
            platform_metadata={"source": "bdsai"},
        )

        chunks = asyncio.get_event_loop().run_until_complete(_collect(gen))
        assert chunks, "expected at least an error SSE frame and done marker"
        payload = "".join(chunks)
        assert "AGENT_NOT_FOUND" in payload or "agent not found" in payload.lower()
