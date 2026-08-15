"""Registration for ``ecommerce.track_price_history`` capability."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.ecommerce.price_history.executor import (
    build_track_price_history_executor,
)
from app.capabilities.ecommerce.price_history.schemas import (
    EcommercePriceHistoryInput,
    EcommercePriceHistoryOutput,
)

ECOMMERCE_TRACK_PRICE_HISTORY = Capability(
    name="ecommerce.track_price_history",
    description=(
        "Track historical price movements, calculate 90-day sparkline trends, and log price changes "
        "for products on Shopee Vietnam."
    ),
    input_schema=EcommercePriceHistoryInput,
    output_schema=EcommercePriceHistoryOutput,
    executor=build_track_price_history_executor(),
    billing_unit=BillingUnit.ECOMMERCE_PRODUCT,
    context_aware=True,
    docs_url="/docs/connectors/native/shopee",
)

register_capability(ECOMMERCE_TRACK_PRICE_HISTORY)
