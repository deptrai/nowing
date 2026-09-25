"""Unit tests for the models catalogue route (`GET /models`)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.routes.model_list_routes import router as model_list_router
from app.users import require_session_context

pytestmark = pytest.mark.unit


def _fake_auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(model_list_router)
    test_app.dependency_overrides[require_session_context] = _fake_auth
    return test_app


def test_list_models_returns_catalogue(app: FastAPI):
    models = [
        {
            "value": "openai/gpt-4o",
            "label": "GPT-4o",
            "provider": "OpenAI",
            "context_window": "128k",
        },
        {
            "value": "anthropic/claude-sonnet-4",
            "label": "Claude Sonnet 4",
            "provider": "Anthropic",
            "context_window": None,
        },
    ]

    with patch(
        "app.routes.model_list_routes.get_model_list",
        AsyncMock(return_value=models),
    ):
        client = TestClient(app)
        res = client.get("/models")

        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["value"] == "openai/gpt-4o"
        assert data[0]["provider"] == "OpenAI"
        assert data[1]["context_window"] is None


def test_list_models_empty_catalogue(app: FastAPI):
    with patch(
        "app.routes.model_list_routes.get_model_list",
        AsyncMock(return_value=[]),
    ):
        client = TestClient(app)
        res = client.get("/models")

        assert res.status_code == 200
        assert res.json() == []


def test_list_models_service_failure_returns_500(app: FastAPI):
    with patch(
        "app.routes.model_list_routes.get_model_list",
        AsyncMock(side_effect=RuntimeError("openrouter unreachable")),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        res = client.get("/models")

        assert res.status_code == 500
        assert "Failed to fetch model list" in res.json()["detail"]
