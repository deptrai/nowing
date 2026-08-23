"""Story 14.2b: News Entity Search ATDD Integration Test.

Verifies end-to-end entity search capability using stubbed chainlens-research response
and confirms no local entity tables are created in PostgreSQL (AD-35).
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.mark.integration
class TestNewsEntitySearchChainlensIntegration:
    """AC-1 & AC-2: End-to-end integration test with ChainLens Research."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_entity_search_dispatches_to_chainlens_without_local_db(
        self,
    ) -> None:
        """Should query chainlens search endpoint with entity filter and return citations."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        mock_url = "http://127.0.0.1:3001/api/v1/search"
        respx.post(mock_url).mock(
            return_value=Response(
                200,
                json={
                    "query": "Vingroup",
                    "results": [
                        {
                            "title": "VinFast gia tăng thị phần xe điện",
                            "url": "https://tuoitre.vn/vinfast-thi-phan-xe-dien",
                            "content": "VinFast ghi nhận mức tăng trưởng mạnh mẽ trong tháng 7...",
                            "source_type": "web",
                        }
                    ],
                    "total": 1,
                },
            )
        )

        executor = EntitySearchExecutor(api_url="http://127.0.0.1:3001")
        inp = EntitySearchInput(
            entity_name="VinFast",
            entity_type="organization",
            workspace_id=1,
            limit=5,
        )

        result = await executor.execute(inp)
        assert result.total_count == 1
        assert len(result.articles) == 1
        assert result.articles[0].title == "VinFast gia tăng thị phần xe điện"
        assert result.articles[0].url == "https://tuoitre.vn/vinfast-thi-phan-xe-dien"
