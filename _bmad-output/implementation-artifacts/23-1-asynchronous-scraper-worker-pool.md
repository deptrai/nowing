story_key: 23-1-asynchronous-scraper-worker-pool
status: done
baseline_commit: 657f53d27efaa9e92716fe2a829daebce85c57b8
epic: 23
story: 1
---

# Story 23.1: Asynchronous Scraper Worker Pool (Celery + Redis Streams)

Status: done

<!-- Note: Governed by FR-89, INV-23.1, INV-23.2, INV-23.3, and Architecture Spine: architecture-epic23-lead-infrastructure.md -->

## Story

As a growth operator and enterprise sales manager,
I want multi-platform lead scraping (Batdongsan, Chợ Tốt, TopCV, Masothue, Social XActions) executed asynchronously across a dedicated Celery worker pool and streamed via Redis Streams directly into PostgreSQL and the live browser matrix,
So that chat SSE streams remain fast and responsive (< 100ms first token), scrapers never block each other or cause OOM crashes, and newly discovered leads pulse into the data table in real time as they are extracted.

---

## Acceptance Criteria

### AC-1 — Dedicated Celery Queue & Non-Blocking Orchestration Dispatch
**Given** a lead generation prompt requiring multi-source scraping (Batdongsan, Chợ Tốt, TopCV, Masothue, XActions),
**When** `LeadGenOrchestrator` dispatches scraping tasks,
**Then** tasks are routed to the dedicated Celery queue `nowing.lead_scrapers` (isolated from `celery_default` to prevent chat SSE starvation).
**And** the orchestrator returns a `job_id` and initial streaming response within 100ms without blocking on scraper HTTP calls.

### AC-2 — Redis Stream Transit Buffer & Dual-Trigger Flush Window
**Given** active Celery scraper workers extracting lead records in parallel,
**When** a worker collects extracted leads,
**Then** it flushes buffered leads to Redis Stream `workspace:{workspace_id}:leads_stream` using either:
  1. **Batch Size Trigger:** Immediately when 5+ leads are buffered.
  2. **Time Window Trigger:** When 3.0 seconds elapse with at least 1 lead buffered.
**And** every `XADD` command strictly uses approximate trimming `MAXLEN ~ 10000` to prevent Redis memory exhaustion (INV-23.2).
**And** flushed leads are upserted into the partitioned PostgreSQL `leads` table with `ON CONFLICT (workspace_id, value_hmac) DO UPDATE` to guarantee idempotent writes.

### AC-3 — Redis Lua Leaky-Bucket Rate Limiter & Circuit Breaker
**Given** scraping tasks dispatched across multiple target platforms,
**When** workers invoke platform APIs/web pages,
**Then** a Lua script executed in Redis enforces per-platform rate limits:
  - Batdongsan: max 5 req/s
  - Chợ Tốt: max 10 req/s
  - TopCV / ITviec: max 3 req/s
  - Masothue: max 2 req/s
**And** if any scraper encounters 3 consecutive Cloudflare CAPTCHA/anti-bot blocks or HTTP 429 errors, the circuit breaker trips for that platform for 10 minutes (`circuit_breaker:scraper:{platform}` with 600s TTL), allowing remaining platforms to continue running unaffected.

### AC-4 — Worker Crash Resilience & Dead-Letter Recovery
**Given** a Celery worker encountering a fatal crash (`SIGKILL`, node restart, or OOM),
**When** Celery tasks are configured with `acks_late=True` and `reject_on_worker_lost=True`,
**Then** unacknowledged tasks are re-queued to another worker without duplicating records in the database.
**And** pending Redis Stream messages are tracked via `XPENDING` and reclaimed via `XCLAIM` after 30 seconds of inactivity.

### AC-5 — Frontend Hardware-Accelerated Realtime Ingestion Pulse
**Given** a client connected to the Leads Split-View Canvas,
**When** new lead batches are streamed into the data table via Zero-cache / Redis pub-sub,
**Then** newly inserted rows display the `.streamed-lead-row-entering` CSS shimmer pulse animation (Mint green glow fading over 800ms) with GPU compositing (`transform: translateZ(0)`), ensuring 60 FPS table rendering even with 500+ live rows.

---

## Tasks / Subtasks

- [x] **Task 1: Celery Queue Architecture & Configuration (`nowing_backend/app/celery_app.py`)**
  - [x] Configure dedicated queue `nowing.lead_scrapers` in `task_routes` and `task_queues`.
  - [x] Set `acks_late=True`, `reject_on_worker_lost=True`, and task execution timeouts (soft: 60s, hard: 120s).
  - [x] Ensure `run_platform_scrape_task` routes strictly to `nowing.lead_scrapers` (INV-23.1).

- [x] **Task 2: Redis Stream Ingestion & Dual-Trigger Buffer Service (`nowing_backend/app/lead_intelligence/services/lead_stream_service.py`)**
  - [x] Implement `LeadStreamBuffer` with dual flush triggers (5 leads OR 3s timeout).
  - [x] Implement `XADD workspace:{id}:leads_stream MAXLEN ~ 10000` (INV-23.2).
  - [x] Implement `build_lead_upsert_stmt` helper with `ON CONFLICT (workspace_id, value_hmac) DO UPDATE`.
  - [x] Implement `ingest_stream_leads_to_db` for bulk database persistence.

- [x] **Task 3: Redis Leaky-Bucket Rate Limiter & Circuit Breaker (`nowing_backend/app/lead_intelligence/services/rate_limiter.py` & `circuit_breaker.py`)**
  - [x] Implement atomic Lua script for leaky-bucket token replenishment in Redis.
  - [x] Implement `PlatformRateLimiter` with per-platform rate limits (Batdongsan: 5, Chợ Tốt: 10, TopCV: 3, Masothue: 2).
  - [x] Implement `PlatformCircuitBreaker` with 3-strike failure counter and 10-minute cooldown TTL (`circuit_breaker:scraper:{platform}`, INV-23.3).

- [x] **Task 4: Celery Scraper Task Definitions (`nowing_backend/app/tasks/lead_scrapers.py`)**
  - [x] Define `@celery_app.task(queue="nowing.lead_scrapers") def run_platform_scrape_task(workspace_id, platform, query_params)`.
  - [x] Wire scraper adapters (Batdongsan, Chợ Tốt, TopCV, Masothue, Social XActions) into Celery task execution loop with stream buffering.
  - [x] Implement `reclaim_pending_stream_messages` for dead-letter recovery via `XCLAIM` after 30s inactivity.

- [x] **Task 5: Frontend Stream Pulse Animation & Matrix Sync (`nowing_web/`)**
  - [x] Add `@keyframes leadCellPulse` and `.streamed-lead-row-entering` class with GPU compositing in `nowing_web/app/globals.css`.
  - [x] Author Playwright E2E verification test `nowing_web/tests/leads/lead-stream-pulse.spec.ts`.

- [x] **Task 6: Automated Testing & Verification Suite**
  - [x] Unit tests: `tests/unit/lead_intelligence/test_lead_stream_buffer.py` (5 passed).
  - [x] Unit tests: `tests/unit/lead_intelligence/test_rate_limiter_lua.py` (5 passed).
  - [x] Unit tests: `tests/unit/lead_intelligence/test_circuit_breaker.py` (5 passed).
  - [x] Integration tests: `tests/integration/tasks/test_scraper_celery_pool.py` (4 passed).
  - [x] Full lead intelligence unit test regression suite: 184/184 tests passed (100% green).
  - [x] Frontend typecheck: `pnpm tsc --noEmit` clean (0 errors).

### Review Findings
- [x] [Review][Patch] Fix Event Loop Mismatch for Redis client in Celery worker processes [`nowing_backend/app/redis_client.py:10`]
- [x] [Review][Patch] Use Redis pipeline in `LeadStreamBuffer.flush()` and prevent data loss on network failure [`nowing_backend/app/lead_intelligence/services/lead_stream_service.py:136`]
- [x] [Review][Patch] Use server `TIME` and `HSET` in rate limiter Lua script with zero-rate guard [`nowing_backend/app/lead_intelligence/services/rate_limiter.py:30`]
- [x] [Review][Patch] Fix Circuit Breaker case sensitivity, reset counter on trip, and fail-open [`nowing_backend/app/lead_intelligence/services/circuit_breaker.py:35`]
- [x] [Review][Patch] Add in-memory deduplication before `pg_insert` in `build_lead_upsert_stmt` [`nowing_backend/app/lead_intelligence/services/lead_stream_service.py:50`]
- [x] [Review][Patch] Add concurrency lock and `time.monotonic()` in `LeadStreamBuffer` [`nowing_backend/app/lead_intelligence/services/lead_stream_service.py:90`]
- [x] [Review][Patch] Log normalization failures and loop retry on rate limiter throttling in Celery scraper task [`nowing_backend/app/tasks/lead_scrapers.py:22`]
- [x] [Review][Patch] Fix orchestrator empty source handling and confidence score types [`nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:97`]

---

## Dev Agent Guardrails & Architectural Invariants

- **INV-23.1 (Worker Queue Isolation):** Scraper tasks BẮT BUỘC chạy trên queue `nowing.lead_scrapers`. Tuyệt đối không dùng queue `celery_default` của chat.
- **INV-23.2 (Bounded Redis Streams):** Mọi lệnh `XADD` BẮT BUỘC có `MAXLEN ~ 10000`.
- **INV-23.3 (Circuit Breaker Persistence):** Trạng thái Circuit Breaker BẮT BUỘC lưu trên Redis với key `circuit_breaker:scraper:{platform}` (TTL 10 phút).

---

## Dev Notes & ATDD Artifacts

- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-23-1-asynchronous-scraper-worker-pool.md`
- **Unit Tests (Buffer & Trimming):** `nowing_backend/tests/unit/lead_intelligence/test_lead_stream_buffer.py`
- **Unit Tests (Rate Limiter Lua):** `nowing_backend/tests/unit/lead_intelligence/test_rate_limiter_lua.py`
- **Unit Tests (Circuit Breaker):** `nowing_backend/tests/unit/lead_intelligence/test_circuit_breaker.py`
- **Integration Tests (Celery Pool & Recovery):** `nowing_backend/tests/integration/tasks/test_scraper_celery_pool.py`
- **Frontend E2E Tests (Realtime Stream Pulse):** `nowing_web/tests/leads/lead-stream-pulse.spec.ts`

---

## Dev Agent Record

### Implementation Plan
1. Configure dedicated Celery queue `nowing.lead_scrapers` and task routes in `celery_app.py`.
2. Build `LeadStreamBuffer` with dual flush triggers (5 leads / 3s window) and `MAXLEN ~ 10000` stream trimming in `lead_stream_service.py`.
3. Implement atomic Lua leaky-bucket `PlatformRateLimiter` and 3-strike `PlatformCircuitBreaker` (TTL 600s).
4. Define `run_platform_scrape_task` Celery task on `nowing.lead_scrapers` queue and `reclaim_pending_stream_messages` recovery.
5. Extend `LeadGenOrchestrator.dispatch_scrape_job` for non-blocking < 100ms job dispatch.
6. Add hardware-accelerated CSS keyframes `leadCellPulse` and class `.streamed-lead-row-entering` in `globals.css`.

### Completion Notes
- All 19 new acceptance tests in unit and integration suites pass (100% green).
- Full regression suite in `tests/unit/lead_intelligence/` passes (184/184 tests green).
- All architectural invariants INV-23.1, INV-23.2, INV-23.3 strictly enforced.
- Backend ruff lint & format 100% clean; frontend TypeScript `tsc --noEmit` passes with 0 errors.

### File List
- `nowing_backend/app/celery_app.py` (modified: added `LEAD_SCRAPERS_QUEUE` and routes)
- `nowing_backend/app/db.py` (modified: added `value_hmac` column to `Lead` model)
- `nowing_backend/app/redis_client.py` (new: async Redis singleton client helper)
- `nowing_backend/app/lead_intelligence/services/lead_stream_service.py` (new: `LeadStreamBuffer`, `build_lead_upsert_stmt`, `ingest_stream_leads_to_db`)
- `nowing_backend/app/lead_intelligence/services/rate_limiter.py` (new: atomic Lua `PlatformRateLimiter`)
- `nowing_backend/app/lead_intelligence/services/circuit_breaker.py` (new: `PlatformCircuitBreaker` with 600s TTL)
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` (modified: added `dispatch_scrape_job` & `DispatchedScrapeJobResponse`)
- `nowing_backend/app/tasks/lead_scrapers.py` (new: `run_platform_scrape_task`, `reclaim_pending_stream_messages`)
- `nowing_backend/tests/unit/lead_intelligence/test_lead_stream_buffer.py` (new: 5 unit tests)
- `nowing_backend/tests/unit/lead_intelligence/test_rate_limiter_lua.py` (new: 5 unit tests)
- `nowing_backend/tests/unit/lead_intelligence/test_circuit_breaker.py` (new: 5 unit tests)
- `nowing_backend/tests/integration/tasks/test_scraper_celery_pool.py` (new: 4 integration tests)
- `nowing_web/app/globals.css` (modified: added `leadCellPulse` animation and `.streamed-lead-row-entering`)
- `nowing_web/tests/leads/lead-stream-pulse.spec.ts` (new: Playwright E2E test)
- `_bmad-output/test-artifacts/atdd-checklist-23-1-asynchronous-scraper-worker-pool.md` (new: ATDD checklist)

### Change Log
- 2026-08-16: Implemented Story 23.1 Asynchronous Scraper Worker Pool (Celery + Redis Streams) with dual-trigger stream buffering, atomic Lua rate limiter, circuit breaker, worker resilience, and CSS shimmer pulse animation. All 184 unit/integration tests passing. Status moved to review.

---

## Verification Commands

```bash
# 1. Run Lead Scraper & Stream Unit Tests
cd nowing_backend
uv run pytest tests/unit/lead_intelligence/test_lead_stream_buffer.py tests/unit/lead_intelligence/test_rate_limiter_lua.py tests/unit/lead_intelligence/test_circuit_breaker.py -q

# 2. Run Celery Scraper Pool Integration Tests
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing REDIS_URL=redis://localhost:6380/0 uv run pytest tests/integration/tasks/test_scraper_celery_pool.py -q

# 3. Lint & Format
ruff check app/tasks/lead_scrapers.py app/lead_intelligence/services/lead_stream_service.py app/lead_intelligence/services/rate_limiter.py
ruff format app/tasks/lead_scrapers.py app/lead_intelligence/services/lead_stream_service.py app/lead_intelligence/services/rate_limiter.py

# 4. Frontend Typecheck
cd ../nowing_web
pnpm tsc --noEmit
```


