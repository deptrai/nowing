"""ChainLens Websets API client service (Story 41.1)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.config import config
from app.services.chainlens.auth import get_chainlens_auth

logger = logging.getLogger(__name__)


_PAGE_MAX_ATTEMPTS = 3
_PAGE_RETRY_BASE_DELAY = 1.0


class WebsetsUnavailableError(Exception):
    """Raised when ChainLens Websets API is unreachable or returns an error response.

    ``retryable=True`` marks transient failures (5xx, 429, network) a caller may
    retry; other 4xx are terminal and flagged False.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


WebsetsUnavailable = WebsetsUnavailableError


class WebsetsService:
    """Client for ChainLens Websets API endpoints."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (
            base_url or getattr(config, "CHAINLENS_API_URL", "http://localhost:3001")
        ).rstrip("/")
        self.timeout = timeout

    async def create_webset(
        self,
        source: dict[str, Any],
        columns: list[dict[str, Any]],
        criteria: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        workspace_id: int,
    ) -> dict[str, Any]:
        """Create a new asynchronous webset build in ChainLens.

        Args:
            source: Source definition (e.g. {"type": "web"} or URL seeds).
            columns: Extracted column specifications.
            criteria: Extraction prompt and inclusion/exclusion criteria.
            metadata: Custom metadata including callback webhookUrl.
            workspace_id: The tenant workspace ID for auth and correlation.

        Returns:
            The created webset dictionary containing webset_id / websetId / id.

        Raises:
            WebsetsUnavailable: On network failure, timeout, or 4xx/5xx response.
        """
        url = f"{self.base_url}/v1/websets"
        headers = get_chainlens_auth().get_outbound_headers(
            workspace_id=workspace_id,
            content_type="application/json",
        )
        payload: dict[str, Any] = {
            "source": source,
            "columns": columns,
        }
        if criteria is not None:
            payload["criteria"] = criteria
        if metadata is not None:
            payload["metadata"] = metadata

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code >= 400:
                    logger.error(
                        "ChainLens create_webset failed: status=%s body=%s",
                        res.status_code,
                        res.text,
                    )
                    raise WebsetsUnavailable(
                        f"ChainLens create_webset failed with status {res.status_code}: {res.text}"
                    )
                return res.json()
        except httpx.HTTPError as exc:
            logger.error("ChainLens create_webset connection error: %s", exc)
            raise WebsetsUnavailable(f"ChainLens service unreachable: {exc}") from exc

    async def get_webset(self, webset_id: str, *, workspace_id: int) -> dict[str, Any]:
        """Fetch the current status and metadata of a webset.

        Args:
            webset_id: ChainLens webset ID (e.g. wbs_123).
            workspace_id: The tenant workspace ID.

        Returns:
            The webset status dictionary.

        Raises:
            WebsetsUnavailable: On network failure or error status.
        """
        url = f"{self.base_url}/v1/websets/{webset_id}"
        headers = get_chainlens_auth().get_outbound_headers(workspace_id=workspace_id)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=headers)
                if res.status_code >= 400:
                    logger.error(
                        "ChainLens get_webset failed: status=%s body=%s",
                        res.status_code,
                        res.text,
                    )
                    raise WebsetsUnavailable(
                        f"ChainLens get_webset failed with status {res.status_code}: {res.text}"
                    )
                return res.json()
        except httpx.HTTPError as exc:
            logger.error("ChainLens get_webset connection error: %s", exc)
            raise WebsetsUnavailable(f"ChainLens service unreachable: {exc}") from exc

    async def iter_ready_items(
        self,
        webset_id: str,
        *,
        workspace_id: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Page through items in a webset, yielding only ready or verified entities.

        Uses cursor-based keyset pagination against GET /v1/websets/{webset_id}/items.

        Args:
            webset_id: ChainLens webset ID.
            workspace_id: The tenant workspace ID.

        Yields:
            Extracted item dictionaries whose status is 'ready' or 'verified'.

        Raises:
            WebsetsUnavailable: On communication failure or non-2xx status code.
        """
        url = f"{self.base_url}/v1/websets/{webset_id}/items"
        cursor: str | None = None
        seen_cursors: set[str] = set()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                params: dict[str, Any] = {
                    "status": "ready,verified",
                    "limit": 100,
                }
                if cursor:
                    params["cursor"] = cursor

                data = await self._get_items_page(
                    client, url, params, workspace_id
                )

                items = data.get("items") or data.get("data") or []
                for item in items:
                    # Filter out any non-ready/verified statuses if returned by API
                    item_status = item.get("status")
                    if item_status is None or item_status in ("ready", "verified"):
                        yield item

                next_cursor = data.get("nextCursor") or data.get("next_cursor")
                # Chặn cả self-loop (A->A) lẫn vòng đa điểm (A->B->A)
                if (
                    not next_cursor
                    or not items
                    or next_cursor == cursor
                    or next_cursor in seen_cursors
                ):
                    break
                if cursor is not None:
                    seen_cursors.add(cursor)
                cursor = next_cursor

    async def _get_items_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, Any],
        workspace_id: int,
    ) -> dict[str, Any]:
        """Fetch one items page with bounded retry + a single 401 token rotation.

        Retries transient failures (5xx, 429, network) up to _PAGE_MAX_ATTEMPTS
        with exponential backoff. On 401, rotates the outbound token once via the
        shared ChainLensServiceAuth singleton — x-user-ctx has a 60s TTL so a
        long drain can legitimately hit an expired token.
        """
        auth = get_chainlens_auth()
        delay = _PAGE_RETRY_BASE_DELAY
        retried_401 = False

        for attempt in range(_PAGE_MAX_ATTEMPTS):
            # x-user-ctx HMAC TTL 60s — regen mỗi attempt để drain dài không 401
            headers = auth.get_outbound_headers(workspace_id=workspace_id)
            try:
                res = await client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                logger.error("ChainLens iter_ready_items connection error: %s", exc)
                if attempt == _PAGE_MAX_ATTEMPTS - 1:
                    raise WebsetsUnavailable(
                        f"ChainLens service unreachable: {exc}", retryable=True
                    ) from exc
                await asyncio.sleep(delay)
                delay *= 2
                continue

            if res.status_code == 401 and not retried_401:
                retried_401 = True
                if auth.rotate(workspace_id=workspace_id, reason="401_response"):
                    continue
                # Không còn token để rotate — rơi xuống nhánh 4xx terminal

            if res.status_code >= 400:
                retryable = res.status_code == 429 or res.status_code >= 500
                logger.error(
                    "ChainLens iter_ready_items failed: status=%s body=%s",
                    res.status_code,
                    res.text,
                )
                if retryable and attempt < _PAGE_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise WebsetsUnavailable(
                    f"ChainLens iter_ready_items failed with status {res.status_code}: {res.text}",
                    retryable=retryable,
                )

            try:
                return res.json()
            except Exception as exc:
                raise WebsetsUnavailable(
                    f"ChainLens iter_ready_items returned non-JSON body: {exc}"
                ) from exc

        raise WebsetsUnavailable("ChainLens iter_ready_items exhausted retries")
