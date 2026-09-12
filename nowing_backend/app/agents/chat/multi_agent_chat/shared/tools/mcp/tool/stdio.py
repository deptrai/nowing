"""Stdio-transport MCP tool factory and loader.

Builds LangChain tools from local process-based MCP servers
(``command``, ``args``, ``env``) discovered via :class:`MCPClient`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.tools import StructuredTool

from app.agents.chat.multi_agent_chat.shared.middleware.dedup_tool_calls import (
    dedup_key_full_args,
)
from app.agents.chat.multi_agent_chat.shared.tools.hitl import request_approval
from app.agents.chat.multi_agent_chat.shared.tools.mcp.client import MCPClient
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool._helpers import (
    _TOOL_CALL_MAX_RETRIES,
    _TOOL_CALL_RETRY_DELAY,
    _create_dynamic_input_model_from_schema,
    _unpack_synthetic_input_data,
)

logger = logging.getLogger(__name__)


async def _create_mcp_tool_from_definition_stdio(
    tool_def: dict[str, Any],
    mcp_client: MCPClient,
    *,
    connector_name: str = "",
    connector_id: int | None = None,
    trusted_tools: list[str] | None = None,
    bypass_internal_hitl: bool = False,
) -> StructuredTool:
    """Create a LangChain tool from an MCP tool definition (stdio transport).

    Set ``bypass_internal_hitl=True`` when an outer ``HumanInTheLoopMiddleware``
    already gates the tool, otherwise the body's ``request_approval()`` is the
    sole HITL gate (single-agent path).
    """
    tool_name = tool_def.get("name", "unnamed_tool")
    raw_description = tool_def.get("description", "No description provided")
    tool_description = (
        f"[MCP server: {connector_name}] {raw_description}"
        if connector_name
        else raw_description
    )
    input_schema = tool_def.get("input_schema", {"type": "object", "properties": {}})

    logger.debug("MCP tool '%s' input schema: %s", tool_name, input_schema)

    input_model = _create_dynamic_input_model_from_schema(tool_name, input_schema)

    async def mcp_tool_call(**kwargs) -> str:
        """Execute the MCP tool call via the client with retry support."""
        logger.debug("MCP tool '%s' called", tool_name)

        if bypass_internal_hitl:
            call_kwargs = _unpack_synthetic_input_data(
                {k: v for k, v in kwargs.items() if v is not None}
            )
        else:
            # Outside try/except so ``GraphInterrupt`` propagates to LangGraph.
            hitl_result = request_approval(
                action_type="mcp_tool_call",
                tool_name=tool_name,
                params=kwargs,
                context={
                    "mcp_server": connector_name,
                    "tool_description": raw_description,
                    "mcp_transport": "stdio",
                    "mcp_connector_id": connector_id,
                },
                trusted_tools=trusted_tools,
            )
            if hitl_result.rejected:
                return "Tool call rejected by user."
            call_kwargs = _unpack_synthetic_input_data(
                {k: v for k, v in hitl_result.params.items() if v is not None}
            )

        last_error: Exception | None = None
        for attempt in range(_TOOL_CALL_MAX_RETRIES):
            try:
                async with mcp_client.connect():
                    result = await mcp_client.call_tool(tool_name, call_kwargs)
                    return str(result)
            except Exception as e:
                last_error = e
                if attempt < _TOOL_CALL_MAX_RETRIES - 1:
                    delay = _TOOL_CALL_RETRY_DELAY * (2**attempt)
                    logger.warning(
                        "MCP tool '%s' failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        tool_name,
                        attempt + 1,
                        _TOOL_CALL_MAX_RETRIES,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "MCP tool '%s' failed after %d attempts: %s",
                        tool_name,
                        _TOOL_CALL_MAX_RETRIES,
                        e,
                        exc_info=True,
                    )

        return f"Error: MCP tool '{tool_name}' failed after {_TOOL_CALL_MAX_RETRIES} attempts: {last_error!s}"

    tool = StructuredTool(
        name=tool_name,
        description=tool_description,
        coroutine=mcp_tool_call,
        args_schema=input_model,
        metadata={
            "mcp_input_schema": input_schema,
            "mcp_transport": "stdio",
            "mcp_connector_name": connector_name or None,
            "mcp_connector_id": connector_id,
            "mcp_is_generic": True,
            "hitl": True,
            # Full-args hash: shared identifiers (cloudId, workspaceId, …)
            # would otherwise collapse legitimate batches.
            "dedup_key": dedup_key_full_args,
        },
    )

    logger.debug("Created MCP tool (stdio): '%s'", tool_name)
    return tool


async def _load_stdio_mcp_tools(
    connector_id: int,
    connector_name: str,
    server_config: dict[str, Any],
    trusted_tools: list[str] | None = None,
    *,
    bypass_internal_hitl: bool = False,
) -> list[StructuredTool]:
    """Load tools from a stdio-based MCP server."""
    tools: list[StructuredTool] = []

    command = server_config.get("command")
    if not command or not isinstance(command, str):
        logger.warning(
            "MCP connector %d (name: '%s') missing or invalid command field, skipping",
            connector_id,
            connector_name,
        )
        return tools

    args = server_config.get("args", [])
    if not isinstance(args, list):
        logger.warning(
            "MCP connector %d (name: '%s') has invalid args field (must be list), skipping",
            connector_id,
            connector_name,
        )
        return tools

    env = server_config.get("env", {})
    if not isinstance(env, dict):
        logger.warning(
            "MCP connector %d (name: '%s') has invalid env field (must be dict), skipping",
            connector_id,
            connector_name,
        )
        return tools

    mcp_client = MCPClient(command, args, env)

    async with mcp_client.connect():
        tool_definitions = await mcp_client.list_tools()

        logger.info(
            "Discovered %d tools from stdio MCP server '%s' (connector %d)",
            len(tool_definitions),
            command,
            connector_id,
        )

    for tool_def in tool_definitions:
        try:
            tool = await _create_mcp_tool_from_definition_stdio(
                tool_def,
                mcp_client,
                connector_name=connector_name,
                connector_id=connector_id,
                trusted_tools=trusted_tools,
                bypass_internal_hitl=bypass_internal_hitl,
            )
            tools.append(tool)
        except Exception as e:
            logger.exception(
                "Failed to create tool '%s' from connector %d: %s",
                tool_def.get("name"),
                connector_id,
                e,
            )

    return tools
