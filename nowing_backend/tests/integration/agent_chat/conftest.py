"""Shared fixtures for HTTP-level public agent-chat integration tests."""

from __future__ import annotations

import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

import app.users as users_module
from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    AgentConfig,
    NewChatThread,
    PersonalAccessToken,
    ResearchThread,
    User,
    VerticalClient,
    Workspace,
    get_async_session,
)
from tests.integration.conftest import _EMBEDDING_DIM

CLIENT_ID = "testclient.vn"
AGENT_ID = "test-agent"
AGENT_CHAT_SCOPES = [
    "agent_chat:thread:create",
    "agent_chat:message:create",
    "agent_chat:thread:read",
]


def _pat_token_hash() -> str:
    return secrets.token_hex(32)


@pytest_asyncio.fixture
async def db_vertical_client(db_session: AsyncSession) -> VerticalClient:
    """An active vertical client for the agent-chat tests."""
    client = VerticalClient(
        client_id=CLIENT_ID,
        display_name="Test Vertical Client",
        is_active=True,
    )
    db_session.add(client)
    await db_session.flush()
    return client


@pytest_asyncio.fixture
async def db_agent_config(
    db_session: AsyncSession,
    db_vertical_client: VerticalClient,
) -> AgentConfig:
    """An active agent config bound to the vertical client."""
    config = AgentConfig(
        client_id=db_vertical_client.client_id,
        name="Test Agent",
        display_name="Test Agent",
        slug=AGENT_ID,
        is_active=True,
        enabled_tools=[],
        disabled_tools=[],
    )
    db_session.add(config)
    await db_session.flush()
    return config


@pytest_asyncio.fixture
async def db_pat(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    db_vertical_client: VerticalClient,
    db_agent_config: AgentConfig,
) -> PersonalAccessToken:
    """A scoped PAT bound to one client and one agent."""
    pat = PersonalAccessToken(
        user_id=db_user.id,
        user=db_user,
        token_hash=_pat_token_hash(),
        token_prefix="nwtest",
        label="agent-chat-test",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        workspace_id=db_workspace.id,
        client_id=db_vertical_client.client_id,
        agent_id=db_agent_config.slug,
        scopes=AGENT_CHAT_SCOPES,
        token_kind="agent_chat",
    )
    db_session.add(pat)
    await db_session.flush()
    return pat


@pytest_asyncio.fixture
async def db_pat_no_agent(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    db_vertical_client: VerticalClient,
) -> PersonalAccessToken:
    """A scoped PAT bound to a client but without an explicit agent."""
    pat = PersonalAccessToken(
        user_id=db_user.id,
        user=db_user,
        token_hash=_pat_token_hash(),
        token_prefix="nwtest",
        label="agent-chat-no-agent-test",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        workspace_id=db_workspace.id,
        client_id=db_vertical_client.client_id,
        agent_id=None,
        scopes=AGENT_CHAT_SCOPES,
        token_kind="agent_chat",
    )
    db_session.add(pat)
    await db_session.flush()
    return pat


@asynccontextmanager
async def _agent_chat_client(
    db_session: AsyncSession,
    db_user: User,
    pat: PersonalAccessToken,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Build an :class:`httpx.AsyncClient` that is authenticated for agent-chat.

    The client runs against the real ``app`` with ``get_async_session`` and
    ``get_auth_context`` overridden, and the Redis-backed rate limiters and
    public-surface feature flag patched to no-ops / True.
    """
    from app.auth import agent_chat as auth_agent_chat
    from app.routes import agent_chat_routes as acr

    async def _session_override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _fake_get_auth_context(
        request,
        session,
        user_manager=None,
    ) -> AuthContext:
        return AuthContext.pat_auth(db_user, pat)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = _session_override

    monkeypatch.setattr(users_module, "get_auth_context", _fake_get_auth_context)
    monkeypatch.setattr(auth_agent_chat.config, "AGENT_CHAT_PUBLIC_ENABLED", True)
    monkeypatch.setattr(acr, "AGENT_CHAT_PUBLIC_ENABLED", True)
    monkeypatch.setattr(acr, "check_agent_chat_limits", lambda *a, **k: None)
    monkeypatch.setattr(acr, "hit_agent_chat_limits", lambda *a, **k: None)

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def agent_chat_client(
    db_session: AsyncSession,
    db_user: User,
    db_pat: PersonalAccessToken,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client authenticated as ``db_pat`` (agent bound)."""
    async with _agent_chat_client(db_session, db_user, db_pat, monkeypatch) as client:
        yield client


@pytest_asyncio.fixture
async def agent_chat_client_no_agent(
    db_session: AsyncSession,
    db_user: User,
    db_pat_no_agent: PersonalAccessToken,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client authenticated as ``db_pat_no_agent`` (no agent bound)."""
    async with _agent_chat_client(
        db_session, db_user, db_pat_no_agent, monkeypatch
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def _disable_rate_limiter() -> Any:
    """Disable the global rate limiter for every agent-chat integration test."""
    original = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original


@pytest.fixture
def patched_memory_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic embeddings for the memory repository using the configured dimension."""
    monkeypatch.setattr(
        "app.services.memory.repository.embed_texts",
        lambda _texts: [[0.1] * _EMBEDDING_DIM for _ in _texts],
    )


async def _make_research_chat_pair(
    db_session: AsyncSession,
    workspace: Workspace,
    user: User,
    vertical_client: VerticalClient,
    *,
    title: str,
    agent_id: str = AGENT_ID,
    source: str = "agent_chat_public",
) -> tuple[ResearchThread, NewChatThread]:
    """Create a ResearchThread + a linked NewChatThread for memory tests."""
    research_thread = ResearchThread(
        workspace_id=workspace.id,
        client_id=vertical_client.client_id,
        title=title,
        created_by_id=user.id,
    )
    db_session.add(research_thread)
    await db_session.flush()

    chat_thread = NewChatThread(
        workspace_id=workspace.id,
        client_id=vertical_client.client_id,
        agent_id=agent_id,
        title=title,
        created_by_id=user.id,
        source=source,
        research_thread_id=research_thread.id,
    )
    db_session.add(chat_thread)
    await db_session.flush()
    return research_thread, chat_thread


def _fake_extraction_llm(content: str) -> Any:
    """Return an AsyncMock LLM that returns the given extraction JSON."""
    fake_llm = AsyncMock()
    fake_llm.ainvoke.return_value = type(
        "FakeMsg",
        (),
        {"content": content},
    )()
    return fake_llm
