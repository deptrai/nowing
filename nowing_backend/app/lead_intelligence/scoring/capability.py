"""Register the ``lead.score`` capability (Story 21.2)."""

from __future__ import annotations

from app.capabilities.core import BillingUnit, Capability, register_capability
from app.capabilities.core.types import CapabilityContext
from app.lead_intelligence.scoring.schemas import LeadScoreInput, LeadScoreOutput
from app.lead_intelligence.scoring.service import LeadScoringService


async def _lead_score_executor(
    payload: LeadScoreInput,
    ctx: CapabilityContext,
) -> LeadScoreOutput:
    """Capability adapter for ``LeadScoringService.score``."""
    service = LeadScoringService()
    return await service.score(
        session=ctx.session,
        ctx=ctx,
        inp=payload,
    )


LEAD_SCORE = Capability(
    name="lead.score",
    description="Calculate and persist composite fit + intent scores for leads.",
    input_schema=LeadScoreInput,
    output_schema=LeadScoreOutput,
    executor=_lead_score_executor,
    billing_unit=BillingUnit.LEAD_SCORE,
    context_aware=True,
    docs_url="/docs/lead-intelligence/scoring",
)

register_capability(LEAD_SCORE)
