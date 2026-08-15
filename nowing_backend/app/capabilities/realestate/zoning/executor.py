"""Capability executor for realestate.zoning (Story 10.8 / AD-GIS-4 / AD-GIS-6)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.capabilities.realestate.zoning.schemas import (
    ZoningCheckInput,
    ZoningCheckOutput,
)
from app.db import async_session_maker
from app.proprietary.platforms.spatial_planning.service import SpatialPlanningService

if TYPE_CHECKING:
    from app.capabilities.core.types import CapabilityContext

logger = logging.getLogger(__name__)


def build_zoning_executor(service: SpatialPlanningService | None = None):
    """Builds the async capability executor for checking real estate zoning."""
    planning_service = service or SpatialPlanningService()

    async def _execute(
        payload: ZoningCheckInput,
        ctx: CapabilityContext | None = None,
    ) -> ZoningCheckOutput:
        if ctx is not None and getattr(ctx, "session", None) is not None:
            result = await planning_service.check_zoning(
                session=ctx.session,
                lat=payload.latitude,
                lng=payload.longitude,
                address=payload.address,
            )
        else:
            async with async_session_maker() as session:
                result = await planning_service.check_zoning(
                    session=session,
                    lat=payload.latitude,
                    lng=payload.longitude,
                    address=payload.address,
                )

        return ZoningCheckOutput(
            latitude=result.latitude,
            longitude=result.longitude,
            address=payload.address,
            has_road_expansion_risk=result.has_road_expansion_risk,
            zones=result.zones,
            summary=result.summary,
            risk_notes=result.risk_notes,
            query_latency_ms=result.query_latency_ms,
        )

    return _execute
