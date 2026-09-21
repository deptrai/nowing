"""``chainlens.contents`` unit tests.

Covers the I/O & edge-case matrix: happy single/multi-URL, partial failure,
auth-walled items, missing config, upstream errors, PII redaction, cost
mapping, and tool registration.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Request, Response
from pydantic import ValidationError


@pytest.mark.unit
class TestContentsSchemas:
    """Schema contracts for chainlens.contents."""

    def test_contents_input_valid(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        payload = ContentsInput(
            urls=["https://example.test/a", "https://example.test/b"],
            query="  compare these docs  ",
            workspace_id=1,
            subpages=2,
            summary=True,
            highlights=["pricing", "terms"],
        )
        assert payload.urls == ["https://example.test/a", "https://example.test/b"]
        assert payload.query == "compare these docs"
        assert payload.workspace_id == 1
        assert payload.estimated_units == 2

    def test_contents_input_blank_query_becomes_none(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        payload = ContentsInput(urls=["https://example.test"], query="   ", workspace_id=1)
        assert payload.query is None

    def test_contents_input_rejects_empty_urls(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        with pytest.raises(ValidationError):
            ContentsInput(urls=[], workspace_id=1)

    def test_contents_input_rejects_blank_url_entry(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        with pytest.raises(ValidationError):
            ContentsInput(urls=["https://example.test", "   "], workspace_id=1)

    def test_contents_input_rejects_non_http_scheme(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        with pytest.raises(ValidationError):
            ContentsInput(urls=["javascript:alert(1)"], workspace_id=1)
        with pytest.raises(ValidationError):
            ContentsInput(urls=["file:///etc/passwd"], workspace_id=1)
        with pytest.raises(ValidationError):
            ContentsInput(urls=["ftp://example.test/x"], workspace_id=1)
        with pytest.raises(ValidationError):
            ContentsInput(
                urls=["https://ok.test", "javascript:alert(1)"], workspace_id=1
            )

    def test_contents_input_accepts_http_scheme(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        payload = ContentsInput(urls=["http://example.test/a"], workspace_id=1)
        assert payload.urls == ["http://example.test/a"]

    def test_estimated_units_scales_with_url_count(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        single = ContentsInput(urls=["https://a.test"], workspace_id=1)
        assert single.estimated_units == 1
        many = ContentsInput(
            urls=[f"https://a.test/{i}" for i in range(10)], workspace_id=1
        )
        assert many.estimated_units == 10
        capped = ContentsInput(
            urls=[f"https://a.test/{i}" for i in range(100)], workspace_id=1
        )
        assert capped.estimated_units == 100

    def test_contents_input_rejects_out_of_range(self) -> None:
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        with pytest.raises(ValidationError):
            ContentsInput(
                urls=["https://example.test"], workspace_id=1, subpages=11
            )
        with pytest.raises(ValidationError):
            ContentsInput(
                urls=["https://example.test"], workspace_id=1, maxAgeHours=0
            )


@pytest.mark.unit
class TestContentsCapabilityRegistration:
    """Capability registration and agent tool exposure."""

    def test_chainlens_contents_registered(self) -> None:
        from app.capabilities.chainlens.contents.definition import CHAINLENS_CONTENTS
        from app.capabilities.core import get_capability

        cap = get_capability("chainlens.contents")
        assert cap is not None
        assert cap == CHAINLENS_CONTENTS
        assert cap.name == "chainlens.contents"
        assert cap.input_schema is not None
        assert cap.output_schema is not None

    def test_chainlens_subagent_loads_contents_tool(self) -> None:
        from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools.index import (
            load_tools,
        )

        tools = load_tools(dependencies={"workspace_id": 1, "user_id": 1})
        tool_names = [t.name for t in tools]
        assert "chainlens_contents" in tool_names

    def test_ci_verbs_includes_contents(self) -> None:
        from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools.index import (
            _CI_VERBS,
        )

        assert "chainlens.contents" in [v.name for v in _CI_VERBS]


@pytest.mark.unit
class TestContentsExecutor:
    """Executor behaviour across the spec's edge-case matrix."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_happy_single_url_defaults_query_to_joined_urls(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        def _match(request: Request) -> Response:
            import json as _json

            body = _json.loads(request.content)
            assert body["output"] == "contents"
            assert body["stream"] is False
            assert body["urls"] == ["https://example.test/page"]
            assert body["query"] == "https://example.test/page"
            assert request.headers.get("authorization") == "Bearer test-token"
            return Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://example.test/page",
                            "title": "Example Page",
                            "content": "# Hello\nClean markdown",
                            "status": "ok",
                        }
                    ],
                    "costDollars": 0.0025,
                },
            )

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://example.test/page"], workspace_id=1)
        )
        assert result.status == "complete"
        assert result.degraded is False
        assert len(result.items) == 1
        assert result.items[0].content == "# Hello\nClean markdown"
        assert result.items[0].status == "ok"
        assert len(result.sources) == 1
        assert result.sources[0].url == "https://example.test/page"
        assert "Clean markdown" in result.content
        assert result.cost_dollars == 0.0025
        assert result.cost_micros is not None and result.cost_micros > 0
        assert result.cost_basis == "actual"

    @pytest.mark.asyncio
    @respx.mock
    async def test_happy_multi_url_aggregates_in_order(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://a.test/1",
                            "title": "A",
                            "content": "first",
                            "status": "ok",
                        },
                        {
                            "url": "https://b.test/2",
                            "title": "B",
                            "content": "second",
                            "summary": "B summary",
                            "highlights": [{"excerpt": "hl1"}],
                            "status": "ok",
                        },
                    ],
                    "costDollars": 0.005,
                },
            )
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(
                urls=["https://a.test/1", "https://b.test/2"],
                query="focus",
                workspace_id=1,
            )
        )
        assert result.status == "complete"
        assert [i.url for i in result.items] == [
            "https://a.test/1",
            "https://b.test/2",
        ]
        assert result.items[1].summary == "B summary"
        assert result.items[1].highlights == ["hl1"]
        assert result.content == "first\n\nsecond"
        assert len(result.sources) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_partial_failure_sets_partial_status(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://a.test/1",
                            "title": "A",
                            "content": "ok body",
                            "status": "ok",
                        },
                        {
                            "url": "https://b.test/2",
                            "status": "error",
                        },
                    ]
                },
            )
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(
                urls=["https://a.test/1", "https://b.test/2"], workspace_id=1
            )
        )
        assert result.status == "partial"
        assert result.degraded is False
        assert result.items[1].status == "error"
        assert len(result.sources) == 1
        assert result.message is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_walled_url_returns_typed_status(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://private.test/dashboard",
                            "status": "unsupported_auth_wall",
                        }
                    ]
                },
            )
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://private.test/dashboard"], workspace_id=1)
        )
        assert result.status == "partial"
        assert result.degraded is False
        assert result.items[0].status == "unsupported_auth_wall"
        assert result.sources == []
        assert "Browser Operator" in (result.message or "")

    @pytest.mark.asyncio
    async def test_missing_api_url_degrades(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        executor = ContentsExecutor(api_url="")
        executor._api_url = ""
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True
        assert result.items == []
        assert result.cost_micros is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_auth_degrades(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        executor = ContentsExecutor(api_url="http://127.0.0.1:3001")
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True
        assert result.items == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_upstream_5xx_degrades(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(503)
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True
        assert result.items == []
        assert result.cost_micros is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_degrades(self) -> None:
        import httpx

        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            side_effect=httpx.TimeoutException("boom")
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_query_is_pii_redacted_before_send(self) -> None:
        import json as _json

        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["body"] = _json.loads(request.content)
            return Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://a.test",
                            "content": "body",
                            "status": "ok",
                        }
                    ]
                },
            )

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(
                urls=["https://a.test"],
                query="call me at 0987654321 or leak@example.test",
                workspace_id=1,
            )
        )
        assert result.status == "complete"
        sent_query = captured["body"]["query"]
        assert "0987654321" not in sent_query
        assert "leak@example.test" not in sent_query

    @pytest.mark.asyncio
    @respx.mock
    async def test_cost_fallback_when_costdollars_missing(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {"url": "https://a.test", "content": "x", "status": "ok"}
                    ]
                },
            )
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "complete"
        assert result.cost_dollars is None
        assert result.cost_micros is None
        assert result.cost_basis == "fallback"

    @pytest.mark.asyncio
    @respx.mock
    async def test_malformed_json_degrades(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(200, text="not json")
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_default_query_not_pii_redacted(self) -> None:
        """Default URL-join query must be sent verbatim (URLs contain digits)."""
        import json as _json

        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["body"] = _json.loads(request.content)
            return Response(
                200,
                json={
                    "results": [
                        {"url": "https://a.test/123", "content": "x", "status": "ok"},
                        {"url": "https://b.test/u@2", "content": "y", "status": "ok"},
                    ]
                },
            )

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        urls = ["https://a.test/123", "https://b.test/u@2"]
        await executor.execute(ContentsInput(urls=urls, workspace_id=1))
        assert captured["body"]["query"] == "\n".join(urls)

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_results_returns_partial_not_complete(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(200, json={"results": []})
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "partial"
        assert result.degraded is False
        assert result.items == []
        assert result.message is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_ok_item_with_no_content_counts_as_failure(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://a.test",
                            "content": "real body",
                            "status": "ok",
                        },
                        {
                            "url": "https://b.test",
                            "status": "ok",
                        },
                    ]
                },
            )
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(
                urls=["https://a.test", "https://b.test"], workspace_id=1
            )
        )
        assert result.status == "partial"
        assert result.items[1].status == "error"
        assert len(result.sources) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_url_in_results_reflected(self) -> None:
        from app.capabilities.chainlens.contents.executor import ContentsExecutor
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://a.test",
                            "content": "body",
                            "status": "ok",
                        }
                    ]
                },
            )
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(
                urls=["https://a.test", "https://gone.test"], workspace_id=1
            )
        )
        assert result.status == "partial"
        assert len(result.items) == 1
        assert result.message is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_combined_content_capped(self) -> None:
        from app.capabilities.chainlens.contents.executor import (
            MAX_COMBINED_CONTENT_CHARS,
            ContentsExecutor,
        )
        from app.capabilities.chainlens.contents.schemas import ContentsInput

        big = "x" * (MAX_COMBINED_CONTENT_CHARS + 1000)
        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {"url": "https://a.test", "content": big, "status": "ok"}
                    ]
                },
            )
        )

        executor = ContentsExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            ContentsInput(urls=["https://a.test"], workspace_id=1)
        )
        assert result.status == "complete"
        assert len(result.content) < MAX_COMBINED_CONTENT_CHARS + 50
        assert result.content.endswith("…[truncated]")
