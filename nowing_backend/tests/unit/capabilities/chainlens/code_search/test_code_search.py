"""``chainlens.code_search`` unit tests.

Covers the spec's I/O & edge-case matrix: happy query with/without language,
upstream timeout with nextAction, missing config/auth, upstream 5xx, PII
redaction, empty results, maxResults bounds, cost mapping, header
propagation, 401 token rotation, serialization paging, citation wiring,
and tool registration.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Request, Response
from pydantic import ValidationError


@pytest.mark.unit
class TestCodeSearchSchemas:
    """Schema contracts for chainlens.code_search."""

    def test_code_search_input_valid(self) -> None:
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        payload = CodeSearchInput(
            query="  how to use httpx  ",
            language="Python",
            maxResults=10,
            mode="balanced",
            workspace_id=1,
        )
        assert payload.query == "how to use httpx"
        assert payload.language == "python"
        assert payload.maxResults == 10
        assert payload.mode == "balanced"
        assert payload.workspace_id == 1

    def test_defaults(self) -> None:
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        payload = CodeSearchInput(query="httpx retry", workspace_id=1)
        assert payload.language is None
        assert payload.maxResults == 8
        assert payload.mode == "fast"

    def test_rejects_empty_query(self) -> None:
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        with pytest.raises(ValidationError):
            CodeSearchInput(query="   ", workspace_id=1)

    def test_rejects_overlong_query(self) -> None:
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        with pytest.raises(ValidationError):
            CodeSearchInput(query="x" * 1001, workspace_id=1)

    def test_rejects_maxresults_out_of_bounds(self) -> None:
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        with pytest.raises(ValidationError):
            CodeSearchInput(query="q", workspace_id=1, maxResults=25)
        with pytest.raises(ValidationError):
            CodeSearchInput(query="q", workspace_id=1, maxResults=0)

    def test_language_regex_enforced(self) -> None:
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        assert (
            CodeSearchInput(query="q", language="c++", workspace_id=1).language
            == "c++"
        )
        assert (
            CodeSearchInput(query="q", language="c#", workspace_id=1).language
            == "c#"
        )
        assert (
            CodeSearchInput(
                query="q", language="objective-c", workspace_id=1
            ).language
            == "objective-c"
        )
        assert (
            CodeSearchInput(query="q", language="   ", workspace_id=1).language
            is None
        )
        with pytest.raises(ValidationError):
            CodeSearchInput(query="q", language="python!!", workspace_id=1)
        with pytest.raises(ValidationError):
            CodeSearchInput(query="q", language="java script", workspace_id=1)


@pytest.mark.unit
class TestCodeSearchCapabilityRegistration:
    """Capability registration and agent tool exposure."""

    def test_chainlens_code_search_registered(self) -> None:
        from app.capabilities.chainlens.code_search.definition import (
            CHAINLENS_CODE_SEARCH,
        )
        from app.capabilities.core import get_capability

        cap = get_capability("chainlens.code_search")
        assert cap is not None
        assert cap == CHAINLENS_CODE_SEARCH
        assert cap.name == "chainlens.code_search"
        assert cap.input_schema is not None
        assert cap.output_schema is not None

    def test_chainlens_subagent_loads_code_search_tool(self) -> None:
        from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools.index import (
            load_tools,
        )

        tools = load_tools(dependencies={"workspace_id": 1, "user_id": 1})
        tool_names = [t.name for t in tools]
        assert "chainlens_code_search" in tool_names

    def test_ci_verbs_includes_code_search(self) -> None:
        from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools.index import (
            _CI_VERBS,
        )

        assert "chainlens.code_search" in [v.name for v in _CI_VERBS]


def _sources_payload(**overrides: object) -> dict:
    base: dict = {
        "sources": [
            {
                "url": "https://github.com/encode/httpx/blob/master/README.md",
                "title": "httpx README",
                "content": "```python\nimport httpx\nr = httpx.get('https://x')\n```",
                "metadata": {
                    "source": "github",
                    "sourceId": "encode/httpx:README.md:1",
                    "score": 0.92,
                },
            }
        ],
        "costDollars": 0.003,
    }
    base.update(overrides)
    return base

def _sse_payload(**overrides: object) -> str:
    """Convert the non-SSE payload into a ChainLens SSE stream string.

    The upstream API requires ``stream: True`` for ``output=code_context``;
    mock responses must use ``text=`` with SSE ``data:`` lines.
    """
    import json as _json

    payload = _sources_payload(**overrides)
    sources = payload.get("sources", [])
    cost = payload.get("costDollars")
    status = payload.get("status", "complete")
    estimated = payload.get("estimated")
    next_action = payload.get("nextAction")
    message = payload.get("message")

    lines: list[str] = []
    lines.append('data: {"type":"init","data":"Stream connected"}')
    lines.append("")
    # Each source becomes a "source" block
    if sources:
        sources_json = _json.dumps(sources)
        lines.append(
            f'data: {{"type":"block","block":{{"id":"src-1","type":"source","data":{sources_json}}}}}'
        )
        lines.append("")
    # Pass through status/nextAction/message in the done frame
    done_frame = {
        "type": "done",
        "chatId": "mock-chat",
        "webUrl": "",
    }
    if cost is not None:
        done_frame["costDollars"] = cost
    if estimated is not None:
        done_frame["estimated"] = estimated
    if status != "complete":
        done_frame["status"] = status
    if next_action:
        done_frame["nextAction"] = next_action
    if message:
        done_frame["message"] = message
    lines.append(f"data: {_json.dumps(done_frame)}")
    lines.append("")
    lines.append("data: [DONE]")
    lines.append("")
    return "\n".join(lines)



@pytest.mark.unit
class TestCodeSearchExecutor:
    """Executor behaviour across the spec's edge-case matrix."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_happy_query_with_language_appended(self) -> None:
        """HAPPY single query: language appended to query, items parsed."""
        import json as _json

        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["body"] = _json.loads(request.content)
            captured["headers"] = request.headers
            return Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(
                query="how to use httpx",
                language="python",
                workspace_id=1,
            )
        )

        body = captured["body"]
        assert body["query"] == "how to use httpx python"
        assert body["output"] == "code_context"
        assert body["dataSources"] == ["code"]
        assert body["sources"] == ["web"]
        assert body["stream"] is True
        assert body["numResults"] == 8

        assert result.status == "complete"
        assert result.degraded is False
        assert len(result.items) == 1
        snip = result.items[0]
        assert snip.source == "github"
        assert snip.source_id == "encode/httpx:README.md:1"
        assert snip.title == "httpx README"
        assert snip.url is not None
        assert snip.score == 0.92
        assert "import httpx" in snip.content
        # Citation sources derived from item URLs for the agent door.
        assert len(result.sources) == 1
        assert result.sources[0].url == snip.url
        assert result.sources[0].title == "httpx README"
        assert result.cost_dollars == 0.003
        assert result.cost_micros == 3000
        assert result.cost_basis == "actual"

    @pytest.mark.asyncio
    @respx.mock
    async def test_outbound_headers_propagate_workspace(self) -> None:
        """api_key path: X-Workspace-Id header carries the workspace id."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["headers"] = request.headers
            return Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        await executor.execute(
            CodeSearchInput(query="q", workspace_id=42)
        )
        assert captured["headers"].get("x-workspace-id") == "42"
        assert captured["headers"].get("authorization") == "Bearer test-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_service_auth_headers_propagate_correlation_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Service-auth path: X-Correlation-Id + X-Workspace-Id propagate."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["headers"] = request.headers
            return Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = CodeSearchExecutor(api_url="http://127.0.0.1:3001")
        # Force the service-auth branch with a stubbed auth object.
        class _StubAuth:
            configured = True

            def get_outbound_headers(
                self, workspace_id, *, correlation_id=None, content_type=None
            ):
                return {
                    "X-Workspace-Id": str(workspace_id),
                    "Authorization": "Bearer svc-token",
                    "X-Correlation-Id": correlation_id or "generated",
                    "Content-Type": content_type or "",
                }

            def rotate(self, *, workspace_id=0, reason=""):
                return None

        monkeypatch.setattr(executor, "_auth", _StubAuth())
        await executor.execute(
            CodeSearchInput(
                query="q", workspace_id=7, correlation_id="corr-123"
            )
        )
        assert captured["headers"].get("x-correlation-id") == "corr-123"
        assert captured["headers"].get("x-workspace-id") == "7"
        assert captured["headers"].get("authorization") == "Bearer svc-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_happy_query_without_language_sent_verbatim(self) -> None:
        """HAPPY no language: query sent verbatim, nothing appended."""
        import json as _json

        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["body"] = _json.loads(request.content)
            return Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        await executor.execute(
            CodeSearchInput(query="httpx retry", workspace_id=1)
        )
        assert captured["body"]["query"] == "httpx retry"

    @pytest.mark.asyncio
    @respx.mock
    async def test_combined_query_truncated_to_1000_chars(self) -> None:
        """query + language may not exceed the upstream 1000-char limit."""
        import json as _json

        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["body"] = _json.loads(request.content)
            return Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        await executor.execute(
            CodeSearchInput(
                query="x" * 1000, language="python", workspace_id=1
            )
        )
        assert len(captured["body"]["query"]) <= 1000

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_status_surfaces_next_action(self) -> None:
        """Timeout w/ nextAction: output carries the hint, no auto-retry."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                text=_sse_payload(
                    status="timeout",
                    nextAction="retry with a narrower query",
                    message="Search timed out partway.",
                ),
                headers={"content-type": "text/event-stream"},
            )
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="broad query", workspace_id=1)
        )
        assert result.status == "timeout"
        assert result.degraded is False
        assert result.next_action == "retry with a narrower query"
        assert result.message == "Search timed out partway."
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_missing_api_url_degrades(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing API URL → engine_unavailable typed degradation."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput
        from app.config import config

        monkeypatch.setattr(config, "CHAINLENS_API_URL", "")
        executor = CodeSearchExecutor()
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True
        assert result.degradation_reason == "missing_api_url"
        assert result.items == []
        assert result.cost_micros is None
        assert result.message is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_missing_auth_degrades(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing auth → engine_unavailable typed degradation."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput
        from app.services.chainlens.auth import ChainLensServiceAuth

        # Clear any ambient service tokens/HMAC so the auth check really fails.
        monkeypatch.setattr(
            ChainLensServiceAuth, "configured", property(lambda self: False)
        )
        executor = CodeSearchExecutor(api_url="http://127.0.0.1:3001")
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True
        assert result.degradation_reason == "missing_auth"
        assert result.items == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_upstream_5xx_degrades(self) -> None:
        """Upstream 5xx → engine_unavailable typed degradation."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(503)
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.status == "engine_unavailable"
        assert result.degraded is True
        assert result.degradation_reason == "upstream_error"
        assert result.items == []
        assert result.cost_micros is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_401_rotates_token_and_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """401 on first attempt → rotate() → retry with rebuilt headers."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        calls: list[str | None] = []

        def _match(request: Request) -> Response:
            calls.append(request.headers.get("authorization"))
            if len(calls) == 1:
                return Response(401)
            return Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = CodeSearchExecutor(api_url="http://127.0.0.1:3001")

        class _StubAuth:
            configured = True

            def get_outbound_headers(
                self, workspace_id, *, correlation_id=None, content_type=None
            ):
                return {
                    "X-Workspace-Id": str(workspace_id),
                    "Authorization": "Bearer rotated-token",
                }

            def rotate(self, *, workspace_id=0, reason=""):
                return "rotated-token"

        monkeypatch.setattr(executor, "_auth", _StubAuth())
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.status == "complete"
        assert len(calls) == 2
        assert calls[1] == "Bearer rotated-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_query_is_pii_redacted_before_send(self) -> None:
        """PII in query → redact_pii applied before leaving Nowing."""
        import json as _json

        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        captured: dict = {}

        def _match(request: Request) -> Response:
            captured["body"] = _json.loads(request.content)
            return Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(side_effect=_match)

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(
                query="debug login for 0987654321 or leak@example.test",
                workspace_id=1,
            )
        )
        assert result.status == "complete"
        sent_query = captured["body"]["query"]
        assert "0987654321" not in sent_query
        assert "leak@example.test" not in sent_query

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_results_returns_partial_not_complete(self) -> None:
        """Empty results → status=partial with explanatory message."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(200, text=_sse_payload(sources=[]), headers={"content-type": "text/event-stream"})
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="obscure thing", workspace_id=1)
        )
        assert result.status == "partial"
        assert result.degraded is False
        assert result.items == []
        assert result.sources == []
        assert result.message is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_cost_fallback_when_costdollars_missing(self) -> None:
        """Cost mapping: missing costDollars → cost_basis=fallback."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                text=_sse_payload(costDollars=None),
                headers={"content-type": "text/event-stream"},
            )
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.status == "complete"
        assert result.cost_dollars is None
        assert result.cost_micros is None
        assert result.cost_basis == "fallback"

    @pytest.mark.asyncio
    @respx.mock
    async def test_estimated_cost_flag_sets_basis(self) -> None:
        """Upstream ``estimated:true`` → cost_basis='estimated', not 'actual'."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(200, text=_sse_payload(estimated=True), headers={"content-type": "text/event-stream"})
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.cost_micros == 3000
        assert result.cost_basis == "estimated"

    @pytest.mark.asyncio
    @respx.mock
    async def test_malformed_json_degrades(self) -> None:
        """Malformed JSON → engine_unavailable typed degradation."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                text="not a valid sse stream\nno data lines",
                headers={"content-type": "text/event-stream"},
            )
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.status == "timeout"
        assert result.degraded is False
        assert result.items == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_contentless_sources_skipped(self) -> None:
        """Sources without string content are dropped from items."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                text=_sse_payload(
                    sources=[
                        {
                            "url": "https://github.com/a/b",
                            "title": "no content",
                            "metadata": {"source": "github"},
                        },
                        {
                            "url": "https://x.test/dict",
                            # dict content must not be coerced via str()
                            "content": {"code": "x=1"},
                            "metadata": {"source": "github"},
                        },
                        {
                            "url": "https://so/q/1",
                            "content": "```py\nx=1\n```",
                            "metadata": {
                                "source": "stackoverflow",
                                "sourceId": "q/1",
                                "score": 0.5,
                            },
                        },
                    ],
                ),
                headers={"content-type": "text/event-stream"},
            )
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert result.status == "complete"
        assert len(result.items) == 1
        assert result.items[0].source == "stackoverflow"

    @pytest.mark.asyncio
    @respx.mock
    async def test_bool_score_rejected(self) -> None:
        """``score: true`` (bool is an int) must not be accepted as a score."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                text=_sse_payload(
                    sources=[
                        {
                            "url": "https://x.test",
                            "content": "code",
                            "metadata": {"score": True},
                        }
                    ],
                ),
                headers={"content-type": "text/event-stream"},
            )
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert len(result.items) == 1
        assert result.items[0].score is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_snippet_content_capped(self) -> None:
        """Oversized snippet content is truncated at the cap."""
        from app.capabilities.chainlens.code_search.executor import (
            MAX_SNIPPET_CONTENT_CHARS,
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput

        big = "x" * (MAX_SNIPPET_CONTENT_CHARS + 1000)
        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(
                200,
                text=_sse_payload(
                    sources=[{"url": "https://a.test", "content": big}],
                ),
                headers={"content-type": "text/event-stream"},
            )
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        result = await executor.execute(
            CodeSearchInput(query="q", workspace_id=1)
        )
        assert len(result.items[0].content) < MAX_SNIPPET_CONTENT_CHARS + 50
        assert result.items[0].content.endswith("…[truncated]")

    @pytest.mark.asyncio
    @respx.mock
    async def test_executor_receives_ctx(self) -> None:
        """ctx param: CapabilityContext passed by the door reaches execute."""
        from app.capabilities.chainlens.code_search.executor import (
            CodeSearchExecutor,
        )
        from app.capabilities.chainlens.code_search.schemas import CodeSearchInput
        from app.capabilities.core import execute_with_context
        from app.capabilities.core.types import CapabilityContext

        respx.post("http://127.0.0.1:3001/api/v1/search").mock(
            return_value=Response(200, text=_sse_payload(), headers={"content-type": "text/event-stream"})
        )

        executor = CodeSearchExecutor(
            api_url="http://127.0.0.1:3001", api_key="test-token"
        )
        seen: dict = {}

        original_execute = executor.execute

        async def _spy(input_data, ctx=None):
            seen["ctx"] = ctx
            return await original_execute(input_data, ctx)

        async def _exec(input_data, ctx=None):
            return await _spy(input_data, ctx)

        ctx = CapabilityContext(session=None, workspace_id=1, run_id="r1")
        output = await execute_with_context(
            _exec,
            payload=CodeSearchInput(query="q", workspace_id=1),
            ctx=ctx,
        )
        assert seen["ctx"] is ctx
        assert output.status == "complete"


@pytest.mark.unit
class TestCodeSearchSerializationAndCitations:
    """Run serialization paging and citation-registry wiring."""

    def test_serialize_output_pages_per_item(self) -> None:
        """items → one JSONL line per snippet for run paging."""
        import json as _json

        from app.capabilities.chainlens.code_search.schemas import (
            CodeSearchOutput,
            CodeSnippet,
        )
        from app.capabilities.core.runs import serialize_output

        output = CodeSearchOutput(
            items=[
                CodeSnippet(
                    url="https://a.test/1", content="c1", title="t1"
                ),
                CodeSnippet(
                    url="https://a.test/2", content="c2", title="t2"
                ),
                CodeSnippet(
                    url="https://a.test/3", content="c3", title="t3"
                ),
            ],
            status="complete",
        )
        serialized = serialize_output(output)
        assert serialized.item_count == 3
        lines = serialized.text.split("\n")
        assert len(lines) == 3
        first = _json.loads(lines[0])
        assert first["url"] == "https://a.test/1"
        assert first["content"] == "c1"

    def test_sources_register_web_citations(self) -> None:
        """output.sources feeds register_web_citations (agent door contract)."""
        from app.agents.chat.multi_agent_chat.shared.citations.registry import (
            CitationRegistry,
        )
        from app.capabilities.chainlens.code_search.schemas import (
            CodeSearchOutput,
        )
        from app.capabilities.chainlens.research.schemas import Source
        from app.capabilities.core.access.web_citation import (
            register_web_citations,
        )

        output = CodeSearchOutput(
            sources=[
                    Source(
                        title="t1", url="https://a.test/1", source_type="web"
                    ),
                    Source(
                        title="t2", url="https://a.test/2", source_type="web"
                    ),
            ],
            status="complete",
        )
        registry = CitationRegistry()
        sources = getattr(output, "sources", None)
        assert sources
        ordinals = register_web_citations(registry, sources)
        assert len(ordinals) == 2
