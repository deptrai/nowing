"""Executor for ``leads.multi_source_gen`` capability (Story 21.15)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.lead_intelligence.schemas import (
    MultiSourceLeadGenRequest,
    MultiSourceLeadGenResponse,
)
from app.lead_intelligence.services.lead_gen_orchestrator import (
    LeadGenOrchestrator,
)


def build_multi_source_lead_gen_executor() -> Callable[
    ..., Awaitable[MultiSourceLeadGenResponse]
]:
    """Construct async executor for leads.multi_source_gen capability."""

    async def _execute(
        payload: MultiSourceLeadGenRequest | dict[str, Any],
        ctx: CapabilityContext,
    ) -> MultiSourceLeadGenResponse:
        req = (
            payload
            if isinstance(payload, MultiSourceLeadGenRequest)
            else MultiSourceLeadGenRequest.model_validate(payload)
        )
        orchestrator = LeadGenOrchestrator()
        result = await orchestrator.execute_and_persist(
            session=ctx.session,
            workspace_id=ctx.workspace_id,
            query=req.query,
            table_id=req.table_id,
            limit=req.limit,
            filters={"locations": req.locations} if req.locations else None,
        )
        return MultiSourceLeadGenResponse(
            status=result.status,
            total_discovered=result.total_discovered,
            total_deduplicated=result.total_deduplicated,
            leads=[item.model_dump() for item in result.leads],
            degraded_sources=result.degraded_sources,
            table_id=result.table_id,
        )

    return _execute
