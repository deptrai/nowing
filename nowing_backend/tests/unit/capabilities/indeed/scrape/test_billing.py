"""Billing integration for indeed.scrape."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _UNIT_NOUNS, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_indeed_job():
    assert BillingUnit.INDEED_JOB.value == "indeed_job"


def test_indeed_rate_config_has_default():
    rate = _platform_rate(BillingUnit.INDEED_JOB)
    assert rate == config.INDEED_SCRAPE_MICROS_PER_ITEM
    assert rate > 0


def test_billing_noun_is_job():
    assert _UNIT_NOUNS[BillingUnit.INDEED_JOB] == "job"
