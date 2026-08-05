"""The vn_jobs namespace registers its verb as one Capability the doors/agent read."""

from __future__ import annotations

import pytest

from app.capabilities import (
    vn_jobs,  # noqa: F401
)
from app.capabilities.core import BillingUnit
from app.capabilities.core.store import get_capability
from app.capabilities.vn_jobs.aggregate.schemas import (
    VnJobAggregateInput,
    VnJobAggregateOutput,
)

pytestmark = pytest.mark.unit


def test_vn_jobs_aggregate_is_registered_and_billable():
    cap = get_capability("vn_jobs.aggregate")

    assert cap.name == "vn_jobs.aggregate"
    assert cap.input_schema is VnJobAggregateInput
    assert cap.output_schema is VnJobAggregateOutput
    assert cap.billing_unit is BillingUnit.VN_JOBS_AGGREGATE_QUERY
