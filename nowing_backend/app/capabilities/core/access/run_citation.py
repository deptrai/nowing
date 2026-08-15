"""Attach a completed scraper run to the citation registry as a citable source."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations.models import CitationSourceType
from app.agents.chat.multi_agent_chat.shared.citations.registry import (
    CitationRegistry,
)


def attach_run_citation(
    registry: CitationRegistry,
    *,
    run_external_id: str,
    capability: str,
) -> tuple[int, str]:
    """Register a ``RUN`` citation and return its ``[n]`` ordinal + label line."""
    n = registry.register(
        CitationSourceType.RUN,
        {"run_id": run_external_id},
        {"capability": capability},
    )
    label = f"\n\nCite this scraper run as [{n}] after any claim drawn from its data."
    return n, label


__all__ = ["attach_run_citation"]
