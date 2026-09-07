---
story_key: 29-5-memory-browser-research-timeline-for-analyst
status: ready-for-dev
baseline_commit: 0aad40ba21a2524b99dd7af2607c8b71e5c0d3e8
epic: 29
story: 5
---

# Story 29.5: Memory Browser & Research Timeline for Analyst

**Status:** `ready-for-dev`  
**Epic:** 29 — SaaS Operations, Advanced Admin Governance & Analyst Workspace  
**Governed by:** FR-104, AR-17, AR-18, UX-DR-PRFAQ-1, UX-DR-PRFAQ-6, NFR-1, NFR-2, NFR-5, INV-29.3, AD-11, AD-55.  
**Dependencies:** Epic 1 (auth/RBAC), Epic 3 (memory, `MemoryVersion`, `ResearchThread`, `MemoryRelation`), Epic 8 (billing/cost/wallet), Epic 25 (admin baseline), Epic 29.1 (`WorkspaceRole` + permission `memory_read`/`memory_write`/`memory_delete`).

---

## Story

As an **Analyst in a workspace**,  
I want a **memory browser that lists, filters, and explores research memories with source citation and version history**,  
so that **I can verify facts, trace research lineage, and flag outdated or low-confidence claims**.

---

## Acceptance Criteria

### AC-1 — Workspace-Scoped Memory List (FR-104, INV-29.3, AD-11)
**Given** the Analyst opens `/dashboard/[workspace_id]/memory-browser`,  
**When** the page loads,  
**Then**:
1. The UI shows a paginated, sortable list of `Memory` rows scoped to `workspace_id`.
2. Default page size is `50`, with a selector for `25 | 50 | 100`.
3. Columns include: content snippet, source type, source URL (clickable), confidence, created at, updated at, created by, version count, flag status.
4. Backend filters all queries by `workspace_id` in SQL `WHERE` (no cross-tenant leakage).
5. Indexes on `(workspace_id, source_type, confidence)`, `(workspace_id, created_at DESC)`, and `(workspace_id, user_id)` are present and exploited by the query planner for workspaces up to 100,000 memories in < 300ms.

### AC-2 — Filters & Search (FR-104, UX-DR-PRFAQ-6 MB-2, NFR-1)
**Given** the Analyst uses the filter bar,  
**When** they select source type, confidence range, time range, creator, or search by keyword,  
**Then**:
1. Source type chips allow `SCRAPER_RUN`, `CHAT_TURN`, `DOCUMENT`, `CONNECTOR` (and any `MemorySourceType` value) via `eq`/`in` filters.
2. Confidence range is a slider from `0.0` to `1.0` mapping to `confidence >= min AND confidence <= max`.
3. Time range filters on `created_at` with presets `24h`, `7d`, `30d`, `90d` and custom from/to ISO timestamps.
4. Creator filter is a dropdown of users with membership in the workspace.
5. Keyword search uses existing `content_search` GIN tsvector index or `content ILIKE` fallback if `content_search` is null.
6. All filters are composable and sent as query params to `GET /api/v1/workspaces/{workspace_id}/memories`.

### AC-3 — Memory Detail Panel (FR-104, UX-DR-PRFAQ-6 MB-3, MB-4, AD-11)
**Given** the Analyst clicks a memory row,  
**When** the detail panel opens,  
**Then**:
1. Full content is rendered (decrypt if `key_id` is set).
2. Source citations are listed with click-to-source behavior:
   - `source_run_id` → link to run log/audit detail;
   - `source_uuid` + `source_entity_type` → link to canonical entity view if exists;
   - `source_id` → chat message or document origin;
   - fallback shows `source_type` badge.
3. Version history shows `MemoryVersion` rows with `previous_content`, `corrected_content`, `corrected_by`, `created_at`.
4. Research threads show the linked `ResearchThread` title and chronological list of related memories in the thread.
5. Related memories from `MemoryRelation` (branch/merge) are shown with relation type and weight.

### AC-4 — Research Timeline View (FR-104, UX-DR-PRFAQ-6 MB-1, AD-11)
**Given** the Analyst toggles "Research timeline" view,  
**When** the view switches,  
**Then**:
1. Memories are grouped by `research_thread_id`.
2. Within each thread, memories are ordered chronologically by `created_at`.
3. Branch/merge markers are rendered for `MemoryRelation` rows where the relation type is `branch` or `merge`.
4. A thread without a title falls back to "Untitled thread #{id}".

### AC-5 — Flag for Review (FR-104, UX-DR-PRFAQ-6 MB-5, AR-18)
**Given** the Analyst flags a memory as outdated or incorrect,  
**When** they submit a note,  
**Then**:
1. The system creates a `memory_review_queue` entry with columns: `id`, `memory_id`, `flag_reason` (text), `flagged_by` (UUID), `status` (`open`), `created_at`.
2. The Owner/Editor of the workspace is notified (in-app notification / email is optional v1; the audit entry is required).
3. The memory is **not** auto-deleted, auto-archived, or auto-rewritten.
4. v1 scope is flag + notify only; no approval-edit workflow.

### AC-6 — Permission Boundary (FR-104, AD-9, AD-55)
**Given** the Analyst has only `memory:read` permission,  
**When** they try to flag or edit a memory,  
**Then**:
1. The UI hides the "Flag for review" and any edit/delete actions.
2. The backend rejects `POST /workspaces/{workspace_id}/memories/{memory_id}/review-flag` or any destructive endpoint with `403 Forbidden`.
3. `memory:write` or `memory:delete` is required for destructive actions.

### AC-7 — Accessibility & Navigation (FR-104, NFR-2, NFR-5)
**Given** the memory browser,  
**Then**:
1. The page is reachable from the analyst workspace dashboard via a nav item "Memory Browser" or "Research".
2. Keyboard navigation (arrow keys, Enter, Escape to close panel) works.
3. Screen-reader labels are provided for confidence slider, source chips, flag button, and pagination.

---

## Dev Notes

### Architecture Compliance
- Use SQLAlchemy 2.0 async `AsyncSession`; every route opens its own session.
- Reuse `check_permission(session, auth, workspace_id, Permission.MEMORY_READ.value)` for read routes and `Permission.MEMORY_WRITE.value` for flag creation.
- Add new backend routes under `app/routes/workspaces_routes.py` or a new `app/routes/memory_browser_routes.py` wired into `app/routes/__init__.py`.
- Use existing `Memory`, `MemoryVersion`, `MemoryRelation`, `ResearchThread`, `User`, `Workspace` models.
- The new `memory_review_queue` table is created via Alembic; no `ON DELETE CASCADE` to `memories` — use `SET NULL` or protect the queue row on memory delete.
- Decryption: reuse `MemoryEncryptionService.decrypt_memory` for `content` and version `previous_content`/`corrected_content`.
- Use `pg_trgm`/`to_tsvector` for keyword search; the `ix_memories_content_search` GIN index already exists.
- Frontend: use Next.js App Router at `app/dashboard/[workspace_id]/memory-browser/page.tsx` with `WorkspaceMemoryBrowser` component under `components/memory-browser/`.
- Use `@tanstack/react-query` for server cache and Jotai for ephemeral UI state (filter panel open/closed, selected memory).
- Pagination uses `limit`/`offset` for v1; cursor-based pagination is optional future work.

### Model Assumptions
- `Memory` columns: `id` (PK int), `workspace_id`, `created_by_id`, `research_thread_id`, `content`, `content_search`, `confidence`, `source_type`, `source_id`, `source_run_id`, `source_uuid`, `source_entity_type`, `source_capability`, `source_input`, `archived_at`, `created_at`, `updated_at`, `key_id`, `encryption_iv`, `encryption_algo`.
- `MemoryVersion` columns: `id`, `memory_id`, `previous_content`, `corrected_content`, `corrected_by_id`, `created_at` (+ encryption metadata).
- `ResearchThread` columns: `id`, `workspace_id`, `created_by_id`, `title`, `client_id`, `current_chat_thread_id`.
- `MemoryRelation` columns: `id`, `workspace_id`, `from_memory_id`, `to_memory_id`, `relation_type`, `weight`.
- `User` columns: `id` (UUID), `email`.
- `WorkspaceMembership` provides `user_id` + `workspace_id` for the creator dropdown.
- `memory_review_queue` is new: `id` (serial PK), `memory_id` (int, FK `memories.id` ON DELETE SET NULL), `workspace_id` (int, FK `workspaces.id` ON DELETE CASCADE), `flag_reason` (text), `flagged_by` (UUID FK `user.id` ON DELETE SET NULL), `status` (`open`, `resolved`, `dismissed`), `created_at`, `resolved_at`, `resolved_by`.

### Permission Guard
- `GET /workspaces/{workspace_id}/memories` → `Permission.MEMORY_READ`.
- `GET /workspaces/{workspace_id}/memories/{memory_id}` → `Permission.MEMORY_READ`.
- `GET /workspaces/{workspace_id}/memories/{memory_id}/versions` → `Permission.MEMORY_READ`.
- `GET /workspaces/{workspace_id}/memories/{memory_id}/relations` → `Permission.MEMORY_READ`.
- `POST /workspaces/{workspace_id}/memories/{memory_id}/review-flag` → `Permission.MEMORY_WRITE`.
- Owner/Superadmin implicitly have all permissions through `check_permission`.

### Query & Performance
- Base query: `select(Memory).where(Memory.workspace_id == workspace_id, Memory.archived_at.is_(None)).order_by(Memory.created_at.desc())`.
- Apply tenant scoping first; then optional filters.
- Confidence range: `func.coalesce(Memory.confidence, 0.0)` between min/max.
- Time range: `Memory.created_at >= since AND Memory.created_at <= until`.
- Keyword: `Memory.content_search.op('@@')(func.plainto_tsquery('english', q))` OR `Memory.content.ilike(f"%{q}%")` when `content_search` is null.
- Creator: `Memory.created_by_id == user_uuid`.
- Ensure query planner uses `ix_memories_workspace_id_client_id` and the new partial/thread indexes.

### Response Shapes (Backend)
- `GET /api/v1/workspaces/{workspace_id}/memories?...`
  ```json
  {
    "items": [{
      "id": 123,
      "content_snippet": "...",
      "source_type": "SCRAPER_RUN",
      "source_url": "...",
      "confidence": 0.95,
      "created_at": "...",
      "updated_at": "...",
      "created_by": {"id": "...", "email": "..."},
      "version_count": 2,
      "flag_status": "open"
    }],
    "total": 1000,
    "page": 1,
    "page_size": 50
  }
  ```
- `GET /api/v1/workspaces/{workspace_id}/memories/{memory_id}`
  Returns full memory with decrypted `content`, source citations, `research_thread`, `versions`, `relations`.
- `POST /api/v1/workspaces/{workspace_id}/memories/{memory_id}/review-flag`
  Body: `{"flag_reason": "..."}`  
  Returns the created `MemoryReviewQueue` object and `201 Created`.

### Frontend Components (proposed)
- `app/dashboard/[workspace_id]/memory-browser/page.tsx` — page shell.
- `components/memory-browser/MemoryBrowser.tsx` — main container (filters, list, detail panel).
- `components/memory-browser/MemoryList.tsx` — paginated table/rows.
- `components/memory-browser/MemoryFilters.tsx` — source chips, confidence slider, date range, creator dropdown, search.
- `components/memory-browser/MemoryDetailPanel.tsx` — content, citations, versions, thread, relations.
- `components/memory-browser/ResearchTimeline.tsx` — grouped by `research_thread_id`.
- `components/memory-browser/FlagForReviewDialog.tsx` — reason input + submit.
- `lib/apis/memory-browser-api.service.ts` — API client.
- `contracts/types/memory-browser.types.ts` — Zod schemas.

### Testing Standards
- Integration tests in `nowing_backend/tests/integration/routes/test_memory_browser.py`:
  - list with workspace scope and filters;
  - detail returns decrypted content and versions;
  - flag creates `memory_review_queue` row;
  - 403 for `memory:read` only user attempting to flag.
- Integration tests in `nowing_backend/tests/integration/services/test_memory_browser_service.py`:
  - keyword search uses GIN index and returns < 300ms for 100k rows;
  - confidence range, time range, source type filters produce correct counts;
  - decryption works for encrypted rows.
- Frontend unit/contract tests in `nowing_web/tests/memory-browser/memory-browser-schema.test.ts`.
- Optional Playwright E2E in `nowing_web/tests/memory-browser/memory-browser.spec.ts`.

### Files to Touch (NEW and UPDATE)
- **NEW:**
  - `nowing_backend/alembic/versions/YYYYMMDD_add_memory_review_queue.py`
  - `nowing_backend/app/models/memory_review_queue.py`
  - `nowing_backend/app/schemas/memory_browser.py`
  - `nowing_backend/app/services/memory_browser_service.py`
  - `nowing_backend/app/routes/memory_browser_routes.py` (or extend `workspaces_routes.py`)
  - `nowing_backend/tests/integration/routes/test_memory_browser.py`
  - `nowing_backend/tests/integration/services/test_memory_browser_service.py`
  - `nowing_web/app/dashboard/[workspace_id]/memory-browser/page.tsx`
  - `nowing_web/components/memory-browser/*`
  - `nowing_web/contracts/types/memory-browser.types.ts`
  - `nowing_web/lib/apis/memory-browser-api.service.ts`
  - `nowing_web/messages/en.json` + `vi.json` i18n keys
- **UPDATE:**
  - `nowing_backend/app/models/__init__.py`
  - `nowing_backend/app/db/__init__.py`
  - `nowing_backend/app/routes/__init__.py`
  - `nowing_web/app/dashboard/[workspace_id]/client-layout.tsx` or nav shell to add "Memory Browser" link

---

## References

- `nowing_backend/app/models/memory.py` — `Memory`, `MemoryVersion`, `MemoryRelation` definitions.
- `nowing_backend/app/models/workspaces.py:560` — `ResearchThread` definition.
- `nowing_backend/app/db/enums.py` — `MemorySourceType`, `Permission` enums.
- `nowing_backend/app/utils/rbac.py:129` — `check_permission` helper.
- `nowing_backend/app/services/memory/encryption.py` — `MemoryEncryptionService`.
- `nowing_web/app/dashboard/[workspace_id]/health/page.tsx` — dashboard page pattern.
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-29-saas-admin-analytics.md` — MB-1..MB-6.
- `_bmad-output/planning-artifacts/epics.md:4462` — Epic 29 / Story 29.5 source AC.
