"""Billing integration for vietnamworks.scrape."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _UNIT_NOUNS, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_vietnamworks_job():
    assert BillingUnit.VIETNAMWORKS_JOB.value == "vietnamworks_job"


def test_vietnamworks_rate_config_has_default():
    rate = _platform_rate(BillingUnit.VIETNAMWORKS_JOB)
    assert rate == config.VIETNAMWORKS_SCRAPE_MICROS_PER_ITEM
    assert rate > 0


def test_billing_noun_is_job():
    assert _UNIT_NOUNS[BillingUnit.VIETNAMWORKS_JOB] == "job"
