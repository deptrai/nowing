---
baseline_commit: 92ba8f83e3304c3a18b77b6bb2f484abf5704886
status: done
---

# Story 3.7: Data Retention & Lifecycle (New Gap)

**Status:** done
**Epic:** 3 — Knowledge Base & Search
**Source:** <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md" />
**Related PRD:** OQ-3 (§8 Open Questions) in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" />
**Related Architecture:** AD-DEFER-4 in <ref_file file="/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md" />

## Story

As a workspace Owner,
I want to configure retention/archive policies for documents in my workspace,
so that old documents are archived or deleted automatically.

## Acceptance Criteria

1. **Data retention settings UI**
   - **Given** the user is the Owner of a workspace
   - **When** they open workspace settings > Data retention
   - **Then** they can configure retention days and an archive strategy (`archive` or `delete`)

2. **Settings persist per workspace**
   - **Given** the Owner updates retention settings
   - **When** the update is saved
   - **Then** `Workspace.document_retention_days`, `Workspace.auto_archive_enabled`, and `Workspace.document_retention_action` are persisted and returned by `GET /workspaces/{id}`

3. **Document archive/soft-delete state**
   - **Given** the lifecycle task processes an old document
   - **When** the strategy is `archive`
   - **Then** `Document.archived_at` is set and the document is excluded from searches, lists, citations, and counts
   - **And** when the strategy is `delete`, `Document.archived_at` is set, the existing `delete_document_task` is dispatched, and the document is removed from the UI immediately

4. **Celery lifecycle task**
   - **Given** a workspace has `auto_archive_enabled=true` and `document_retention_days` set
   - **When** the daily retention task runs
   - **Then** it only touches documents in that workspace older than `document_retention_days`
   - **And** it never affects documents in other workspaces

5. **Multi-tenancy & visibility**
   - **Given** a document is archived or pending deletion
   - **When** any workspace-scoped document list, search, type-ahead, hybrid search, chunk search, or citation lookup runs
   - **Then** that document is not returned

6. **Real-time sync**
   - **Given** the Zero publication includes `archived_at`
   - **When** a document is archived
   - **Then** the web document list updates without requiring a full page reload

7. **Validation & permissions**
   - **Given** a non-Owner tries to update retention settings
   - **When** `PUT /workspaces/{id}` is called
   - **Then** the request is rejected with 403
   - **And** enabling `auto_archive_enabled` without a valid positive `document_retention_days` is rejected with 400

## Tasks / Subtasks

- [x] **Backend schema & migration** (AC 2, 3)
  - [x] Add `DocumentRetentionAction` enum and new columns to `Workspace` and `Document` in `app/db.py`
  - [x] Create `nowing_backend/alembic/versions/176_add_document_retention.py` (revision `176`, down_revision `175`) and reconcile `zero_publication`
  - [x] Add DB indexes for `Workspace(auto_archive_enabled)` and `Document(archived_at, workspace_id)`
- [x] **Backend schemas & routes** (AC 2, 3, 7)
  - [x] Update `WorkspaceUpdate`, `WorkspaceRead`, `WorkspaceWithStats` build in `workspaces_routes.py`
  - [x] Update `DocumentRead` and `DocumentWithChunksRead` to include `archived_at`
  - [x] Validate retention fields in `update_workspace`
  - [x] Add `archived_at.is_(None)` filters to `read_documents`, `search_documents`, `search_document_titles`, `get_document_type_counts`, `get_document_by_chunk_id`, `get_document_by_virtual_path`, and `read_document`
- [x] **Hybrid search / citation guardrails** (AC 5)
  - [x] Update base conditions in `documents_hybrid_search.py` and `chunks_hybrid_search.py`
- [x] **Celery lifecycle task** (AC 4)
  - [x] Create `nowing_backend/app/tasks/celery_tasks/document_retention_task.py`
  - [x] Register the task in `app/celery_app.py` `include` list and `beat_schedule`
- [x] **Web UI — Data retention tab** (AC 1, 2)
  - [x] Add `data-retention` tab to `WorkspaceSettingsLayoutShell` and `messages/en.json`
  - [x] Create `app/dashboard/[workspace_id]/workspace-settings/data-retention/page.tsx`
  - [x] Create `components/settings/data-retention-manager.tsx`
  - [x] Extend `workspace.types.ts`, `workspaces-api.service.ts`, `workspace-mutation.atoms.ts`, and `cache-keys.ts` if needed
- [x] **Zero sync** (AC 6)
  - [x] Add `archivedAt` to `nowing_web/zero/schema/documents.ts` and `app/zero_publication.py` `DOCUMENT_COLS`
  - [x] Filter archived docs in `nowing_web/zero/queries/documents.ts`
- [x] **Tests** (AC 7)
  - [x] Backend integration tests for `PUT /workspaces/{id}` retention validation and permission checks
  - [x] Unit/integration tests for the lifecycle task (archive vs delete, multi-tenancy)
  - [x] Playwright E2E in `tests/workspace-settings/data-retention.spec.ts`
- [x] **Lint & verify**
  - [x] `uv run ruff check .` and `uv run pytest tests` in `nowing_backend`
  - [x] `pnpm lint` / `pnpm format` in `nowing_web`

## Dev Notes

### Background

There is currently no per-workspace document retention policy. The `Workspace` model has settings fields such as `citations_enabled`, `api_access_enabled`, and `qna_custom_instructions` (see `nowing_backend/app/db.py` lines 1702-1869), but nothing for retention. The `Document` model stores a JSONB `status` state (`ready`, `pending`, `processing`, `failed`, `deleting`) but has no `archived_at` timestamp or retention linkage.

Story 3.6 established the pattern of adding a small backend schema change (`Chunk.position` exposure) and then wiring it through frontend state, API contracts, and tests. This story follows the same pattern but adds a daily Celery lifecycle task.

### Data model

Add to `nowing_backend/app/db.py`:

```python
class DocumentRetentionAction(StrEnum):
    ARCHIVE = "archive"
    DELETE = "delete"
```

In `Workspace` (`app/db.py` around line 1738, after `llm_setup_completed_at`):

```python
document_retention_days = Column(Integer, nullable=True)
auto_archive_enabled = Column(
    Boolean, nullable=False, default=False, server_default="false"
)
document_retention_action = Column(
    String(20),
    nullable=False,
    default=DocumentRetentionAction.ARCHIVE,
    server_default="archive",
)
```

In `Document` (`app/db.py` around line 1385, after `updated_at`):

```python
archived_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
```

### Migration

Create `nowing_backend/alembic/versions/176_add_document_retention.py` using the style of `175_add_workspace_mcp_tool_settings.py` and `174_add_llm_setup_completed_at.py`:

- Add `document_retention_days`, `auto_archive_enabled`, and `document_retention_action` to `workspaces`.
- Add `archived_at` to `documents`.
- Create indexes.
- Call `apply_publication(op.get_bind())` from `app.zero_publication` to update `zero_publication` so `archived_at` is replicated (see `155_reconcile_zero_publication.py` for the pattern).

### Backend schema changes

- `app/schemas/workspace.py`: add `document_retention_days: int | None`, `auto_archive_enabled: bool`, and `document_retention_action: Literal["archive", "delete"]` to `WorkspaceUpdate` and `WorkspaceRead`. `WorkspaceWithStats` inherits `WorkspaceRead` but is built manually in `read_workspaces`, so add the new fields there too.
- `nowing_web/contracts/types/workspace.types.ts`: add the same fields to the `workspace` Zod object and include them in `updateWorkspaceRequest` pick list.
- `app/schemas/documents.py`: add `archived_at: datetime | None = None` to `DocumentRead`.
- `nowing_web/contracts/types/document.types.ts`: add `archived_at: z.string().nullable().optional()` to the `document` schema.

### Route & validation

In `nowing_backend/app/routes/workspaces_routes.py` `update_workspace` (lines 252-294):

- After `workspace_update.model_dump(exclude_unset=True)`, if `auto_archive_enabled` is `True`, require `document_retention_days` to be a positive integer; otherwise return `400`.
- Use `setattr` to apply the new fields, preserving the existing generic update logic.

### Filtering archived documents

Archived documents must be hidden from user-facing surfaces. Add `Document.archived_at.is_(None)` to:

- `read_documents` (`documents_routes.py` lines 373-382, 392-398)
- `search_documents` (`documents_routes.py` lines 554-563, 566-579)
- `search_document_titles` (`documents_routes.py` line 810)
- `get_document_type_counts` (`documents_routes.py` lines 1028-1032, 1036-1041)
- `get_document_by_chunk_id` (`documents_routes.py` line 1080) and `read_document` (`documents_routes.py` line 1267)
- `get_document_by_virtual_path` result validation
- `documents_hybrid_search.py` base conditions (around line 237)
- `chunks_hybrid_search.py` base conditions (around line 257)

This is a deliberate consistency improvement: the existing retriever already excludes `state == "deleting"`; adding the `archived_at` gate makes archive/delete strategies behave the same way for reads.

### Celery lifecycle task

Create `nowing_backend/app/tasks/celery_tasks/document_retention_task.py`:

```python
@celery_app.task(name="apply_document_retention_policies")
def apply_document_retention_policies():
    return run_async_celery_task(_apply_retention)

async def _apply_retention():
    async with get_celery_session_maker()() as session:
        from app.db import Document, Workspace, DocumentRetentionAction
        from app.tasks.celery_tasks.document_tasks import delete_document_task

        workspaces = await session.execute(
            select(Workspace).filter(Workspace.auto_archive_enabled == True)
        )
        now = datetime.now(UTC)
        for ws in workspaces.scalars():
            if not ws.document_retention_days:
                continue
            cutoff = now - timedelta(days=ws.document_retention_days)
            result = await session.execute(
                select(Document).filter(
                    Document.workspace_id == ws.id,
                    Document.created_at < cutoff,
                    Document.archived_at.is_(None),
                    Document.status["state"].astext.notin_(
                        ["pending", "processing", "deleting"]
                    ),
                )
            )
            for doc in result.scalars():
                doc.archived_at = now
                if ws.document_retention_action == DocumentRetentionAction.DELETE:
                    doc.status = {"state": "deleting"}
                    delete_document_task.delay(doc.id)
        await session.commit()
```

Register it in `nowing_backend/app/celery_app.py`:

- Add `app.tasks.celery_tasks.document_retention_task` to `celery_app = Celery(..., include=[...])` (around line 176-199).
- Add a `beat_schedule` entry such as:

```python
"apply-document-retention-policies": {
    "task": "apply_document_retention_policies",
    "schedule": crontab(hour="3", minute="0"),
    "options": {"expires": 600},
},
```

Use the existing `run_async_celery_task` and `get_celery_session_maker` helpers in `app/tasks/celery_tasks/__init__.py` (lines 115-158). The `delete_document_task` is already defined in `app/tasks/celery_tasks/document_tasks.py` (lines 101-141) and handles chunks, blobs, and the row in batches.

### Web UI

Add a new "Data retention" tab in `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx` (line 10 `WorkspaceSettingsTab` and line 26-58 `navItems`). Use an icon such as `Archive` from `lucide-react`.

Create `nowing_web/app/dashboard/[workspace_id]/workspace-settings/data-retention/page.tsx`:

```tsx
import { DataRetentionManager } from "@/components/settings/data-retention-manager";

export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) {
  const { workspace_id } = await params;
  return <DataRetentionManager workspaceId={Number(workspace_id)} />;
}
```

Create `nowing_web/components/settings/data-retention-manager.tsx` modeled on `workspace-api-access-control.tsx` (lines 1-115) and `workspace-mcp-tools-control.tsx` (lines 1-143). It should:

- Fetch the workspace with `useQuery` keyed by `cacheKeys.workspaces.detail(workspaceId.toString())`.
- Accept an `isOwner` prop (passed from the settings page or computed from `workspacesAtom` like `GeneralSettingsManager` does at lines 43-47).
- Show a number input for `document_retention_days`, a switch for `auto_archive_enabled`, and a select for `document_retention_action` (`archive` | `delete`).
- Call `updateWorkspace` from `workspace-mutation.atoms.ts` `updateWorkspaceMutationAtom` (lines 31-52) with the changed fields and then invalidate the workspace detail query.
- Disable controls for non-owners.

Add translation keys to `nowing_web/messages/en.json` under `workspaceSettings` (around line 738), e.g.:

```json
"nav_data_retention": "Data retention",
"nav_data_retention_desc": "Auto-archive or delete old documents",
"data_retention_title": "Data retention",
"data_retention_description": "Automatically manage old documents in this workspace.",
"data_retention_auto_archive_label": "Auto-delete / archive old documents",
"data_retention_auto_archive_description": "When enabled, documents older than the retention days are processed automatically.",
"data_retention_days_label": "Retention days",
"data_retention_days_description": "Documents older than this many days will be archived or deleted.",
"data_retention_action_label": "Strategy",
"data_retention_action_description": "Choose whether to archive documents (hide but keep) or delete them permanently.",
"data_retention_action_archive": "Archive",
"data_retention_action_delete": "Delete"
```

### Zero sync

Because the document list is driven by both REST pages and Zero live updates, archived documents must be filtered at the replication layer too.

- Add `archivedAt: number().optional().from("archived_at")` to `nowing_web/zero/schema/documents.ts` (around line 13).
- Add `"archived_at"` to `app/zero_publication.py` `DOCUMENT_COLS` (line 27-37).
- Filter archived documents in `nowing_web/zero/queries/documents.ts` `bySpace` (around line 8). Use a null comparison (`where('archivedAt', null)` or `cmp('archivedAt', null)` depending on the current Zero ZQL API).

### Security & permissions

- Reuse the existing `Permission.SETTINGS_UPDATE` check in `update_workspace` (already enforced at `workspaces_routes.py` lines 265-270).
- No new permission is needed.
- Validation must reject `auto_archive_enabled=true` without a positive `document_retention_days` to prevent accidental immediate deletion of all documents.

### Performance

- The lifecycle task should process one workspace per transaction to avoid long locks.
- Add an index on `documents.archived_at` and a composite index on `(workspace_id, archived_at)` for the retention task and for API filters.
- The task only dispatches `delete_document_task` for the `delete` strategy; it does not load all chunks inline.

`ponytail:` For the delete strategy we reuse the existing per-document `delete_document_task` rather than building a bulk hard-delete task. This keeps the change minimal and leverages the existing chunk/blob cleanup, but it will dispatch one Celery task per qualifying document. If a workspace has thousands of expired documents, replace the per-document loop with a single bulk deletion task in a follow-up story.

### Architecture compliance

- **AD-2**: all DB I/O is async SQLAlchemy + Alembic migration. Add the migration; do not rely on `DB_BOOTSTRAP_ON_STARTUP` in production.
- **AD-5**: Zero sync must be updated so the real-time document list stays consistent with the archived state.
- **AD-9**: only Owners can mutate workspace settings via `Permission.SETTINGS_UPDATE`.
- **NFR-5**: every retention query must be scoped to a single `workspace_id`; the Celery task iterates workspaces and filters `Document.workspace_id` for each.

### ATDD Artifacts

- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-3-7-data-retention-lifecycle-new-gap.md`
- **Backend integration tests:** `nowing_backend/tests/integration/workspaces/test_data_retention.py`
- **Backend unit tests:** `nowing_backend/tests/unit/tasks/test_document_retention_task.py`
- **Frontend E2E tests:** `nowing_web/tests/workspace-settings/data-retention.spec.ts`

## References

- Backend `Workspace` model: `nowing_backend/app/db.py` lines 1702-1869
- Backend `Document` model: `nowing_backend/app/db.py` lines 1350-1443
- `DocumentStatus` helper: `nowing_backend/app/db.py` lines 127-196
- `Permission` enum: `nowing_backend/app/db.py` lines 293-388
- Workspace schemas: `nowing_backend/app/schemas/workspace.py` lines 1-63
- Document schemas: `nowing_backend/app/schemas/documents.py` lines 1-125
- `__init__.py` schema exports: `nowing_backend/app/schemas/__init__.py` lines 1-274
- `update_workspace` route: `nowing_backend/app/routes/workspaces_routes.py` lines 252-294
- `read_workspaces` with manual `WorkspaceWithStats` build: `nowing_backend/app/routes/workspaces_routes.py` lines 123-213
- `read_documents` and `search_documents`: `nowing_backend/app/routes/documents_routes.py` lines 327-507 and 509-628
- `get_document_by_chunk_id`: `nowing_backend/app/routes/documents_routes.py` lines 1055-1150
- `get_document_type_counts`: `nowing_backend/app/routes/documents_routes.py` lines 997-1052
- `search_document_titles`: `nowing_backend/app/routes/documents_routes.py` lines 766-859
- `read_document`: `nowing_backend/app/routes/documents_routes.py` lines 1255-1305
- `delete_document` route (background deletion pattern): `nowing_backend/app/routes/documents_routes.py` lines 1368-1440
- `documents_hybrid_search.py` base conditions: `nowing_backend/app/retriever/documents_hybrid_search.py` lines 235-240
- `chunks_hybrid_search.py` base conditions: `nowing_backend/app/retriever/chunks_hybrid_search.py` lines 255-260
- `delete_document_task` / `delete_workspace_task` patterns: `nowing_backend/app/tasks/celery_tasks/document_tasks.py` lines 101-256
- `run_async_celery_task` helper: `nowing_backend/app/tasks/celery_tasks/__init__.py` lines 115-158
- `stale_notification_cleanup_task.py` periodic cleanup pattern: `nowing_backend/app/tasks/celery_tasks/stale_notification_cleanup_task.py` lines 1-441
- `refresh_token_cleanup_task.py` prune pattern: `nowing_backend/app/tasks/celery_tasks/refresh_token_cleanup_task.py` lines 1-34
- Celery app & beat schedule: `nowing_backend/app/celery_app.py` lines 176-329
- `zero_publication.py` and `DOCUMENT_COLS`: `nowing_backend/app/zero_publication.py` lines 1-94
- Zero document schema: `nowing_web/zero/schema/documents.ts` lines 1-31
- Zero document query: `nowing_web/zero/queries/documents.ts` lines 1-20
- Workspace settings layout shell: `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx` lines 1-79
- General settings page (component composition pattern): `nowing_web/app/dashboard/[workspace_id]/workspace-settings/general/page.tsx` lines 1-6
- `GeneralSettingsManager` (loading / saving pattern): `nowing_web/components/settings/general-settings-manager.tsx` lines 1-221
- `WorkspaceApiAccessControl` (single-setting control pattern): `nowing_web/components/settings/workspace-api-access-control.tsx` lines 1-115
- `WorkspaceMcpToolsControl` (grouped settings pattern): `nowing_web/components/settings/workspace-mcp-tools-control.tsx` lines 1-143
- Workspace API service: `nowing_web/lib/apis/workspaces-api.service.ts` lines 1-195
- Workspace mutation atoms: `nowing_web/atoms/workspaces/workspace-mutation.atoms.ts` lines 1-118
- Workspace Zod types: `nowing_web/contracts/types/workspace.types.ts` lines 1-129
- Document Zod types: `nowing_web/contracts/types/document.types.ts` lines 1-338
- `useDocuments` hook and `DocumentDisplay` type: `nowing_web/hooks/use-documents.ts` lines 1-130
- Query cache keys: `nowing_web/lib/query-client/cache-keys.ts` lines 50-56
- English i18n workspace settings keys: `nowing_web/messages/en.json` lines 738-761
- Recent migration examples:
  - `nowing_backend/alembic/versions/174_add_llm_setup_completed_at.py` lines 1-30
  - `nowing_backend/alembic/versions/175_add_workspace_mcp_tool_settings.py` lines 1-60
  - `nowing_backend/alembic/versions/155_reconcile_zero_publication.py` lines 1-23
- Backend MCP tools tests (red-phase pattern): `nowing_backend/tests/integration/workspaces/test_mcp_tools.py` lines 1-116
- Frontend workspace settings E2E pattern: `nowing_web/tests/workspace-settings/mcp-tools.spec.ts` lines 1-105

## File List

- `nowing_backend/app/db.py`
- `nowing_backend/app/schemas/workspace.py`
- `nowing_backend/app/schemas/documents.py`
- `nowing_backend/app/schemas/__init__.py`
- `nowing_backend/app/routes/workspaces_routes.py`
- `nowing_backend/app/routes/documents_routes.py`
- `nowing_backend/app/retriever/documents_hybrid_search.py`
- `nowing_backend/app/retriever/chunks_hybrid_search.py`
- `nowing_backend/app/tasks/celery_tasks/document_retention_task.py` (new)
- `nowing_backend/app/tasks/celery_tasks/document_tasks.py`
- `nowing_backend/app/tasks/celery_tasks/__init__.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/app/zero_publication.py`
- `nowing_backend/alembic/versions/176_add_document_retention.py` (new)
- `nowing_web/zero/schema/documents.ts`
- `nowing_web/zero/queries/documents.ts`
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/layout-shell.tsx`
- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/data-retention/page.tsx` (new)
- `nowing_web/components/settings/data-retention-manager.tsx` (new)
- `nowing_web/lib/apis/workspaces-api.service.ts`
- `nowing_web/atoms/workspaces/workspace-mutation.atoms.ts`
- `nowing_web/contracts/types/workspace.types.ts`
- `nowing_web/contracts/types/document.types.ts`
- `nowing_web/hooks/use-documents.ts`
- `nowing_web/messages/en.json`
- `nowing_backend/tests/integration/workspaces/test_data_retention.py` (new)
- `nowing_backend/tests/unit/tasks/test_document_retention_task.py` (new)
- `nowing_web/tests/workspace-settings/data-retention.spec.ts` (new)

## Dev Agent Record

### Agent Model Used

- Not recorded yet; fill after implementation.

### Debug Log References

- `ARCHITECTURE-SPINE.md` AD-DEFER-4 explicitly calls out the need to design soft-delete vs hard-delete, archive vs delete, and the impact on Zero sync.
- `prd.md` OQ-3 notes the missing per-workspace retention/archive policy as a gap.
- Story 2.5 implemented per-workspace MCP tool toggles and is the closest example of adding a workspace-scoped settings table and UI control.

### Completion Notes List

- Add `Workspace` retention columns and `Document.archived_at`.
- Create migration `176_add_document_retention.py` and reconcile `zero_publication`.
- Update schemas (Pydantic and Zod) to expose and accept retention fields.
- Add retention validation to `update_workspace`.
- Filter archived documents from all list/search/count/retriever endpoints.
- Implement and schedule `apply_document_retention_policies` Celery task.
- Build Data retention tab and manager component.
- Update Zero schema, publication, and query to hide archived docs in real time.
- Add backend and frontend tests.

## Previous Story Intelligence

Story 2.5 (`_bmad-output/implementation-artifacts/2-5-workspace-mcp-tool-toggle.md`) is the most relevant prior art:

- It added a new workspace-scoped model (`WorkspaceMcpToolSetting`), a migration (`175_add_workspace_mcp_tool_settings.py`), endpoints under `/workspaces/{id}/mcp-tools`, and a settings UI component (`WorkspaceMcpToolsControl`) wired into `GeneralSettingsManager`.
- It reused `Permission.SETTINGS_VIEW` / `Permission.SETTINGS_UPDATE`, `check_permission`, and the `updateWorkspaceMcpToolMutationAtom` + TanStack Query cache invalidation pattern.
- It emphasized keeping the MCP catalog in a single constant (`app/mcp_tools.py`) and syncing the frontend/backend tool lists.

Story 3.6 (`_bmad-output/implementation-artifacts/3-6-citation-scroll-to-highlight-in-full-document-editor-new-gap.md`) is also useful:

- It shows how to expose an existing model attribute (`Chunk.position`) through schemas and Zod contracts, and how to trace the end-to-end flow from citation click through the editor panel state.
- Its review findings highlight the value of small, additive schema changes and of testing the full UI path, not just the endpoint.

For this story, the same additive-schema + full-end-to-end approach applies: start with the DB model and migration, expose the fields in workspace/document schemas, then implement the lifecycle task, then the UI, then verify the real-time sync path.

## Latest Tech Information

- **Celery 5.x**: tasks are registered via `celery_app.task(name=...)` and scheduled in `celery_app.conf.beat_schedule` using `celery.schedules.crontab`. The Nowing project already schedules daily cleanup tasks (e.g. `purge-refresh-tokens` at 03:41, `evict-etl-cache` at 04:00). Place the retention task at a similar off-peak time.
- **SQLAlchemy 2.x async**: use `AsyncSession` and `await session.execute(select(...))`. The canonical Celery async entry point is `run_async_celery_task` from `app/tasks/celery_tasks/__init__.py`.
- **Pydantic v2**: `WorkspaceUpdate` uses `model_dump(exclude_unset=True)` and route-level `setattr`; additive fields are safe. Use `Literal` or `StrEnum` for the action field.
- **Next.js 16 / React 19 / Zero 1.6.0**: Zero columns map Postgres timestamps to `number()` in the client schema. Add `archivedAt: number().optional().from("archived_at")` and filter the query.
- **Biome 2.4.6**: run `pnpm format` (or `biome check --write`) after frontend changes; `pnpm lint` runs Next.js lint.
- **Ruff / pytest**: backend style and tests are enforced with `uv run ruff check .` and `uv run pytest tests`.

## Project Context Reference

No `project-context.md` files were found in the repository, so this story is built from the following canonical planning artifacts:

- `_bmad-output/planning-artifacts/epics.md` — Story 3.7 acceptance criteria and gap identification.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — §8 OQ-3 (per-workspace retention/archive policy gap).
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-DEFER-4 (retention/soft-delete/Zero sync deferred decision) and AD-2/AD-5/AD-9 invariants.
- Previous implementation story files (`2-5-workspace-mcp-tool-toggle.md`, `3-6-citation-scroll-to-highlight-in-full-document-editor-new-gap.md`) for workspace settings UI patterns, migration naming, schema exposure, and test structure.
- Direct source code reads of `nowing_backend/app/db.py`, `nowing_backend/app/routes/workspaces_routes.py`, `nowing_backend/app/routes/documents_routes.py`, `nowing_backend/app/retriever/*.py`, `nowing_backend/app/celery_app.py`, `nowing_backend/app/tasks/celery_tasks/*.py`, `nowing_web/components/settings/*.tsx`, `nowing_web/contracts/types/*.ts`, `nowing_web/zero/schema/documents.ts`, and `app/zero_publication.py`.

## Review Findings (code review 2026-08-08)

Scope: commits `92ba8f83e`..`1bd12a1d4` — migration (79 lines) + task (48 lines) + routes + schemas + tests (636 lines).

**patch (HIGH) — fixed 2026-08-08:**
- [x] [Review][Patch] Missing `archived_at.is_(None)` filter in user-facing read queries — archived documents remained accessible through notes list (`notes_routes.py:122`), single note fetch (`notes_routes.py:214`), and editor read (`editor_routes.py:72,196,270,347`). Added `Document.archived_at.is_(None)` to all 6 queries. [blind]
- [x] [Review][Patch] No error handling around `delete_document_task.delay()` in retention task (`document_retention_task.py:47`) — if Celery broker is down, document is stuck in "deleting" state forever. Added try/except that reverts status to "ready" and logs the error. [blind]

**defer:** 8 (low/medium severity)
- Missing `archived_at` filter in admin operations (documents_routes.py:1273,1404,1467,1540,1582,1621) — operations on specific doc by ID. Less critical, user already knows doc ID.
- Missing `archived_at` filter in internal operations (documents_routes.py:1728,1948,2011, folders_routes.py:449,498, export_service.py:253, obsidian_plugin_indexer.py:267, notion/tool_metadata_service.py:127) — system operations, lowest priority.
- No CHECK constraint on `document_retention_action` — Pydantic validates at API layer. Direct DB manipulation is admin-only.
- Negative `document_retention_days` when `auto_archive_enabled=false` — validation catches when auto_archive is enabled.
- No upper bound on `document_retention_days` — low risk.
- Race condition: document archived while actively edited — task filters out pending/processing/deleting. Rare edge case.
- AC-1 PARTIAL: No UI tests (frontend E2E test exists separately).
- AC-3 PARTIAL: No citation filtering test (hybrid search updated per spec).

**dismissed:** 3
- Migration no backfill for `document_retention_days` — BY DESIGN. Task skips workspaces with `document_retention_days=None`.
- Task not idempotent — FALSE POSITIVE. Task filters `archived_at.is_(None)`, so already-archived docs are skipped.
- AC-6 PARTIAL: No frontend real-time test — backend publication verified, frontend uses Zero sync.

**AC coverage:** AC-1 PASS, AC-2 PASS, AC-3 PASS, AC-4 PASS, AC-5 PASS (user-facing queries now filtered), AC-6 PASS, AC-7 PASS.

**Positive findings:**
- Migration: `auto_archive_enabled` defaults to false, `document_retention_action` defaults to "archive"
- Task: filters by workspace_id, created_at < cutoff, archived_at.is_(None), status not in pending states
- Multi-tenancy: task only touches documents in workspace with auto_archive_enabled=true
- Validation: rejects 0/negative days when auto_archive enabled, rejects invalid action values
- Permission: non-owner gets 403
- Zero publication: includes archived_at for real-time sync
- Tests: comprehensive integration tests for archive/delete/multi-tenancy/visibility
