"""Compat shim — gateway webhook routes split into ``app/routes/gateway_webhook/``.

Keeps ``from app.routes.gateway_webhook_routes import router, config_router``
working and re-exports symbols historically imported from this module.
"""

from fastapi import HTTPException

from app.config import config
from app.routes.gateway_webhook import config_router, router
from app.routes.gateway_webhook._helpers import verify_slack_signature
from app.routes.gateway_webhook.bindings import (
    SendBindingMessageRequest,
    send_message_to_binding,
)
from app.routes.gateway_webhook.oauth import (
    discord_gateway_callback,
    install_discord_gateway,
)
from app.routes.gateway_webhook.webhooks import (
    _resolve_webhook_account,
    slack_webhook,
    telegram_webhook,
)

__all__ = [
    "HTTPException",
    "SendBindingMessageRequest",
    "_resolve_webhook_account",
    "config",
    "config_router",
    "discord_gateway_callback",
    "install_discord_gateway",
    "router",
    "send_message_to_binding",
    "slack_webhook",
    "telegram_webhook",
    "verify_slack_signature",
]
