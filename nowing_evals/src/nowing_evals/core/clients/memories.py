"""Client for the long-term memory recall surface.

Verified against:

* ``nowing_backend/app/routes/memories_routes.py:33-71`` — ``POST
  /workspaces/{workspace_id}/memories`` (201, body = ``MemoryCreate``,
  response = ``MemoryRead``).
* ``nowing_backend/app/routes/memories_routes.py:74-121`` — ``POST
  /workspaces/{workspace_id}/memories/search`` (body =
  ``MemorySearchRequest``, response = ``MemorySearchResponse``).
* ``nowing_backend/app/schemas/memory.py:43-111`` — request/response schemas.

Story 3.9 scores this backend surface directly rather than the MCP
``nowing_recall`` tool: retrieval quality is measured without an LLM in the
loop (see story §9, "Recall surface choice"). The MCP contract is asserted
separately by the selfcheck (AC-7).

**Known contract wart (story §9):** ``MemorySearchHit`` declares a ``score``
field, but the route hardcodes ``score=0.0`` for every hit — the RRF fusion
score from ``MemoryHybridSearch`` is not propagated. ``search`` therefore
drops an all-zero ``score`` column so the recall oracle sees "no score" and
degrades to rank-only classification instead of scoring every hit as noise
against a non-zero ``min_similarity``. When the backend starts returning real
scores this becomes a no-op and the oracle picks the threshold back up.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _strip_placeholder_scores(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop ``score`` when the backend returned the hardcoded 0.0 placeholder.

    The route sets ``score=0.0`` unconditionally, so an all-zero column carries
    no ranking information. Removing the key lets the oracle fall back to rank
    position (top_k membership) rather than comparing 0.0 against a positive
    ``min_similarity`` and classifying every hit as noise.

    A genuinely all-zero *real* score column is indistinguishable from the
    placeholder, and treating it as "no signal" is the safe reading either way.
    """

    if not items:
        return items
    scores = [item.get("score") for item in items]
    if any(s is None for s in scores):
        return items
    try:
        if any(float(s) != 0.0 for s in scores):
            return items
    except (TypeError, ValueError):
        return items
    logger.debug(
        "memories/search returned an all-zero score column for %d hit(s); "
        "dropping it so the recall oracle uses rank position",
        len(items),
    )
    return [{k: v for k, v in item.items() if k != "score"} for item in items]


class MemoriesClient:
    """Create + search long-term memories for one workspace."""

    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    async def create(
        self,
        *,
        workspace_id: int,
        content: str,
        type_: str = "semantic",
        tags: list[str] | None = None,
        confidence: float = 1.0,
        source_type: str = "manual",
        source_id: int | None = None,
        research_thread_id: int | None = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/workspaces/{id}/memories`` → the created ``MemoryRead``.

        ``type_``/``source_type`` are validated server-side against the
        ``MemoryType``/``MemorySourceType`` enums; an invalid value surfaces as
        a 422 via ``raise_for_status``.
        """

        payload: dict[str, Any] = {
            "content": content,
            "type": type_,
            "source_type": source_type,
            "tags": list(tags or []),
            "confidence": confidence,
        }
        if source_id is not None:
            payload["source_id"] = source_id
        if research_thread_id is not None:
            payload["research_thread_id"] = research_thread_id

        response = await self._http.post(
            f"{self._base}/api/v1/workspaces/{workspace_id}/memories",
            json=payload,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    async def search(
        self,
        *,
        workspace_id: int,
        query: str,
        top_k: int = 5,
        type_: str | None = None,
        tags: list[str] | None = None,
        research_thread_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """``POST /api/v1/workspaces/{id}/memories/search`` → ranked ``items``.

        Returns the ranked hit list in backend order (rank 1 first). The
        backend clamps ``top_k`` to ``1..100``; the recall gate clamps to
        ``<= 5`` separately (RS-2). An all-zero placeholder ``score`` column is
        stripped — see the module docstring.
        """

        payload: dict[str, Any] = {"query": query, "top_k": top_k}
        if type_ is not None:
            payload["type"] = type_
        if tags:
            payload["tags"] = list(tags)
        if research_thread_id is not None:
            payload["research_thread_id"] = research_thread_id

        response = await self._http.post(
            f"{self._base}/api/v1/workspaces/{workspace_id}/memories/search",
            json=payload,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        return _strip_placeholder_scores([dict(item) for item in items])


__all__ = ["MemoriesClient"]
