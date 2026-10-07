"""Billing integration for itviec.scrape."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _UNIT_NOUNS, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_itviec_job():
    assert BillingUnit.ITVIEC_JOB.value == "itviec_job"


def test_itviec_rate_config_has_default():
    rate = _platform_rate(BillingUnit.ITVIEC_JOB)
    assert rate == config.ITVIEC_SCRAPE_MICROS_PER_ITEM
    assert rate > 0


def test_billing_noun_is_job():
    assert _UNIT_NOUNS[BillingUnit.ITVIEC_JOB] == "job"
