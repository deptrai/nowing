"""Shared helpers for direct MCP write-back automation actions."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector, SearchSourceConnectorType

PROVIDER_TO_CONNECTOR_TYPE: dict[str, SearchSourceConnectorType] = {
    "notion": SearchSourceConnectorType.NOTION_CONNECTOR,
    "linear": SearchSourceConnectorType.LINEAR_CONNECTOR,
    "jira": SearchSourceConnectorType.JIRA_CONNECTOR,
    "slack": SearchSourceConnectorType.SLACK_CONNECTOR,
}

PROVIDER_TO_SERVICE_KEY: dict[str, str] = {
    "notion": "notion",
    "linear": "linear",
    "jira": "jira",
    "slack": "slack",
}

CREATE_TOOL_NAMES: dict[str, list[str]] = {
    "notion": ["notion-create-pages", "create-pages"],
    "linear": ["save_issue"],
    "jira": ["createJiraIssue"],
    "slack": ["send_message", "slack_send_message"],
}

UPDATE_TOOL_NAMES: dict[str, list[str]] = {
    "notion": ["notion-update-page", "update-page"],
    "linear": ["save_issue"],
    "jira": ["editJiraIssue"],
    "slack": ["send_message", "slack_send_message"],
}


def _connector_type_value(value: SearchSourceConnectorType | str) -> str:
    return value.value if isinstance(value, Enum) else str(value)


def _provider_connector_type(provider: str) -> SearchSourceConnectorType:
    try:
        return PROVIDER_TO_CONNECTOR_TYPE[provider]
    except KeyError as exc:
        raise ValueError(f"Unknown write-back provider: {provider}") from exc


async def _default_load_mcp_tools(
    session: AsyncSession,
    workspace_id: int,
    *,
    bypass_internal_hitl: bool = True,
) -> list[Any]:
    from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import load_mcp_tools

    return await load_mcp_tools(
        session,
        workspace_id,
        bypass_internal_hitl=bypass_internal_hitl,
    )


def _config(connector: SearchSourceConnector) -> dict[str, Any]:
    return connector.config or {}


async def resolve_connector(
    session: AsyncSession | None,
    workspace_id: int,
    provider: str,
    connector_name: str | None = None,
    candidates: list[Any] | None = None,
) -> SearchSourceConnector:
    """Find the single MCP connector of the requested type for this workspace.

    ``candidates`` is accepted for test injection; when ``None`` the workspace's
    connectors are queried from the database.
    """
    target_ct = _provider_connector_type(provider)
    target_value = _connector_type_value(target_ct)

    if candidates is None:
        if session is None:
            raise RuntimeError("No database session available to resolve connector")
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.workspace_id == workspace_id,
                SearchSourceConnector.connector_type == target_ct,
                cast(SearchSourceConnector.config, JSONB).has_key("server_config"),
            )
        )
        connectors = list(result.scalars())
    else:
        connectors = candidates

    matches: list[Any] = []
    for connector in connectors:
        cfg = _config(connector)
        server_config = cfg.get("server_config")
        if server_config is None or not isinstance(server_config, dict):
            continue
        ct = _connector_type_value(connector.connector_type)
        if ct != target_value:
            continue
        if connector_name is not None and connector.name != connector_name:
            continue
        matches.append(connector)

    if not matches:
        detail = f" named '{connector_name}'" if connector_name else ""
        raise RuntimeError(
            f"No {provider} MCP connector configured with server_config{detail}"
        )

    if len(matches) > 1 and connector_name is None:
        names = [c.name for c in matches]
        raise RuntimeError(
            f"Multiple {provider} connectors found: {names}; provide connector_name"
        )

    selected = matches[0]
    # Check auth only on the connector we actually selected, so an unrelated
    # expired same-type connector cannot block a healthy, explicitly-named one.
    if _config(selected).get("auth_expired"):
        raise RuntimeError(
            f"The {provider} connector '{selected.name}' authentication expired. "
            "Please re-authenticate the connector in your settings."
        )
    return selected


async def load_tools_for_connector(
    session: AsyncSession,
    workspace_id: int,
    *,
    load_mcp_tools: Callable[[AsyncSession, int], Awaitable[list[Any]]] | None = None,
) -> list[Any]:
    """Load MCP tools for the workspace, bypassing internal HITL approvals."""
    loader = load_mcp_tools or _default_load_mcp_tools
    return await loader(
        session=session,
        workspace_id=workspace_id,
        bypass_internal_hitl=True,
    )


def _tool_connector_id(tool: Any) -> int | None:
    return (tool.metadata or {}).get("mcp_connector_id")


def _tool_original_name(tool: Any) -> str | None:
    return (tool.metadata or {}).get("mcp_original_tool_name")


def _tool_input_schema(tool: Any) -> dict[str, Any]:
    return (tool.metadata or {}).get("mcp_input_schema") or {
        "type": "object",
        "properties": {},
    }


def _service_key_for_provider(provider: str) -> str | None:
    return PROVIDER_TO_SERVICE_KEY.get(provider)


def _strip_prefix(name: str, connector_id: int, provider: str) -> str:
    service_key = _service_key_for_provider(provider)
    if service_key:
        prefix = f"{service_key}_{connector_id}_"
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def select_write_tool(
    tools: list[Any],
    connector_id: int,
    provider: str,
    object_id: str | None = None,
) -> Any:
    """Pick the MCP tool that implements create or update for this provider."""
    create_names = CREATE_TOOL_NAMES[provider]
    update_names = UPDATE_TOOL_NAMES[provider]

    names = update_names + create_names if object_id else create_names + update_names

    def matches(tool: Any) -> bool:
        if _tool_connector_id(tool) != connector_id:
            return False
        original = _tool_original_name(tool)
        if original in names:
            return True
        bare = _strip_prefix(tool.name, connector_id, provider)
        return bare in names

    selected: Any | None = None
    for tool in tools:
        if matches(tool):
            selected = tool
            break

    if selected is None:
        # Fallback: if exactly one tool belongs to the target connector, use it.
        # Mainly exercised by unit tests using fake tools without the exact MCP
        # original names; production servers should advertise known names.
        connector_tools = [t for t in tools if _tool_connector_id(t) == connector_id]
        if len(connector_tools) == 1:
            selected = connector_tools[0]

    if selected is None:
        raise RuntimeError(
            f"No MCP write tool found for {provider} on connector {connector_id}"
        )

    # Update requested but only a create tool is advertised → refuse rather than
    # silently create a duplicate. Providers whose update tool == create tool
    # (e.g. Slack) are create-only by design and never trip this.
    if object_id:
        resolved = _tool_original_name(selected) or _strip_prefix(
            selected.name, connector_id, provider
        )
        if resolved in create_names and resolved not in update_names:
            raise RuntimeError(
                f"Update requested (object_id set) for {provider}, but only a create "
                f"tool ('{resolved}') is available; refusing to create a duplicate."
            )

    return selected


def _set_if_present(args: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        args[key] = value


def _set_from_properties(
    args: dict[str, Any],
    properties: dict[str, Any],
    source: dict[str, Any],
    key: str,
    *aliases: str,
) -> None:
    """Set ``args[key]`` from ``source[key]`` if ``key`` or an alias is a schema property."""
    for candidate in (key, *aliases):
        if candidate in properties:
            if key not in source:
                continue
            args[candidate] = source[key]
            return


def build_tool_args(
    tool: Any,
    params: Any,
    provider: str,
    connector: Any | None = None,
    cloud_id: str | None = None,
) -> dict[str, Any]:
    """Map a typed Pydantic params model to the MCP tool's input schema."""
    schema = _tool_input_schema(tool)
    properties = schema.get("properties") or {}
    data = params.model_dump(exclude={"connector_name", "object_id"})

    if not properties:
        # Generic / test tool with no declared schema — pass params directly.
        return data

    args: dict[str, Any] = {}

    if provider == "notion":
        title = data.get("title", "")
        content = data.get("content") or ""
        object_id = getattr(params, "object_id", None)

        if "pages" in properties:
            page: dict[str, Any] = {"title": title, "content": content}
            parent_page_id = data.get("parent_page_id")
            if parent_page_id:
                page["parent"] = {"page_id": parent_page_id}
            args["pages"] = [page]
        elif "page_id" in properties and object_id:
            args["page_id"] = object_id
            if "properties" in properties:
                args["properties"] = {"title": [{"text": {"content": title}}]}
            elif "data" in properties:
                args["data"] = content
            else:
                args["title"] = title
                args["content"] = content
        else:
            _set_from_properties(args, properties, data, "title")
            _set_from_properties(args, properties, data, "content")

    elif provider == "linear":
        _set_from_properties(args, properties, data, "title")
        _set_from_properties(args, properties, data, "description")
        _set_from_properties(args, properties, data, "team_id", "team", "teamId")
        _set_from_properties(args, properties, data, "state")
        object_id = getattr(params, "object_id", None)
        if object_id and "id" in properties:
            args["id"] = object_id

    elif provider == "jira":
        object_id = getattr(params, "object_id", None)
        if "cloudId" in properties:
            args["cloudId"] = cloud_id
        if object_id:
            if "issueIdOrKey" in properties:
                args["issueIdOrKey"] = object_id
            if "summary" in properties:
                args["summary"] = data.get("summary", "")
            if "description" in properties:
                desc = data.get("description")
                if desc is not None:
                    args["description"] = desc
            if "additional_fields" in properties and "additional_fields" in data:
                args["additional_fields"] = data["additional_fields"]
        else:
            if "projectKey" in properties:
                args["projectKey"] = data.get("project_key", "")
            if "summary" in properties:
                args["summary"] = data.get("summary", "")
            if "description" in properties:
                desc = data.get("description")
                if desc is not None:
                    args["description"] = desc
            if "issueTypeName" in properties:
                args["issueTypeName"] = data.get("issue_type", "Task")
            elif "issueType" in properties:
                args["issueType"] = data.get("issue_type", "Task")
            if "additional_fields" in properties and "additional_fields" in data:
                args["additional_fields"] = data["additional_fields"]

    elif provider == "slack":
        _set_from_properties(args, properties, data, "channel")
        _set_from_properties(args, properties, data, "text")
        _set_from_properties(args, properties, data, "thread_ts", "threadTs")

    # Drop null values to avoid passing empty optional keys.
    return {k: v for k, v in args.items() if v is not None}


def parse_mcp_result(
    result_str: str | Any,
    provider: str,
    connector_id: int = 0,
    connector_name: str = "",
) -> dict[str, Any]:
    """Normalize an MCP tool response into a JSON-serializable reference dict."""
    if isinstance(result_str, str):
        if result_str.startswith("Error:") or result_str.startswith(
            "Tool call rejected"
        ):
            raise RuntimeError(f"MCP tool failed: {result_str}")

        try:
            parsed = json.loads(result_str)
        except json.JSONDecodeError:
            parsed = {"text": result_str}
    else:
        parsed = result_str

    if isinstance(parsed, dict):
        if parsed.get("error"):
            raise RuntimeError(f"MCP tool failed: {parsed['error']}")
    else:
        parsed = {"text": parsed}

    object_id: str | None = None
    url: str | None = None

    if isinstance(parsed, dict):
        url = (
            parsed.get("url")
            or parsed.get("page_url")
            or parsed.get("issue_url")
            or parsed.get("permalink")
            or parsed.get("webUrl")
            or parsed.get("href")
        )

        if provider == "notion":
            object_id = parsed.get("id") or parsed.get("page_id")
        elif provider == "linear":
            object_id = parsed.get("id") or parsed.get("identifier")
        elif provider == "jira":
            object_id = parsed.get("key") or parsed.get("id")
        elif provider == "slack":
            object_id = parsed.get("ts") or parsed.get("message_ts") or parsed.get("id")
        else:
            object_id = parsed.get("id")

    return {
        "provider": provider,
        "connector_id": connector_id,
        "connector_name": connector_name,
        "object_id": object_id or "",
        "url": url or "",
        "raw": parsed,
    }


async def resolve_jira_cloud_id(
    session: AsyncSession | None,
    connector: Any,
    *,
    fetch_resources: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None,
) -> str:
    """Return the Atlassian cloudId for a Jira connector.

    ``fetch_resources`` is accepted for test injection. The default implementation
    calls the ``getAccessibleAtlassianResources`` MCP tool.
    """
    cfg = _config(connector)
    cloud_id = cfg.get("cloud_id")
    if cloud_id:
        return str(cloud_id)

    if fetch_resources is not None:
        resources = await fetch_resources()
    else:
        if session is None:
            raise RuntimeError("No database session available to resolve Jira cloudId")
        tools = await _default_load_mcp_tools(session, connector.workspace_id)
        tool = next(
            (
                t
                for t in tools
                if _tool_connector_id(t) == connector.id
                and _tool_original_name(t) == "getAccessibleAtlassianResources"
            ),
            None,
        )
        if tool is None:
            raise RuntimeError(
                "Jira connector missing cloud_id and getAccessibleAtlassianResources tool"
            )
        result_str = await tool.coroutine()
        try:
            resources = json.loads(result_str)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Invalid Jira resources response: {result_str}"
            ) from exc

    if not resources:
        raise RuntimeError("No Atlassian resources found for Jira connector")

    first = resources[0]
    if isinstance(first, dict):
        cloud_id = first.get("id") or first.get("cloudId")
        if not cloud_id:
            raise RuntimeError(
                "Atlassian resource is missing an id/cloudId for the Jira connector"
            )
        return str(cloud_id)
    if not first:
        raise RuntimeError("No Atlassian cloudId found for Jira connector")
    return str(first)


async def execute_write_back(
    provider: str,
    params_model: type[Any],
    ctx: Any,
    params: dict[str, Any],
    *,
    tool: Any | None = None,
    connectors: list[Any] | None = None,
    load_mcp_tools: Callable[[AsyncSession, int], Awaitable[list[Any]]] | None = None,
) -> dict[str, Any]:
    """Generic write-back flow used by each provider-specific action."""
    validated = params_model.model_validate(params)

    if tool is None:
        connector = await resolve_connector(
            ctx.session,
            ctx.workspace_id,
            provider,
            connector_name=getattr(validated, "connector_name", None),
            candidates=connectors,
        )
        tools = await load_tools_for_connector(
            ctx.session,
            ctx.workspace_id,
            load_mcp_tools=load_mcp_tools,
        )
        tool = select_write_tool(
            tools,
            connector.id,
            provider,
            object_id=getattr(validated, "object_id", None),
        )

        cloud_id: str | None = None
        if provider == "jira":
            schema = _tool_input_schema(tool)
            if "cloudId" in schema.get("properties", {}):
                cloud_id = await resolve_jira_cloud_id(ctx.session, connector)

        args = build_tool_args(
            tool,
            validated,
            provider,
            connector=connector,
            cloud_id=cloud_id,
        )
        result_str = await tool.coroutine(**args)
        return parse_mcp_result(
            result_str,
            provider,
            connector.id,
            connector.name or "",
        )

    # Test-injected tool path: skip DB resolution and use the tool directly.
    args = build_tool_args(tool, validated, provider, connector=None, cloud_id=None)
    result_str = await tool.coroutine(**args)
    return parse_mcp_result(
        result_str,
        provider,
        _tool_connector_id(tool) or 0,
        (tool.metadata or {}).get("mcp_connector_name") or "",
    )
