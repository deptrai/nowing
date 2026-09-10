---
story_key: 30-9-technical-debt-retirement-and-system-hardening
status: in-progress
epic: 30
story: 9
---

# Story 30.9: Technical Debt Retirement & System Hardening

**Status:** `in-progress`  
**Epic:** Epic 30 — Technical Debt  
**Consolidation Note:** Consolidates 5 micro-scope tech debt stories (30.1, 30.3, 30.4, 30.6, 30.7) into a unified reliability and hardening package.  
**Governed by:** Architecture Spine, Reliability Standards, Celery/Redis Async Execution Rules.

---

## Story

As a **system operator and developer**,  
I want **concurrency locks, atomic preference merges, storage reconciliation, and hardened test/diagnostic routines**,  
so that **the platform avoids duplicate execution runs, race conditions, storage quota drifts, and unhandled diagnostic timeouts**.

---

## Acceptance Criteria

### AC-1: Automation Run Idempotency & Dedup Lock (from Story 30.1)
**Given** a user or client triggers `POST /automations/{id}/run`,  
**When** duplicate requests are sent concurrently (e.g., rapid double-clicks or network retries with an `Idempotency-Key` header),  
**Then**:
1. The endpoint accepts an optional `Idempotency-Key` header.
2. A Redis lock or dedup mechanism (`SETNX` with a 5-second TTL) ensures only one `PENDING` run is created per automation for identical requests.
3. If an identical trigger is already in progress within the window, the endpoint returns the existing `RunSummary` (HTTP 200) or HTTP 409 Conflict rather than creating duplicate runs.

### AC-2: Atomic User Notification Preferences Merge (from Story 30.4)
**Given** concurrent requests to `PATCH /users/me/notification-preferences`,  
**When** two clients update different preference channels at the same time,  
**Then**:
1. The backend locks the user row using `SELECT ... FOR UPDATE` (or atomic DB update) during the read-merge-write transaction.
2. The merge preserves non-overlapping keys across concurrent updates without in-memory race overwrites.
3. Successfully persists the merged preferences and returns the updated `UserRead`.

### AC-3: Storage Quota Reconciliation (from Story 30.3)
**Given** workspace document files stored across storage backends and database,  
**When** `sum_storage_bytes` is computed or a reconciliation task runs,  
**Then**:
1. A reconciliation service/method checks and ensures `DocumentFile.size_bytes` accurately reflects live, non-archived documents.
2. Orphaned or purged backend files no longer inflate workspace storage totals.

### AC-4: Diagnostic Script CI Robustness (from Story 30.6)
**Given** `scripts/verify_chat_image_capability.py` running in CI or smoke tests,  
**When** provider endpoints experience transient network latency,  
**Then**:
1. Both `_live_chat_image_call` and `_live_image_gen_call` pass `num_retries=1` to `litellm.acompletion` and `litellm.aimage_generation`.
2. The diagnostic script terminates cleanly without hanging indefinitely.

### AC-5: Unit Test Coverage for `test_model` (from Story 30.7)
**Given** the `test_model` function in `app/services/model_connection_service.py`,  
**When** unit tests execute,  
**Then**:
1. Unit tests in `tests/unit/services/test_model_connection_service.py` mock `litellm.acompletion`.
2. Tests assert that `num_retries=0` and `timeout=TEST_TIMEOUT_SECONDS` are passed.
3. Both successful connection tests and error branches (`VerifyResult`) are verified.

---

## Tasks / Subtasks

- [ ] Task 1: Automation Run Idempotency & Dedup Lock (AC: 1)
  - [ ] 1.1 Support `Idempotency-Key` header in `app/automations/api/run.py`.
  - [ ] 1.2 Implement Redis dedup lock in `app/automations/services/run.py` (or `launch_run`).
  - [ ] 1.3 Add unit test in `tests/unit/automations/` verifying concurrent trigger suppression.
- [ ] Task 2: Atomic Notification Preferences Merge (AC: 2)
  - [ ] 2.1 Refactor `update_current_user_notification_preferences` in `app/routes/users_routes.py` to use `SELECT ... FOR UPDATE`.
  - [ ] 2.2 Add unit/integration test verifying concurrent merge safety.
- [ ] Task 3: Storage Quota Reconciliation (AC: 3)
  - [ ] 3.1 Implement storage reconciliation in `app/services/workspace_limits.py` to reconcile deleted/archived backend files.
  - [ ] 3.2 Add test in `tests/unit/services/test_workspace_limits.py`.
- [ ] Task 4: Diagnostic Script CI Robustness (AC: 4)
  - [ ] 4.1 Update `scripts/verify_chat_image_capability.py` with `num_retries=1` for `acompletion` and `aimage_generation`.
- [ ] Task 5: Unit Test Coverage for `test_model` (AC: 5)
  - [ ] 5.1 Create `tests/unit/services/test_model_connection_service.py` testing `test_model()`.
  - [ ] 5.2 Assert kwargs and error mapping.
- [ ] Task 6: Verification & Sprint Status Update
  - [ ] 6.1 Run all unit & integration tests.
  - [ ] 6.2 Check ruff linting.

---

## Dev Notes
- Reuses existing Redis client `app/redis_client.py` for distributed locks.
- Reuses SQLAlchemy `with_for_update()` for user row locking.
