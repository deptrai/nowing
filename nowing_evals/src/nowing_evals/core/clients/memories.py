"""Client for workspace-scoped long-term memory endpoints.

Verified against ``nowing_backend/app/routes/memories_routes.py`` and
``nowing_backend/app/schemas/memory.py``. Memory endpoints are scoped by a
product ``workspace_id``; this is intentionally distinct from the eval
harness's ``search_space_id``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import httpx

# Mirrors ``MemorySourceType`` in ``nowing_backend/app/db.py``. Notably there is
# no "eval" member, so eval fixtures are identified by a reserved tag instead
# (see ``suites/memory/recall/ingest.EVAL_TAG``).
VALID_SOURCE_TYPES = frozenset(
    {"document", "chat_message", "scraper_run", "manual", "unknown"}
)

# ``MemorySearchRequest.top_k`` is constrained ``ge=1, le=100`` server-side.
_MIN_TOP_K = 1
_MAX_TOP_K = 100


class MemoriesClient:
    """Thin wrapper around create, ranked search and delete memory endpoints."""

    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base = base_url.rstrip("/")

    def _decode(self, response: httpx.Response, *, what: str) -> Any:
        """Decode a JSON body, naming the endpoint when the body isn't JSON.

        A proxy or login interstitial happily returns ``200 text/html``; raising
        a bare ``JSONDecodeError`` from deep inside httpx hides which call failed.
        """

        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            snippet = response.text[:200]
            raise RuntimeError(
                f"{what} returned a non-JSON body "
                f"(status={response.status_code}, content-type="
                f"{response.headers.get('content-type', '?')!r}): {snippet!r}"
            ) from exc

    async def create(
        self,
        workspace_id: int,
        content: str,
        *,
        type_: str = "semantic",
        tags: Sequence[str] | None = None,
        confidence: float = 1.0,
        source_type: str = "manual",
        source_id: int | None = None,
        research_thread_id: int | None = None,
    ) -> dict[str, Any]:
        """Create one labeled memory in the selected workspace."""

        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type {source_type!r} is not a backend MemorySourceType; "
                f"expected one of {', '.join(sorted(VALID_SOURCE_TYPES))}"
            )
        response = await self._http.post(
            f"{self._base}/api/v1/workspaces/{workspace_id}/memories",
            json={
                "content": content,
                "type": type_,
                "tags": list(tags or []),
                "confidence": confidence,
                "source_type": source_type,
                "source_id": source_id,
                "research_thread_id": research_thread_id,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = self._decode(response, what="memory create")
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected memory create payload: {payload!r}")
        return payload

    async def search(
        self,
        workspace_id: int,
        query: str,
        *,
        top_k: int = 5,
        type_: str | None = None,
        tags: Sequence[str] | None = None,
        research_thread_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return ordered memory hits from ``/memories/search``.

        Non-dict items are a contract violation and raise rather than being
        filtered out: dropping one silently shifts every later item up a rank,
        so an item that was really 6th would be scored as if it were 5th.
        """

        if isinstance(top_k, bool) or not isinstance(top_k, int):
            raise ValueError("top_k must be an integer")
        if not _MIN_TOP_K <= top_k <= _MAX_TOP_K:
            raise ValueError(f"top_k must be between {_MIN_TOP_K} and {_MAX_TOP_K}, got {top_k}")
        response = await self._http.post(
            f"{self._base}/api/v1/workspaces/{workspace_id}/memories/search",
            json={
                "query": query,
                "top_k": top_k,
                "type": type_,
                "tags": list(tags or []),
                "research_thread_id": research_thread_id,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = self._decode(response, what="memory search")
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise RuntimeError(f"Unexpected memory search payload: {payload!r}")
        items = payload["items"]
        for position, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise RuntimeError(
                    f"Memory search returned a non-object item at rank {position}: {item!r}"
                )
        return list(items)

    async def delete(self, memory_id: int) -> None:
        """Delete one memory (``DELETE /memories/{id}``), tolerating a prior delete."""

        response = await self._http.delete(f"{self._base}/api/v1/memories/{memory_id}")
        if response.status_code == 404:
            return
        response.raise_for_status()


__all__ = ["VALID_SOURCE_TYPES", "MemoriesClient"]
