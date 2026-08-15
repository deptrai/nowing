"""Executor for ``leads.reverse_icp`` capability (Story 21.10)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core.types import CapabilityContext
from app.lead_intelligence.reverse_icp import ReverseIcpService
from app.lead_intelligence.schemas import ReverseIcpRequest, ReverseIcpResponse


def build_reverse_icp_executor() -> Callable[..., Awaitable[ReverseIcpResponse]]:
    """Construct async executor for leads.reverse_icp capability."""

    async def _execute(
        payload: ReverseIcpRequest | dict[str, Any],
        ctx: CapabilityContext,
    ) -> ReverseIcpResponse:
        req = (
            payload
            if isinstance(payload, ReverseIcpRequest)
            else ReverseIcpRequest.model_validate(payload)
        )
        service = ReverseIcpService()
        return await service.analyze_url(
            url=req.url,
            custom_instructions=req.custom_instructions,
        )

    return _execute
