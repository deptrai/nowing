"""Billing registration for the Muaban BĐS scrape capability."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _PLATFORM_RATE_KEYS, _UNIT_NOUNS
from app.capabilities.core.types import BillingUnit

pytestmark = pytest.mark.unit


def test_muaban_bds_billing_unit_is_registered():
    assert BillingUnit.MUABAN_BDS_ITEM == "muaban_bds_item"
    assert _PLATFORM_RATE_KEYS[BillingUnit.MUABAN_BDS_ITEM]
    assert _UNIT_NOUNS[BillingUnit.MUABAN_BDS_ITEM] == "listing"
