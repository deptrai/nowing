"""Zalo Gateway Package (Story 21.6 / AD-41)."""

from app.gateway.zalo.client import (
    ZALO_OPENAPI_BASE,
    ZALO_RATE_LIMIT_PER_MINUTE,
    ZaloClient,
    format_vietnam_phone,
    generate_assisted_outbound_draft,
)
from app.gateway.zalo.telegram_alerts import (
    build_lead_telegram_alert,
    send_telegram_lead_alert,
)
from app.gateway.zalo.webhook import (
    detect_buying_intent,
    handle_zalo_webhook_event,
    verify_zalo_signature,
)

__all__ = [
    "ZALO_OPENAPI_BASE",
    "ZALO_RATE_LIMIT_PER_MINUTE",
    "ZaloClient",
    "build_lead_telegram_alert",
    "detect_buying_intent",
    "format_vietnam_phone",
    "generate_assisted_outbound_draft",
    "handle_zalo_webhook_event",
    "send_telegram_lead_alert",
    "verify_zalo_signature",
]
