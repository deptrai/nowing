"""HTTP-transport MCP tool factory and loader.

Builds LangChain tools from remote HTTP-based MCP servers
(``streamable-http``/``http``/``sse`` — ``url``, ``headers``), including the
401 → token-refresh recovery path and WEB_RESULT citation minting.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.agents.chat.multi_agent_chat.shared.citations import load_registry
from app.agents.chat.multi_agent_chat.shared.citations.models import CitationSourceType
from app.agents.chat.multi_agent_chat.shared.middleware.dedup_tool_calls import (
    dedup_key_full_args,
)
from app.agents.chat.multi_agent_chat.shared.tools.hitl import request_approval
from app.agents.chat.multi_agent_chat.shared.tools.mcp.cache import (
    CachedMCPTools,
    write_cached_tools,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool._helpers import (
    _create_dynamic_input_model_from_schema,
    _extract_citable_urls,
    _is_auth_error,
    _unpack_synthetic_input_data,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool.oauth import (
    _force_refresh_and_get_headers,
    _mark_connector_auth_expired,
)
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

logger = logging.getLogger(__name__)


async def _create_mcp_tool_from_definition_http(
    tool_def: dict[str, Any],
    url: str,
    headers: dict[str, str],
    *,
    connector_name: str = "",
    connector_id: int | None = None,
    trusted_tools: list[str] | None = None,
    readonly_tools: frozenset[str] | None = None,
    tool_name_prefix: str | None = None,
    is_generic_mcp: bool = False,
    bypass_internal_hitl: bool = False,
) -> StructuredTool:
    """Create a LangChain tool from an MCP tool definition (HTTP transport).

    Write tools are wrapped with HITL approval; read-only tools (listed in
    ``readonly_tools``) execute immediately without user confirmation. Set
    ``bypass_internal_hitl=True`` when an outer ``HumanInTheLoopMiddleware``
    already gates the tool.

    When ``tool_name_prefix`` is set (multi-account disambiguation), the
    tool exposed to the LLM gets a prefixed name (e.g. ``linear_25_list_issues``)
    but the actual MCP ``call_tool`` still uses the original name.
    """
    original_tool_name = tool_def.get("name", "unnamed_tool")
    raw_description = tool_def.get("description", "No description provided")
    input_schema = tool_def.get("input_schema", {"type": "object", "properties": {}})
    is_readonly = readonly_tools is not None and original_tool_name in readonly_tools

    exposed_name = (
        f"{tool_name_prefix}_{original_tool_name}"
        if tool_name_prefix
        else original_tool_name
    )
    if tool_name_prefix:
        tool_description = f"[Account: {connector_name}] {raw_description}"
    elif is_generic_mcp and connector_name:
        tool_description = f"[MCP server: {connector_name}] {raw_description}"
    else:
        tool_description = raw_description

    logger.debug("MCP HTTP tool '%s' input schema: %s", exposed_name, input_schema)

    input_model = _create_dynamic_input_model_from_schema(exposed_name, input_schema)

    async def _do_mcp_call(
        call_headers: dict[str, str],
        call_kwargs: dict[str, Any],
        timeout: float = 60.0,
    ) -> str:
        """Execute a single MCP HTTP call with the given headers."""
        call_start = time.perf_counter()
        async with (
            streamablehttp_client(url, headers=call_headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            init_start = time.perf_counter()
            await session.initialize()
            init_elapsed = time.perf_counter() - init_start

            tool_start = time.perf_counter()
            response = await asyncio.wait_for(
                session.call_tool(original_tool_name, arguments=call_kwargs),
                timeout=timeout,
            )
            tool_elapsed = time.perf_counter() - tool_start

            result = []
            for content in response.content:
                if hasattr(content, "text"):
                    result.append(content.text)
                elif hasattr(content, "data"):
                    result.append(str(content.data))
                else:
                    result.append(str(content))

            payload = "\n".join(result) if result else ""

        _perf_log.info(
            "[mcp_http_call] connector=%s tool=%s init=%.3fs call=%.3fs total=%.3fs out_chars=%d",
            connector_id,
            original_tool_name,
            init_elapsed,
            tool_elapsed,
            time.perf_counter() - call_start,
            len(payload),
        )
        return payload

    async def mcp_http_tool_call(
        runtime: ToolRuntime | None = None, **kwargs
    ) -> str | Command:
        """Execute the MCP tool call via HTTP transport.

        When ``runtime`` is available and the tool produces citable web URLs
        (e.g. ``web_search_exa``, ``web_fetch_exa``), each URL is registered
        as a ``WEB_RESULT`` citation and the result is returned as a
        ``Command`` with the updated registry — mirroring how capability
        tools in ``access/agent.py`` mint citations.
        """
        logger.debug("MCP HTTP tool '%s' called", exposed_name)

        if is_readonly or bypass_internal_hitl:
            call_kwargs = _unpack_synthetic_input_data(
                {k: v for k, v in kwargs.items() if v is not None}
            )
        else:
            hitl_result = request_approval(
                action_type="mcp_tool_call",
                tool_name=exposed_name,
                params=kwargs,
                context={
                    "mcp_server": connector_name,
                    "tool_description": raw_description,
                    "mcp_transport": "http",
                    "mcp_connector_id": connector_id,
                },
                trusted_tools=trusted_tools,
            )
            if hitl_result.rejected:
                return "Tool call rejected by user."
            call_kwargs = _unpack_synthetic_input_data(
                {k: v for k, v in hitl_result.params.items() if v is not None}
            )

        def _with_citations(result_str: str) -> str | Command:
            """Register WEB_RESULT citations for citable MCP tools, or return as-is."""
            if runtime is None:
                return result_str
            pairs = _extract_citable_urls(original_tool_name, result_str, call_kwargs)
            if not pairs:
                return result_str
            registry = load_registry(getattr(runtime, "state", None))
            for url, title in pairs:
                registry.register(
                    CitationSourceType.WEB_RESULT,
                    {"url": url},
                    {"title": title} if title else {},
                )
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=result_str,
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                    "citation_registry": registry,
                }
            )

        try:
            result_str = await _do_mcp_call(headers, call_kwargs)
            logger.debug(
                "MCP HTTP tool '%s' succeeded (len=%d)", exposed_name, len(result_str)
            )
            return _with_citations(result_str)

        except Exception as first_err:  # HTTP tool execution failure; check 401 recovery or return error
            if not _is_auth_error(first_err) or connector_id is None:
                logger.exception(
                    "MCP HTTP tool '%s' execution failed: %s", exposed_name, first_err
                )
                return f"Error: MCP HTTP tool '{exposed_name}' execution failed: {first_err!s}"

            logger.warning(
                "MCP HTTP tool '%s' got 401 — attempting token refresh for connector %s",
                exposed_name,
                connector_id,
            )
            fresh_headers = await _force_refresh_and_get_headers(connector_id)
            if fresh_headers is None:
                await _mark_connector_auth_expired(connector_id)
                return (
                    f"Error: MCP tool '{exposed_name}' authentication expired. "
                    "Please re-authenticate the connector in your settings."
                )

            try:
                result_str = await _do_mcp_call(fresh_headers, call_kwargs)
                logger.info(
                    "MCP HTTP tool '%s' succeeded after 401 recovery",
                    exposed_name,
                )
                return _with_citations(result_str)
            except Exception as retry_err:  # HTTP tool execution retry failure; return error message
                logger.exception(
                    "MCP HTTP tool '%s' still failing after token refresh: %s",
                    exposed_name,
                    retry_err,
                )
                if _is_auth_error(retry_err):
                    await _mark_connector_auth_expired(connector_id)
                    return (
                        f"Error: MCP tool '{exposed_name}' authentication expired. "
                        "Please re-authenticate the connector in your settings."
                    )
                return f"Error: MCP HTTP tool '{exposed_name}' execution failed: {retry_err!s}"

    mcp_http_tool_call.__annotations__["runtime"] = ToolRuntime

    tool = StructuredTool(
        name=exposed_name,
        description=tool_description,
        coroutine=mcp_http_tool_call,
        args_schema=input_model,
        metadata={
            "mcp_input_schema": input_schema,
            "mcp_transport": "http",
            "mcp_url": url,
            "mcp_connector_name": connector_name or None,
            "mcp_is_generic": is_generic_mcp,
            "hitl": not is_readonly,
            # Full-args hash: shared identifiers (cloudId, workspaceId, …)
            # would otherwise collapse legitimate batches.
            "dedup_key": dedup_key_full_args,
            "mcp_original_tool_name": original_tool_name,
            "mcp_connector_id": connector_id,
        },
    )

    logger.debug("Created MCP tool (HTTP): '%s'", exposed_name)
    return tool


async def _load_http_mcp_tools(
    connector_id: int,
    connector_name: str,
    server_config: dict[str, Any],
    trusted_tools: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    readonly_tools: frozenset[str] | None = None,
    tool_name_prefix: str | None = None,
    is_generic_mcp: bool = False,
    *,
    bypass_internal_hitl: bool = False,
    cached_tools: CachedMCPTools | None = None,
    connector_type: str | None = None,
) -> list[StructuredTool]:
    """Load tools from an HTTP-based MCP server.

    Args:
        allowed_tools: If non-empty, only tools whose names appear in this
            list are loaded.  Empty/None means load everything (used for
            user-managed generic MCP servers).
        readonly_tools: Tool names that skip HITL approval (read-only operations).
        tool_name_prefix: If set, each tool name is prefixed for multi-account
            disambiguation (e.g. ``linear_25``).
        cached_tools: If provided, skip live discovery and rebuild wrappers
            from the persisted definitions.
        connector_type: The connector_type string (e.g. ``XACTIONS_MCP_CONNECTOR``).
    """
    if connector_type == "XACTIONS_MCP_CONNECTOR":
        from app.agents.chat.multi_agent_chat.shared.tools.mcp.xactions_gateway import (
            create_xactions_meta_tools,
        )

        # XActions meta-tools are built from static Pydantic schemas that
        # mirror the daemon's tool surface.  We never rely on the persisted
        # ``cached_tools`` shortcut here so daemon-side schema changes are
        # picked up on every (re)discovery instead of being masked by a stale
        # cache.
        meta_tools = create_xactions_meta_tools(
            connector_id,
            connector_name,
            server_config,
            trusted_tools=trusted_tools,
            bypass_internal_hitl=bypass_internal_hitl,
        )
        if tool_name_prefix:
            for tool in meta_tools:
                tool.metadata["mcp_original_tool_name"] = tool.name
                tool.name = f"{tool_name_prefix}_{tool.name}"
                if tool.description and not tool.description.startswith("[Account:"):
                    tool.description = f"[Account: {connector_name}] {tool.description}"
        # Persist the current meta-tool surface so operators can inspect what
        # the gateway exposed at discovery time (parity with generic MCP).
        tool_definitions = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": (
                    t.args_schema.model_json_schema() if t.args_schema else {}
                ),
            }
            for t in meta_tools
        ]
        await write_cached_tools(
            connector_id,
            tool_definitions,
            server_name="xactions-meta-gateway",
            server_version="1.0.0",
            transport=server_config.get("transport", "streamable-http"),
        )
        return meta_tools

    tools: list[StructuredTool] = []

    url = server_config.get("url")
    if not url or not isinstance(url, str):
        logger.warning(
            "MCP connector %d (name: '%s') missing or invalid url field, skipping",
            connector_id,
            connector_name,
        )
        return tools

    headers = server_config.get("headers", {})
    if not isinstance(headers, dict):
        logger.warning(
            "MCP connector %d (name: '%s') has invalid headers field (must be dict), skipping",
            connector_id,
            connector_name,
        )
        return tools

    allowed_set = set(allowed_tools) if allowed_tools else None

    async def _discover(
        disc_headers: dict[str, str],
    ) -> tuple[dict[str, str | None], list[dict[str, Any]]]:
        """Connect, initialize, and list tools — returns (serverInfo, tools)."""
        async with (
            streamablehttp_client(url, headers=disc_headers) as (read, write, _),
            ClientSession(read, write) as session,
        ):
            init_result = await session.initialize()
            server_info: dict[str, str | None] = {"name": None, "version": None}
            si = getattr(init_result, "serverInfo", None)
            if si is not None:
                server_info["name"] = getattr(si, "name", None)
                server_info["version"] = getattr(si, "version", None)

            response = await session.list_tools()
            return server_info, [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema
                    if hasattr(tool, "inputSchema")
                    else {},
                }
                for tool in response.tools
            ]

    if cached_tools is not None:
        tool_definitions = [
            {
                "name": td.name,
                "description": td.description,
                "input_schema": td.input_schema,
            }
            for td in cached_tools.tools
        ]
    else:
        try:
            server_info, tool_definitions = await _discover(headers)
        except Exception as first_err:  # HTTP discovery failure; check 401 recovery or re-raise
            if not _is_auth_error(first_err) or connector_id is None:
                logger.exception(
                    "Failed to connect to HTTP MCP server at '%s' (connector %d): %s",
                    url,
                    connector_id,
                    first_err,
                )
                return tools

            logger.warning(
                "HTTP MCP discovery for connector %d got 401 — attempting token refresh",
                connector_id,
            )
            fresh_headers = await _force_refresh_and_get_headers(connector_id)
            if fresh_headers is None:
                await _mark_connector_auth_expired(connector_id)
                logger.error(
                    "HTTP MCP discovery for connector %d: token refresh failed, marking auth_expired",
                    connector_id,
                )
                return tools

            try:
                server_info, tool_definitions = await _discover(fresh_headers)
                headers = fresh_headers
                logger.info(
                    "HTTP MCP discovery for connector %d succeeded after 401 recovery",
                    connector_id,
                )
            except Exception as retry_err:  # HTTP discovery retry failure; return empty tool list
                logger.exception(
                    "HTTP MCP discovery for connector %d still failing after refresh: %s",
                    connector_id,
                    retry_err,
                )
                if _is_auth_error(retry_err):
                    await _mark_connector_auth_expired(connector_id)
                return tools

        await write_cached_tools(
            connector_id,
            tool_definitions,
            server_name=server_info.get("name"),
            server_version=server_info.get("version"),
            transport=server_config.get("transport", "streamable-http"),
        )

    total_discovered = len(tool_definitions)

    if allowed_set:
        filtered = [td for td in tool_definitions if td["name"] in allowed_set]
        if not filtered and total_discovered:
            # The server renamed its tools out from under our allowlist
            # (e.g. Notion's "notion-" prefix rename) — a fully-dead
            # allowlist would silently disable the connector. Load
            # everything instead: renamed tools won't match
            # ``readonly_tools`` either, so every tool stays HITL-gated.
            logger.warning(
                "HTTP MCP server '%s' (connector %d): allowlist matched 0/%d "
                "advertised tools — server likely renamed its tools. "
                "Loading all tools (HITL-gated). Update the registry allowlist: %s",
                url,
                connector_id,
                total_discovered,
                sorted(td["name"] for td in tool_definitions),
            )
        else:
            tool_definitions = filtered
            logger.info(
                "HTTP MCP server '%s' (connector %d): %d/%d tools after allowlist filter",
                url,
                connector_id,
                len(tool_definitions),
                total_discovered,
            )
    else:
        logger.info(
            "Discovered %d tools from HTTP MCP server '%s' (connector %d) — no allowlist, loading all",
            total_discovered,
            url,
            connector_id,
        )

    for tool_def in tool_definitions:
        try:
            tool = await _create_mcp_tool_from_definition_http(
                tool_def,
                url,
                headers,
                connector_name=connector_name,
                connector_id=connector_id,
                trusted_tools=trusted_tools,
                readonly_tools=readonly_tools,
                tool_name_prefix=tool_name_prefix,
                is_generic_mcp=is_generic_mcp,
                bypass_internal_hitl=bypass_internal_hitl,
            )
            tools.append(tool)
        except Exception as e:  # HTTP tool creation failure; skip tool
            logger.exception(
                "Failed to create HTTP tool '%s' from connector %d: %s",
                tool_def.get("name"),
                connector_id,
                e,
            )

    return tools
