"""RunEventWriter — persist SSE events for background agent runs to PostgreSQL.

Sync write() enqueues events from middleware hooks (sync call sites).
Async run_flush_loop() drains the queue: INSERT INTO chat_run_events, then
PUBLISH to Redis. DB is always written first (C6: never publish unpersisted).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import insert, select, text, update

from app.db import ChatRun, ChatRunEvent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

log = logging.getLogger(__name__)

_FLUSH_BATCH_SIZE = 50
_FLUSH_INTERVAL_MS = 25
_MAX_PAYLOAD_BYTES = 256 * 1024  # M8: cap individual event size to prevent TOAST/replay blowups


class RunEventWriter:
    """Persist SSE events to DB and publish to Redis for live SSE tail.

    Thread-safety: write() is sync-safe from any asyncio coroutine.
    run_flush_loop() must run as a separate asyncio.Task in the same event loop.
    """

    def __init__(
        self,
        run_id: UUID,
        redis_client,  # aioredis or redis.asyncio client
        session_factory,  # async_sessionmaker or shielded_async_session
    ) -> None:
        self._run_id = run_id
        self._redis = redis_client
        self._session_factory = session_factory
        self._queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue(maxsize=10000)
        self._next_seq: int | None = None
        self._stop = asyncio.Event()
        # For resume dedup (C4): populated by _seed_seen_events()
        self._seen_spawn_agents: set[str] = set()
        self._seen_source_keys: set[str] = set()
        self._seen_attribution_agents: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, event_type: str, payload: dict) -> None:
        """SYNC enqueue — safe to call from sync middleware hooks (30+ sites)."""
        # M8: enforce per-event payload size cap
        try:
            if len(json.dumps(payload)) > _MAX_PAYLOAD_BYTES:
                log.warning(
                    "RunEventWriter payload %s exceeds %d bytes — dropping",
                    event_type, _MAX_PAYLOAD_BYTES,
                )
                return
        except (TypeError, ValueError):
            log.warning("RunEventWriter payload not JSON-serializable — dropping %s", event_type)
            return
        try:
            self._queue.put_nowait((event_type, payload))
        except asyncio.QueueFull:
            self._coalesce_or_drop(event_type, payload)

    async def run_flush_loop(self) -> None:
        """Drain queue → INSERT → PUBLISH. Call as asyncio.Task alongside agent task."""
        await self._seed_next_seq()
        await self._seed_seen_events()

        while not self._stop.is_set() or not self._queue.empty():
            batch = await self._drain_batch()
            if not batch:
                if self._stop.is_set():
                    break
                await asyncio.sleep(_FLUSH_INTERVAL_MS / 1000)
                continue
            await self._flush_batch(batch)

    async def stop(self) -> None:
        """Signal flush loop to stop; flush loop drains remaining queue before exit.
        Caller MUST `await flush_task` after stop() to ensure batch in-flight commits.
        """
        # Bound the wait so producers writing during shutdown can't deadlock us.
        deadline = asyncio.get_event_loop().time() + 5.0
        while not self._queue.empty() and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.01)
        self._stop.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _coalesce_or_drop(self, event_type: str, payload: dict) -> None:
        """On queue overflow: coalesce text-delta for same agentId, drop others."""
        if event_type != "text-delta":
            log.warning("RunEventWriter queue full — dropping %s event", event_type)
            return
        agent_id = payload.get("agentId", "")
        # Scan from end to find existing text-delta for same agent and replace
        queue_list = list(self._queue._queue)  # type: ignore[attr-defined]
        for i in range(len(queue_list) - 1, -1, -1):
            et, pl = queue_list[i]
            if et == "text-delta" and pl.get("agentId") == agent_id:
                queue_list[i] = (event_type, payload)
                # Rebuild deque
                new_dq: deque = deque(queue_list, maxlen=self._queue.maxsize)
                self._queue._queue = new_dq  # type: ignore[attr-defined]
                return
        # No prior text-delta for this agent — drop (queue is full)
        log.warning("RunEventWriter queue full — dropping text-delta for agent %s", agent_id)

    async def _seed_next_seq(self) -> None:
        """Seed _next_seq from DB so resume continues the sequence (H2)."""
        async with self._session_factory() as session:
            row = await session.execute(
                text(
                    "SELECT COALESCE(MAX(seq), -1) + 1 FROM chat_run_events WHERE run_id = :rid"
                ),
                {"rid": str(self._run_id)},
            )
            self._next_seq = row.scalar()
            log.debug("RunEventWriter seeded _next_seq=%d for run %s", self._next_seq, self._run_id)

    async def _seed_seen_events(self) -> None:
        """Load existing event log to build dedup sets for resume (C4)."""
        async with self._session_factory() as session:
            rows = await session.execute(
                select(ChatRunEvent.event_type, ChatRunEvent.payload).where(
                    ChatRunEvent.run_id == self._run_id
                )
            )
            for event_type, payload in rows:
                if not isinstance(payload, dict):
                    continue
                if event_type == "orchestra-spawn":
                    agent_id = payload.get("agentId") or (payload.get("data") or {}).get("agentId")
                    if agent_id:
                        self._seen_spawn_agents.add(agent_id)
                elif event_type == "data-orchestra-source-fetched":
                    data = payload.get("data") or {}
                    key = f"{data.get('agentId')}:{data.get('domain')}"
                    self._seen_source_keys.add(key)
                elif event_type == "data-orchestra-model-attribution":
                    data = payload.get("data") or {}
                    agent_id = data.get("agentId")
                    if agent_id:
                        self._seen_attribution_agents.add(agent_id)

    def _should_dedup(self, event_type: str, payload: dict) -> bool:
        """Return True if this event is a duplicate of an already-persisted event (C4)."""
        if not isinstance(payload, dict):
            return False
        if event_type == "orchestra-spawn":
            agent_id = payload.get("agentId") or (payload.get("data") or {}).get("agentId")
            if agent_id and agent_id in self._seen_spawn_agents:
                return True
        elif event_type == "data-orchestra-source-fetched":
            data = payload.get("data") or {}
            key = f"{data.get('agentId')}:{data.get('domain')}"
            if key in self._seen_source_keys:
                return True
        elif event_type == "data-orchestra-model-attribution":
            data = payload.get("data") or {}
            agent_id = data.get("agentId")
            if agent_id and agent_id in self._seen_attribution_agents:
                return True
        return False

    async def _drain_batch(self) -> list[tuple[str, dict]]:
        """Collect up to _FLUSH_BATCH_SIZE events, waiting up to _FLUSH_INTERVAL_MS."""
        batch: list[tuple[str, dict]] = []
        deadline = asyncio.get_event_loop().time() + (_FLUSH_INTERVAL_MS / 1000)

        while len(batch) < _FLUSH_BATCH_SIZE:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                batch.append(item)
            except asyncio.TimeoutError:
                break

        return batch

    async def _flush_batch(self, batch: list[tuple[str, dict]]) -> None:
        """INSERT batch into chat_run_events, then PUBLISH to Redis (C6: insert before publish)."""
        rows_to_insert = []
        rows_to_publish = []
        # C4 atomicity: snapshot seen-sets BEFORE mutation so we can rollback on error
        snap_spawn = set(self._seen_spawn_agents)
        snap_source = set(self._seen_source_keys)
        snap_attr = set(self._seen_attribution_agents)

        for event_type, payload in batch:
            if self._should_dedup(event_type, payload):
                log.debug("RunEventWriter dedup-skip %s for run %s", event_type, self._run_id)
                continue

            seq = self._next_seq
            self._next_seq += 1
            row = {
                "run_id": str(self._run_id),
                "seq": seq,
                "event_type": event_type,
                "payload": payload,
            }
            rows_to_insert.append(row)
            rows_to_publish.append(row)

            # Update seen-sets for dedup (rolled back atomically on flush error)
            if not isinstance(payload, dict):
                continue
            if event_type == "orchestra-spawn":
                agent_id = payload.get("agentId") or (payload.get("data") or {}).get("agentId")
                if agent_id:
                    self._seen_spawn_agents.add(agent_id)
            elif event_type == "data-orchestra-source-fetched":
                data = payload.get("data") or {}
                key = f"{data.get('agentId')}:{data.get('domain')}"
                self._seen_source_keys.add(key)
            elif event_type == "data-orchestra-model-attribution":
                data = payload.get("data") or {}
                agent_id = data.get("agentId")
                if agent_id:
                    self._seen_attribution_agents.add(agent_id)

        if not rows_to_insert:
            return

        max_seq_in_batch = max(r["seq"] for r in rows_to_insert)

        try:
            async with self._session_factory() as session:
                # C6: INSERT first, then PUBLISH — never publish unpersisted events
                for row in rows_to_insert:
                    await session.execute(
                        text(
                            "INSERT INTO chat_run_events (run_id, seq, event_type, payload) "
                            "VALUES (:run_id, :seq, :event_type, :payload::jsonb) "
                            "ON CONFLICT (run_id, seq) DO NOTHING"
                        ),
                        {
                            "run_id": row["run_id"],
                            "seq": row["seq"],
                            "event_type": row["event_type"],
                            "payload": json.dumps(row["payload"]),
                        },
                    )
                await session.execute(
                    text(
                        "UPDATE chat_runs SET last_event_seq = :seq WHERE id = :rid"
                    ),
                    {"seq": max_seq_in_batch, "rid": str(self._run_id)},
                )
                await session.commit()

            # PUBLISH only after successful commit (C6)
            channel = f"nowing:run:{self._run_id}"
            for row in rows_to_publish:
                try:
                    await self._redis.publish(channel, json.dumps(row))
                except Exception as exc:
                    log.warning("Redis publish failed for run %s: %s", self._run_id, exc)

        except Exception as exc:
            log.error(
                "RunEventWriter flush failed for run %s (seq range %d-%d): %s",
                self._run_id,
                rows_to_insert[0]["seq"],
                max_seq_in_batch,
                exc,
                exc_info=True,
            )
            # Atomic restore: seq + seen-sets rolled back together so retry isn't dedup-skipped
            self._next_seq = rows_to_insert[0]["seq"]
            self._seen_spawn_agents = snap_spawn
            self._seen_source_keys = snap_source
            self._seen_attribution_agents = snap_attr
