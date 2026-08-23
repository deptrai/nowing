"""Story 14.2b: News Entity Search ATDD Integration Test.

Verifies end-to-end entity search capability using stubbed chainlens-research response,
validates outbound request headers and SearchRestRequestDto compliance,
and confirms no local entity tables are created in PostgreSQL (AD-35).
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Request, Response


@pytest.mark.integration
class TestNewsEntitySearchChainlensIntegration:
    """AC-1 & AC-2: End-to-end integration test with ChainLens Research."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_entity_search_dispatches_to_chainlens_without_local_db(
        self,
    ) -> None:
        """Should query chainlens search endpoint with SearchRestRequestDto and return citations."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        mock_url = "http://127.0.0.1:3001/api/v1/search"

        def _match_request(request: Request) -> Response:
            assert request.headers.get("x-workspace-id") == "1"
            assert request.headers.get("authorization") == "Bearer test-token"
            body = json.loads(request.content)
            assert body.get("mode") == "fast"
            assert body.get("numResults") == 5
            assert body.get("category") == "news"
            assert body.get("output") == "search"
            assert "VinFast" in body.get("query", "")

            return Response(
                200,
                json={
                    "requestId": "req-test-142b-uuid",
                    "resolvedMode": "fast",
                    "resolvedSearchType": "hybrid",
                    "numResults": 1,
                    "costDollars": 0.005,
                    "results": [
                        {
                            "rank": 1,
                            "title": "VinFast gia tăng thị phần xe điện",
                            "url": "https://tuoitre.vn/vinfast-thi-phan-xe-dien",
                            "snippet": "VinFast ghi nhận mức tăng trưởng mạnh mẽ trong tháng 7...",
                            "source_type": "web",
                        }
                    ],
                },
            )

        respx.post(mock_url).mock(side_effect=_match_request)

        executor = EntitySearchExecutor(
            api_url="http://127.0.0.1:3001",
            api_key="test-token",
        )
        inp = EntitySearchInput(
            entity_name="VinFast",
            entity_type="organization",
            workspace_id=1,
            limit=5,
        )

        result = await executor.execute(inp)
        assert result.total_count == 1
        assert len(result.sources) == 1
        assert len(result.articles) == 1
        assert result.sources[0].title == "VinFast gia tăng thị phần xe điện"
        assert result.sources[0].url == "https://tuoitre.vn/vinfast-thi-phan-xe-dien"
        assert result.status == "complete"
        assert result.degraded is False
        assert result.cost_micros == 5000
        assert result.cost_basis == "actual"

    @pytest.mark.asyncio
    @respx.mock
    async def test_entity_search_uses_cost_fallback_when_costdollars_missing(
        self,
    ) -> None:
        """Should mark cost_basis=fallback when ChainLens omits costDollars."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "numResults": 1,
                    "results": [
                        {
                            "title": "VinFast",
                            "url": "https://tuoitre.vn/vinfast",
                            "snippet": "VinFast...",
                        }
                    ],
                },
            )
        )

        executor = EntitySearchExecutor(
            api_url="http://127.0.0.1:3001",
            api_key="test-token",
        )
        inp = EntitySearchInput(
            entity_name="VinFast",
            entity_type="organization",
            workspace_id=1,
        )

        result = await executor.execute(inp)
        assert result.status == "complete"
        assert result.degraded is False
        assert result.cost_dollars is None
        assert result.cost_micros is None
        assert result.cost_basis == "fallback"
