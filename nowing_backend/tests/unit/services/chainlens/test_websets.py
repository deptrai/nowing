"""Unit tests for ChainLens Websets API client service (Story 41.1)."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.chainlens.websets import (
    WebsetsService,
    WebsetsUnavailable,
    WebsetsUnavailableError,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def websets_service() -> WebsetsService:
    return WebsetsService(base_url="http://test-chainlens:3001", timeout=5.0)


class TestWebsetsService:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_webset_success(self, websets_service: WebsetsService) -> None:
        route = respx.post("http://test-chainlens:3001/v1/websets").mock(
            return_value=httpx.Response(
                201,
                json={"id": "wbs_123", "status": "running"},
            )
        )

        res = await websets_service.create_webset(
            source={"type": "web"},
            columns=[{"name": "company_name", "type": "text"}],
            criteria={"prompt": "Find tech companies"},
            metadata={"webhookUrl": "http://localhost:8000/webhook"},
            workspace_id=42,
        )

        assert res["id"] == "wbs_123"
        assert route.called
        req = route.calls.last.request
        assert "Authorization" in req.headers
        assert req.headers.get("X-Workspace-Id") == "42"
        assert "X-Correlation-Id" in req.headers

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_webset_error_raises_unavailable(
        self, websets_service: WebsetsService
    ) -> None:
        respx.post("http://test-chainlens:3001/v1/websets").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(WebsetsUnavailableError):
            await websets_service.create_webset(
                source={"type": "web"},
                columns=[],
                workspace_id=42,
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_webset_success(self, websets_service: WebsetsService) -> None:
        route = respx.get("http://test-chainlens:3001/v1/websets/wbs_123").mock(
            return_value=httpx.Response(
                200,
                json={"id": "wbs_123", "status": "idle", "readyCount": 10},
            )
        )

        res = await websets_service.get_webset("wbs_123", workspace_id=42)
        assert res["id"] == "wbs_123"
        assert res["status"] == "idle"
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_webset_error_raises_unavailable(
        self, websets_service: WebsetsService
    ) -> None:
        respx.get("http://test-chainlens:3001/v1/websets/wbs_404").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        with pytest.raises(WebsetsUnavailable):
            await websets_service.get_webset("wbs_404", workspace_id=42)

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_pagination_and_filtering(
        self, websets_service: WebsetsService
    ) -> None:
        # Page 1: 3 items (2 ready/verified, 1 running), nextCursor="page_2"
        respx.get("http://test-chainlens:3001/v1/websets/wbs_123/items").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": "it_1", "status": "ready", "data": {"name": "Acme"}},
                            {
                                "id": "it_2",
                                "status": "running",
                                "data": {"name": "Pending"},
                            },
                            {
                                "id": "it_3",
                                "status": "verified",
                                "data": {"name": "Beta"},
                            },
                        ],
                        "nextCursor": "page_2",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "it_4",
                                "status": "ready",
                                "data": {"name": "Gamma"},
                            },
                        ],
                        "nextCursor": None,
                    },
                ),
            ]
        )

        yielded_items = []
        async for item in websets_service.iter_ready_items("wbs_123", workspace_id=42):
            yielded_items.append(item)

        assert len(yielded_items) == 3
        ids = [it["id"] for it in yielded_items]
        assert ids == ["it_1", "it_3", "it_4"]
