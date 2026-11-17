"""ChainLens Async Research Jobs Client & Resumption (Story 20.9).

Handles long-running (> 60s) deep research queries via ChainLens Async Jobs API:
- POST /v1/async-jobs (submit)
- GET /v1/async-jobs/{runId} (status & final deliverable recovery)
- GET /v1/async-jobs/{runId}/events (SSE live phase/text streaming)
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import config
from app.services.chainlens.auth import get_chainlens_auth

logger = logging.getLogger(__name__)


class ChainLensAsyncJobError(Exception):
    """Raised when ChainLens Async Jobs API encounters a failure."""


class ChainLensAsyncJobsClient:
    """Client for asynchronous deep research execution and resumption."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (
            base_url
            or getattr(config, "CHAINLENS_API_URL", "http://localhost:3001")
        ).rstrip("/")

    async def submit_job(
        self,
        *,
        workspace_id: int,
        query: str,
        mode: str = "balanced",
        sources: list[str] | None = None,
        chat_id: str | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit a new asynchronous deep research job to ChainLens.

        Returns:
            Dict containing ``runId``, ``status`` (pending), and ``createdAt``.
        """
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)
        headers["Content-Type"] = "application/json"

        payload = {
            "query": query,
            "mode": mode,
            "sources": sources or ["web"],
        }
        if chat_id:
            payload["chatId"] = chat_id
        if output_schema:
            payload["outputSchema"] = output_schema

        url = f"{self.base_url}/v1/async-jobs"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.post(url, json=payload, headers=headers)
                if not res.is_success:
                    raise ChainLensAsyncJobError(
                        f"Submit async job failed ({res.status_code}): {res.text}"
                    )
                return res.json()
            except httpx.HTTPError as exc:
                logger.error("[AsyncJobs] Network error submitting job: %s", exc)
                raise ChainLensAsyncJobError(f"HTTP connection error: {exc}") from exc

    async def get_job(
        self,
        run_id: str,
        *,
        workspace_id: int = 0,
    ) -> dict[str, Any] | None:
        """Fetch the current status and payload of an async job.

        Returns:
            Dict containing status ('pending'|'running'|'completed'|'failed'),
            or ``None`` if 404 (not found).
        """
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)

        url = f"{self.base_url}/v1/async-jobs/{run_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                res = await client.get(url, headers=headers)
                if res.status_code == 404:
                    return None
                if not res.is_success:
                    raise ChainLensAsyncJobError(
                        f"Get async job failed ({res.status_code}): {res.text}"
                    )
                return res.json()
            except httpx.HTTPError as exc:
                logger.error("[AsyncJobs] Network error fetching job %s: %s", run_id, exc)
                raise ChainLensAsyncJobError(f"HTTP connection error: {exc}") from exc

    async def stream_events(
        self,
        run_id: str,
        *,
        workspace_id: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream real-time research phases and text deltas via SSE."""
        auth = get_chainlens_auth()
        headers = auth.get_outbound_headers(workspace_id=workspace_id)
        headers["Accept"] = "text/event-stream"

        url = f"{self.base_url}/v1/async-jobs/{run_id}/events"
        async with (
            httpx.AsyncClient(timeout=300.0) as client,
            client.stream("GET", url, headers=headers) as response,
        ):
            if not response.is_success:
                raise ChainLensAsyncJobError(
                    f"Event stream failed ({response.status_code})"
                )

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        yield json.loads(data_str)
                    except Exception:
                        continue

    async def recover_report(
        self,
        run_id: str,
        *,
        workspace_id: int = 0,
    ) -> dict[str, Any] | None:
        """Recover a completed research report without re-paying token costs.

        Returns:
            The ``result`` object containing markdown report, citations, and metadata,
            or ``None`` if the job has not completed or does not exist.
        """
        job = await self.get_job(run_id, workspace_id=workspace_id)
        if not job:
            logger.warning("[AsyncJobs] Job %s not found for recovery", run_id)
            return None

        status = job.get("status")
        if status != "completed":
            logger.info(
                "[AsyncJobs] Job %s not yet completed (current status: %s)",
                run_id,
                status,
            )
            return None

        logger.info(
            "[AsyncJobs] Successfully recovered completed research for runId=%s",
            run_id,
        )
        return job.get("result") or job.get("deliverables") or job
