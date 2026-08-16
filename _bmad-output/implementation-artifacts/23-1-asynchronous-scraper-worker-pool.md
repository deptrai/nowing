story_key: 23-1-asynchronous-scraper-worker-pool
status: ready-for-dev
baseline_commit: 657f53d27efaa9e92716fe2a829daebce85c57b8
epic: 23
story: 1
---

# Story 23.1: Asynchronous Scraper Worker Pool (Celery + Redis Streams)

Status: ready-for-dev

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

- [ ] **Task 1: Celery Queue Architecture & Configuration (`nowing_backend/app/celery_app.py`)**
  - [ ] Configure dedicated queue `nowing.lead_scrapers` in `task_routes` and `task_queues`.
  - [ ] Set `acks_late=True`, `reject_on_worker_lost=True`, and task execution timeouts (soft: 60s, hard: 120s).
  - [ ] Add Celery worker startup script in `scripts/docker/entrypoint.sh` for scraper worker concurrency.

- [ ] **Task 2: Redis Stream Ingestion & Dual-Trigger Buffer Service (`nowing_backend/app/lead_intelligence/services/lead_stream_service.py`)**
  - [ ] Implement `LeadStreamBuffer` with dual flush triggers (5 leads OR 3s timeout).
  - [ ] Implement `XADD workspace:{id}:leads_stream MAXLEN ~ 10000`.
  - [ ] Implement background Redis Stream consumer worker processing stream batches and upserting into partitioned `leads` table.

- [ ] **Task 3: Redis Leaky-Bucket Rate Limiter & Circuit Breaker (`nowing_backend/app/lead_intelligence/services/rate_limiter.py`)**
  - [ ] Implement atomic Lua script for leaky-bucket token replenishment in Redis.
  - [ ] Implement `PlatformCircuitBreaker` with 3-strike failure counter and 10-minute cooldown TTL.
  - [ ] Add `AntiBotEscalationLog` event logging on circuit trip.

- [ ] **Task 4: Celery Scraper Task Definitions (`nowing_backend/app/tasks/lead_scrapers.py`)**
  - [ ] Define `@celery_app.task(queue="nowing.lead_scrapers") def run_platform_scrape_task(workspace_id, platform, query_params)`.
  - [ ] Wire existing scraper adapters (Batdongsan, Chợ Tốt, TopCV, Masothue, XActions) into Celery task execution loop with stream buffering.

- [ ] **Task 5: Frontend Stream Pulse Animation & Matrix Sync**
  - [ ] Verify `NowingLeadMatrix.tsx` renders new incoming records with `.streamed-lead-row-entering` animation.
  - [ ] Add floating pill badge `[⚡ Có X lead mới vừa cập nhật ↑]` when user is scrolled down.

- [ ] **Task 6: Automated Testing & Chaos Verification Suite**
  - [ ] Unit tests: `tests/unit/lead_intelligence/test_lead_stream_buffer.py` (verifying 5 leads batch and 3s timer flush).
  - [ ] Unit tests: `tests/unit/lead_intelligence/test_rate_limiter_lua.py` (verifying leaky bucket rate limits).
  - [ ] Unit tests: `tests/unit/lead_intelligence/test_circuit_breaker.py` (verifying 3-failure trip and TTL).
  - [ ] Integration tests: `tests/integration/tasks/test_scraper_celery_pool.py` (verifying end-to-end async scrape -> Redis stream -> DB upsert).

---

## Dev Agent Guardrails & Architectural Invariants

- **INV-23.1 (Worker Queue Isolation):** Scraper tasks BẮT BUỘC chạy trên queue `nowing.lead_scrapers`. Tuyệt đối không dùng queue `celery_default` của chat.
- **INV-23.2 (Bounded Redis Streams):** Mọi lệnh `XADD` BẮT BUỘC có `MAXLEN ~ 10000`.
- **INV-23.3 (Circuit Breaker Persistence):** Trạng thái Circuit Breaker BẮT BUỘC lưu trên Redis với key `circuit_breaker:scraper:{platform}` (TTL 10 phút).

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
