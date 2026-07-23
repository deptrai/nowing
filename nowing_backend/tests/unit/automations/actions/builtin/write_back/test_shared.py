"""Red-phase unit tests for shared write-back helpers (Story 6.4)."""

from __future__ import annotations

import importlib
import json
from types import SimpleNamespace
from typing import Any

import pytest

pytestmark = pytest.mark.unit


def _load_shared():
    """Lazy-load the shared helper module; fails until Story 6.4 is implemented."""
    return importlib.import_module("app.automations.actions.builtin.write_back.shared")


def _make_tool(
    *,
    name: str,
    connector_id: int,
    original_name: str | None = None,
    schema: dict[str, Any] | None = None,
):
    async def _coroutine(**_kwargs: Any) -> str:
        return json.dumps({"id": "obj-123", "url": "https://example.com/obj-123"})

    return SimpleNamespace(
        name=name,
        coroutine=_coroutine,
        metadata={
            "mcp_connector_id": connector_id,
            "mcp_connector_name": "Test Connector",
            "mcp_original_tool_name": original_name or name,
            "mcp_input_schema": schema or {"type": "object", "properties": {}},
        },
    )



async def test_resolve_connector_finds_single_match_by_type():
    """When exactly one MCP connector of the target type exists, return it."""
    shared = _load_shared()
    connector = SimpleNamespace(
        id=1,
        name="Notion",
        connector_type="NOTION_CONNECTOR",
        config={"server_config": {"transport": "stdio", "command": "mcp-server"}},
    )
    result = await shared.resolve_connector(
        session=None,
        workspace_id=42,
        provider="notion",
        connector_name=None,
        candidates=[connector],
    )
    assert result.id == 1
    assert result.name == "Notion"



async def test_resolve_connector_requires_name_when_multiple():
    """Multiple connectors of the same type require explicit connector_name."""
    shared = _load_shared()
    candidates = [
        SimpleNamespace(
            id=1,
            name="Notion A",
            connector_type="NOTION_CONNECTOR",
            config={"server_config": {}},
        ),
        SimpleNamespace(
            id=2,
            name="Notion B",
            connector_type="NOTION_CONNECTOR",
            config={"server_config": {}},
        ),
    ]
    with pytest.raises(RuntimeError, match="Multiple notion connectors found"):
        await shared.resolve_connector(
            session=None,
            workspace_id=42,
            provider="notion",
            connector_name=None,
            candidates=candidates,
        )



async def test_resolve_connector_fails_when_missing_server_config():
    """A connector without server_config is not a valid MCP write target."""
    shared = _load_shared()
    connector = SimpleNamespace(
        id=1,
        name="Notion OAuth",
        connector_type="NOTION_CONNECTOR",
        config={},
    )
    with pytest.raises(RuntimeError, match="server_config"):
        await shared.resolve_connector(
            session=None,
            workspace_id=42,
            provider="notion",
            connector_name=None,
            candidates=[connector],
        )



async def test_select_tool_matches_by_connector_id_and_original_name():
    """Tool lookup must handle multi-account prefixing."""
    shared = _load_shared()
    tools = [
        _make_tool(name="notion_7_create-pages", connector_id=7, original_name="create-pages"),
        _make_tool(name="notion_8_create-pages", connector_id=8, original_name="create-pages"),
    ]
    selected = shared.select_write_tool(
        tools=tools,
        connector_id=8,
        provider="notion",
    )
    assert selected.name == "notion_8_create-pages"



async def test_select_tool_falls_back_to_known_aliases():
    """If the unprefixed original name isn't found, try known aliases."""
    shared = _load_shared()
    tools = [
        _make_tool(
            name="notion_7_notion-create-pages",
            connector_id=7,
            original_name="notion-create-pages",
        ),
    ]
    selected = shared.select_write_tool(
        tools=tools,
        connector_id=7,
        provider="notion",
    )
    assert selected is not None



async def test_jira_cloud_id_uses_config_value_first():
    """Jira cloudId resolution prefers connector.config.cloud_id."""
    shared = _load_shared()
    connector = SimpleNamespace(config={"cloud_id": "cloud-abc"})
    cloud_id = await shared.resolve_jira_cloud_id(session=None, connector=connector)
    assert cloud_id == "cloud-abc"



async def test_jira_cloud_id_calls_resources_api_when_missing():
    """When cloud_id is absent, fetch accessible Atlassian resources via MCP."""
    shared = _load_shared()
    connector = SimpleNamespace(config={})

    async def _fake_call() -> list[dict[str, str]]:
        return [{"id": "cloud-xyz", "name": "acme"}]

    cloud_id = await shared.resolve_jira_cloud_id(
        session=None,
        connector=connector,
        fetch_resources=_fake_call,
    )
    assert cloud_id == "cloud-xyz"



async def test_parse_mcp_result_extracts_object_id_and_url():
    """Successful MCP tool responses are parsed into a normalized reference dict."""
    shared = _load_shared()
    raw = json.dumps({"id": "page-123", "url": "https://notion.so/page-123"})
    result = shared.parse_mcp_result(raw, provider="notion")
    assert result["object_id"] == "page-123"
    assert result["url"] == "https://notion.so/page-123"
    assert result["provider"] == "notion"



async def test_parse_mcp_result_raises_on_error_string():
    """Error strings returned by the MCP tool wrapper fail the step clearly."""
    shared = _load_shared()
    with pytest.raises(RuntimeError, match="MCP tool .* failed"):
        shared.parse_mcp_result(
            "Error: MCP tool 'create-pages' execution failed",
            provider="notion",
        )



async def test_bypass_internal_hitl_is_passed_to_load_mcp_tools():
    """Automation handlers never prompt for human approval."""
    shared = _load_shared()
    called_with: dict[str, Any] = {}

    async def _fake_load(*, bypass_internal_hitl: bool, **_kwargs: Any) -> list[Any]:
        called_with["bypass_internal_hitl"] = bypass_internal_hitl
        return []

    await shared.load_tools_for_connector(
        session=None,
        workspace_id=42,
        load_mcp_tools=_fake_load,
    )
    assert called_with["bypass_internal_hitl"] is True
