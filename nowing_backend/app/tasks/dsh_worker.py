from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import signal
import socket
import sys
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from redis.asyncio.client import Redis
from redis.exceptions import ResponseError

from app.capabilities.chainlens.research.executor import build_research_executor
from app.capabilities.chainlens.research.schemas import ResearchInput
from app.config import config
from app.redis_client import get_redis_client
from app.tasks.dsh_worker_langgraph import LangGraphMissionExecutor

_research_executor = build_research_executor()

logger = logging.getLogger(__name__)

# Hard 60s ceiling on every synchronous Redis stream / REST round-trip (AC-2 / AD-108).
_DSH_CALL_TIMEOUT_SECONDS = 60.0
_DSH_SYNC_TIMEOUT = min(
    float(getattr(config, "DSH_SYNC_TIMEOUT_SECONDS", _DSH_CALL_TIMEOUT_SECONDS)),
    _DSH_CALL_TIMEOUT_SECONDS,
)


def _checkpoint_update(**kwargs: Any) -> dict[str, Any]:
    """Build a JSON-serialisable checkpoint update with None values omitted.

    ``current_subtask_id`` is always preserved (including ``None``) because the
    sidecar must be able to clear it on terminal/success transitions.
    ``started_at`` and ``completed_at`` are normalised to ISO strings so the
    sidecar payload is JSON-serialisable even if a caller passes a ``datetime``.
    """
    result: dict[str, Any] = {}
    for k, v in kwargs.items():
        if v is None and k != "current_subtask_id":
            continue
        if k in ("started_at", "completed_at") and isinstance(v, datetime):
            v = v.isoformat()
        result[k] = v
    return result


# ---------------------------------------------------------------------------
# Error taxonomy for the sidecar
# ---------------------------------------------------------------------------
class DshWorkerError(Exception):
    """Base class for DSH worker errors."""

    pass


class DshRetryableError(DshWorkerError):
    """A transient failure that should count against the retry budget."""

    pass


class DshNonRetryableError(DshWorkerError):
    """A failure that should move the mission straight to the DLQ."""

    pass


class DshBillingError(DshNonRetryableError):
    """The workspace cannot pay for the operation (402)."""

    pass


class DshNotFoundError(DshNonRetryableError):
    """A requested resource does not exist (404)."""

    pass


class DshValidationError(DshNonRetryableError):
    """The payload or state is invalid (422)."""

    pass


class DshTransientError(DshRetryableError):
    """A transient REST or upstream error (5xx, 429, timeout)."""

    pass


# ---------------------------------------------------------------------------
# REST client
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Mission executor
# ---------------------------------------------------------------------------
class DeepLeadResearchExecutor:
    """Default deterministic sequential executor for deep-lead-research missions."""

    def __init__(self, rest_client: DshRestClient) -> None:
        self.rest_client = rest_client

    @staticmethod
    def _extract_domain(url: str | None) -> str | None:
        if not url:
            return None
        try:
            parsed = urlparse(url)
            return parsed.netloc if parsed.netloc else None
        except Exception:
            return None

    async def _patch_checkpoint(
        self,
        mission_id: uuid.UUID,
        checkpoint: dict[str, Any],
        phase: str,
        progress_percent: int,
        current_subtask_id: str | None = None,
        status: str | None = None,
        error: dict[str, Any] | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict[str, Any]:
        update = _checkpoint_update(
            checkpoint=checkpoint,
            phase=phase,
            progress_percent=progress_percent,
            current_subtask_id=current_subtask_id,
            status=status,
            error=error,
            started_at=started_at,
            completed_at=completed_at,
        )
        response = await self.rest_client.patch_checkpoint(mission_id, update)
        # Merge the server's checkpoint back so the next patch does not fail on
        # a stale version. The checkpoint dict is mutated in place so callers
        # that hold references to it see the updated subtasks/sources/leads.
        response_checkpoint = response.get("checkpoint") if isinstance(response, dict) else None
        if response_checkpoint:
            checkpoint.clear()
            checkpoint.update(response_checkpoint)
        return response

    def _mission_id(self, mission: dict[str, Any] | Any) -> uuid.UUID:
        raw = mission["id"] if isinstance(mission, dict) else mission.id
        return uuid.UUID(raw) if isinstance(raw, str) else raw

    def _mission_workspace_id(self, mission: dict[str, Any] | Any) -> int:
        return (
            mission["workspace_id"]
            if isinstance(mission, dict)
            else mission.workspace_id
        )

    def _mission_payload(self, mission: dict[str, Any] | Any) -> dict[str, Any]:
        payload = mission["payload"] if isinstance(mission, dict) else mission.payload
        return payload or {}

    def _mission_checkpoint(self, mission: dict[str, Any] | Any) -> dict[str, Any]:
        checkpoint = (
            mission["checkpoint"] if isinstance(mission, dict) else mission.checkpoint
        )
        if not checkpoint:
            checkpoint = {"version": 1, "phase": "crawl", "subtasks": []}
        return checkpoint

    async def run(self, mission: dict[str, Any] | Any) -> None:
        """Run the four phases sequentially, updating checkpoint after each."""
        mission_id = self._mission_id(mission)
        workspace_id = self._mission_workspace_id(mission)
        payload = self._mission_payload(mission)
        query = payload.get("query", "") if isinstance(payload, dict) else ""

        checkpoint = self._mission_checkpoint(mission)
        subtasks = checkpoint.get("subtasks", [])

        # Phase: crawl -> reasoning -> extraction -> ingestion
        # 1. Crawl (ChainLens research)
        if not any(
            s.get("id") == "crawl" and s.get("status") == "success" for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="crawl",
                progress_percent=10,
                current_subtask_id="crawl",
                status="running",
            )
            try:
                research_output = await self.rest_client.chainlens_research(
                    workspace_id, query
                )
                sources = research_output.get("sources", [])
                subtasks.append(
                    {
                        "id": "crawl",
                        "status": "success",
                        "run_id": research_output.get("run_id"),
                        "sources_count": len(sources),
                    }
                )
                checkpoint["subtasks"] = subtasks
                checkpoint["sources"] = sources
                await self._patch_checkpoint(
                    mission_id,
                    checkpoint,
                    phase="reasoning",
                    progress_percent=35,
                    current_subtask_id="reasoning",
                )
            except Exception as exc:
                subtasks.append(
                    {
                        "id": "crawl",
                        "status": "failed",
                        "error": str(exc),
                    }
                )
                checkpoint["subtasks"] = subtasks
                await self._patch_checkpoint(
                    mission_id,
                    checkpoint,
                    phase="crawl",
                    progress_percent=0,
                    current_subtask_id="crawl",
                    status="error",
                    error={"phase": "crawl", "message": str(exc)},
                )
                raise

        # 2. Reasoning
        if not any(
            s.get("id") == "reasoning" and s.get("status") == "success"
            for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="reasoning",
                progress_percent=45,
                current_subtask_id="reasoning",
            )
            # Deterministic reasoning can be a no-op for 26.2.
            subtasks.append({"id": "reasoning", "status": "success"})
            checkpoint["subtasks"] = subtasks
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="extraction",
                progress_percent=60,
                current_subtask_id="extraction",
            )

        # 3. Extraction
        if not any(
            s.get("id") == "extraction" and s.get("status") == "success"
            for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="extraction",
                progress_percent=70,
                current_subtask_id="extraction",
            )
            sources = checkpoint.get("sources", [])
            extracted_leads = [
                self._source_to_lead(source, workspace_id) for source in sources
            ]
            # Filter degenerate leads that would fail the batch-ingest validator.
            extracted_leads = [lead for lead in extracted_leads if lead is not None]
            subtasks.append(
                {
                    "id": "extraction",
                    "status": "success",
                    "leads_count": len(extracted_leads),
                }
            )
            checkpoint["subtasks"] = subtasks
            checkpoint["leads"] = extracted_leads
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="ingestion",
                progress_percent=85,
                current_subtask_id="ingestion",
            )

        # 4. Ingestion
        if not any(
            s.get("id") == "ingestion" and s.get("status") == "success"
            for s in subtasks
        ):
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="ingestion",
                progress_percent=90,
                current_subtask_id="ingestion",
            )
            leads = checkpoint.get("leads", [])
            if leads:
                try:
                    ingest_res = await self.rest_client.batch_ingest_leads(
                        workspace_id, leads
                    )
                    try:
                        # Trigger Telegram notification for top high-fit lead if any (Story 26.6)
                        from app.lead_intelligence.dnc.normalizer import (
                            normalize_domain,
                        )
                        from app.services.dsh_telegram_checkpoint_service import (
                            DshTelegramCheckpointService,
                        )
                        from app.services.lead_batch_service import generate_lead_hmac

                        checkpoint_svc = DshTelegramCheckpointService()
                        high_fit_candidate = checkpoint_svc.select_high_fit_lead(leads)
                        if high_fit_candidate:
                            lead_id = None
                            if isinstance(high_fit_candidate, dict):
                                cand_company = (
                                    high_fit_candidate.get("company_name")
                                    or high_fit_candidate.get("title")
                                    or "Doanh nghiệp"
                                )
                                cand_domain = normalize_domain(
                                    high_fit_candidate.get("domain")
                                )
                                cand_hmac = high_fit_candidate.get(
                                    "value_hmac"
                                ) or generate_lead_hmac(
                                    workspace_id, cand_company, cand_domain
                                )
                                mapping = ingest_res.get("lead_id_mapping") or {}
                                lead_id = mapping.get(cand_hmac)
                                if not lead_id:
                                    logger.info(
                                        "High-fit lead mapping missing for mission %s; skipping notification",
                                        mission_id,
                                    )
                            elif hasattr(high_fit_candidate, "id"):
                                lead_id = high_fit_candidate.id

                            if lead_id:
                                try:
                                    await self.rest_client.notify_high_fit_lead(
                                        mission_id, lead_id
                                    )
                                except Exception as notify_exc:
                                    logger.warning(
                                        "Failed to notify high fit lead for mission %s: %s",
                                        mission_id,
                                        notify_exc,
                                    )
                    except Exception as notify_exc:
                        logger.warning(
                            "Failed to process high fit lead notification for mission %s: %s",
                            mission_id,
                            notify_exc,
                        )
                except Exception as exc:
                    subtasks.append(
                        {
                            "id": "ingestion",
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                    checkpoint["subtasks"] = subtasks
                    await self._patch_checkpoint(
                        mission_id,
                        checkpoint,
                        phase="ingestion",
                        progress_percent=85,
                        current_subtask_id="ingestion",
                        status="error",
                        error={"phase": "ingestion", "message": str(exc)},
                    )
                    raise
            subtasks.append({"id": "ingestion", "status": "success"})
            checkpoint["subtasks"] = subtasks
            await self._patch_checkpoint(
                mission_id,
                checkpoint,
                phase="terminal",
                progress_percent=100,
                current_subtask_id=None,
                status="success",
            )

    def _source_to_lead(
        self, source: dict[str, Any], workspace_id: int
    ) -> dict[str, Any] | None:
        """Convert a ChainLens source into a LeadItem-shaped dict.

        Returns None for degenerate leads that would fail batch validation.
        """
        url = source.get("url")
        domain = source.get("domain") or self._extract_domain(url)
        lead = {
            "source": "dsh_research",
            "source_url": url,
            "client_id": source.get("client_id"),
            "company_name": source.get("company_name"),
            "domain": domain,
            "phone": source.get("phone"),
            "email": source.get("email"),
            "title": source.get("title"),
            "industry": source.get("industry"),
            "location": source.get("location"),
            "fit_score": source.get("fit_score", 0.0),
            "intent_score": source.get("intent_score", 0.0),
            "composite_score": source.get("composite_score"),
        }
        if not any([lead["phone"], lead["email"], lead["domain"]]):
            logger.warning("Skipping degenerate lead from source %s", url)
            return None
        return lead


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def _default_consumer_name() -> str:
    """Return a unique consumer name per process/host for load balancing."""
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


_RENEW_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
else
    return 0
end
"""


class DshWorker:
    """Long-running sidecar worker for DSH missions."""

    def __init__(
        self,
        consumer_name: str | None = None,
        redis_client: Redis | None = None,
        executor: DeepLeadResearchExecutor | LangGraphMissionExecutor | None = None,
        rest_client: DshRestClient | None = None,
    ) -> None:
        self.consumer_name = consumer_name or _default_consumer_name()
        self._redis = redis_client
        self._executor = executor
        self._rest_client = rest_client
        self._running = False
        self._tasks: set[asyncio.Task] = set()

    @property
    def stream(self) -> str:
        return config.DSH_STREAM_TASKS

    @property
    def group(self) -> str:
        return config.DSH_CONSUMER_GROUP

    @property
    def dlq(self) -> str:
        return config.DSH_STREAM_DLQ

    @property
    def lock_ttl(self) -> int:
        return config.DSH_LOCK_TTL_SECONDS

    @property
    def heartbeat_interval(self) -> int:
        return config.DSH_HEARTBEAT_INTERVAL_SECONDS

    @property
    def max_retries(self) -> int:
        return config.DSH_MAX_RETRIES

    @property
    def rest_client(self) -> DshRestClient:
        if self._rest_client is None:
            self._rest_client = DshRestClient(
                config.DSH_INTERNAL_BASE_URL,
                config.DSH_WORKER_PAT,
                config.DSH_WORKER_SECRET,
                timeout=float(config.DSH_SYNC_TIMEOUT_SECONDS),
            )
        return self._rest_client

    def _lock_key(self, mission_id: uuid.UUID) -> str:
        return f"nowing:dsh:lock:{mission_id}"

    async def _redis_client(self) -> Redis:
        if self._redis is None:
            self._redis = await get_redis_client()
        return self._redis

    async def _ensure_consumer_group(self, redis_client: Redis) -> None:
        try:
            # ponytail: start at 0-0 so a (re)started worker consumes the
            # backlog instead of only messages published after boot.
            await redis_client.xgroup_create(
                name=self.stream,
                groupname=self.group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc).upper():
                raise

    async def _try_set_lock(
        self,
        redis_client: Redis,
        mission_id: uuid.UUID,
    ) -> bool:
        """Try to claim the per-mission Redis lock with NX + TTL."""
        return await redis_client.set(
            self._lock_key(mission_id),
            self.consumer_name,
            nx=True,
            ex=self.lock_ttl,
        )

    async def _renew_lock_and_idle(
        self,
        redis_client: Redis,
        mission_id: uuid.UUID,
        msg_id: bytes | str,
    ) -> bool:
        """Heartbeat: refresh the Redis lock, then reset PEL idle time.

        Uses a Lua script so we only extend TTL when we still own the lock.
        We renew the lock FIRST so that a lost lock is detected before we
        reset the pending-entry-list idle time; otherwise we could delay
        another worker from reclaiming the message.
        """
        try:
            ok = await redis_client.eval(
                _RENEW_LOCK_SCRIPT,
                1,
                self._lock_key(mission_id),
                self.consumer_name,
                self.lock_ttl,
            )
            if not ok:
                logger.info("Lock for mission %s is no longer ours", mission_id)
                return False
            await redis_client.xclaim(
                self.stream,
                self.group,
                self.consumer_name,
                0,
                [msg_id],
            )
            return True
        except Exception as exc:
            logger.warning("Heartbeat failed for mission %s: %s", mission_id, exc)
            return False

    async def _autoclaim(
        self,
        redis_client: Redis,
        min_idle_ms: int | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Reclaim idle messages using XAUTOCLAIM.

        ``min_idle_ms`` overrides ``config.DSH_XAUTOCLAIM_MIN_IDLE_MS`` when the
        caller needs a non-production value (e.g. smoke tests).
        """
        claimed: list[tuple[str, dict[str, Any]]] = []
        start_id = "0-0"
        idle = min_idle_ms if min_idle_ms is not None else config.DSH_XAUTOCLAIM_MIN_IDLE_MS
        while True:
            response = await asyncio.wait_for(
                redis_client.xautoclaim(
                    self.stream,
                    self.group,
                    self.consumer_name,
                    idle,
                    start_id,
                    count=10,
                ),
                timeout=_DSH_CALL_TIMEOUT_SECONDS,
            )
            # redis-py can return a 2- or 3-element list; the first two elements are
            # next_start_id and the message list.
            next_start, messages = response[0], response[1]
            for msg_id, fields in messages:
                claimed.append((msg_id, fields))
            if not next_start or next_start == start_id or not messages:
                break
            start_id = next_start
        return claimed

    def _parse_payload(self, fields: dict[str, Any]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for key, value in fields.items():
            key_s = key.decode() if isinstance(key, bytes) else key
            value_s = value.decode() if isinstance(value, bytes) else value
            if key_s in ("payload", "payload_json"):
                try:
                    parsed["payload"] = json.loads(value_s)
                except json.JSONDecodeError:
                    parsed["payload"] = value_s
            elif key_s == "checkpoint":
                try:
                    parsed[key_s] = json.loads(value_s)
                except json.JSONDecodeError:
                    parsed[key_s] = value_s
            elif key_s == "attempt":
                try:
                    parsed[key_s] = int(value_s)
                except (ValueError, TypeError):
                    parsed[key_s] = value_s
            else:
                parsed[key_s] = value_s
        return parsed

    async def _heartbeat_loop(
        self,
        redis_client: Redis,
        mission_id: uuid.UUID,
        msg_id: str,
        executor_task: asyncio.Task,
    ) -> None:
        """Periodically reset idle time and renew the lock while a mission runs."""
        try:
            while self._running:
                await asyncio.sleep(self.heartbeat_interval)
                ok = await self._renew_lock_and_idle(redis_client, mission_id, msg_id)
                if not ok:
                    logger.warning(
                        "Lock lost for mission %s; cancelling executor", mission_id
                    )
                    executor_task.cancel()
                    break
        except asyncio.CancelledError:
            pass

    async def _handle_message(
        self,
        redis_client: Redis,
        msg_id: str,
        fields: dict[str, Any],
    ) -> bool:
        """Process one stream message. Returns True if XACK should be attempted."""
        parsed = self._parse_payload(fields)
        mission_id_str = parsed.get("mission_id")
        if not mission_id_str:
            logger.error("Stream message %s has no mission_id", msg_id)
            return True

        try:
            mission_id = uuid.UUID(str(mission_id_str))
        except ValueError:
            logger.error(
                "Invalid mission_id %r in stream message %s", mission_id_str, msg_id
            )
            return True

        # Idempotent lock check for new and reclaimed messages.
        if not await self._try_set_lock(redis_client, mission_id):
            logger.info("Mission %s is already locked; skip", mission_id)
            return False

        try:
            mission = await self.rest_client.get_mission(mission_id)
            if mission.get("status") in ("success", "error", "dlq", "cancelled"):
                logger.info(
                    "Mission %s already terminal (%s); skip",
                    mission_id,
                    mission.get("status"),
                )
                return True
        except DshNonRetryableError as exc:
            logger.error("Mission %s non-retryable load error: %s", mission_id, exc)
            try:
                await self._dlq(redis_client, msg_id, mission_id, str(exc))
            except Exception as dlq_exc:
                logger.exception(
                    "Failed to DLQ mission %s after non-retryable load: %s",
                    mission_id,
                    dlq_exc,
                )
                return False
            return True
        except Exception as exc:
            logger.exception("Could not load mission %s: %s", mission_id, exc)
            return False

        try:
            # Only the deep-lead-research executor is supported in 26.8.
            if mission.get("mission_type") != "deep_lead_research":
                await self.rest_client.patch_checkpoint(
                    mission_id,
                    _checkpoint_update(
                        status="error",
                        error={
                            "message": f"Unsupported mission_type {mission.get('mission_type')!r}",
                            "failed_at": datetime.now(UTC).isoformat(),
                        },
                        completed_at=datetime.now(UTC).isoformat(),
                    ),
                )
                return True

            # Seed checkpoint attempt from the stream if the row is fresh.
            checkpoint = mission.get("checkpoint") or {}
            if checkpoint.get("attempt") is None:
                checkpoint["attempt"] = parsed.get("attempt", 1)
                mission["checkpoint"] = checkpoint

            running_response = await self.rest_client.patch_checkpoint(
                mission_id,
                _checkpoint_update(
                    status="running",
                    phase="crawl",
                    progress_percent=0,
                    current_subtask_id="crawl",
                    checkpoint=checkpoint,
                    started_at=datetime.now(UTC).isoformat(),
                ),
            )
            if isinstance(running_response, dict) and running_response.get("checkpoint"):
                mission["checkpoint"] = running_response["checkpoint"]

            if self._executor is not None:
                executor = self._executor
            elif config.DSH_EXECUTOR_ENGINE == "langgraph":
                executor = LangGraphMissionExecutor(self.rest_client)
            else:
                executor = DeepLeadResearchExecutor(self.rest_client)
            executor_task = asyncio.create_task(executor.run(mission))
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(redis_client, mission_id, msg_id, executor_task)
            )
            self._tasks.add(executor_task)
            self._tasks.add(heartbeat_task)

            try:
                await executor_task
                await self.rest_client.patch_checkpoint(
                    mission_id,
                    _checkpoint_update(
                        status="success",
                        phase="terminal",
                        progress_percent=100,
                        current_subtask_id=None,
                        completed_at=datetime.now(UTC).isoformat(),
                    ),
                )
                return True
            except asyncio.CancelledError:
                logger.info(
                    "Mission %s cancelled (heartbeat/lock lost or shutdown)", mission_id
                )
                return False
            finally:
                heartbeat_task.cancel()
                self._tasks.discard(heartbeat_task)
                self._tasks.discard(executor_task)
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

        except asyncio.CancelledError:
            logger.info(
                "Mission %s cancelled (heartbeat/lock lost or shutdown)", mission_id
            )
            return False
        except DshNonRetryableError as exc:
            try:
                mission = await self.rest_client.get_mission(mission_id)
            except Exception as refresh_exc:
                logger.warning(
                    "Could not refresh mission %s before DLQ: %s",
                    mission_id,
                    refresh_exc,
                )
            try:
                await self._dlq(redis_client, msg_id, mission, str(exc))
                return True
            except Exception as dlq_exc:
                logger.exception(
                    "Failed to DLQ mission %s after non-retryable error: %s",
                    mission_id,
                    dlq_exc,
                )
                return False
        except Exception as exc:
            try:
                mission = await self.rest_client.get_mission(mission_id)
            except Exception as refresh_exc:
                logger.warning(
                    "Could not refresh mission %s before retry: %s",
                    mission_id,
                    refresh_exc,
                )
            try:
                return await self._maybe_retry_or_dlq(
                    redis_client, msg_id, mission, str(exc)
                )
            except Exception as retry_exc:
                logger.exception(
                    "Failed to schedule retry for mission %s: %s",
                    mission_id,
                    retry_exc,
                )
                return False

    async def _maybe_retry_or_dlq(
        self,
        redis_client: Redis,
        msg_id: str,
        mission: dict[str, Any],
        error_message: str,
    ) -> bool:
        """Increment retry_count; if exceeded, DLQ and signal XACK."""
        mission_id = uuid.UUID(str(mission["id"]))
        retry_count = (mission.get("retry_count") or 0) + 1
        checkpoint = mission.get("checkpoint") or {}
        checkpoint["attempt"] = (checkpoint.get("attempt") or 0) + 1
        checkpoint["version"] = (checkpoint.get("version") or 0) + 1

        if retry_count >= self.max_retries:
            return await self._dlq(
                redis_client,
                msg_id,
                mission,
                error_message,
                retry_count=retry_count,
            )

        await self.rest_client.patch_checkpoint(
            mission_id,
            _checkpoint_update(
                status="pending",
                checkpoint=checkpoint,
                retry_count=retry_count,
                error={
                    "message": error_message,
                    "failed_at": datetime.now(UTC).isoformat(),
                },
            ),
        )
        return False

    async def _dlq(
        self,
        redis_client: Redis,
        msg_id: str,
        mission_or_id: dict[str, Any] | uuid.UUID,
        error_message: str,
        retry_count: int | None = None,
    ) -> bool:
        """Move a mission to the DLQ, writing a bounded stream entry."""
        if isinstance(mission_or_id, uuid.UUID):
            # Used when the mission row could not be loaded at all.
            mission_id = mission_or_id
            payload: dict[str, Any] | None = None
            checkpoint: dict[str, Any] = {}
            attempt = 1
            if retry_count is None:
                retry_count = 0
        else:
            mission = mission_or_id
            mission_id = uuid.UUID(str(mission["id"]))
            payload = mission.get("payload")
            checkpoint = mission.get("checkpoint") or {}
            attempt = checkpoint.get("attempt", 1)
            if retry_count is None:
                retry_count = mission.get("retry_count") or 0

        checkpoint["version"] = (checkpoint.get("version") or 0) + 1
        error = {
            "message": error_message,
            "failed_at": datetime.now(UTC).isoformat(),
        }

        await self.rest_client.patch_checkpoint(
            mission_id,
            _checkpoint_update(
                status="dlq",
                checkpoint=checkpoint,
                retry_count=retry_count,
                error=error,
                completed_at=datetime.now(UTC).isoformat(),
            ),
        )

        try:
            await redis_client.xadd(
                self.dlq,
                {
                    "original_id": msg_id,
                    "mission_id": str(mission_id),
                    "payload_json": json.dumps(payload) if payload is not None else "",
                    "error_json": json.dumps(error),
                    "failed_at": error["failed_at"],
                    "attempt": str(attempt),
                },
                maxlen=10000,
                approximate=True,
            )
        except Exception as exc:
            logger.exception("Failed to write mission %s to DLQ: %s", mission_id, exc)
            # The checkpoint is already dlq; a missing DLQ stream entry is logged.
        return True

    async def _read_new_messages(
        self,
        redis_client: Redis,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Read one batch of new messages from the consumer group."""
        entries = await asyncio.wait_for(
            redis_client.xreadgroup(
                groupname=self.group,
                consumername=self.consumer_name,
                streams={self.stream: ">"},
                count=1,
                block=config.DSH_REDIS_BLOCK_MS,
            ),
            timeout=_DSH_CALL_TIMEOUT_SECONDS,
        )

        messages: list[tuple[str, dict[str, Any]]] = []
        if entries:
            for _stream_name, stream_messages in entries:
                for msg_id, fields in stream_messages:
                    messages.append((msg_id, fields))
        return messages

    async def run(self) -> None:
        """Main worker loop with bounded exponential backoff on Redis errors."""
        redis_client = await self._redis_client()
        await self._ensure_consumer_group(redis_client)
        self._redis = redis_client
        self._running = True

        consecutive_redis_errors = 0
        last_autoclaim = 0.0
        while self._running:
            # Periodically XAUTOCLAIM idle messages
            now = asyncio.get_event_loop().time()
            if now - last_autoclaim >= self.heartbeat_interval:
                try:
                    reclaimed = await self._autoclaim(redis_client)
                    consecutive_redis_errors = 0
                except Exception as exc:
                    logger.exception("XAUTOCLAIM failed: %s", exc)
                    consecutive_redis_errors += 1
                    await asyncio.sleep(min(30, 2**consecutive_redis_errors))
                    continue

                for msg_id, fields in reclaimed:
                    parsed = self._parse_payload(fields)
                    mission_id_str = parsed.get("mission_id")
                    if mission_id_str:
                        try:
                            lock_key = self._lock_key(uuid.UUID(str(mission_id_str)))
                            if await redis_client.exists(lock_key):
                                logger.info(
                                    "Reclaimed message %s for mission %s still locked; skip",
                                    msg_id,
                                    mission_id_str,
                                )
                                continue
                        except Exception:
                            pass

                    should_ack = await self._handle_message(
                        redis_client, msg_id, fields
                    )
                    if should_ack:
                        try:
                            await redis_client.xack(self.stream, self.group, msg_id)
                        except Exception as exc:
                            logger.exception("Failed to XACK %s: %s", msg_id, exc)

                last_autoclaim = now

            try:
                messages = await self._read_new_messages(redis_client)
                consecutive_redis_errors = 0
            except Exception as exc:
                logger.exception("XREADGROUP failed: %s", exc)
                consecutive_redis_errors += 1
                await asyncio.sleep(min(30, 2**consecutive_redis_errors))
                continue

            if not messages:
                await asyncio.sleep(1)
                continue

            for msg_id, fields in messages:
                should_ack = await self._handle_message(redis_client, msg_id, fields)
                if should_ack:
                    try:
                        await redis_client.xack(self.stream, self.group, msg_id)
                    except Exception as exc:
                        logger.exception("Failed to XACK %s: %s", msg_id, exc)

    def stop(self) -> None:
        """Signal the worker to stop and cancel in-flight tasks."""
        self._running = False
        for task in list(self._tasks):
            task.cancel()

    async def aclose(self) -> None:
        await self.rest_client.aclose()


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------
async def healthcheck() -> int:
    """Liveness probe used by docker-compose."""
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
    except Exception as exc:
        logger.error("DSH healthcheck Redis ping failed: %s", exc)
        return 1

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{config.DSH_INTERNAL_BASE_URL.rstrip('/')}/health"
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.error("DSH healthcheck API ping failed: %s", exc)
        return 1

    return 0


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def _validate_config() -> None:
    if not config.DSH_WORKER_PAT or not config.DSH_WORKER_SECRET:
        raise SystemExit(
            "DSH_WORKER_PAT and DSH_WORKER_SECRET must be set and non-empty"
        )
    if config.DSH_LOCK_TTL_SECONDS <= config.DSH_HEARTBEAT_INTERVAL_SECONDS:
        raise SystemExit(
            "DSH_LOCK_TTL_SECONDS must be greater than DSH_HEARTBEAT_INTERVAL_SECONDS"
        )
    if (
        config.DSH_XAUTOCLAIM_MIN_IDLE_MS
        <= config.DSH_HEARTBEAT_INTERVAL_SECONDS * 1000
    ):
        raise SystemExit(
            "DSH_XAUTOCLAIM_MIN_IDLE_MS must be greater than heartbeat interval in ms"
        )


async def run_dsh_worker() -> None:
    """Entry point for the SERVICE_ROLE=dsh sidecar."""
    _validate_config()
    worker = DshWorker()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, ValueError):
            # Signals may not be supported on this platform (e.g. Windows).
            loop.add_signal_handler(sig, worker.stop)

    try:
        await worker.run()
    finally:
        worker.stop()
        await worker.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()

    if args.healthcheck:
        sys.exit(asyncio.run(healthcheck()))

    try:
        asyncio.run(run_dsh_worker())
    except SystemExit as exc:
        if exc.code not in (0, None):
            sys.exit(exc.code)
