"""Red-phase unit tests for Story 18.2 in the public agent-chat routes.

These tests follow the same dependency-override pattern as
``test_agent_chat_routes.py`` but focus on the 18.2-specific behaviors:

* ``POST /workspaces/{id}/agent-chat/threads`` persists ``client_id`` and
  ``agent_id`` on the ``NewChatThread`` row.
* ``POST /workspaces/{id}/agent-chat/threads/{id}/messages`` forwards
  ``platform_metadata`` (and the client/agent context) to ``stream_new_chat``.

They will fail until ``app/routes/agent_chat_routes.py`` and the underlying
schema/orchestrator changes land.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import NewChatThread, ResearchThread, get_async_session

pytestmark = pytest.mark.unit


class _FakeScalarResult:
    def __init__(self, first: Any, all_rows: list[Any] | None) -> None:
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
    """Minimal ``AsyncSession`` stand-in for the public agent-chat routes."""

    def __init__(self, *, first: Any = None, all_rows: list[Any] | None = None) -> None:
        self._first = first
        self._all = all_rows or []
        self.added: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._first, self._all)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True
        research = next((o for o in self.added if isinstance(o, ResearchThread)), None)
        chat = next((o for o in self.added if isinstance(o, NewChatThread)), None)
        if research and research.id is None:
            research.id = 1001
        if chat and chat.id is None:
            chat.id = 2001
        if research and chat and chat.research_thread_id is None:
            chat.research_thread_id = research.id

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            if isinstance(obj, ResearchThread):
                obj.id = 1001
            elif isinstance(obj, NewChatThread):
                obj.id = 2001

    async def close(self) -> None:
        self.closed = True

    @asynccontextmanager
    async def begin_nested(self) -> AsyncGenerator[_FakeSession, None]:
        yield self


def _make_auth(
    workspace_id: int = 42,
    client_id: str = "bdsai.vn",
    agent_id: str = "bdsai-listing-assistant",
    scopes: list[str] | None = None,
) -> AuthContext:
    """Build a fake PAT auth context for dependency overrides."""
    user = SimpleNamespace(
        id=uuid.UUID("12345678-1234-5678-1234-123456789abc"),
        is_active=True,
    )
    pat = SimpleNamespace(
        id=1,
        user_id=user.id,
        workspace_id=workspace_id,
        client_id=client_id,
        agent_id=agent_id,
        scopes=scopes or ["agent_chat:thread:create", "agent_chat:message:create"],
        token_kind="agent_chat",
        label="test-pat",
        is_valid=True,
    )
    return AuthContext.pat_auth(user, pat)


class _PatAuthDep:
    def __init__(self) -> None:
        self._mock = AsyncMock(return_value=_make_auth())

    @property
    def return_value(self):
        return self._mock.return_value

    @property
    def side_effect(self):
        return self._mock.side_effect

    @side_effect.setter
    def side_effect(self, value):
        self._mock.side_effect = value

    def assert_called(self, *args, **kwargs):
        return self._mock.assert_called(*args, **kwargs)

    async def __call__(
        self,
        request: Request,
        session: AsyncSession = Depends(get_async_session),
    ) -> Any:
        if isinstance(self._mock.side_effect, HTTPException):
            raise self._mock.side_effect
        return await self._mock(request, session)


def _assert_audit_no_body(audit_mock: AsyncMock, status: int) -> dict[str, Any]:
    assert audit_mock.called, "audit was not called"
    kwargs = audit_mock.call_args.kwargs
    assert "content" not in kwargs, "audit must not include message content"
    assert "message" not in kwargs, "audit must not include raw message body"
    assert "external_metadata" not in kwargs, "audit must not include external_metadata"
    assert kwargs.get("status") == status
    return kwargs


def _threads_url(workspace_id: int) -> str:
    return f"/api/v1/workspaces/{workspace_id}/agent-chat/threads"


def _messages_url(workspace_id: int, thread_id: int) -> str:
    return f"/api/v1/workspaces/{workspace_id}/agent-chat/threads/{thread_id}/messages"


@pytest.fixture(scope="session")
def acr():
    import app.routes.agent_chat_routes as _acr

    return _acr


@pytest.fixture
def fake_session():
    return _FakeSession()


@pytest.fixture
def pat_auth():
    return _PatAuthDep()


@pytest.fixture
def client(acr, fake_session, pat_auth, monkeypatch):
    """Build a ``TestClient`` around the agent-chat router with 18.2 seams mocked."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    prefix = (
        ""
        if any(getattr(r, "path", "").startswith("/api/v1") for r in acr.router.routes)
        else "/api/v1"
    )
    app.include_router(acr.router, prefix=prefix)

    app.dependency_overrides[acr.get_async_session] = lambda: fake_session
    app.dependency_overrides[acr.require_agent_chat_pat] = pat_auth

    async def _default_stream(*_args, **_kwargs):
        yield b'data: {"type":"text","content":"ok"}\n\n'

    monkeypatch.setattr(acr, "AGENT_CHAT_PUBLIC_ENABLED", True)
    monkeypatch.setattr(acr, "set_request_tenant_context", AsyncMock())
    monkeypatch.setattr(acr, "audit", AsyncMock())
    monkeypatch.setattr(acr, "stream_new_chat", _default_stream)

    return TestClient(app, raise_server_exceptions=False)


class TestCreateThread182:
    def test_persists_client_id_and_agent_id(self, acr, client, fake_session, pat_auth):
        """AC-1/AC-2: public thread creation stores client_id and agent_id."""
        resp = client.post(
            _threads_url(42),
            json={
                "agent_id": "bdsai-listing-assistant",
                "client_id": "bdsai.vn",
                "platform_metadata": {"source": "api"},
            },
        )
        assert resp.status_code in (200, 201), resp.text

        pat_auth.assert_called()
        assert fake_session.committed

        chat = next(
            (o for o in fake_session.added if isinstance(o, NewChatThread)), None
        )
        assert chat is not None, "NewChatThread was not added to the session"
        assert getattr(chat, "client_id", None) == "bdsai.vn"
        assert getattr(chat, "agent_id", None) == "bdsai-listing-assistant"

        _assert_audit_no_body(acr.audit, resp.status_code)

    def test_thread_platform_metadata_is_preserved_for_first_turn(
        self, acr, client, fake_session, pat_auth, monkeypatch
    ):
        """AC-3: thread creation accepts platform_metadata and threads it through
        to the first user turn context (the route may either store it on the
        thread or pass it to the first stream call)."""
        platform_metadata = {"source": "api", "listing_id": 42}

        resp = client.post(
            _threads_url(42),
            json={
                "agent_id": "bdsai-listing-assistant",
                "client_id": "bdsai.vn",
                "platform_metadata": platform_metadata,
            },
        )
        assert resp.status_code in (200, 201), resp.text

        # The thread row should retain enough context to forward platform_metadata
        # to the chat turn.  18.2 may store it on NewChatThread or pass it along
        # when the first message is sent.
        chat = next(
            (o for o in fake_session.added if isinstance(o, NewChatThread)), None
        )
        assert chat is not None
        assert getattr(chat, "platform_metadata", None) == platform_metadata or str(
            platform_metadata
        ) in str(chat.__dict__)


class TestSendMessage182:
    def test_forwards_client_id_agent_id_and_platform_metadata(
        self, acr, client, fake_session, pat_auth, monkeypatch
    ):
        """AC-1/AC-2/AC-3: send message passes agent/client context and
        platform_metadata to the streaming orchestrator."""
        fake_session._first = SimpleNamespace(
            id=123,
            workspace_id=42,
            client_id="bdsai.vn",
            research_thread_id=1001,
            title="Test thread",
        )

        platform_metadata = {"source": "api", "listing_id": 42}
        calls: list[tuple[tuple, dict]] = []

        async def _record_stream(*args, **kwargs):
            calls.append((args, kwargs))
            yield b'data: {"type":"text","content":"hello"}\n\n'

        monkeypatch.setattr(acr, "stream_new_chat", _record_stream)

        resp = client.post(
            _messages_url(42, 123),
            json={
                "content": "Hello",
                "external_metadata": {"foo": "bar"},
                "platform_metadata": platform_metadata,
            },
        )
        assert resp.status_code == 200, resp.text
        assert "text/event-stream" in resp.headers.get("content-type", "")
        assert calls, "stream_new_chat was not invoked"

        kwargs = calls[0][1]
        assert kwargs.get("client_id") == "bdsai.vn"
        assert kwargs.get("agent_id") == "bdsai-listing-assistant"
        assert kwargs.get("platform_metadata") == platform_metadata

    def test_message_without_platform_metadata_defaults_to_none(
        self, acr, client, fake_session, pat_auth, monkeypatch
    ):
        """AC-4: legacy public messages without platform_metadata default to None."""
        fake_session._first = SimpleNamespace(
            id=123,
            workspace_id=42,
            client_id="bdsai.vn",
            research_thread_id=1001,
            title="Test thread",
        )

        calls: list[tuple[tuple, dict]] = []

        async def _record_stream(*args, **kwargs):
            calls.append((args, kwargs))
            yield b'data: {"type":"text","content":"hello"}\n\n'

        monkeypatch.setattr(acr, "stream_new_chat", _record_stream)

        resp = client.post(
            _messages_url(42, 123),
            json={"content": "Hello"},
        )
        assert resp.status_code == 200, resp.text
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
        assert kwargs.get("platform_metadata") is None

    def test_rejects_message_to_thread_with_different_client_id(
        self, acr, client, fake_session
    ):
        """AC-2/AC-10: a client_id on the turn must match the thread's client_id."""
        fake_session._first = SimpleNamespace(
            id=123,
            workspace_id=42,
            client_id="other-client.vn",
            research_thread_id=1001,
            title="Test thread",
        )

        resp = client.post(
            _messages_url(42, 123),
            json={"content": "Hello"},
        )
        assert resp.status_code == 404, resp.text
        acr.audit.assert_called()
