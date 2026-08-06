"""Billing integration for vn_jobs.aggregate."""

from __future__ import annotations

import pytest

from app.capabilities.core.billing import _JOBS_BILLING_UNIT_MAP, _platform_rate
from app.capabilities.core.types import BillingUnit
from app.config import config

pytestmark = pytest.mark.unit


def test_billing_unit_includes_vn_jobs_aggregate_query():
    assert BillingUnit.VN_JOBS_AGGREGATE_QUERY.value == "vn_jobs_aggregate_query"


def test_vn_jobs_aggregate_query_rate_config_has_default():
    rate = _platform_rate(BillingUnit.VN_JOBS_AGGREGATE_QUERY)
    assert rate == config.VN_JOBS_AGGREGATE_QUERY_MICROS_PER_QUERY
    assert rate > 0


def test_jobs_source_map_includes_all_sources():
    assert _JOBS_BILLING_UNIT_MAP == {
        "vietnamworks": BillingUnit.VIETNAMWORKS_JOB,
        "topcv": BillingUnit.TOPCV_JOB,
        "itviec": BillingUnit.ITVIEC_JOB,
        "indeed": BillingUnit.INDEED_JOB,
    }
