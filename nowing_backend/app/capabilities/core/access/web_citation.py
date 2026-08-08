"""Register web source URLs as ``WEB_RESULT`` citations in the registry.

Used after a capability (e.g. ``chainlens.research``) returns a structured
output with a ``sources`` list — each URL becomes a citable ``[n]`` label
the model can reference, and the frontend renders as a ``UrlCitation`` chip.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.agents.chat.multi_agent_chat.shared.citations.models import CitationSourceType
from app.agents.chat.multi_agent_chat.shared.citations.registry import (
    CitationRegistry,
)


class _WebSource(Protocol):
    """Structural type for ``ResearchOutput.sources[]`` and similar shapes."""

    url: str
    title: str | None


def register_web_citations(
    registry: CitationRegistry,
    sources: Sequence[_WebSource],
) -> list[int]:
    """Register each source URL as a ``WEB_RESULT`` citation.

    Returns the list of ``[n]`` ordinals (one per source, in order). Sources
    with empty URLs are skipped. Duplicate URLs keep their existing ``[n]``
    via the registry's find-or-create semantics.
    """
    ordinals: list[int] = []
    for src in sources:
        url = (src.url or "").strip()
        if not url:
            continue
        n = registry.register(
            CitationSourceType.WEB_RESULT,
            {"url": url},
            {"title": src.title} if src.title else {},
        )
        ordinals.append(n)
    return ordinals


__all__ = ["register_web_citations"]
