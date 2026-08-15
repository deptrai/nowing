"""Capability registration for ``procurement.summarize``."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.procurement.summarize.executor import (
    build_procurement_summarize_executor,
)
from app.capabilities.procurement.summarize.schemas import (
    ProcurementSummarizeInput,
    ProcurementSummarizeOutput,
)

PROCUREMENT_SUMMARIZE = Capability(
    name="procurement.summarize",
    description=(
        "Summarize bidding dossier (E-HSMT) requirements for a given TBMT bid_no. "
        "Extracts 4 core criteria (Annual turnover, Similar contracts, Key personnel, "
        "Bid security guarantee) and provides real-time deadline countdown."
    ),
    input_schema=ProcurementSummarizeInput,
    output_schema=ProcurementSummarizeOutput,
    executor=build_procurement_summarize_executor(),
    billing_unit=BillingUnit.PROCUREMENT_HSMT,
    docs_url="/docs/capabilities/procurement",
)

register_capability(PROCUREMENT_SUMMARIZE)
