"""DSH worker main loop and message handling."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio.client import Redis
from redis.exceptions import ResponseError

from app.config import config
from app.redis_client import get_redis_client
from app.tasks.dsh_worker import errors
from app.tasks.dsh_worker.constants import _RENEW_LOCK_SCRIPT
from app.tasks.dsh_worker.helpers import _checkpoint_update
from app.tasks.dsh_worker.rest_client import DshRestClient
from app.tasks.dsh_worker_browser_operator import HumanInterventionRequired
from app.tasks.dsh_worker_langgraph import LangGraphMissionExecutor

logger = logging.getLogger(__name__)


def _dsh_call_timeout_seconds() -> float:
    """Return the live value of ``_DSH_CALL_TIMEOUT_SECONDS``.

    Tests monkeypatch ``app.tasks.dsh_worker._DSH_CALL_TIMEOUT_SECONDS`` to
    speed up hanging-call assertions. Reading it from the package namespace at
    runtime makes those patches effective without changing call sites.
    """
    import app.tasks.dsh_worker as dsh_package

    return dsh_package._DSH_CALL_TIMEOUT_SECONDS


def _legacy_executor_class() -> type:
    """Return the live ``DeepLeadResearchExecutor`` class from the package.

    Tests monkeypatch ``app.tasks.dsh_worker.DeepLeadResearchExecutor``.
    Dynamic lookup lets the patch take effect without hardcoding the import.
    """
    import app.tasks.dsh_worker as dsh_package

    return dsh_package.DeepLeadResearchExecutor


def _default_consumer_name() -> str:
    """Return a unique consumer name per process/host for load balancing."""
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


class DshWorker:
    """Long-running sidecar worker for DSH missions."""

    def __init__(
        self,
        consumer_name: str | None = None,
        redis_client: Redis | None = None,
        executor: Any | None = None,
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
                timeout=_dsh_call_timeout_seconds(),
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
        except errors.DshNonRetryableError as exc:
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
            elif config.DSH_EXECUTOR_ENGINE == "legacy":
                executor = _legacy_executor_class()(self.rest_client)
            else:
                executor = LangGraphMissionExecutor(self.rest_client)
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
            except HumanInterventionRequired as e:
                logger.warning("Mission %s requires human intervention: %s", mission_id, e)
                # Save checkpoint and pause
                workspace_id = mission.get("workspace_id") if isinstance(mission, dict) else mission.workspace_id
                user_id = mission.get("user_id") if isinstance(mission, dict) else mission.user_id
                challenge = getattr(e, "challenge", str(e))
                payload = self._mission_payload(mission)
                target_url = str(payload.get("target_url") or "")

                now = datetime.now(UTC)
                expires_at = now + timedelta(seconds=900)
                checkpoint = self._mission_checkpoint(mission)
                checkpoint["takeover"] = {
                    "challenge": challenge,
                    "target_url": target_url,
                    "started_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                }

                await self.rest_client.patch_checkpoint(
                    mission_id,
                    _checkpoint_update(
                        status="running",
                        phase="waiting_for_human",
                        current_subtask_id="cdp_crawl",
                        checkpoint=checkpoint,
                    ),
                )
                # 15-minute takeover TTL. Resume route must delete this key.
                takeover_key = f"dsh:lock:takeover:{workspace_id}:{mission_id}"
                await redis_client.setex(takeover_key, 900, str(user_id) if user_id else "1")
                await redis_client.xack(self.stream, self.group, msg_id)
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

            return True
        except asyncio.CancelledError:
            logger.info(
                "Mission %s cancelled (heartbeat/lock lost or shutdown)", mission_id
            )
            return False
        except errors.DshNonRetryableError as exc:
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
            timeout=_dsh_call_timeout_seconds(),
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
