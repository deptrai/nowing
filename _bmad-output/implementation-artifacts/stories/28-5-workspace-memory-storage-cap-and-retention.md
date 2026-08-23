---
story_id: "28.5"
epic: "28"
story_key: 28-5-workspace-memory-storage-cap-and-retention
baseline_commit: 6cd320a39
status: ready-for-dev
---

# Story 28.5: Workspace Memory Storage Cap & Retention Lifecycle

Status: ready-for-dev

**Story ID:** 28.5
**Epic:** Epic 28 — Self-Host Trust, Data Portability & Cloud GA Legal Readiness
**Priority:** P1
**Source artifacts:**
- PRD: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` (OQ-3 — memory / scraped-data retention `[GAP]`)
- PRFAQ: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-PRFAQ-2026-08-21.md` (FR-97)
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/AD-28-3-retention-right-to-delete.md` (ADOPTED) · `ARCHITECTURE-SPINE.md` (`AD-DEFER-4` → RESOLVED)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 28.3 ToS / Legal Review & Retention Policy)
- Previous stories: `8-12-workspace-limits.md` (limit model), `3-7-data-retention-lifecycle-new-gap.md` (document retention pattern)

---

## Story

As a cloud workspace owner,
I want my workspace to enforce a memory count cap and apply a retention lifecycle to old memories,
So that my workspace cannot grow unbounded, my costs are predictable, and I stay compliant with scraped-source ToS.

---

## Acceptance Criteria

**AC-1:** **Given** a workspace is at or over its `max_memory_count` limit, **when** any code path calls `MemoryRepository.create_memory`, **then** the request is rejected with HTTP 403 and `{"error_code": "limit_exceeded", "limit_type": "memory"}` before any new row is inserted.

**AC-2:** **Given** a memory write matches an existing near-duplicate, **when** `MemoryRepository.create_memory` updates the existing row, **then** the limit check does not reject the write because the count does not increase.

**AC-3:** **Given** a workspace with no `max_memory_count` limit (`None`) or a self-hosted deployment, **when** a memory is created, **then** the write succeeds without a limit check.

**AC-4:** **Given** the workspace owner opens workspace settings > Data retention, **when** they configure `memory_retention_days`, `memory_auto_archive_enabled`, and `memory_retention_action` (`archive` | `delete`), **then** the settings persist and are returned by `GET /workspaces/{id}`.

**AC-5:** **Given** `memory_auto_archive_enabled=true` and a valid `memory_retention_days`, **when** the daily retention Celery task runs, **then** it only touches `Memory` rows in that workspace older than the retention window and applies `memory_retention_action`.

**AC-6:** **Given** a memory has been archived (`archived_at IS NOT NULL`), **when** `MemoryHybridSearch`, `list_memories`, MCP recall, or chat memory injection runs, **then** the archived row is not returned.

**AC-7:** **Given** `memory_retention_action=delete`, **when** the retention task processes an old memory, **then** the memory, its `MemoryVersion` rows, and its `MemoryRelation` rows are purged (they have `ondelete=CASCADE`).

**AC-8:** **Given** a workspace owner calls `DELETE /workspaces/{id}/memories/{memory_id}`, **when** the erasure is confirmed, **then** the memory and its versions/relations/embedding are purged within the SLA, and an `audit_events` entry is written.

**AC-9:** **Given** a bulk deletion of >100,000 memories by `source_type` + `source_id`, **when** the job runs, **then** it is chunked into batches of 1,000 rows with dry-run, progress reporting, and cancel-ability without corrupting the HNSW index.

**AC-10:** **And** `ruff`, `tsc --noEmit`, `biome`, backend unit/integration tests, and Playwright E2E tests pass with no regression to Story 3.14 memory latency benchmark.

---

## Technical Context

### Already [BUILT] — reuse, do NOT re-implement

- **Document retention pattern** — Story 3.7: `Workspace.document_retention_days`, `Workspace.auto_archive_enabled`, `Workspace.document_retention_action`, `Document.archived_at`, Celery `apply_document_retention_policies`.
- **Workspace limits pattern** — Story 8.12: `workspace_limits` table, `WorkspaceLimitService`, `_advisory_lock`, `ResolvedWorkspaceLimits`.
- **Memory CRUD/search** — `Memory`, `MemoryRepository.create_memory` / `update_memory`, `MemoryHybridSearch`, `memories_routes.py`.
- **Event bus & audit** — `app/event_bus/`, `audit_events` table/pattern.

### The [GAP] this story closes

1. Per-workspace memory count cap (`WorkspaceLimit.max_memory_count`) and soft bytes metric (`max_memory_bytes`), enforced in `MemoryRepository.create_memory`.
2. `Memory.archived_at` and `Workspace.memory_retention_*` fields mirroring document retention.
3. `apply_memory_retention_policies` Celery task mirroring document retention.
4. Search/list/recall exclude archived memory.
5. `DELETE /workspaces/{id}/memories/{memory_id}` right-to-delete endpoint + audit.
6. Bulk delete by `source_type`/`source_id` with dry-run, chunked 1,000 rows, progress, cancel.

---

## Dev Notes

### Decisions already ratified

- **Soft-delete marker:** `Memory.archived_at` (nullable TIMESTAMP + index), **not** `Memory.status = 'archived'`. This mirrors `Document.archived_at` and the existing `data-retention-manager.tsx` pattern. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/db.py" lines="1547-1549" />
- **Workspace retention fields:** `memory_retention_days` (Integer), `memory_auto_archive_enabled` (Boolean), `memory_retention_action` (String, default `"archive"`) — mirror `document_retention_*`. Self-host defaults to disabled/unlimited. <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/db.py" lines="1967-1977" />
- **Retention action values:** reuse `DocumentRetentionAction` enum (`archive`, `delete`). `archive` sets `archived_at = now()`; `delete` hard deletes immediately (v1 has no grace period; can add `memory_grace_period_days` later if legal requires).
- **Memory cap binds:** `AD-DEFER-4` (data lifecycle), `AD-18`/`NFR-1b/1c/1d` (memory bound). The cap is a guardrail to prevent the unbounded growth that makes `AD-18` per-turn costs explode.
- **Source risk tier (`memory_source_legal_tiers`) is owned by Story 28.3.** Story 28.5 does NOT create this table. If it exists, the retention task MAY use per-source defaults; otherwise it uses workspace defaults.
- **Boundary with Story 28.3:**
  - **28.3** owns: ToS review, source risk tier, high-risk source disable by default, user-facing bulk-delete confirm UX.
  - **28.5** owns: schema, enforcement, retention lifecycle, backend right-to-delete endpoint, audit writes.

### Files to read before modifying

- `nowing_backend/app/db.py` — `Memory`, `Workspace`, `WorkspaceLimit`, `DocumentRetentionAction`, `MemoryVersion`, `MemoryRelation`.
- `nowing_backend/app/services/workspace_limits.py` — `ResolvedWorkspaceLimits`, `WorkspaceLimitService`, `_advisory_lock`, `_limit_error`.
- `nowing_backend/app/services/memory/repository.py` — `MemoryRepository.create_memory` (single choke point).
- `nowing_backend/app/services/memory/search.py` — `MemoryHybridSearch._scope_conditions`.
- `nowing_backend/app/tasks/celery_tasks/document_retention_task.py` — pattern to mirror.
- `nowing_backend/app/routes/memories_routes.py` — existing CRUD.
- `nowing_backend/app/routes/workspaces_routes.py` — workspace settings/limits.
- `nowing_backend/app/schemas/workspace.py` — `WorkspaceUpdate`, `WorkspaceRead`, `WorkspaceLimitsResponse`, `WorkspaceLimitUpdate`, `WorkspaceLimitUsage`.
- `nowing_web/components/settings/workspace-limits-manager.tsx`.
- `nowing_web/components/settings/data-retention-manager.tsx`.

### Pitfalls

- `MemoryRepository.create_memory` has a `commit=False` batch path. Ensure the limit check runs before insert regardless of `commit`.
- `Memory.versions` and `Memory.relations` have `cascade="all, delete-orphan"`; hard delete is safe.
- Do **not** reuse `Workspace.max_storage_bytes` or `WorkspaceLimit.max_storage_bytes` for memory — those are document-only.
- `max_memory_bytes` is hard to compute accurately (TOAST). Treat it as a soft/estimated metric; `max_memory_count` is the hard gate.
- Bulk delete must not lock the `memories` table long enough to block HNSW inserts. Use `id IN (...)` with 1,000-row batches and explicit `COMMIT` between batches.

---

## Tasks / Subtasks

- [ ] **T1 — Schema & migration**
  - [ ] T1.1 Add `memory_retention_days` (nullable Integer), `memory_auto_archive_enabled` (Boolean, default false), `memory_retention_action` (String(20), default `"archive"`) to `Workspace`.
  - [ ] T1.2 Add a check constraint for memory retention: `NOT memory_auto_archive_enabled OR (memory_retention_days IS NOT NULL AND memory_retention_days > 0 AND memory_retention_days <= 36500)`.
  - [ ] T1.3 Add `max_memory_count` (nullable Integer) and `max_memory_bytes` (nullable BigInteger) to `WorkspaceLimit`.
  - [ ] T1.4 Add `archived_at` (nullable TIMESTAMP) to `Memory` with index.
  - [ ] T1.5 Create Alembic migration `230_add_memory_retention_and_storage_cap.py`.

- [ ] **T2 — Workspace limits service**
  - [ ] T2.1 Extend `ResolvedWorkspaceLimits` with `max_memory_count` and `max_memory_bytes`.
  - [ ] T2.2 Add `WorkspaceLimitService.count_memories(session, workspace_id)`.
  - [ ] T2.3 Add `WorkspaceLimitService.estimate_memory_storage_bytes(session, workspace_id)` (best-effort; see Dev Notes).
  - [ ] T2.4 Add `WorkspaceLimitService.check_memory_limit(session, workspace_id, additional=1)` using advisory lock.
  - [ ] T2.5 Update `get_usage_snapshot` to include memory count/bytes in `WorkspaceLimitUsage`.

- [ ] **T3 — Memory repository gating**
  - [ ] T3.1 In `MemoryRepository.create_memory`, call `workspace_limit_service.check_memory_limit` after duplicate check and before `session.add(memory)`.
  - [ ] T3.2 Skip check when `workspace_id is None` (personal memory) or self-host with no override.

- [ ] **T4 — Search and list filtering**
  - [ ] T4.1 Add `Memory.archived_at.is_(None)` to `MemoryHybridSearch._scope_conditions`.
  - [ ] T4.2 Add `archived_at.is_(None)` to `MemoryRepository.list_memories` and any other workspace-scoped `Memory` query.

- [ ] **T5 — Memory retention Celery task**
  - [ ] T5.1 Create `app/tasks/celery_tasks/memory_retention_task.py` with `apply_memory_retention_policies`, mirror `document_retention_task.py`.
  - [ ] T5.2 Register task in `app/celery_app.py` `include` and `beat_schedule`.
  - [ ] T5.3 Archive old memories (`archived_at = now`); hard delete when `memory_retention_action == "delete"`.

- [ ] **T6 — Routes and schemas**
  - [ ] T6.1 Extend `WorkspaceUpdate` and `WorkspaceRead` with memory retention fields.
  - [ ] T6.2 Extend `WorkspaceLimitUpdate` and `WorkspaceLimitsResponse` with memory limit fields and usage.
  - [ ] T6.3 Add `DELETE /workspaces/{workspace_id}/memories/{memory_id}` route (right-to-delete) with audit.
  - [ ] T6.4 Add admin/owner `POST /workspaces/{workspace_id}/memories/bulk-delete` with dry-run + confirm + chunked 1,000 rows.
  - [ ] T6.5 Seed `workspace_limits` plan defaults for `max_memory_count` (e.g., free 1_000, team 10_000, enterprise None) and `max_memory_bytes` (e.g., free 5_000_000_000, team 50_000_000_000).

- [ ] **T7 — Frontend**
  - [ ] T7.1 Add memory count/bytes to `workspace-limits-manager.tsx`.
  - [ ] T7.2 Add a "Memory retention" section to `data-retention-manager.tsx` using the same switch/input/select pattern as document retention.
  - [ ] T7.3 Add i18n keys to `messages/en.json` (and mirror to other locales or rely on English fallback).

- [ ] **T8 — Verification**
  - [ ] T8.1 Unit tests: `WorkspaceLimitService.check_memory_limit` at/below/above boundary; concurrent boundary.
  - [ ] T8.2 Integration tests: `POST /workspaces/{id}/memories` rejects at cap; retention task archives/deletes correctly; search excludes archived; `DELETE` right-to-delete + audit.
  - [ ] T8.3 `ruff check` / `ruff format` on changed backend files.
  - [ ] T8.4 `tsc --noEmit` and `biome check` on changed web files.
  - [ ] T8.5 Re-run `scripts/benchmark_memory_story_3_14.py` to confirm no latency regression from `archived_at` filter.

---

## Verification

Backend:
```bash
cd nowing_backend
ruff check app/db.py app/services/workspace_limits.py app/services/memory/repository.py app/services/memory/search.py app/routes/workspaces_routes.py app/routes/memories_routes.py app/schemas/workspace.py app/tasks/celery_tasks/memory_retention_task.py alembic/versions/230_add_memory_retention_and_storage_cap.py
uv run alembic upgrade head
uv run pytest tests/unit/services/test_workspace_limits.py tests/integration/services/test_workspace_limits.py tests/integration/memory -q
uv run pytest tests/unit/automations tests/integration/automations -q
```

Frontend:
```bash
cd nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/settings/workspace-limits-manager.tsx components/settings/data-retention-manager.tsx
```

E2E / performance:
```bash
cd nowing_backend
uv run python scripts/benchmark_memory_story_3_14.py --small-corpus 100 --large-corpus 10000 --warmups 20 --samples 100 --freshness-samples 0 --output /Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/evidence/3-14-memory-performance-28-5-regression.json
```

---

## Dev Agent Record

**Debug Log:**

- (empty — populate during implementation)

**Completion Notes:**

- (empty — populate during implementation)

---

## File List

- `_bmad-output/implementation-artifacts/stories/28-5-workspace-memory-storage-cap-and-retention.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/AD-28-3-retention-right-to-delete.md`
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`
- `nowing_backend/alembic/versions/230_add_memory_retention_and_storage_cap.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/workspace.py`
- `nowing_backend/app/services/workspace_limits.py`
- `nowing_backend/app/services/memory/repository.py`
- `nowing_backend/app/services/memory/search.py`
- `nowing_backend/app/routes/workspaces_routes.py`
- `nowing_backend/app/routes/memories_routes.py`
- `nowing_backend/app/tasks/celery_tasks/memory_retention_task.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/tests/unit/services/test_workspace_limits.py` (extend)
- `nowing_backend/tests/integration/services/test_workspace_limits.py` (extend)
- `nowing_backend/tests/integration/memory/test_memory_retention.py` (new)
- `nowing_web/components/settings/workspace-limits-manager.tsx`
- `nowing_web/components/settings/data-retention-manager.tsx`
- `nowing_web/messages/en.json`

---

## Change Log

- 2026-08-23: Story file created based on impact analysis of memory cap + retention.
- 2026-08-23: Aligned with `AD-28.3` (ADOPTED): use `Memory.archived_at`, `Workspace.memory_retention_*` (mirror document retention), `WorkspaceLimit.max_memory_count`, cap binds `AD-DEFER-4`/`AD-18`/`NFR-1b/1c/1d`, source risk tier deferred to Story 28.3.
