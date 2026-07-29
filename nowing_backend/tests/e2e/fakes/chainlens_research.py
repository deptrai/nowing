"""Stub ChainLens Research executor for E2E.

The real ``chainlens.research`` capability calls an upstream service that
requires ``CHAINLENS_API_KEY``. In a hermetic E2E environment that key is not
available, so any chat turn that invokes the research tool would fail with
``ConfigurationError``. This stub returns a deterministic ResearchOutput so web
smoke tests can exercise the full chat flow.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from app.capabilities.chainlens.research.schemas import ResearchInput, ResearchOutput

logger = logging.getLogger(__name__)


async def fake_research_executor(payload: ResearchInput) -> ResearchOutput:
    """Return a canned ChainLens Research response for E2E."""
    logger.info(
        "[fake-chainlens-research] query=%r mode=%r sources=%r history_len=%d",
        payload.query,
        payload.mode,
        payload.sources,
        len(payload.history),
    )
    return ResearchOutput(
        answer=f"This is an E2E fake research answer for: {payload.query}",
        sources=[
            {
                "title": "E2E Source",
                "url": "https://example.com",
            }
        ],
        status="complete",
    )


def install(patches: list[Any]) -> None:
    """Replace the live ``chainlens.research`` executor with the fake one.

    The capability is a frozen dataclass registered at import time, so we
    replace it with a fresh instance and also update the agent tool list that
    already captured a reference to the original.
    """
    from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools import (
        index as chainlens_tools_index,
    )
    from app.capabilities.chainlens.research import definition as chainlens_definition
    from app.capabilities.core import store as capability_store

    original = chainlens_definition.CHAINLENS_RESEARCH
    patched = dataclasses.replace(original, executor=fake_research_executor)

    chainlens_definition.CHAINLENS_RESEARCH = patched
    capability_store._REGISTRY["chainlens.research"] = patched

    # The chainlens subagent tool module captured the original reference.
    if getattr(chainlens_tools_index, "_CI_VERBS", None):
        chainlens_tools_index._CI_VERBS[0] = patched

    logger.info("[fake-chainlens-research] installed stub for chainlens.research")
