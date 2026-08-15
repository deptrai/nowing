"""Capability registration for ``social.search_leads`` (Story 21.8 / AC 5)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability

from .executor import build_search_leads_executor
from .schemas import SocialSearchLeadsInput, SocialSearchLeadsOutput

SOCIAL_SEARCH_LEADS = Capability(
    name="social.search_leads",
    description=(
        "Search captured social posts (Facebook Groups, Twitter feeds) for high-intent "
        "leads with extracted Vietnamese phone numbers, emails, prices, and locations."
    ),
    input_schema=SocialSearchLeadsInput,
    output_schema=SocialSearchLeadsOutput,
    executor=build_search_leads_executor(),
    billing_unit=BillingUnit.SOCIAL_LEAD_ITEM,
    docs_url="/docs/capabilities/social/search_leads",
)

register_capability(SOCIAL_SEARCH_LEADS)
