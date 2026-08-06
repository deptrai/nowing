"""Billing integration for masothue.scrape."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _UNIT_NOUNS, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_masothue_billing_unit_noun() -> None:
    assert _UNIT_NOUNS[BillingUnit.MASOTHUE_COMPANY] == "company"


def test_masothue_default_rate() -> None:
    assert config.MASOTHUE_SCRAPE_MICROS_PER_ITEM == 3000


def test_masothue_platform_rate() -> None:
    rate = _platform_rate(BillingUnit.MASOTHUE_COMPANY)
    assert rate == 3000
