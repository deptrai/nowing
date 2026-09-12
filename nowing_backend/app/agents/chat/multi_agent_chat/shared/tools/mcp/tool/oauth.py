"""MCP OAuth token lifecycle: decrypt/inject, proactive refresh, 401 recovery.

Owns the ``_token_enc`` singleton (lazy :class:`TokenEncryption` built from
``app.config.SECRET_KEY``). All token plaintext stays out of
``server_config.headers`` in the DB — headers are injected on a copy.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.utils.oauth_security import TokenEncryption

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool._helpers import (
    invalidate_mcp_tools_cache,
)
from app.db import SearchSourceConnector
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_BUFFER_SECONDS = 300  # refresh 5 min before expiry

_token_enc: TokenEncryption | None = None


def _get_token_enc() -> TokenEncryption:
    global _token_enc
    if _token_enc is None:
        from app.config import config as app_config
        from app.utils.oauth_security import TokenEncryption

        _token_enc = TokenEncryption(app_config.SECRET_KEY)
    return _token_enc


def _inject_oauth_headers(
    cfg: dict[str, Any],
    server_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Decrypt the MCP OAuth access token and inject it into server_config headers.

    The DB never stores plaintext tokens in ``server_config.headers``.  This
    function decrypts ``mcp_oauth.access_token`` at runtime and returns a
    *copy* of ``server_config`` with the Authorization header set.
    """
    mcp_oauth = cfg.get("mcp_oauth", {})
    encrypted_token = mcp_oauth.get("access_token")
    if not encrypted_token:
        return server_config

    try:
        access_token = _get_token_enc().decrypt_token(encrypted_token)

        result = dict(server_config)
        result["headers"] = {
            **server_config.get("headers", {}),
            "Authorization": f"Bearer {access_token}",
        }
        return result
    except Exception:
        logger.error(
            "Failed to decrypt MCP OAuth token — connector will be skipped",
            exc_info=True,
        )
        return None


async def _refresh_connector_token(
    session: AsyncSession,
    connector: SearchSourceConnector,
) -> str | None:
    """Refresh the OAuth token for an MCP connector and persist the result.

    This is the shared core used by both proactive (pre-expiry) and reactive
    (401 recovery) refresh paths.  It handles:
    - Decrypting the current refresh token / client secret
    - Calling the token endpoint
    - Encrypting and persisting the new tokens
    - Clearing ``auth_expired`` if it was set
    - Invalidating the MCP tools cache

    Returns the **plaintext** new access token on success, or ``None`` on
    failure (no refresh token, IdP error, etc.).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.orm.attributes import flag_modified

    from app.services.mcp_oauth.discovery import refresh_access_token

    cfg = connector.config or {}
    mcp_oauth = cfg.get("mcp_oauth", {})

    refresh_token = mcp_oauth.get("refresh_token")
    if not refresh_token:
        logger.warning(
            "MCP connector %s: no refresh_token available",
            connector.id,
        )
        return None

    enc = _get_token_enc()
    decrypted_refresh = enc.decrypt_token(refresh_token)
    decrypted_secret = (
        enc.decrypt_token(mcp_oauth["client_secret"])
        if mcp_oauth.get("client_secret")
        else ""
    )

    token_json = await refresh_access_token(
        token_endpoint=mcp_oauth["token_endpoint"],
        refresh_token=decrypted_refresh,
        client_id=mcp_oauth["client_id"],
        client_secret=decrypted_secret,
    )

    new_access = token_json.get("access_token")
    if not new_access:
        logger.warning(
            "MCP connector %s: token refresh returned no access_token",
            connector.id,
        )
        return None

    new_expires_at = None
    if token_json.get("expires_in"):
        new_expires_at = datetime.now(UTC) + timedelta(
            seconds=int(token_json["expires_in"])
        )

    updated_oauth = dict(mcp_oauth)
    updated_oauth["access_token"] = enc.encrypt_token(new_access)
    if token_json.get("refresh_token"):
        updated_oauth["refresh_token"] = enc.encrypt_token(token_json["refresh_token"])
    updated_oauth["expires_at"] = new_expires_at.isoformat() if new_expires_at else None

    updated_cfg = {**cfg, "mcp_oauth": updated_oauth}
    updated_cfg.pop("auth_expired", None)
    connector.config = updated_cfg
    flag_modified(connector, "config")
    await session.commit()
    await session.refresh(connector)

    invalidate_mcp_tools_cache(connector.workspace_id)

    return new_access


async def _maybe_refresh_mcp_oauth_token(
    session: AsyncSession,
    connector: SearchSourceConnector,
    cfg: dict[str, Any],
    server_config: dict[str, Any],
) -> dict[str, Any]:
    """Refresh the access token for an MCP OAuth connector if it is about to expire.

    Returns the (possibly updated) ``server_config``.
    """
    from datetime import UTC, datetime, timedelta

    mcp_oauth = cfg.get("mcp_oauth", {})
    expires_at_str = mcp_oauth.get("expires_at")
    if not expires_at_str:
        return server_config

    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if datetime.now(UTC) < expires_at - timedelta(
            seconds=_TOKEN_REFRESH_BUFFER_SECONDS
        ):
            return server_config
    except (ValueError, TypeError):
        return server_config

    refresh_start = time.perf_counter()
    try:
        new_access = await _refresh_connector_token(session, connector)
        if not new_access:
            _perf_log.info(
                "[mcp_oauth_refresh] connector=%s elapsed=%.3fs outcome=no_token",
                connector.id,
                time.perf_counter() - refresh_start,
            )
            return server_config

        logger.info(
            "Proactively refreshed MCP OAuth token for connector %s", connector.id
        )
        _perf_log.info(
            "[mcp_oauth_refresh] connector=%s elapsed=%.3fs outcome=refreshed",
            connector.id,
            time.perf_counter() - refresh_start,
        )

        refreshed_config = dict(server_config)
        refreshed_config["headers"] = {
            **server_config.get("headers", {}),
            "Authorization": f"Bearer {new_access}",
        }
        return refreshed_config

    except Exception:
        _perf_log.info(
            "[mcp_oauth_refresh] connector=%s elapsed=%.3fs outcome=failed",
            connector.id,
            time.perf_counter() - refresh_start,
        )
        logger.warning(
            "Failed to refresh MCP OAuth token for connector %s",
            connector.id,
            exc_info=True,
        )
        return server_config


# ---------------------------------------------------------------------------
# Reactive 401 handling helpers
# ---------------------------------------------------------------------------


async def _force_refresh_and_get_headers(
    connector_id: int,
) -> dict[str, str] | None:
    """Force-refresh OAuth token for a connector and return fresh HTTP headers.

    Opens a **new** DB session so this can be called from inside tool closures
    that don't have access to the original session.

    Returns ``None`` when the connector is not OAuth-backed, has no
    refresh token, or the refresh itself fails.
    """
    from app.db import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == connector_id,
                )
            )
            connector = result.scalars().first()
            if not connector:
                return None

            cfg = connector.config or {}
            if not cfg.get("mcp_oauth"):
                return None

            server_config = cfg.get("server_config", {})

            new_access = await _refresh_connector_token(session, connector)
            if not new_access:
                return None

            logger.info(
                "Force-refreshed MCP OAuth token for connector %s (401 recovery)",
                connector_id,
            )
            return {
                **server_config.get("headers", {}),
                "Authorization": f"Bearer {new_access}",
            }

    except Exception:
        logger.warning(
            "Failed to force-refresh MCP OAuth token for connector %s",
            connector_id,
            exc_info=True,
        )
        return None


async def _mark_connector_auth_expired(connector_id: int) -> None:
    """Set ``config.auth_expired = True`` so the frontend shows re-auth UI."""
    from app.db import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.id == connector_id,
                )
            )
            connector = result.scalars().first()
            if not connector:
                return

            cfg = dict(connector.config or {})
            if cfg.get("auth_expired"):
                return

            cfg["auth_expired"] = True
            connector.config = cfg

            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(connector, "config")
            await session.commit()

            logger.info(
                "Marked MCP connector %d as auth_expired after unrecoverable 401",
                connector_id,
            )
            invalidate_mcp_tools_cache(connector.workspace_id)

    except Exception:
        logger.warning(
            "Failed to mark connector %s as auth_expired",
            connector_id,
            exc_info=True,
        )
