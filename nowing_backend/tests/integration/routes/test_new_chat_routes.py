"""Integration tests for Story 18.2 in the internal new-chat routes.

These tests run against a real Postgres database and the full FastAPI app.
The streaming ``POST /new_chat`` tests monkeypatch ``stream_new_chat`` so they
exercise the route and orchestrator parameter plumbing without making actual
LLM calls; they are marked ``expensive`` because an unmocked streaming run
would hit the full agent/LLM stack.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    AgentConfig,
    ChatVisibility,
    NewChatThread,
    User,
    Workspace,
)
from app.routes import new_chat_routes

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def db_agent_config(db_session: AsyncSession) -> AgentConfig:
    """A vertical-client agent config with custom system instructions."""
    config = AgentConfig(
        client_id="bdsai.vn",
        slug="bdsai-listing-assistant",
        name="BDS Listing Assistant",
        system_instructions="You are a BDS listing assistant. Always cite sources.",
        model_name="gpt-4o",
        citations_enabled=False,
        enabled_tools=["search_knowledge_base", "ls"],
        disabled_tools=["deep_research"],
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()
    return config


@pytest_asyncio.fixture
async def db_client_thread(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> NewChatThread:
    """A thread owned by the regular user, tagged with a vertical client_id."""
    thread = NewChatThread(
        title="Client Thread",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
        client_id="bdsai.vn",
    )
    db_session.add(thread)
    await db_session.flush()
    return thread


class TestCreateThread:
    async def test_post_threads_persists_client_id_and_agent_id(
        self,
        client_as_regular_user: Any,
        db_session: AsyncSession,
        db_workspace: Workspace,
    ) -> None:
        """AC-1/AC-2: POST /threads stores client_id and agent_id on the row."""
        payload = {
            "title": "Tagged Thread",
            "archived": False,
            "workspace_id": db_workspace.id,
            "client_id": "bdsai.vn",
            "agent_id": "bdsai-listing-assistant",
        }

        response = await client_as_regular_user.post("/api/v1/threads", json=payload)
        assert response.status_code == 200, response.text

        body = response.json()
        assert body.get("client_id") == "bdsai.vn"
        assert body.get("agent_id") == "bdsai-listing-assistant"

        row = (
            await db_session.execute(
                select(NewChatThread).where(NewChatThread.id == body["id"])
            )
        ).scalar_one()
        assert row.client_id == "bdsai.vn"
        assert getattr(row, "agent_id", None) == "bdsai-listing-assistant"

    async def test_post_threads_legacy_body_still_works(
        self,
        client_as_regular_user: Any,
        db_session: AsyncSession,
        db_workspace: Workspace,
    ) -> None:
        """AC-4: a legacy thread create without client_id/agent_id is accepted
        and leaves both columns NULL."""
        payload = {
            "title": "Legacy Thread",
            "archived": False,
            "workspace_id": db_workspace.id,
        }

        response = await client_as_regular_user.post("/api/v1/threads", json=payload)
        assert response.status_code == 200, response.text

        body = response.json()
        assert body.get("client_id") is None
        assert body.get("agent_id") is None

        row = (
            await db_session.execute(
                select(NewChatThread).where(NewChatThread.id == body["id"])
            )
        ).scalar_one()
        assert row.client_id is None
        assert getattr(row, "agent_id", None) is None


class TestNewChat:
    @pytest.mark.expensive
    async def test_post_new_chat_with_agent_id_resolves_system_instructions(
        self,
        client_as_regular_user: Any,
        db_session: AsyncSession,
        db_user: User,
        db_workspace: Workspace,
        db_client_thread: NewChatThread,
        db_agent_config: AgentConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-1: POST /new_chat with agent_id loads the registry AgentConfig and
        forwards an ``agent_config_override`` whose system instructions match the
        configured agent, plus client_id and platform_metadata.
        """
        calls: list[tuple[tuple, dict]] = []

        async def _fake_stream(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[bytes, None]:
            calls.append((args, kwargs))
            yield b'data: {"type":"text","content":"hello"}\n\n'

        monkeypatch.setattr(new_chat_routes, "stream_new_chat", _fake_stream)

        platform_metadata = {"source": "bdsai", "listing_id": 42}
        response = await client_as_regular_user.post(
            "/api/v1/new_chat",
            json={
                "chat_id": db_client_thread.id,
                "user_query": "List nearby properties",
                "workspace_id": db_workspace.id,
                "agent_id": "bdsai-listing-assistant",
                "client_id": "bdsai.vn",
                "platform_metadata": platform_metadata,
            },
        )
        assert response.status_code == 200, response.text
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert calls, "stream_new_chat was not invoked"

        kwargs = calls[0][1]
        assert "client_id" in kwargs, (
            "client_id must be explicitly passed to stream_new_chat"
        )
        assert "agent_id" in kwargs, (
            "agent_id must be explicitly passed to stream_new_chat"
        )
        assert "platform_metadata" in kwargs, (
            "platform_metadata must be explicitly passed to stream_new_chat"
        )
        assert kwargs.get("client_id") == "bdsai.vn"
        assert kwargs.get("agent_id") == "bdsai-listing-assistant"
        assert kwargs.get("platform_metadata") == platform_metadata

        agent_config_override = kwargs.get("agent_config_override")
        assert agent_config_override is not None
        assert (
            agent_config_override.system_instructions
            == db_agent_config.system_instructions
        )
        assert (
            agent_config_override.citations_enabled == db_agent_config.citations_enabled
        )
        assert agent_config_override.model_name == db_agent_config.model_name

    @pytest.mark.expensive
    async def test_post_new_chat_without_agent_id_is_regression_safe(
        self,
        client_as_regular_user: Any,
        db_session: AsyncSession,
        db_user: User,
        db_workspace: Workspace,
        db_client_thread: NewChatThread,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-4: POST /new_chat without agent_id/client_id still works and uses
        the default Nowing agent."""
        calls: list[tuple[tuple, dict]] = []

        async def _fake_stream(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[bytes, None]:
            calls.append((args, kwargs))
            yield b'data: {"type":"text","content":"ok"}\n\n'

        monkeypatch.setattr(new_chat_routes, "stream_new_chat", _fake_stream)

        response = await client_as_regular_user.post(
            "/api/v1/new_chat",
            json={
                "chat_id": db_client_thread.id,
                "user_query": "Hello",
                "workspace_id": db_workspace.id,
            },
        )
        assert response.status_code == 200, response.text
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert calls, "stream_new_chat was not invoked"

        kwargs = calls[0][1]
        assert "client_id" in kwargs, (
            "client_id must be explicitly passed to stream_new_chat"
        )
        assert "agent_id" in kwargs, (
            "agent_id must be explicitly passed to stream_new_chat"
        )
        assert "platform_metadata" in kwargs, (
            "platform_metadata must be explicitly passed to stream_new_chat"
        )
        assert kwargs.get("client_id") is None
        assert kwargs.get("agent_id") is None
        assert kwargs.get("platform_metadata") is None

        agent_config = kwargs.get("agent_config")
        assert agent_config is not None
        assert agent_config.system_instructions is None
        assert agent_config.use_default_system_instructions is True
