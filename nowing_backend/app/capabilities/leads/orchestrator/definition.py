"""Registration of the ``leads.multi_source_gen`` capability (Story 21.15)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.leads.orchestrator.executor import (
    build_multi_source_lead_gen_executor,
)
from app.lead_intelligence.schemas import (
    MultiSourceLeadGenRequest,
    MultiSourceLeadGenResponse,
)

LEADS_MULTI_SOURCE_GEN = Capability(
    name="leads.multi_source_gen",
    description="Unified multi-source AI lead generation across Batdongsan, Chợ Tốt, Mua Bán, TopCV, ITviec, VietnamWorks, Masothue, Mua Sắm Công, and Social groups with deduplication.",
    input_schema=MultiSourceLeadGenRequest,
    output_schema=MultiSourceLeadGenResponse,
    executor=build_multi_source_lead_gen_executor(),
    billing_unit=None,
    docs_url="/docs/lead-intelligence/multi-source-lead-gen",
)

register_capability(LEADS_MULTI_SOURCE_GEN)
