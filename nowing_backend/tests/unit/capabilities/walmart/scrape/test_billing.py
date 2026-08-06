"""Billing integration for walmart.scrape."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _UNIT_NOUNS, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_walmart_product():
    assert BillingUnit.WALMART_PRODUCT.value == "walmart_product"


def test_walmart_product_rate_config_has_default():
    rate = _platform_rate(BillingUnit.WALMART_PRODUCT)
    assert rate == config.WALMART_SCRAPE_MICROS_PER_ITEM
    assert rate > 0


def test_billing_noun_is_product():
    assert _UNIT_NOUNS[BillingUnit.WALMART_PRODUCT] == "product"
