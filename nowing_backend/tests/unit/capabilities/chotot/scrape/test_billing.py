"""Unit tests for Chotot BĐS billing registration."""

from __future__ import annotations

import pytest

from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_chotot_bds_item():
    assert hasattr(BillingUnit, "CHOTOT_BDS_ITEM")
    assert BillingUnit.CHOTOT_BDS_ITEM.value == "chotot_bds_item"


def test_chotot_bds_rate_config_has_default():
    assert hasattr(config, "CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM")
    assert config.CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM == 3500
