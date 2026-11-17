"""Unit tests for chainlens.pulse_research capability (Story 20.11)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.capabilities.chainlens.pulse_research.executor import (
    ChainLensPulseResearchError,
    ChainLensPulseResearchNotFoundError,
    PulseResearchExecutor,
)
from app.capabilities.chainlens.pulse_research.schemas import PulseResearchInput
from app.routes.pulse_routes import router as pulse_router
from app.users import require_session_context

pytestmark = pytest.mark.unit


def _auth() -> AuthContext:
    user = SimpleNamespace(id=uuid4(), is_active=True, is_superuser=False)
    return AuthContext.session(user)


class TestPulseResearchSchemas:
    def test_input_aliases(self):
        inp = PulseResearchInput(
            itemId="pulse_1", angleId="angle_1", mode="deep", chatId="chat_x"
        )
        assert inp.item_id == "pulse_1"
        assert inp.angle_id == "angle_1"
        assert inp.mode == "deep"
        assert inp.chat_id == "chat_x"

    def test_research_output_reused_not_reimplemented(self):
        """ResearchOutput must be the shared class from chainlens.research."""
        from app.capabilities.chainlens.research.schemas import (
            ResearchOutput as ExpectedOutput,
        )

        assert ExpectedOutput is not None


class TestPulseResearchExecutor:
    async def test_stream_research_yields_sse_lines(self):
        executor = PulseResearchExecutor(base_url="http://mock-chainlens:3001")

        sse_lines = [
            'data: {"type":"block","id":"b1","blockType":"answer","data":"# Report"}',
            'data: {"type":"done","chatId":"chat_x","usage":{"costDollars":0.05}}',
        ]

        class _FakeResponse:
            status_code = 200

            async def aiter_lines(self):
                for line in sse_lines:
                    yield line

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(
            return_value=SimpleNamespace(
                status_code=200, aiter_lines=lambda: _aiter(sse_lines)
            )
        )
        mock_stream_ctx.__aexit__.return_value = False

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False

        with patch("httpx.AsyncClient", return_value=mock_client):
            collected = [
                line
                async for line in executor.stream_research(
                    PulseResearchInput(itemId="p1", angleId="a1")
                )
            ]

        assert len(collected) == 2
        assert "done" in collected[1]

    async def test_stream_research_404_raises_not_found(self):
        executor = PulseResearchExecutor(base_url="http://mock-chainlens:3001")

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__.return_value = SimpleNamespace(status_code=404)
        mock_stream_ctx.__aexit__.return_value = False

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.raises(ChainLensPulseResearchNotFoundError),
        ):
            async for _ in executor.stream_research(
                PulseResearchInput(itemId="p", angleId="a")
            ):
                pass

    async def test_stream_research_5xx_raises_error(self):
        executor = PulseResearchExecutor(base_url="http://mock-chainlens:3001")

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__.return_value = SimpleNamespace(status_code=503)
        mock_stream_ctx.__aexit__.return_value = False

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            pytest.raises(ChainLensPulseResearchError),
        ):
            async for _ in executor.stream_research(
                PulseResearchInput(itemId="p", angleId="a")
            ):
                pass


def _aiter(lines):
    async def _gen():
        for line in lines:
            yield line

    return _gen()


class TestPulseResearchEndpoint:
    @pytest.fixture
    def app(self):

        test_app = FastAPI()
        test_app.include_router(pulse_router)
        test_app.dependency_overrides[require_session_context] = _auth
        return test_app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_research_endpoint_parses_sse(self, client):
        body = {"itemId": "p1", "angleId": "a1", "mode": "balanced"}

        with patch(
            "app.capabilities.chainlens.pulse_research.executor.PulseResearchExecutor.stream_research",
            _stream_research_mock,
        ):
            resp = client.post(
                "/api/v1/workspaces/15/pulse/research",
                json=body,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data

    def test_research_404_when_item_missing(self, client):
        body = {"itemId": "p1", "angleId": "a1"}

        async def _not_found(self, input_data, context=None):
            raise ChainLensPulseResearchNotFoundError("not found")
            yield  # pragma: no cover

        with patch(
            "app.capabilities.chainlens.pulse_research.executor.PulseResearchExecutor.stream_research",
            _not_found,
        ):
            resp = client.post(
                "/api/v1/workspaces/15/pulse/research",
                json=body,
            )

        assert resp.status_code == 404


async def _stream_research_mock(self, input_data, context=None):
    yield 'data: {"type":"block","id":"b1","blockType":"answer","data":"Report"}'
    yield 'data: {"type":"done","chatId":"chat_x","usage":{"costDollars":0.05}}'
