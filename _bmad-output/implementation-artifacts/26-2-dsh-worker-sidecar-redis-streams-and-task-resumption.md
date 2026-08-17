---
story_key: "26-2"
epic: "epic-26"
story: "26.2"
title: "dsh-worker Sidecar Container, Redis Streams & Task Resumption"
status: "done"
baseline_commit: "699e74dfe"
---

# Story 26.2: dsh-worker Sidecar Container, Redis Streams & Task Resumption

## CRITICAL DESIGN DECISIONS — Resolve Before Dev

1. **Sidecar auth model.** The sidecar must not access the database directly (AD-102 Rule 2). Decide whether the sidecar uses:
   - **Option A (recommended):** A workspace-scoped `PersonalAccessToken` with `token_kind='service_account'`, where `workspace_id` matches the mission's workspace. The service-account user must be a workspace member with `LEADS_WRITE` (or `DSH_MISSIONS_WRITE`) so normal RBAC passes. For the internal `PATCH /v1/dsh/missions/.../checkpoint` route, the sidecar must send an `X-Dsh-Worker-Secret` header and the gateway must compare it to `config.DSH_WORKER_SECRET` using `hmac.compare_digest` (constant-time). The secret check is sufficient on that route; the PAT workspace-membership check may be bypassed only there.
   - **Option B:** A new `token_kind='dsh_worker'` PAT with `scopes=["dsh_missions:write","leads:write"]` and a custom auth dependency that validates workspace scoping without requiring a `WorkspaceMembership` row. This is cleaner but requires touching `app/users.py`, `app/db.py`, and PAT creation routes. Even with Option B, the `X-Dsh-Worker-Secret` must still be sent and validated with `hmac.compare_digest` for `PATCH .../checkpoint`.
2. **One image or a separate package.** The existing `nowing_backend` image already contains all dependencies and `app/` code. The sidecar can run from the same image with `SERVICE_ROLE=dsh`, avoiding a new Docker build and cross-package imports. This is consistent with AD-102’s “sidecar is an exception to the monolith process” rule, not a business-domain microservice.
3. **Mission model shape.** For crash resumption, mission state must be in PostgreSQL, but PII/full payload should not be published to `zero_publication`. Use a `dsh_missions` table with PII-safe columns (`status`, `phase`, `progress_percent`) published and `payload`/`checkpoint` JSONB kept private.
4. **XAUTOCLAIM idempotent lock.** DSH uses `XAUTOCLAIM` (Redis 6.2+) because it claims all idle messages in the Pending Entry List in a single round-trip, which is the right fit for a long-running worker that may crash and resume. The existing `app/tasks/lead_scrapers.py:168–214` pattern does fine-grained manual reclaim with `XPENDING` + `XCLAIM`; DSH keeps that pattern in mind but does not copy it verbatim. A long mission stays in the Redis PEL for minutes/hours. The active worker must call `XCLAIM ... IDLE 0` on its own message every ~30s; otherwise a second worker will see `idle_time > 60s` and `XAUTOCLAIM` it. Add a per-mission Redis lock `nowing:dsh:lock:{mission_id}` with a TTL of 90s so only a dead worker’s mission is resumed.
5. **Tini + WAL protection.** `nowing_backend/Dockerfile` currently has no `tini` and `docker/postgresql.conf` lacks `max_slot_wal_keep_size`/`wal_keep_size`. These are mandatory for AD-108. Do not ship the sidecar without them.

## Story

As a backend platform engineer,
I want a `dsh-worker` sidecar container that consumes long-running mission messages from a dedicated Redis Stream (`nowing:dsh:tasks`) and executes them via `XREADGROUP`,
So that autonomous 1–8h lead-research missions can run outside the FastAPI request/response cycle, survive a worker crash through `XAUTOCLAIM` + PostgreSQL checkpoint resumption, and finally report results back to the Nowing gateway through authenticated REST endpoints (`POST /api/v1/workspaces/:workspace_id/leads/batch-ingest`, `POST /api/v1/workspaces/:workspace_id/scrapers/chainlens/research?mode=async`, etc.).

---

## Acceptance Criteria

### AC-1: dsh-worker Sidecar Container & Redis Stream Consumer (AD-102, AD-106)

- **Given** a running Nowing stack with Redis 7 and PostgreSQL 16,
- **When** a `dsh-worker` container starts with `SERVICE_ROLE=dsh` and valid `DSH_WORKER_PAT` / `DSH_WORKER_SECRET`,
- **Then** it:
  1. Creates/ensures the consumer group `dsh_workers` on `nowing:dsh:tasks` (`XGROUP CREATE ... MKSTREAM`), swallowing `BUSYGROUP`.
  2. Consumes mission messages with `XREADGROUP` as a uniquely named consumer (`{hostname}-{pid}-{uuid}`), with `count=1`, `block=5000ms`.
  3. For each message, sets a Redis lock `nowing:dsh:lock:{mission_id}` with 90s TTL and a heartbeat loop that renews the lock and calls `XCLAIM nowing:dsh:tasks dsh_workers {consumer} 0 {msg_id} IDLE 0` every `DSH_HEARTBEAT_INTERVAL_SECONDS` (default 30s) to reset message idle time.
  4. Persists a `dsh_missions` row with `status='running'`, `phase='crawl'`, `progress_percent=0`, and a `checkpoint` JSONB starting at `{phase: "crawl", subtasks: []}`.
  5. Executes the mission through a `DshMissionExecutor` (default `DeepLeadResearchExecutor`) that dispatches sub-tasks hierarchically: `crawl` → `reasoning` → `extraction` → `ingestion`. For 26.2 the default executor may be a sequential pipeline; the Expert Pool pattern (Research Specialist, Scraper Specialist, PII Auditor) is the intended extension point.
  6. Calls `batch_ingest_leads` and scraper/ChainLens endpoints through authenticated REST, not direct DB access.
  7. Updates `checkpoint` after each sub-task via `PATCH /v1/dsh/missions/{mission_id}/checkpoint` and only `XACK` the original stream message after the whole mission reaches a terminal state (`success`, `error`, or `dlq`).

### AC-2: Crash Resumption & Dead-Letter Queue (AD-102, AD-108)

- **Given** a `dsh-worker` process that crashes or is killed while processing a mission,
- **When** a new `dsh-worker` starts (or another replica exists) and the original message has been idle for more than 60s,
- **Then**:
  1. The new worker calls `XAUTOCLAIM nowing:dsh:tasks dsh_workers {new_consumer} 60000 COUNT 10` (single round-trip reclaim of all idle messages; the older `app/tasks/lead_scrapers.py:168–214` pattern uses `XPENDING` + `XCLAIM` for fine-grained manual reclaim, but `XAUTOCLAIM` is the right primitive here).
  2. For each reclaimed message, it first checks `nowing:dsh:lock:{mission_id}` and skips the message if the lock is still held by a live worker (heartbeat TTL not expired). This prevents double execution in a split-brain scenario.
  3. It reads the mission row by `mission_id`, loads `checkpoint`, and resumes from the last completed sub-task (`chainlens.research` run id, lead batch ids, etc.).
  4. It increments `retry_count` on the mission row and `checkpoint.attempt`.
  5. If `retry_count >= 3` consecutive failures, it `XACK` the message and writes it to the dead-letter stream `nowing:dsh:dlq` with `error`, `failed_at`, `original_id`, and `payload`, then sets `dsh_missions.status='dlq'`.

### AC-3: Mission Dispatch & Real-Time State (AD-104)

- **Given** an authenticated user or service principal with permission to create leads in a workspace,
- **When** `POST /api/v1/workspaces/{workspace_id}/dsh/missions` is called with a valid `DshMissionRequest` payload,
- **Then** it:
  1. Inserts a `dsh_missions` row in `pending` state.
  2. `XADD`s the mission to `nowing:dsh:tasks` with the serialized payload.
  3. Returns `DshMissionResponse` with `mission_id` and `status='pending'`.
  4. Publishes only PII-safe columns (`id`, `workspace_id`, `mission_type`, `status`, `phase`, `progress_percent`, `current_subtask_id`, `created_at`, `updated_at`) through `zero_publication` so the Glass Box Mission Progress UI updates with < 10ms latency.

### AC-4: Container & WAL Protection (AD-108)

- **Given** the `dsh-worker` Docker image,
- **When** it starts,
- **Then**:
  1. The Dockerfile must install `tini` and use it as PID 1: `ENTRYPOINT ["/usr/bin/tini", "--", "/app/scripts/docker/entrypoint.sh"]`.
  2. The worker must enforce a 60s hard timeout on every synchronous tool call / REST round-trip and on every `XREADGROUP` block.
  3. `docker/postgresql.conf` must add `max_slot_wal_keep_size = 4096MB` and `wal_keep_size = 1024MB` before the sidecar is considered production-ready.
  4. `docker/docker-compose.yml` must include a `dsh_worker` service with `SERVICE_ROLE: dsh`, healthcheck, and dependency on `migrations` + `redis`.

---

## Source Artifacts & Traceability

| Artifact | Path | Relevant Lines | What it provides |
|----------|------|----------------|------------------|
| Epics & Stories | `_bmad-output/planning-artifacts/epics.md` | 3342–3352 | Story 26.2 text and AC-1/AC-2. |
| Architecture Invariants | `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` | 104–111, 147–151, 157–162 | AD-102 (sidecar + Redis Streams + XAUTOCLAIM/DLQ), AD-106 (Mission Supervisor → Expert Pool), AD-108 (tini, 60s timeout, WAL limits). |
| Implementation Readiness | `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17-epic26.md` | 45 | FR-L3 traceability matrix. |
| Previous story | `_bmad-output/implementation-artifacts/26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md` | full file | The gateway endpoints (`batch_ingest_leads`, `POST /v1/chainlens/ingest`) the sidecar will call. |
| Redis Stream consumer pattern | `nowing_backend/app/tasks/social_stream_worker.py` | 42–45, 500–614 | `XGROUP CREATE`, `XREADGROUP`, `XACK`, DLQ `XADD` pattern. |
| Redis XCLAIM recovery pattern | `nowing_backend/app/tasks/lead_scrapers.py` | 168–214 | `XPENDING`/`XCLAIM` reclaim after `min_idle_ms`. |
| Redis client helper | `nowing_backend/app/redis_client.py` | 15–41 | `get_redis_client()` async factory. |
| Lead batch endpoint | `nowing_backend/app/routes/lead_batch_routes.py` | 72–114 | `POST /api/v1/workspaces/{workspace_id}/leads/batch-ingest`. |
| Lead batch service | `nowing_backend/app/services/lead_batch_service.py` | 130–150 | `LeadBatchService.ingest_batch()` wrapper. |
| ChainLens research capability | `nowing_backend/app/capabilities/chainlens/research/definition.py` | 9–22 | Capability registration for `chainlens.research`. |
| ChainLens research executor | `nowing_backend/app/capabilities/chainlens/research/executor.py` | 1–47, 1100–1120 | Calls ChainLens, returns `ResearchOutput`. |
| Capability REST execution | `nowing_backend/app/capabilities/core/access/rest.py` | 201–369 | Generic `POST /workspaces/{id}/scrapers/{platform}/{verb}?mode=async` route. |
| Async runner / run lifecycle | `nowing_backend/app/capabilities/core/async_runner.py` | 49–96, 98–202 | `start_async_run` and `_execute_async_run` background task pattern. |
| Run row model | `nowing_backend/app/db.py` | 3630–3712 | `Run` table shape to map sub-task `run_id`s. |
| ChainLens ingest job model | `nowing_backend/app/db.py` | 4353–4405 | `ChainLensIngestJob` for ingest job id tracking. |
| ChainLens chunk model | `nowing_backend/app/db.py` | 1655–1674 | `ChainLensChunk` table with UUID composite PK. |
| ChainLens reception service | `nowing_backend/app/services/chainlens/ingest_reception.py` | 58–120 | Stateless chunk ingestion service (Story 26.1). |
| Personal access token model | `nowing_backend/app/db.py` | 3561–3629 | `PersonalAccessToken` with `workspace_id`, `scopes`, `token_kind`. |
| PAT auth resolution | `nowing_backend/app/users.py` | 330–383 | `get_auth_context` resolves `nw_pat_...` tokens. |
| Permission enum | `nowing_backend/app/db.py` | 304–417 | Existing permissions; add `DSH_MISSIONS_WRITE`/`DSH_MISSIONS_READ`. |
| Capability registry | `nowing_backend/app/capabilities/core/store.py` | 1–67 | `CapabilityRegistry` / `get_capability`. |
| Execute with context | `nowing_backend/app/capabilities/core/__init__.py` | 70–88 | `execute_with_context` helper. |
| Zero publication | `nowing_backend/app/zero_publication.py` | 134–156, 207–219 | `LEADS_COLS` pattern for adding `DSH_MISSION_COLS`. |
| Config / Redis / Celery | `nowing_backend/app/config/__init__.py` | 653–664 | `REDIS_URL`, `REDIS_APP_URL`, `CELERY_*` constants. |
| Entrypoint script | `nowing_backend/scripts/docker/entrypoint.sh` | 1–184 | `SERVICE_ROLE` cases; add `dsh`. |
| Dockerfile | `nowing_backend/Dockerfile` | 1–224 | No `tini`; must add. |
| Docker compose | `docker/docker-compose.yml` | 180–210 | Celery worker service pattern to copy for `dsh_worker`. |
| PostgreSQL config | `docker/postgresql.conf` | 1–20 | Missing `max_slot_wal_keep_size`/`wal_keep_size`. |

---

## Technical Context — Already BUILT

- **Redis Streams are already in production use for social post ingestion and lead scraper recovery.** `app/tasks/social_stream_worker.py:500–614` shows a full `XGROUP CREATE` → `XREADGROUP` → `XACK` → DLQ `XADD` consumer loop. `app/tasks/lead_scrapers.py:168–214` shows `XPENDING`/`XCLAIM` crash recovery.
- **A shared async Redis client exists:** `app/redis_client.py:15–41` provides `get_redis_client()` tied to the running event loop.
- **Batch lead ingestion is live:** `app/routes/lead_batch_routes.py:72–114` and `app/services/lead_batch_service.py:130–150` accept 1–100 leads, DNC-filter, HMAC, and encrypt PII.
- **ChainLens research is a first-class capability:** `app/capabilities/chainlens/research/definition.py` and `app/capabilities/chainlens/research/executor.py`. The REST router already supports `?mode=async` (`app/capabilities/core/access/rest.py:255–274`) and `GET /workspaces/{id}/scrapers/runs/{run_id}/events` for SSE tailing.
- **Run lifecycle / async runner is already centralized:** `app/capabilities/core/async_runner.py:49–96` and `app/capabilities/core/events_redis.py:37–107` provide a battle-tested pattern for starting, tracking, and streaming background work across processes.
- **PAT auth exists and is resolved by `get_auth_context`:** `app/users.py:330–383` and `app/utils/pat.py:36–52`.
- **Container `SERVICE_ROLE` infrastructure is in place:** `nowing_backend/scripts/docker/entrypoint.sh:156–184` handles `migrate`, `api`, `worker`, `beat`, `all`.
- **Zero-Cache publication mechanism is in place:** `app/zero_publication.py` lets you add a new `DSH_MISSION_COLS` block and `ZERO_PUBLICATION["dsh_missions"]` entry.
- **The `ChainLensChunk` model already exists in `app/db.py` and was not introduced by Story 26.1; Story 26.1 added the `ChainLensIngestJob` table and the `verified_contacts` PII hardening columns (`is_unlocked`, `pii_access_audit_logs`, `value_hmac`):** `app/db.py:1655–1674` (`ChainLensChunk`), `app/db.py:4353–4405` (`ChainLensIngestJob`), `app/db.py:5065–5152` (`verified_contacts`). The base `verified_contacts` PII columns pre-date Story 26.1.

## GAPs This Story Closes

1. **No `dsh-worker` package or container.** There is no `app/dsh_worker/`, no `SERVICE_ROLE=dsh`, and no `dsh_worker` compose service.
2. **No `nowing:dsh:tasks` / `nowing:dsh:dlq` stream plumbing.** No producer, no consumer group, no `XAUTOCLAIM` resume logic.
3. **No mission persistence model.** There is no `DshMission` table, no `dsh_missions` entry in `zero_publication`, and no checkpoint schema.
4. **No mission dispatch / checkpoint REST routes.** There is no `POST /api/v1/workspaces/{id}/dsh/missions` and no `PATCH /v1/dsh/missions/{id}/checkpoint`.
5. **No tini PID 1 / WAL protection.** `nowing_backend/Dockerfile` and `docker/postgresql.conf` are missing AD-108 requirements.
6. **No sidecar auth contract.** A service token / PAT permission model for the worker needs to be defined.

---

## Implementation Plan

### Task 1 — Schema & Migration

- Add `dsh_missions` table to `nowing_backend/app/db.py` and create `alembic/versions/<revision>_add_dsh_mission_tables.py`. Suggested columns:
  - `id` UUID PK
  - `workspace_id` Integer FK → `workspaces.id` (index)
  - `user_id` UUID FK → `user.id` (who dispatched; nullable for service)
  - `mission_type` String(50) not null (e.g. `deep_lead_research`, `noop`)
  - `status` String(20) not null (`pending`, `running`, `success`, `error`, `cancelled`, `dlq`)

    Use the same vocabulary as `Run.status` (`app/db.py:3683`): `running`, `success`, `error`, `cancelled`. Add `pending` for the pre-dispatch state and `dlq` for the stream dead-letter state.
  - `phase` String(50) (`crawl`, `reasoning`, `extraction`, `ingestion`)
  - `progress_percent` Integer default 0
  - `current_subtask_id` String(255) nullable
  - `payload` JSONB not null default `{}`
  - `checkpoint` JSONB not null default `{}`
  - `retry_count` Integer default 0
  - `error` JSONB nullable
  - `started_at`, `completed_at`, `created_at`, `updated_at` timestamps
- **Checkpoint JSONB schema.** `checkpoint` defaults to `{}` and is written by the worker after each sub-task. Suggested shape:
  ```json
  {
    "phase": "crawl|reasoning|extraction|ingestion",
    "subtasks": [
      {"name": "...", "status": "pending|running|completed|failed", "run_id": "...", "batch_ids": []}
    ],
    "attempt": 1,
    "last_updated_at": "..."
  }
  ```
- (Optional but recommended) add `dsh_mission_subtasks` table if the dev agent prefers a normalized sub-task state over `checkpoint.subtasks`.
- Update `app/zero_publication.py` with a `DSH_MISSION_COLS` block (PII-safe columns only) and add `"dsh_missions": DSH_MISSION_COLS` to `ZERO_PUBLICATION`:
  ```python
  DSH_MISSION_COLS = [
      "id",
      "workspace_id",
      "mission_type",
      "status",
      "phase",
      "progress_percent",
      "current_subtask_id",
      "created_at",
      "updated_at",
  ]
  ```
- Add `Permission.DSH_MISSIONS_WRITE` and `DSH_MISSIONS_READ` to the `Permission` enum. `Permission` is a Python `StrEnum` in `app/db.py:304–417`, so this is code-only and needs no alembic migration. Update `app/utils/rbac.py` and any default role permission maps (e.g., `Editor`/`Viewer` in `app/db.py:435–531`) to recognize the new values.

### Task 2 — Config

- In `app/config/__init__.py` add a `DSH_*` block:
  - `DSH_STREAM_KEY = "nowing:dsh:tasks"`
  - `DSH_CONSUMER_GROUP = "dsh_workers"`
  - `DSH_DEAD_LETTER_STREAM = "nowing:dsh:dlq"`
  - `DSH_BLOCK_MS = 5000`
  - `DSH_CLAIM_IDLE_MS = 60000`
  - `DSH_HEARTBEAT_INTERVAL_SECONDS = 30`
  - `DSH_LOCK_TTL_SECONDS = 90`
  - `DSH_MAX_RETRIES = 3`
  - `DSH_INTERNAL_BASE_URL = os.getenv("DSH_INTERNAL_BASE_URL", "http://backend:8000")`
  - `DSH_WORKER_PAT = os.getenv("DSH_WORKER_PAT")`
  - `DSH_WORKER_SECRET = os.getenv("DSH_WORKER_SECRET")`

### Task 3 — Auth / Internal Routes

- Add `app/routes/dsh_worker_routes.py` (or `app/routes/dsh_routes.py`) with:
  - `POST /api/v1/workspaces/{workspace_id}/dsh/missions` — public dispatch (PAT/session, `LEADS_WRITE` or `DSH_MISSIONS_WRITE`).
  - `GET /api/v1/workspaces/{workspace_id}/dsh/missions/{mission_id}` — public status.
  - `PATCH /v1/dsh/missions/{mission_id}/checkpoint` — internal sidecar checkpoint; requires both `Authorization: Bearer {DSH_WORKER_PAT}` (workspace-scoped, `token_kind='service_account'`) and `X-Dsh-Worker-Secret`. The gateway validates the secret with `hmac.compare_digest(config.DSH_WORKER_SECRET, ...)` and may bypass the workspace-membership check only on this route. Option B (`token_kind='dsh_worker'`) remains an alternative if the dev agent wants a custom auth dependency.
  - `POST /v1/dsh/missions/{mission_id}/subtasks` — optional internal subtask creation.
- Mount in `app/app.py` alongside `lead_batch_router`.
- Add `app/services/dsh_mission_service.py` for mission CRUD and checkpoint updates.
- Add `app/schemas/dsh.py` with `DshMissionRequest`, `DshMissionResponse`, `DshCheckpointRequest` Pydantic schemas.

### Task 4 — dsh-worker Package

Create `nowing_backend/app/dsh_worker/`:

- `__init__.py` — package marker.
- `main.py` — entrypoint: `asyncio.run(run_worker())`, signal handlers, 60s global context timeout, exit on `SIGTERM`.
- `config.py` — thin `DSHConfig` dataclass read from `app.config.config`.
- `consumer.py` — `DshStreamConsumer`:
  - `ensure_consumer_group()`
  - `xreadgroup_loop()`
  - `xautoclaim_pending()`
  - `heartbeat_claim(msg_id)` (periodic `XCLAIM ... IDLE 0`)
  - `xack_message(msg_id)`
  - `move_to_dlq(msg_id, payload, error)`
  - Redis lock helpers (`acquire_mission_lock`, `renew_mission_lock`).
- `client.py` — `NowingDshClient` (httpx async client, PAT auth, 60s timeout):
  - `dispatch_mission(...)` (used by route, not worker)
  - `post_checkpoint(...)` — always sends `X-Dsh-Worker-Secret` alongside the PAT.
  - `call_chainlens_research(...)`
  - `call_scraper(...)`
  - `call_batch_ingest_leads(...)`
  - `get_run(run_id)` and `tail_run_events(run_id)` (SSE or poll).
- `supervisor.py` — `DshMissionSupervisor`:
  - `execute(mission_id, payload)`
  - Builds a `MissionPlan` with subtasks: `crawl/research`, `scraper/gap_fill` (optional), `extraction`, `ingestion`.
  - For 26.2, the default `DeepLeadResearchExecutor` may implement a **deterministic, domain-only lead batch** from `ResearchOutput.sources` (no PII extraction) to keep the pipeline end-to-end without waiting for Story 26.3. Phone/email extraction from source content is explicitly deferred to the Hybrid LLM Router (Story 26.3).
  - Calls `post_checkpoint` after each sub-task completion.
- `lock.py` — Redis lock primitives using `get_redis_client()`.
- `health.py` — optional `--healthcheck` CLI that verifies Redis connectivity.

### Task 5 — Container / Compose / WAL

- `nowing_backend/Dockerfile`:
  - Add `tini` to the apt install list in the `base` stage.
  - Set the production stage to `ENTRYPOINT ["/usr/bin/tini", "--", "/app/scripts/docker/entrypoint.sh"]` and `CMD []` so `tini` supervises `entrypoint.sh` as PID 1.
- `nowing_backend/scripts/docker/entrypoint.sh`:
  - Add a `dsh)` case that `exec`s `python -m app.dsh_worker.main` (do not wrap with a second `tini`; `tini` is the container ENTRYPOINT).
- `docker/postgresql.conf`:
  - Add `max_slot_wal_keep_size = 4096MB` and `wal_keep_size = 1024MB`.
- `docker/docker-compose.yml`:
  - Add a `dsh_worker` service. Copy the `celery_worker` block (`Source Artifacts line 108`; `docker/docker-compose.yml:180–210`) and change `SERVICE_ROLE` to `dsh` and the healthcheck. Suggested snippet:
    ```yaml
      dsh_worker:
        image: ghcr.io/modsetter/nowing-backend:${NOWING_VERSION:-latest}${NOWING_VARIANT:+-${NOWING_VARIANT}}
        volumes:
          - shared_temp:/shared_tmp
          - object_store:/app/.local_object_store
        env_file:
          - .env
        extra_hosts:
          - "host.docker.internal:host-gateway"
        environment:
          DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://${DB_USER:-nowing}:${DB_PASSWORD:-nowing}@${DB_HOST:-db}:${DB_PORT:-5432}/${DB_NAME:-nowing}}
          REDIS_APP_URL: ${REDIS_URL:-redis://redis:6379/0}
          PYTHONPATH: /app
          FILE_STORAGE_LOCAL_PATH: /app/.local_object_store
          SERVICE_ROLE: dsh
          DSH_WORKER_PAT: ${DSH_WORKER_PAT}
          DSH_WORKER_SECRET: ${DSH_WORKER_SECRET}
        depends_on:
          db:
            condition: service_healthy
          redis:
            condition: service_healthy
          migrations:
            condition: service_completed_successfully
        healthcheck:
          test: ["CMD", "python", "-m", "app.dsh_worker.health"]
          interval: 30s
          timeout: 10s
          retries: 3
          start_period: 60s
        restart: unless-stopped
    ```
- `docker/docker-compose.deps-only.yml` (if used for local tests): optionally start a `dsh_worker` container or let the dev agent run it manually.

### Task 6 — Tests

- Unit:
  - `tests/unit/dsh_worker/test_consumer.py` — mocked Redis `xreadgroup`, `xautoclaim`, `xack`, `xclaim` idle reset, DLQ.
  - `tests/unit/dsh_worker/test_lock.py` — Redis lock TTL/renewal.
  - `tests/unit/dsh_worker/test_supervisor.py` — deterministic domain-only batch from fake `ResearchOutput`.
  - `tests/unit/routes/test_dsh_worker_routes.py` — dispatch, status, checkpoint auth.
- Integration:
  - `tests/integration/dsh_worker/test_crash_resumption.py` — real Redis + Postgres, kill worker mid-mission, assert `XAUTOCLAIM` resumes from `checkpoint`.
  - `tests/integration/dsh_worker/test_dlq.py` — force three failures, assert message lands in `nowing:dsh:dlq` and `dsh_missions.status='dlq'`.
  - `tests/integration/dsh_worker/test_end_to_end.py` — dispatch `noop` mission, assert worker completes and XACKs.

---

## API Contract

### REST

#### `POST /api/v1/workspaces/{workspace_id}/dsh/missions`

**Request body** (`DshMissionRequest`):
```json
{
  "mission_type": "deep_lead_research",
  "payload": {
    "query": "Công ty AI tại TP HCM",
    "mode": "balanced",
    "sources": ["web", "academic"],
    "max_leads": 50
  }
}
```

**Response** (`DshMissionResponse`):
```json
{
  "mission_id": "01912a...",
  "workspace_id": 42,
  "status": "pending",
  "phase": "crawl",
  "progress_percent": 0
}
```

#### `GET /api/v1/workspaces/{workspace_id}/dsh/missions/{mission_id}`

**Response**:
```json
{
  "mission_id": "01912a...",
  "workspace_id": 42,
  "mission_type": "deep_lead_research",
  "status": "running",
  "phase": "extraction",
  "progress_percent": 66,
  "current_subtask_id": "ingest-1",
  "retry_count": 0,
  "created_at": "2026-08-18T...",
  "updated_at": "2026-08-18T..."
}
```

#### `PATCH /v1/dsh/missions/{mission_id}/checkpoint` (internal, sidecar-only)

**Headers:** `Authorization: Bearer {DSH_WORKER_PAT}` **and** `X-Dsh-Worker-Secret: {DSH_WORKER_SECRET}`. The gateway validates the secret with `hmac.compare_digest` against `config.DSH_WORKER_SECRET`; the workspace-membership check may be bypassed only on this internal route.

**Request body** (`DshCheckpointRequest`):
```json
{
  "status": "running",
  "phase": "extraction",
  "progress_percent": 66,
  "current_subtask_id": "ingest-1",
  "checkpoint": {
    "phase": "extraction",
    "subtasks": [
      {"id": "research-1", "type": "chainlens.research", "status": "completed", "run_id": "run_..."},
      {"id": "extract-1", "type": "lead_batch", "status": "running", "lead_ids": []}
    ]
  },
  "retry_count": 0,
  "error": null
}
```

**Response:** `200 OK` with the updated mission summary.

### Redis Streams

**Stream `nowing:dsh:tasks`** (produced by dispatch route, consumed by worker):

Field/value payload:
```
mission_id: <uuid>
workspace_id: 42
user_id: <uuid>
mission_type: deep_lead_research
payload_json: <json-string>
created_at: 2026-08-18T...
attempt: 1
```

**Consumer group:** `dsh_workers`  
**Consumer name format:** `{hostname}-{pid}-{uuid}`

**Stream `nowing:dsh:dlq`** (produced by worker on 3rd failure):

```
original_id: <stream-message-id>
mission_id: <uuid>
payload_json: <json-string>
error_json: <json-string>
failed_at: 2026-08-18T...
attempt: 3
```

**Lock key:** `nowing:dsh:lock:{mission_id}` with 90s TTL.  
**Heartbeat key:** `nowing:dsh:worker:{consumer_name}:heartbeat` with 60s TTL (optional, used by healthcheck).

---

## Files to Create / Modify

### New files

- `nowing_backend/app/dsh_worker/__init__.py`
- `nowing_backend/app/dsh_worker/main.py`
- `nowing_backend/app/dsh_worker/config.py`
- `nowing_backend/app/dsh_worker/consumer.py`
- `nowing_backend/app/dsh_worker/client.py`
- `nowing_backend/app/dsh_worker/supervisor.py`
- `nowing_backend/app/dsh_worker/lock.py`
- `nowing_backend/app/dsh_worker/health.py`
- `nowing_backend/app/routes/dsh_worker_routes.py`
- `nowing_backend/app/services/dsh_mission_service.py`
- `nowing_backend/app/schemas/dsh.py`
- `nowing_backend/alembic/versions/<revision>_add_dsh_mission_tables.py`
- `nowing_backend/tests/unit/dsh_worker/test_consumer.py`
- `nowing_backend/tests/unit/dsh_worker/test_lock.py`
- `nowing_backend/tests/unit/dsh_worker/test_supervisor.py`
- `nowing_backend/tests/unit/routes/test_dsh_worker_routes.py`
- `nowing_backend/tests/integration/dsh_worker/test_crash_resumption.py`
- `nowing_backend/tests/integration/dsh_worker/test_dlq.py`
- `nowing_backend/tests/integration/dsh_worker/test_end_to_end.py`

### Files to modify

- `nowing_backend/app/db.py` — add `DshMission` model (and optionally `DshMissionSubtask`).
- `nowing_backend/app/config/__init__.py` — add `DSH_*` config constants.
- `nowing_backend/app/zero_publication.py` — add `DSH_MISSION_COLS` and `ZERO_PUBLICATION["dsh_missions"]`.
- `nowing_backend/app/app.py` — mount `dsh_worker_router`.
- `nowing_backend/app/db.py` — add `DSH_MISSIONS_WRITE`/`DSH_MISSIONS_READ` to the `Permission` enum (code-only; no migration).
- `nowing_backend/scripts/docker/entrypoint.sh` — add `dsh` service role.
- `nowing_backend/Dockerfile` — install `tini`, set as PID 1.
- `docker/postgresql.conf` — add `max_slot_wal_keep_size` and `wal_keep_size`.
- `docker/docker-compose.yml` — add `dsh_worker` service.

---

## Tasks / Subtasks

- [ ] **Task 1:** Create `dsh_missions` schema, migration, and `zero_publication` entry (PII-safe columns only).
- [ ] **Task 2:** Add `DSH_*` configuration constants to `app/config/__init__.py`.
- [ ] **Task 3:** Implement public dispatch and internal checkpoint REST routes with service-token auth.
- [ ] **Task 4:** Implement `app/dsh_worker/consumer.py` with `XREADGROUP`, `XCLAIM` heartbeat, `XAUTOCLAIM`, and `XACK`/DLQ logic.
- [ ] **Task 5:** Implement `app/dsh_worker/client.py` (httxy, 60s timeout, PAT/secret auth) wrapping `batch_ingest_leads` and scraper/ChainLens endpoints.
- [ ] **Task 6:** Implement `app/dsh_worker/supervisor.py` with a pluggable `DshMissionExecutor`; ship the default `DeepLeadResearchExecutor` that runs `chainlens.research` → deterministic domain-only lead batch → checkpoint loop.
- [ ] **Task 7:** Wire `SERVICE_ROLE=dsh` into `entrypoint.sh`, install `tini`, and add the `dsh_worker` service to `docker-compose.yml`.
- [ ] **Task 8:** Add `max_slot_wal_keep_size = 4096MB` and `wal_keep_size = 1024MB` to `docker/postgresql.conf`.
- [ ] **Task 9:** Write unit + integration tests for consumer, lock, crash resumption, DLQ, and end-to-end `noop` mission.
- [ ] **Task 10:** Run verification commands (ruff, pytest, docker-compose healthcheck) and mark story done.

---

### Review Findings

Code review completed 2026-08-17. Findings from Blind Hunter, Edge Case Hunter and Acceptance Auditor.

#### decision_needed

- [ ] [Review][Decision] DSH worker performs direct PostgreSQL reads and writes — `_handle_message` and `_maybe_retry_or_dlq` use `async_session_maker()`, `DshMission` and `DshMissionService` to load, update and DLQ the mission row, violating AD-102 rule 2 that the sidecar must interact with Nowing exclusively through authenticated interfaces. `location: nowing_backend/app/tasks/dsh_worker.py:458-608, nowing_backend/app/routes/dsh_routes.py:112-142`
- [ ] [Review][Decision] XAUTOCLAIM reclaims idle messages before verifying the live lock — `_autoclaim` transfers ownership of idle messages to the new consumer and only afterwards `_handle_message` checks `nowing:dsh:lock:{mission_id}`, so a message whose original worker is still alive can be claimed and processed twice. `location: nowing_backend/app/tasks/dsh_worker.py:420-442,665-667`
- [ ] [Review][Decision] DLQ stream grows unbounded — `nowing:dsh:dlq` is appended to on the 3rd failure with no `MAXLEN`, no consumer and no trim policy, so it will consume Redis memory in production. `location: nowing_backend/app/tasks/dsh_worker.py:582-595`

#### patch

- [ ] [Review][Patch] ChainLens research called with `?mode=sync` and result not polled — causes the worker to receive a 202 and complete with no leads. `location: nowing_backend/app/tasks/dsh_worker.py:76-84`
- [ ] [Review][Patch] DLQ write is not followed by XACK — after `retry_count` reaches `max_retries`, `_maybe_retry_or_dlq` updates the mission to `dlq` and writes to the DLQ stream but returns `False`, so the original message is reprocessed indefinitely. `location: nowing_backend/app/tasks/dsh_worker.py:569-608,675-681`
- [ ] [Review][Patch] Redis lock renewal does not verify ownership — `_try_set_lock` uses `SET NX EX` and `_renew_lock_and_idle` calls `EXPIRE` without checking the stored value, so after the lock expires another worker can acquire it while the old worker still refreshes the TTL. `location: nowing_backend/app/tasks/dsh_worker.py:386-418`
- [ ] [Review][Patch] Global PAT can access any mission checkpoint — internal GET and PATCH routes only enforce workspace scoping when `auth.pat.workspace_id is not None`; a global PAT that also knows `X-Dsh-Worker-Secret` can read or update any mission. `location: nowing_backend/app/routes/dsh_routes.py:134-141,168-175`
- [ ] [Review][Patch] Heartbeat failure does not cancel the executor — if `_renew_lock_and_idle` fails, `_heartbeat_loop` breaks but the executor task keeps running while the lock will expire. `location: nowing_backend/app/tasks/dsh_worker.py:512-554,610-621`
- [ ] [Review][Patch] Lock TTL has no margin over heartbeat interval — `DSH_LOCK_TTL_SECONDS=90` with `DSH_HEARTBEAT_INTERVAL_SECONDS=30` is exactly 3x and is not validated against `DSH_XAUTOCLAIM_MIN_IDLE_MS`; misconfiguration can let the lock expire before renewal. `location: nowing_backend/app/config/__init__.py:669-674, nowing_backend/app/tasks/dsh_worker.py:610-621`
- [ ] [Review][Patch] Worker starts with empty DSH credentials and fails silently — `DSH_WORKER_PAT` and `DSH_WORKER_SECRET` default to empty strings; the worker starts and every authenticated REST call fails instead of failing fast. `location: nowing_backend/app/config/__init__.py:667-668, nowing_backend/app/tasks/dsh_worker.py:623-628`
- [ ] [Review][Patch] No exponential backoff on Redis errors — `_read_new_messages` catches Redis exceptions and returns `[]`, then `run` only sleeps 1s, hammering Redis during outages. `location: nowing_backend/app/tasks/dsh_worker.py:630-652,670-681`
- [ ] [Review][Patch] Checkpoint status is not validated — `DshMissionCheckpointUpdate.status` is a plain `str | None` and `DshMissionService.update_checkpoint` writes it directly; invalid values hit the DB `CHECK` constraint and disallowed transitions are possible. `location: nowing_backend/app/schemas/dsh.py:31, nowing_backend/app/services/dsh_mission_service.py:103-105`
- [ ] [Review][Patch] Mission payload and type are not validated or dispatched — `DshMissionRequest.payload` is an untyped dict and `mission_type` is a plain `str`; the worker always runs `DeepLeadResearchExecutor` regardless of type. `location: nowing_backend/app/schemas/dsh.py:9-21, nowing_backend/app/tasks/dsh_worker.py:137-163`
- [ ] [Review][Patch] `DshMissionResponse` includes `user_id`, violating the PII-safe column list — `user_id` is not in `DSH_MISSION_COLS` and both public and internal endpoints return it. `location: nowing_backend/app/schemas/dsh.py:38-53, nowing_backend/app/routes/dsh_routes.py:109,142,190`
- [ ] [Review][Patch] Public mission status GET route is missing — the spec requires `GET /api/v1/workspaces/{workspace_id}/dsh/missions/{mission_id}`; only `POST` is on the public router. `location: nowing_backend/app/routes/dsh_routes.py:60-109,112-142`
- [ ] [Review][Patch] No payload size validation before XADD — `DshMissionService.publish_to_stream` calls `json.dumps(mission.payload)` and `xadd` without a size limit; an oversized payload can fail Redis or approach the 1GB PostgreSQL JSONB limit. `location: nowing_backend/app/services/dsh_mission_service.py:116-128, nowing_backend/app/db.py:3797-3808`
- [ ] [Review][Patch] Stream payload missing `user_id` and `attempt` — `publish_to_stream` only writes `mission_id`, `workspace_id`, `mission_type` and `payload`, breaking the API contract. `location: nowing_backend/app/services/dsh_mission_service.py:119-126`
- [ ] [Review][Patch] DLQ message uses `mission.id` and omits `attempt` — the DLQ `original_id` should be the original stream `msg_id` and `attempt` should be included for tracing/resubmission. `location: nowing_backend/app/tasks/dsh_worker.py:583-590`
- [ ] [Review][Patch] Healthcheck only verifies the worker process is running — `docker-compose` healthcheck is `ps aux | grep -q 'dsh_worker'` and does not check Redis or DB connectivity. `location: docker/docker-compose.yml:262-263`
- [ ] [Review][Patch] Worker has no SIGTERM handler and runs in the background — `run_dsh_worker` starts `DshWorker().run()` with no signal handlers and the entrypoint launches it with `&`, so container stop kills the process without finishing the current checkpoint or cleanly releasing the lock. `location: nowing_backend/app/tasks/dsh_worker.py:683-699, nowing_backend/scripts/docker/entrypoint.sh:134-138`
- [ ] [Review][Patch] Extracted leads may fail batch-ingest validation — `_source_to_lead` may produce a lead with `phone`, `email` and `domain` all `None`; the batch endpoint's `_reject_degenerate` validator then rejects the whole batch with 422. `location: nowing_backend/app/tasks/dsh_worker.py:270-322`
- [ ] [Review][Patch] Worker does not classify retryable vs non-retryable REST errors — `DshRestClient` raises on `402`, `404`, `422` and `5xx` without distinguishing billing, not-found, validation and transient errors, so an empty wallet or bad payload causes full mission retries. `location: nowing_backend/app/tasks/dsh_worker.py:59-84,86-107`
- [ ] [Review][Patch] Checkpoint updates are not idempotent — `DshMissionService.update_checkpoint` overwrites `mission.checkpoint` without an `updated_at` or version check, so a split-brain scenario can clobber the checkpoint. `location: nowing_backend/app/services/dsh_mission_service.py:80-114`
- [ ] [Review][Patch] Checkpoint JSONB has no schema version — the default checkpoint and all updates lack a version field, so future schema changes will break resumption of in-flight missions. `location: nowing_backend/app/db.py:3803-3808, nowing_backend/app/services/dsh_mission_service.py:45-46`
- [ ] [Review][Patch] DSH internal base URL is not exposed through config — `_build_default_executor` reads `DSH_INTERNAL_API_URL` directly from `os.getenv` and the env name differs from the spec's `DSH_INTERNAL_BASE_URL`. `location: nowing_backend/app/tasks/dsh_worker.py:626, nowing_backend/app/config/__init__.py:666-681`
- [ ] [Review][Patch] XGROUP CREATE uses `id='0'` for new consumer group — creates the group from the beginning of the stream; if the stream already has unconsumed messages the worker will reprocess them. `location: nowing_backend/app/tasks/dsh_worker.py:372-384`

#### defer

- [x] [Review][Defer] Missing structured mission-lifecycle observability — functional logging exists; structured logs and metrics are a production-hardening follow-up, not a 26.2 launch blocker. `location: nowing_backend/app/tasks/dsh_worker.py:1-699` — deferred, not in ACs.

#### dismissed

- [x] [Review][Dismiss] Ingestion is not skipped for an empty leads list — `DeepLeadResearchExecutor.run` already guards with `if leads:`. Dismissed as false positive. `location: nowing_backend/app/tasks/dsh_worker.py:270-272`
- [x] [Review][Dismiss] Workspace membership check intentionally bypassed on checkpoint route — design decision #1 explicitly says the workspace-membership check may be bypassed on the internal route; the scoping check that remains is sufficient. `location: nowing_backend/app/routes/dsh_routes.py:168-175`
- [x] [Review][Dismiss] DLQ message body includes checkpoint — the DLQ `xadd` payload does not contain `checkpoint`, so sensitive checkpoint data is not written to the DLQ. `location: nowing_backend/app/tasks/dsh_worker.py:583-590`
- [x] [Review][Dismiss] XREADGROUP block missing a 60s hard timeout — `XREADGROUP` is configured to block for 5000ms as required by AC-1.2; the 60s timeout is for synchronous REST round-trips. `location: nowing_backend/app/tasks/dsh_worker.py:630-642`
- [x] [Review][Dismiss] Heartbeat interval drifts by lock-renewal time — the drift is negligible compared to the 90s lock TTL and does not materially affect safety. `location: nowing_backend/app/tasks/dsh_worker.py:610-621`
- [x] [Review][Dismiss] `dsh_worker` service omits `extra_hosts` — the worker talks to backend and redis by Docker service DNS, not `host.docker.internal`, so `extra_hosts` is unnecessary. `location: docker/docker-compose.yml:240-267`

---

## Dev Notes & ATDD Red-Phase Test Scaffolds

### Pattern: Reuse Before You Build

| Concern | Reuse First | Avoid |
|---------|-------------|-------|
| Redis client | `app/redis_client.py:get_redis_client()` | New connection pool per module |
| Stream consumer loop | `app/tasks/social_stream_worker.py:500–614` | Inventing a new streaming primitive |
| XAUTOCLAIM crash resumption (informed by XPENDING/XCLAIM pattern) | `app/tasks/lead_scrapers.py:168–214` | Rewriting `XAUTOCLAIM` wrapper from scratch |
| Background run lifecycle | `app/capabilities/core/async_runner.py:49–96` | Calling scrapers synchronously inside the worker |
| REST client | `httpx.AsyncClient` (already in `pyproject.toml`) | Importing `nowing_mcp` into `nowing_backend` |
| Auth | `PersonalAccessToken` / `get_auth_context` | A new token table |
| Bulk lead ingest | `POST /api/v1/workspaces/{id}/leads/batch-ingest` | Direct `leads` table writes from sidecar |
| Research capability | `POST /workspaces/{id}/scrapers/chainlens/research?mode=async` | Reimplementing ChainLens call |

### Red-Phase Test Scaffolds (write these first, expect them to fail)

1. **Consumer loop test** (unit):
   ```python
   async def test_worker_consumes_and_xacks_once():
       # arrange: xadd a noop mission, mock all REST calls
       # act: run worker for one iteration
       # assert: xreadgroup called, mission completed, xack called exactly once
   ```
2. **XAUTOCLAIM resumption test** (integration, needs Redis + Postgres):
   ```python
   async def test_worker_recovers_via_xautoclaim_and_resumes_checkpoint():
       # arrange: insert dsh_missions row, xadd, start worker, kill worker after first checkpoint
       # act: start second worker, wait for xautoclaim
       # assert: second worker reads checkpoint.phase == first worker's last write, mission completes
   ```
3. **DLQ test** (integration):
   ```python
   async def test_three_failures_move_to_dlq():
       # arrange: xadd mission whose executor always raises
       # act: run worker through 3 attempts
       # assert: xack, message in nowing:dsh:dlq, dsh_missions.status == 'dlq'
   ```
4. **Container smoke test** (shell):
   ```bash
   docker compose -f docker/docker-compose.yml run --rm dsh_worker python -m app.dsh_worker.health
   ```
   Expected exit 0 and `nowing:dsh:lock:healthcheck` key set.

### Critical Open Questions

1. **PAT vs service-token for checkpoint:** Decide between Option A/B in `CRITICAL DESIGN DECISIONS` before opening `app/routes/dsh_worker_routes.py`.
2. **Subtask state location:** For the first implementation, `checkpoint` JSONB is acceptable; a separate `dsh_mission_subtasks` table is the cleaner long-term target. Do not normalize prematurely unless the dev agent is comfortable with the extra migration and route surface.
3. **Rate limiting for `batch_ingest_leads` from the sidecar:** The route currently has `@limiter.limit("30/minute")` keyed by `get_real_client_ip`. A mission may call batch ingest more than 30 times per minute. Either exempt the service user (not yet supported) or change the key to `f"lead_batch:{workspace_id}"` with a higher cap. Resolve before integration tests.
4. **Mission extraction scope (26.2 vs 26.3):** Do not build an LLM-based extractor in 26.2. The default `DeepLeadResearchExecutor` should emit a deterministic, PII-safe, domain-only lead batch from each `ResearchOutput.sources[].url`, then hand real phone/email extraction to Story 26.3.
5. **Mission cancel:** Not in the core AC. A simple `POST /api/v1/workspaces/{id}/dsh/missions/{mid}/cancel` that sets `status='cancelled'` and the worker checks `GET mission` before each sub-task is a good follow-up if time allows.

---

## Verification Commands

From `nowing_backend/`:

```bash
# Lint new modules
ruff check app/dsh_worker app/routes/dsh_worker_routes.py app/services/dsh_mission_service.py app/schemas/dsh.py app/db.py app/zero_publication.py
echo "---"

# Unit tests
uv run pytest tests/unit/dsh_worker tests/unit/routes/test_dsh_worker_routes.py -q

echo "---"
# Integration tests (requires Postgres + Redis, see AGENTS.md)
docker compose -f ../docker/docker-compose.deps-only.yml up -d db redis
uv run alembic upgrade head
uv run python -c "from sqlalchemy import create_engine; from app.zero_publication import ensure_publication; e=create_engine('postgresql+psycopg2://postgres:postgres@localhost:5432/nowing'); e.connect().run_sync(ensure_publication)"
uv run pytest tests/integration/dsh_worker -m integration -q

echo "---"
# Docker smoke (after Dockerfile/compose changes)
docker compose -f ../docker/docker-compose.yml build backend
docker compose -f ../docker/docker-compose.yml run --rm dsh_worker python -m app.dsh_worker.health

echo "---"
# WAL protection check
grep -E 'max_slot_wal_keep_size|wal_keep_size' ../docker/postgresql.conf

echo "---"
# tini check
docker compose -f ../docker/docker-compose.yml run --rm dsh_worker ps -p 1 -o comm=
```

---

## References

- Architecture contract: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` (AD-102, AD-106, AD-108)
- Implementation readiness: `_bmad-output/planning-artifacts/implementation-readiness-report-2026-08-17-epic26.md`
- Story 26.1 artifact: `_bmad-output/implementation-artifacts/26-1-fastmcp-batch-ingest-and-stateless-chainlens-pipeline.md`
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml`

---

## Story Completion Status

**Status:** `ready-for-dev`

Created from baseline commit `699e74dfe` on 2026-08-18. This story file is the canonical input for the dev agent (Amelia / `bmad-agent-dev`). The next step is for the dev agent to resolve the four critical design decisions at the top of this file, then proceed to `bmad-nowing-test-first-atdd`.

## Challenge Log (grill-me)

### Q1 — Already implemented?
- Finding: No `dsh-worker`, `dsh_missions` table, `nowing:dsh:tasks`/`nowing:dsh:dlq` stream, `XAUTOCLAIM` resume, or mission checkpoint code exists in the backend. A repo-wide search (`dsh[-_]worker|dsh_mission|dsh:tasks|XAUTOCLAIM|XREADGROUP`) only returned matches inside this story file; `find_file_by_name **/dsh_worker*` returned nothing. However, the following existing patterns should be reused rather than invented:
  - `XGROUP CREATE` / `XREADGROUP` / `XACK` / DLQ `XADD` consumer loop: `nowing_backend/app/tasks/social_stream_worker.py:42-45, 500-614`.
  - `XPENDING` / `XCLAIM` manual reclaim: `nowing_backend/app/tasks/lead_scrapers.py:168-214`.
  - Async background run lifecycle (`asyncio.create_task`, `Run` row, progress bus, terminal events): `nowing_backend/app/capabilities/core/async_runner.py:49-96, 98-202`.
  - Shared Redis client: `nowing_backend/app/redis_client.py:15-41` (5s connect/read timeouts, 30s health check).
  - `PersonalAccessToken` / `get_auth_context`: `nowing_backend/app/db.py:3561-3629`, `nowing_backend/app/users.py:330-383`, `nowing_backend/app/utils/pat.py:36-52`.
  - Batch lead ingestion endpoint: `nowing_backend/app/routes/lead_batch_routes.py:72-114`.
  - `chainlens.research` capability and async REST door: `nowing_backend/app/capabilities/chainlens/research/definition.py:9-22`, `nowing_backend/app/capabilities/chainlens/research/executor.py:793-865`, `nowing_backend/app/capabilities/core/access/rest.py:201-369`.
  - `Run` table shape: `nowing_backend/app/db.py:3630-3712`.
- Verdict: no duplicate found. Proceed.

### Q2 — Simpler alternative?
- Alternatives considered:
  - `app/capabilities/core/async_runner.py:83-95`: spawns `asyncio.create_task` inside the FastAPI process, persists a `Run` row, but is process-local. On API pod crash the task dies; there is no per-subtask checkpoint resumption across workers and it cannot satisfy AC-2 (`XAUTOCLAIM` + Redis Streams) or the 1–8h mission lifetime.
  - Celery (`nowing_backend/app/celery_app.py:236-247`): has `task_time_limit=28800` (8h), `task_acks_late=True`, `reject_on_worker_lost=True`, but it retries the *whole* task on worker loss and does not expose `XREADGROUP`/`XAUTOCLAIM` consumer groups or a per-subtask PostgreSQL checkpoint. It also shares queues with fast tasks and would block the `connectors` queue.
  - Existing `Run` table (`nowing_backend/app/db.py:3630-3712`): stores capability-level `status`, `progress`, `error` and `memory_extraction_status`, but has no mission `phase`, `checkpoint` JSONB, `retry_count`, or `dlq` state, and it does not act as a Redis Streams consumer.
- Verdict: No acceptable simpler alternative; the Redis Streams sidecar is required by AD-102/AD-106 and the ACs. Proceed.

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] Boundary: Mission `payload` or `checkpoint` JSONB approaches PostgreSQL's 1GB `jsonb` limit (`app/db.py` proposed `payload`/`checkpoint` JSONB columns). Sidecar must chunk/stream or reject oversized payloads before `XADD`.
- [ ] Boundary: `progress_percent` not bounded; the proposed `dsh_missions` schema has `progress_percent` as an unvalidated `Integer` (story plan). Supervisor could write `>100` or `<0`; add a `CheckConstraint` (`0 <= progress_percent <= 100`) or clamp in code.
- [ ] Null/empty: Empty `payload_json` or `payload={}`. `DshMissionRequest` schema is not yet defined; the route must either reject or the supervisor must handle `payload.query` missing/blank.
- [ ] Null/empty: `ResearchOutput.sources` is empty. For the deterministic domain-only batch executor, zero sources means `batch_ingest_leads` with `leads: []` violates `min_length=1` (`app/routes/lead_batch_routes.py:49`). The worker must skip the ingestion sub-task rather than call the endpoint with an empty batch.
- [ ] Null/empty: 0 sub-tasks or all sub-tasks fail. The checkpoint schema starts with `subtasks: []`; if no subtask completes the mission should terminal as `error`, not `success`, and the `XACK` should still happen.
- [ ] Null/empty: `batch_ingest_leads` returns `ingested_count=0` and `failed_count=0` (all blacklisted/degenerate). The worker must not crash on `LeadItemValidationError` (`app/services/lead_batch_service.py:35-44`) and should record the subtask as `failed`/`skipped`.
- [ ] Null/empty: `ResearchOutput.cost_dollars` missing or malformed. The executor already tolerates this (`app/capabilities/chainlens/research/executor.py:525-535`), but billing falls back to `CHAINLENS_QUERY_MICROS_PER_CALL` (`app/capabilities/core/billing.py:478-487`). The worker must handle a returned `costDollars` of `null`/`0`/non-finite without treating it as an error.
- [ ] Concurrent: Worker heartbeat lost for 90s then resumes. The per-mission Redis lock TTL is 90s and `XAUTOCLAIM` min-idle is 60s; if the old worker renews just as the new one claims, both can hold the same stream message. Need idempotent sub-task execution and final `XACK` (Redis `XACK` is idempotent).
- [ ] Concurrent: `XAUTOCLAIM` returns a message whose worker is still alive because of heartbeat delay / clock skew. The spec's `nowing:dsh:lock:{mission_id}` check helps, but the lock and PEL idle time are independent; add a `last_heartbeat` field and refuse to resume if `lock` exists and `idle_time < 90s`.
- [ ] Concurrent: Two workers claim the same message but the lock is held. If lock acquisition is not `SET NX EX`-atomic, both can pass. The consumer must `SET` with `NX` and `PX 90000`, then `XCLAIM ... IDLE 0`, and skip on lock failure.
- [ ] Concurrent: Mission cancelled while a sub-task is running. There is no `cancel` route in the ACs and the supervisor does not re-read `dsh_missions.status` between sub-tasks; a long ChainLens call may continue after a cancel.
- [ ] State/schema: Checkpoint schema migration / unknown old keys. `checkpoint` is free-form JSONB with no `version` field (story plan). Resuming after a code upgrade with a changed `subtasks` shape can break resumption.
- [ ] State/schema: `dsh_missions` `status` vocabulary includes `pending`, `running`, `success`, `error`, `cancelled`, `dlq` (story plan), but no `CHECK` constraint on the column is proposed; invalid values can be written.
- [ ] State/schema: `Permission` enum currently has no `DSH_MISSIONS_WRITE` or `DSH_MISSIONS_READ` (`app/db.py:304-423`). `check_permission` also requires a `WorkspaceMembership` row (`app/utils/rbac.py:153-170`), which a service account may not have. Option A/B in the story must be resolved before coding the `PATCH /v1/dsh/missions/{id}/checkpoint` route.
- [ ] State/schema: Sidecar service-account PAT can expire or be revoked mid-mission. `PersonalAccessToken.expires_at` is nullable and `resolve_pat` only checks expiry (`app/utils/pat.py:40-52`); `PATCH checkpoint` can start returning `401`/`403` 1–8 hours after dispatch.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] Redis: Redis unavailable / partial. `get_redis_client()` has 5s connect and socket timeouts (`nowing_backend/app/redis_client.py:35-36`). Worker `xreadgroup`/`xautoclaim` will raise; the main loop must catch, back-off, and retry without crashing.
- [ ] Redis: `nowing:dsh:tasks` stream is `XTRIM`-ed or the consumer group is reset/destroyed while a mission is in the PEL. `XAUTOCLAIM` returns nothing even though `dsh_missions` has a `running` row. Need a periodic DB reconciliation loop that re-`XADD`s stale `running` missions older than a threshold.
- [ ] Redis: `XREADGROUP` block returns empty repeatedly (no new missions). The AC specifies `block=5000ms` but no back-off or max idle iterations; without a sleep the worker can spin and hammer Redis.
- [ ] Redis: Double `XACK` / duplicate message after split-brain. `XACK` is idempotent on the same id, but if a second worker re-`XADD`s the same mission to DLQ, duplicate DLQ entries can grow. Add `original_id` dedup in DLQ.
- [ ] Postgres: Postgres unavailable or connection pool exhausted. `engine` is configured with `pool_size=30`, `max_overflow=150`, `pool_timeout=30` (`nowing_backend/app/db.py:3846-3853`). A checkpoint update that fails means crash resumption is broken; worker must fail the mission rather than `XACK`.
- [ ] Postgres: `dsh_missions` row is in `running` but the stream message is gone. The worker must detect this, set `status='error'` and `XACK` only when it actually owns a PEL entry; otherwise the mission orphan loop should reclaim it.
- [ ] ChainLens/batch ingest/scraper: ChainLens API timeout / 5xx / `costDollars` missing. `_call_chainlens` uses `config.CHAINLENS_REQUEST_TIMEOUT_SECONDS` (default 300s, `app/config/__init__.py:1114-1116`) and returns `status='engine_unavailable'` for 5xx/400 (`app/capabilities/chainlens/research/executor.py:846-862`). Sidecar must treat partial output as a resume point, not a mission failure.
- [ ] ChainLens/batch ingest/scraper: `POST /workspaces/{id}/scrapers/chainlens/research?mode=async` returns `402` from `gate_capability` (`app/capabilities/core/billing.py:204-225`) when the workspace wallet is empty. The sidecar must not retry a 402 indefinitely; it should mark the subtask `failed` and eventually DLQ.
- [ ] ChainLens/batch ingest/scraper: `batch_ingest_leads` returns `429` (rate limit), `422` (`LeadItemValidationError`), or `5xx`. The route has `@limiter.limit("30/minute")` keyed by `get_real_client_ip` (`app/routes/lead_batch_routes.py:77`, `app/rate_limiter.py:16-39`). A long mission may exceed this, especially if the sidecar appears from a single container IP. The sidecar must back off on `429` and the route may need a workspace-scoped exemption/key.
- [ ] ChainLens/batch ingest/scraper: Scraper returns empty or malformed. `chainlens_internal.py:198-239` returns `no_items`/`no_chunks` with `ingested_count=0` instead of raising. The sidecar must decide whether this is a retry-able failure or a terminal `success` with no output.
- [ ] ChainLens/batch ingest/scraper: Embedding model returns wrong-dimension vectors. `ChainLensChunk.embedding = Vector(1536)` (`app/db.py:1678-1681`) while other tables use `Vector(config.embedding_model_instance.dimension)`. If a gap-fill ingest path writes a 1024-dim vector, the insert fails.
- [ ] Auth/credit: `PATCH /v1/dsh/missions/{id}/checkpoint` returns `401`/`403`/`404`. PAT workspace-membership check may fail for the service account (`app/utils/rbac.py:153-170` requires `WorkspaceMembership`), the `X-Dsh-Worker-Secret` may mismatch, or the mission row may be deleted. The worker should stop and let DLQ logic handle it, not crash.
- [ ] Container/shutdown: Worker container receives `SIGTERM`. `nowing_backend/Dockerfile` does not install `tini` and `docker/postgresql.conf` lacks `max_slot_wal_keep_size`/`wal_keep_size` (story file confirms). `entrypoint.sh` only traps `SIGTERM`/`SIGINT` for `api`/`worker`/`beat`/`all` cases (`nowing_backend/scripts/docker/entrypoint.sh:46-57, 156-184`); a new `dsh` case must be added and `tini` must be PID 1 to avoid zombie children and ensure clean shutdown.
- [ ] Container/shutdown: WAL segment removed before replica catches up. `docker/postgresql.conf` currently has `wal_level=logical`, `max_replication_slots=10`, but no `max_slot_wal_keep_size`/`wal_keep_size` (`docker/postgresql.conf:1-20`). AD-108 requires `max_slot_wal_keep_size = 4096MB` and `wal_keep_size = 1024MB`.
- [ ] Container/shutdown: DLQ after 3 retries — who consumes `nowing:dsh:dlq`? The AC only specifies writing to the DLQ. There is no consumer, no `MAXLEN`, and no retention policy; the DLQ stream will grow unbounded unless a sweep/alert is added.

### Triage
- Q1: **Clean — proceed.** No duplicate `dsh-worker` implementation; existing Redis Streams / async runner / PAT / batch lead patterns are reusable and explicitly referenced in the story.
- Q2: **Clean — proceed.** `async_runner`, Celery, and the `Run` table do not meet AC-1/AC-2 (Redis Streams, `XAUTOCLAIM`, per-subtask checkpoint, DLQ). The sidecar is architecture-mandated.
- Q3: **Non-critical findings** — route to dev agent for schema/test design. The `progress_percent` bounds, payload size, empty-source batch, rate-limit key, and checkpoint schema versioning are test skeleton items.
- Q4: **Non-critical findings** — route to dev agent for resilience design. The Redis/Postgres reconciliation, DLQ consumer, `tini`/WAL gaps, and 429/402 handling are test skeleton items.

## Resolved Design Decisions

The following decisions are locked before dev to avoid mid-implementation drift:

1. **Sidecar auth model — Option A (recommended):** The sidecar uses a workspace-scoped `PersonalAccessToken` with `token_kind='service_account'`. The same PAT is supplied as `DSH_WORKER_PAT`. The public dispatch route `POST /api/v1/workspaces/{workspace_id}/dsh/missions` is gated by `LEADS_WRITE` (or `DSH_MISSIONS_WRITE`) through the normal `check_permission` path. The internal `PATCH /v1/dsh/missions/{mission_id}/checkpoint` route is gated by the `X-Dsh-Worker-Secret` header compared to `config.DSH_WORKER_SECRET` with `hmac.compare_digest`; workspace-membership is not required on that one route, but the PAT's `workspace_id` must match the mission's `workspace_id`.

2. **One image:** `dsh-worker` runs from the existing `nowing_backend` image with `SERVICE_ROLE=dsh`. No new package is introduced.

3. **Mission model:** New `dsh_missions` table in `app/db.py` with `id` (UUID PK), `workspace_id`, `user_id`, `mission_type`, `status`, `phase`, `progress_percent` (clamped 0–100), `current_subtask_id`, `retry_count`, `started_at`, `completed_at`, `payload` (JSONB, private), `checkpoint` (JSONB, private). Only PII-safe columns (`id`, `workspace_id`, `mission_type`, `status`, `phase`, `progress_percent`, `current_subtask_id`, `created_at`, `updated_at`) are published to `zero_publication`.

4. **XAUTOCLAIM idempotent lock:** Each mission is a single Redis Stream message in `nowing:dsh:tasks`. The active worker owns `nowing:dsh:lock:{mission_id}` with a 90s TTL, renewed every `DSH_HEARTBEAT_INTERVAL_SECONDS` (default 30s) together with `XCLAIM ... IDLE 0` to reset PEL idle time. `XAUTOCLAIM` is run with `MINIDLE 60000` on startup and after idle loops. A second worker will skip a message whose lock is still held.
