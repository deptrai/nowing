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

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_regenerates_headers_per_page(
        self, websets_service: WebsetsService
    ) -> None:
        """x-user-ctx HMAC có TTL 60s — headers phải regen mỗi page, không reuse."""
        respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "items": [{"id": "a", "status": "ready"}],
                        "nextCursor": "p2",
                    },
                ),
                httpx.Response(
                    200,
                    json={
                        "items": [{"id": "b", "status": "ready"}],
                        "nextCursor": None,
                    },
                ),
            ]
        )

        from unittest.mock import MagicMock, patch

        with patch(
            "app.services.chainlens.websets.get_chainlens_auth"
        ) as mock_auth_getter:
            mock_auth_getter.return_value.get_outbound_headers = MagicMock(
                return_value={"Authorization": "Bearer x"}
            )
            async for _ in websets_service.iter_ready_items("wbs_1", workspace_id=1):
                pass

        assert mock_auth_getter.return_value.get_outbound_headers.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_breaks_on_repeated_cursor(
        self, websets_service: WebsetsService
    ) -> None:
        """nextCursor lặp lại giá trị cũ -> break, không infinite loop."""
        route = respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"id": "a", "status": "ready"}],
                    "nextCursor": "same-cursor",
                },
            )
        )

        count = 0
        async for _ in websets_service.iter_ready_items("wbs_1", workspace_id=1):
            count += 1
            if count > 10:
                break

        # Page 1 cursor=None -> page 2 cursor=same -> page 3 same -> break
        assert route.call_count == 2
        assert count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_non_json_raises_unavailable(
        self, websets_service: WebsetsService
    ) -> None:
        """Proxy trả HTML/non-JSON -> WebsetsUnavailable, không raw decode error."""
        respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            return_value=httpx.Response(200, text="<html>502 Bad Gateway</html>")
        )

        with pytest.raises(WebsetsUnavailableError):
            async for _ in websets_service.iter_ready_items("wbs_1", workspace_id=1):
                pass

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_breaks_on_multi_hop_cursor_cycle(
        self, websets_service: WebsetsService
    ) -> None:
        """Vòng cursor A->B->A->B... (revisit cursor đã thấy) -> break."""
        route = respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            side_effect=[
                httpx.Response(200, json={"items": [{"id": "a"}], "nextCursor": "B"}),
                httpx.Response(200, json={"items": [{"id": "b"}], "nextCursor": "A"}),
                httpx.Response(200, json={"items": [{"id": "c"}], "nextCursor": "B"}),
            ]
        )

        items = [
            it
            async for it in websets_service.iter_ready_items("wbs_1", workspace_id=1)
        ]
        assert [it["id"] for it in items] == ["a", "b", "c"]
        assert route.call_count == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_rotates_token_once_on_401(
        self, websets_service: WebsetsService
    ) -> None:
        """401 -> rotate token qua auth singleton + retry cùng request 1 lần."""
        from unittest.mock import MagicMock, patch

        route = respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            side_effect=[
                httpx.Response(401, json={"error": "token expired"}),
                httpx.Response(200, json={"items": [{"id": "a"}], "nextCursor": None}),
            ]
        )

        with patch(
            "app.services.chainlens.websets.get_chainlens_auth"
        ) as mock_auth_getter:
            mock_auth = mock_auth_getter.return_value
            mock_auth.get_outbound_headers = MagicMock(
                return_value={"Authorization": "Bearer x"}
            )
            mock_auth.rotate = MagicMock(return_value="new-token")
            items = [
                it
                async for it in websets_service.iter_ready_items(
                    "wbs_1", workspace_id=1
                )
            ]

        assert [it["id"] for it in items] == ["a"]
        assert route.call_count == 2
        mock_auth.rotate.assert_called_once_with(
            workspace_id=1, reason="401_response"
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_401_no_rotation_raises_terminal(
        self, websets_service: WebsetsService
    ) -> None:
        """401 khi rotate trả None (hết token) -> raise retryable=False ngay."""
        from unittest.mock import MagicMock, patch

        route = respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )

        with patch(
            "app.services.chainlens.websets.get_chainlens_auth"
        ) as mock_auth_getter:
            mock_auth = mock_auth_getter.return_value
            mock_auth.get_outbound_headers = MagicMock(return_value={})
            mock_auth.rotate = MagicMock(return_value=None)
            with pytest.raises(WebsetsUnavailableError) as exc_info:
                async for _ in websets_service.iter_ready_items(
                    "wbs_1", workspace_id=1
                ):
                    pass

        assert exc_info.value.retryable is False
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_retries_5xx_then_succeeds(
        self, websets_service: WebsetsService
    ) -> None:
        """5xx transient -> backoff retry, page sau thành công."""
        from unittest.mock import AsyncMock, patch

        route = respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            side_effect=[
                httpx.Response(500, json={"error": "upstream"}),
                httpx.Response(200, json={"items": [{"id": "a"}], "nextCursor": None}),
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            items = [
                it
                async for it in websets_service.iter_ready_items(
                    "wbs_1", workspace_id=1
                )
            ]

        assert [it["id"] for it in items] == ["a"]
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_iter_ready_items_5xx_exhausted_raises_retryable(
        self, websets_service: WebsetsService
    ) -> None:
        """5xx hết attempts -> WebsetsUnavailable retryable=True."""
        from unittest.mock import AsyncMock, patch

        route = respx.get("http://test-chainlens:3001/v1/websets/wbs_1/items").mock(
            return_value=httpx.Response(500, json={"error": "upstream"})
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(WebsetsUnavailableError) as exc_info,
        ):
            async for _ in websets_service.iter_ready_items("wbs_1", workspace_id=1):
                pass

        assert exc_info.value.retryable is True
        assert route.call_count == 3
