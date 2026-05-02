# Story 11.7: Resilience & Performance Hardening Round 2

Status: backlog
Priority: **P1 — within 2 weeks of production launch**
Source: Sprint Change Proposal 2026-05-02 (round-2 review IMPORTANT items from stories 11-1, 11-3, 11-4)

## Story

As a system operator,
I want round-2-review resilience gaps (token-waste, heartbeat-cancel safety, slow-table DELETE, scoping clarification) addressed within 2 weeks of launch,
So that production stability degrades gracefully under sustained load and edge cases.

## Acceptance Criteria

1. **Given** a tool raises exception/timeout AFTER `limiter.acquire()` succeeded, **When** the wrapper catches the exception, **Then** the consumed token is returned to the bucket. Implementation: `TokenBucketRateLimiter` exposes `release()` method; `crypto_tool_decorator` calls it on exception path.

2. **Given** a SSE consumer disconnects mid-stream during `_with_heartbeat` wrap, **When** Starlette cancels the request, **Then** the inner generator's cancellation does NOT corrupt LangGraph state or leak DB sessions. Implementation: structured concurrency / sentinel pattern; integration test simulating disconnect mid-DB-write asserts session is properly closed.

3. **Given** `crypto_data_snapshots` table at production scale (10M+ rows), **When** `cleanup_orphaned_crypto_snapshots` runs the `NOT EXISTS` batch, **Then** each batch completes within 60s (target). Implementation: verify index `ix_crypto_snapshots_cache_lookup` covers the orphan-detection query plan via `EXPLAIN ANALYZE`; if not, add covering index.

4. **Given** the snapshot scoping mismatch (refresh writes `search_space_id=NULL`, cleanup purges `IS NOT NULL`), **When** PM/Architect reviews the design, **Then** ADR-013 is finalized with an accepted decision (Answer A: bi-modal intentional + document, OR Answer B: refactor refresh to per-workspace). Code aligns with ADR decision.

## Tasks / Subtasks

- [ ] Task 1: TokenBucket release() API (AC #1)
  - [ ] 1.1 Add `release(self, count: int = 1) -> None` method to `TokenBucketRateLimiter`
  - [ ] 1.2 Lua script for atomic increment with `min(capacity, tokens + count)` cap
  - [ ] 1.3 Local fallback path mirrors the Lua semantics
  - [ ] 1.4 Modify `crypto_tool_decorator`: in `except` branches AND `asyncio.TimeoutError`, call `await limiter.release()` before re-raising
  - [ ] 1.5 Tests: `test_token_returned_on_tool_exception`, `test_token_returned_on_timeout`, `test_release_caps_at_capacity`
- [ ] Task 2: Heartbeat cancellation safety (AC #2)
  - [ ] 2.1 Audit `_with_heartbeat` and `_stream_new_chat_inner` for state mutated under cancellation (DB sessions, LangGraph checkpoints, Redis pubsub)
  - [ ] 2.2 Refactor `_with_heartbeat` to use `asyncio.shield()` for cleanup blocks OR migrate to structured-concurrency pattern (anyio task group)
  - [ ] 2.3 Add integration test: open SSE, abort client mid-DB-write, assert session is properly closed and no orphan rows
  - [ ] 2.4 Decision: keep current `task.cancel()` if test confirms safety, OR adopt new pattern
- [ ] Task 3: NOT EXISTS query plan analysis (AC #3)
  - [ ] 3.1 Snapshot production-shape data (or seed staging with realistic distribution)
  - [ ] 3.2 Run `EXPLAIN ANALYZE` on the orphan-detection DELETE
  - [ ] 3.3 If query uses `Seq Scan` or > 60s per batch: add composite index on `(search_space_id, id)` filtered for `search_space_id IS NOT NULL`
  - [ ] 3.4 Document outcome + index in story Dev Notes
- [ ] Task 4: ADR-013 snapshot scoping (AC #4)
  - [ ] 4.1 Schedule PM/Architect review meeting using ADR-013 as input
  - [ ] 4.2 Document decision back into ADR-013 (move "Status: Decision Required" → "Status: Accepted" with answer)
  - [ ] 4.3 If Answer A: update `CryptoDataSnapshot` model docstring + 11-3 spec clarification
  - [ ] 4.4 If Answer B: backfill migration + refresh task refactor (estimate +2 days)

## Dev Notes

### References
- ADR-013: Crypto Data Snapshots — Scoping Strategy (decision required)
- Sprint Change Proposal 2026-05-02
- Source items in `_bmad-output/implementation-artifacts/deferred-work.md`:
  - Story 11-1 round-2: heartbeat cancel safety
  - Story 11-3 round-2: NOT EXISTS scan, search-space scoping
  - Story 11-4 round-2: token waste on tool exception

### Code targets
- `nowing_backend/app/agents/new_chat/middleware/rate_limiter.py` — release() API
- `nowing_backend/app/agents/new_chat/tools/utils.py` — decorator exception path
- `nowing_backend/app/tasks/chat/stream_new_chat.py` — `_with_heartbeat` cancellation
- `nowing_backend/app/tasks/celery_tasks/crypto_refresh_tasks.py` — orphan query (read-only verification)
- `nowing_backend/app/db.py` — possibly model docstring update + new index migration
- `_bmad-output/planning-artifacts/adrs/ADR-013-snapshot-scoping-bimodal.md` — finalize

### Testing
- Unit: release() semantics, cap-at-capacity
- Integration: SSE disconnect mid-DB-write, NOT EXISTS query plan benchmark
- Manual: ADR-013 review meeting

### Estimated effort
- 5 BE-days = ~5 days
- ADR-013 Answer B path adds ~2 BE-days if chosen

## Dev Agent Record

### Agent Model Used
TBD

### Completion Notes List
TBD

### File List
TBD
