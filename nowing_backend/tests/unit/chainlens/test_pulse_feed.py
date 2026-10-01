"""Unit tests for chainlens.pulse_feed capability and routes (Story 20.10)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.capabilities.chainlens.pulse_feed.definition import CHAINLENS_PULSE_FEED
from app.capabilities.chainlens.pulse_feed.executor import PulseFeedExecutor
from app.capabilities.chainlens.pulse_feed.schemas import (
    PulseAngleResponse,
    PulseFeedInput,
    PulseFeedOutput,
    PulseItem,
)
from app.routes.pulse_routes import router as pulse_router
from app.users import require_session_context

pytestmark = pytest.mark.unit


def _auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


class TestPulseFeedSchemas:
    def test_schema_serialization(self):
        item = PulseItem(
            id="item_1",
            title="OpenAI Releases New Model",
            summary="Full summary here",
            topic="ai",
            publishedAt="2026-10-01T08:00:00Z",
            hasAngles=True,
        )
        assert item.has_angles is True
        assert item.published_at == "2026-10-01T08:00:00Z"

        output = PulseFeedOutput(
            items=[item],
            pagination={"nextCursor": "2026-09-30T00:00:00Z", "hasMore": True, "limit": 20},
        )
        assert len(output.items) == 1
        assert output.pagination.has_more is True

    def test_input_validation(self):
        inp = PulseFeedInput(topic="finance", limit=10)
        assert inp.topic == "finance"
        assert inp.limit == 10

        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PulseFeedInput(topic="invalid_topic_name")


class TestPulseFeedExecutor:
    async def test_fetch_feed_success(self):
        mock_data = {
            "items": [
                {
                    "id": "pulse_1",
                    "title": "Anthropic Claude 5 Announced",
                    "summary": "Full summary",
                    "topic": "ai",
                    "hasAngles": True,
                }
            ],
            "pagination": {"nextCursor": "cursor_abc", "hasMore": True, "limit": 10},
        }

        mock_res = MagicMock()
        mock_res.is_success = True
        mock_res.json.return_value = mock_data

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        executor = PulseFeedExecutor(base_url="http://mock-chainlens:3001")
        with patch("httpx.AsyncClient", return_value=mock_http):
            res = await executor.execute(PulseFeedInput(topic="ai", limit=10))

        assert len(res.items) == 1
        assert res.items[0].id == "pulse_1"
        assert res.pagination.has_more is True

    async def test_fetch_angles_success(self):
        mock_angles = [
            {
                "angleId": "angle_1",
                "label": "Competitive Moat Analysis",
                "description": "How this impacts competitors",
                "prompt": "Analyze the competitive moat...",
                "estimatedCredits": 2,
                "costDollars": 0.05,
                "model": "claude-haiku-4.5",
            }
        ]

        mock_res = MagicMock()
        mock_res.is_success = True
        mock_res.json.return_value = mock_angles

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_res)
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        executor = PulseFeedExecutor(base_url="http://mock-chainlens:3001")
        with patch("httpx.AsyncClient", return_value=mock_http):
            angles = await executor.get_item_angles("pulse_1", workspace_id=15)

        assert len(angles) == 1
        assert angles[0].angle_id == "angle_1"
        assert angles[0].estimated_credits == 2

    async def test_fetch_feed_http_error_fails_safe(self):
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=Exception("Network failure"))
        mock_http.__aenter__.return_value = mock_http
        mock_http.__aexit__.return_value = False

        executor = PulseFeedExecutor(base_url="http://mock-chainlens:3001")
        with patch("httpx.AsyncClient", return_value=mock_http):
            res = await executor.execute(PulseFeedInput())

        assert len(res.items) == 0
        assert res.pagination.has_more is False


class TestPulseRoutes:
    @pytest.fixture
    def app(self):
        test_app = FastAPI()
        test_app.include_router(pulse_router)
        test_app.dependency_overrides[require_session_context] = _auth
        return test_app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_get_feed_200(self, client, app):
        from app.routes.pulse_routes import _get_executor

        mock_exec = MagicMock()
        mock_exec.execute = AsyncMock(
            return_value=PulseFeedOutput(
                items=[
                    PulseItem(
                        id="p1",
                        title="AI Benchmark",
                        summary="s",
                        topic="ai",
                    )
                ]
            )
        )
        app.dependency_overrides[_get_executor] = lambda: mock_exec

        resp = client.get("/api/v1/workspaces/15/pulse/feed?topic=ai")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_get_angles_200(self, client, app):
        from app.routes.pulse_routes import _get_executor

        mock_exec = MagicMock()
        mock_exec.get_item_angles = AsyncMock(
            return_value=[
                PulseAngleResponse(
                    angleId="a1",
                    label="Angle 1",
                    description="d",
                    prompt="p",
                )
            ]
        )
        app.dependency_overrides[_get_executor] = lambda: mock_exec

        resp = client.get("/api/v1/workspaces/15/pulse/items/item_abc/angles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["angleId"] == "a1"

    def test_capability_registered(self):
        assert CHAINLENS_PULSE_FEED.name == "chainlens.pulse_feed"
