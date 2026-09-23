"""MCP Tool Factory.

This package creates LangChain tools from MCP servers using the Model Context Protocol.
Tools are dynamically discovered from MCP servers - no manual configuration needed.

Supports both transport types:
- stdio: Local process-based MCP servers (command, args, env)
- streamable-http/http/sse: Remote HTTP-based MCP servers (url, headers)

All MCP tools are unconditionally gated by HITL (Human-in-the-Loop) approval.
Per the MCP spec: "Clients MUST consider tool annotations to be untrusted unless
they come from trusted servers."  Users can bypass HITL for specific tools by
clicking "Always Allow", which adds the tool name to the connector's
``config.trusted_tools`` allow-list.

Layout: ``_helpers`` (cache state + shared helpers), ``stdio`` / ``http``
(per-transport tool factories + loaders), ``oauth`` (token lifecycle + 401
recovery), ``_loader`` (``load_mcp_tools`` + ``discover_single_mcp_connector``).
This ``__init__`` re-exports the original ``tool.py`` symbol surface so
existing ``from ...tools.mcp.tool import X`` paths keep working.
"""

from typing import Any

from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool._helpers import (
    _CITABLE_MCP_TOOLS,
    _MAX_EXTRACTED_URLS,
    _MCP_CACHE_MAX_SIZE,
    _MCP_CACHE_TTL_SECONDS,
    _TITLE_URL_RE,
    _TOOL_CALL_MAX_RETRIES,
    _TOOL_CALL_RETRY_DELAY,
    _URL_RE,
    _create_dynamic_input_model_from_schema,
    _evict_expired_mcp_cache,
    _extract_citable_urls,
    _is_auth_error,
    _mcp_tools_cache,
    _MCPCacheKey,
    _unpack_synthetic_input_data,
    invalidate_mcp_tools_cache,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool._loader import (
    _MCP_DISCOVERY_TIMEOUT_SECONDS,
    discover_single_mcp_connector,
    load_mcp_tools,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool.http import (
    _create_mcp_tool_from_definition_http,
    _load_http_mcp_tools,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool.oauth import (
    _TOKEN_REFRESH_BUFFER_SECONDS,
    _force_refresh_and_get_headers,
    _get_token_enc,
    _inject_oauth_headers,
    _mark_connector_auth_expired,
    _maybe_refresh_mcp_oauth_token,
    _refresh_connector_token,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool.stdio import (
    _create_mcp_tool_from_definition_stdio,
    _load_stdio_mcp_tools,
)

__all__ = [
    "_CITABLE_MCP_TOOLS",
    "_MAX_EXTRACTED_URLS",
    "_MCP_CACHE_MAX_SIZE",
    "_MCP_CACHE_TTL_SECONDS",
    "_MCP_DISCOVERY_TIMEOUT_SECONDS",
    "_TITLE_URL_RE",
    "_TOKEN_REFRESH_BUFFER_SECONDS",
    "_TOOL_CALL_MAX_RETRIES",
    "_TOOL_CALL_RETRY_DELAY",
    "_URL_RE",
    "_MCPCacheKey",
    "_create_dynamic_input_model_from_schema",
    "_create_mcp_tool_from_definition_http",
    "_create_mcp_tool_from_definition_stdio",
    "_evict_expired_mcp_cache",
    "_extract_citable_urls",
    "_force_refresh_and_get_headers",
    "_get_token_enc",
    "_inject_oauth_headers",
    "_is_auth_error",
    "_load_http_mcp_tools",
    "_load_stdio_mcp_tools",
    "_mark_connector_auth_expired",
    "_maybe_refresh_mcp_oauth_token",
    "_mcp_tools_cache",
    "_refresh_connector_token",
    "_token_enc",
    "_unpack_synthetic_input_data",
    "discover_single_mcp_connector",
    "invalidate_mcp_tools_cache",
    "load_mcp_tools",
]


import sys as _sys
import types as _types


class _ToolPackageModule(_types.ModuleType):
    """Module proxy delegating mutable _token_enc reads and writes to .oauth."""

    def __getattr__(self, name: str) -> Any:
        if name == "_token_enc":
            from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import oauth

            return oauth._token_enc
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_token_enc":
            from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import oauth

            oauth._token_enc = value
            return
        super().__setattr__(name, value)


_sys.modules[__name__].__class__ = _ToolPackageModule
