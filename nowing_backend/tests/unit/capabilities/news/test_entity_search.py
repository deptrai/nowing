"""Story 14.2b: News Entity Search Unit Tests.

Covers AC1 and AC2 acceptance criteria, hardened validation, executor routing,
PII redaction, and degradation handling.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Request, Response
from pydantic import ValidationError


@pytest.mark.unit
class TestEntitySearchSchemas:
    """AC-1: Schema contracts for news entity search."""

    def test_entity_search_input_valid(self) -> None:
        """Should accept valid entity search input with allowed entity types."""
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        payload = EntitySearchInput(
            entity_name="Tập đoàn Vingroup",
            entity_type="organization",
            workspace_id=1,
            limit=10,
        )
        assert payload.entity_name == "Tập đoàn Vingroup"
        assert payload.entity_type == "organization"
        assert payload.workspace_id == 1
        assert payload.limit == 10
        assert payload.estimated_units == 1

    def test_entity_search_input_normalizes_type_and_whitespace(self) -> None:
        """Should normalize entity_type case and strip whitespace in mode=before."""
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        payload = EntitySearchInput(
            entity_name="  Tập đoàn Hòa Phát  ",
            entity_type="Organization",  # type: ignore[arg-type]
            workspace_id=2,
        )
        assert payload.entity_name == "Tập đoàn Hòa Phát"
        assert payload.entity_type == "organization"

    def test_entity_search_input_rejects_empty_name(self) -> None:
        """Should raise ValidationError when entity_name is empty or whitespace."""
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        with pytest.raises(ValidationError):
            EntitySearchInput(
                entity_name="   ",
                entity_type="person",
                workspace_id=1,
            )

    def test_entity_search_input_rejects_invalid_type(self) -> None:
        """Should raise ValidationError when entity_type is not in allowed enum."""
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        with pytest.raises(ValidationError):
            EntitySearchInput(
                entity_name="Hà Nội",
                entity_type="invalid_type",  # type: ignore[arg-type]
                workspace_id=1,
            )

    def test_entity_search_output_structure(self) -> None:
        """Should return properly structured EntitySearchOutput with sources and articles."""
        from app.capabilities.chainlens.research.schemas import Source
        from app.capabilities.news.entity_search.schemas import EntitySearchOutput

        source = Source(
            title="Vingroup công bố kết quả kinh doanh",
            url="https://vnexpress.net/vingroup-ket-qua-kinh-doanh",
            content="Tập đoàn Vingroup vừa công bố doanh thu quý 2...",
            source_type="web",
        )
        output = EntitySearchOutput(
            entity_name="Vingroup",
            entity_type="organization",
            sources=[source],
            total_count=1,
            cost_micros=5000,
            cost_basis="actual",
        )
        assert output.entity_name == "Vingroup"
        assert len(output.sources) == 1
        assert len(output.articles) == 1
        assert (
            output.articles[0].url
            == "https://vnexpress.net/vingroup-ket-qua-kinh-doanh"
        )
        assert output.total_count == 1
        assert output.status == "complete"
        assert output.cost_micros == 5000
        assert output.cost_basis == "actual"


@pytest.mark.unit
class TestEntitySearchCapabilityRegistration:
    """AC-2: Capability registration and discovery in Nowing registry."""

    def test_news_entity_search_registered(self) -> None:
        """Should register news.entity_search in capability registry."""
        from app.capabilities.core import get_capability
        from app.capabilities.news.entity_search.definition import NEWS_ENTITY_SEARCH

        cap = get_capability("news.entity_search")
        assert cap is not None
        assert cap == NEWS_ENTITY_SEARCH
        assert cap.name == "news.entity_search"
        assert cap.input_schema is not None
        assert cap.output_schema is not None

    def test_chainlens_subagent_loads_news_entity_search_tool(self) -> None:
        """Should expose news.entity_search tool via chainlens subagent tool loader."""
        from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools.index import (
            load_tools,
        )

        tools = load_tools(dependencies={"workspace_id": 1, "user_id": 1})
        tool_names = [t.name for t in tools]
        assert "news_entity_search" in tool_names


@pytest.mark.unit
class TestEntitySearchExecutor:
    """AC-1 & AC-2: Executor calling ChainLens Research endpoint without local DB search."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "placeholder",
        [
            "<NAME>",
            "<PERSON>",
            "[REDACTED]",
            "<NAME_1>",
            "'<NAME>'",
            "<name> (person)",
        ],
    )
    async def test_executor_handles_redacted_placeholders(
        self, placeholder: str
    ) -> None:
        """Should return degraded empty output when entity name is any PII placeholder."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        executor = EntitySearchExecutor()
        inp = EntitySearchInput(
            entity_name=placeholder,
            entity_type="person",
            workspace_id=1,
        )
        result = await executor.execute(inp)
        assert result.degraded is True
        assert result.status == "engine_unavailable"
        assert result.sources == []
        assert result.articles == []
        assert result.total_count == 0
        assert result.cost_micros is None
        assert "bảo mật thông tin cá nhân" in (result.message or "")

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_handles_redacted_substring_not_false_positive(self) -> None:
        """Should not treat a name containing '<NAME>' substring as redacted."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        executor = EntitySearchExecutor(
            api_url="http://127.0.0.1:3001",
            api_key="test-token",
        )

        def _match(request: Request) -> Response:
            assert request.headers.get("authorization") == "Bearer test-token"
            return Response(
                200,
                json={
                    "numResults": 1,
                    "results": [
                        {
                            "title": "Công ty <NAME>",
                            "url": "https://example.test/article",
                            "snippet": "Tin tức",
                        }
                    ],
                },
            )

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        inp = EntitySearchInput(
            entity_name="Công ty <NAME>",
            entity_type="organization",
            workspace_id=1,
        )
        result = await executor.execute(inp)
        assert result.degraded is False
        assert result.status == "complete"
        assert len(result.sources) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_returns_empty_results(self) -> None:
        """Should handle a ChainLens response with zero results."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "numResults": 0,
                    "total": 0,
                    "results": [],
                },
            )
        )

        executor = EntitySearchExecutor(
            api_url="http://127.0.0.1:3001",
            api_key="test-token",
        )
        inp = EntitySearchInput(
            entity_name="Không tồn tại",
            entity_type="organization",
            workspace_id=1,
        )
        result = await executor.execute(inp)
        assert result.degraded is False
        assert result.status == "complete"
        assert result.sources == []
        assert result.articles == []
        assert result.total_count == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_parses_pub_date(self) -> None:
        """Should populate Source.pub_date when ChainLens provides it."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "numResults": 1,
                    "results": [
                        {
                            "title": "VinFast gia tăng thị phần",
                            "url": "https://tuoitre.vn/vinfast",
                            "snippet": "VinFast...",
                            "pubDate": "2026-07-20T00:00:00Z",
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
        assert result.degraded is False
        assert len(result.sources) == 1
        assert result.sources[0].pub_date == "2026-07-20T00:00:00Z"

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_uses_cost_fallback_when_costdollars_missing(self) -> None:
        """Should set cost_basis=fallback and leave cost_micros None when engine omits cost."""
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
        assert result.degraded is False
        assert result.status == "complete"
        assert result.cost_dollars is None
        assert result.cost_micros is None
        assert result.cost_basis == "fallback"

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_handles_http_errors(self) -> None:
        """Should degrade on 5xx / 429 from ChainLens."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(503)
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
        assert result.degraded is True
        assert result.status == "engine_unavailable"
        assert result.sources == []
        assert result.cost_micros is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_handles_malformed_json(self) -> None:
        """Should degrade gracefully when ChainLens returns non-JSON body."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(200, text="not json")
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
        assert result.degraded is True
        assert result.status == "engine_unavailable"
        assert result.sources == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_degrades_without_auth(self) -> None:
        """Should degrade when neither ChainLensServiceAuth nor api_key is configured."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        executor = EntitySearchExecutor(
            api_url="http://127.0.0.1:3001",
        )
        inp = EntitySearchInput(
            entity_name="VinFast",
            entity_type="organization",
            workspace_id=1,
        )
        result = await executor.execute(inp)
        assert result.degraded is True
        assert result.status == "engine_unavailable"
        assert result.sources == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_redacts_phone_and_email_in_source_snippets(self) -> None:
        """Should sanitize source title/content for phone/email PII."""
        from app.capabilities.news.entity_search.executor import EntitySearchExecutor
        from app.capabilities.news.entity_search.schemas import EntitySearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "numResults": 1,
                    "results": [
                        {
                            "title": "Liên hệ 0987654321 để biết thêm",
                            "url": "https://example.test/article",
                            "snippet": "Gửi email đến leak@example.test hoặc gọi 0987654321",
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
            entity_name="Example",
            entity_type="organization",
            workspace_id=1,
        )
        result = await executor.execute(inp)
        assert result.degraded is False
        assert len(result.sources) == 1
        assert "<PHONE>" in result.sources[0].title
        assert "<PHONE>" in (result.sources[0].content or "")
        assert "<EMAIL>" in (result.sources[0].content or "")
