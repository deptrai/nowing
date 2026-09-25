"""Unit tests for chat comments and mentions routes."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.db import get_async_session
from app.routes.chat_comments_routes import router as chat_comments_router
from app.schemas.chat_comments import (
    AuthorResponse,
    CommentBatchResponse,
    CommentListResponse,
    CommentReplyResponse,
    CommentResponse,
    MentionListResponse,
)
from app.users import require_session_context

pytestmark = pytest.mark.unit


class _FakeSession:
    async def execute(self, _stmt):
        raise AssertionError("chat comment routes delegate to the service layer")


def _fake_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


def _author() -> AuthorResponse:
    return AuthorResponse(id=uuid4(), display_name="QA", email="qa@nowing.net")


def _reply(**overrides) -> CommentReplyResponse:
    now = datetime.now(UTC)
    data = {
        "id": 5,
        "content": "reply",
        "content_rendered": "<p>reply</p>",
        "author": _author(),
        "created_at": now,
        "updated_at": now,
        "is_edited": False,
    }
    data.update(overrides)
    return CommentReplyResponse(**data)


def _comment(**overrides) -> CommentResponse:
    now = datetime.now(UTC)
    data = {
        "id": 3,
        "message_id": 42,
        "content": "looks good",
        "content_rendered": "<p>looks good</p>",
        "author": _author(),
        "created_at": now,
        "updated_at": now,
        "is_edited": False,
        "reply_count": 0,
        "replies": [],
    }
    data.update(overrides)
    return CommentResponse(**data)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(chat_comments_router)
    test_app.dependency_overrides[require_session_context] = _fake_auth
    test_app.dependency_overrides[get_async_session] = lambda: _FakeSession()
    return test_app


def test_batch_list_comments(app: FastAPI):
    payload = CommentBatchResponse(
        comments_by_message={"42": CommentListResponse(comments=[_comment()], total_count=1)}
    )

    with patch(
        "app.routes.chat_comments_routes.get_comments_for_messages_batch",
        AsyncMock(return_value=payload),
    ) as mock:
        client = TestClient(app)
        res = client.post("/messages/comments/batch", json={"message_ids": [42]})

        assert res.status_code == 200
        data = res.json()
        assert data["comments_by_message"]["42"]["total_count"] == 1
        mock.assert_awaited_once()
        assert mock.call_args.args[1] == [42]


def test_batch_list_comments_rejects_empty_ids(app: FastAPI):
    client = TestClient(app)
    res = client.post("/messages/comments/batch", json={"message_ids": []})

    assert res.status_code == 422


def test_list_comments(app: FastAPI):
    payload = CommentListResponse(comments=[_comment()], total_count=1)

    with patch(
        "app.routes.chat_comments_routes.get_comments_for_message",
        AsyncMock(return_value=payload),
    ) as mock:
        client = TestClient(app)
        res = client.get("/messages/42/comments")

        assert res.status_code == 200
        data = res.json()
        assert data["total_count"] == 1
        assert data["comments"][0]["message_id"] == 42
        assert mock.call_args.args[1] == 42


def test_add_comment(app: FastAPI):
    with patch(
        "app.routes.chat_comments_routes.create_comment",
        AsyncMock(return_value=_comment()),
    ) as mock:
        client = TestClient(app)
        res = client.post("/messages/42/comments", json={"content": "looks good"})

        assert res.status_code == 200
        assert res.json()["content"] == "looks good"
        assert mock.call_args.args[1] == 42
        assert mock.call_args.args[2] == "looks good"


def test_add_comment_blank_content_returns_422(app: FastAPI):
    client = TestClient(app)
    res = client.post("/messages/42/comments", json={"content": ""})

    assert res.status_code == 422


def test_add_reply(app: FastAPI):
    with patch(
        "app.routes.chat_comments_routes.create_reply",
        AsyncMock(return_value=_reply()),
    ) as mock:
        client = TestClient(app)
        res = client.post("/comments/3/replies", json={"content": "reply"})

        assert res.status_code == 200
        assert res.json()["content"] == "reply"
        assert mock.call_args.args[1] == 3


def test_edit_comment(app: FastAPI):
    with patch(
        "app.routes.chat_comments_routes.update_comment",
        AsyncMock(return_value=_reply(content="edited", is_edited=True)),
    ) as mock:
        client = TestClient(app)
        res = client.put("/comments/3", json={"content": "edited"})

        assert res.status_code == 200
        assert res.json()["is_edited"] is True
        assert mock.call_args.args[1] == 3
        assert mock.call_args.args[2] == "edited"


def test_remove_comment(app: FastAPI):
    with patch(
        "app.routes.chat_comments_routes.delete_comment",
        AsyncMock(return_value={"deleted": True}),
    ) as mock:
        client = TestClient(app)
        res = client.delete("/comments/3")

        assert res.status_code == 200
        assert mock.call_args.args[1] == 3


def test_list_mentions(app: FastAPI):
    with patch(
        "app.routes.chat_comments_routes.get_user_mentions",
        AsyncMock(return_value=MentionListResponse(mentions=[], total_count=0)),
    ) as mock:
        client = TestClient(app)
        res = client.get("/mentions?workspace_id=10")

        assert res.status_code == 200
        assert res.json() == {"mentions": [], "total_count": 0}
        assert mock.call_args.args[2] == 10
