"""Register the ``lead.enrich`` capability (Story 21.3)."""

from __future__ import annotations

from app.capabilities.core import Capability, register_capability
from app.capabilities.core.types import CapabilityContext
from app.lead_intelligence.enrichment.schemas import (
    EnrichmentInput,
    EnrichmentOutput,
)
from app.lead_intelligence.enrichment.service import EnrichmentService


async def _lead_enrich_executor(
    payload: EnrichmentInput,
    ctx: CapabilityContext,
) -> EnrichmentOutput:
    """Capability adapter for ``EnrichmentService.enrich``."""
    service = EnrichmentService()
    lead_id = payload.lead_id
    if lead_id is None and payload.lead_ids:
        lead_id = payload.lead_ids[0]
    if lead_id is None:
        return EnrichmentOutput(
            enrichment_request_id=None,
            lead_id=None,
            contact_count=0,
            cost_micros=0,
            verified_contact_ids=[],
            degraded=True,
            degradation_reasons=["lead_not_found"],
        )
    return await service.enrich(
        session=ctx.session,
        ctx=ctx,
        lead_id=lead_id,
        requested_count=payload.requested_count,
    )


LEAD_ENRICH = Capability(
    name="lead.enrich",
    description="Enrich a lead with verified contact details via a provider waterfall.",
    input_schema=EnrichmentInput,
    output_schema=EnrichmentOutput,
    executor=_lead_enrich_executor,
    billing_unit=None,
    context_aware=True,
    docs_url="/docs/lead-intelligence/enrichment",
    metadata={
        "emits_leads": False,
        "requires_pii_redaction_context": "lead_enrichment",
    },
)

register_capability(LEAD_ENRICH)
