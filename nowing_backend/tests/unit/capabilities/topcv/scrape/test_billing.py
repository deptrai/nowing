"""Billing integration for topcv.scrape."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _UNIT_NOUNS, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_topcv_job():
    assert BillingUnit.TOPCV_JOB.value == "topcv_job"


def test_topcv_rate_config_has_default():
    rate = _platform_rate(BillingUnit.TOPCV_JOB)
    assert rate == config.TOPCV_SCRAPE_MICROS_PER_ITEM
    assert rate > 0


def test_billing_noun_is_job():
    assert _UNIT_NOUNS[BillingUnit.TOPCV_JOB] == "job"
