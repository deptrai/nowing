# ATDD Checklist — 29-5-memory-browser-research-timeline-for-analyst

Test description skeleton for Story 29.5. Titles only — no `assert` bodies yet.
Merged edge cases/failure modes from `Challenge Log (grill-me)` in story file.

---

## AC-1 — Workspace-Scoped Memory List

### Pattern 1 (Mirror Test)
- [ ] should return `items` with exactly `{id, content_snippet, source_type, source_url, confidence, created_at, updated_at, created_by {id, email}, version_count, flag_status}` per row
- [ ] should return `total`, `page`, `page_size` fields on list response
- [ ] should NOT return `content` full text in list items (only `content_snippet` truncated to N chars)
- [ ] should NOT return `embedding`, `content_search`, `key_id`, `encryption_iv`, `encryption_algo` in list items
- [ ] should derive `source_url` from `source_run_id` → `run_<uuid>` citation pattern, or `/leads/{source_uuid}` when `source_entity_type='lead'`
- [ ] should set `flag_status='open'` when open `memory_review_queue` row exists, else `null`/`none`
- [ ] should set `version_count` = count of `MemoryVersion` rows for that memory

### Pattern 2 (Over-Mocking)
- [ ] should handle `MemoryEncryptionService.decrypt_memory` throwing `DecryptionError` → return 500 `decryption_failed`
- [ ] should handle `get_async_session` returning broken session → 500 (FastAPI dependency failure)

### Pattern 3 (Happy Path Only)
- [ ] Boundary: `page_size=25` returns exactly 25 items; `page_size=100` max accepted; `page_size=101` → 422
- [ ] Boundary: `page=1` first page; `page=0` → 422; `page=-1` → 422; `page` beyond total → empty `items` with `total` preserved
- [ ] Null/empty: workspace with zero memories → `items=[]`, `total=0`
- [ ] Concurrent: two simultaneous list requests → consistent results (read committed isolation)
- [ ] Tenant: `workspace_id` in path vs `Memory.workspace_id` mismatch → list only returns matching rows (no cross-tenant)

### Pattern 4 (Arithmetic)
- [ ] should compute `total` as exact count of matching non-archived memories (verify with 5 seeded rows)
- [ ] should compute `version_count` as exact count (verify with 3 versions on one memory)

### Pattern 5 (Error Message)
- [ ] should return 403 with error detail "You don't have permission" when user lacks `memory:read`
- [ ] should return 403 "You don't have access to this workspace" for non-member

### Pattern 6 (SQL — integration, @pytest.mark.integration)
- [ ] should execute `SELECT ... WHERE workspace_id = ?` — no cross-workspace rows returned (integration, real DB)
- [ ] should use `ix_memories_browser_list` index for `(workspace_id, source_type, confidence, created_at DESC)` query (EXPLAIN check optional)
- [ ] should exclude `archived_at IS NOT NULL` rows by default

---

## AC-2 — Filters & Search

### Pattern 1 (Mirror)
- [ ] should accept `source_type` as single value or comma-separated list → maps to `Memory.source_type.in_(...)`
- [ ] should accept `confidence_min`/`confidence_max` query params → maps to `confidence >= min AND confidence <= max`
- [ ] should accept `created_after`/`created_before` ISO timestamps → maps to `created_at >= since AND created_at <= until`
- [ ] should accept `created_by` UUID → maps to `Memory.created_by_id == user_uuid`
- [ ] should accept `keyword` query param → maps to tsvector `@@` on `to_tsvector('english', content)`
- [ ] should accept `sort` param values `created_at`, `confidence`, `updated_at` with `asc`/`desc`
- [ ] should return only `MemorySourceType` enum values in `source_type` filter validation → invalid value → 422

### Pattern 3 (Edge cases)
- [ ] Boundary: `confidence_min=0.0` / `confidence_max=1.0` include boundary values
- [ ] Boundary: `confidence_min > confidence_max` → 422 validation error
- [ ] Null/empty: `keyword=''` or whitespace → treated as no keyword filter (no tsquery)
- [ ] Null/empty: `created_by` invalid UUID format → 422
- [ ] Encrypted rows: `keyword` filter on encrypted row with `content_search IS NULL` → falls back to `content ILIKE` post-decryption or returns no match

### Pattern 6 (SQL — integration)
- [ ] should execute tsvector `@@` query against `ix_memories_content_search` index (EXPLAIN shows GIN index scan)
- [ ] should filter `source_type IN ('SCRAPER_RUN','DOCUMENT')` correctly (integration, real DB)
- [ ] should filter `confidence BETWEEN 0.5 AND 0.9` correctly (integration)
- [ ] should filter `created_by` = specific user UUID correctly (integration)
- [ ] should combine multiple filters with AND semantics (e.g. `source_type=SCRAPER_RUN` + `confidence_min=0.8` + `created_after=7d`)

---

## AC-3 — Memory Detail Panel

### Pattern 1 (Mirror)
- [ ] should return full `content` (decrypted) for `key_id IS NULL` or valid key
- [ ] should return `source_url` derived: `source_run_id` → `/dashboard/{ws}/runs/{id}`; `source_uuid` + `entity_type='lead'` → `/dashboard/{ws}/leads/{uuid}`; `source_id` → `chat_message:{id}` badge
- [ ] should return `versions` array ordered by `created_at` ascending
- [ ] should return `research_thread` object with `id`, `title`, `memory_ids` in chronological order
- [ ] should return `relations` array with `{relation_type, to_memory_id, weight}` — NULL `to_memory_id` rendered without link
- [ ] should NOT return `embedding` vector in detail response

### Pattern 2 (Over-Mocking)
- [ ] should handle `MemoryEncryptionService.decrypt_memory` throwing → 500 `decryption_failed`
- [ ] should handle `MemoryEncryptionService.decrypt_memory_version` throwing on one version → 500 (no partial render)

### Pattern 3 (Edge cases)
- [ ] Null/empty: `research_thread_id` NULL → `research_thread` field is `null`
- [ ] Null/empty: `MemoryVersion.corrected_by_id` NULL → `corrected_by` = `null` or "unknown"
- [ ] Null/empty: `source_run_id`/`source_uuid`/`source_id` all NULL → `source_url` = `null`, badge = `source_type`
- [ ] Dangling: `MemoryRelation.to_memory_id` references deleted memory → relation still listed, `to_memory` fields null

### Pattern 6 (SQL — integration)
- [ ] should join `MemoryVersion` correctly and return all versions for memory (integration)
- [ ] should join `MemoryRelation` correctly for both `from_memory_id` and `to_memory_id` directions (integration)
- [ ] should join `ResearchThread` and return `title` when `research_thread_id` set (integration)
- [ ] should 404 when `memory_id` belongs to different `workspace_id` (integration — existence leak check)

---

## AC-4 — Research Timeline View

### Pattern 1 (Mirror)
- [ ] should group memories by `research_thread_id`, each group has `{thread_id, title, memories[]}`
- [ ] should order threads by `MAX(created_at)` desc or `MIN(created_at)` asc (spec: chronological within thread)
- [ ] should return `title` as "Untitled thread #{id}" when `ResearchThread.title` is NULL
- [ ] should mark memories with `MemoryRelation` `DERIVED_FROM`/`CORRECTS` as branch/merge indicators

### Pattern 3 (Edge cases)
- [ ] Null/empty: workspace with no `ResearchThread` → timeline returns `threads=[]`
- [ ] Null/empty: `ResearchThread.title` is NULL or empty string → fallback "Untitled thread #{id}"
- [ ] Edge: memory with `research_thread_id` pointing to thread in different workspace → excluded from timeline

### Pattern 6 (SQL — integration)
- [ ] should scope `ResearchThread` join by `workspace_id` (integration)
- [ ] should order memories within each thread by `created_at` ascending (integration)

---

## AC-5 — Flag for Review

### Pattern 1 (Mirror)
- [ ] should create `memory_review_queue` row with `{memory_id, workspace_id, flag_reason, flagged_by, status='open'}`
- [ ] should return `201 Created` with the created `MemoryReviewQueue` object
- [ ] should call `NotificationService.create_notification` with `notification_type='memory_review_flag'`, `workspace_id`, `metadata={memory_id, flag_reason}`
- [ ] should NOT modify the `Memory` row (no auto-delete, no archive, no rewrite)

### Pattern 2 (Over-Mocking)
- [ ] should handle `NotificationService.create_notification` throwing → flag creation rolls back (atomic transaction)

### Pattern 3 (Edge cases)
- [ ] Null/empty: `flag_reason` empty string → 422 validation error
- [ ] Null/empty: `flag_reason` whitespace-only → 422 validation error
- [ ] Boundary: `flag_reason` max length (e.g. 2000 chars) accepted; >2000 → 422
- [ ] Concurrent: two analysts flag same memory simultaneously → two separate `memory_review_queue` rows (no dedup in v1)
- [ ] Tenant: flag on memory from different workspace → 404 (not 403)

### Pattern 5 (Error Message)
- [ ] should return 403 "You don't have permission" when user has `memory:read` only (no `memory:update`)
- [ ] should return 404 "Memory not found" for non-existent `memory_id` in workspace

### Pattern 6 (SQL — integration)
- [ ] should insert row into `memory_review_queue` table with correct FK values (integration, real DB)
- [ ] should create `Notification` row with `type='memory_review_flag'` for Owner/Editor members (integration)
- [ ] should rollback both queue row and notification if either fails (transaction atomicity)

---

## AC-6 — Permission Boundary

### Pattern 3 (Edge cases)
- [ ] `memory:read` user calls `POST /review-flag` → 403
- [ ] `memory:read` user calls `DELETE /memories/{id}` → 403 (existing route)
- [ ] Non-member calls `GET /memories` → 403 "You don't have access to this workspace"
- [ ] `Viewer` role (has `memory:read`) can list but cannot flag
- [ ] `Editor` role (has `memory:read` + `memory:update`) can list and flag

### Pattern 5 (Error Message)
- [ ] 403 response includes error detail string (not bare status)
- [ ] 404 vs 403: cross-workspace memory access returns 404 to avoid existence leak

---

## AC-7 — Accessibility & Navigation

### Pattern 1 (Mirror)
- [ ] should render "Memory Browser" nav item in sidebar when user has `memory:read`
- [ ] should mark nav item `isActive` when `pathname.includes('/memory-browser')`
- [ ] should have `aria-label` on confidence slider, source chips, flag button, pagination controls
- [ ] should support keyboard: Arrow keys navigate list rows, Enter opens detail, Escape closes panel

### Pattern 3 (Edge cases)
- [ ] `memory:read` user sees nav item; user without `memory:read` does not see it (or sees disabled)
- [ ] Screen reader announces row count and current page

---

## Cross-cutting / Integration-level

### Pattern 6 (SQL — integration, real Postgres)
- [ ] `memory_review_queue` table exists after migration with correct columns and FKs
- [ ] `ix_memories_browser_list` index exists after migration on `memories (workspace_id, source_type, confidence, created_at DESC)`
- [ ] `ON DELETE SET NULL` on `memory_review_queue.memory_id` works (deleting memory does not delete queue row)
- [ ] `ON DELETE CASCADE` on `memory_review_queue.workspace_id` works (deleting workspace cleans up queue)
- [ ] Full flow: list → filter → detail → flag → verify queue row + notification (end-to-end integration)
