"""Capability registration for ``procurement.search``."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.procurement.search.executor import (
    build_procurement_search_executor,
)
from app.capabilities.procurement.search.schemas import (
    ProcurementSearchInput,
    ProcurementSearchOutput,
)

PROCUREMENT_SEARCH = Capability(
    name="procurement.search",
    description=(
        "Search national public procurement tenders (TBMT) from muasamcong.mpi.gov.vn. "
        "Filter by keywords, procurement field (Xây lắp, Mua sắm hàng hóa, Dịch vụ tư vấn), "
        "estimated price range, and location."
    ),
    input_schema=ProcurementSearchInput,
    output_schema=ProcurementSearchOutput,
    executor=build_procurement_search_executor(),
    billing_unit=BillingUnit.PROCUREMENT_QUERY,
    docs_url="/docs/capabilities/procurement",
)

register_capability(PROCUREMENT_SEARCH)
