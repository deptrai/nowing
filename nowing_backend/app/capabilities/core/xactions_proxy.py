"""XActions thin-proxy executor factory (Story 40.2).

Provides a shared executor that proxies capability calls to XActions via MCP
instead of running local scrapers. Each platform capability registers its own
executor that delegates to this factory.

Billing is handled upstream by the REST endpoint (gate_capability → charge_capability);
this module only handles the proxy call + error mapping.
"""

from __future__ import annotations

import logging
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.exceptions import ExternalServiceError
from app.proprietary.platforms.xactions.mcp_client import (
    XActionsMcpError,
    get_shared_client,
)

logger = logging.getLogger(__name__)


def make_xactions_executor(
    platform: str,
    action: str = "scrape",
    args_mapper: Any | None = None,
) -> Any:
    """Create an executor that proxies to XActions via MCP.

    Args:
        platform: Platform name (e.g., 'topcv', 'chotot').
        action: XActions action (default: 'scrape').
        args_mapper: Optional callable(input) → dict for x_scrape args.
                     If None, uses input.model_dump() directly.

    Returns:
        Executor callable: (input) → output dict
    """

    async def execute(
        input: Any, ctx: CapabilityContext | None = None
    ) -> dict[str, Any]:
        workspace_id = getattr(ctx, "workspace_id", None) if ctx else None
        target_id = getattr(input, "target_id", None) or getattr(
            input, "target_url", None
        )

        args = args_mapper(input) if args_mapper else input.model_dump()

        payload = {
            "platform": platform,
            "action": action,
            "args": args,
            "context": {
                "targetId": str(target_id) if target_id else None,
                "workspaceId": str(workspace_id) if workspace_id else None,
            },
        }

        client = await get_shared_client()

        try:
            result = await client.call_tool("x_scrape", payload)
        except XActionsMcpError as exc:
            logger.warning(
                "XActions error for %s.%s: code=%s message=%s",
                platform,
                action,
                exc.code,
                exc.message,
            )
            raise _map_xactions_error(exc) from exc
        except Exception as exc:
            logger.exception("XActions call failed for %s.%s", platform, action)
            raise _map_generic_error(exc) from exc

        if not result.get("success"):
            error = result.get("error") or {}
            raise _map_xactions_error(
                XActionsMcpError(
                    message=error.get("message", "XActions scrape failed"),
                    code=error.get("code"),
                    retry_after=error.get("retryAfter"),
                )
            )

        data = result.get("data", [])
        return {
            "items": data if isinstance(data, list) else [data],
            "cost_micros": (result.get("meta") or {}).get("cost_micros"),
            "degraded": (result.get("meta") or {}).get("degraded", False),
            "degradation_reason": (result.get("meta") or {}).get("degradation_reason"),
            "total_items": len(data) if isinstance(data, list) else 1,
            "stream": (result.get("meta") or {}).get("stream", False),
        }

    return execute


def _map_xactions_error(exc: XActionsMcpError) -> Exception:
    """Map XActionsMcpError to HTTP-friendly exceptions."""
    if exc.code == "XACT_4001":
        return ExternalServiceError(
            "Scraper temporarily unavailable (XActions circuit open)",
            code="XACT_4001",
        )
    if exc.code in ("VALIDATION_ERROR", "INVALID_ARGS", "XACT_4002"):
        return ExternalServiceError(
            f"Invalid scrape arguments: {exc.message}",
            code="XACT_4002",
        )
    return ExternalServiceError(
        f"XActions scrape failed: {exc.message}",
        code=exc.code or "XACTIONS_ERROR",
    )


def _map_generic_error(exc: Exception) -> Exception:
    """Map generic exceptions to ExternalServiceError."""
    return ExternalServiceError(
        f"XActions scrape failed: {exc}",
        code="XACTIONS_UPSTREAM_ERROR",
    )


class _ProxyArgs:
    """Minimal input shim so the proxy executor can read args without a pydantic model.

    ``make_xactions_executor`` reads ``input.model_dump()`` when no ``args_mapper``
    is supplied — this shim exposes the raw dict through that interface.
    """

    def __init__(self, args: dict[str, Any]):
        self._args = args

    def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
        return dict(self._args)


def _is_tool_not_found(exc: XActionsMcpError) -> bool:
    """Mirror adapter_v2's tool_not_found detection (Story 40.2 local fallback)."""
    code_str = str(exc.code) if exc.code is not None else ""
    if code_str in ("XACT_404", "tool_not_found", "404"):
        return True
    msg_lower = (exc.message or "").lower()
    return "tool_not_found" in msg_lower or "tool not found" in msg_lower


async def xactions_scrape_or_local(
    platform: str,
    action: str,
    args: dict[str, Any],
    local_fn: Any,
    ctx: CapabilityContext | None = None,
) -> dict[str, Any]:
    """Try the XActions gateway first; fall back to the local scraper on
    tool_not_found / connectivity failure (Story 40.2 residual — local
    decommission lands when XActions covers every platform action).

    Only attempts the gateway when ``XACTIONS_USE_UNIFIED_DISPATCH`` is enabled;
    otherwise calls ``local_fn`` directly so scrapes never pay an MCP connect
    probe when the cutover flag is off (the common case until rollout completes).

    Returns the proxy executor's raw result dict on the XActions path, or the
    local fallback's result. Raises only when both paths fail.
    """
    if not getattr(config, "XACTIONS_USE_UNIFIED_DISPATCH", False):
        return await local_fn()

    try:
        proxy = make_xactions_executor(platform=platform, action=action)
        return await proxy(_ProxyArgs(args), ctx)
    except ExternalServiceError as exc:
        if getattr(exc, "code", None) == "XACT_4001":
            raise  # circuit open — fail fast, do not hammer the local path
        logger.warning(
            "xactions_scrape_or_local: XActions unavailable for %s.%s (%s) — "
            "falling back to local scraper",
            platform,
            action,
            exc,
        )
    except Exception as exc:  # gateway down must not break scraping
        logger.warning(
            "xactions_scrape_or_local: XActions call failed for %s.%s (%s) — "
            "falling back to local scraper",
            platform,
            action,
            exc,
        )

    return await local_fn()
