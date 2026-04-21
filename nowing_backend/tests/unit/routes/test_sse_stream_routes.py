"""
Unit tests for SSE Chat Stream endpoint — Story 3.2 (P0/P1)

Covers:
  POST /api/v1/new_chat — SSE streaming endpoint
    - 401 unauthenticated
    - 404 thread not found
    - 403 no CHATS_CREATE permission
    - 403 pro-model gating (cloud mode)
    - 402 token quota exceeded
    - 200 returns StreamingResponse with correct headers

All tests are unit-level: no real DB, no real LLM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.db import ChatVisibility, User, get_async_session
from app.users import current_active_user

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    user.display_name = "Test User"
    user.subscription_status = None
    return user


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_thread(mock_user):
    t = MagicMock()
    t.id = 42
    t.title = "Test Thread"
    t.archived = False
    t.search_space_id = 1
    t.visibility = ChatVisibility.PRIVATE
    t.created_by_id = mock_user.id
    t.needs_history_bootstrap = False
    t.created_at = datetime.now(UTC)
    t.updated_at = datetime.now(UTC)
    return t


@pytest.fixture
def mock_search_space():
    ss = MagicMock()
    ss.id = 1
    ss.agent_llm_id = -1
    return ss


@pytest.fixture
def client(mock_user, mock_session) -> TestClient:
    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture
def unauthenticated_client(mock_session) -> TestClient:
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(get_async_session, None)


_VALID_BODY = {
    "chat_id": 42,
    "search_space_id": 1,
    "user_query": "What is nowing?",
    "mentioned_document_ids": [],
    "mentioned_nowing_doc_ids": [],
    "disabled_tools": [],
}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestNewChatSSEAuth:
    """[P0] Auth requirements for SSE stream endpoint."""

    def test_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No access token → 401."""
        resp = unauthenticated_client.post("/api/v1/new_chat", json=_VALID_BODY)
        assert resp.status_code == 401

    def test_missing_body_returns_422(self, client):
        """[P1] Missing required fields → 422."""
        resp = client.post("/api/v1/new_chat", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 404 — thread not found
# ---------------------------------------------------------------------------


class TestNewChatSSEThreadNotFound:
    """[P1] Thread not found → 404."""

    def test_thread_not_found_returns_404(self, client):
        """[P1] DB returns no thread → 404."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/v1/new_chat",
            json={**_VALID_BODY, "chat_id": 9999},
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 403 — permission denied
# ---------------------------------------------------------------------------


class TestNewChatSSEPermission:
    """[P1] Permission checks on SSE endpoint."""

    def test_no_chats_create_permission_returns_403(self, client, mock_thread):
        """[P1] User lacks CHATS_CREATE → 403."""
        from fastapi import HTTPException

        mock_session = app.dependency_overrides[get_async_session]()
        mock_thread_result = MagicMock()
        mock_thread_result.scalars.return_value.first.return_value = mock_thread
        mock_session.execute = AsyncMock(return_value=mock_thread_result)

        with patch(
            "app.routes.new_chat_routes.check_permission",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=403, detail="Permission denied"),
        ):
            resp = client.post("/api/v1/new_chat", json=_VALID_BODY)

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 402 — token quota exceeded
# ---------------------------------------------------------------------------


class TestNewChatSSEQuota:
    """[P1/Story 3.5] Token quota enforcement → 402."""

    def test_token_quota_exceeded_returns_402(self, client, mock_thread, mock_search_space):
        """[P1] Token quota exceeded → 402 with upgrade_url in detail."""
        from app.services.token_quota_service import TokenQuotaExceededError

        mock_session = app.dependency_overrides[get_async_session]()

        # thread query → found
        mock_thread_result = MagicMock()
        mock_thread_result.scalars.return_value.first.return_value = mock_thread

        # search_space query → found
        mock_ss_result = MagicMock()
        mock_ss_result.scalars.return_value.first.return_value = mock_search_space

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_ss_result]
        )
        mock_session.commit = AsyncMock()

        quota_error = TokenQuotaExceededError(
            "Quota exceeded", tokens_used=100000, monthly_token_limit=50000
        )

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
            ),
            patch(
                "app.config.config.is_cloud",
                return_value=True,
            ),
            patch(
                "app.routes.new_chat_routes.TokenQuotaService",
            ) as MockQuotaService,
        ):
            mock_svc = AsyncMock()
            mock_svc.check_token_quota = AsyncMock(side_effect=quota_error)
            MockQuotaService.return_value = mock_svc

            resp = client.post("/api/v1/new_chat", json=_VALID_BODY)

        assert resp.status_code == 402
        body = resp.json()
        assert body["detail"]["error"] == "token_quota_exceeded"
        assert "upgrade_url" in body["detail"]


# ---------------------------------------------------------------------------
# 200 — SSE stream response
# ---------------------------------------------------------------------------


class TestNewChatSSESuccess:
    """[P1] Successful SSE stream returns correct response."""

    def test_valid_request_returns_streaming_response(
        self, client, mock_thread, mock_search_space
    ):
        """[P1] Valid auth + thread → streaming response with SSE headers."""
        mock_session = app.dependency_overrides[get_async_session]()

        mock_thread_result = MagicMock()
        mock_thread_result.scalars.return_value.first.return_value = mock_thread

        mock_ss_result = MagicMock()
        mock_ss_result.scalars.return_value.first.return_value = mock_search_space

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_ss_result]
        )
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()

        async def fake_stream(*args, **kwargs):
            yield b"data: {}\n\n"

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
            ),
            patch(
                "app.config.config.is_cloud",
                return_value=False,
            ),
            patch(
                "app.routes.new_chat_routes.stream_new_chat",
                return_value=fake_stream(),
            ),
        ):
            resp = client.post("/api/v1/new_chat", json=_VALID_BODY)

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_search_space_not_found_returns_404(self, client, mock_thread):
        """[P1] Thread found but search space missing → 404."""
        mock_session = app.dependency_overrides[get_async_session]()

        mock_thread_result = MagicMock()
        mock_thread_result.scalars.return_value.first.return_value = mock_thread

        mock_ss_result = MagicMock()
        mock_ss_result.scalars.return_value.first.return_value = None  # not found

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_ss_result]
        )
        mock_session.commit = AsyncMock()

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
            ),
            patch(
                "app.config.config.is_cloud",
                return_value=False,
            ),
        ):
            resp = client.post("/api/v1/new_chat", json=_VALID_BODY)

        assert resp.status_code == 404

    def test_cloud_mode_custom_model_forbidden_returns_403(
        self, client, mock_thread, mock_search_space
    ):
        """[P1] Cloud mode + positive model_id (custom) → 403."""
        mock_session = app.dependency_overrides[get_async_session]()

        mock_thread_result = MagicMock()
        mock_thread_result.scalars.return_value.first.return_value = mock_thread

        mock_ss_result = MagicMock()
        mock_ss_result.scalars.return_value.first.return_value = mock_search_space

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_ss_result]
        )
        mock_session.commit = AsyncMock()

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
            ),
            patch(
                "app.config.config.is_cloud",
                return_value=True,
            ),
        ):
            resp = client.post(
                "/api/v1/new_chat",
                json={**_VALID_BODY, "model_id": 5},  # positive → custom, forbidden
            )

        assert resp.status_code == 403
