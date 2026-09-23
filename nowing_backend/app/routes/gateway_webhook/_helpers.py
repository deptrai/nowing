"""Messaging gateway routes."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

from fastapi import HTTPException
from starlette.responses import RedirectResponse

from app.config import config
from app.db import (
    ExternalChatAccount,
    ExternalChatAccountMode,
    ExternalChatPlatform,
)
from app.utils.oauth_security import OAuthStateManager, TokenEncryption

logger = logging.getLogger(__name__)
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


def _get_state_manager() -> OAuthStateManager:
    global _state_manager
    if _state_manager is None:
        if not config.SECRET_KEY:
            raise HTTPException(status_code=500, detail="SECRET_KEY is not configured")
        _state_manager = OAuthStateManager(config.SECRET_KEY)
    return _state_manager


def _get_token_encryption() -> TokenEncryption:
    global _token_encryption
    if _token_encryption is None:
        if not config.SECRET_KEY:
            raise HTTPException(status_code=500, detail="SECRET_KEY is not configured")
        _token_encryption = TokenEncryption(config.SECRET_KEY)
    return _token_encryption


def _slack_redirect_uri() -> str:
    if config.GATEWAY_SLACK_REDIRECT_URI:
        return config.GATEWAY_SLACK_REDIRECT_URI
    base = config.BACKEND_URL or ""
    return f"{base.rstrip('/')}/api/v1/gateway/slack/callback"


def _discord_redirect_uri() -> str:
    if config.GATEWAY_DISCORD_REDIRECT_URI:
        return config.GATEWAY_DISCORD_REDIRECT_URI
    base = config.BACKEND_URL or ""
    return f"{base.rstrip('/')}/api/v1/gateway/discord/callback"


def _slack_frontend_redirect(
    space_id: int, *, success: bool = False, error: str | None = None
) -> RedirectResponse:
    qs = (
        "slack_gateway=connected"
        if success
        else f"error={error or 'slack_gateway_failed'}"
    )
    return RedirectResponse(
        url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/user-settings?{qs}"
    )


def _discord_frontend_redirect(
    space_id: int, *, success: bool = False, error: str | None = None
) -> RedirectResponse:
    qs = (
        "discord_gateway=connected"
        if success
        else f"error={error or 'discord_gateway_failed'}"
    )
    return RedirectResponse(
        url=f"{config.NEXT_FRONTEND_URL}/dashboard/{space_id}/user-settings?{qs}"
    )


def verify_slack_signature(
    *, signing_secret: str, timestamp: str | None, signature: str | None, body: bytes
) -> bool:
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > 60 * 5:
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    digest = hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)


def _slack_event_kind(payload: dict[str, Any]) -> str:
    event_type = str((payload.get("event") or {}).get("type") or "")
    return "message" if event_type in {"app_mention", "message"} else "other"


def _active_whatsapp_account_mode() -> ExternalChatAccountMode | None:
    if config.GATEWAY_WHATSAPP_INTAKE_MODE == "cloud":
        return ExternalChatAccountMode.CLOUD_SHARED
    if config.GATEWAY_WHATSAPP_INTAKE_MODE == "baileys":
        return ExternalChatAccountMode.SELF_HOST_BYO
    return None


def _is_inactive_whatsapp_account(account: ExternalChatAccount) -> bool:
    return (
        account.platform == ExternalChatPlatform.WHATSAPP
        and account.mode != _active_whatsapp_account_mode()
    )


def _telegram_gateway_enabled() -> bool:
    return (
        config.GATEWAY_TELEGRAM_INTAKE_MODE != "disabled"
        and bool(config.TELEGRAM_SHARED_BOT_TOKEN)
        and bool(config.TELEGRAM_SHARED_BOT_USERNAME)
        and (
            config.GATEWAY_TELEGRAM_INTAKE_MODE != "webhook"
            or bool(config.TELEGRAM_WEBHOOK_SECRET)
        )
    )


def _slack_gateway_enabled() -> bool:
    return bool(
        config.GATEWAY_SLACK_ENABLED
        and config.GATEWAY_SLACK_CLIENT_ID
        and config.GATEWAY_SLACK_CLIENT_SECRET
        and config.GATEWAY_SLACK_SIGNING_SECRET
    )


def _discord_gateway_enabled() -> bool:
    return bool(
        config.GATEWAY_DISCORD_ENABLED
        and config.DISCORD_CLIENT_ID
        and config.DISCORD_CLIENT_SECRET
        and config.DISCORD_BOT_TOKEN
    )


def _classify_telegram_event(payload: dict[str, Any]) -> str:
    if "message" in payload:
        return "message"
    if "edited_message" in payload:
        return "edited_message"
    if "callback_query" in payload:
        return "callback_query"
    return "other"


def _telegram_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    if "message" in payload:
        return payload["message"]
    if "edited_message" in payload:
        return payload["edited_message"]
    callback_query = payload.get("callback_query")
    if isinstance(callback_query, dict):
        return callback_query.get("message")
    return None
