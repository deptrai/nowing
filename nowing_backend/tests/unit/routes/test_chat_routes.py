"""
Unit tests for Chat Thread routes — Story 3.1 (P1) + 9-UX-1b run/resume

Covers:
  POST /api/v1/threads    — create thread (201, 401, 403, 422)
  GET  /api/v1/threads    — list threads (200, 401, 403)
  GET  /api/v1/threads/{id} — get thread with messages (200, 401, 404)
  DELETE /api/v1/threads/{id} — delete thread (200, 401, 404)
  POST   /threads/{id}/runs          — start run (200, 401, 404)
  GET    /threads/{id}/runs/active    — list active runs (200, 401, 404, feature flag)
  POST   /threads/{id}/runs/{rid}/cancel — cancel run (200, 401, 403, 404)
  POST   /threads/{id}/runs/{rid}/resume — resume run (200, 401, 403, 404)
  PATCH  /threads/{id}/visibility     — update visibility (200, 401, 404)
  POST   /threads/{id}/messages       — append message (200, 400, 401, 404)

All tests are unit-level: no real DB.
External dependencies mocked via app.dependency_overrides and unittest.mock.
"""

from __future__ import annotations

import os
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
    return user


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_thread(mock_user):
    """Minimal NewChatThread ORM mock."""
    t = MagicMock()
    t.id = 42
    t.title = "Test Thread"
    t.archived = False
    t.search_space_id = 1
    t.visibility = ChatVisibility.PRIVATE
    t.created_by_id = mock_user.id
    t.created_at = datetime.now(UTC)
    t.updated_at = datetime.now(UTC)
    return t


@pytest.fixture
def client(mock_user, mock_session) -> TestClient:
    """Authenticated client with DB session overridden."""
    app.dependency_overrides[current_active_user] = lambda: mock_user
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture
def unauthenticated_client(mock_session) -> TestClient:
    """No auth override — returns 401 on protected routes."""
    app.dependency_overrides.pop(current_active_user, None)
    app.dependency_overrides[get_async_session] = lambda: mock_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.pop(get_async_session, None)


# ---------------------------------------------------------------------------
# POST /api/v1/threads — create thread
# ---------------------------------------------------------------------------


class TestCreateThread:
    """[P1] Story 3.1 — AC BE-4: POST /threads creates session, returns id."""

    def test_create_thread_returns_thread_with_id(self, client, mock_thread):
        """[P1] Valid body + auth → 200 with id, title, search_space_id."""
        with patch("app.routes.new_chat_routes.check_permission", new_callable=AsyncMock):
            # Mock session.add, commit, refresh
            client.app.dependency_overrides[get_async_session]()
            # Patch the DB operations called inside create_thread
            with patch(
                "app.routes.new_chat_routes.NewChatThread",
                return_value=mock_thread,
            ):
                mock_sess = app.dependency_overrides[get_async_session]()
                mock_sess.add = MagicMock()
                mock_sess.commit = AsyncMock()
                mock_sess.refresh = AsyncMock()

                resp = client.post(
                    "/api/v1/threads",
                    json={"search_space_id": 1, "title": "Test Thread"},
                )

        # 200 or 201 depending on fastapi default for POST
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert "id" in body

    def test_create_thread_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No access token → 401 Unauthorized."""
        resp = unauthenticated_client.post(
            "/api/v1/threads",
            json={"search_space_id": 1, "title": "Test"},
        )
        assert resp.status_code == 401

    def test_create_thread_missing_search_space_id_returns_422(self, client):
        """[P1] Missing required search_space_id → 422."""
        resp = client.post(
            "/api/v1/threads",
            json={"title": "No space"},
        )
        assert resp.status_code == 422

    def test_create_thread_no_permission_returns_403(self, client):
        """[P1] User lacks CHATS_CREATE permission → 403."""
        from fastapi import HTTPException

        with patch(
            "app.routes.new_chat_routes.check_permission",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=403, detail="Permission denied"),
        ):
            resp = client.post(
                "/api/v1/threads",
                json={"search_space_id": 99, "title": "Unauthorized"},
            )

        assert resp.status_code == 403

    def test_create_thread_empty_body_returns_422(self, client):
        """[P2] Empty body → 422."""
        resp = client.post("/api/v1/threads", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/threads — list threads
# ---------------------------------------------------------------------------


class TestListThreads:
    """[P1] Story 3.1 — list threads requires auth + search_space_id."""

    def test_list_threads_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        resp = unauthenticated_client.get("/api/v1/threads?search_space_id=1")
        assert resp.status_code == 401

    def test_list_threads_missing_search_space_id_returns_422(self, client):
        """[P1] Missing required query param → 422."""
        resp = client.get("/api/v1/threads")
        assert resp.status_code == 422

    def test_list_threads_no_permission_returns_403(self, client):
        """[P1] User lacks CHATS_READ → 403."""
        from fastapi import HTTPException

        with patch(
            "app.routes.new_chat_routes.check_permission",
            new_callable=AsyncMock,
            side_effect=HTTPException(status_code=403, detail="No access"),
        ):
            resp = client.get("/api/v1/threads?search_space_id=99")

        assert resp.status_code == 403

    def test_list_threads_authenticated_returns_200(self, client):
        """[P1] Valid auth + search_space_id → 200 with threads/archived_threads keys."""
        with patch(
            "app.routes.new_chat_routes.check_permission",
            new_callable=AsyncMock,
        ):
            # Mock the DB query results
            mock_session = app.dependency_overrides[get_async_session]()

            # search_space query
            mock_ss_result = MagicMock()
            mock_ss_result.scalar_one_or_none.return_value = MagicMock(user_id=None)

            # threads query
            mock_thread_result = MagicMock()
            mock_thread_result.scalars.return_value.all.return_value = []

            mock_session.execute = AsyncMock(
                side_effect=[mock_ss_result, mock_thread_result]
            )

            resp = client.get("/api/v1/threads?search_space_id=1")

        assert resp.status_code == 200
        body = resp.json()
        assert "threads" in body
        assert "archived_threads" in body


# ---------------------------------------------------------------------------
# GET /api/v1/threads/{thread_id} — get thread with messages
# ---------------------------------------------------------------------------


class TestGetThread:
    """[P1] Story 3.1 — get thread requires auth."""

    def test_get_thread_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        resp = unauthenticated_client.get("/api/v1/threads/42")
        assert resp.status_code == 401

    def test_get_thread_not_found_returns_404(self, client):
        """[P1] Thread doesn't exist → 404 (session.execute returns None for thread query)."""
        mock_session = app.dependency_overrides[get_async_session]()
        # First execute: thread query returns None
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_not_found)

        resp = client.get("/api/v1/threads/9999")

        assert resp.status_code == 404

    def test_get_thread_valid_returns_200(self, client, mock_thread):
        """[P1] Valid thread id + auth → 200 with messages."""
        mock_session = app.dependency_overrides[get_async_session]()

        # 1st execute: thread query → found
        mock_thread_result = MagicMock()
        mock_thread_result.scalars.return_value.first.return_value = mock_thread

        # 2nd execute: messages query → empty
        mock_msg_result = MagicMock()
        mock_msg_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[mock_thread_result, mock_msg_result]
        )

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            resp = client.get("/api/v1/threads/42")

        assert resp.status_code == 200
        body = resp.json()
        assert "messages" in body


# ---------------------------------------------------------------------------
# DELETE /api/v1/threads/{thread_id} — delete thread
# ---------------------------------------------------------------------------


class TestDeleteThread:
    """[P1] Story 3.1 — delete thread requires auth + ownership."""

    def test_delete_thread_unauthenticated_returns_401(self, unauthenticated_client):
        """[P0] No auth → 401."""
        resp = unauthenticated_client.delete("/api/v1/threads/42")
        assert resp.status_code == 401

    def test_delete_thread_not_found_returns_404(self, client):
        """[P1] Thread doesn't exist → 404."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_not_found)

        resp = client.delete("/api/v1/threads/9999")

        assert resp.status_code == 404

    def test_delete_thread_returns_200(self, client, mock_thread):
        """[P1] Valid owned thread → 200."""
        mock_session = app.dependency_overrides[get_async_session]()
        mock_thread_result = MagicMock()
        mock_thread_result.scalars.return_value.first.return_value = mock_thread
        mock_session.execute = AsyncMock(return_value=mock_thread_result)
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=mock_thread,
            ),
        ):
            resp = client.delete("/api/v1/threads/42")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# PATCH /api/v1/threads/{id}/visibility — update visibility
# ---------------------------------------------------------------------------


class TestUpdateThreadVisibility:
    """[P1] Story 9-UX-1b — PATCH visibility requires auth + ownership."""

    def test_update_visibility_unauthenticated_returns_401(
        self, unauthenticated_client
    ):
        resp = unauthenticated_client.patch(
            "/api/v1/threads/42/visibility",
            json={"visibility": "SEARCH_SPACE"},
        )
        assert resp.status_code == 401

    def test_update_visibility_not_found_returns_404(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_sess.execute = AsyncMock(return_value=mock_not_found)

        resp = client.patch(
            "/api/v1/threads/9999/visibility",
            json={"visibility": "SEARCH_SPACE"},
        )
        assert resp.status_code == 404

    def test_update_visibility_returns_200(self, client, mock_thread):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_thread
        mock_sess.execute = AsyncMock(return_value=mock_result)
        mock_sess.commit = AsyncMock()
        mock_sess.refresh = AsyncMock()

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            resp = client.patch(
                "/api/v1/threads/42/visibility",
                json={"visibility": "SEARCH_SPACE"},
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/threads/{id}/messages — append message
# ---------------------------------------------------------------------------


class TestAppendMessage:
    """[P1] Story 9-UX-1b — POST message requires auth + valid role/content."""

    def test_append_message_unauthenticated_returns_401(
        self, unauthenticated_client
    ):
        resp = unauthenticated_client.post(
            "/api/v1/threads/42/messages",
            json={"role": "user", "content": "hello"},
        )
        assert resp.status_code == 401

    def test_append_message_missing_role_returns_400(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = MagicMock()
        mock_sess.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/v1/threads/42/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 400

    def test_append_message_missing_content_returns_400(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = MagicMock()
        mock_sess.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/v1/threads/42/messages",
            json={"role": "user"},
        )
        assert resp.status_code == 400

    def test_append_message_invalid_role_returns_400(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = MagicMock()
        mock_sess.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/api/v1/threads/42/messages",
            json={"role": "alien", "content": "hello"},
        )
        assert resp.status_code == 400

    def test_append_message_thread_not_found_returns_404(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_sess.execute = AsyncMock(return_value=mock_not_found)

        resp = client.post(
            "/api/v1/threads/9999/messages",
            json={"role": "user", "content": "hello"},
        )
        assert resp.status_code == 404

    def test_append_message_returns_200(self, client, mock_thread):
        from types import SimpleNamespace
        from app.db import NewChatMessageRole

        mock_sess = app.dependency_overrides[get_async_session]()

        mock_message = SimpleNamespace(
            id=101,
            thread_id=42,
            role=NewChatMessageRole.USER,
            content="hello",
            author_id=mock_thread.created_by_id,
            author_display_name=None,
            author_avatar_url=None,
            created_at=datetime.now(UTC),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_thread
        mock_sess.execute = AsyncMock(return_value=mock_result)
        mock_sess.add = MagicMock()
        mock_sess.flush = AsyncMock()
        mock_sess.commit = AsyncMock()

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.routes.new_chat_routes.NewChatMessage",
                return_value=mock_message,
            ),
        ):
            resp = client.post(
                "/api/v1/threads/42/messages",
                json={"role": "user", "content": "hello"},
            )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/threads/{id}/runs — start run
# ---------------------------------------------------------------------------


class TestStartNewRun:
    """[P1] Story 9-UX-1b — dispatch detached agent run."""

    RUN_BODY = {
        "search_space_id": 1,
        "user_query": "analyze BTC",
    }

    def test_start_run_unauthenticated_returns_401(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            "/api/v1/threads/42/runs",
            json=self.RUN_BODY,
        )
        assert resp.status_code == 401

    def test_start_run_thread_not_found_returns_404(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_sess.execute = AsyncMock(return_value=mock_not_found)

        resp = client.post("/api/v1/threads/9999/runs", json=self.RUN_BODY)
        assert resp.status_code == 404

    def test_start_run_search_space_not_found_returns_404(self, client, mock_thread):
        mock_sess = app.dependency_overrides[get_async_session]()

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.first.return_value = None
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)
        mock_sess.commit = AsyncMock()

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.routes.new_chat_routes.config") as mock_config,
        ):
            mock_config.is_cloud.return_value = False
            resp = client.post("/api/v1/threads/42/runs", json=self.RUN_BODY)

        assert resp.status_code == 404

    def test_start_run_returns_200(self, client, mock_thread):
        mock_sess = app.dependency_overrides[get_async_session]()

        mock_search_space = MagicMock()
        mock_search_space.id = 1
        mock_search_space.agent_llm_id = None

        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()
        mock_run.thread_id = 42
        mock_run.session_id = "sess-1"
        mock_run.langgraph_thread_id = "lg-1"
        mock_run.status = "running"
        mock_run.user_query = "analyze BTC"
        mock_run.started_at = datetime.now(UTC)
        mock_run.completed_at = None
        mock_run.final_message_id = None

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.first.return_value = mock_search_space
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)
        mock_sess.commit = AsyncMock()

        with (
            patch(
                "app.routes.new_chat_routes.check_permission",
                new_callable=AsyncMock,
            ),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("app.routes.new_chat_routes.config") as mock_config,
            patch(
                "app.tasks.chat.run_manager.start_run",
                new_callable=AsyncMock,
                return_value=mock_run,
            ),
        ):
            mock_config.is_cloud.return_value = False
            resp = client.post("/api/v1/threads/42/runs", json=self.RUN_BODY)

        assert resp.status_code == 200
        body = resp.json()
        assert body["thread_id"] == 42
        assert body["status"] == "running"


# ---------------------------------------------------------------------------
# GET /api/v1/threads/{id}/runs/active — list active runs
# ---------------------------------------------------------------------------


class TestGetActiveRuns:
    """[P1] Story 9-UX-1b — list running/abandoned runs for a thread."""

    def test_get_active_runs_unauthenticated_returns_401(
        self, unauthenticated_client
    ):
        resp = unauthenticated_client.get("/api/v1/threads/42/runs/active")
        assert resp.status_code == 401

    def test_get_active_runs_thread_not_found_returns_404(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_sess.execute = AsyncMock(return_value=mock_not_found)

        with patch.dict(os.environ, {"RESUMABLE_RUNS_ENABLED": "true"}):
            resp = client.get("/api/v1/threads/9999/runs/active")

        assert resp.status_code == 404

    def test_get_active_runs_feature_flag_disabled_returns_empty(self, client):
        with patch.dict(os.environ, {"RESUMABLE_RUNS_ENABLED": "false"}):
            resp = client.get("/api/v1/threads/42/runs/active")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_active_runs_returns_200(self, client, mock_thread):
        mock_sess = app.dependency_overrides[get_async_session]()

        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()
        mock_run.thread_id = 42
        mock_run.session_id = "sess-1"
        mock_run.langgraph_thread_id = "lg-1"
        mock_run.status = "running"
        mock_run.user_query = "analyze BTC"
        mock_run.started_at = datetime.now(UTC)
        mock_run.completed_at = None
        mock_run.final_message_id = None

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.all.return_value = [mock_run]
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)

        with (
            patch.dict(os.environ, {"RESUMABLE_RUNS_ENABLED": "true"}),
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            resp = client.get("/api/v1/threads/42/runs/active")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["status"] == "running"


# ---------------------------------------------------------------------------
# POST /api/v1/threads/{id}/runs/{rid}/cancel — cancel run
# ---------------------------------------------------------------------------


class TestCancelRun:
    """[P1] Story 9-UX-1b — cancel a running agent run."""

    RUN_ID = "00000000-0000-4000-8000-000000000001"

    def test_cancel_run_unauthenticated_returns_401(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f"/api/v1/threads/42/runs/{self.RUN_ID}/cancel"
        )
        assert resp.status_code == 401

    def test_cancel_run_thread_not_found_returns_404(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_sess.execute = AsyncMock(return_value=mock_not_found)

        resp = client.post(f"/api/v1/threads/9999/runs/{self.RUN_ID}/cancel")
        assert resp.status_code == 404

    def test_cancel_run_not_found_returns_404(self, client, mock_thread):
        mock_sess = app.dependency_overrides[get_async_session]()

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.first.return_value = None
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)

        with patch(
            "app.routes.new_chat_routes.check_thread_access",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = client.post(
                f"/api/v1/threads/42/runs/{self.RUN_ID}/cancel"
            )

        assert resp.status_code == 404

    def test_cancel_run_not_owner_returns_403(self, client, mock_thread, mock_user):
        mock_sess = app.dependency_overrides[get_async_session]()

        mock_run = MagicMock()
        mock_run.id = uuid.UUID(self.RUN_ID)
        mock_run.thread_id = 42
        mock_run.created_by_id = uuid.uuid4()

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.first.return_value = mock_run
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)

        with patch(
            "app.routes.new_chat_routes.check_thread_access",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = client.post(
                f"/api/v1/threads/42/runs/{self.RUN_ID}/cancel"
            )

        assert resp.status_code == 403

    def test_cancel_run_returns_200(self, client, mock_thread, mock_user):
        mock_sess = app.dependency_overrides[get_async_session]()

        mock_run = MagicMock()
        mock_run.id = uuid.UUID(self.RUN_ID)
        mock_run.thread_id = 42
        mock_run.created_by_id = mock_user.id

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.first.return_value = mock_run
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)

        with (
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.tasks.chat.run_manager.cancel_run",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            resp = client.post(
                f"/api/v1/threads/42/runs/{self.RUN_ID}/cancel"
            )

        assert resp.status_code == 200
        assert resp.json()["cancelled"] is True


# ---------------------------------------------------------------------------
# POST /api/v1/threads/{id}/runs/{rid}/resume — resume run
# ---------------------------------------------------------------------------


class TestResumeRun:
    """[P1] Story 9-UX-1b — resume an abandoned agent run."""

    RUN_ID = "00000000-0000-4000-8000-000000000002"

    def test_resume_run_unauthenticated_returns_401(self, unauthenticated_client):
        resp = unauthenticated_client.post(
            f"/api/v1/threads/42/runs/{self.RUN_ID}/resume"
        )
        assert resp.status_code == 401

    def test_resume_run_thread_not_found_returns_404(self, client):
        mock_sess = app.dependency_overrides[get_async_session]()
        mock_not_found = MagicMock()
        mock_not_found.scalars.return_value.first.return_value = None
        mock_sess.execute = AsyncMock(return_value=mock_not_found)

        resp = client.post(f"/api/v1/threads/9999/runs/{self.RUN_ID}/resume")
        assert resp.status_code == 404

    def test_resume_run_not_found_returns_404(self, client, mock_thread):
        mock_sess = app.dependency_overrides[get_async_session]()

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.first.return_value = None
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)

        with patch(
            "app.routes.new_chat_routes.check_thread_access",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = client.post(
                f"/api/v1/threads/42/runs/{self.RUN_ID}/resume"
            )

        assert resp.status_code == 404

    def test_resume_run_not_owner_returns_403(self, client, mock_thread, mock_user):
        mock_sess = app.dependency_overrides[get_async_session]()

        mock_run = MagicMock()
        mock_run.id = uuid.UUID(self.RUN_ID)
        mock_run.thread_id = 42
        mock_run.created_by_id = uuid.uuid4()

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            else:
                result.scalars.return_value.first.return_value = mock_run
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)

        with patch(
            "app.routes.new_chat_routes.check_thread_access",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = client.post(
                f"/api/v1/threads/42/runs/{self.RUN_ID}/resume"
            )

        assert resp.status_code == 403

    def test_resume_run_returns_200(self, client, mock_thread, mock_user):
        mock_sess = app.dependency_overrides[get_async_session]()

        mock_run = MagicMock()
        mock_run.id = uuid.UUID(self.RUN_ID)
        mock_run.thread_id = 42
        mock_run.created_by_id = mock_user.id

        mock_search_space = MagicMock()
        mock_search_space.id = 1

        resumed_run = MagicMock()
        resumed_run.id = uuid.uuid4()
        resumed_run.thread_id = 42
        resumed_run.session_id = "sess-resumed"
        resumed_run.langgraph_thread_id = "lg-resumed"
        resumed_run.status = "running"
        resumed_run.user_query = "analyze BTC"
        resumed_run.started_at = datetime.now(UTC)
        resumed_run.completed_at = None
        resumed_run.final_message_id = None

        call_count = 0

        async def _execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalars.return_value.first.return_value = mock_thread
            elif call_count == 2:
                result.scalars.return_value.first.return_value = mock_run
            else:
                result.scalars.return_value.first.return_value = mock_search_space
            return result

        mock_sess.execute = AsyncMock(side_effect=_execute_side_effect)

        with (
            patch(
                "app.routes.new_chat_routes.check_thread_access",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.tasks.chat.run_manager.resume_run",
                new_callable=AsyncMock,
                return_value=resumed_run,
            ),
        ):
            resp = client.post(
                f"/api/v1/threads/42/runs/{self.RUN_ID}/resume"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["session_id"] == "sess-resumed"
