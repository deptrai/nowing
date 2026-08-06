"""Billing integration for walmart.reviews."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _UNIT_NOUNS, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_walmart_review():
    assert BillingUnit.WALMART_REVIEW.value == "walmart_review"


def test_walmart_review_rate_config_has_default():
    rate = _platform_rate(BillingUnit.WALMART_REVIEW)
    assert rate == config.WALMART_REVIEW_MICROS_PER_ITEM
    assert rate > 0


def test_billing_noun_is_review():
    assert _UNIT_NOUNS[BillingUnit.WALMART_REVIEW] == "review"
