"""``vn_bds.aggregate`` capability registration."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_aggregate_executor
from .schemas import VnBdsAggregateInput, VnBdsAggregateOutput

VN_BDS_AGGREGATE = Capability(
    name="vn_bds.aggregate",
    description=(
        "Aggregate and cross-score Vietnamese real-estate listings from "
        "batdongsan.com.vn, Chợ Tốt Nhà, and Muaban.net. Deduplicates by "
        "phone/address, detects price conflicts, and returns a normalized "
        "listing with a 0-1 confidence score."
    ),
    input_schema=VnBdsAggregateInput,
    output_schema=VnBdsAggregateOutput,
    executor=build_aggregate_executor(),
    billing_unit=BillingUnit.VN_BDS_AGGREGATE_QUERY,
    docs_url="/docs/connectors/native/vn_bds",
)

register_capability(VN_BDS_AGGREGATE)
