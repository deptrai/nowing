---
baseline_commit: 2fc8cf396635cae2ac73c7d0e38a5353b65e565b
---

# Story 21.13: Multi-Table Tabs & Send/Export Hub

Status: done

<!-- Note: Governed by epic21-architecture-update.md (AD-31 to AD-49) & ux-contract-lead-intelligence-panel.md -->

## Story

As a sales rep managing multiple target campaigns,
I want a browser-tabbed spreadsheet interface supporting multiple simultaneous lead tables with live Zero-cache sync and a multi-format Send/Export Hub (CSV, Lark Base, Google Sheets),
So that I can switch between property types, industries, and candidate lists without losing filter state, and easily export qualified leads to my team's CRM or spreadsheet.

## Acceptance Criteria

1. **Given** a workspace with multiple lead lists, **When** user opens the Lead Intelligence panel, **Then** the top toolbar renders scrollable tabs (`TableTabs`), persisting the active tab ID in the URL query parameter `?table={id}` with smooth tab switching.
2. **Given** the active table view, **When** backend scrapers or enrichment tasks stream new leads, **Then** Zero-cache (`zero.nowing.net`) updates the reactive table grid in real-time ($< 100$ms latency) without requiring a full page refresh.
3. **Given** table management actions, **When** user clicks `+ New Table`, renames, or deletes a tab, **Then** changes are persisted to `workspace_tables` in PostgreSQL with multi-tenancy `workspace_id` isolation and synchronized via Zero-cache.
4. **Given** qualified leads in the table, **When** clicking `Send & Export ⌄`, **Then** a dropdown modal offers:
   - `📥 Download CSV` (Immediate streaming file download with PII masking options).
   - `🚀 Sync to Lark Base` (1-click push to Lark Bitable with automated schema mapping).
   - `📊 Sync to Google Sheets` (Append to selected Google Spreadsheet via OAuth).
   - `🔗 Share Read-only Link` (Generate time-limited secure shareable link).
5. **Given** large export batches ($> 1,000$ rows), **When** exported to Lark Base or Google Sheets, **Then** Celery background workers process chunks of 500 rows with retry and idempotency header `X-Nowing-Sync-Id`, displaying a real-time progress toast on the UI.

## Tasks / Subtasks

- [x] Task 1: Database Schema & Zero-Cache Publication (AC: 1, 2, 3)
  - [x] 1.1 Tạo bảng `workspace_tables` trong `nowing_backend/app/db.py` (`id: UUID`, `workspace_id: Integer`, `name: String`, `icon: String`, `filter_preset: JSONB`, `columns_config: JSONB`, `created_at`, `updated_at`).
  - [x] 1.2 Thêm cột `table_id: UUID` (nullable FK to `workspace_tables.id`) vào bảng `leads`.
  - [x] 1.3 Tạo Alembic migration `alembic/versions/209_add_workspace_tables_and_lead_tab_fk.py`.
  - [x] 1.4 Đăng ký bảng `workspace_tables` vào `nowing_backend/app/zero_publication.py` với RLS filter `workspace_id`.
- [x] Task 2: REST APIs & Table Management Endpoints (AC: 1, 3)
  - [x] 2.1 Xây dựng `nowing_backend/app/routes/workspace_tables_routes.py` (`GET`, `POST`, `PATCH`, `DELETE /workspaces/{id}/tables`, `POST /workspaces/{id}/tables/{table_id}/assign-leads`, `POST /workspaces/{id}/leads/export`, `GET /workspaces/{id}/leads/export/jobs/{job_id}`).
  - [x] 2.2 Định nghĩa Pydantic schemas tại `nowing_backend/app/schemas/workspace_table.py`.
  - [x] 2.3 Đăng ký router vào `nowing_backend/app/routes/__init__.py`.
- [x] Task 3: Export Hub & Cloud Connectors (Lark Base & Google Sheets) (AC: 4, 5)
  - [x] 3.1 Xây dựng `ExportService` trong `nowing_backend/app/services/export_service.py` hỗ trợ CSV generation với PII redaction (`mask_pii: bool`, `mask_phone`, `mask_email`).
  - [x] 3.2 Xây dựng connector Lark Base tại `nowing_backend/app/connectors/lark_base.py` gọi Open API (`open.larksuite.com/open-apis/bitable/v1/apps/...`) với chunked batching.
  - [x] 3.3 Xây dựng connector Google Sheets tại `nowing_backend/app/connectors/google_sheets.py` qua Google Sheets v4 API (`sheets.googleapis.com/v4/spreadsheets/...:append`).
  - [x] 3.4 Tạo Celery async task `nowing_backend/app/tasks/lead_export_worker.py` xử lý batch sync kèm idempotency key `X-Nowing-Sync-Id`.
- [x] Task 4: Frontend Multi-Table Tabs & State Management (AC: 1, 2, 3)
  - [x] 4.1 Xây dựng component `nowing_web/components/leads/multi-table-tabs.tsx` với khả năng cuộn ngang, thêm tab mới, đổi icon và rename inline.
  - [x] 4.2 Đồng bộ active tab với Next.js 16 App Router search params (`useSearchParams` & `useRouter`).
  - [x] 4.3 Xây dựng `nowing_web/lib/hooks/use-workspace-tables.ts` và API service `nowing_web/lib/apis/workspace-tables-api.service.ts`.
- [x] Task 5: Frontend Send & Export Dropdown & Modal (AC: 4, 5)
  - [x] 5.1 Xây dựng component `nowing_web/components/leads/send-export-dropdown.tsx` với 4 lựa chọn (CSV, Lark, Sheets, Share).
  - [x] 5.2 Xây dựng modal cấu hình Lark Base / Google Sheets mapping trường dữ liệu (`FieldMappingModal.tsx`).
  - [x] 5.3 Tích hợp Toast notification hiển thị tiến độ xuất dữ liệu (`ExportProgressBar`).
  - [x] 5.4 Cập nhật `nowing_web/components/leads/LeadsContent.tsx` tích hợp Multi-table Tabs, Send/Export Hub và lọc theo tab.
- [x] Task 6: Testing & Quality Gates (AC: 1-5)
  - [x] 6.1 Unit tests: `tests/unit/routes/test_workspace_tables_routes.py` & `tests/unit/services/test_export_service.py` (10 tests passed).
  - [x] 6.2 Integration tests: `tests/integration/services/test_lark_base_sync.py` & `tests/integration/services/test_google_sheets_sync.py` (4 tests passed).
  - [x] 6.3 Typecheck & linter quality gates: `pnpm tsc --noEmit` & `pnpm exec biome check` (0 errors), `uv run ruff check` & `uv run ruff format` (0 errors).

### Review Findings

- [x] [Review][Patch] Add config JSONB column to ExportJob ORM model in db.py to align with Alembic migration 209 [`nowing_backend/app/db.py:4521`]

## Dev Notes

- **URL Preserved State:** Query parameter `?table={id}` được bảo toàn khi người dùng chuyển đổi tab hoặc tải lại trang.
- **Lark Base & Google Sheets Batching:** Dữ liệu lớn được chia thành các batch 500 dòng và xử lý qua Celery background worker kèm tracking status `ExportJob`.
- **PII Protection:** Tuân thủ Nghị định 13/2023/NĐ-CP: tự động che số điện thoại (`0908***456`, `+84908***456`) và email (`u***@domain.com`) khi bật chế độ PII Masking.

### References
- [Architecture Spine: epic21-architecture-update.md]
- [UX Design: _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md]
- [Mockup: _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/mockups/workspace-lead-intelligence.html]

## Dev Agent Record

### Implementation Summary
- **Database & Zero-Cache:** Added `WorkspaceTable` and `ExportJob` models to `app/db.py`, added `table_id` FK to `Lead`, registered `workspace_tables` in `app/zero_publication.py`, and created Alembic migration 209.
- **Backend APIs & Workers:** Added CRUD routes for workspace tables, lead assignment, and export triggering in `app/routes/workspace_tables_routes.py`. Implemented `ExportService` (CSV, Lark Base, Google Sheets formatters, PII masking), Lark Base connector (`app/connectors/lark_base.py`), Google Sheets connector (`app/connectors/google_sheets.py`), and Celery worker (`app/tasks/lead_export_worker.py`).
- **Frontend Spreadsheet Tabs & Export Hub:** Built `MultiTableTabs` with horizontal scroll, inline rename, delete, and add new table. Built `SendExportDropdown`, `FieldMappingModal`, and `ExportProgressBar`. Integrated everything seamlessly into `LeadsContent.tsx` with URL search param sync (`?table={id}`).

### Verification Results
- `uv run --no-sync pytest tests/unit/routes/test_workspace_tables_routes.py tests/unit/services/test_export_service.py tests/unit/routes/test_leads_routes.py tests/integration/services/test_lark_base_sync.py tests/integration/services/test_google_sheets_sync.py -q`: **22/22 PASSED (1.14s)**
- `uv run --no-sync ruff check` & `uv run --no-sync ruff format`: **PASSED (0 errors)**
- `pnpm tsc --noEmit`: **PASSED (0 errors)**
- `pnpm exec biome check`: **PASSED (0 errors)**
- `python3 scripts/check-docs-drift.py`: **PASSED**

### File List
- `nowing_backend/alembic/versions/209_add_workspace_tables_and_lead_tab_fk.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/app/connectors/google_sheets.py`
- `nowing_backend/app/connectors/lark_base.py`
- `nowing_backend/app/db.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/routes/leads_routes.py`
- `nowing_backend/app/routes/workspace_tables_routes.py`
- `nowing_backend/app/schemas/__init__.py`
- `nowing_backend/app/schemas/workspace_table.py`
- `nowing_backend/app/services/export_service.py`
- `nowing_backend/app/tasks/lead_export_worker.py`
- `nowing_backend/app/zero_publication.py`
- `nowing_backend/tests/integration/services/test_google_sheets_sync.py`
- `nowing_backend/tests/integration/services/test_lark_base_sync.py`
- `nowing_backend/tests/unit/routes/test_workspace_tables_routes.py`
- `nowing_backend/tests/unit/services/test_export_service.py`
- `nowing_web/components/leads/ExportProgressBar.tsx`
- `nowing_web/components/leads/FieldMappingModal.tsx`
- `nowing_web/components/leads/LeadsContent.tsx`
- `nowing_web/components/leads/multi-table-tabs.tsx`
- `nowing_web/components/leads/send-export-dropdown.tsx`
- `nowing_web/contracts/types/leads.types.ts`
- `nowing_web/contracts/types/workspace-table.types.ts`
- `nowing_web/lib/apis/leads-api.service.ts`
- `nowing_web/lib/apis/workspace-tables-api.service.ts`
- `nowing_web/lib/hooks/use-leads.ts`
- `nowing_web/lib/hooks/use-workspace-tables.ts`
