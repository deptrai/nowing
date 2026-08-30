"""DSH REST client for sidecar <-> gateway communication."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any
from uuid import UUID

import httpx

from app.capabilities.chainlens.research.executor import build_research_executor
from app.capabilities.chainlens.research.schemas import ResearchInput
from app.tasks.dsh_worker.constants import _DSH_CALL_TIMEOUT_SECONDS, _DSH_SYNC_TIMEOUT
from app.tasks.dsh_worker.errors import (
    DshBillingError,
    DshNonRetryableError,
    DshNotFoundError,
    DshTransientError,
    DshValidationError,
)

logger = logging.getLogger(__name__)

_research_executor = build_research_executor()


class DshRestClient:
    """REST client used by the sidecar to talk to the Nowing gateway."""

    def __init__(
        self,
        base_url: str,
        pat: str,
        worker_secret: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.pat = pat
        self.worker_secret = worker_secret
        self.timeout = min(float(timeout), _DSH_CALL_TIMEOUT_SECONDS)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.pat}",
                "X-Dsh-Worker-Secret": self.worker_secret,
            },
            timeout=httpx.Timeout(timeout),
        )

    def _raise_for_status(
        self,
        response: httpx.Response,
        context: str,
    ) -> None:
        """Classify REST failures into retryable vs non-retryable buckets."""
        if response.is_success:
            return
        status = response.status_code
        detail = f"{context}: HTTP {status} {response.text[:200]}"
        if status == 402:
            raise DshBillingError(detail)
        if status == 404:
            raise DshNotFoundError(detail)
        if status == 422:
            raise DshValidationError(detail)
        if status == 429 or status >= 500:
            raise DshTransientError(detail)
        # Any other 4xx is treated as non-retryable (e.g. 403 misconfiguration).
        raise DshNonRetryableError(detail)

    async def get_mission(self, mission_id: uuid.UUID) -> dict[str, Any]:
        response = await self._client.get(f"/v1/dsh/missions/{mission_id}")
        self._raise_for_status(response, f"get_mission {mission_id}")
        return response.json()

    async def patch_checkpoint(
        self,
        mission_id: uuid.UUID,
        update: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._client.patch(
            f"/v1/dsh/missions/{mission_id}/checkpoint",
            json=update,
        )
        self._raise_for_status(response, f"patch_checkpoint {mission_id}")
        return response.json()

    async def chainlens_research(
        self,
        workspace_id: int,
        query: str,
        output: str | None = None,
        output_schema: dict[str, Any] | None = None,
        mode: str = "balanced",
    ) -> dict[str, Any]:
        """Call the local chainlens.research capability directly.

        ponytail: the REST route this client used to call no longer exists in
        the gateway, so we invoke the executor the gateway itself uses and
        return a flat dict for backward compatibility with the legacy and
        LangGraph executors.
        """
        try:
            payload = ResearchInput(
                query=query,
                mode=mode,  # type: ignore[arg-type]
                output=output,  # type: ignore[arg-type]
                output_schema=output_schema,
                workspace_id=workspace_id,
            )
        except Exception as exc:
            raise DshTransientError(f"Invalid chainlens.research payload: {exc}") from exc

        output_obj = await _research_executor(payload, None)

        if output_obj.status in ("engine_unavailable", "timeout"):
            raise DshTransientError(
                output_obj.degradation_reason
                or output_obj.engine_reason
                or output_obj.status
            )

        result: dict[str, Any] = output_obj.model_dump()
        result["run_id"] = output_obj.chat_id or str(uuid.uuid4())
        return result

    async def _poll_run(self, workspace_id: int, run_id: str) -> dict[str, Any]:
        """Poll GET /scrapers/runs/{run_id} until a terminal status."""
        while True:
            response = await self._client.get(
                f"/api/v1/workspaces/{workspace_id}/scrapers/runs/{run_id}",
                timeout=httpx.Timeout(_DSH_SYNC_TIMEOUT),
            )
            self._raise_for_status(response, f"poll_run {run_id}")
            run = response.json()
            status = run.get("status")

            if status == "success":
                output_text = run.get("output_text") or ""
                if not output_text:
                    raise DshTransientError(f"Run {run_id} succeeded with no output")
                try:
                    return json.loads(output_text.splitlines()[0])
                except (json.JSONDecodeError, IndexError) as exc:
                    raise DshTransientError(
                        f"Run {run_id} has unparsable output: {exc}"
                    ) from exc

            if status in {"error", "cancelled"}:
                raise DshTransientError(
                    f"Run {run_id} ended with status {status}: {run.get('error')}"
                )

            await asyncio.sleep(5)

    async def batch_ingest_leads(
        self,
        workspace_id: int,
        leads: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {"leads": leads}
        # Back-off on 429; otherwise raise.
        for attempt in range(3):
            response = await self._client.post(
                f"/api/v1/workspaces/{workspace_id}/leads/batch-ingest",
                json=payload,
                timeout=httpx.Timeout(_DSH_SYNC_TIMEOUT),
            )
            if response.status_code == 429:
                wait = 2**attempt
                logger.warning("batch_ingest rate limited; retry in %ss", wait)
                await asyncio.sleep(wait)
                continue
            self._raise_for_status(response, "batch_ingest_leads")
            return response.json()
        raise DshTransientError("batch_ingest_leads exhausted retries on 429")

    async def notify_high_fit_lead(
        self,
        mission_id: UUID | str,
        lead_id: UUID | str,
        contact_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"lead_id": str(lead_id)}
        if contact_id:
            payload["contact_id"] = str(contact_id)
        response = await self._client.post(
            f"/v1/dsh/missions/{mission_id}/notify-high-fit",
            json=payload,
            timeout=httpx.Timeout(_DSH_SYNC_TIMEOUT),
        )
        self._raise_for_status(response, "notify_high_fit_lead")
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()
