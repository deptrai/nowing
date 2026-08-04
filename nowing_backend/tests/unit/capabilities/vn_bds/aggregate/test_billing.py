"""Unit tests for the ``vn_bds.aggregate`` billing registration."""

from __future__ import annotations

import pytest

from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_vn_bds_aggregate_query():
    assert hasattr(BillingUnit, "VN_BDS_AGGREGATE_QUERY")
    assert BillingUnit.VN_BDS_AGGREGATE_QUERY.value == "vn_bds_aggregate_query"


def test_aggregate_query_rate_config_has_default():
    assert hasattr(config, "VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY")
    assert config.VN_BDS_AGGREGATE_QUERY_MICROS_PER_QUERY == 5000
