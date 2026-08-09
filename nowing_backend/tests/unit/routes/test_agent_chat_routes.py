"""Red-phase unit tests for Story 18.1 "Public Agent-Chat Endpoints".

These tests exercise the not-yet-implemented `app.routes.agent_chat_routes`
FastAPI router by mounting it in a minimal `FastAPI` app and driving it with
`TestClient`.  All real DB, auth, tenant-context, streaming, and audit seams are
monkeypatched or overridden:

* `get_async_session` dependency -> `_FakeSession`
* `require_agent_chat_pat` dependency -> `AsyncMock`/side-effect injection
* `AGENT_CHAT_PUBLIC_ENABLED` -> bool feature flag
* `set_request_tenant_context` -> `AsyncMock`
* `stream_new_chat` -> async generator under test control
* `audit` -> `AsyncMock` inspected for PII exclusion

The tests will fail until the route module and its dependencies are implemented,
which is the intended red-phase state.
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
    """Minimal `AsyncSession` stand-in for the public agent-chat routes."""

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
        # Simulate Postgres assigning ids so the route can build a response.
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


def _assert_audit_no_body(audit_mock: AsyncMock, status: int) -> dict[str, Any]:
    """Assert that `audit` was called and that no message PII leaked."""
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
    """Resolve the route module under test."""
    try:
        import app.routes.agent_chat_routes as _acr
    except ImportError as exc:
        pytest.fail(f"Story 18.1 route module not found: {exc}")
    return _acr


@pytest.fixture
def fake_session():
    return _FakeSession()


class _PatAuthDep:
    """Callable dependency with FastAPI-friendly signature and mock helpers."""

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


@pytest.fixture
def pat_auth():
    return _PatAuthDep()


@pytest.fixture
def client(acr, fake_session, pat_auth, monkeypatch):
    """Build a `TestClient` around a minimal FastAPI app with the agent-chat router."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    # The router may already include /api/v1 or be mounted relative to it.
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
    monkeypatch.setattr(
        acr,
        "_resolve_agent_config",
        AsyncMock(
            return_value=SimpleNamespace(
                client_id="bdsai.vn",
                slug="bdsai-listing-assistant",
                system_instructions=None,
                citations_enabled=True,
                model_name=None,
                is_active=True,
            )
        ),
    )

    return TestClient(app, raise_server_exceptions=False)


def test_create_thread_returns_ids_and_run_id(acr, client, fake_session, pat_auth):
    """AC-1: create thread returns {thread_id, research_thread_id} and X-Run-Id."""
    resp = client.post(
        _threads_url(42),
        json={
            "agent_id": "bdsai-listing-assistant",
            "client_id": "bdsai.vn",
            "platform_metadata": {"source": "api"},
        },
    )
    assert resp.status_code in (200, 201), resp.text

    body = resp.json()
    assert "thread_id" in body
    assert "research_thread_id" in body
    assert body["thread_id"] == 2001
    assert body["research_thread_id"] == 1001

    assert "X-Run-Id" in resp.headers
    run_id = uuid.UUID(resp.headers["X-Run-Id"])

    pat_auth.assert_called()
    assert fake_session.committed
    acr.set_request_tenant_context.assert_called()

    audit_kwargs = _assert_audit_no_body(acr.audit, resp.status_code)
    assert audit_kwargs["workspace_id"] == 42
    assert audit_kwargs["pat_id"] == 1
    assert audit_kwargs["client_id"] == "bdsai.vn"
    assert audit_kwargs["agent_id"] == "bdsai-listing-assistant"
    assert audit_kwargs["run_id"] == run_id


def test_create_thread_missing_body_returns_422(client):
    """AC-4: missing/empty request body is rejected with 422 field errors."""
    resp = client.post(_threads_url(42))
    assert resp.status_code == 422


def test_create_thread_workspace_mismatch_returns_403(client, pat_auth):
    """AC-1/AC-10: workspace_id outside PAT scope returns 403."""
    pat_auth.side_effect = HTTPException(
        status_code=403, detail="workspace_id not in PAT scope"
    )
    resp = client.post(_threads_url(42), json={})
    assert resp.status_code == 403


def test_send_message_returns_sse_stream_with_run_id(
    acr, client, fake_session, pat_auth, monkeypatch
):
    """AC-2: send message returns a text/event-stream with X-Run-Id."""
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
        json={"content": "Hello", "external_metadata": {"foo": "bar"}},
    )
    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "X-Run-Id" in resp.headers
    assert resp.text

    assert calls, "stream_new_chat was not invoked"
    kwargs = calls[0][1]
    assert kwargs.get("chat_id") == 123
    assert kwargs.get("user_query") == "Hello"
    assert kwargs.get("client_id") == "bdsai.vn"
    assert kwargs.get("agent_id") == "bdsai-listing-assistant"
    assert kwargs.get("auth_context") == pat_auth.return_value

    acr.set_request_tenant_context.assert_called()

    audit_kwargs = _assert_audit_no_body(acr.audit, 200)
    assert audit_kwargs["run_id"] == uuid.UUID(resp.headers["X-Run-Id"])


def test_send_message_missing_content_returns_422(client):
    """AC-4: missing `content` field returns 422."""
    resp = client.post(_messages_url(42, 123), json={})
    assert resp.status_code == 422


def test_send_message_empty_content_returns_422(client):
    """AC-4: empty `content` string returns 422."""
    resp = client.post(_messages_url(42, 123), json={"content": ""})
    assert resp.status_code == 422


def test_send_message_nonexistent_thread_returns_404(acr, client, fake_session):
    """AC-2: sending a message to an unknown thread returns 404."""
    fake_session._first = None
    resp = client.post(_messages_url(42, 123), json={"content": "Hello"})
    assert resp.status_code == 404
    acr.audit.assert_called()
    _assert_audit_no_body(acr.audit, 404)


def test_send_message_thread_from_other_workspace_returns_404(
    acr, client, fake_session
):
    """AC-2/AC-10: thread row belonging to a different workspace is not found (404)."""
    fake_session._first = SimpleNamespace(
        id=123,
        workspace_id=999,
        client_id="bdsai.vn",
        research_thread_id=1001,
    )
    resp = client.post(_messages_url(42, 123), json={"content": "Hello"})
    assert resp.status_code == 404
    acr.audit.assert_called()
    _assert_audit_no_body(acr.audit, 404)


def test_create_thread_feature_flag_disabled_returns_503(acr, client, monkeypatch):
    """Cross-AC: AGENT_CHAT_PUBLIC_ENABLED=false returns 503."""
    monkeypatch.setattr(acr, "AGENT_CHAT_PUBLIC_ENABLED", False)
    resp = client.post(
        _threads_url(42),
        json={
            "agent_id": "bdsai-listing-assistant",
            "client_id": "bdsai.vn",
        },
    )
    assert resp.status_code == 503


def test_create_thread_rate_limit_returns_429_with_retry_after(client, pat_auth):
    """AC-9: rate-limited request returns 429 with Retry-After."""
    pat_auth.side_effect = HTTPException(
        status_code=429,
        detail="Rate limit exceeded",
        headers={"Retry-After": "30"},
    )
    resp = client.post(_threads_url(42), json={})
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "30"


def test_send_message_chat_timeout_returns_503_or_partial(
    acr, client, fake_session, monkeypatch
):
    """AC-7: chat service TimeoutError yields 503 Retry-After or a partial frame."""
    fake_session._first = SimpleNamespace(
        id=123,
        workspace_id=42,
        client_id="bdsai.vn",
        research_thread_id=1001,
    )

    async def _timeout_stream(*_args, **_kwargs):
        # Async generator that raises before the first yield.
        raise TimeoutError("chat service timed out")
        yield

    monkeypatch.setattr(acr, "stream_new_chat", _timeout_stream)

    resp = client.post(
        _messages_url(42, 123),
        json={"content": "Hello"},
    )
    if resp.status_code == 503:
        assert "Retry-After" in resp.headers or "degraded" in resp.text.lower(), (
            "503 must carry Retry-After or degraded payload"
        )
    elif resp.status_code == 200:
        assert "degraded" in resp.text.lower(), (
            "partial stream must expose degraded=true"
        )
    else:
        pytest.fail(f"Expected 503 or partial 200 on timeout, got {resp.status_code}")
