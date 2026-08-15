"""E-commerce product capabilities (Story 17.2)."""

from __future__ import annotations

from app.capabilities.ecommerce import (
    price_history as _price_history,  # noqa: F401
    search as _search,  # noqa: F401
)
from app.capabilities.ecommerce.price_history.definition import (
    ECOMMERCE_TRACK_PRICE_HISTORY,
)
from app.capabilities.ecommerce.search.definition import ECOMMERCE_SEARCH_PRODUCTS

__all__ = [
    "ECOMMERCE_SEARCH_PRODUCTS",
    "ECOMMERCE_TRACK_PRICE_HISTORY",
]
