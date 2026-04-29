---
storyId: 9-UX-1b
storyTitle: Background Agent Resume — Persistent Execution + Multi-Run + DB Event Log
epicParent: epic-9-crypto-orchestra
dependsOn: [Story 9-UX-1 DONE]
blocks: []
relatedFRs: [FR35 Graceful Degradation, FR27 Comprehensive Analysis]
relatedNFRs: [NFR-Q1 Resilience, NFR-Q3 Graceful Degradation, NFR-UX Live Research Visibility]
priority: P0 (Phase 2 UX overhaul — fixes "research lost on refresh" UX failure surfaced during 9-UX-1 live test)
estimatedEffort: 2 weeks (1 BE + 0.5 FE) — bumped from 1.5w after v2 review found 7 critical design fixes
status: done  # 2026-04-26: all patches applied via 9-UX-1c; 47 BE + 20 FE tests pass; integration tests pass
revision: v2 (2026-04-25)  # v1 had design holes flagged in adversarial review; v2 addresses C1-C7 + H1-H8
createdAt: 2026-04-25
author: Luisphan + Claude (carved out from 9-UX-1 production findings)
---

## Revision History

- **v2 (2026-04-25)** — Adversarial review found 7 critical + 8 high issues. Story updated to fix:
  - C1: LangGraph thread_id collision under multi-run → introduce `langgraph_thread_id = "run-{uuid}"`
  - C2: `anyio.CancelScope(shield=True)` is wrong primitive → use `_active_runs: dict` + `add_done_callback` (codebase pattern)
  - C3: SSE replay→subscribe race window → SUBSCRIBE first, buffer, SELECT, drain
  - C4: Resume re-emits orchestra-spawn for completed sub-agents → `_seen_spawn_agents` dedup
  - C5: `_emit_orchestra_event` is sync, RunEventWriter.write was async → split sync `write()` + async `run_flush_loop()`
  - C6: PUBLISH-before-INSERT crash window → invariant: PUBLISH only AFTER successful COMMIT
  - C7: `/regenerate` parity vague → byte-equivalent SSE wire format contract + regression test
  - H1-H8: FK target naming, writer counter resume, session_id uniqueness, model_id columns, replay sentinel, auth checks, checkpoint selection rule, atom multi-run audit
  - Task count: 23 → 26 (added T13 parity test, T14 dedup test, T26 single-worker constraint)
- **v1 (2026-04-25)** — Initial story carved from 9-UX-1 production findings.

# Story 9-UX-1b: Background Agent Resume

## User Story

**As a** crypto researcher kicking off a long-running comprehensive token analysis (2-15 minutes),
**I want** the agent's work to persist across browser refreshes, navigation away, accidental tab close, and even backend process restarts —
**So that** I never lose 5+ minutes of LLM-generated research because of a misclick or a flaky network, and I can confidently start parallel queries knowing each will complete in the background.

**Bar to clear**: User submits "phân tích toàn diện UNI", refreshes the page mid-stream → orchestra strip restored within 1 second showing the same progress, and continues live as if nothing happened.

---

## Context

### Problem surfaced during 9-UX-1 live verification (2026-04-25)

During production testing of Story 9-UX-1 Live Research Lab, two failure modes were observed end-to-end:

1. **SSE cancel on navigation**: User navigates from `/new-chat/32` to `/new-chat/30` mid-stream → Starlette cancels the request → `astream_events()` task dies → 4/6 sub-agents that had completed are LOST (not persisted to DB), only LangGraph checkpoint remains. The orchestra strip vanishes from the original chat. User sees empty thread on return.

2. **Worker restart kills task**: 9-UX-1 v3 patches removed retry caps so agents retry indefinitely. But uvicorn restart still kills all running asyncio tasks. The LangGraph checkpoint persists state, but no mechanism re-spawns the task.

### Root cause

`stream_new_chat()` is an async generator scoped to the HTTP request. Three independent layers all need fixing:

- **Lifecycle**: Stream dies with the request — needs detached task survival
- **Persistence**: SSE events live only in-memory + Redis pubsub — needs DB event log
- **Discoverability**: FE has no way to ask "is there a run in progress for thread N" — needs `/runs/active` endpoint

### Why this story (not back into 9-UX-1)

9-UX-1 is marked `done` (37 patches across 2 review rounds, 58 tests pass). The Research Lab UI works perfectly when the stream is healthy. This story carves out the **execution layer** as a clean follow-up:

- 9-UX-1 = "what user sees" (UI components, narration, source attribution)
- 9-UX-1b = "where execution lives" (runs as background tasks, replays from DB)

Plan source: [/Users/luisphan/.claude/plans/harmonic-cuddling-glacier.md](/Users/luisphan/.claude/plans/harmonic-cuddling-glacier.md) (rewritten 2026-04-25 v3 after user clarification: PostgreSQL durable + replay-all + multi-run + retry-forever).

---

## Prerequisites

- [x] Story 9-UX-1 DONE — Research Lab UI components stable (verified live in browser)
- [x] LangGraph `AsyncPostgresSaver` checkpointer wired (verified via `app/agents/new_chat/checkpointer.py:90`)
- [x] Redis broker running (existing Celery infrastructure)
- [x] `_stream_writer_var` ContextVar shipped in 9-UX-1 V2-D1 (existing in `chat_deepagent.py:443`)
- [x] `shielded_async_session()` helper available (`app/db.py:2333`)

---

## Acceptance Criteria

### AC1 — DB schema: `chat_runs` + `chat_run_events`

Two new tables via Alembic migration **134_add_chat_runs.py** + **135_add_chat_run_heartbeat.py** (applied 2026-04-26). **Idempotent** (follow project pattern in `alembic/versions/115_add_page_purchases_table.py`):

```sql
chat_runs (
  id UUID PK DEFAULT gen_random_uuid(),
  thread_id INTEGER FK→new_chat_threads(id) ON DELETE CASCADE,
  created_by_id UUID FK→user.id,                  -- H1: singular table name (codebase convention)
  session_id VARCHAR(64) NOT NULL,                 -- H3: NOT UNIQUE (multi-run/thread allows reuse forms)
  langgraph_thread_id VARCHAR(96) NOT NULL,        -- C1: separate from chat thread_id, format: "run-{run_id}"
  user_query TEXT,
  llm_config_id INTEGER FK→new_llm_configs.id,     -- H4: persist for resume (avoid silent model swap)
  model_id INTEGER,                                -- H4: optional model override
  mentioned_document_ids JSONB,                    -- H4: persist for resume context
  disabled_tools JSONB,                            -- H4: persist for resume context
  status VARCHAR(16) DEFAULT 'running',            -- M10 state machine: see below
  last_event_seq INTEGER DEFAULT 0,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  final_message_id INTEGER FK→new_chat_messages.id,
  error_message VARCHAR(8000)                      -- M8: bounded length (truncate before INSERT)
)

chat_run_events (
  id BIGSERIAL PK,
  run_id UUID FK→chat_runs.id ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (run_id, seq)
)

CREATE INDEX idx_chat_runs_thread_active ON chat_runs(thread_id) WHERE status = 'running';
CREATE INDEX idx_chat_runs_thread_created ON chat_runs(thread_id, started_at DESC);
CREATE INDEX idx_chat_run_events_run_seq ON chat_run_events(run_id, seq);
```

**State machine (M10)** — `status` transitions:
- `running` → `completed` (normal end)
- `running` → `failed` (uncaught exception, error_message populated)
- `running` → `cancelled` (user clicked stop button)
- `running` → `abandoned` (worker died — set by `mark_abandoned_runs_on_startup`)
- `abandoned` → `running` (user clicked Resume button → spawn new task from checkpoint)
- All other transitions REJECTED (e.g. `cancelled` cannot resume — must start fresh run).

**C1 — LangGraph thread isolation for multi-run**: `langgraph_thread_id` is the key passed to `AsyncPostgresSaver` `configurable.thread_id`. Format `f"run-{run_id}"` (UUID-derived). This prevents 2 concurrent runs on the same chat thread from sharing checkpoint state. After run completes successfully, the final assistant message is reconciled into `new_chat_messages` table keyed by chat `thread_id` (not `langgraph_thread_id`) — so the chat history view stays unified.

ORM models in `app/db.py` follow `BaseModel + TimestampMixin` pattern (override since UUID PK).

### AC2 — `RunEventWriter` service

**C5 — sync emit + async flush loop** to preserve compatibility with sync `_emit_orchestra_event` call sites in middleware (30+ sites):

New file [`app/services/run_event_writer.py`](nowing_backend/app/services/run_event_writer.py):

```python
class RunEventWriter:
    def __init__(self, run_id: UUID, redis_client, session_factory):
        self._run_id = run_id
        self._queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue(maxsize=10000)  # M6: bounded
        self._redis = redis_client
        self._session_factory = session_factory
        self._next_seq: int | None = None  # H2: seeded from DB on first flush
        self._stop = asyncio.Event()

    def write(self, event_type: str, payload: dict) -> None:
        """SYNC enqueue — safe to call from sync middleware hooks."""
        try:
            self._queue.put_nowait((event_type, payload))
        except asyncio.QueueFull:
            # M6 backpressure: coalesce text-delta events for same agent
            self._coalesce_or_drop(event_type, payload)

    async def run_flush_loop(self) -> None:
        """Started by start_run() as separate task. Drains queue → DB INSERT → Redis PUBLISH."""
        # H2: seed counter from DB so resume continues sequence
        async with self._session_factory() as session:
            row = await session.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM chat_run_events WHERE run_id = :rid",
                {"rid": self._run_id},
            )
            self._next_seq = row.scalar()

        while not self._stop.is_set():
            batch = await self._drain_batch(max_events=50, max_wait_ms=25)  # C6: 25ms instead of 100ms
            if not batch:
                continue
            async with self._session_factory() as session:
                # C6: INSERT FIRST, then PUBLISH — never publish unpersisted events
                rows = []
                for event_type, payload in batch:
                    rows.append({
                        "run_id": self._run_id,
                        "seq": self._next_seq,
                        "event_type": event_type,
                        "payload": payload,
                    })
                    self._next_seq += 1
                # ON CONFLICT DO NOTHING for idempotency (run_id, seq) UNIQUE
                await session.execute(insert_stmt.on_conflict_do_nothing())
                await session.execute(
                    "UPDATE chat_runs SET last_event_seq = :seq WHERE id = :rid",
                    {"seq": self._next_seq - 1, "rid": self._run_id},
                )
                await session.commit()
            # PUBLISH only after successful commit (C6)
            for row in rows:
                await self._redis.publish(f"nowing:run:{self._run_id}", json.dumps(row))

    async def stop(self) -> None:
        """Graceful shutdown — drain remaining queue then signal stop."""
        # Drain in tight loop until empty, then signal
        while not self._queue.empty():
            await asyncio.sleep(0.01)
        self._stop.set()
```

**Critical correctness invariants**:
- **C5**: `write()` is SYNC — middleware sync hooks unchanged
- **C6**: PUBLISH ALWAYS AFTER successful DB INSERT+COMMIT — DB is source of truth
- **H2**: `_next_seq` seeded from DB on flush-loop start (resume safety)
- **Idempotency**: `INSERT ... ON CONFLICT (run_id, seq) DO NOTHING` — late retries silently skipped
- **M6 backpressure**: bounded queue (`maxsize=10000`); on overflow, coalesce consecutive `text-delta` events for same agentId (keep latest only — they're cumulative)
- **Graceful shutdown**: `stop()` awaits queue drain — no events lost on normal completion

### AC3 — Detached task lifecycle (`run_manager.py`)

**C2 — use codebase pattern**: drop `anyio.CancelScope` (wrong primitive — it's request-scoped). Use `_background_tasks: set[Task]` + `add_done_callback` exactly like existing `new_chat_routes.py:62-100`. `asyncio.create_task` snapshots ContextVars correctly so writer var propagates into nested sub-agent tasks.

New file [`app/tasks/chat/run_manager.py`](nowing_backend/app/tasks/chat/run_manager.py):

```python
# Module-level strong refs (M1: single-uvicorn-worker constraint — see Dev Notes)
_active_runs: dict[UUID, asyncio.Task] = {}
_cancel_events: dict[UUID, asyncio.Event] = {}

async def start_run(
    thread_id: int,
    user_query: str,
    user_id: UUID,
    llm_config_id: int | None,
    model_id: int | None,
    mentioned_document_ids: list[int] | None,
    disabled_tools: list[str] | None,
) -> ChatRun:
    # 1. INSERT chat_runs
    run = ChatRun(
        thread_id=thread_id,
        created_by_id=user_id,
        session_id=f"{thread_id}-{uuid4().hex[:8]}",
        langgraph_thread_id=f"run-{run_id}",  # C1: isolation key
        user_query=user_query,
        llm_config_id=llm_config_id,
        model_id=model_id,
        mentioned_document_ids=mentioned_document_ids,
        disabled_tools=disabled_tools,
        status="running",
    )
    async with shielded_async_session() as session:
        session.add(run)
        await session.commit()
        await session.refresh(run)

    # 2. Setup writer + cancel signaling
    writer = RunEventWriter(run.id, get_redis(), shielded_async_session)
    _cancel_events[run.id] = asyncio.Event()

    # 3. Spawn detached task — context snapshot includes writer var
    async def _execute():
        token = _stream_writer_var.set(writer.write)
        flush_task = asyncio.create_task(writer.run_flush_loop())
        try:
            await _stream_agent_events_detached(
                run_id=run.id,
                langgraph_thread_id=run.langgraph_thread_id,
                cancel_event=_cancel_events[run.id],
                writer=writer,
                # ... agent config passed through
            )
            await _mark_run_completed(run.id)
        except asyncio.CancelledError:
            await _mark_run_cancelled(run.id)
            raise
        except Exception as exc:
            err = (str(exc) or repr(exc))[:8000]  # M8 truncate
            await _mark_run_failed(run.id, err)
            raise
        finally:
            _stream_writer_var.reset(token)
            await writer.stop()  # graceful drain
            try:
                flush_task.cancel()
                await flush_task
            except (asyncio.CancelledError, BaseException):
                pass

    task = asyncio.create_task(_execute())
    _active_runs[run.id] = task

    def _cleanup(t: asyncio.Task):
        _active_runs.pop(run.id, None)
        _cancel_events.pop(run.id, None)
    task.add_done_callback(_cleanup)

    return run

async def cancel_run(run_id: UUID) -> bool:
    """Cooperative cancel — sets event, then task.cancel() as fallback."""
    event = _cancel_events.get(run_id)
    if event:
        event.set()  # cooperative — retry loops check between sleeps
    task = _active_runs.get(run_id)
    if task and not task.done():
        # Give 2s for cooperative cancel via event, then force cancel
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
        return True
    return False

async def resume_run(run_id: UUID) -> ChatRun:
    """Spawn new task continuing from LangGraph checkpoint (C4 — dedup events).

    H7 checkpoint selection rule: pick LATEST checkpoint where last message is NOT a
    HumanMessage (mirrors /regenerate logic). If checkpoint state is corrupted/empty,
    raise HTTPException(409) — no fallback inline.
    """
    run = await _load_run(run_id)
    if run.status not in ("abandoned",):
        raise HTTPException(409, "only abandoned runs can be resumed")
    # Spawn similar to start_run but with checkpoint_id resolved from latest non-human-end
    # ...

async def mark_abandoned_runs_on_startup() -> int:
    """M2: wrapped in try/except for fresh-deploy migration race.
    M5: skip when UVICORN_RELOAD=true (dev hot-reload protection)."""
    if os.getenv("UVICORN_RELOAD") == "true":
        return 0
    try:
        async with shielded_async_session() as session:
            result = await session.execute(
                "UPDATE chat_runs SET status='abandoned' WHERE status='running' RETURNING id"
            )
            await session.commit()
            return result.rowcount
    except Exception as exc:  # ProgrammingError, UndefinedTable on fresh deploy
        log.warning("mark_abandoned_runs_on_startup skipped (table not ready?): %s", exc)
        return 0
```

**Cancel propagation invariants (C12)**: v3's retry-forever middleware uses bare `except Exception:` — does NOT catch `asyncio.CancelledError` (which is `BaseException`). Cancel propagates correctly into retry loops. The `cancel_event` is checked between `asyncio.sleep` calls inside `SubAgentResilienceMiddleware` retry loop (T5 sub-task: add `cancel_event.is_set() → raise CancelledError` check).

### AC4 — New REST endpoints

**H6 — Auth on every endpoint**: all `/runs/*` endpoints `Depends(current_active_user)` + call `check_thread_access(session, thread, user, require_ownership=False)`. Returns 403 if user has no thread access (mirrors existing `/regenerate` pattern at `new_chat_routes.py:1206`).

Add to [`app/routes/new_chat_routes.py`](nowing_backend/app/routes/new_chat_routes.py):

- **`POST /api/v1/threads/{thread_id}/runs`** — body: `StartRunRequest{user_query, search_space_id, llm_config_id?, model_id?, mentioned_document_ids?, disabled_tools?}` → returns `{run_id: UUID, session_id: str, status: "running"}` synchronously after dispatch (target <300ms server-side processing time, exclusive of network).

- **`GET /api/v1/threads/{thread_id}/runs/active`** → returns `{runs: [{id, session_id, status, last_event_seq, started_at, error_message?}]}`. Filter `status IN ('running', 'abandoned')` ordered `started_at DESC`. Used by FE on mount.

- **`GET /api/v1/threads/{thread_id}/runs/{run_id}/stream`** — SSE endpoint with **C3 race-free protocol**:

  ```
  1. SUBSCRIBE Redis pubsub `nowing:run:{run_id}` → buffer messages in memory
  2. SELECT * FROM chat_run_events WHERE run_id=$1 ORDER BY seq → record max_replayed_seq
  3. yield each replayed event with envelope { _replay: true, seq, event_type, data }   (H5)
  4. yield { type: "replay-end", last_seq: max_replayed_seq }                            (H5 sentinel)
  5. drain buffer dropping any message with seq <= max_replayed_seq                       (C3 dedup)
  6. yield remaining buffered messages                                                    (C3 plug gap)
  7. continue tailing pubsub until chat_runs.status changes to terminal value
  8. on terminal status, yield { type: "run-end", status, completed_at } then close      (M11)
  ```

  - **Re-attach (run completed)**: if `status` is already terminal at request time, replay all events + run-end + close. Returns 200, NOT 404.
  - **Auth**: 403 if user has no thread access. 404 only if run_id doesn't exist.

- **`POST /api/v1/threads/{thread_id}/runs/{run_id}/cancel`** → cooperative cancel via `cancel_run()`. Returns updated `ChatRun` row. Idempotent (cancelled twice → returns same row).

- **`POST /api/v1/threads/{thread_id}/runs/{run_id}/resume`** — only valid for `status='abandoned'`. Resumes from LATEST non-human-end checkpoint via `AsyncPostgresSaver.alist()` (mirrors `/regenerate:1264` pattern). H7 if checkpoint state is corrupted (empty list or only human messages), respond 409 — no inline fallback. Updates same `chat_runs` row to `status='running'`, increments `started_at` to now (track resume attempts).

### AC5 — Backward compat: `/regenerate` keeps working

**C7 — Byte-equivalent SSE wire format contract**: Existing FE consumers of `/regenerate` rely on the Vercel UI Stream protocol via `VercelStreamingService`. New `/runs/{rid}/stream` MUST emit the SAME envelope for all 13+ event types from 9-UX-1.

**Wire format parity rule**:
- Every event in `chat_run_events.payload` is the **already-formatted SSE data** (not raw payload). Stored as `{ "type": "data-orchestra-narration", "data": {...} }` JSONB.
- `/runs/{rid}/stream` emits `data: {payload}\n\n` directly — no transformation needed.
- `/regenerate` (legacy) internally:
  1. Calls `start_run(...)` → gets `run_id`
  2. Emits FIRST event `data: {"type": "run-meta", "data": {"runId": "..."}}` — new event for FE to know its run id (FE may ignore for backward compat)
  3. Pipes events from `/runs/{rid}/stream` logic identically (NOT via separate HTTP request — share the same generator function)
- **Regression test (T7-test)**: byte-equivalence assertion — record SSE bytes from old code path on a fixed query (mock LLM), compare against new code path on same query. ALL 13+ orchestra event types must serialize identically.

**Explicit non-changes** (FE assumption invariants):
- `data-orchestra-narration`, `data-orchestra-source-fetched`, `data-orchestra-fact-captured`, `data-orchestra-model-attribution`, `data-orchestra-rate-gate-wait`, `data-orchestra-llm-call`, `orchestra-spawn`, `orchestra-update`, `orchestra-done`, `orchestra-fail`, `orchestra-cancel`, `orchestra-complete`, `text-delta`, `tool-input-start`, `tool-input-available`, `tool-output-available`, `data-thinking-step`, `data-thread-title-update`, `data-token-usage`, `error`, `[DONE]` — all wire-identical.
- New events (`run-meta`, `run-end`, `replay-end`) are ADDITIVE — old FE will ignore unknown types via existing default-case in [page.tsx switch](nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx).

### AC6 — `_stream_writer_var` integration

[`chat_deepagent.py:_emit_orchestra_event`](nowing_backend/app/agents/new_chat/chat_deepagent.py) already routes via `_stream_writer_var.get()`. Modify only the writer signature: in detached task path, the writer wraps `RunEventWriter.write(event_type, data)` instead of appending to in-memory queue.

In-memory queue (`_orchestra_writer_queue`) in `stream_new_chat.py` becomes vestigial for `/regenerate` backward-compat path only; new `/runs` path skips it entirely.

### AC7 — Startup hook for orphan cleanup

[`app/app.py`](nowing_backend/app/app.py) lifespan adds:

```python
async with lifespan(app):
    # ... existing startup ...
    abandoned_count = await mark_abandoned_runs_on_startup()
    log.info("startup: marked %d orphaned runs as abandoned", abandoned_count)
    yield
    # ... existing shutdown ...
```

### AC8 — Multi-run/thread support (FE atom)

Update [`atoms/chat/orchestra.atom.ts`](nowing_web/atoms/chat/orchestra.atom.ts):

- `OrchestraState.sessions: Map<sessionId, OrchestraSession>` — already keyed correctly.
- Each spawn event carries `sessionId` from `chat_runs.session_id` → 2 concurrent runs produce 2 entries.
- **H8 — `activeQueryHash` rename**: existing `activeOrchestraSessionAtom` uses `state.activeQueryHash` (singular) which gets overwritten on every new spawn → run 2 starts → run 1's view disappears. Refactor:
  - Rename `activeQueryHash` → `lastSpawnedSessionId` (clarify intent)
  - Add new derived atom `activeRunSessionsAtom`: `(state) => Array.from(state.sessions.values()).filter(s => s.outcome === "running" || s.outcome === "abandoned").sort((a,b) => b.spawnedAt - a.spawnedAt)`
  - Audit all 4+ consumers of `activeOrchestraSessionAtom` (grep `activeOrchestraSessionAtom` in `nowing_web/`) — migrate each to either `lastSpawnedSessionAtom` (single, latest) or `activeRunSessionsAtom` (array) based on intent.
- **Multi-strip ordering rule (M9)**: `activeRunSessionsAtom` returns ordered by `spawnedAt DESC`. UI shows first 3, "+N more" collapse for the rest.

### AC9 — Multi-strip rendering

[`orchestra-strip.tsx`](nowing_web/components/new-chat/orchestra/orchestra-strip.tsx):

- Read `useAtomValue(activeRunSessionsAtom)` instead of single `activeOrchestraSessionAtom`
- Render one `<OrchestraStrip>` per session, vertically stacked, max 3 visible
- If >3, show "+N more" collapsible

### AC10 — FE auto-resume on mount

[`app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx`](nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx):

- On `useEffect(() => { ... }, [chat_id])`:
  1. `fetch /threads/{tid}/runs/active`
  2. For each active run: open SSE to `/runs/{rid}/stream`
  3. Pipe events through existing `applyOrchestraEvent` reducer
  4. Multiple SSE connections concurrently (one per active run)
- On unmount: abort all SSE connections (existing AbortController pattern)
- BE detached task continues regardless

### AC11 — Resume button for abandoned runs

When FE sees a run with `status='abandoned'`, render a "Resume" button in the orchestra strip header. Click → `POST /runs/{rid}/resume`.

**H7 — Checkpoint selection rule**: BE resume_run() walks `checkpointer.alist(config={"configurable": {"thread_id": run.langgraph_thread_id}})` newest-first, picks the first checkpoint where `last_message.type != "human"`. If no such checkpoint exists (run died before first agent step), respond 409 `{"error": "checkpoint_not_resumable"}` — FE shows "Cannot resume — please send a fresh query".

**C4 — Resume event dedup**: Resumed `agent.astream_events()` re-fires `on_chain_start` for already-completed sub-agent nodes. Without dedup, FE would see duplicate `orchestra-spawn` events. Mitigation:
- On resume, writer `RunEventWriter.run_flush_loop()` first reads `SELECT event_type, payload FROM chat_run_events WHERE run_id = $1` → builds `_seen_spawn_agents: set[str]` from existing `orchestra-spawn` events
- In flush loop, before INSERT, drop any `orchestra-spawn` whose `agentId` is in seen-set (idempotent at semantic level, not just `(run_id, seq)` UNIQUE level)
- Same dedup for `orchestra-source-fetched` (key by `agentId + source.domain`) and `orchestra-model-attribution` (key by `agentId`)
- Other event types (`orchestra-narration`, `text-delta`, etc.) are append-only — no dedup needed
- Emit synthetic `orchestra-resume` event with `last_seq_before_resume` so FE atom can transition lane state from `abandoned` → `running` smoothly without flicker.

**Status transition on Resume**: `abandoned` → `running`. UPDATE `chat_runs SET status='running', started_at=NOW(), error_message=NULL WHERE id=$1`.

### AC12 — Persistent retry preserved

The v3 retry-forever logic from 9-UX-1 (`SubAgentResilienceMiddleware`, synthesis retry, main orchestrator retry) MUST continue working unchanged. Detached task survival means the retry loops actually have time to converge during transient provider 429.

### AC13 — Event ordering guarantee

The `(run_id, seq)` UNIQUE constraint enforces ordering. `RunEventWriter` uses an in-process counter (`self._next_seq`) per run instance to avoid race with `MAX(seq)+1` SELECT. Concurrent writes within ONE run should not happen (single asyncio task per run), but defense-in-depth via UNIQUE.

---

## Tasks / Subtasks

### Backend

- [x] **T1** (BE) — Alembic migration `134_add_chat_runs.py` + `135_add_chat_run_heartbeat.py` (applied 2026-04-26): tables + indexes + downgrade. Idempotent pattern from migration 115. **Includes** `langgraph_thread_id`, `llm_config_id`, `model_id`, `mentioned_document_ids`, `disabled_tools`, `error_message VARCHAR(8000)`. **No UNIQUE on `session_id`**. (AC1, M12)
- [ ] **T2** (BE) — ORM models `ChatRun` + `ChatRunEvent` in `app/db.py`. UUID PK override. FK to `user.id` (singular). Relationships back-populated to `NewChatThread`. (H1)
- [ ] **T3** (BE) — `RunEventWriter` class in `app/services/run_event_writer.py`:
  - **Sync `write()`** → enqueue to bounded `asyncio.Queue(maxsize=10000)` (C5, M6)
  - **Async `run_flush_loop()`** seeds `_next_seq` from DB on startup (H2), drains 25ms or 50 events, INSERT then PUBLISH (C6)
  - On `text-delta` queue overflow: coalesce to latest per agentId (M6)
  - On resume: load existing event log, build `_seen_spawn_agents` for dedup (C4)
  - Graceful `stop()` awaits queue drain
- [ ] **T4** (BE) — `run_manager.py`:
  - `start_run` uses `asyncio.create_task` + `_active_runs: dict` + `add_done_callback` (NOT `anyio.CancelScope`) (C2)
  - `langgraph_thread_id = f"run-{uuid}"` for checkpoint isolation (C1)
  - `cancel_run` sets `_cancel_events[rid]` (cooperative) → 2s grace → `task.cancel()` (force)
  - `resume_run` selects checkpoint via `checkpointer.alist()` newest-first non-human-end (H7)
  - `mark_abandoned_runs_on_startup` wrapped in `try/except (UndefinedTable, ProgrammingError)` (M2), skipped when `UVICORN_RELOAD=true` (M5)
- [ ] **T5** (BE) — Refactor `stream_new_chat._stream_agent_events` to accept `RunEventWriter`. Add `_stream_session_id_var: ContextVar[str]` set by `start_run`; refactor 10+ session_id derivation sites (Architecture#7). Add `cancel_event.is_set()` check inside `SubAgentResilienceMiddleware` retry sleep loops (M4 cooperative cancel).
- [ ] **T6** (BE) — New endpoints in `new_chat_routes.py`:
  - `POST /runs` `start_run` dispatch (response <300ms server-side)
  - `GET /runs/active` filter `status IN ('running', 'abandoned')`
  - `GET /runs/{rid}/stream` SSE — **SUBSCRIBE→buffer→SELECT→drain** order (C3), emits `replay-end` sentinel (H5), terminal `run-end` event, all wrapped with byte-equivalent envelope to `/regenerate` (C7)
  - `POST /runs/{rid}/cancel` cooperative
  - `POST /runs/{rid}/resume` only valid `abandoned`
  - **All endpoints**: `Depends(current_active_user)` + `check_thread_access()` (H6)
  - Feature-flag `RESUMABLE_RUNS_ENABLED` gate on `start_run`/`active`, NOT on `/regenerate` (M3)
- [ ] **T7** (BE) — Modify `/regenerate` endpoint to internally call `start_run` + share generator function with `/runs/{rid}/stream` (NOT internal HTTP request). Emit `run-meta` first event with `runId`. (AC5, C7)
- [ ] **T8** (BE) — Lifespan startup hook in `app.py` calls `mark_abandoned_runs_on_startup()` after `setup_checkpointer_tables()`. Single-worker assertion or warn (M1).
- [ ] **T9** (BE) — Unit tests for `RunEventWriter`:
  - Idempotency on `(run_id, seq)` UNIQUE
  - `_next_seq` seeded from DB on resume (H2)
  - `text-delta` coalesce on queue overflow (M6)
  - PUBLISH happens AFTER successful INSERT/COMMIT (C6)
  - Graceful `stop()` drains queue
- [ ] **T10** (BE) — Integration test: spawn run → cancel mid-stream → verify `status='cancelled'`, final `orchestra-cancel` event written, in-flight retry loops aborted via cancel_event check.
- [ ] **T11** (BE) — Integration test: spawn run → simulate FE disconnect (close httpx context) → verify detached task continues + events accumulate in DB beyond disconnect timestamp.
- [ ] **T12** (BE) — Integration test: 2 concurrent runs same chat thread → distinct `langgraph_thread_id` (C1) → no checkpoint state cross-contamination → 2 distinct event streams.
- [ ] **T13** (BE) — Regression test for `/regenerate` parity (C7): record SSE bytes from old code on fixed mock-LLM query, compare against new path on same query, assert byte-equivalent for all 13+ orchestra events.
- [ ] **T14** (BE) — Integration test for resume dedup (C4): spawn run → mark abandoned manually → resume → verify NO duplicate `orchestra-spawn` events for completed sub-agents.

### Frontend

- [ ] **T15** (FE) — `lib/apis/chat-runs-api.service.ts` — typed client methods (matches `chat-threads-api.service.ts` plural-with-hyphen convention).
- [ ] **T16** (FE) — `atoms/chat/active-runs.atom.ts` + refactor `orchestra.atom.ts`:
  - Rename `activeQueryHash` → `lastSpawnedSessionId` (H8 clarity)
  - New `activeRunSessionsAtom` derived: filter running/abandoned, sort `spawnedAt DESC`
  - Audit + migrate 4+ consumers of `activeOrchestraSessionAtom`
  - Add reducer for new events: `run-meta`, `replay-end`, `run-end`, `orchestra-resume`
- [ ] **T17** (FE) — Modify `orchestra-strip.tsx` to render N strips from `activeRunSessionsAtom`, max 3 visible (M9), "+N more" collapse for 4+.
- [ ] **T18** (FE) — Modify `page.tsx` mount effect: `getActiveRuns(thread_id)` → attach SSE for each via `streamRun(rid)`. Update send-message flow: 2-step (`startRun` POST returns `runId` → open SSE to `/runs/{runId}/stream`). Discard duplicate atom updates when `_replay: true` events seen (H5).
- [ ] **T19** (FE) — Resume button UI in strip header when `outcome='abandoned'`. POST to `/runs/{rid}/resume`. Handle 409 `checkpoint_not_resumable` with toast.
- [ ] **T20** (FE) — Component unit tests: multi-strip rendering with 1/3/5 active runs, resume button triggers API + status transitions, `replay-end` sentinel suppresses fade animations during replay.
- [ ] **T21** (E2E) — Playwright: send query → refresh page mid-stream → verify orchestra strip restored within 1s, no duplicate spawn events visible, progress continues live.
- [ ] **T22** (E2E) — Playwright: send 2 concurrent queries on same thread → verify 2 strips render with distinct session_ids → cancel one → other continues.

### Cross-cutting

- [ ] **T23** — Feature flag `RESUMABLE_RUNS_ENABLED=true` in `.env.example`. Default `true`. Three enforcement points (M3): `start_run`, `/runs/active`, `mark_abandoned_runs_on_startup`. NOT enforced on `/regenerate`.
- [ ] **T24** — Update [architecture.md](_bmad-output/planning-artifacts/architecture.md) with new SSE contract + run lifecycle state machine diagram.
- [ ] **T25** — Document `chat_runs.status` state machine in ORM model docstring.
- [ ] **T26** — Single-worker constraint document: README + `.env.example` warn `UVICORN_WORKERS=1` required (M1).

---

## Dev Notes

### Existing patterns to reuse (DO NOT reinvent)

| Need | Existing util | Path |
|---|---|---|
| Cancel-safe DB session | `shielded_async_session()` | [`app/db.py:2333`](nowing_backend/app/db.py) |
| ContextVar writer | `_stream_writer_var` | [`chat_deepagent.py:443`](nowing_backend/app/agents/new_chat/chat_deepagent.py) |
| SSE format helpers | `VercelStreamingService` | [`new_streaming_service.py`](nowing_backend/app/services/new_streaming_service.py) |
| Redis client | Celery broker URL | [`celery_app.py:32`](nowing_backend/app/celery_app.py) `CELERY_BROKER_URL` |
| Async PG checkpointer | `get_checkpointer()` | [`app/agents/new_chat/checkpointer.py:90`](nowing_backend/app/agents/new_chat/checkpointer.py) |
| Stream event handler routing | `_stream_agent_events` | [`stream_new_chat.py:243`](nowing_backend/app/tasks/chat/stream_new_chat.py) |
| Orchestra reducer (sessionId-keyed) | `applyOrchestraEvent` | [`orchestra.atom.ts:170`](nowing_web/atoms/chat/orchestra.atom.ts) |
| AbortController + readSSEStream | `readSSEStream()` | [`streaming-state.ts:355`](nowing_web/lib/chat/streaming-state.ts) |
| Background task tracking pattern | `_background_tasks: set` + `add_done_callback` | [`new_chat_routes.py:62-102`](nowing_backend/app/routes/new_chat_routes.py) |

### LangGraph checkpointer notes

- **Already saves per-step automatically** via `AsyncPostgresSaver`. Tables created at app startup via `setup_checkpointer_tables()`.
- Resume from checkpoint: pass `config={"configurable": {"thread_id": str(chat_id), "checkpoint_id": ...}}` to `agent.astream_events()`.
- For abandoned-run resume: `checkpointer.alist(config)` returns checkpoint tuples ordered by ts; pick latest where last message is not HumanMessage (existing pattern in `/regenerate`).

### Redis pubsub gotcha

- Same Redis instance as Celery broker (`redis://localhost:6379/0`). Subscribe channel `nowing:run:{run_id}`.
- **Pubsub messages are not persistent** — DB is source of truth. SSE endpoint always replays from DB FIRST, then subscribes for live tail.
- For tail: keep pubsub subscription open until `chat_runs.status != 'running'` polled every 500ms.

### Migration patterns (from 115_add_page_purchases_table.py)

- Idempotent DDL: `IF NOT EXISTS` checks, `pg_type` lookups for enums
- Revision id: simple incrementing integer, e.g., `"118"`, `down_revision = "117"` (check current latest)
- Downgrade: `DROP INDEX IF EXISTS` + `DROP TABLE IF EXISTS`

### Multi-run UI density

- Cap visible strips at 3 (most users will have 1; multi-run is power-user feature)
- 4+ active runs: render first 3 + "+N more" expand button
- When run completes, strip transitions to `collapsed` variant per existing 9-UX-1 logic — naturally frees space

### Session ID derivation

For backward compat with existing 9-UX-1 code:
- Single-run case: `session_id = str(thread_id)` (current behavior)
- Multi-run: `session_id = f"{thread_id}-{run_id[:8]}"` (suffix when 2nd run starts)
- Frontend derives from event payload, no special handling

### Risks (from plan)

| Risk | Severity | Mitigation |
|---|---|---|
| DB write throughput (5000 INSERTs/min worst case) | 🟡 Medium | Batch INSERTs every 100ms in writer. PG handles 10k INSERTs/sec on commodity hw. |
| Migration on prod with in-flight chats | 🟡 Medium | Tables additive (no FK alterations). Deploy migration first, then code. Feature-flag `RESUMABLE_RUNS_ENABLED`. |
| `asyncio.create_task` lifecycle complexity | 🟡 Medium | Track in `_active_tasks: dict`. Test cancel race conditions. |
| Multi-run UI overflow | 🟢 Low | Cap visible at 3, "+N more" collapse. Defer if usage is rare. |
| Redis pubsub message loss during reconnect | 🟢 Low | DB is source of truth — pubsub is for live tail only. |

### Pre-flight gotchas (from v2 review — must read before coding)

- **M1 — single-uvicorn-worker constraint**: `_active_runs` dict is module-level. With `--workers N>1`, cancel that lands on a different worker is a no-op; orphan cleanup may mark sibling workers' healthy runs as abandoned. Document deployment must use `--workers 1` (or sticky session via Redis control channel — out of scope). Add `assert int(os.getenv("UVICORN_WORKERS", "1")) == 1` at startup or warn loudly.
- **M2 — migration ordering**: Container boots → lifespan startup runs `mark_abandoned_runs_on_startup()` → fails if migration hasn't applied. Mitigation: `try/except (UndefinedTable, ProgrammingError): log.warn(...); return 0`.
- **M3 — Feature flag enforcement points**: `RESUMABLE_RUNS_ENABLED` checked in 3 places ONLY:
  1. `start_run()` — if False, returns 503 (clients must use `/regenerate` legacy path)
  2. `/runs/active` GET — if False, returns empty array (FE never tries to attach)
  3. `mark_abandoned_runs_on_startup()` — skip silently if False
  - `/regenerate` is NEVER gated (always works to preserve compat).
- **M4 — Cancel mid-LLM-call quota cost**: Cancellation during in-flight LiteLLM HTTP call consumes provider tokens that don't refund. Document as known limitation. No reconciliation in this story.
- **M5 — uvicorn `--reload` (dev hot-reload) destructive**: Every file save triggers lifespan startup → marks ALL running runs as abandoned → FE auto-resume → ghost duplicate task burns tokens. Mitigation: skip orphan cleanup when `os.getenv("UVICORN_RELOAD") == "true"` or `DEBUG=true`.
- **M6 — Backpressure on text-delta bursts**: Token streaming bursts 50-200 deltas/sec/run × 10 runs = 2000/sec. Bounded queue `maxsize=10000` + coalescing rule (consecutive `text-delta` for same agentId → keep latest only — tokens are cumulative).
- **M7 — Browser SSE 6-connection limit**: Most browsers cap concurrent SSE per origin at 6. With 3+ active runs + main app traffic, FE may starve. Mitigation: deferred — typical usage <3 concurrent runs. Document.
- **M8 — `error_message` truncation**: LangChain stack traces can be 50KB+. `error_message VARCHAR(8000)` enforces truncation in app layer before INSERT (`(str(exc) or repr(exc))[:8000]`).
- **M9 — Multi-strip max 3 visible** ordered by `spawnedAt DESC`. "+N more" collapse for 4+. Power-user feature; defer overflow polish.
- **M11 — `run-end` SSE marker**: explicit FE-consumable terminal event with `{type: "run-end", status, completed_at}`. After this, SSE connection closes.
- **M12 — Migration revision id**: latest on disk is `119_add_vision_llm_id_to_search_spaces.py` → this story creates `120_add_chat_runs.py` with `down_revision="119"`.

### Out of scope

- **Distributed worker pool** (Celery for agent execution) — current asyncio.create_task in uvicorn process is sufficient until concurrent active runs > 50.
- **Heartbeat-based worker monitoring** — user chose "run forever". Worker restart marks runs as abandoned, FE-triggered resume.
- **Run history UI** — existing `new_chat_messages` already has assistant outputs.
- **Cross-device session sync** — design is per-user already; cross-device works because data is in DB. No UX changes.
- **Multi-uvicorn-worker support** — requires Redis control channel for cross-worker cancel; defer until traffic demands it.
- **Cancel-time quota reconciliation** — out of scope; provider tokens consumed during in-flight cancel are not refunded.

### Project Structure Notes

- BE: backend code in `nowing_backend/app/`. Migrations in `alembic/versions/` (incrementing revision id `116`+).
- FE: web code in `nowing_web/`. New service file follows `lib/apis/*-api.service.ts` pattern.
- New code follows Python type hints (`from __future__ import annotations` not needed — modern). FE uses TypeScript strict mode, named exports preferred over default.
- ORM model: prefer `BaseModel + TimestampMixin` from `app/db.py:530-550`. For UUID PK, override `id` column explicitly.
- Enum handling: use `StrEnum` (Python 3.11+); SQLAlchemy `Enum(MyEnum)` in column.
- Routes: `Depends(current_active_user)` + `Depends(get_async_session)`. Permission check via `check_permission(...)` and thread access via `check_thread_access(...)`.
- Streaming response headers: `Cache-Control: no-cache, X-Accel-Buffering: no`.
- DB session: commit + close BEFORE starting stream (avoid lock contention).

### References

- Plan source: [/Users/luisphan/.claude/plans/harmonic-cuddling-glacier.md](/Users/luisphan/.claude/plans/harmonic-cuddling-glacier.md)
- Previous story: [9-UX-1-live-research-lab.md](_bmad-output/planning-artifacts/stories/9-UX-1-live-research-lab.md) (Status: done — 37 patches across v1+v2 review rounds)
- 9-UX-1 production findings: SSE cancel + worker restart issues observed during live test 2026-04-25 11:25-13:10
- Architecture references:
  - SSE pattern: [`new_chat_routes.py:1062-1190`](nowing_backend/app/routes/new_chat_routes.py)
  - Background task tracking: [`new_chat_routes.py:62-102`](nowing_backend/app/routes/new_chat_routes.py)
  - LangGraph checkpointer: [`checkpointer.py:90`](nowing_backend/app/agents/new_chat/checkpointer.py)
  - Lifespan hook: [`app.py:86-101`](nowing_backend/app/app.py)
  - Migration template: [`alembic/versions/115_add_page_purchases_table.py`](nowing_backend/alembic/versions/115_add_page_purchases_table.py)
  - ORM patterns: [`db.py:530-650`](nowing_backend/app/db.py)
  - Existing `_stream_writer_var`: [`chat_deepagent.py:443`](nowing_backend/app/agents/new_chat/chat_deepagent.py)
  - `shielded_async_session`: [`db.py:2333`](nowing_backend/app/db.py)

---

## Definition of Done

- [ ] All 13 ACs verified
- [ ] All 26 tasks done (or DoD-deferred with rationale)
- [ ] Alembic migration applies cleanly on dev DB + downgrade reverts
- [ ] BE unit tests pass for `RunEventWriter` (idempotency, ordering, batch flush)
- [ ] BE integration tests pass (spawn → disconnect → resume; cancel; multi-run)
- [ ] FE component tests pass (multi-strip rendering, resume button)
- [ ] Playwright E2E passes: refresh-mid-stream + multi-run scenarios
- [ ] No regression in 9-UX-1 ACs (run existing tests + manual UNI query verification)
- [ ] Story 9-UX-1's `/regenerate` endpoint still works (backward compat)
- [ ] Performance budget: run start <300ms, replay 100 events <500ms, live event latency <50ms p95
- [ ] Feature flag `RESUMABLE_RUNS_ENABLED` defaults to `true` for new installs

---

## Verification Plan

### Manual (browser, primary path)
1. Submit "phân tích toàn diện UNI" → orchestra strip xuất hiện với 6 lanes
2. **Refresh trang giữa chừng (Cmd+R)** → strip biến mất 1s rồi xuất hiện lại với cùng progress (replay từ DB)
3. **Close tab hoàn toàn** → đợi 30s → mở lại → click chat tab → strip restored với progress đã advance
4. **Submit 2 queries song song** (UNI + BTC trong 2 message liền nhau) → 2 strips render
5. **Click cancel** → strip update outcome="cancelled", task ngừng emit events
6. **Restart BE process giữa chừng** → mở chat → run hiển thị "abandoned · Resume?" → click Resume → task mới spawn từ checkpoint, tiếp tục

### Automated
```bash
# BE migration check
cd nowing_backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head

# BE unit tests
.venv/bin/python -m pytest tests/unit/services/test_run_event_writer.py tests/unit/tasks/test_run_manager.py

# BE integration (uses Postgres + Redis)
.venv/bin/python -m pytest tests/integration/chat/test_resume_flow.py

# FE unit tests
cd nowing_web && npx vitest run __tests__/atoms/active-runs.test.ts __tests__/components/new-chat/multi-strip.test.tsx

# E2E (assumes BE+FE running)
npx playwright test playwright/e2e/resume-agent.spec.ts

# Regression: 9-UX-1 still passes
.venv/bin/python -m pytest tests/unit/agents/new_chat/test_source_attribution_middleware.py
npx vitest run __tests__/components/new-chat/orchestra-lab.test.tsx
```

### Performance verification
```bash
# Use Chrome DevTools Network panel
# 1. Start a run, observe POST /runs response time → should be <300ms
# 2. Refresh during run, observe GET /runs/{rid}/stream timing:
#    - First batch (replay) should arrive <500ms after request
#    - Live tail latency: events should arrive <50ms after BE INSERT
```

---

## Dev Agent Record

### Agent Model Used

(To be populated by dev agent)

### Debug Log References

(To be populated by dev agent)

### Completion Notes List

(To be populated by dev agent)

### File List

(To be populated by dev agent)

---

## Review Findings

### Adversarial Code Review (2026-04-25) — 3 layer parallel sweep

**Layers**: Blind Hunter (diff-only) · Edge Case Hunter (path tracing + project read) · Acceptance Auditor (spec compliance)

**Triage**: 0 decision-needed · 37 patch · 9 defer · 7 dismissed (noise)

#### ✅ Confirmed correctly implemented (Acceptance Auditor verified)

- AC1 chat_runs + chat_run_events tables, all required columns, idempotent migration
- C1 LangGraph thread isolation via `langgraph_thread_id = "run-{uuid}"` [run_manager.py:1086, stream_new_chat.py:1476]
- C2 cancel pattern via `_active_runs: dict` + `add_done_callback` (not anyio CancelScope) [run_manager.py:994, 1188]
- C5 sync `write()` + async `run_flush_loop()` split [run_event_writer.py:753, 760]
- C6 INSERT-before-PUBLISH ordering verified by `test_flush_batch_inserts_before_publish` [run_event_writer.py:917-943]
- C4 resume dedup via `_seen_spawn_agents` / `_seen_source_keys` / `_seen_attribution_agents` sets
- H2 `_next_seq` seeded from `COALESCE(MAX(seq),-1)+1` on flush-loop startup
- H6 thread-level auth (`check_thread_access`) on every `/runs/*` endpoint (⚠ run-level ownership still missing — see C7 below)
- H7 checkpoint selection rule (latest non-HumanMessage; 409 if none) [run_manager.py:1308-1328, 1255]
- M2 graceful try/except + M5 UVICORN_RELOAD skip in mark_abandoned_runs_on_startup
- M8 error_message truncation to 8000 chars
- T9 unit test idempotency / seq-restore-on-error coverage
- AC10 FE auto-resume on mount via getActiveRuns + streamRun
- T26 single-worker constraint documented in `.env.example`

#### Patches Applied (2026-04-25 batch-apply)

**Critical fixes applied:**
- [x] [Review][Patch] `start_new_run` removed manual `await session.close()` — let dependency teardown handle [new_chat_routes.py]
- [x] [Review][Patch] `cancel_run` dropped `asyncio.shield`; on timeout `task.cancel()` + suppress `CancelledError`. `_execute` finally now prefers `cancelled` status when `cancel_event.is_set()` [run_manager.py]
- [x] [Review][Patch] `_flush_batch` snapshots seen-sets before mutation; restores atomically with `_next_seq` on commit error [run_event_writer.py]
- [x] [Review][Patch] `RunEventWriter.stop()` bounded by 5s deadline so producer-during-shutdown can't deadlock the loop [run_event_writer.py]
- [x] [Review][Patch] Run-level ownership check (`run.created_by_id != user.id → 403`) added on `/cancel`, `/resume`, `/stream`; `/runs/active` filtered to caller's runs only [new_chat_routes.py]

**Critical — STILL OPEN (architectural, deferred to next iteration):**
- [ ] [Review][Patch] C7 SSE wire format violates Vercel envelope contract (BE emits `event:`+`data:` lines instead of bare `data:`; FE parses both — breaks byte-equivalence with `/regenerate`) [new_chat_routes.py; page.tsx]
- [ ] [Review][Patch] Detached writer stores `{"_raw": chunk}` instead of structured Vercel JSONB → breaks `_seed_seen_events` dedup + creates duplicate persistence path with `_stream_writer_var` middleware [stream_new_chat.py; run_event_writer.py]
- [ ] [Review][Patch] C3 SSE replay→subscribe ORDERING wrong (SELECT-first instead of SUBSCRIBE-first/buffer/SELECT/drain) — events INSERTed between phase-1 SELECT and phase-2 SUBSCRIBE may be lost [new_chat_routes.py]
- [ ] [Review][Patch] `RunEventWriter._coalesce_or_drop` mutates `asyncio.Queue._queue` (private deque) → race with flush coro mid-`get()` [run_event_writer.py]
- [ ] [Review][Patch] Dropped events on overflow silently lost without DB fallback — non-text events (orchestra-spawn etc.) coalesce-or-drop on queue full, breaking C6 invariant [run_event_writer.py]

#### 🟡 Major Patches Applied

- [x] [Review][Patch] `_extract_sse_event_type` rewritten: tries JSON parse first, then strict regex `^[0-9a-z]:"` for Vercel text-delta — non-Vercel `a:b` strings no longer misclassified [stream_new_chat.py]
- [x] [Review][Patch] `_mark_run_failed` now redacts: full error → server log only; DB stores generic "see server logs" sentinel [run_manager.py]
- [x] [Review][Patch] `_find_resumable_checkpoint` distinguishes infra failure (raises `CheckpointerUnavailableError` → 503) from clean miss (returns None → 409) [run_manager.py]
- [x] [Review][Patch] FE `useEffect` cleanup now calls `reader.cancel()` for each reader before `ac.abort()` [page.tsx]
- [x] [Review][Patch] FE tracks `lastSeqByRun` map; reconnects pass tracked `seq` not -1 [page.tsx]
- [x] [Review][Patch] `chat_run_events.payload` capped at 256KB in `RunEventWriter.write()` — oversized events dropped with warning [run_event_writer.py]
- [x] [Review][Patch] DB-only fallback `cancel_run` path now PUBLISHes `orchestra-cancel` to Redis after UPDATE — live SSE tail sees terminal [run_manager.py]
- [x] [Review][Patch] `pubsub.get_message` timeout caught with try/except → falls through to heartbeat instead of breaking inner while [new_chat_routes.py]
- [x] [Review][Patch] Client-disconnect detection via `await request.is_disconnected()` at top of pubsub loop [new_chat_routes.py]
- [x] [Review][Patch] `payload.get("_raw")` already guarded with `isinstance(payload, dict)` — confirmed at lines 1815, 1851, 1884; same guard added to `_seed_seen_events` / `_should_dedup` [run_event_writer.py, new_chat_routes.py]
- [x] [Review][Patch] SSE `run-replay-end` payload now built via `json.dumps({...})` — quote/newline injection impossible [new_chat_routes.py]
- [x] [Review][Patch] `gen.aclose()` wrapped in `asyncio.wait_for(timeout=2.0)` + `contextlib.suppress(Exception)` [stream_new_chat.py]
- [x] [Review][Patch] Per-chunk `await asyncio.sleep(0)` in detached consumer yields to flush_task [stream_new_chat.py]
- [x] [Review][Patch] `_active_runs[run_id] = task` registration uses `asyncio.ensure_future` and runs immediately after future creation; `_cleanup` callback stays as `add_done_callback` [run_manager.py]
- [x] [Review][Patch] FE `JSON.parse(dataLine)` wrapped in try/catch — malformed event no longer aborts stream [page.tsx]
- [x] [Review][Patch] FE skips SSE comment / heartbeat lines (`: text`) before regex-matching event/data [page.tsx]
- [x] [Review][Patch] V10 M1: `app.py` lifespan now logs WARN if `UVICORN_WORKERS != 1` and `RESUMABLE_RUNS_ENABLED=true` [app.py]
- [x] [Review][Patch] V11 M3: `/runs/active` returns `[]` when `RESUMABLE_RUNS_ENABLED=false` [new_chat_routes.py]

#### 🟡 Major — STILL OPEN (require dedicated follow-up)

- [ ] [Review][Patch] `mark_abandoned_runs_on_startup` blanket UPDATE has no worker fence — multi-replica deploy needs heartbeat timestamp before this is safe to enable [run_manager.py]
- [ ] [Review][Patch] `_seed_next_seq` + dedup not transactional with INSERT — two writers per run race; ON CONFLICT DO NOTHING swallows second's events silently. Needs per-run advisory lock or RETURNING-style sequence [run_event_writer.py]
- [ ] [Review][Patch] `langgraph_thread_id = "run-{uuid}"` UUID coercion compatibility — needs PostgresSaver verification test before production rollout [run_manager.py]
- [ ] [Review][Patch] Redis publish per-message failure has no retry — live-tail desyncs from DB silently. DB poll fallback documented but not implemented [run_event_writer.py]
- [ ] [Review][Patch] `stream_new_chat_detached` returns `None` but assigned to `final_message_id` → FK never set. Needs message-id capture from final SSE event [run_manager.py]
- [ ] [Review][Patch] V8 cooperative cancel inside `SubAgentResilienceMiddleware` retry sleep loops — Tier 3 paced retries (30s+) ignore cancel_event. Need to instrument middleware sites [chat_deepagent middleware]
- [ ] [Review][Patch] V9 Replay events lack `_replay: true` envelope marker — coupled with C7 Vercel envelope refactor; defer to same iteration [new_chat_routes.py + page.tsx]

#### 🚮 Re-classified during patch application

- ~~`streamRun` API timeout default~~ — DISMISSED: legitimate runs are 5-15+ min; hard timeout would break feature. BE-side `is_disconnected()` provides the leak protection.
- ~~Concurrent migration race (SELECT-then-CREATE)~~ — DISMISSED: alembic_version row-lock prevents concurrent upgrades; defensive pre-check is fine.

#### Deferred (large scope or low priority — track as follow-up)

- [x] [Review][Defer] V3 C7 `/regenerate` parity not implemented (large scope refactor; existing /regenerate works as backward-compat path; recommend 9-UX-1c follow-up)
- [x] [Review][Defer] V5 AC8/AC9/T16/T17 multi-strip rendering + `activeRunSessionsAtom` migration missing (large FE refactor; current single-strip works for single-run)
- [x] [Review][Defer] V6 AC11/T19 Resume button UI in orchestra strip header missing (current banner above Thread is functional substitute)
- [x] [Review][Defer] V7 T5 `_stream_session_id_var: ContextVar[str]` refactor (10+ derivation sites unchanged) — not blocking; current `langgraph_thread_id_override` route works for primary path
- [x] [Review][Defer] V12a T10/T11/T12 integration tests missing (cancel-mid-stream, detached-survives-disconnect, multi-run-isolation) — require Postgres+Redis fixtures
- [x] [Review][Defer] V12b T13 `/regenerate` byte-equivalence regression test missing (blocked by V3 deferral)
- [x] [Review][Defer] V12c T20 FE component unit tests for multi-strip + resume button missing (blocked by V5/V6 deferral)
- [x] [Review][Defer] V12d T21/T22 Playwright E2E for refresh-mid-stream and 2 concurrent queries missing (broader test scope)
- [x] [Review][Defer] Migration downgrade leaves dangling NewChatThread.chat_runs ORM relationship (downgrade rare; manual fixup acceptable)
- [x] [Review][Defer] AC7 startup hook ordering + count not logged at call site (function logs internally — cosmetic)

#### Dismissed (noise / handled / non-issue)

- `_run_to_response` ISO string vs datetime — Pydantic coerces correctly
- `_RESUMABLE_RUNS_ENABLED` module-level — intentional; only test concern
- Test asserts `>= 2` events — low-priority polish
- Magic constants `_FLUSH_BATCH_SIZE=50, _FLUSH_INTERVAL_MS=25` — internal tuning
- `result.rowcount` reliability — works correctly on asyncpg
- Test patches `app.tasks.chat.run_manager.asyncio.wait_for` — works via module attribute reference
- Migration revision number 134 vs spec's 120 — disk state advanced between drafting and dev

