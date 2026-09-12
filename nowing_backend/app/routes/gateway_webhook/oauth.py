"""Messaging gateway routes."""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatBinding,
    ExternalChatBindingState,
    ExternalChatHealthStatus,
    ExternalChatPeerKind,
    ExternalChatPlatform,
    get_async_session,
)
from app.gateway.accounts import (
    get_discord_account_by_guild,
    get_slack_account_by_team,
)
from app.gateway.discord.adapter import discord_user_peer_id
from app.gateway.slack.adapter import slack_user_peer_id
from app.users import get_auth_context
from app.utils.oauth_security import OAuthStateManager, TokenEncryption
from app.utils.rbac import check_workspace_access

from ._helpers import (
    _discord_frontend_redirect,
    _discord_gateway_enabled,
    _discord_redirect_uri,
    _get_state_manager,
    _get_token_encryption,
    _slack_frontend_redirect,
    _slack_gateway_enabled,
    _slack_redirect_uri,
)

logger = logging.getLogger(__name__)
router = APIRouter()

SLACK_AUTHORIZATION_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
DISCORD_AUTHORIZATION_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API = "https://discord.com/api/v10"
SLACK_BOT_SCOPES = [
    "app_mentions:read",
    "chat:write",
    "channels:read",
    "groups:read",
    "im:write",
    "users:read",
    "team:read",
]
DISCORD_GATEWAY_SCOPES = ["identify", "guilds", "bot"]
DISCORD_VIEW_CHANNEL = 1 << 10
DISCORD_SEND_MESSAGES = 1 << 11
DISCORD_READ_MESSAGE_HISTORY = 1 << 16
DISCORD_SEND_MESSAGES_IN_THREADS = 1 << 38
DISCORD_GATEWAY_PERMISSIONS = (
    DISCORD_VIEW_CHANNEL
    | DISCORD_SEND_MESSAGES
    | DISCORD_READ_MESSAGE_HISTORY
    | DISCORD_SEND_MESSAGES_IN_THREADS
)
_state_manager: OAuthStateManager | None = None
_token_encryption: TokenEncryption | None = None


@router.get("/slack/install")
async def install_slack_gateway(
    workspace_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    user = auth.user
    if not _slack_gateway_enabled():
        raise HTTPException(
            status_code=500, detail="Slack gateway OAuth is not configured"
        )
    await check_workspace_access(session, auth, workspace_id)
    state = _get_state_manager().generate_secure_state(workspace_id, user.id)
    auth_params = {
        "client_id": config.GATEWAY_SLACK_CLIENT_ID,
        "scope": ",".join(SLACK_BOT_SCOPES),
        "redirect_uri": _slack_redirect_uri(),
        "state": state,
    }
    return {"auth_url": f"{SLACK_AUTHORIZATION_URL}?{urlencode(auth_params)}"}


@router.get("/slack/callback")
async def slack_gateway_callback(
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    space_id = None
    if state:
        try:
            state_data = _get_state_manager().validate_state(state)
            space_id = int(state_data["space_id"])
        except Exception:
            state_data = None
    else:
        state_data = None

    if error:
        return _slack_frontend_redirect(
            space_id or 0, error="slack_gateway_oauth_denied"
        )
    if not code or state_data is None:
        raise HTTPException(
            status_code=400, detail="Invalid Slack gateway OAuth callback"
        )
    if not _slack_gateway_enabled():
        raise HTTPException(
            status_code=500, detail="Slack gateway OAuth is not configured"
        )

    user_id = UUID(state_data["user_id"])
    token_payload = {
        "client_id": config.GATEWAY_SLACK_CLIENT_ID,
        "client_secret": config.GATEWAY_SLACK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": _slack_redirect_uri(),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            SLACK_TOKEN_URL,
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    token_response.raise_for_status()
    token_json = token_response.json()
    if not token_json.get("ok", False):
        raise HTTPException(
            status_code=400,
            detail=f"Slack gateway OAuth failed: {token_json.get('error', 'unknown_error')}",
        )

    bot_token = token_json.get("access_token")
    team = token_json.get("team") or {}
    team_id = team.get("id")
    if not bot_token or not team_id:
        raise HTTPException(
            status_code=400, detail="Slack gateway OAuth returned incomplete data"
        )

    bot_user_id = token_json.get("bot_user_id")
    app_id = token_json.get("app_id")
    authed_user = token_json.get("authed_user") or {}
    authed_slack_user_id = authed_user.get("id")
    enc = _get_token_encryption()
    credentials = {
        "bot_token": bot_token,
        "token_type": token_json.get("token_type", "bot"),
        "scope": token_json.get("scope"),
    }
    cursor_state = {
        "team_id": team_id,
        "team_name": team.get("name"),
        "enterprise_id": (token_json.get("enterprise") or {}).get("id"),
        "app_id": app_id,
        "bot_user_id": bot_user_id,
        "scope": token_json.get("scope"),
    }

    account = await get_slack_account_by_team(session, team_id=team_id)
    if account is None:
        account = ExternalChatAccount(
            platform=ExternalChatPlatform.SLACK,
            mode=ExternalChatAccountMode.CLOUD_SHARED,
            is_system_account=True,
            encrypted_credentials=enc.encrypt_token(json.dumps(credentials)),
            bot_username="Nowing",
            cursor_state=cursor_state,
            health_status=ExternalChatHealthStatus.UNKNOWN,
        )
        session.add(account)
        await session.flush()
    else:
        account.encrypted_credentials = enc.encrypt_token(json.dumps(credentials))
        account.cursor_state = {**(account.cursor_state or {}), **cursor_state}
        account.health_status = ExternalChatHealthStatus.UNKNOWN

    if authed_slack_user_id:
        peer_id = slack_user_peer_id(team_id, authed_slack_user_id)
        existing_binding_result = await session.execute(
            select(ExternalChatBinding).where(
                ExternalChatBinding.account_id == account.id,
                ExternalChatBinding.external_peer_id == peer_id,
                ExternalChatBinding.state.in_(
                    [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
                ),
            )
        )
        binding = existing_binding_result.scalars().first()
        if binding is None:
            session.add(
                ExternalChatBinding(
                    account_id=account.id,
                    user_id=user_id,
                    workspace_id=space_id,
                    state=ExternalChatBindingState.BOUND,
                    external_peer_id=peer_id,
                    external_peer_kind=ExternalChatPeerKind.DIRECT,
                    external_username=authed_slack_user_id,
                    external_metadata={
                        "kind": "slack_user",
                        "team_id": team_id,
                        "slack_user_id": authed_slack_user_id,
                    },
                )
            )
        elif binding.user_id == user_id:
            binding.workspace_id = space_id
            binding.external_metadata = {
                **(binding.external_metadata or {}),
                "kind": "slack_user",
                "team_id": team_id,
                "slack_user_id": authed_slack_user_id,
            }

    await session.commit()
    return _slack_frontend_redirect(space_id, success=True)


@router.get("/discord/install")
async def install_discord_gateway(
    workspace_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    user = auth.user
    if not _discord_gateway_enabled():
        raise HTTPException(
            status_code=500, detail="Discord gateway OAuth is not configured"
        )
    await check_workspace_access(session, auth, workspace_id)
    state = _get_state_manager().generate_secure_state(workspace_id, user.id)
    auth_params = {
        "client_id": config.DISCORD_CLIENT_ID,
        "scope": " ".join(DISCORD_GATEWAY_SCOPES),
        "redirect_uri": _discord_redirect_uri(),
        "response_type": "code",
        "state": state,
        "permissions": str(DISCORD_GATEWAY_PERMISSIONS),
    }
    return {"auth_url": f"{DISCORD_AUTHORIZATION_URL}?{urlencode(auth_params)}"}


@router.get("/discord/callback")
async def discord_gateway_callback(
    code: str | None = None,
    error: str | None = None,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    space_id = None
    if state:
        try:
            state_data = _get_state_manager().validate_state(state)
            space_id = int(state_data["space_id"])
        except Exception:
            state_data = None
    else:
        state_data = None

    if error:
        return _discord_frontend_redirect(
            space_id or 0, error="discord_gateway_oauth_denied"
        )
    if not code or state_data is None:
        raise HTTPException(
            status_code=400, detail="Invalid Discord gateway OAuth callback"
        )
    if not _discord_gateway_enabled():
        raise HTTPException(
            status_code=500, detail="Discord gateway OAuth is not configured"
        )

    user_id = UUID(state_data["user_id"])
    token_payload = {
        "client_id": config.DISCORD_CLIENT_ID,
        "client_secret": config.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _discord_redirect_uri(),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            DISCORD_TOKEN_URL,
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    token_response.raise_for_status()
    token_json = token_response.json()

    oauth_access_token = token_json.get("access_token")
    guild = token_json.get("guild") or {}
    guild_id = guild.get("id")
    guild_name = guild.get("name")
    discord_user_id = None
    discord_username = None
    if oauth_access_token:
        async with httpx.AsyncClient(timeout=30.0) as client:
            user_response = await client.get(
                f"{DISCORD_API}/users/@me",
                headers={"Authorization": f"Bearer {oauth_access_token}"},
            )
        user_response.raise_for_status()
        user_json = user_response.json()
        discord_user_id = user_json.get("id")
        discord_username = user_json.get("username")

    if not guild_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Discord gateway OAuth did not return a guild. "
                "Choose a server during bot installation and try again."
            ),
        )

    enc = _get_token_encryption()
    credentials = {
        "bot_token": config.DISCORD_BOT_TOKEN,
        "token_type": "bot",
        "scope": token_json.get("scope"),
    }
    cursor_state = {
        "guild_id": guild_id,
        "guild_name": guild_name,
        "application_id": config.DISCORD_CLIENT_ID,
        "scope": token_json.get("scope"),
        "permissions": str(DISCORD_GATEWAY_PERMISSIONS),
    }

    account = await get_discord_account_by_guild(session, guild_id=str(guild_id))
    if account is None:
        account = ExternalChatAccount(
            platform=ExternalChatPlatform.DISCORD,
            mode=ExternalChatAccountMode.CLOUD_SHARED,
            is_system_account=True,
            encrypted_credentials=enc.encrypt_token(json.dumps(credentials)),
            bot_username="Nowing",
            cursor_state=cursor_state,
            health_status=ExternalChatHealthStatus.UNKNOWN,
        )
        session.add(account)
        await session.flush()
    else:
        account.encrypted_credentials = enc.encrypt_token(json.dumps(credentials))
        account.cursor_state = {**(account.cursor_state or {}), **cursor_state}
        account.health_status = ExternalChatHealthStatus.UNKNOWN

    if discord_user_id:
        peer_id = discord_user_peer_id(str(guild_id), str(discord_user_id))
        existing_binding_result = await session.execute(
            select(ExternalChatBinding).where(
                ExternalChatBinding.account_id == account.id,
                ExternalChatBinding.external_peer_id == peer_id,
                ExternalChatBinding.state.in_(
                    [ExternalChatBindingState.BOUND, ExternalChatBindingState.SUSPENDED]
                ),
            )
        )
        binding = existing_binding_result.scalars().first()
        metadata = {
            "kind": "discord_user",
            "guild_id": guild_id,
            "guild_name": guild_name,
            "discord_user_id": discord_user_id,
        }
        if binding is None:
            session.add(
                ExternalChatBinding(
                    account_id=account.id,
                    user_id=user_id,
                    workspace_id=space_id,
                    state=ExternalChatBindingState.BOUND,
                    external_peer_id=peer_id,
                    external_peer_kind=ExternalChatPeerKind.DIRECT,
                    external_username=discord_username or discord_user_id,
                    external_metadata=metadata,
                )
            )
        elif binding.user_id == user_id:
            binding.workspace_id = space_id
            binding.external_username = discord_username or binding.external_username
            binding.external_metadata = {
                **(binding.external_metadata or {}),
                **metadata,
            }

    await session.commit()
    return _discord_frontend_redirect(space_id, success=True)
