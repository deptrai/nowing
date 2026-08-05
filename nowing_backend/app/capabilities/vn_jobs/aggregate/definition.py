"""``vn_jobs.aggregate`` capability registration."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_aggregate_executor
from .schemas import VnJobAggregateInput, VnJobAggregateOutput

VN_JOBS_AGGREGATE = Capability(
    name="vn_jobs.aggregate",
    description=(
        "Aggregate and compare Vietnamese job postings from VietnamWorks, "
        "TopCV, and ITviec. Returns a normalized, deduplicated, "
        "confidence-scored view. Research use only."
    ),
    input_schema=VnJobAggregateInput,
    output_schema=VnJobAggregateOutput,
    executor=build_aggregate_executor(),
    billing_unit=BillingUnit.VN_JOBS_AGGREGATE_QUERY,
    docs_url="/docs/connectors/native/vn_jobs",
)

register_capability(VN_JOBS_AGGREGATE)
