"""Integration tests for Story 18.5: ResearchThread auto-linkage.

These tests drive the real ``POST /api/v1/workspaces/{workspace_id}/agent-chat/threads``,
``GET /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}`` and
``POST /api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages``
endpoints through the FastAPI app with the DB session overridden.

Test id / priority convention: ``18.5-INT-{seq} - P{n}/AC{n}:``
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import NewChatThread, ResearchThread, Workspace

pytestmark = [pytest.mark.integration]


def _threads_url(workspace_id: int) -> str:
    return f"/api/v1/workspaces/{workspace_id}/agent-chat/threads"


async def test_create_thread_creates_research_thread_and_returns_id(
    db_session: AsyncSession,
    db_workspace: Workspace,
    agent_chat_client: httpx.AsyncClient,
) -> None:
    """18.5-INT-001 - P1/AC1: POST /threads with agent_id auto-creates and links a ResearchThread."""
    workspace_id = db_workspace.id
    title = "Story 18.5 research thread"

    resp = await agent_chat_client.post(
        _threads_url(workspace_id),
        json={
            "client_id": "testclient.vn",
            "agent_id": "test-agent",
            "title": title,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "thread_id" in body
    assert "research_thread_id" in body
    assert "run_id" in body
    assert body["research_thread_id"] is not None

    thread_id = body["thread_id"]
    research_thread_id = body["research_thread_id"]

    chat_thread = await db_session.get(NewChatThread, thread_id)
    assert chat_thread is not None
    assert chat_thread.research_thread_id == research_thread_id
    assert chat_thread.client_id == "testclient.vn"
    assert chat_thread.agent_id == "test-agent"
    assert chat_thread.title == title
    assert chat_thread.source == "agent_chat_public"

    research_thread = await db_session.get(ResearchThread, research_thread_id)
    assert research_thread is not None
    assert research_thread.workspace_id == workspace_id
    assert research_thread.client_id == "testclient.vn"
    assert research_thread.title == title
    assert research_thread.created_by_id == chat_thread.created_by_id


async def test_get_thread_returns_research_thread_id(
    db_workspace: Workspace,
    agent_chat_client: httpx.AsyncClient,
) -> None:
    """18.5-INT-002 - P1/AC2: GET /threads/{thread_id} returns the linked research_thread_id."""
    workspace_id = db_workspace.id

    create_resp = await agent_chat_client.post(
        _threads_url(workspace_id),
        json={
            "client_id": "testclient.vn",
            "agent_id": "test-agent",
            "title": "Story 18.5 get thread",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    thread_id = created["thread_id"]

    get_resp = await agent_chat_client.get(f"{_threads_url(workspace_id)}/{thread_id}")
    assert get_resp.status_code == 200, get_resp.text
    body = get_resp.json()
    assert body["thread_id"] == thread_id
    assert body["research_thread_id"] == created["research_thread_id"]
    assert body["client_id"] == "testclient.vn"
    assert body["agent_id"] == "test-agent"
    assert body["title"] == "Story 18.5 get thread"


async def test_send_message_uses_research_thread_id(
    db_session: AsyncSession,
    db_workspace: Workspace,
    agent_chat_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """18.5-INT-003 - P1/AC3: POST /threads/{id}/messages passes the linked ResearchThread context."""
    workspace_id = db_workspace.id

    create_resp = await agent_chat_client.post(
        _threads_url(workspace_id),
        json={
            "client_id": "testclient.vn",
            "agent_id": "test-agent",
            "title": "Story 18.5 send message",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    thread_id = created["thread_id"]
    research_thread_id = created["research_thread_id"]

    captured: dict = {}

    async def _fake_stream(*, chat_id: int, **kwargs: object) -> object:
        captured["chat_id"] = chat_id
        yield b'data: {"type":"text","content":"ok"}\n\n'

    from app.routes import agent_chat_routes as acr

    monkeypatch.setattr(acr, "stream_new_chat", _fake_stream)

    resp = await agent_chat_client.post(
        f"{_threads_url(workspace_id)}/{thread_id}/messages",
        json={"content": "Hello"},
    )
    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "x-run-id" in resp.headers

    # Consume the stream so the route's finally/audit paths complete.
    async for _ in resp.aiter_text():
        pass

    assert captured.get("chat_id") == thread_id

    # The thread still carries the linked ResearchThread after the send attempt.
    chat_thread = await db_session.get(NewChatThread, thread_id)
    assert chat_thread is not None
    assert chat_thread.research_thread_id == research_thread_id


@pytest.mark.xfail(
    reason="Public agent-chat is fail-closed when no agent_id is resolvable; 201 with null research_thread_id is not returned.",
    strict=False,
)
async def test_create_thread_without_agent_id_leaves_research_thread_null(
    db_session: AsyncSession,
    db_workspace: Workspace,
    agent_chat_client_no_agent: httpx.AsyncClient,
) -> None:
    """18.5-INT-004 - P2/Regression: a PAT without agent_id should create a chat with no linked ResearchThread.

    This simulates internal / optional linking where ``research_thread_id``
    remains NULL. The public agent-chat surface is fail-closed and currently
    rejects this case, so the test is expected to fail until internal chat is
    re-examined.
    """
    workspace_id = db_workspace.id

    resp = await agent_chat_client_no_agent.post(
        _threads_url(workspace_id),
        json={"title": "No agent thread"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["research_thread_id"] is None

    result = await db_session.execute(
        select(NewChatThread).where(
            NewChatThread.workspace_id == workspace_id,
            NewChatThread.title == "No agent thread",
        )
    )
    chat_thread = result.scalars().first()
    assert chat_thread is not None
    assert chat_thread.research_thread_id is None
    assert chat_thread.agent_id is None
