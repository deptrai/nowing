"""Shared helpers for the MCP tool package.

Holds the in-process tools cache (``_mcp_tools_cache`` — the single owner),
citable-URL extraction, dynamic input-schema modeling, and auth-error
detection used by the stdio/HTTP loaders and the OAuth recovery helpers.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, create_model

logger = logging.getLogger(__name__)

_MCP_CACHE_TTL_SECONDS = 300  # 5 minutes
_MCP_CACHE_MAX_SIZE = 50
_TOOL_CALL_MAX_RETRIES = 3
_TOOL_CALL_RETRY_DELAY = 1.5  # seconds, doubles per attempt
# Keyed by ``(workspace_id, bypass_internal_hitl)`` so single-agent and
# multi-agent paths cannot share tool closures with different HITL wiring.
_MCPCacheKey = tuple[int, bool]
_mcp_tools_cache: dict[_MCPCacheKey, tuple[float, list[StructuredTool]]] = {}

# ponytail: URL extraction for MCP tools that return web results (e.g. Exa).
# Matches http(s) URLs in plain text; capped at 20 to avoid runaway extraction
# on tools that dump large link lists.
_URL_RE = re.compile(r"https?://[^\s<>'\"`,)\]]+")
_MAX_EXTRACTED_URLS = 20

# ponytail: Exa search results follow "Title: <title>\nURL: <url>" format.
# This regex pairs them; unmatched URLs get None title.
_TITLE_URL_RE = re.compile(r"Title:\s*(.+?)\s*\n+URL:\s*(https?://\S+)", re.IGNORECASE)

# Tool names that produce citable web results. ``web_fetch_exa`` takes a URL
# as input (so we cite the input, not the output); ``web_search_exa`` returns
# URLs in its result text.
_CITABLE_MCP_TOOLS = frozenset({"web_search_exa", "web_fetch_exa"})


def _extract_citable_urls(
    tool_name: str,
    result_text: str,
    call_kwargs: dict[str, Any],
) -> list[tuple[str, str | None]]:
    """Extract (url, title) pairs to cite from an MCP tool's result or input args.

    For ``web_fetch_exa`` the URL is the input arg (title is None); for
    ``web_search_exa`` URLs and titles are parsed from the result text.
    Other tools return empty.
    """
    if tool_name not in _CITABLE_MCP_TOOLS:
        return []
    if tool_name == "web_fetch_exa":
        url = (call_kwargs.get("url") or "").strip()
        return [(url, None)] if url else []
    # web_search_exa: first try structured "Title: ...\nURL: ..." pairs.
    pairs: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for m in _TITLE_URL_RE.finditer(result_text):
        title = m.group(1).strip()
        url = m.group(2).rstrip(".,;:!?")
        if url not in seen:
            seen.add(url)
            pairs.append((url, title or None))
            if len(pairs) >= _MAX_EXTRACTED_URLS:
                return pairs
    # Fallback: extract bare URLs without titles.
    for m in _URL_RE.finditer(result_text):
        url = m.group(0).rstrip(".,;:!?")
        if url not in seen:
            seen.add(url)
            pairs.append((url, None))
            if len(pairs) >= _MAX_EXTRACTED_URLS:
                break
    return pairs


def _evict_expired_mcp_cache() -> None:
    """Remove expired entries from the MCP tools cache to prevent unbounded growth."""
    now = time.monotonic()
    expired = [
        k
        for k, (ts, _) in _mcp_tools_cache.items()
        if now - ts >= _MCP_CACHE_TTL_SECONDS
    ]
    for k in expired:
        del _mcp_tools_cache[k]
    if expired:
        logger.debug("Evicted %d expired MCP cache entries", len(expired))


def _create_dynamic_input_model_from_schema(
    tool_name: str,
    input_schema: dict[str, Any],
) -> type[BaseModel]:
    """Create a Pydantic model from MCP tool's JSON schema.

    Models always allow extra fields (``extra="allow"``) so that parameters
    missing from a broken or incomplete JSON schema (e.g. ``zod-to-json-schema``
    producing an empty ``$schema``-only object) can still be forwarded to the
    MCP server.

    When the schema declares **no** properties, a synthetic ``input_data``
    field of type ``dict`` is injected so the LLM has a visible parameter to
    populate.  The caller should unpack ``input_data`` before forwarding to
    the MCP server (see ``_unpack_synthetic_input_data``).
    """
    properties = input_schema.get("properties", {})
    required_fields = input_schema.get("required", [])

    field_definitions = {}
    for param_name, param_schema in properties.items():
        param_description = param_schema.get("description", "")
        is_required = param_name in required_fields

        if is_required:
            field_definitions[param_name] = (
                Any,
                Field(..., description=param_description),
            )
        else:
            field_definitions[param_name] = (
                Any | None,
                Field(None, description=param_description),
            )

    if not properties:
        field_definitions["input_data"] = (
            dict[str, Any] | None,
            Field(
                None,
                description=(
                    "Arguments to pass to this tool as a JSON object. "
                    "Infer sensible key names from the tool name and description "
                    '(e.g. {"search": "my query"} for a search tool).'
                ),
            ),
        )

    model_name = f"{tool_name.replace(' ', '').replace('-', '_')}Input"
    model = create_model(
        model_name, __config__=ConfigDict(extra="allow"), **field_definitions
    )
    return model


def _unpack_synthetic_input_data(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Unpack the synthetic ``input_data`` field into top-level kwargs.

    When the MCP tool schema is empty, ``_create_dynamic_input_model_from_schema``
    adds a catch-all ``input_data: dict`` field.  This helper merges that dict
    back into the top-level kwargs so the MCP server receives flat arguments.
    """
    input_data = kwargs.pop("input_data", None)
    if isinstance(input_data, dict):
        kwargs.update(input_data)
    return kwargs


# ---------------------------------------------------------------------------
# Reactive 401 handling helpers
# ---------------------------------------------------------------------------


def _is_auth_error(exc: Exception) -> bool:
    """Check if an exception indicates an HTTP 401 authentication failure."""
    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code == 401
    except ImportError as exc:
        logger.debug("Suppressed %r", exc)
    err_str = str(exc).lower()
    return "401" in err_str or "unauthorized" in err_str


def invalidate_mcp_tools_cache(workspace_id: int | None = None) -> None:
    """Invalidate cached MCP tools (both ``bypass_internal_hitl`` variants together)."""
    if workspace_id is not None:
        for key in [k for k in _mcp_tools_cache if k[0] == workspace_id]:
            _mcp_tools_cache.pop(key, None)
    else:
        _mcp_tools_cache.clear()
