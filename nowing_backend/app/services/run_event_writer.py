"""RunEventWriter — persist SSE events for background agent runs to PostgreSQL.

Sync write() enqueues events from middleware hooks (sync call sites).
Async run_flush_loop() drains the queue: INSERT INTO chat_run_events, then
PUBLISH to Redis. DB is always written first (C6: never publish unpersisted).

AC7 (T5): replaced asyncio.Queue + private _queue._queue mutation with
  collections.deque(maxlen=10000) + asyncio.Event signal. Per-agentId
  _pending_delta dict coalesces text-delta upstream before deque insertion.

AC8 (T6): pg_advisory_xact_lock per run_id in _flush_batch guards seq
  allocation so two concurrent writers cannot collide on same seq.

AC9 (T8): heartbeat task in run_flush_loop updates last_heartbeat_at every
  30s. mark_abandoned_runs_on_startup filters by heartbeat age so healthy
  runs on sibling workers are not incorrectly marked abandoned.

AC11 (T11): Redis publish retries 3x with 100ms backoff per message on
  transient failure. DB is canonical — pubsub is fast-path only.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import insert, select, text, update

from app.db import ChatRun, ChatRunEvent

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

log = logging.getLogger(__name__)

_FLUSH_BATCH_SIZE = 50
_FLUSH_INTERVAL_MS = 25
_MAX_PAYLOAD_BYTES = 256 * 1024  # cap individual event size to prevent TOAST/replay blowups
_HEARTBEAT_INTERVAL_S = 30  # T8: update last_heartbeat_at every 30s
_PUBLISH_RETRY_TIMES = 3
_PUBLISH_RETRY_DELAY_S = 0.1


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
        # T5: deque + event instead of asyncio.Queue (eliminates private _queue._queue access)
        self._deque: collections.deque[tuple[str, dict]] = collections.deque(maxlen=10000)
        self._signal = asyncio.Event()
        # Per-agentId text-delta coalescing (upstream of deque, never blocks)
        self._pending_delta: dict[str, tuple[str, dict]] = {}
        self._next_seq: int | None = None
        self._stop = asyncio.Event()
        self._overflow_count = 0
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

        # T5: text-delta coalescing — per-agentId for orchestra progress updates.
        # Main synthesis text-delta (no agentId) goes to deque directly to:
        #   1. Preserve all tokens (replace would drop ~80% at 25ms flush intervals)
        #   2. Maintain text-start → text-delta ordering (pending_delta drains before deque)
        if event_type == "text-delta":
            agent_id = payload.get("agentId", "") or (payload.get("data") or {}).get("agentId", "")
            if agent_id:
                # Orchestra agent progress update — keep latest only (coalesce)
                self._pending_delta[agent_id] = (event_type, payload)
                self._signal.set()
                return
            # Main synthesis text — fall through to deque (preserves all tokens + order)

        # T5: deque.append is atomic in CPython (GIL). On maxlen overflow the OLDEST
        # item is silently rotated out. For non-text events this is a data-loss risk —
        # we track it for ops visibility (overflow_count metric) but accept it since
        # 10000 queued items = severe backpressure indicating a different problem.
        was_full = len(self._deque) >= (self._deque.maxlen or 10001)
        self._deque.append((event_type, payload))
        if was_full:
            self._overflow_count += 1
            log.warning(
                "RunEventWriter deque overflow (count=%d) — oldest event dropped to enqueue %s",
                self._overflow_count, event_type,
            )
        self._signal.set()

    async def run_flush_loop(self) -> None:
        """Drain queue → INSERT → PUBLISH. Call as asyncio.Task alongside agent task."""
        await self._seed_next_seq()
        await self._seed_seen_events()

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            while not self._stop.is_set() or self._deque or self._pending_delta:
                batch = await self._drain_batch()
                if not batch:
                    if self._stop.is_set():
                        break
                    await asyncio.sleep(_FLUSH_INTERVAL_MS / 1000)
                    continue
                await self._flush_batch(batch)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass

    async def stop(self) -> None:
        """Signal flush loop to stop; flush loop drains remaining queue before exit.
        Caller MUST `await flush_task` after stop() to ensure batch in-flight commits.
        """
        self._signal.set()
        deadline = asyncio.get_running_loop().time() + 5.0
        while (self._deque or self._pending_delta) and asyncio.get_running_loop().time() < deadline:
            self._signal.set()
            await asyncio.sleep(0.01)
        self._stop.set()
        self._signal.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """T8/AC9: Update last_heartbeat_at every 30s so startup fence is accurate."""
        while not self._stop.is_set():
            try:
                await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
                if self._stop.is_set():
                    break
                async with self._session_factory() as session:
                    await session.execute(
                        text(
                            "UPDATE chat_runs SET last_heartbeat_at = NOW() WHERE id = :rid"
                        ),
                        {"rid": str(self._run_id)},
                    )
                    await session.commit()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                log.warning(
                    "RunEventWriter heartbeat update failed for run %s: %s",
                    self._run_id, exc,
                )

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
        deadline = asyncio.get_running_loop().time() + (_FLUSH_INTERVAL_MS / 1000)

        # Wait for signal that deque or pending_delta has data
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining > 0 and not self._deque and not self._pending_delta:
            try:
                self._signal.clear()
                await asyncio.wait_for(self._signal.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                pass

        # Drain pending_delta first (coalesced text-deltas)
        if self._pending_delta:
            keys = list(self._pending_delta.keys())
            for key in keys:
                batch.append(self._pending_delta.pop(key))
                if len(batch) >= _FLUSH_BATCH_SIZE:
                    return batch

        # Drain deque
        while batch and len(batch) < _FLUSH_BATCH_SIZE and self._deque:
            batch.append(self._deque.popleft())
        # If batch empty so far, drain from deque up to limit
        while len(batch) < _FLUSH_BATCH_SIZE and self._deque:
            batch.append(self._deque.popleft())

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
                # T6/AC8: per-run advisory lock — guards seq allocation so two concurrent
                # writers on the same run_id cannot allocate duplicate seqs.
                # pg_advisory_xact_lock is scoped to transaction → auto-released on commit.
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(cast(:rid as text), 0))"),
                    {"rid": str(self._run_id)},
                )
                # Re-seed _next_seq under the lock to pick up any seqs written by other writers
                row_seq = await session.execute(
                    text(
                        "SELECT COALESCE(MAX(seq), -1) + 1 FROM chat_run_events WHERE run_id = :rid"
                    ),
                    {"rid": str(self._run_id)},
                )
                db_next_seq = row_seq.scalar()
                if db_next_seq > rows_to_insert[0]["seq"]:
                    # Another writer advanced seq — reassign all rows
                    offset = db_next_seq - rows_to_insert[0]["seq"]
                    for r in rows_to_insert:
                        r["seq"] += offset
                    max_seq_in_batch = max(r["seq"] for r in rows_to_insert)
                    self._next_seq = max_seq_in_batch + 1

                # C6: INSERT first, then PUBLISH — never publish unpersisted events
                for row in rows_to_insert:
                    await session.execute(
                        text(
                            "INSERT INTO chat_run_events (run_id, seq, event_type, payload) "
                            "VALUES (:run_id, :seq, :event_type, cast(:payload as jsonb)) "
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

            # T11/AC11: PUBLISH after commit with per-message retry
            channel = f"nowing:run:{self._run_id}"
            for row in rows_to_publish:
                for attempt in range(_PUBLISH_RETRY_TIMES):
                    try:
                        await self._redis.publish(channel, json.dumps(row))
                        break
                    except Exception as exc:
                        if attempt < _PUBLISH_RETRY_TIMES - 1:
                            await asyncio.sleep(_PUBLISH_RETRY_DELAY_S)
                        else:
                            log.warning(
                                "Redis publish failed after %d retries for run %s: %s",
                                _PUBLISH_RETRY_TIMES, self._run_id, exc,
                            )

        except Exception as exc:
            log.error(
                "RunEventWriter flush failed for run %s (seq range %d-%d): %s",
                self._run_id,
                rows_to_insert[0]["seq"],
                max_seq_in_batch,
                exc,
                exc_info=True,
            )
            # Atomic restore: seq + seen-sets + events rolled back together so retry succeeds
            self._next_seq = rows_to_insert[0]["seq"]
            self._seen_spawn_agents = snap_spawn
            self._seen_source_keys = snap_source
            self._seen_attribution_agents = snap_attr
            # Re-enqueue events at front of deque so they're retried in next flush cycle
            for event_type, payload in reversed(batch):
                self._deque.appendleft((event_type, payload))
            self._signal.set()
