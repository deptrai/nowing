"""Registration of the ``leads.reverse_icp`` capability (Story 21.10)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.leads.reverse_icp.executor import build_reverse_icp_executor
from app.lead_intelligence.schemas import ReverseIcpRequest, ReverseIcpResponse

LEADS_REVERSE_ICP = Capability(
    name="leads.reverse_icp",
    description="Analyze a website URL or project landing page to extract Ideal Customer Profile, Buyer Personas, and search queries.",
    input_schema=ReverseIcpRequest,
    output_schema=ReverseIcpResponse,
    executor=build_reverse_icp_executor(),
    billing_unit=None,
    docs_url="/docs/lead-intelligence/reverse-icp",
)

register_capability(LEADS_REVERSE_ICP)
