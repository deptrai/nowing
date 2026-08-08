"""Tests for MCP tool citation registration (Exa web_search/web_fetch)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langgraph.types import Command

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
    _extract_citable_urls,
)

pytestmark = pytest.mark.unit


# --- _extract_citable_urls -------------------------------------------------


def test_web_fetch_exa_returns_input_url() -> None:
    pairs = _extract_citable_urls(
        "web_fetch_exa",
        result_text="page content here",
        call_kwargs={"url": "https://example.com/page"},
    )
    assert pairs == [("https://example.com/page", None)]


def test_web_fetch_exa_empty_url_returns_empty() -> None:
    pairs = _extract_citable_urls(
        "web_fetch_exa",
        result_text="content",
        call_kwargs={"url": ""},
    )
    assert pairs == []


def test_web_search_exa_extracts_urls_with_titles() -> None:
    result = (
        "Title: Foo\nURL: https://foo.com/article\n\n"
        "Title: Bar\nURL: https://bar.com/post\n\n"
        "Some text without URL"
    )
    pairs = _extract_citable_urls(
        "web_search_exa",
        result_text=result,
        call_kwargs={},
    )
    assert pairs == [
        ("https://foo.com/article", "Foo"),
        ("https://bar.com/post", "Bar"),
    ]


def test_web_search_exa_bare_urls_get_none_title() -> None:
    result = "https://example.com/a\nhttps://example.com/b"
    pairs = _extract_citable_urls(
        "web_search_exa",
        result_text=result,
        call_kwargs={},
    )
    assert pairs == [
        ("https://example.com/a", None),
        ("https://example.com/b", None),
    ]


def test_web_search_exa_deduplicates_urls() -> None:
    result = "https://example.com/a\nhttps://example.com/a\nhttps://example.com/b"
    pairs = _extract_citable_urls(
        "web_search_exa",
        result_text=result,
        call_kwargs={},
    )
    assert pairs == [
        ("https://example.com/a", None),
        ("https://example.com/b", None),
    ]


def test_web_search_exa_caps_at_max() -> None:
    result = "\n".join(f"https://example.com/{i}" for i in range(50))
    pairs = _extract_citable_urls(
        "web_search_exa",
        result_text=result,
        call_kwargs={},
    )
    assert len(pairs) == 20
    assert pairs[0] == ("https://example.com/0", None)


def test_non_citable_tool_returns_empty() -> None:
    pairs = _extract_citable_urls(
        "some_other_tool",
        result_text="https://example.com/irrelevant",
        call_kwargs={},
    )
    assert pairs == []


def test_web_search_exa_no_urls_returns_empty() -> None:
    pairs = _extract_citable_urls(
        "web_search_exa",
        result_text="No URLs in this text",
        call_kwargs={},
    )
    assert pairs == []


# --- Integration: mcp_http_tool_call with citations ------------------------


def _make_runtime(registry: CitationRegistry | None = None) -> MagicMock:
    """Build a fake ToolRuntime with a state dict containing the registry."""
    state: dict = {}
    if registry is not None:
        state["citation_registry"] = registry
    runtime = MagicMock()
    runtime.state = state
    runtime.tool_call_id = "test_call_123"
    return runtime


@pytest.mark.asyncio
async def test_mcp_http_tool_registers_citations_for_web_search_exa(
    monkeypatch,
) -> None:
    """When web_search_exa returns URLs and runtime is present, citations are registered."""
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
        _create_mcp_tool_from_definition_http,
    )

    tool_def = {
        "name": "web_search_exa",
        "description": "Search the web with Exa",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    }

    fake_result = (
        "Title: Result 1\nURL: https://example.com/r1\n\n"
        "Title: Result 2\nURL: https://example.com/r2"
    )

    async def fake_do_call(headers, call_kwargs, timeout=60.0):
        return fake_result

    tool = await _create_mcp_tool_from_definition_http(
        url="https://mcp.exa.ai/mcp",
        headers={"x-api-key": "fake"},
        tool_def=tool_def,
        connector_name="Exa",
        connector_id=1,
        readonly_tools=frozenset({"web_search_exa"}),
        bypass_internal_hitl=True,
    )

    # Monkeypatch the inner _do_mcp_call closure to avoid real HTTP.
    # The closure is defined inside _create_mcp_tool_from_definition_http; we patch at the module
    # level by replacing the streamablehttp_client context manager.
    import app.agents.chat.multi_agent_chat.shared.tools.mcp.tool as mcp_mod

    class _FakeStream:
        async def __aenter__(self):
            return (None, None, None)

        async def __aexit__(self, *args):
            return False

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def initialize(self):
            pass

        async def call_tool(self, name, arguments):
            resp = MagicMock()
            content_item = MagicMock()
            content_item.text = fake_result
            resp.content = [content_item]
            return resp

    monkeypatch.setattr(
        mcp_mod, "streamablehttp_client", lambda *a, **kw: _FakeStream()
    )
    monkeypatch.setattr(mcp_mod, "ClientSession", lambda *a, **kw: _FakeSession())

    registry = CitationRegistry()
    runtime = _make_runtime(registry)

    result = await tool.coroutine(runtime=runtime, query="test")

    assert isinstance(result, Command)
    updated_registry = result.update.get("citation_registry")
    assert updated_registry is not None
    assert len(updated_registry.by_n) == 2
    entry1 = updated_registry.resolve(1)
    assert entry1.source_type == CitationSourceType.WEB_RESULT
    assert entry1.locator["url"] == "https://example.com/r1"
    assert entry1.display["title"] == "Result 1"


@pytest.mark.asyncio
async def test_mcp_http_tool_registers_citations_for_web_fetch_exa(
    monkeypatch,
) -> None:
    """When web_fetch_exa is called with a URL and runtime is present, the input URL is registered."""
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
        _create_mcp_tool_from_definition_http,
    )

    tool_def = {
        "name": "web_fetch_exa",
        "description": "Fetch a URL with Exa",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
        },
    }

    fake_result = "# Page Title\n\nSome fetched content here."

    class _FakeStream:
        async def __aenter__(self):
            return (None, None, None)

        async def __aexit__(self, *args):
            return False

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def initialize(self):
            pass

        async def call_tool(self, name, arguments):
            resp = MagicMock()
            content_item = MagicMock()
            content_item.text = fake_result
            resp.content = [content_item]
            return resp

    import app.agents.chat.multi_agent_chat.shared.tools.mcp.tool as mcp_mod

    monkeypatch.setattr(
        mcp_mod, "streamablehttp_client", lambda *a, **kw: _FakeStream()
    )
    monkeypatch.setattr(mcp_mod, "ClientSession", lambda *a, **kw: _FakeSession())

    tool = await _create_mcp_tool_from_definition_http(
        url="https://mcp.exa.ai/mcp",
        headers={"x-api-key": "fake"},
        tool_def=tool_def,
        connector_name="Exa",
        connector_id=1,
        readonly_tools=frozenset({"web_fetch_exa"}),
        bypass_internal_hitl=True,
    )

    registry = CitationRegistry()
    runtime = _make_runtime(registry)

    result = await tool.coroutine(
        runtime=runtime, url="https://example.com/fetched-page"
    )

    assert isinstance(result, Command)
    updated_registry = result.update.get("citation_registry")
    assert updated_registry is not None
    assert len(updated_registry.by_n) == 1
    entry = updated_registry.resolve(1)
    assert entry.source_type == CitationSourceType.WEB_RESULT
    assert entry.locator["url"] == "https://example.com/fetched-page"


@pytest.mark.asyncio
async def test_mcp_http_tool_no_citations_for_non_exa_tool(monkeypatch) -> None:
    """Non-Exa MCP tools should return plain string, no Command."""
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
        _create_mcp_tool_from_definition_http,
    )

    tool_def = {
        "name": "list_issues",
        "description": "List Linear issues",
        "input_schema": {
            "type": "object",
            "properties": {"team_id": {"type": "string"}},
        },
    }

    fake_result = "Issue 1: https://linear.app/issue/LIN-1"

    class _FakeStream:
        async def __aenter__(self):
            return (None, None, None)

        async def __aexit__(self, *args):
            return False

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def initialize(self):
            pass

        async def call_tool(self, name, arguments):
            resp = MagicMock()
            content_item = MagicMock()
            content_item.text = fake_result
            resp.content = [content_item]
            return resp

    import app.agents.chat.multi_agent_chat.shared.tools.mcp.tool as mcp_mod

    monkeypatch.setattr(
        mcp_mod, "streamablehttp_client", lambda *a, **kw: _FakeStream()
    )
    monkeypatch.setattr(mcp_mod, "ClientSession", lambda *a, **kw: _FakeSession())

    tool = await _create_mcp_tool_from_definition_http(
        url="https://api.linear.app/mcp",
        headers={"Authorization": "Bearer fake"},
        tool_def=tool_def,
        connector_name="Linear",
        connector_id=2,
        readonly_tools=frozenset({"list_issues"}),
        bypass_internal_hitl=True,
    )

    registry = CitationRegistry()
    runtime = _make_runtime(registry)

    result = await tool.coroutine(runtime=runtime, team_id="ENG")

    # Non-citable tool returns plain string, not Command.
    assert isinstance(result, str)
    assert len(registry.by_n) == 0


@pytest.mark.asyncio
async def test_mcp_http_tool_no_runtime_returns_string(monkeypatch) -> None:
    """Without runtime, even Exa tools return plain string (no citation path)."""
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
        _create_mcp_tool_from_definition_http,
    )

    tool_def = {
        "name": "web_search_exa",
        "description": "Search the web",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
    }

    fake_result = "https://example.com/result"

    class _FakeStream:
        async def __aenter__(self):
            return (None, None, None)

        async def __aexit__(self, *args):
            return False

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def initialize(self):
            pass

        async def call_tool(self, name, arguments):
            resp = MagicMock()
            content_item = MagicMock()
            content_item.text = fake_result
            resp.content = [content_item]
            return resp

    import app.agents.chat.multi_agent_chat.shared.tools.mcp.tool as mcp_mod

    monkeypatch.setattr(
        mcp_mod, "streamablehttp_client", lambda *a, **kw: _FakeStream()
    )
    monkeypatch.setattr(mcp_mod, "ClientSession", lambda *a, **kw: _FakeSession())

    tool = await _create_mcp_tool_from_definition_http(
        url="https://mcp.exa.ai/mcp",
        headers={"x-api-key": "fake"},
        tool_def=tool_def,
        connector_name="Exa",
        connector_id=1,
        readonly_tools=frozenset({"web_search_exa"}),
        bypass_internal_hitl=True,
    )

    # No runtime — should return plain string.
    result = await tool.coroutine(query="test")

    assert isinstance(result, str)
    assert "https://example.com/result" in result
