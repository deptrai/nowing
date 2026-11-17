"""Executor for chainlens.pulse_research capability (Story 20.11).

Reuses the incremental SSE parser and ResearchOutput from
``chainlens.research`` — the wire contract is identical
(``init`` → ``text_delta`` → ``done{usage, chatId}``).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from app.capabilities.chainlens.pulse_research.schemas import PulseResearchInput
from app.capabilities.chainlens.research.schemas import ResearchOutput
from app.capabilities.chainlens.research.sse_parser import _parse_sse
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.services.chainlens.auth import get_chainlens_auth

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class ChainLensPulseResearchError(Exception):
    """Raised when the pulse research engine is unavailable (5xx)."""


class ChainLensPulseResearchNotFoundError(Exception):
    """Raised when the requested item or angle does not exist (404)."""


class PulseResearchExecutor:
    """Executes angle deep-research streams against ChainLens Pulse."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (
            base_url
            or getattr(config, "CHAINLENS_API_URL", "http://localhost:3001")
        ).rstrip("/")

    async def stream_research(
        self,
        input_data: PulseResearchInput,
        context: CapabilityContext | None = None,
    ) -> AsyncIterator[str]:
        """Yield raw SSE lines from ChainLens pulse research.

        The yielded lines are the SAME block-based SSE contract as
        ``chainlens.research`` — feed them to ``_parse_sse`` for parsing.
        """
        workspace_id = getattr(context, "workspace_id", 0) if context else 0
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "text/event-stream"

        payload = {
            "itemId": input_data.item_id,
            "angleId": input_data.angle_id,
            "mode": input_data.mode,
            "output": "news",
        }
        if input_data.chat_id:
            payload["chatId"] = input_data.chat_id

        url = f"{self.base_url}/v1/pulse/research"
        async with (
            httpx.AsyncClient(timeout=300.0) as client,
            client.stream("POST", url, json=payload, headers=headers) as response,
        ):
            if response.status_code >= 500:
                raise ChainLensPulseResearchError(
                    f"Pulse research engine unavailable ({response.status_code})"
                )
            if response.status_code == 404:
                raise ChainLensPulseResearchNotFoundError(
                    f"Item or angle not found: {input_data.item_id}/{input_data.angle_id}"
                )

            async for line in response.aiter_lines():
                yield line


def build_pulse_research_executor():
    """Factory creating the pulse research executor callable."""
    executor = PulseResearchExecutor()

    async def _execute(
        input_data: PulseResearchInput,
        context: CapabilityContext | None = None,
    ) -> ResearchOutput:
        lines = executor.stream_research(input_data, context)
        # Reuse the shared research SSE parser — same wire contract.
        result = _parse_sse(lines)
        if hasattr(result, "__await__"):
            result = await result
        return result

    return _execute
