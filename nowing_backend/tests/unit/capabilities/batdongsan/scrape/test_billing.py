"""Unit tests for Batdongsan billing registration."""

from __future__ import annotations

import pytest

from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_batdongsan_item():
    assert hasattr(BillingUnit, "BATDONGSAN_ITEM")
    assert BillingUnit.BATDONGSAN_ITEM.value == "batdongsan_item"


def test_batdongsan_rate_config_has_default():
    assert hasattr(config, "BATDONGSAN_SCRAPE_MICROS_PER_ITEM")
    assert config.BATDONGSAN_SCRAPE_MICROS_PER_ITEM == 3500
