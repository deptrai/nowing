"""Messaging gateway routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.auth.context import AuthContext
from app.config import config
from app.users import get_auth_context

from ._helpers import (
    _discord_gateway_enabled,
    _slack_gateway_enabled,
    _telegram_gateway_enabled,
)

logger = logging.getLogger(__name__)
config_router = APIRouter(prefix="/gateway", tags=["gateway"])


@config_router.get("/config")
async def get_gateway_config(
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, bool | str]:
    if not config.GATEWAY_ENABLED:
        return {
            "enabled": False,
            "telegram_enabled": False,
            "whatsapp_intake_mode": "disabled",
            "slack_enabled": False,
            "discord_enabled": False,
        }
    return {
        "enabled": True,
        "telegram_enabled": _telegram_gateway_enabled(),
        "whatsapp_intake_mode": config.GATEWAY_WHATSAPP_INTAKE_MODE,
        "slack_enabled": _slack_gateway_enabled(),
        "discord_enabled": _discord_gateway_enabled(),
    }
