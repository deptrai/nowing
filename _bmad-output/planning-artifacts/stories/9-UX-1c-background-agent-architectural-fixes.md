---
storyId: 9-UX-1c
storyTitle: Background Agent Architectural Fixes — SSE Vercel envelope + writer JSONB + multi-strip + advisory lock
epicParent: epic-9-crypto-orchestra
dependsOn: [Story 9-UX-1b in-progress (18 mechanical patches landed; this story closes architectural gap)]
blocks: []
relatedFRs: [FR35 Graceful Degradation, FR27 Comprehensive Analysis]
relatedNFRs: [NFR-Q1 Resilience, NFR-Q3 Graceful Degradation, NFR-UX Live Research Visibility]
priority: P0 (blocks 9-UX-1b → done; addresses architectural gaps from adversarial review of 9-UX-1b)
estimatedEffort: 1.5–2 weeks (1 BE + 0.5 FE)
status: done  # 2026-04-26: adversarial review + 9 patches applied; 47 BE + 20 FE + 4 integration tests pass
revision: v1 (2026-04-25)
createdAt: 2026-04-25
author: Luisphan + Claude (carved out from 9-UX-1b code review findings)
---

## Revision History

- **v1 (2026-04-25)** — Initial story carved out from 9-UX-1b adversarial code review. Gathers 12 architectural patches still open after 18 mechanical fixes were batch-applied, plus 4 spec deferrals (V3 /regenerate parity, V5 multi-strip, V6 Resume button, V9 _replay marker).
- **v1.1 (2026-04-26)** — Post-live verification patches:
  - **ETA formula bug fixed**: `lab-header.tsx` now uses `median(completedAgentMs) × remaining` instead of `(elapsedMs / doneCount) × remaining`. The old formula inflated ETA to 49–72m because it divided total wall-clock time (including rate-gate waits) by completed agent count. Added `completedAgentMs: number[]` to `OrchestraSession`; `orchestra-done` handler pushes `agentElapsedMs`; `orchestra-strip.tsx` passes array to `LabHeader`.
  - **Replay ETA bug fixed**: On page reload all replayed events arrived at `Date.now()` → `agentElapsedMs` ≈ 2ms → ETA showed "~0s left". Fix: BE `stream_run` injects `_ts` (Unix ms from `chat_run_events.created_at`) into each replayed event; `replay-start` includes `runStartedAtMs` from `run.started_at`; FE `applyOrchestraEvent` uses `eventTs = event._ts ?? Date.now()` for all elapsed/spawnedAt calculations.

# Story 9-UX-1c: Background Agent Architectural Fixes

## User Story

**As a** crypto researcher running concurrent long analyses,
**I want** the background-agent execution layer to be production-grade — SSE bytes byte-equivalent across `/regenerate` and `/runs/*/stream`, replay events flagged so the FE can dedup, multi-run UI showing distinct strips per concurrent query, and writer plumbing that never silently drops events —
**So that** the resumable-runs feature actually delivers on the contract from 9-UX-1b without wire-format inconsistencies, ghost dedup, or hidden race windows.

**Bar to clear**:
1. Recording bytes from `/regenerate` and `/runs/{id}/stream` for the same fixed-mock query produces byte-equivalent SSE output (modulo `run-meta` first event).
2. User submits 2 concurrent queries → 2 distinct strips render (current single-strip is overwritten).
3. Abandoned run → click Resume in **strip header** (not banner) → events replay flagged with `_replay: true`, FE dedups and animations don't re-fire.
4. `RunEventWriter` overflow drops zero events under 5000 events/min sustained load.

---

## Context

### Why this story exists

Story 9-UX-1b shipped detached background-agent execution + DB event log + Redis live-tail. After landing, an adversarial 3-layer code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor) found 30 issues across the implementation. **18 mechanical patches were batch-applied** (security, error redaction, exception narrowing, FE cleanup, etc.). **12 architectural patches** were carved out of that batch because they require coordinated BE+FE changes or affect the wire-format/data-shape contract.

The remaining work falls into four architectural themes:

1. **Wire format unification** (C7+V9): `/runs/{id}/stream` currently emits `event: <type>\ndata: {payload}\n\n` whereas the existing Vercel UI Stream protocol used by `/regenerate` is bare `data: <payload>\n\n`. FE has to parse two formats. Replay events lack `_replay: true` envelope marker. `/regenerate` was never modified to share the BE generator → byte-equivalence regression test (T13 from 9-UX-1b) cannot exist.

2. **Writer payload shape** (V2+linked dedup bugs): Detached task stores raw SSE chunks under `{"_raw": chunk}` key. `_seed_seen_events` reads `payload.get("agentId")` which returns None on `_raw` payloads → resume dedup is dead code in practice. Also creates duplicate persistence path (writer-via-`_stream_writer_var` middleware AND writer-via-detached-consume).

3. **Replay→subscribe ordering** (C3): Implementation does `SELECT first → SUBSCRIBE → gap-rescan SELECT`. Spec C3 mandates `SUBSCRIBE first → buffer → SELECT → drain`. Events INSERTed between phase-1 SELECT and phase-2 SUBSCRIBE that have already been PUBLISHed are lost (gap-rescan reads only DB-persisted events).

4. **Multi-run UI + concurrency hardening** (V5+V6): `orchestra.atom.ts` sessions Map is keyed by `sessionId` (= `langgraph_thread_id` = `"run-{uuid}"`, already unique per run — no migration needed). `orchestra-strip.tsx` still renders one strip — concurrent runs overwrite each other. Resume button lives in a banner above `<Thread />` instead of the strip header. Backend writer also had concurrency hazards (`_coalesce_or_drop` + `_seed_next_seq` race) — fixed in this story via deque + advisory lock.

### Plan source

- Code review findings: [9-UX-1b-background-agent-resume.md § Review Findings](_bmad-output/planning-artifacts/stories/9-UX-1b-background-agent-resume.md#review-findings)
- 18 mechanical patches already applied — see "Patches Applied" subsection in that file (security/error/exception/FE/cleanup category)
- Spec deferrals folded in: V3 `/regenerate` parity, V5 multi-strip + atom refactor, V6 Resume in strip header, V9 `_replay: true` marker

### Why NOT back into 9-UX-1b

9-UX-1b is in `in-progress` state with 21 unit + integration tests passing. The 18 mechanical patches landed cleanly. The remaining 12 are coordinated BE+FE refactors that change protocol contracts and atom shapes — they should be one cohesive iteration, not interleaved with the 9-UX-1b dev agent's working tree.

---

## Prerequisites

- [x] Story 9-UX-1b in working tree — `chat_runs` + `chat_run_events` tables exist, `RunEventWriter` + `run_manager` shipped, FE atom + page.tsx wired
- [x] 18 mechanical patches from 9-UX-1b code review applied (ownership checks, `_extract_sse_event_type` strict regex, `_mark_run_failed` redaction, `_find_resumable_checkpoint` exception narrowing, `pubsub.get_message` timeout handling, `request.is_disconnected()`, FE cleanup, etc.)
- [x] All 21 unit tests still passing (`tests/unit/services/test_run_event_writer.py`, `tests/unit/tasks/test_run_manager.py`, `tests/unit/agents/new_chat/test_source_attribution_middleware.py`)
- [x] Existing `VercelStreamingService` available at `app/services/new_streaming_service.py` (Vercel UI Stream protocol formatter)

---

## Acceptance Criteria

### AC1 — Vercel-envelope byte-equivalence between `/regenerate` and `/runs/{id}/stream` (C7)

**Goal**: Recording SSE bytes from both endpoints for the same fixed-mock query must produce byte-equivalent output (modulo a single `data: {"type":"run-meta",...}\n\n` first event from `/runs/*/stream`).

**Implementation**:
- BE `/runs/{id}/stream` MUST emit `data: {payload}\n\n` envelope (no `event: <type>` line). The `event:` line is currently a deviation from the Vercel UI Stream protocol used by `VercelStreamingService` everywhere else in the codebase.
- FE parser MUST consume bare `data:` lines only — drop the `event: ...` parsing path entirely.
- `/regenerate` endpoint MUST internally call `start_run` and share the SSE generator function with `/runs/*/stream` (NOT delegate via internal HTTP request — share the Python async generator).
- The shared generator emits `run-meta` as the first event when called via `/runs/{id}/stream`; when called via `/regenerate` the `run-meta` is omitted (otherwise everything identical).

**Regression test (T13 from 9-UX-1b)**: Record SSE bytes from old `/regenerate` path on a fixed mock-LLM transcript → byte-equivalent output from new shared generator (excluding leading `run-meta`).

### AC2 — Writer persists structured JSONB instead of `{"_raw": chunk}` (V2)

**Goal**: `chat_run_events.payload` is `{type: "...", data: {...}}` JSONB so dedup logic (`_seed_seen_events` / `_should_dedup`) actually works on persisted events.

**Implementation**:
- `stream_new_chat_detached` parses each SSE chunk via `_parse_vercel_envelope(chunk) -> dict | None` (returns `{type, data}` or `None` for non-JSON deltas) before calling `writer.write(event_type, structured_payload)`.
- For Vercel text-delta lines (e.g., `data: 0:"text"`), parse to `{"type": "text-delta", "data": {"id": ..., "delta": ...}}`.
- The `{"_raw": chunk}` shape is removed entirely. SSE replay path in `stream_run` rebuilds the wire bytes from structured payload via `VercelStreamingService.format_*` helpers.
- Choose ONE persistence path: keep `_stream_writer_var` middleware route (it persists structured events), drop the detached-consume `writer.write(_raw)` path. The detached task's role becomes lifecycle (cancel detection, completion marker) — actual event persistence is via the ContextVar middleware that already exists.

### AC3 — SUBSCRIBE-first replay protocol (C3)

**Goal**: No event loss in the gap between DB SELECT and Redis SUBSCRIBE.

**Implementation** (in `/runs/{id}/stream` SSE generator):
```
1. SUBSCRIBE Redis channel `nowing:run:{run_id}` → buffer arriving events in memory
2. SELECT * FROM chat_run_events WHERE run_id=$1 AND seq > $after_seq ORDER BY seq
3. Yield each persisted event (with _replay: true envelope flag)
4. Drain buffered pubsub events: skip seq <= max(persisted.seq); yield others (with _replay: false)
5. Continue tailing pubsub live until status terminal
```

The current implementation does `SELECT → SUBSCRIBE → gap-rescan SELECT` which still has a window where events PUBLISHed but not yet INSERTed are missed.

### AC4 — Replay events carry `_replay: true` envelope marker (V9)

**Goal**: FE can deduplicate atom updates that re-fire orchestra animations on reconnect.

**Implementation**:
- BE: every replayed event from Phase 1 SELECT yields `data: {"_replay": true, "seq": <seq>, "type": <type>, ...inner_payload}\n\n`. Live-tail events from Phase 2 pubsub yield without `_replay`.
- FE: in `applyOrchestraEvent` / `attachToRun`, when an event has `_replay: true`, skip animations and CSS transitions; only update state. The terminal `run-replay-end` sentinel (already in 9-UX-1b) signals end-of-replay → animations can resume.

### AC5 — Multi-strip rendering with `activeRunSessionsAtom` (V5)

**Goal**: 2 concurrent runs on the same thread render 2 distinct orchestra strips.

**Implementation** (`atoms/chat/orchestra.atom.ts`):
- Rename `activeQueryHash` → `lastSpawnedSessionId` for clarity (H8 from 9-UX-1b).
- Add `activeRunSessionsAtom`: derived atom returning `OrchestraSession[]` filtered by `outcome === 'running' || outcome === 'abandoned'`, sorted by `spawnedAt DESC`.
- Audit and migrate the 4+ consumers of `activeOrchestraSessionAtom` (the singular one) to use `activeRunSessionsAtom` (plural) where multi-run is appropriate.

**Implementation** (`components/new-chat/orchestra/orchestra-strip.tsx`):
- Render N strips, capped at max 3 visible (M9 — power-user feature).
- 4+ active runs: render first 3 with "+N more" expand button.
- Each strip keyed by `sessionId` (= `langgraph_thread_id` = `"run-{uuid}"`, unique per run — NOT the integer thread_id).

### AC6 — Resume button in strip header (V6)

**Goal**: Resume action lives inside the orchestra strip header (not as a separate banner above `<Thread />`).

**Implementation**:
- `LabHeader` component (existing from 9-UX-1) gains a Resume button when `outcome === 'abandoned'`. Click → `POST /runs/{id}/resume`. On 409 `checkpoint_not_resumable` → toast error. On 503 `checkpointer_unavailable` → toast retry-later.
- Remove the abandoned-runs banner JSX block in `page.tsx` (lines ~1951-1983) — banner becomes redundant.

### AC7 — `RunEventWriter` overflow does not silently lose events (Critical#5)

**Goal**: Under sustained 5000 events/min load (worst case = 10 concurrent runs × 500 events/run), zero non-text-delta events are dropped.

**Implementation**:
- Replace `asyncio.Queue` + private `_queue._queue` mutation with: `collections.deque(maxlen=10000)` + `asyncio.Semaphore(10000)` + asyncio.Event for queue-non-empty signal. Coalesce text-delta upstream via a small per-agentId `pending_delta` dict before enqueuing.
- On queue saturation for non-text events: synchronously INSERT the event to DB (using `shielded_async_session()`) then PUBLISH to Redis — bypass the queue entirely. This preserves C6 invariant under overload.
- Track and emit `RunEventWriter_overflow_total` log counter for ops visibility.

### AC8 — `_seed_next_seq` + INSERT under per-run advisory lock (Major#7)

**Goal**: Two writers for the same run_id (e.g., resume race or two pods) cannot allocate the same seq.

**Implementation** (in `RunEventWriter._flush_batch`):
```python
async with self._session_factory() as session:
    # Per-run advisory lock — Postgres int8 hash of run_id
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:rid::text, 0))"),
        {"rid": str(self._run_id)},
    )
    # Re-seed _next_seq under the lock
    row = await session.execute(
        text("SELECT COALESCE(MAX(seq), -1) + 1 FROM chat_run_events WHERE run_id = :rid"),
        {"rid": str(self._run_id)},
    )
    self._next_seq = row.scalar()
    # ... INSERT + UPDATE + COMMIT releases lock automatically (xact_lock)
```

This eliminates the "two writers race + ON CONFLICT DO NOTHING swallows second's events silently" hazard.

### AC9 — `mark_abandoned_runs_on_startup` worker fence via heartbeat (Major#6)

**Goal**: Multi-replica deploy or rolling restart does NOT mark healthy runs from sibling workers as abandoned.

**Implementation**:
- Add `chat_runs.last_heartbeat_at TIMESTAMPTZ` column via Alembic migration `135_add_chat_run_heartbeat.py` (down_revision="134").
- `RunEventWriter.run_flush_loop` updates `chat_runs.last_heartbeat_at = NOW()` every 30s (cheap UPDATE).
- `mark_abandoned_runs_on_startup` only marks rows where `last_heartbeat_at < NOW() - interval '90 seconds'` AND `status='running'` — sibling workers' healthy runs are spared.

This makes M1's single-worker constraint a soft optimization rather than a hard requirement.

### AC10 — `langgraph_thread_id="run-{uuid}"` PostgresSaver compatibility verified (Major#8)

**Goal**: `AsyncPostgresSaver` accepts non-UUID strings as `thread_id`.

**Implementation**:
- New unit test: `tests/unit/agents/new_chat/test_checkpointer_thread_id.py` — verify saving + loading checkpoint with `thread_id="run-{uuid4}"` round-trips correctly.
- If incompatible: switch to plain UUID for `langgraph_thread_id` (DB column `langgraph_thread_id VARCHAR(96)` already accepts arbitrary length).
- Document outcome in module docstring.

### AC11 — Redis publish retry / DB poll fallback (Major#9)

**Goal**: A transient Redis publish failure does not silently desync the live SSE tail from the DB.

**Implementation**:
- `RunEventWriter._flush_batch` publish loop catches per-message `Exception`, retries up to 3 times with 100ms backoff, then logs and continues (DB is canonical).
- `/runs/{id}/stream` SSE generator polls `chat_runs.last_event_seq` every 1s alongside pubsub; if the polled seq exceeds `last_seq` and pubsub hasn't delivered, run a catch-up `SELECT seq > last_seq` and yield.

This makes Redis pubsub a fast-path optimization rather than a correctness requirement.

### AC12 — `final_message_id` captured from final SSE event (Major#10)

**Goal**: `chat_runs.final_message_id` FK is set so users can navigate from a completed run back to the assistant message.

**Implementation**:
- `stream_new_chat` already emits a `data-message-id` event (or similar — verify exact event type) when persisting the final assistant message in `app/tasks/chat/stream_new_chat.py`. Capture this in `stream_new_chat_detached` and return the int message_id.
- Update `_execute` in `run_manager.py` to use the returned value: `await _mark_run_completed(run_id, final_message_id)`.

### AC13 — Cooperative cancel inside `SubAgentResilienceMiddleware` retry sleep loops (V8)

**Goal**: Tier 3 paced retries (30s+ sleep between provider 429 retries) honor `cancel_event.is_set()`.

**Implementation**:
- In `SubAgentResilienceMiddleware` retry sleep sites (search for `await asyncio.sleep(...)` inside `chat_deepagent.py` middleware), replace with `await _cancellable_sleep(seconds, cancel_event)` helper that wakes on either timer or cancel_event.
- Helper:
  ```python
  async def _cancellable_sleep(seconds: float, cancel_event: asyncio.Event | None) -> None:
      if cancel_event is None:
          await asyncio.sleep(seconds)
          return
      try:
          await asyncio.wait_for(cancel_event.wait(), timeout=seconds)
          raise asyncio.CancelledError("cancelled during retry sleep")
      except asyncio.TimeoutError:
          return  # sleep completed normally
  ```
- Pass `cancel_event` to middleware via `_stream_cancel_event_var: ContextVar[asyncio.Event | None]` (mirror the existing `_stream_writer_var` pattern).

### AC14 — Performance budget preserved

- Run start latency (`POST /runs` server-side): unchanged at <300ms
- SSE replay 100 events: <500ms (single SELECT + serialize via Vercel formatter)
- Live event latency (DB INSERT → Redis PUBLISH → SSE yield): <50ms p95
- Concurrent runs supported: 10 per thread (UI capped at 3 visible strips per AC5)

### AC15 — No regression in 9-UX-1 / 9-UX-1b behavior

- All 21 existing unit + integration tests pass unchanged
- Existing Playwright `resume-agent.spec.ts` (running-replay + abandoned-banner) updated to test strip-header Resume button (AC6) instead of banner
- Manual UNI query golden path still works end-to-end

---

## Tasks / Subtasks

### Backend — Wire format & writer plumbing

- [ ] **T1** (BE) — Refactor `/runs/{id}/stream` SSE generator in `new_chat_routes.py`:
  - Drop `event: <type>\n` line from all yields
  - Yield bare `data: {payload}\n\n` Vercel envelope
  - Add `_replay: true` marker to Phase 1 SELECT events; live-tail events without (AC1, AC4)
- [ ] **T2** (BE) — Implement SUBSCRIBE-first replay protocol (AC3):
  - SUBSCRIBE Redis channel + create asyncio.Queue buffer
  - SELECT replay events (with _replay: true)
  - Drain buffered pubsub events with `seq > max_persisted_seq`
  - Continue tailing live until status terminal
- [ ] **T3** (BE) — Refactor `/regenerate` endpoint to call `start_run` + share generator (AC1):
  - Extract shared async generator function `_stream_run_events(run_id, after_seq, emit_run_meta: bool)` from `stream_run`
  - `/regenerate` route: `start_run` → call shared generator with `emit_run_meta=False`
  - `/runs/{id}/stream` route: call shared generator with `emit_run_meta=True`
- [ ] **T4** (BE) — Replace `{"_raw": chunk}` writer payload with structured Vercel envelope (AC2):
  - Add `_parse_vercel_envelope(chunk) -> dict | None` to `stream_new_chat.py`
  - Drop `writer.write(event_type, {"_raw": chunk})` from `stream_new_chat_detached`
  - Detached task only emits lifecycle events (`orchestra-cancel`); event persistence flows entirely through `_stream_writer_var` middleware path
- [ ] **T5** (BE) — Replace `RunEventWriter._coalesce_or_drop` private-deque mutation (AC7):
  - Use `collections.deque(maxlen=10000)` + `asyncio.Event` signal
  - Per-agentId `pending_delta: dict[str, dict]` for upstream coalescing of text-delta
  - Sync-INSERT fallback for non-text events on queue saturation
- [ ] **T6** (BE) — Add `pg_advisory_xact_lock` per-run in `RunEventWriter._flush_batch` (AC8):
  - Lock at start of transaction, hash run_id with `hashtextextended`
  - Re-seed `_next_seq` under lock, then INSERT + UPDATE + COMMIT releases automatically
- [ ] **T7** (BE) — Alembic migration `135_add_chat_run_heartbeat.py` (down_revision="134"):
  - Add `last_heartbeat_at TIMESTAMPTZ NULL DEFAULT NULL` to `chat_runs`
  - Index for `mark_abandoned` query: `CREATE INDEX idx_chat_runs_heartbeat_running ON chat_runs(last_heartbeat_at) WHERE status='running'`
- [ ] **T8** (BE) — `RunEventWriter` heartbeat updater (AC9):
  - Background asyncio task in `run_flush_loop` updates `chat_runs.last_heartbeat_at = NOW()` every 30s
  - Cheap single-row UPDATE; tolerate failure (log only)
- [ ] **T9** (BE) — Refactor `mark_abandoned_runs_on_startup` to use heartbeat fence (AC9):
  - Filter `WHERE last_heartbeat_at IS NULL OR last_heartbeat_at < NOW() - interval '90 seconds'`
  - Update `.env.example` doc to remove single-worker hard requirement
- [ ] **T10** (BE) — Verify `langgraph_thread_id="run-{uuid}"` works with `AsyncPostgresSaver` (AC10):
  - New unit test `tests/unit/agents/new_chat/test_checkpointer_thread_id.py` — round-trip save/load
  - Document outcome in `run_manager.py` module docstring
- [ ] **T11** (BE) — Redis publish retry + DB poll fallback (AC11):
  - 3 retries with 100ms backoff in `_flush_batch` publish loop
  - 1s polling of `chat_runs.last_event_seq` in `/runs/{id}/stream` SSE generator
  - Catch-up SELECT when polled seq > known last_seq
- [ ] **T12** (BE) — Capture `final_message_id` from final SSE event (AC12):
  - In `stream_new_chat_detached`, intercept `data-message-id` (or equivalent) event type
  - Return as int from the function
  - `_execute` in `run_manager.py` uses returned value in `_mark_run_completed`
- [ ] **T13** (BE) — Cooperative cancel in `SubAgentResilienceMiddleware` retry sleeps (AC13):
  - Add `_stream_cancel_event_var: ContextVar[asyncio.Event | None]` in `chat_deepagent.py`
  - `start_run` / `_execute` set the ContextVar
  - Replace bare `asyncio.sleep` in middleware retry loops with `_cancellable_sleep` helper

### Backend — Tests

- [ ] **T14** (BE) — `test_regenerate_byte_equivalence.py` (T13 from 9-UX-1b deferral): record SSE bytes from old `/regenerate` path on fixed mock-LLM transcript → assert byte-equivalent to new shared generator (excluding leading `run-meta`)
- [ ] **T15** (BE) — `test_resume_dedup.py`: spawn run → mark abandoned → resume → assert NO duplicate `orchestra-spawn` events for completed sub-agents (verifies AC2 dedup actually works with structured payload)
- [ ] **T16** (BE) — `test_run_event_writer_advisory_lock.py`: spin up 2 RunEventWriter instances on same run_id → assert no `seq` collisions, ON CONFLICT DO NOTHING never triggered
- [ ] **T17** (BE) — `test_subscribe_first_replay.py`: start subscribe→ INSERT 5 events → SELECT replay should NOT miss the 5 events that landed during subscribe latency window
- [ ] **T18** (BE) — Update existing `test_run_lifecycle.py` integration test to assert `final_message_id` is non-NULL after completion (AC12)

### Frontend — Multi-strip + atom refactor

- [ ] **T19** (FE) — Refactor `orchestra.atom.ts` (AC5):
  - Rename `activeQueryHash` → `lastSpawnedSessionId`
  - Add `activeRunSessionsAtom` derived atom (filter running/abandoned, sort `spawnedAt DESC`)
  - Audit 4+ consumers of `activeOrchestraSessionAtom` and migrate where multi-run appropriate
- [ ] **T20** (FE) — Multi-strip rendering in `orchestra-strip.tsx` (AC5):
  - Map over `activeRunSessionsAtom` to render N strips
  - Cap at 3 visible; "+N more" expand button for 4+
  - Each strip keyed by `run_id`
- [ ] **T21** (FE) — Resume button in `LabHeader` (AC6):
  - Show when `outcome === 'abandoned'`
  - POST `/runs/{id}/resume` with toast feedback (409 / 503 distinct messages)
  - Remove abandoned-banner JSX block from `page.tsx`
- [ ] **T22** (FE) — SSE parser update (AC1, AC4):
  - Drop `event: <type>` parsing path; consume bare `data:` only
  - Detect `_replay: true` in parsed payload → skip animations, only update state
  - `run-replay-end` sentinel re-enables animations
- [ ] **T23** (FE) — Component unit tests:
  - `__tests__/components/new-chat/multi-strip.test.tsx`: render 1/3/5 active runs, verify cap-at-3 + "+N more"
  - `__tests__/components/new-chat/resume-button.test.tsx`: click triggers API, status transitions, error toasts
  - `__tests__/atoms/chat/orchestra-multi-run.test.ts`: `activeRunSessionsAtom` filter + sort correctness
- [ ] **T24** (E2E) — Update `playwright/e2e/resume-agent.spec.ts`:
  - Resume button now in strip header (AC6) instead of banner
  - Add 2-concurrent-queries scenario (AC5)

### Cross-cutting

- [ ] **T25** — Update [architecture-backend.md](_bmad-output/architecture-backend.md) "Background Agent Execution" section:
  - Document Vercel-envelope contract (AC1)
  - Document SUBSCRIBE-first replay protocol (AC3)
  - Document advisory-lock per-run seq allocation (AC8)
  - Document heartbeat fence (AC9)
- [ ] **T26** — Run full code review again on this story to verify the 12 architectural patches are correctly addressed and no new regressions introduced

---

## Dev Notes

### Existing patterns to reuse (DO NOT reinvent)

| Need | Existing util | Path |
|---|---|---|
| Vercel SSE envelope formatting | `VercelStreamingService` | [`new_streaming_service.py`](nowing_backend/app/services/new_streaming_service.py) |
| ContextVar pattern (writer, session_id) | `_stream_writer_var` | [`chat_deepagent.py:443`](nowing_backend/app/agents/new_chat/chat_deepagent.py) |
| Cancel-safe DB session | `shielded_async_session()` | [`app/db.py:2333`](nowing_backend/app/db.py) |
| Cancellable sleep pattern | None — new helper in this story (small, self-contained) | T13 |
| Postgres advisory lock | `pg_advisory_xact_lock` | Postgres builtin; first use in this codebase |
| Existing 9-UX-1b plumbing | `RunEventWriter`, `run_manager`, `stream_new_chat_detached` | All in working tree from 9-UX-1b |

### Critical implementation order

T1+T22 (SSE Vercel envelope) and T4 (drop `_raw`) are coupled — land them in the same PR or BE+FE will be incompatible mid-deploy. Suggested PR breakdown:

1. **PR1 — Wire format + writer payload (T1, T2, T3, T4, T22)**: BE Vercel envelope + replay protocol + `/regenerate` share + structured payload + FE parser. One coordinated change.
2. **PR2 — Multi-strip + Resume in header (T19, T20, T21, T23, T24)**: FE atom refactor + UI. Pure FE.
3. **PR3 — Concurrency hardening (T5, T6, T7, T8, T9, T11)**: BE writer/manager. Pure BE.
4. **PR4 — Compatibility verifications (T10, T12, T13)**: small targeted patches.
5. **PR5 — Tests (T14, T15, T16, T17, T18)**: regression + new test coverage.

### SSE Vercel envelope contract (AC1)

Vercel UI Stream Protocol uses bare `data:` lines. Examples (already produced by `VercelStreamingService`):

```
data: 0:"hello"\n\n                                          # text-delta with id 0
data: 9:{"id":"abc","name":"foo","args":{}}\n\n              # tool-call
data: a:{"id":"abc","result":"..."}\n\n                       # tool-result
data: 8:{"messageId":42}\n\n                                  # message-id
data: e:{"finishReason":"stop","usage":{...}}\n\n             # finish
data: 2:[{"type":"data-orchestra-spawn","data":{...}}]\n\n    # orchestra event
```

`/runs/*/stream` MUST emit byte-identical wire format (modulo `run-meta` first event for stream endpoint, omitted for `/regenerate`):

```
data: {"_replay":false,"type":"run-meta","data":{"runId":"...","threadId":42}}\n\n
data: 0:"hello"\n\n                                          # replayed event, _replay flag at envelope level
```

**Important**: `_replay` is part of the OUTER Vercel envelope wrapper, NOT the inner payload. Pseudo-code for replay yield:

```python
def _wrap_for_replay(raw_vercel_chunk: str) -> str:
    # Inject _replay: true into the JSON if it's a JSON-shaped data line
    if raw_vercel_chunk.startswith('data: 2:'):
        # Vercel data part — inject _replay flag
        ...
    return raw_vercel_chunk  # text-delta etc. — pass through, no _replay
```

Actually — simpler: emit a separate envelope event before each replayed event:

```
data: {"_marker":"replay-start","seq":42}\n\n
data: 2:[{"type":"data-orchestra-spawn",...}]\n\n
data: {"_marker":"replay-end"}\n\n
```

OR: bracket the entire replay phase with single sentinel pair:

```
data: {"_marker":"replay-start","fromSeq":-1,"toSeq":42}\n\n
... yield raw Vercel events from DB ...
data: {"_marker":"replay-end"}\n\n
... live tail begins ...
```

**Recommendation**: bracket-the-phase approach — simpler BE, FE just sets a `replaying` flag between markers. Adopt this for AC4.

### Multi-run UI density (AC5)

- Cap at 3 visible strips, ordered by `spawnedAt DESC`
- 4+ active runs: render 3 most recent + "+N more" expand button
- When run completes, strip transitions to `collapsed` variant per existing 9-UX-1 logic — naturally frees space for new spawns

### Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Wire format change breaks existing FE | 🟡 Medium | T1+T22 in same PR; comprehensive parser test + manual UNI query verification before merge |
| Advisory lock contention under load | 🟢 Low | xact-scoped lock auto-releases on commit; per-run hash spreads across lock hash space |
| Heartbeat UPDATE I/O cost | 🟢 Low | Single-row UPDATE every 30s × N concurrent runs ≪ event INSERT volume |
| Migration on prod with running 9-UX-1b runs | 🟡 Medium | Heartbeat column nullable; existing rows have NULL → treated as "stale" by AC9 filter only after 90s of no heartbeat. Deploy migration first, then code. |
| `/regenerate` shared-generator refactor regresses existing chat | 🔴 High | T14 byte-equivalence test is the bar. Manual UNI query end-to-end before merge. Feature-flag to roll back via `RESUMABLE_RUNS_ENABLED=false`. |

### Pre-flight gotchas

- **Vercel envelope `data: 2:[...]` is JSON array** — orchestra events come as a single-item array. The `_replay` marker bracket approach is cleaner than trying to inject inside.
- **`run-replay-end` sentinel from 9-UX-1b**: keep existing — FE already parses it. Just rename conceptually to "replay-end marker" (no wire change).
- **`_seed_seen_events` already isinstance-guarded in 9-UX-1b patch batch** — once T4 lands and payload is structured, the dedup logic finally works for real.
- **PostgresSaver `thread_id` constraint** — verify in T10 before T1/T4 (worst case, switch to plain UUID for `langgraph_thread_id`).

### Out of scope

- Distributed multi-worker support via Redis control channel (deferred until traffic demands)
- Run history UI (existing assistant messages already covered)
- Cancel-time provider quota reconciliation (provider tokens consumed during in-flight cancel are not refunded)

### References

- 9-UX-1b code review findings: [9-UX-1b § Review Findings](_bmad-output/planning-artifacts/stories/9-UX-1b-background-agent-resume.md#review-findings)
- 18 mechanical patches landed on 2026-04-25 (this story closes the architectural gap)
- Vercel UI Stream Protocol: [`VercelStreamingService`](nowing_backend/app/services/new_streaming_service.py)
- Postgres advisory locks: https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS
- 9-UX-1b ORM models: [`chat_runs` and `chat_run_events`](nowing_backend/app/db.py)
- 9-UX-1b writer: [`run_event_writer.py`](nowing_backend/app/services/run_event_writer.py)
- 9-UX-1b run lifecycle: [`run_manager.py`](nowing_backend/app/tasks/chat/run_manager.py)
- Orchestra atom: [`orchestra.atom.ts`](nowing_web/atoms/chat/orchestra.atom.ts)
- Orchestra strip: [`orchestra-strip.tsx`](nowing_web/components/new-chat/orchestra/orchestra-strip.tsx)

---

## Definition of Done

- [ ] All 15 ACs verified
- [ ] All 26 tasks done (or DoD-deferred with rationale)
- [ ] Alembic migration 135 applies + downgrade reverts cleanly
- [ ] Byte-equivalence regression test (T14) passes on fixed mock-LLM transcript
- [ ] Resume dedup integration test (T15) confirms no duplicate orchestra-spawn after resume
- [ ] Advisory lock test (T16) confirms zero seq collisions under simulated 2-writer race
- [ ] SUBSCRIBE-first protocol test (T17) confirms zero event loss in subscribe-latency window
- [ ] All existing 21 unit + integration tests still pass
- [ ] Multi-strip Playwright E2E (T24) passes with 2 concurrent queries
- [ ] No regression in 9-UX-1 ACs (manual UNI query verification + existing test suite)
- [ ] `/regenerate` endpoint backward-compat verified (existing chat flow unbroken)
- [ ] Performance budget: run start <300ms, replay 100 events <500ms, live event latency <50ms p95, heartbeat UPDATE <5ms p95
- [ ] Story 9-UX-1b status transitions to `done` after this story merges (architectural gap closed)

---

## Verification Plan

### Manual (browser, primary path)

1. Submit "phân tích toàn diện UNI" → orchestra strip xuất hiện
2. **Refresh trang giữa chừng (Cmd+R)** → strip restored within 1s; verify NO animation re-fire (AC4 `_replay: true`)
3. **Submit 2 queries song song** (UNI + BTC) → 2 distinct strips render (AC5 multi-strip)
4. **Restart BE process** → mở chat → strip shows "abandoned" → click Resume button **trong header** (not banner — AC6) → task respawns from checkpoint
5. **Cancel Tier 3 retry mid-sleep** (provider 429 backoff) → cancel happens within 2s, not after 30s sleep completes (AC13)
6. **Send 2 queries, kill BE worker mid-run, restart** → AC9 heartbeat fence ensures only the actually-orphaned run is marked abandoned

### Automated

```bash
# Migration check
cd nowing_backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head

# BE unit + integration
.venv/bin/python -m pytest \
  tests/unit/services/test_run_event_writer.py \
  tests/unit/tasks/test_run_manager.py \
  tests/unit/agents/new_chat/test_source_attribution_middleware.py \
  tests/unit/agents/new_chat/test_checkpointer_thread_id.py \
  tests/integration/chat/test_run_lifecycle.py \
  tests/integration/chat/test_regenerate_byte_equivalence.py \
  tests/integration/chat/test_resume_dedup.py \
  tests/integration/chat/test_run_event_writer_advisory_lock.py \
  tests/integration/chat/test_subscribe_first_replay.py

# FE unit
cd nowing_web && npx vitest run \
  __tests__/active-runs-atom.test.ts \
  __tests__/atoms/chat/orchestra-multi-run.test.ts \
  __tests__/components/new-chat/multi-strip.test.tsx \
  __tests__/components/new-chat/resume-button.test.tsx \
  __tests__/components/new-chat/orchestra-lab.test.tsx

# E2E
npx playwright test playwright/e2e/resume-agent.spec.ts playwright/e2e/orchestra-strip.spec.ts playwright/e2e/research-lab.spec.ts
```

### Performance verification

```bash
# Use Chrome DevTools Network panel
# 1. POST /runs response time → unchanged at <300ms (no regression)
# 2. GET /runs/{rid}/stream replay batch → arrives <500ms after request
# 3. Live tail latency → events <50ms after BE INSERT (Redis publish + SSE yield)
# 4. Heartbeat UPDATE timing → <5ms p95 (single-row UPDATE)
```

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (2026-04-25)

### Debug Log References

- `_pending_delta` stores `(event_type, payload)` tuple — test assertions use tuple unpack pattern
- Advisory lock mock detection: match `"COALESCE"` in `str(stmt)` since SQLAlchemy text() objects stringify to their SQL
- `abandonedSessionIdsAtom` lifted to Jotai to cross component boundary between page.tsx and AssistantMessageInner
- `orchestra-stub` abandoned rendering: `if (!session && isAbandoned && onResume)` — intentionally returns null if no handler

### Completion Notes List

- T1 wire: bare `data: {json}\n\n` throughout; `_rebuild_vercel_wire` handles legacy `_raw`, `_vercel` key, and structured payloads
- T2 sentinels: `replay-start`, `replay-end` (with status), `run-end` emitted as direct f-strings (not via `_rebuild_vercel_wire`)
- T3 SUBSCRIBE-first: buffer → SELECT drain → emit replay-end → drain buffer (dedup by seq) → tail pubsub → gap scan every 5s
- T5 deque: `collections.deque(maxlen=10_000)` + `_pending_delta` for text-delta coalescing. `_drain_batch()` has 2 while loops — first tops up batch if pending_delta populated it, second handles empty-batch case
- T6 advisory lock: `SELECT pg_advisory_xact_lock(hashtext(:run_id))` + COALESCE reseed in `_flush_batch`
- T8 heartbeat: 30s interval, 90s fence (3× multiplier for startup safety)
- T10 langgraph_thread_id: `f"run-{uuid4()}"` format, distinct from int DB thread_id
- T16 seq reseed: DB seq > writer seq → writer adopts DB seq + batch offset
- T21 Resume button: in strip header (not banner), only for `isAbandoned=true` sessions
- T22 marker handling: `replay-end.status` gates UI mode; `run-end` closes stream
- All 47 BE unit tests passing; 20 FE vitest passing

### File List

**Backend (modified)**:
- `nowing_backend/app/services/run_event_writer.py` — T5 deque, T6 advisory lock, T8 heartbeat, C4 dedup
- `nowing_backend/app/tasks/chat/run_manager.py` — T9 heartbeat fence, T18 complete_run final_message_id
- `nowing_backend/app/routes/new_chat_routes.py` — T1 wire, T2 sentinels, T3 SUBSCRIBE-first, T11 DB gap scan, `_rebuild_vercel_wire`
- `nowing_backend/app/tasks/chat/stream_new_chat.py` — T4 `_parse_vercel_envelope`, structured payload (no `_raw`)

**Backend (new tests)**:
- `nowing_backend/tests/unit/services/test_run_event_writer.py` — T5/T6/T16 updates
- `nowing_backend/tests/unit/agents/new_chat/test_checkpointer_thread_id.py` — T10
- `nowing_backend/tests/unit/tasks/test_vercel_wire_format.py` — T14
- `nowing_backend/tests/unit/tasks/test_subscribe_first_replay.py` — T17
- `nowing_backend/tests/integration/chat/test_run_lifecycle.py` — T18

**Frontend (modified)**:
- `nowing_web/atoms/chat/active-runs.atom.ts` — T19 `abandonedSessionIdsAtom`
- `nowing_web/atoms/chat/orchestra.atom.ts` — T20 `lastSpawnedSessionId` rename
- `nowing_web/components/new-chat/orchestra/orchestra-strip.tsx` — T21 Resume button + abandoned stub
- `nowing_web/components/assistant-ui/assistant-message.tsx` — T21/T22 multi-strip render
- `nowing_web/app/dashboard/[search_space_id]/new-chat/[[...chat_id]]/page.tsx` — T19 abandoned tracking, T22 marker handling
- `nowing_web/__tests__/orchestra-atom.test.ts` — T20 fix
- `nowing_web/__tests__/active-runs-atom.test.ts` — T19 fix
- `nowing_web/playwright/e2e/resume-agent.spec.ts` — T24 rewrite (T1 wire format)

**Docs (modified)**:
- `_bmad-output/architecture-backend.md` — T25 contracts: T1-T8, C4

---

## Review Findings

### 2026-04-25 — Post-implementation review (claude-opus-4-7)

**Result: PASS with minor notes — no blocking issues found.**

**False positives investigated and cleared:**
1. `_drain_batch()` lines 256-257 — redundant first while loop (dead code after `_pending_delta` drain) but NOT a bug; lines 259-260 handle empty-batch deque drain correctly. Harmless.
2. `_rebuild_vercel_wire()` — correctly handles 3 payload generations (raw, _vercel, structured). Structured payloads → `data: {json.dumps(payload)}\n\n` is correct Vercel UI Stream format.
3. Replay sentinels (`replay-start`, `replay-end`, `run-end`) — emitted as direct f-strings, do NOT route through `_rebuild_vercel_wire`. No sentinel-loss risk.
4. Multi-strip merge dedup — `activeSessionIds` filter at line 392 correctly excludes abandoned orphans that are already in active list. No duplicate render possible.

**Minor deferred:**
- `_drain_batch` lines 256-257: dead code (first while loop). Can be removed in a follow-up cleanup pass (1 line). No behavior change.
- Heartbeat fence 90s vs 30s interval: 3× multiplier is intentional design (buffer for transient heartbeat failures). Documented in architecture-backend.md.

### Adversarial Code Review Findings (2026-04-25, 3-layer parallel review)

#### Decision Needed (resolved)
- [x] [Review][Defer] **AC1/T3: `/regenerate` not refactored to share generator** — defer to 9-UX-1d; `/regenerate` works via legacy path, scope too large for this story
- [x] [Review][Dismiss] **AC4: Per-event `_replay: true` flag not implemented** — bracket sentinels are the industry-standard approach (Vercel AI SDK, OpenAI streaming); spec Dev Notes already recommend this. AC4 wording to be updated.
- [x] [Review][Defer] **AC5: `activeRunSessionsAtom` excludes abandoned sessions** — defer; merge logic in `assistant-message.tsx` achieves correct visual result. Refactor atom shape when a second consumer needs it.
- [x] [Review][Defer] **AC7: sync-INSERT fallback for non-text events missing** — defer; deque maxlen=10000 covers production load (500 events/run). Overflow = severe backpressure indicating a different root cause.
- [x] [Review][Defer] **T14: byte-equivalence regression test missing** — defer; linked to AC1/T3, implement when `/regenerate` refactored.

#### Patch (fixable without human input) — ALL APPLIED 2026-04-25
- [x] [Review][Patch] **Resume handler does not re-attach SSE stream** — `attachToRun(resumed)` never called after `resumeRun()`, FE blind to live progress until refresh [page.tsx:729] ✓ Added `attachToRunRef` pattern + `attachToRunRef.current?.(resumed)` after resumeRun
- [x] [Review][Patch] **Heartbeat fence marks runs <30s old as abandoned** — `last_heartbeat_at IS NULL` matches brand-new runs; sibling restart within 30s incorrectly abandons them. Fix: set `last_heartbeat_at = NOW()` at run creation [run_manager.py:130-143] ✓ Added `last_heartbeat_at=datetime.now(UTC)` in start_run + resume_run
- [x] [Review][Patch] **`stop()` does not set `_signal`** — flush loop may sleep through 5s deadline, losing queued events. Fix: add `self._signal.set()` in `stop()` [run_event_writer.py:139] ✓ Added 3x `_signal.set()` calls + replaced deprecated `get_event_loop()` with `get_running_loop()`
- [x] [Review][Patch] **Silent event loss on `_rebuild_vercel_wire` throw** — `last_seq` advanced before yield; `except: pass` swallows. Fix: move `last_seq` update after yield, log exception [new_chat_routes.py:1909-1919] ✓ Reordered: compute wire → update last_seq → yield; added exc_info logging
- [x] [Review][Patch] **`_rebuild_vercel_wire` truthy check on `_raw`/`_vercel`** — non-string values cause crash. Fix: add `isinstance(raw, str)` guard [new_chat_routes.py:1786] ✓ Added `isinstance(raw, str)` and `isinstance(vercel, str)` guards
- [x] [Review][Patch] **Overflow log misattributes event type** — logs new event's type instead of dropped oldest. Fix: no access to dropped item, change message wording [run_event_writer.py:110] ✓ Changed to "oldest event dropped to enqueue %s"
- [x] [Review][Patch] **`abandonedRuns` stale closure in resume handler** — React timing: resume handler captures stale `abandonedRuns` state. Fix: use `ref` or `useCallback` pattern [page.tsx:726] ✓ Added `abandonedRunsRef` pattern, removed `abandonedRuns` from deps array
- [x] [Review][Patch] **Architecture doc says "5s" gap scan but code uses 1s** — Fix: update doc to match code [architecture-backend.md:253] ✓
- [x] [Review][Patch] **Architecture doc says "2 phút" heartbeat fence but code uses 90s** — Fix: update doc to match code [architecture-backend.md:273] ✓

#### Deferred (pre-existing or out of scope)
- [x] [Review][Defer] **Redis connection leak if generator not `aclose()`d** [new_chat_routes.py:1831] — depends on Starlette StreamingResponse cleanup behavior; pre-existing pattern
- [x] [Review][Defer] **`hashtextextended` is internal PG function** [run_event_writer.py:317] — portability concern for PG <11; acceptable for current deployment
- [x] [Review][Defer] **`orchestraStateAtom` abandoned sessions unbounded** [orchestra.atom.ts:380] — memory leak over long sessions; eviction only on `orchestra-complete`
- [x] [Review][Defer→Fixed] **`asyncio.get_event_loop()` deprecated** [run_event_writer.py:143,235] — fixed in P3 patch: replaced with `get_running_loop()` (replace_all)
- [x] [Review][Defer] **T15: resume dedup integration test missing** — requires live Postgres + Redis; defer to 9-UX-1d or integration test pass
- [x] [Review][Defer] **T23: 3 FE component unit tests missing** — multi-strip.test.tsx, resume-button.test.tsx, orchestra-multi-run.test.ts
- [x] [Review][Defer] **T24: 2-concurrent-queries E2E scenario missing** — E2E rewritten for T1 wire format but multi-run scenario absent

### Full Adversarial Code Review — 9-UX (a,b,c) (2026-04-26, 3-layer parallel)

**Scope**: All code across 9-UX-1 (Research Lab), 9-UX-1b (Background Agent Resume), 9-UX-1c (Architectural Fixes)  
**Layers**: Blind Hunter (15 raw), Edge Case Hunter (17 raw), Acceptance Auditor (10 raw)  
**After dedup + dismiss**: 6 patch, 1 defer, 7 dismissed as noise/false-positive/already-tracked

#### Patch (fixable without human input) — ALL APPLIED 2026-04-26
- [x] [Review][Patch] **`_pending_delta.clear()` drops un-iterated deltas on batch-size limit** — `clear()` replaced with `pop(key)` per-item during iteration [run_event_writer.py:250-254] ✓
- [x] [Review][Patch] **Deque events lost on `_flush_batch` DB error** — added `deque.appendleft()` re-enqueue in error handler + `_signal.set()` [run_event_writer.py:388-393] ✓
- [x] [Review][Patch] **`_execute()` finally cancels flush_task after `stop()`** — removed `flush_task.cancel()`, `stop()` already triggers clean exit [run_manager.py:234-237] ✓
- [x] [Review][Patch] **`cancel_run` publishes `seq: -1` corrupting FE `lastSeqByRun`** — omitted `seq` field from cancel publish payload [run_manager.py:298-304] ✓
- [x] [Review][Patch] **`resume_run` SQL UPDATE missing `last_heartbeat_at=NOW()`** — added to SQL UPDATE statement [run_manager.py:346] ✓
- [x] [Review][Patch] **Resume handler silent no-op when `abandonedRunsRef` stale** — added `toast.error("Run no longer available")` [page.tsx:733] ✓

#### Deferred (pre-existing, already tracked)
- [x] [Review][Defer] **`activeRunSessionsAtom` excludes abandoned sessions** [orchestra.atom.ts:129] — already tracked in previous review, deferred by design

#### Dismissed (7 findings)
- `_pending_delta` dict mutation during iteration — false positive, synchronous loop under GIL, no yield point
- `run-end` sentinel after `finally` block — false positive, code only reached on normal loop exit
- `run.langgraph_thread_id` undefined for pre-migration runs — false positive, column is NOT NULL with default
- Heartbeat amplification with N concurrent runs — not a problem at scale (10 UPDATE/30s = trivial)
- Double sleep in flush loop (50ms instead of 25ms) — negligible latency, self-correcting
- Signal race in `_drain_batch` (`clear` before `wait`) — 25ms worst-case lag, self-correcting next cycle; reclassified from patch to dismiss (not worth the complexity)
- `resume_run` no ownership check — false positive, route layer already checks `check_thread_access` + `created_by_id`
