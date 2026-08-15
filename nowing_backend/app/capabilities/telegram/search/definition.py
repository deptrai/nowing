"""telegram.search capability registration (Story 22.1 / AD-1, AD-6)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.telegram.search.executor import (
    build_telegram_search_executor,
)
from app.capabilities.telegram.search.schemas import (
    TelegramSearchInput,
    TelegramSearchOutput,
)

TELEGRAM_SEARCH = Capability(
    name="telegram.search",
    description=(
        "Search and extract public Telegram channel messages via zero-login web preview. "
        "Supports filtering by keyword and intent ('sell', 'buy', 'seeking', 'news') "
        "with automatic extraction of Vietnamese phone numbers, emails, prices, and hashtags."
    ),
    input_schema=TelegramSearchInput,
    output_schema=TelegramSearchOutput,
    executor=build_telegram_search_executor(),
    billing_unit=BillingUnit.TELEGRAM_MESSAGE,
    docs_url="/docs/connectors/native/telegram",
)

register_capability(TELEGRAM_SEARCH)
