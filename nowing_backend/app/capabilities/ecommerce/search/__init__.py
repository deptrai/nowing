"""Search products capability module."""

from __future__ import annotations

from .definition import ECOMMERCE_SEARCH_PRODUCTS
from .schemas import EcommerceProductItem, EcommerceSearchInput, EcommerceSearchOutput

__all__ = [
    "ECOMMERCE_SEARCH_PRODUCTS",
    "EcommerceProductItem",
    "EcommerceSearchInput",
    "EcommerceSearchOutput",
]
