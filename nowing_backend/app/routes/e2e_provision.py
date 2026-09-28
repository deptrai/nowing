"""E2E connector provision endpoint.

``POST /__e2e__/connectors/provision`` — creates a pre-connected
``SearchSourceConnector`` row using ``E2E_<PROVIDER>_*`` env vars, so Playwright
specs can drive real third-party journeys without running an OAuth consent
dance in the browser (Google blocks headless bots anyway).

Mount gate: this router is only registered when ``E2E_PROVISION_ENABLED=TRUE``
(see ``app/routes/__init__.py``). When the env is unset/false the route doesn't
exist → production returns 404 and leaks nothing.

Request gate:
1. ``x-playwright-test: true`` header — absent → 404 (gate stays invisible).
2. ``require_superuser`` — only platform admins can provision.

Response never contains secrets — only ``connector_id`` and metadata.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    get_async_session,
)
from app.users import require_superuser
from app.utils.connector_naming import generate_unique_connector_name
from app.utils.oauth_security import TokenEncryption

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/__e2e__", tags=["__e2e__"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ProvisionRequest(BaseModel):
    """Body for POST /__e2e__/connectors/provision."""

    connector: str = Field(
        ...,
        description=(
            "Provider key — matches the E2E_<PROVIDER>_* env prefix. "
            "One of: slack, notion, linear, jira, clickup, confluence, airtable, "
            "google_drive, gmail, google_calendar, dropbox, onedrive, "
            "composio_drive, composio_gmail, composio_calendar."
        ),
    )
    workspace_id: int = Field(..., description="Target workspace ID (e.g. 15).")
    name: str | None = Field(
        default=None,
        description="Optional connector display name; auto-generated if absent.",
    )


class ProvisionResponse(BaseModel):
    """Response — never carries secrets."""

    connector_id: int
    connector_type: str
    name: str
    workspace_id: int


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


async def _require_playwright_header(
    x_playwright_test: str | None = Header(default=None, alias="x-playwright-test"),
) -> None:
    """Return 404 when the header is absent — hides the gate's existence."""
    if x_playwright_test != "true":
        # 404 (not 403): keeps the endpoint invisible to scanners even when
        # the operator forgot to disable E2E_PROVISION_ENABLED.
        raise HTTPException(status_code=404, detail="Not Found")


# ---------------------------------------------------------------------------
# Per-provider config builders
# ---------------------------------------------------------------------------


def _get_enc() -> TokenEncryption:
    if not config.SECRET_KEY:
        raise HTTPException(
            status_code=500, detail="SECRET_KEY not configured for token encryption"
        )
    return TokenEncryption(config.SECRET_KEY)


def _require_env(env: dict[str, str | None], keys: list[str], provider: str) -> None:
    """Verify required env vars are present; 404 if any missing."""
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Provider '{provider}' not provisioned: missing env vars "
                f"{', '.join(missing)}"
            ),
        )


def _build_slack_config(env: dict[str, str | None]) -> dict[str, Any]:
    """Slack bot_token connector config — mirrors slack_add_connector_route."""
    _require_env(env, ["bot_token", "team_id"], "slack")
    enc = _get_enc()
    return {
        "bot_token": enc.encrypt_token(env["bot_token"]),
        "refresh_token": enc.encrypt_token(env["refresh_token"])
        if env.get("refresh_token")
        else None,
        "bot_user_id": env.get("bot_user_id"),
        "team_id": env["team_id"],
        "team_name": env.get("team_name"),
        "token_type": "Bearer",
        "expires_in": None,
        "expires_at": None,
        "scope": None,
        "_token_encrypted": True,
    }


def _build_notion_config(env: dict[str, str | None]) -> dict[str, Any]:
    """Notion OAuth connector config — mirrors notion_add_connector_route."""
    _require_env(env, ["access_token"], "notion")
    enc = _get_enc()
    return {
        "access_token": enc.encrypt_token(env["access_token"]),
        "refresh_token": enc.encrypt_token(env["refresh_token"])
        if env.get("refresh_token")
        else None,
        "expires_in": None,
        "expires_at": None,
        "workspace_id": env.get("workspace_id"),
        "workspace_name": env.get("workspace_name"),
        "workspace_icon": None,
        "bot_id": env.get("bot_id"),
        "_token_encrypted": True,
    }


def _build_mcp_oauth_config(
    provider: str,
    env: dict[str, str | None],
    svc: Any,
    extra_meta_keys: list[str] | None = None,
) -> dict[str, Any]:
    """MCP OAuth connector config — mirrors mcp_oauth_route.py shape.

    ``svc`` is a ``MCPServiceConfig`` (Linear/Jira/ClickUp/Slack-MCP/Airtable/
    Notion-MCP/Confluence). Tokens live under ``mcp_oauth`` so the runtime
    refresh path can rotate them.
    """
    _require_env(env, ["access_token", "client_id", "token_endpoint"], provider)
    enc = _get_enc()
    expires_at = None
    expires_in = None
    if env.get("expires_in"):
        try:
            expires_in = int(env["expires_in"])
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        except (ValueError, TypeError):
            expires_in = None

    cfg: dict[str, Any] = {
        "server_config": {
            "transport": "streamable-http",
            "url": svc.mcp_url,
        },
        "mcp_service": provider,
        "mcp_oauth": {
            "client_id": env["client_id"],
            "client_secret": enc.encrypt_token(env["client_secret"])
            if env.get("client_secret")
            else "",
            "token_endpoint": env["token_endpoint"],
            "access_token": enc.encrypt_token(env["access_token"]),
            "refresh_token": enc.encrypt_token(env["refresh_token"])
            if env.get("refresh_token")
            else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": env.get("scope"),
        },
        "_token_encrypted": True,
    }

    # Account metadata — keys the connector picker / LLM sees (no secrets).
    meta_keys = ["display_name"] + (extra_meta_keys or [])
    for key in meta_keys:
        if env.get(key):
            cfg[key] = env[key]
    return cfg


def _build_google_oauth_config(env: dict[str, str | None]) -> dict[str, Any]:
    """Google (Drive/Gmail/Calendar) — refresh-token only.

    The backend's refresh flow mints access_token on first call, so we store
    the refresh token + OAuth client creds encrypted.
    """
    _require_env(env, ["client_id", "client_secret", "refresh_token"], "google_*")
    enc = _get_enc()
    return {
        "access_token": None,  # refreshed on first call
        "refresh_token": enc.encrypt_token(env["refresh_token"]),
        "client_id": env["client_id"],
        "client_secret": enc.encrypt_token(env["client_secret"]),
        "expires_in": None,
        "expires_at": None,
        "token_type": "Bearer",
        "_token_encrypted": True,
    }


def _build_dropbox_config(env: dict[str, str | None]) -> dict[str, Any]:
    _require_env(env, ["access_token"], "dropbox")
    enc = _get_enc()
    return {
        "access_token": enc.encrypt_token(env["access_token"]),
        "refresh_token": enc.encrypt_token(env["refresh_token"])
        if env.get("refresh_token")
        else None,
        "app_key": env.get("app_key"),
        "app_secret": enc.encrypt_token(env["app_secret"])
        if env.get("app_secret")
        else None,
        "_token_encrypted": True,
    }


def _build_onedrive_config(env: dict[str, str | None]) -> dict[str, Any]:
    _require_env(env, ["access_token"], "onedrive")
    enc = _get_enc()
    return {
        "access_token": enc.encrypt_token(env["access_token"]),
        "refresh_token": enc.encrypt_token(env["refresh_token"])
        if env.get("refresh_token")
        else None,
        "client_id": env.get("client_id"),
        "client_secret": enc.encrypt_token(env["client_secret"])
        if env.get("client_secret")
        else None,
        "_token_encrypted": True,
    }


def _build_composio_config(
    toolkit_id: str, env: dict[str, str | None]
) -> dict[str, Any]:
    """Composio-backed connector — tokens live on Composio's side.

    Mirrors the real ``composio_routes.py`` OAuth-callback shape: only the
    connected account id + toolkit metadata are persisted. The Composio API
    key is *read* by ``ComposioService`` from the global env at runtime — it
    is never stored on the row (the connector-list API returns ``config`` to
    workspace members, so a plaintext key here would leak).
    """
    _require_env(env, ["api_key", "connected_account_id"], f"composio_{toolkit_id}")
    return {
        "composio_connected_account_id": env["connected_account_id"],
        "toolkit_id": toolkit_id,
        "toolkit_name": toolkit_id,  # display name resolved downstream
        "is_indexable": toolkit_id == "googledrive",
    }


# ---------------------------------------------------------------------------
# Provider → connector_type / builder map
# ---------------------------------------------------------------------------


def _provider_to_connector_type(provider: str) -> SearchSourceConnectorType:
    """Map provider key to its ``SearchSourceConnectorType`` enum value."""
    mapping: dict[str, SearchSourceConnectorType] = {
        "slack": SearchSourceConnectorType.SLACK_CONNECTOR,
        "notion": SearchSourceConnectorType.NOTION_CONNECTOR,
        "linear": SearchSourceConnectorType.LINEAR_CONNECTOR,
        "jira": SearchSourceConnectorType.JIRA_CONNECTOR,
        "clickup": SearchSourceConnectorType.CLICKUP_CONNECTOR,
        "confluence": SearchSourceConnectorType.CONFLUENCE_CONNECTOR,
        "airtable": SearchSourceConnectorType.AIRTABLE_CONNECTOR,
        "google_drive": SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
        "gmail": SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR,
        "google_calendar": SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR,
        "dropbox": SearchSourceConnectorType.DROPBOX_CONNECTOR,
        "onedrive": SearchSourceConnectorType.ONEDRIVE_CONNECTOR,
        "composio_drive": SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        "composio_gmail": SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR,
        "composio_calendar": SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
    }
    try:
        return mapping[provider]
    except KeyError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported connector '{provider}'. Valid: {sorted(mapping)}",
        ) from e


def _build_config_for(
    provider: str, env: dict[str, str | None]
) -> dict[str, Any]:
    """Dispatch to the per-provider config builder."""
    if provider == "slack":
        return _build_slack_config(env)
    if provider == "notion":
        return _build_notion_config(env)
    if provider in ("google_drive", "gmail", "google_calendar"):
        return _build_google_oauth_config(env)
    if provider == "dropbox":
        return _build_dropbox_config(env)
    if provider == "onedrive":
        return _build_onedrive_config(env)
    if provider in ("composio_drive", "composio_gmail", "composio_calendar"):
        toolkit_id = {
            "composio_drive": "googledrive",
            "composio_gmail": "gmail",
            "composio_calendar": "googlecalendar",
        }[provider]
        return _build_composio_config(toolkit_id, env)
    if provider in ("linear", "jira", "clickup", "confluence", "airtable"):
        from app.services.mcp_oauth.registry import MCP_SERVICES

        svc = MCP_SERVICES.get(provider)
        if svc is None:
            raise HTTPException(
                status_code=500,
                detail=f"MCP service '{provider}' not registered",
            )
        meta_keys = list(svc.account_metadata_keys)
        return _build_mcp_oauth_config(provider, env, svc, meta_keys)
    raise HTTPException(
        status_code=422, detail=f"Unsupported connector '{provider}'"
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/connectors/provision", response_model=ProvisionResponse)
async def provision_connector(
    body: ProvisionRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
    _header: None = Depends(_require_playwright_header),
) -> ProvisionResponse:
    """Create a pre-connected ``SearchSourceConnector`` from E2E_* env vars.

    Used by Playwright specs to drive real third-party journeys without
    OAuth-in-browser. Never returns tokens — only the connector id.
    """
    provider = body.connector.lower()
    env = config.E2E_PROVIDER_ENV.get(provider)
    if env is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported connector '{provider}'. "
                f"Valid: {sorted(config.E2E_PROVIDER_ENV.keys())}"
            ),
        )

    connector_type = _provider_to_connector_type(provider)
    connector_config = _build_config_for(provider, env)

    # Idempotent provisioning. Realistically one connector of each type per
    # (workspace_id, user_id) suffices for E2E — and re-running must update
    # the same row rather than insert a duplicate. Two paths collide when a
    # default name is generated dynamically: instead of keying the lookup on
    # name (which would diverge as names cycle), key on the (workspace, user,
    # connector_type) triple and only filter by name when the caller passed
    # one explicitly.
    filters = [
        SearchSourceConnector.workspace_id == body.workspace_id,
        SearchSourceConnector.user_id == auth.user.id,
        SearchSourceConnector.connector_type == connector_type,
    ]
    if body.name is not None:
        filters.append(SearchSourceConnector.name == body.name)

    result = await session.execute(select(SearchSourceConnector).where(*filters))
    existing = result.scalars().first()
    if existing is not None:
        existing.config = connector_config
        flag_modified(existing, "config")
        try:
            await session.commit()
            await session.refresh(existing)
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(
                status_code=409, detail=f"Provision failed: {e!s}"
            ) from e
        logger.info(
            "[e2e] re-provisioned connector %s (%s) for user %s ws %s",
            existing.id,
            provider,
            auth.user.id,
            body.workspace_id,
        )
        return ProvisionResponse(
            connector_id=existing.id,
            connector_type=connector_type.value,
            name=existing.name,
            workspace_id=existing.workspace_id,
        )

    # No existing connector — pick a name.
    if body.name is not None:
        name = body.name
    else:
        try:
            name = await generate_unique_connector_name(
                session, connector_type, body.workspace_id, auth.user.id, None
            )
        except Exception:  # fallback to deterministic name
            name = f"E2E {provider.replace('_', ' ').title()}"

    new_connector = SearchSourceConnector(
        name=name,
        connector_type=connector_type,
        is_indexable=connector_type
        in (
            SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
            SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            SearchSourceConnectorType.NOTION_CONNECTOR,
            SearchSourceConnectorType.DROPBOX_CONNECTOR,
            SearchSourceConnectorType.ONEDRIVE_CONNECTOR,
        ),
        config=connector_config,
        workspace_id=body.workspace_id,
        user_id=auth.user.id,
    )
    session.add(new_connector)
    try:
        await session.commit()
        await session.refresh(new_connector)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Connector for provider '{provider}' already exists",
        ) from e

    logger.info(
        "[e2e] provisioned connector %s (%s) for user %s ws %s",
        new_connector.id,
        provider,
        auth.user.id,
        body.workspace_id,
    )
    return ProvisionResponse(
        connector_id=new_connector.id,
        connector_type=connector_type.value,
        name=new_connector.name,
        workspace_id=new_connector.workspace_id,
    )
