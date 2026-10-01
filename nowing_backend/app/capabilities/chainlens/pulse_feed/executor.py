"""Executor for chainlens.pulse_feed capability (Story 20.10)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.capabilities.chainlens.pulse_feed.schemas import (
    PulseAngleResponse,
    PulseFeedInput,
    PulseFeedOutput,
)
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.services.chainlens.auth import get_chainlens_auth

logger = logging.getLogger(__name__)


class PulseFeedExecutor:
    """Executes calls to ChainLens /v1/pulse/feed and /v1/pulse/items/{id}/angles."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (
            base_url
            or getattr(config, "CHAINLENS_API_URL", "http://localhost:3001")
        ).rstrip("/")

    async def execute(
        self,
        input_data: PulseFeedInput,
        context: CapabilityContext | None = None,
    ) -> PulseFeedOutput:
        workspace_id = getattr(context, "workspace_id", 0) if context else 0
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)

        params: dict[str, Any] = {"limit": input_data.limit}
        if input_data.topic and input_data.topic != "all":
            params["topic"] = input_data.topic
        if input_data.cursor:
            params["cursor"] = input_data.cursor

        url = f"{self.base_url}/v1/pulse/feed"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.get(url, params=params, headers=headers)
                if not res.is_success:
                    logger.warning(
                        "[PulseFeed] Failed to fetch feed (%s): %s",
                        res.status_code,
                        res.text,
                    )
                    return PulseFeedOutput()

                data = res.json()
                return PulseFeedOutput.model_validate(data)
            except Exception as exc:
                logger.error("[PulseFeed] Network error fetching feed: %s", exc)
                return PulseFeedOutput()

    async def get_item_angles(
        self,
        item_id: str,
        workspace_id: int = 0,
    ) -> list[PulseAngleResponse]:
        """Fetch pre-generated research angles for a specific pulse feed item."""
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)

        url = f"{self.base_url}/v1/pulse/items/{item_id}/angles"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.get(url, headers=headers)
                if not res.is_success:
                    return []
                items = res.json()
                return [PulseAngleResponse.model_validate(a) for a in items]
            except Exception as exc:
                logger.warning(
                    "[PulseFeed] Failed to fetch angles for item %s: %s", item_id, exc
                )
                return []


def build_pulse_feed_executor():
    """Factory creating the pulse feed executor callable."""
    executor = PulseFeedExecutor()

    async def _execute(
        input_data: PulseFeedInput,
        context: CapabilityContext | None = None,
    ) -> PulseFeedOutput:
        return await executor.execute(input_data, context)

    return _execute
