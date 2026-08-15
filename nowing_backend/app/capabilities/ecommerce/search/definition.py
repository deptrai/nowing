"""Registration for ``ecommerce.search_products`` capability."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.ecommerce.search.executor import build_search_executor
from app.capabilities.ecommerce.search.schemas import (
    EcommerceSearchInput,
    EcommerceSearchOutput,
)

ECOMMERCE_SEARCH_PRODUCTS = Capability(
    name="ecommerce.search_products",
    description=(
        "Search Vietnamese e-commerce products on Shopee by keyword with exact price normalization, "
        "ratings, sold counts, and discount percentages."
    ),
    input_schema=EcommerceSearchInput,
    output_schema=EcommerceSearchOutput,
    executor=build_search_executor(),
    billing_unit=BillingUnit.ECOMMERCE_PRODUCT,
    docs_url="/docs/connectors/native/shopee",
)

register_capability(ECOMMERCE_SEARCH_PRODUCTS)
