from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import socket
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from redis.asyncio.client import Redis
from redis.exceptions import (
    BusyGroupError,
    ResponseError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import DshMission, DshMissionStatus, async_session_maker
from app.redis_client import get_redis_client
from app.schemas.dsh import DshMissionCheckpointUpdate
from app.services.dsh_mission_service import DshMissionService

logger = logging.getLogger(__name__)


def _default_consumer_name() -> str:
    """Return a unique consumer name per process/host for load balancing."""
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


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
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.pat}",
                "X-Dsh-Worker-Secret": self.worker_secret,
            },
            timeout=httpx.Timeout(timeout),
        )

    async def get_mission(self, mission_id: uuid.UUID) -> dict[str, Any]:
        response = await self._client.get(f"/v1/dsh/missions/{mission_id}")
        response.raise_for_status()
        return response.json()

    async def patch_checkpoint(
        self,
        mission_id: uuid.UUID,
        update: DshMissionCheckpointUpdate,
    ) -> dict[str, Any]:
        response = await self._client.patch(
            f"/v1/dsh/missions/{mission_id}/checkpoint",
            json=update.model_dump(exclude_none=True),
        )
        response.raise_for_status()
        return response.json()

    async def chainlens_research(self, workspace_id: int, query: str) -> dict[str, Any]:
        payload = {"query": query}
        response = await self._client.post(
            f"/api/v1/workspaces/{workspace_id}/scrapers/chainlens/research?mode=sync",
            json=payload,
            timeout=httpx.Timeout(config.DSH_SYNC_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        return response.json()

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
                timeout=httpx.Timeout(config.DSH_SYNC_TIMEOUT_SECONDS),
            )
            if response.status_code == 429:
                wait = 2**attempt
                logger.warning("batch_ingest rate limited; retry in %ss", wait)
                await asyncio.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        return {}

    async def aclose(self) -> None:
        await self._client.aclose()


class DeepLeadResearchExecutor:
    """Default deterministic sequential executor for deep-lead-research missions."""

    def __init__(self, rest_client: DshRestClient) -> None:
        self.rest_client = rest_client

    async def _patch_checkpoint(
        self,
        mission_id: uuid.UUID,
        checkpoint: dict[str, Any],
        phase: str,
        progress_percent: int,
        current_subtask_id: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        update = DshMissionCheckpointUpdate(
            checkpoint=checkpoint,
            phase=phase,
            progress_percent=progress_percent,
            current_subtask_id=current_subtask_id,
            status=status,
        )
        return await self.rest_client.patch_checkpoint(mission_id, update)

    async def run(self, mission: DshMission) -> None:
        """Run the four phases sequentially, updating checkpoint after each."""
        mission_id = mission.id
        workspace_id = mission.workspace_id
        payload = mission.payload or {}
        query = payload.get("query", "") if isinstance(payload, dict) else ""

        checkpoint = mission.checkpoint or {"phase": "crawl", "subtasks": []}
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
                    await self.rest_client.batch_ingest_leads(workspace_id, leads)
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
    ) -> dict[str, Any]:
        """Convert a ChainLens source into a LeadItem-shaped dict."""
        return {
            "source": "dsh_research",
            "source_url": source.get("url"),
            "client_id": source.get("client_id"),
            "company_name": source.get("company_name"),
            "domain": source.get("domain"),
            "phone": source.get("phone"),
            "email": source.get("email"),
            "title": source.get("title"),
            "industry": source.get("industry"),
            "location": source.get("location"),
            "fit_score": source.get("fit_score", 0.0),
            "intent_score": source.get("intent_score", 0.0),
            "composite_score": source.get("composite_score"),
        }


class DshWorker:
    """Long-running sidecar worker for DSH missions."""

    def __init__(
        self,
        consumer_name: str | None = None,
        redis_client: Redis | None = None,
        executor: DeepLeadResearchExecutor | None = None,
    ) -> None:
        self.consumer_name = consumer_name or _default_consumer_name()
        self._redis = redis_client
        self._executor = executor
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

    def _lock_key(self, mission_id: uuid.UUID) -> str:
        return f"nowing:dsh:lock:{mission_id}"

    async def _redis_client(self) -> Redis:
        if self._redis is None:
            self._redis = await get_redis_client()
        return self._redis

    async def _ensure_consumer_group(self, redis_client: Redis) -> None:
        try:
            await redis_client.xgroup_create(
                name=self.stream,
                groupname=self.group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc).upper():
                raise
        except BusyGroupError:
            pass

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
        """Heartbeat: reset PEL idle time and refresh the Redis lock."""
        try:
            await redis_client.xclaim(
                self.stream,
                self.group,
                self.consumer_name,
                0,
                [msg_id],
            )
            await redis_client.expire(self._lock_key(mission_id), self.lock_ttl)
            return True
        except Exception as exc:
            logger.warning("Heartbeat failed for mission %s: %s", mission_id, exc)
            return False

    async def _autoclaim(self, redis_client: Redis) -> list[tuple[str, dict[str, str]]]:
        """Reclaim idle messages using XAUTOCLAIM."""
        claimed: list[tuple[str, dict[str, str]]] = []
        start_id = "0"
        while True:
            try:
                next_start, messages = await redis_client.xautoclaim(
                    self.stream,
                    self.group,
                    self.consumer_name,
                    config.DSH_XAUTOCLAIM_MIN_IDLE_MS,
                    start_id,
                    count=10,
                )
            except Exception as exc:
                logger.exception("XAUTOCLAIM failed: %s", exc)
                break
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
            if key_s in ("payload", "checkpoint"):
                try:
                    parsed[key_s] = json.loads(value_s)
                except json.JSONDecodeError:
                    parsed[key_s] = value_s
            else:
                parsed[key_s] = value_s
        return parsed

    async def _load_mission(
        self,
        session: AsyncSession,
        mission_id: uuid.UUID,
    ) -> DshMission | None:
        result = await session.execute(
            select(DshMission).where(DshMission.id == mission_id)
        )
        return result.scalars().first()

    async def _mission_from_stream(
        self,
        session: AsyncSession,
        payload: dict[str, Any],
    ) -> DshMission | None:
        mission_id = payload.get("mission_id")
        if not mission_id:
            return None
        try:
            return await self._load_mission(
                session,
                uuid.UUID(mission_id),
            )
        except Exception as exc:
            logger.warning("Could not load mission %s: %s", mission_id, exc)
            return None

    async def _handle_message(
        self,
        redis_client: Redis,
        msg_id: str,
        fields: dict[str, Any],
    ) -> bool:
        """Process one stream message. Returns True if XACK should be attempted."""
        parsed = self._parse_payload(fields)
        async with async_session_maker() as session:
            mission = await self._mission_from_stream(session, parsed)
            if mission is None:
                logger.error("Mission not found for stream message %s", msg_id)
                return True

            mission_id = mission.id

            # Idempotent lock check
            if not await self._try_set_lock(redis_client, mission_id):
                logger.info("Mission %s is already locked; skip", mission_id)
                return False

            # Heartbeat task
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(redis_client, mission_id, msg_id)
            )
            self._tasks.add(heartbeat_task)

            try:
                # Mark running
                service = DshMissionService()
                await service.update_checkpoint(
                    session,
                    mission,
                    status=DshMissionStatus.RUNNING.value,
                    started_at=datetime.now(UTC),
                    phase="crawl",
                    progress_percent=0,
                )
                await session.commit()

                executor = self._executor or self._build_default_executor()
                await executor.run(mission)

                # Success terminal
                await service.update_checkpoint(
                    session,
                    mission,
                    status=DshMissionStatus.SUCCESS.value,
                    completed_at=datetime.now(UTC),
                    phase="terminal",
                    progress_percent=100,
                )
                await session.commit()
                return True
            except Exception as exc:
                await session.rollback()
                logger.exception("Mission %s failed: %s", mission_id, exc)
                await self._maybe_retry_or_dlq(
                    session,
                    redis_client,
                    mission,
                    str(exc),
                )
                # Do not XACK here; retry/dlq logic decides.
                return False
            finally:
                heartbeat_task.cancel()
                self._tasks.discard(heartbeat_task)
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

    async def _maybe_retry_or_dlq(
        self,
        session: AsyncSession,
        redis_client: Redis,
        mission: DshMission,
        error_message: str,
    ) -> None:
        """Increment retry_count; if exceeded, DLQ and XACK."""
        service = DshMissionService()
        retry_count = (mission.retry_count or 0) + 1
        checkpoint = mission.checkpoint or {}
        checkpoint["attempt"] = (checkpoint.get("attempt", 0) or 0) + 1

        if retry_count >= self.max_retries:
            await service.update_checkpoint(
                session,
                mission,
                status=DshMissionStatus.DLQ.value,
                retry_count=retry_count,
                checkpoint=checkpoint,
                error={
                    "message": error_message,
                    "failed_at": datetime.now(UTC).isoformat(),
                },
            )
            await session.commit()
            try:
                await redis_client.xadd(
                    self.dlq,
                    {
                        "original_id": str(mission.id),
                        "payload": json.dumps(mission.payload),
                        "error": error_message,
                        "failed_at": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception as exc:
                logger.exception(
                    "Failed to write mission %s to DLQ: %s", mission.id, exc
                )
        else:
            await service.update_checkpoint(
                session,
                mission,
                status=DshMissionStatus.PENDING.value,
                retry_count=retry_count,
                checkpoint=checkpoint,
                error={
                    "message": error_message,
                    "failed_at": datetime.now(UTC).isoformat(),
                },
            )
            await session.commit()

    async def _heartbeat_loop(
        self,
        redis_client: Redis,
        mission_id: uuid.UUID,
        msg_id: str,
    ) -> None:
        """Periodically reset idle time and renew the lock while a mission runs."""
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            ok = await self._renew_lock_and_idle(redis_client, mission_id, msg_id)
            if not ok:
                break

    def _build_default_executor(self) -> DeepLeadResearchExecutor:
        pat = config.DSH_WORKER_PAT
        secret = config.DSH_WORKER_SECRET
        base_url = os.getenv("DSH_INTERNAL_API_URL", "http://localhost:8000")
        rest_client = DshRestClient(base_url, pat, secret)
        return DeepLeadResearchExecutor(rest_client)

    async def _read_new_messages(
        self,
        redis_client: Redis,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Read one batch of new messages from the consumer group."""
        try:
            entries = await redis_client.xreadgroup(
                groupname=self.group,
                consumername=self.consumer_name,
                streams={self.stream: ">"},
                count=1,
                block=config.DSH_REDIS_BLOCK_MS,
            )
        except Exception as exc:
            logger.error("XREADGROUP failed: %s", exc)
            return []

        messages: list[tuple[str, dict[str, Any]]] = []
        if entries:
            for _stream_name, stream_messages in entries:
                for msg_id, fields in stream_messages:
                    messages.append((msg_id, fields))
        return messages

    async def run(self) -> None:
        """Main worker loop."""
        redis_client = await self._redis_client()
        await self._ensure_consumer_group(redis_client)
        self._running = True

        last_autoclaim = 0.0
        while self._running:
            # Periodically XAUTOCLAIM idle messages
            now = asyncio.get_event_loop().time()
            if now - last_autoclaim >= self.heartbeat_interval:
                reclaimed = await self._autoclaim(redis_client)
                for msg_id, fields in reclaimed:
                    await self._handle_message(redis_client, msg_id, fields)
                last_autoclaim = now

            messages = await self._read_new_messages(redis_client)
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
        """Signal the worker to stop."""
        self._running = False


async def run_dsh_worker() -> None:
    """Entry point for the SERVICE_ROLE=dsh sidecar."""
    worker = DshWorker()
    try:
        await worker.run()
    except Exception as exc:
        logger.exception("DSH worker crashed: %s", exc)
        raise


if __name__ == "__main__":
    asyncio.run(run_dsh_worker())
