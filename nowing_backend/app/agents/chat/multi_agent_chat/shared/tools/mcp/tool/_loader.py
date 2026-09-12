"""Top-level MCP tool loading: per-workspace discovery orchestration.

``load_mcp_tools`` fans out discovery across a workspace's MCP connectors
(stdio or HTTP), caches the assembled tool list per
``(workspace_id, bypass_internal_hitl)``, and
``discover_single_mcp_connector`` forces a live refresh of one connector's
persisted ``cached_tools`` row.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from langchain_core.tools import StructuredTool
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.tools.mcp.cache import (
    read_cached_tools,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool._helpers import (
    _MCP_CACHE_MAX_SIZE,
    _MCP_CACHE_TTL_SECONDS,
    _evict_expired_mcp_cache,
    _mcp_tools_cache,
    _MCPCacheKey,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool.http import (
    _load_http_mcp_tools,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool.oauth import (
    _inject_oauth_headers,
    _mark_connector_auth_expired,
    _maybe_refresh_mcp_oauth_token,
)
from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool.stdio import (
    _load_stdio_mcp_tools,
)
from app.db import SearchSourceConnector
from app.services.mcp_oauth.registry import MCP_SERVICES, get_service_by_connector_type
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

logger = logging.getLogger(__name__)

_MCP_DISCOVERY_TIMEOUT_SECONDS = 30


async def discover_single_mcp_connector(connector_id: int) -> None:
    """Force live MCP discovery for one connector so its ``cached_tools`` row is fresh.

    ``_load_http_mcp_tools`` persists ``cached_tools`` as a side effect of any
    live discovery; passing ``cached_tools=None`` here guarantees we go to the
    network. The returned wrappers are discarded — the in-process LRU is
    rebuilt lazily on the next user query. Stdio connectors are not cached and
    are skipped.
    """
    from app.db import async_session_maker

    started = time.perf_counter()
    try:
        async with async_session_maker() as session:
            connector = await session.get(SearchSourceConnector, connector_id)
            if connector is None:
                logger.info(
                    "discover_single_mcp_connector: connector %d not found",
                    connector_id,
                )
                return

            cfg = connector.config or {}
            server_config = cfg.get("server_config", {})
            if not server_config or not isinstance(server_config, dict):
                return

            transport = server_config.get("transport", "stdio")
            if transport not in ("streamable-http", "http", "sse"):
                return

            if cfg.get("mcp_oauth"):
                server_config = await _maybe_refresh_mcp_oauth_token(
                    session, connector, cfg, server_config
                )
                cfg = connector.config or {}
                server_config = _inject_oauth_headers(cfg, server_config)
                if server_config is None:
                    logger.info(
                        "discover_single_mcp_connector: OAuth token unavailable for connector %d",
                        connector_id,
                    )
                    return

            ct = (
                connector.connector_type.value
                if hasattr(connector.connector_type, "value")
                else str(connector.connector_type)
            )
            svc_cfg = get_service_by_connector_type(ct)
            allowed_tools = svc_cfg.allowed_tools if svc_cfg else []
            readonly_tools = svc_cfg.readonly_tools if svc_cfg else frozenset()

            await asyncio.wait_for(
                _load_http_mcp_tools(
                    connector.id,
                    connector.name,
                    server_config,
                    trusted_tools=cfg.get("trusted_tools", []),
                    allowed_tools=allowed_tools,
                    readonly_tools=readonly_tools,
                    tool_name_prefix=None,
                    is_generic_mcp=svc_cfg is None,
                    bypass_internal_hitl=True,
                    cached_tools=None,
                    connector_type=ct,
                ),
                timeout=_MCP_DISCOVERY_TIMEOUT_SECONDS,
            )

            _perf_log.info(
                "[mcp_prefetch] connector=%s elapsed=%.3fs",
                connector_id,
                time.perf_counter() - started,
            )
    except TimeoutError:
        logger.warning(
            "discover_single_mcp_connector: connector %d timed out after %ds",
            connector_id,
            _MCP_DISCOVERY_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning(
            "discover_single_mcp_connector: failed for connector %d",
            connector_id,
            exc_info=True,
        )


async def load_mcp_tools(
    session: AsyncSession,
    workspace_id: int,
    *,
    bypass_internal_hitl: bool = False,
) -> list[StructuredTool]:
    """Load all MCP tools from the user's active MCP server connectors.

    Results are cached per ``(workspace_id, bypass_internal_hitl)`` for up
    to 5 minutes; bypass is keyed because each variant builds a different tool
    closure (with vs. without the in-wrapper ``request_approval`` gate).
    """
    _evict_expired_mcp_cache()

    now = time.monotonic()
    cache_key: _MCPCacheKey = (workspace_id, bypass_internal_hitl)
    cached = _mcp_tools_cache.get(cache_key)
    if cached is not None:
        cached_at, cached_tools = cached
        if now - cached_at < _MCP_CACHE_TTL_SECONDS:
            logger.info(
                "Using cached MCP tools for workspace %s (%d tools, age=%.0fs, bypass_hitl=%s)",
                workspace_id,
                len(cached_tools),
                now - cached_at,
                bypass_internal_hitl,
            )
            return list(cached_tools)

    try:
        # Find all connectors with MCP server config: generic MCP_CONNECTOR type
        # and service-specific types (LINEAR_CONNECTOR, etc.) created via MCP OAuth.
        # Cast JSON -> JSONB so we can use has_key to filter by the presence of "server_config".
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.workspace_id == workspace_id,
                cast(SearchSourceConnector.config, JSONB).has_key("server_config"),
            ),
        )

        connectors = list(result.scalars())

        # Group connectors by type to detect multi-account scenarios.
        # When >1 connector shares the same type, tool names would collide
        # so we prefix them with "{service_key}_{connector_id}_".
        type_groups: dict[str, list[SearchSourceConnector]] = defaultdict(list)
        for connector in connectors:
            ct = (
                connector.connector_type.value
                if hasattr(connector.connector_type, "value")
                else str(connector.connector_type)
            )
            type_groups[ct].append(connector)

        multi_account_types: set[str] = {
            ct for ct, group in type_groups.items() if len(group) > 1
        }
        if multi_account_types:
            logger.info(
                "Multi-account detected for connector types: %s",
                multi_account_types,
            )

        discovery_tasks: list[dict[str, Any]] = []
        for connector in connectors:
            try:
                cfg = connector.config or {}
                server_config = cfg.get("server_config", {})

                if not server_config or not isinstance(server_config, dict):
                    logger.warning(
                        "MCP connector %d (name: '%s') has invalid or missing server_config, skipping",
                        connector.id,
                        connector.name,
                    )
                    continue

                if cfg.get("mcp_oauth"):
                    server_config = await _maybe_refresh_mcp_oauth_token(
                        session,
                        connector,
                        cfg,
                        server_config,
                    )
                    cfg = connector.config or {}
                    server_config = _inject_oauth_headers(cfg, server_config)
                    if server_config is None:
                        logger.warning(
                            "Skipping MCP connector %d — OAuth token decryption failed",
                            connector.id,
                        )
                        await _mark_connector_auth_expired(connector.id)
                        continue

                trusted_tools = cfg.get("trusted_tools", [])

                ct = (
                    connector.connector_type.value
                    if hasattr(connector.connector_type, "value")
                    else str(connector.connector_type)
                )

                svc_cfg = get_service_by_connector_type(ct)
                allowed_tools = svc_cfg.allowed_tools if svc_cfg else []
                readonly_tools = svc_cfg.readonly_tools if svc_cfg else frozenset()

                tool_name_prefix: str | None = None
                if ct in multi_account_types and svc_cfg:
                    service_key = next(
                        (k for k, v in MCP_SERVICES.items() if v is svc_cfg),
                        None,
                    )
                    if service_key:
                        tool_name_prefix = f"{service_key}_{connector.id}"

                discovery_tasks.append(
                    {
                        "connector_id": connector.id,
                        "connector_name": connector.name,
                        "connector_type": ct,
                        "server_config": server_config,
                        "trusted_tools": trusted_tools,
                        "allowed_tools": allowed_tools,
                        "readonly_tools": readonly_tools,
                        "tool_name_prefix": tool_name_prefix,
                        "transport": server_config.get("transport", "stdio"),
                        "is_generic_mcp": svc_cfg is None,
                        "cached_tools": read_cached_tools(connector),
                    }
                )

            except Exception as e:
                logger.exception(
                    "Failed to prepare MCP connector %d: %s",
                    connector.id,
                    e,
                )

        async def _discover_one(task: dict[str, Any]) -> list[StructuredTool]:
            discover_start = time.perf_counter()
            transport = task["transport"]
            cached_tools = task.get("cached_tools")
            try:
                if transport in ("streamable-http", "http", "sse"):
                    result = await asyncio.wait_for(
                        _load_http_mcp_tools(
                            task["connector_id"],
                            task["connector_name"],
                            task["server_config"],
                            trusted_tools=task["trusted_tools"],
                            allowed_tools=task["allowed_tools"],
                            readonly_tools=task["readonly_tools"],
                            tool_name_prefix=task["tool_name_prefix"],
                            is_generic_mcp=task.get("is_generic_mcp", False),
                            bypass_internal_hitl=bypass_internal_hitl,
                            cached_tools=cached_tools,
                            connector_type=task.get("connector_type"),
                        ),
                        timeout=_MCP_DISCOVERY_TIMEOUT_SECONDS,
                    )
                else:
                    result = await asyncio.wait_for(
                        _load_stdio_mcp_tools(
                            task["connector_id"],
                            task["connector_name"],
                            task["server_config"],
                            trusted_tools=task["trusted_tools"],
                            bypass_internal_hitl=bypass_internal_hitl,
                        ),
                        timeout=_MCP_DISCOVERY_TIMEOUT_SECONDS,
                    )
                _perf_log.info(
                    "[mcp_discover] connector=%s name=%r transport=%s tools=%d elapsed=%.3fs cache=%s",
                    task["connector_id"],
                    task["connector_name"],
                    transport,
                    len(result),
                    time.perf_counter() - discover_start,
                    "hit" if cached_tools is not None else "miss",
                )
                return result
            except TimeoutError:
                _perf_log.info(
                    "[mcp_discover] connector=%s name=%r transport=%s elapsed=%.3fs outcome=timeout",
                    task["connector_id"],
                    task["connector_name"],
                    transport,
                    time.perf_counter() - discover_start,
                )
                logger.error(
                    "MCP connector %d timed out after %ds during discovery",
                    task["connector_id"],
                    _MCP_DISCOVERY_TIMEOUT_SECONDS,
                )
                return []
            except Exception as e:
                _perf_log.info(
                    "[mcp_discover] connector=%s name=%r transport=%s elapsed=%.3fs outcome=error",
                    task["connector_id"],
                    task["connector_name"],
                    transport,
                    time.perf_counter() - discover_start,
                )
                logger.exception(
                    "Failed to load tools from MCP connector %d: %s",
                    task["connector_id"],
                    e,
                )
                return []

        gather_start = time.perf_counter()
        results = await asyncio.gather(*[_discover_one(t) for t in discovery_tasks])
        _perf_log.info(
            "[mcp_discover] gather_wall=%.3fs connectors=%d total_tools=%d",
            time.perf_counter() - gather_start,
            len(discovery_tasks),
            sum(len(r) for r in results),
        )
        tools: list[StructuredTool] = [tool for sublist in results for tool in sublist]

        _mcp_tools_cache[cache_key] = (now, tools)

        if len(_mcp_tools_cache) > _MCP_CACHE_MAX_SIZE:
            oldest_key = min(_mcp_tools_cache, key=lambda k: _mcp_tools_cache[k][0])
            del _mcp_tools_cache[oldest_key]

        logger.info(
            "Loaded %d MCP tools for workspace %d (bypass_hitl=%s)",
            len(tools),
            workspace_id,
            bypass_internal_hitl,
        )
        return tools

    except Exception as e:
        logger.exception("Failed to load MCP tools: %s", e)
        return []
