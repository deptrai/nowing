---
story_key: 29-5-memory-browser-research-timeline-for-analyst
status: done
baseline_commit: 0aad40ba21a2524b99dd7af2607c8b71e5c0d3e8
epic: 29
story: 5
---

# Story 29.5: Memory Browser & Research Timeline for Analyst

**Status:** `done`  
**Epic:** 29 — SaaS Operations, Advanced Admin Governance & Analyst Workspace  
**Governed by:** FR-104, AR-17, AR-18, UX-DR-PRFAQ-1, UX-DR-PRFAQ-6, NFR-1, NFR-2, NFR-5, INV-29.3, AD-11, AD-55.  
**Dependencies:** Epic 1 (auth/RBAC), Epic 3 (memory, `MemoryVersion`, `ResearchThread`, `MemoryRelation`), Epic 8 (billing/cost/wallet), Epic 25 (admin baseline), Epic 29.1 (`WorkspaceRole` + permission `memory:read`/`memory:update`/`memory:delete`).

---

## Story

As an **Analyst in a workspace**,  
I want a **memory browser that lists, filters, and explores research memories with source citation and version history**,  
so that **I can verify facts, trace research lineage, and flag outdated or low-confidence claims**.

---

## Acceptance Criteria

### AC-1 — Workspace-Scoped Memory List (FR-104, INV-29.3, AD-11)
**Given** the Analyst opens `/dashboard/[workspace_id]/research/memory-browser`,  
**When** the page loads,  
**Then**:
1. The UI shows a paginated, sortable list of `Memory` rows scoped to `workspace_id`.
2. Default page size is `50`, with a selector for `25 | 50 | 100`.
3. Columns include: content snippet, source type, source link (derived — see Dev Notes), confidence, created at, updated at, created by, version count, flag status.
4. Backend filters all queries by `workspace_id` in SQL `WHERE` (no cross-tenant leakage).
5. Migration adds composite index `ix_memories_browser_list` on `(workspace_id, source_type, confidence, created_at DESC)` — existing indexes cover `(workspace_id, research_thread_id, created_at, id)` and `(workspace_id, client_id)` but **not** the `(workspace_id, source_type, confidence)` triple needed for the filter bar; the new index is required for < 300ms on 100k-row workspaces.

### AC-2 — Filters & Search (FR-104, UX-DR-PRFAQ-6 MB-2, NFR-1)
**Given** the Analyst uses the filter bar,  
**When** they select source type, confidence range, time range, creator, or search by keyword,  
**Then**:
1. Source type chips allow `SCRAPER_RUN`, `CHAT_MESSAGE`, `DOCUMENT`, `MANUAL`, `SIGNAL`, `LEAD`, and `CONNECTOR*` values from the `MemorySourceType` enum (`DOCUMENT`, `CHAT_MESSAGE`, `SCRAPER_RUN`, `MANUAL`, `UNKNOWN`, `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `CRM_CONNECTION`, `CRM_SYNC`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`, plus connector types `LUMA_CONNECTOR`, `ELASTICSEARCH_CONNECTOR`, `WEBCRAWLER_CONNECTOR`, `BOOKSTACK_CONNECTOR`, `CIRCLEBACK_CONNECTOR`, `OBSIDIAN_CONNECTOR`, `MCP_CONNECTOR`, `EXA_MCP_CONNECTOR`, `DROPBOX_CONNECTOR`, `COMPOSIO_GOOGLE_DRIVE_CONNECTOR`, `COMPOSIO_GMAIL_CONNECTOR`, `COMPOSIO_GOOGLE_CALENDAR_CONNECTOR`, `RSS_FEED`) via `eq`/`in` filters.
2. Confidence range is a slider from `0.0` to `1.0` mapping to `confidence >= min AND confidence <= max`.
3. Time range filters on `created_at` with presets `24h`, `7d`, `30d`, `90d` and custom from/to ISO timestamps.
4. Creator filter is a dropdown populated from `WorkspaceMembership` joined to `User` for the current `workspace_id` (any status, deduplicated by `user_id`).
5. Keyword search uses existing `ix_memories_content_search` GIN index on `to_tsvector('english', content)`; fallback `content ILIKE` is only used for encrypted rows where `content_search` is null and the caller cannot decrypt.
6. All filters are composable and sent as query params to `GET /api/v1/workspaces/{workspace_id}/memories`.

### AC-3 — Memory Detail Panel (FR-104, UX-DR-PRFAQ-6 MB-3, MB-4, AD-11)
**Given** the Analyst clicks a memory row,  
**When** the detail panel opens,  
**Then**:
1. Full content is rendered (decrypt if `key_id` is set).
2. Source citations are listed with click-to-source behavior:
   - `source_run_id` → link to `/dashboard/[workspace_id]/runs/{source_run_id}` (if a runs route exists) or show `source_type` badge + run id; 
   - `source_uuid` + `source_entity_type` → link to canonical entity view (e.g. `/dashboard/[workspace_id]/leads/{source_uuid}` when `source_entity_type = "lead"`, `/dashboard/[workspace_id]/documents/{source_uuid}` when `source_entity_type = "document"`);
   - `source_id` → chat message id (no direct URL in v1; show `source_type` badge + id);
   - `source_capability`/`source_input` are displayed as expandable JSON for re-execution context;
   - fallback shows `source_type` badge.
3. Version history shows `MemoryVersion` rows with `previous_content`, `corrected_content`, `corrected_by`, `created_at`.
4. Research threads show the linked `ResearchThread` title and chronological list of related memories in the thread.
5. Related memories from `MemoryRelation` are shown with relation type and weight.

### AC-4 — Research Timeline View (FR-104, UX-DR-PRFAQ-6 MB-1, AD-11)
**Given** the Analyst toggles "Research timeline" view,  
**When** the view switches,  
**Then**:
1. Memories are grouped by `research_thread_id`.
2. Within each thread, memories are ordered chronologically by `created_at`.
3. Branch/merge markers are rendered for `MemoryRelation` rows where the relation type is `DERIVED_FROM` or `CORRECTS` (closest equivalents; `MemoryRelationType` has no literal `branch`/`merge` values).
4. A thread without a title falls back to "Untitled thread #{id}".

### AC-5 — Flag for Review (FR-104, UX-DR-PRFAQ-6 MB-5, AR-18)
**Given** the Analyst flags a memory as outdated or incorrect,  
**When** they submit a note,  
**Then**:
1. The system creates a `memory_review_queue` entry with columns: `id`, `memory_id`, `workspace_id`, `flag_reason` (text), `flagged_by` (UUID), `status` (`open`), `created_at`.
2. The Owner/Editor of the workspace is notified via `NotificationService` (`app/notifications/service/facade.py`) using an in-app notification with type `memory_review_flag`; the audit entry is required.
3. The memory is **not** auto-deleted, auto-archived, or auto-rewritten.
4. v1 scope is flag + notify only; no approval-edit workflow.

### AC-6 — Permission Boundary (FR-104, AD-9, AD-55)
**Given** the Analyst has only `memory:read` permission,  
**When** they try to flag or edit a memory,  
**Then**:
1. The UI hides the "Flag for review" and any edit/delete actions.
2. The backend rejects `POST /workspaces/{workspace_id}/memories/{memory_id}/review-flag` or any destructive endpoint with `403 Forbidden`.
3. `memory:update` or `memory:delete` is required for destructive actions (`memory:write` does not exist in `Permission`; use `MEMORY_UPDATE`/`MEMORY_DELETE`).

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
- Reuse `check_permission(session, auth, workspace_id, Permission.MEMORY_READ.value)` for read routes and `Permission.MEMORY_UPDATE.value` for flag creation.
- Add new backend routes under `app/routes/workspaces_routes.py` or a new `app/routes/memory_browser_routes.py` wired into `app/routes/__init__.py`.
- Use existing `Memory`, `MemoryVersion`, `MemoryRelation`, `ResearchThread`, `User`, `Workspace` models.
- The new `memory_review_queue` table is created via Alembic; no `ON DELETE CASCADE` to `memories` — use `SET NULL` or protect the queue row on memory delete.
- Decryption: reuse `MemoryEncryptionService.decrypt_memory` for `content` and version `previous_content`/`corrected_content`.
- Use `pg_trgm`/`to_tsvector` for keyword search; the `ix_memories_content_search` GIN index already exists.
- Frontend: use Next.js App Router at `app/dashboard/[workspace_id]/research/memory-browser/page.tsx` with `WorkspaceMemoryBrowser` component under `components/memory-browser/`.
- Use `@tanstack/react-query` for server cache and Jotai for ephemeral UI state (filter panel open/closed, selected memory).
- Pagination uses `limit`/`offset` for v1; cursor-based pagination is optional future work.

### Model Assumptions
- `Memory` columns: `id` (PK int), `workspace_id`, `created_by_id`, `research_thread_id`, `content`, `content_search`, `confidence`, `source_type`, `source_id`, `source_run_id`, `source_uuid`, `source_entity_type`, `source_capability`, `source_input`, `archived_at`, `created_at`, `updated_at`, `key_id`, `encryption_iv`, `encryption_algo`.
- `source_url` is **not** a `Memory` column; it is derived server-side from `source_run_id` / `source_uuid` + `source_entity_type` / `source_id`.
- `flag_status` is derived from `memory_review_queue` (`open` if any row with `status = 'open'` exists for the memory).
- `MemorySourceType` values (from `app/db/enums.py`): `DOCUMENT`, `CHAT_MESSAGE`, `SCRAPER_RUN`, `MANUAL`, `UNKNOWN`, `SIGNAL`, `LEAD`, `LEAD_SCORE`, `ENRICHMENT`, `CRM_CONNECTION`, `CRM_SYNC`, `SEQUENCE_EVENT`, `OUTCOME_EVENT`, `LUMA_CONNECTOR`, `ELASTICSEARCH_CONNECTOR`, `WEBCRAWLER_CONNECTOR`, `BOOKSTACK_CONNECTOR`, `CIRCLEBACK_CONNECTOR`, `OBSIDIAN_CONNECTOR`, `MCP_CONNECTOR`, `EXA_MCP_CONNECTOR`, `DROPBOX_CONNECTOR`, `COMPOSIO_GOOGLE_DRIVE_CONNECTOR`, `COMPOSIO_GMAIL_CONNECTOR`, `COMPOSIO_GOOGLE_CALENDAR_CONNECTOR`, `RSS_FEED`.
- `MemoryVersion` columns: `id`, `memory_id`, `previous_content`, `corrected_content`, `corrected_by_id`, `created_at` (+ encryption metadata).
- `ResearchThread` columns: `id`, `workspace_id`, `created_by_id`, `title`, `client_id`, `current_chat_thread_id`.
- `MemoryRelation` columns: `id`, `workspace_id`, `from_memory_id`, `to_memory_id`, `relation_type` (`MemoryRelationType` enum: `RELATED`, `DERIVED_FROM`, `CORRECTS`, `SOURCE_DOCUMENT`, `SOURCE_CHAT`, `SOURCE_RUN`), `weight`.
- `User` columns: `id` (UUID), `email`.
- `WorkspaceMembership` provides `user_id` + `workspace_id` for the creator dropdown.
- `memory_review_queue` is new: `id` (serial PK), `memory_id` (int, FK `memories.id` ON DELETE SET NULL — note: `Memory.versions` uses `cascade="all, delete-orphan"` so a hard memory delete already cascades; `SET NULL` here keeps the review row for audit), `workspace_id` (int, FK `workspaces.id` ON DELETE CASCADE), `flag_reason` (text), `flagged_by` (UUID FK `user.id` ON DELETE SET NULL), `status` (`open`, `resolved`, `dismissed`), `created_at`, `resolved_at`, `resolved_by`.
- Notify Owner/Editor via `NotificationService.create_notification(session, user_id, notification_type="memory_review_flag", title=..., message=..., workspace_id=workspace_id, notification_metadata={"memory_id": ..., "flag_reason": ...})` — this matches `app/notifications/service/facade.py:35` signature.

### Permission Guard
- `GET /workspaces/{workspace_id}/memories` → `Permission.MEMORY_READ`.
- `GET /workspaces/{workspace_id}/memories/{memory_id}` → `Permission.MEMORY_READ`.
- `GET /workspaces/{workspace_id}/memories/{memory_id}/versions` → `Permission.MEMORY_READ`.
- `GET /workspaces/{workspace_id}/memories/{memory_id}/relations` → `Permission.MEMORY_READ`.
- `POST /workspaces/{workspace_id}/memories/{memory_id}/review-flag` → `Permission.MEMORY_UPDATE`.
- Owner/Superadmin implicitly have all permissions through `check_permission`.

### Query & Performance
- Base query: `select(Memory).where(Memory.workspace_id == workspace_id, Memory.archived_at.is_(None)).order_by(Memory.created_at.desc())`.
- Apply tenant scoping first; then optional filters.
- Confidence range: `func.coalesce(Memory.confidence, 0.0)` between min/max.
- Time range: `Memory.created_at >= since AND Memory.created_at <= until`.
- Keyword: use `func.to_tsvector('english', Memory.content).op('@@')(func.plainto_tsquery('english', q))` to exploit `ix_memories_content_search`; fallback `Memory.content.ilike(f"%{q}%")` only for encrypted rows without `content_search`.
- Creator: `Memory.created_by_id == user_uuid`.
- Ensure query planner uses `ix_memories_workspace_id_client_id`, `ix_memories_thread_recency`, and the new migration index `ix_memories_browser_list` on `(workspace_id, source_type, confidence, created_at DESC)`.

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
- `app/dashboard/[workspace_id]/research/memory-browser/page.tsx` — page shell.
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
  - `nowing_backend/alembic/versions/YYYYMMDD_add_memory_review_queue.py` — creates `memory_review_queue` table and adds `ix_memories_browser_list` index on `memories (workspace_id, source_type, confidence, created_at DESC)`
  - `nowing_backend/app/models/memory_review_queue.py`
  - `nowing_backend/app/schemas/memory_browser.py`
  - `nowing_backend/app/services/memory_browser_service.py`
  - `nowing_backend/app/routes/memory_browser_routes.py` (or extend `workspaces_routes.py`)
  - `nowing_backend/tests/integration/routes/test_memory_browser.py`
  - `nowing_backend/tests/integration/services/test_memory_browser_service.py`
  - `nowing_web/app/dashboard/[workspace_id]/research/memory-browser/page.tsx`
  - `nowing_web/components/memory-browser/*`
  - `nowing_web/contracts/types/memory-browser.types.ts`
  - `nowing_web/lib/apis/memory-browser-api.service.ts`
  - `nowing_web/messages/en.json` + `vi.json` i18n keys
- **UPDATE:**
  - `nowing_backend/app/models/__init__.py`
  - `nowing_backend/app/db/__init__.py`
  - `nowing_backend/app/routes/__init__.py`
  - `nowing_web/components/layout/providers/LayoutDataProvider.tsx` — add "Memory Browser" nav item to `navItems` (pattern: `{ title: tNav("memory_browser"), url: `/dashboard/${workspaceId}/research/memory-browser`, icon: BookMarked, isActive: isMemoryBrowserActive }`); also add `isMemoryBrowserActive = pathname?.includes("/memory-browser")` and import `BookMarked` from `lucide-react`. Add `nav_menu.memory_browser` i18n key to `messages/en.json` + `vi.json`.

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

## Challenge Log (grill-me)

### Q1 — Already implemented?
- **No duplicate logic found for the full browser UX.** `GET /workspaces/{workspace_id}/memories` exists but only supports `type`/`tags`/`client_id`/`limit` filters and returns a flat `list[MemoryRead]`. `MemoryHybridSearch` is a ranked search (max 5 results, RRF fusion) — not a paginated list. No `memory_review_queue` model, no browser route, no `MemoryBrowserListResponse` schema, and no source-derivation helper exist.
- **Existing building blocks to reuse:** `Memory`, `MemoryVersion`, `MemoryRelation`, `ResearchThread`, `check_permission`, `MemoryEncryptionService`, `NotificationService`, `to_tsvector('english', Memory.content)` keyword expression, and `MemoryRead` `citation` logic.
- **Verdict:** Proceed.

### Q2 — Simpler alternative?
- **Keyword search expression** can reuse the existing `to_tsvector('english', Memory.content).op('@@')(func.plainto_tsquery('english', q))` pattern from `app/services/memory/search.py`; do not call `MemoryHybridSearch.search()` because it is limited to top-5 and returns `ScoredMemory`.
- **Source link derivation** should be computed in the new `MemoryBrowserListItem` Pydantic schema from `source_run_id`/`source_uuid`/`source_entity_type`/`source_id` (no dedicated service needed).
- **Creator dropdown** is a straightforward `select(User)` joined through `WorkspaceMembership`.
- **Verdict:** Reuse patterns; no HALT.

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] Boundary: `confidence` min=0.0 / max=1.0; `min > max` rejected with 422; `page_size` > 100 rejected with 422; `page` zero/negative rejected.
- [ ] Null/empty: `research_thread_id` NULL → "Untitled thread #{id}"; all source pointers NULL → fallback to source type badge; `MemoryVersion.corrected_by_id` NULL → show "unknown"; `MemoryRelation.to_memory_id` NULL → render relation without target link.
- [ ] Concurrent: double `POST /review-flag` from same or different analysts — create two queue rows (no idempotency key required, v1); flagging a memory from another workspace must 404.
- [ ] Encrypted rows: `content_search` NULL and `key_id` set → keyword filter falls back to `content ILIKE` *after* decryption (or returns no match if decryption fails); search must work over `content_search` when present to exploit GIN index.
- [ ] Tenant boundary: `client_id`/`agent_id` scoping from `Memory` must be respected (AC-18.6 pattern). Default to `Memory.client_id.is_(None)` for regular workspace analysts; superadmin/vertical clients may pass `client_id` filter.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] `MemoryEncryptionService.decrypt_memory` throws `DecryptionError` → return 500 with error code `decryption_failed` (do not render raw error message to UI).
- [ ] `MemoryEncryptionService.decrypt_memory_version` throws for version rows → detail panel returns 500, row must not be partially rendered with mixed plaintext/ciphertext.
- [ ] `NotificationService.create_notification` fails → flag creation should rollback as part of same DB transaction (flag + notification atomic).
- [ ] `WorkspaceMembership` creator query empty → UI shows empty creator dropdown and filter is disabled.
- [ ] `check_permission` returns 403 for `MEMORY_READ` → route shows access-denied, nav item hidden/visible depending on permission.
- [ ] `GET /memories/{id}` with mismatched workspace → 404 (not 403) to avoid existence leak.
- [ ] `MemoryRelation.to_memory_id` points to deleted `Memory` → detail panel renders relation without target link.

### Triage
- **Critical:** None. No duplicate, no cheaper alternative that eliminates the spec.
- **Non-critical gaps to fold into ATDD:** boundary validation, encryption fallback behavior, `client_id` scoping, notification transactionality, dangling relation handling.
- **Action:** Proceed to `bmad-nowing-test-first-atdd`.
