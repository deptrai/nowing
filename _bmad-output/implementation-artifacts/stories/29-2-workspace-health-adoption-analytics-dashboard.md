---
story_key: 29-2-workspace-health-adoption-analytics-dashboard
status: done
baseline_commit: 7e57a6ee4
epic: 29
story: 2
---

# Story 29.2: Workspace Health & Adoption Analytics Dashboard

**Status:** `done`  
**Epic:** 29 — SaaS Operations, Advanced Admin Governance & Analyst Workspace  
**Governed by:** FR-101, AR-17, UX-DR-PRFAQ-5, NFR-1, NFR-5, INV-29.3, AD-52, `epics.md` lines 4392–4414, `ux-contract-epic-29-saas-admin-analytics.md` §2 (HD-1..HD-5).  
**Dependencies:** Existing `Workspace`, `WorkspaceLimit`, `Memory`, `TokenUsage`, `WorkspaceRole`, `WorkspaceMembership`, `Permission.ANALYTICS_READ`, `Permission.MEMORY_READ` (Story 29.1).

---

## Story

As a **workspace Owner or delegated analyst**,  
I want **a SaaS-style health dashboard showing adoption, memory growth, query volume, credit burn, and source coverage**,  
so that **I can understand usage patterns, justify cost, and decide when to upgrade**.

---

## Acceptance Criteria

### AC-1 — Pre-Aggregated Daily Health Table & Rollup (`workspace_health_daily`, AD-52)
**Given** the need for high-performance workspace analytics without expensive live table scans,  
**When** daily analytics are recorded or aggregated,  
**Then**:
1. A database model `WorkspaceHealthDaily` (`workspace_health_daily` table) stores pre-aggregated metrics with a unique constraint on `(workspace_id, date)`:
   - `id`: Primary key (`INTEGER` or `UUID`).
   - `workspace_id`: Foreign key to `workspaces.id` (`ondelete="CASCADE"`, indexed).
   - `date`: Date of the aggregated metric (`DATE`, indexed, UTC normalized).
   - `active_members_dau`: Distinct active members who performed actions on that date (`INTEGER`, default 0).
   - `active_members_wau`: Distinct active members in the 7-day window ending on that date (`INTEGER`, default 0).
   - `total_memories`: Cumulative count of non-deleted memories in the workspace as of that date (`INTEGER`, default 0).
   - `memory_growth_count`: New memories created on that date (`INTEGER`, default 0).
   - `recall_queries`: Volume of `nowing_recall` queries executed (`INTEGER`, default 0).
   - `remember_queries`: Volume of `nowing_remember` queries executed (`INTEGER`, default 0).
   - `research_queries`: Volume of `nowing_research` / deep research turns executed (`INTEGER`, default 0).
   - `credits_consumed_micros`: Total credits consumed in micros on that date (`BIGINT`, default 0).
   - `cost_per_turn_micros`: Average credit cost per query/turn on that date (`BIGINT`, default 0).
   - `top_sources`: Ranked JSONB list of sources: `[{"source_type": str, "memory_count": int, "query_count": int, "cost_micros": int}]`.
   - `source_coverage_gap_count`: Number of enabled sources in the workspace with 0 memories created in the last 30 days (`INTEGER`, default 0).
   - `created_at`, `updated_at`: Standard timestamp mixins.
2. A rollup service/task `refresh_workspace_health_daily(session, target_date, workspace_id=None)` calculates and upserts rows for the given date from underlying operational tables (`Memory`, `TokenUsage`, `Run`, `WorkspaceMembership`, `PlatformScraperConfig`).
3. Source coverage gap definition: counts `source_type` values currently enabled in the workspace that have zero `Memory` rows created in the last 30 days (`created_at >= now() - interval '30 days'`), scoped to `workspace_id`.

### AC-2 — Sub-500ms Health Analytics API & Real-Time Overlay (INV-29.3, NFR-1)
**Given** an authenticated user requesting workspace health analytics,  
**When** `GET /api/v1/workspaces/{workspace_id}/health` is invoked with query parameter `range` (`7d`, `30d`, `90d`, or `custom` with `start_date` and `end_date`),  
**Then**:
1. **Date Range Normalization (UTC):**
   - `7d`: UTC today - 6 days through UTC today.
   - `30d`: UTC today - 29 days through UTC today.
   - `90d`: UTC today - 89 days through UTC today.
   - `custom`: Explicit `start_date` through `end_date` (enforcing `start_date <= end_date`).
2. **Sub-500ms Performance & Today Live Overlay (AD-52, NFR-1):**
   - Historical dates (< today) are queried directly from `workspace_health_daily` via indexed lookup `WHERE workspace_id = :workspace_id AND date BETWEEN :start AND :yesterday`.
   - Current date (today) is supplemented with a lightweight live query over `Memory` and `TokenUsage` within the current UTC day, seamlessly concatenated into `daily_metrics`.
3. **Time-Series & Sparkline Data Contracts:**
   - The response includes `daily_metrics: list[WorkspaceHealthDailyPoint]`, where each point provides: `date`, `active_members_dau`, `total_memories`, `memory_growth_count`, `query_volume` (`recall` + `remember` + `research`), `credits_consumed_micros`, and `cost_per_turn_micros`.
   - Each metric card in the summary payload provides a 14-day `sparkline: list[float | int]` and a 7-day `change_pct: float`.
4. **Permission Gating & Public Snapshot Masking (INV-29.3):**
   - **Full Access (`Permission.ANALYTICS_READ` or Owner):** Receives the full payload with active member metrics, financial credit burn, cost-per-turn, and quota limits.
   - **Reduced Public Snapshot (`Permission.MEMORY_READ` only):** Receives counts and trends only (`total_memories`, `memory_growth_count`, `recall_queries`, `remember_queries`, `research_queries`, `source_coverage_gap_count`, `top_sources` with `cost_micros=None`). Financial and identity fields are strictly masked to `None`: `active_members_dau=None`, `active_members_wau=None`, `credits_consumed_micros=None`, `cost_per_turn_micros=None`, `quota_progress=None`.
   - **Unauthorized (neither permission):** Returns HTTP `403 Forbidden`.
5. **Tenant Isolation (INV-29.3):** All SQL queries enforce `WHERE workspace_id = :workspace_id` before applying any date or source filters.

### AC-3 — Metric Drill-Down & Source Attribution (HD-3, HD-5)
**Given** the workspace health analytics view,  
**When** a user clicks on a specific source (e.g. `reddit`, `youtube`, `documents`) or `GET /api/v1/workspaces/{workspace_id}/health/sources/{source_type}` is called,  
**Then**:
1. The API returns the source breakdown within the selected time period:
   - Total memory count generated by this source.
   - Total query volume attributing this source in citations.
   - Total cost attribution in micros (`cost_micros` or `None` if public snapshot).
   - Recent memory timeline samples (limited to latest 5 items).
2. Gated by `workspace_id = :workspace_id` and requires `Permission.MEMORY_READ`.
3. Returns HTTP `404 Not Found` if the requested `source_type` has no recorded data in the workspace.

### AC-4 — Source Coverage Gap Detection & Drawer (HD-4)
**Given** enabled data scrapers/connectors in the workspace,  
**When** `GET /api/v1/workspaces/{workspace_id}/health/coverage-gaps` is called,  
**Then**:
1. The endpoint returns every enabled `source_type` with 0 memories created in the last 30 days.
2. For each gap, returns:
   - `source_type`: Connector identifier (e.g. `"reddit"`, `"hubspot"`).
   - `enabled_since`: ISO timestamp when source was activated.
   - `last_synced_at`: ISO timestamp of most recent activity, or `null`.
   - `remediation_action`: Suggested fix (e.g. `"Verify API credentials"`, `"Trigger manual sync"`).
   - `configure_url`: Client route to configure the source (`"/dashboard/{workspace_id}/connectors"`).

### AC-5 — Quota Progress Bars & Advisory Upgrade CTA (HD-2)
**Given** current workspace usage metrics,  
**When** metrics are compared against the workspace's plan limits (`WorkspaceLimit` looked up by `Workspace.plan_tier`),  
**Then**:
1. Utilization percentages are computed for:
   - Memory count: `current_total_memories / max_memory_count`
   - Monthly credits: `current_month_credits / max_monthly_credits`
   - Storage bytes: `current_storage_bytes / max_storage_bytes`
2. **Advisory Tier Progression:**
   - When any metric reaches ≥ 80% and < 100%:
     - Progress bar turns amber (`bg-amber-500`).
     - Surfaces an upgrade CTA banner recommending the next tier:
       - `free` plan → recommends `team`.
       - `team` plan → recommends `growth`.
       - `growth` plan → recommends `enterprise`.
   - When any metric reaches ≥ 100%:
     - Progress bar turns red (`bg-destructive`).
     - Surfaces an urgent quota warning badge.
3. **Non-blocking Guarantee:** Reaching or exceeding quota in this analytics dashboard does NOT block ongoing read operations or dashboard access (advisory only).

### AC-6 — Health Analytics Dashboard UI & Export (HD-1..HD-5)
**Given** the web client at `/dashboard/[workspace_id]/health`,  
**When** the page renders,  
**Then**:
1. **HD-1 (Metric Cards):** Displays top metric cards: Active Members (DAU/WAU), Total Memories, Memory Growth Rate, Query Volume (`recall` vs `research`), Credits Consumed, and Cost Per Turn. Each card renders value, 7-day change percentage, and 14-day sparkline.
2. **HD-2 (Quota Progress):** Displays utilization progress bars with color-coded 80% amber / 100% red thresholds and "Upgrade Plan" CTA button.
3. **HD-3 (Top Sources Table):** Renders ranked table of sources with memory count, query volume, and coverage gap status chips.
4. **HD-4 (Coverage Gap Drawer):** Clicking "Source coverage gap" opens a slide-over drawer detailing inactive sources with direct deep-links to `/dashboard/[workspace_id]/connectors`.
5. **HD-5 (Drill-Down Sheet):** Clicking any source row opens a detailed drill-down sheet showing time-series volume and cost attribution.
6. **Navigation Integration:** Added to `LayoutDataProvider.tsx` sidebar navigation as `"Health & Analytics"` (`url: /dashboard/${workspaceId}/health`, icon: `Activity`), visible to users with `analytics:read` or `memory:read`.
7. **Empty State UX:** When workspace has 0 memories and 0 queries, renders an onboarding guide ("No health activity yet. Start by connecting sources or creating memories") instead of empty graphs.
8. **Export Action:** "Export" button allowing one-click download as:
   - **CSV:** Headers `date,dau,wau,total_memories,new_memories,recall_queries,remember_queries,research_queries,credits_micros,cost_per_turn_micros,coverage_gaps`.
   - **JSON:** Formatted summary payload matching `WorkspaceHealthSummaryResponse`.

---

## Tasks / Subtasks

- [x] Task 1 — Database Model & Rollup Service (AC: 1, 2)
  - [x] 1.1 Create `WorkspaceHealthDaily` model in `nowing_backend/app/models/workspaces.py` (or `app/models/workspace_health.py`):
    - Fields: `workspace_id`, `date`, `active_members_dau`, `active_members_wau`, `total_memories`, `memory_growth_count`, `recall_queries`, `remember_queries`, `research_queries`, `credits_consumed_micros`, `cost_per_turn_micros`, `top_sources`, `source_coverage_gap_count`.
  - [x] 1.2 Add composite unique index `(workspace_id, date)` and foreign key to `workspaces.id` with `ondelete="CASCADE"`.
  - [x] 1.3 Implement `WorkspaceHealthService` in `nowing_backend/app/services/workspace_health_service.py`:
    - `refresh_daily_rollups(session, target_date, workspace_id=None)`: Rollup calculation from `Memory`, `TokenUsage`, `Run`, `WorkspaceMembership`.
    - `get_health_summary(session, workspace_id, date_range, is_public_snapshot=False)`: Merges pre-aggregated historical rows with current-day live overlay.
    - `get_source_drilldown(session, workspace_id, source_type, date_range, is_public_snapshot=False)`.
    - `get_coverage_gaps(session, workspace_id)`: Formula for enabled sources with 0 memories in last 30 days.
  - [x] 1.4 Add background Celery task or periodic rollup trigger in `nowing_backend/app/tasks/workspace_health_tasks.py`.

- [x] Task 2 — Backend Endpoints & Export Handler (AC: 2, 3, 4, 5, 6)
  - [x] 2.1 Define Pydantic schemas in `nowing_backend/app/schemas/workspace_health.py`:
    - `WorkspaceHealthSummaryResponse`, `WorkspaceHealthDailyPoint`, `SparklineData`, `SourceBreakdownResponse`, `CoverageGapsResponse`, `QuotaProgressItem`.
  - [x] 2.2 Create `nowing_backend/app/routes/workspace_health_routes.py`:
    - `GET /api/v1/workspaces/{workspace_id}/health`: Check `analytics:read` vs `memory:read` (INV-29.3), return summary with sparklines, quota progress, and daily metrics.
    - `GET /api/v1/workspaces/{workspace_id}/health/sources/{source_type}`: Source drill-down with timeline samples.
    - `GET /api/v1/workspaces/{workspace_id}/health/coverage-gaps`: Inactive source listing with remediation actions.
    - `GET /api/v1/workspaces/{workspace_id}/health/export`: Format param `csv` or `json` returning `StreamingResponse` with `Content-Disposition`.
  - [x] 2.3 Register router in `nowing_backend/app/routes/__init__.py`.

- [x] Task 3 — Frontend Contracts & API Service (AC: 2, 3, 4, 6)
  - [x] 3.1 Define TypeScript schemas in `nowing_web/contracts/types/workspace-health.types.ts`:
    - `workspaceHealthSummaryResponse`, `sourceBreakdownResponse`, `coverageGapsResponse`, `workspaceHealthDailyPoint`.
  - [x] 3.2 Implement API client in `nowing_web/lib/apis/workspace-health-api.service.ts`:
    - `getHealthMetrics(workspaceId, range, startDate?, endDate?)`
    - `getSourceDrilldown(workspaceId, sourceType, range)`
    - `getCoverageGaps(workspaceId)`
    - `downloadHealthExport(workspaceId, format, range)`
  - [x] 3.3 Register query cache keys in `nowing_web/lib/query-client/cache-keys.ts` under `cacheKeys.workspaces.health`.

- [x] Task 4 — Frontend UI Dashboard & Navigation (AC: 5, 6)
  - [x] 4.1 Update `nowing_web/components/layout/providers/LayoutDataProvider.tsx`:
    - Add `"Health & Analytics"` nav item (`/dashboard/${workspaceId}/health`, icon `Activity`), active when pathname includes `/health`.
  - [x] 4.2 Create page route at `nowing_web/app/dashboard/[workspace_id]/health/page.tsx`.
  - [x] 4.3 Build `WorkspaceHealthDashboard` in `nowing_web/components/analytics/workspace-health-dashboard.tsx`:
    - Range selector buttons (`7d`, `30d`, `90d`, custom date picker).
    - HD-1: 6 Metric Cards with 14-day sparklines and 7-day change percentage.
    - HD-2: Quota Progress Bars with 80% amber / 100% red thresholds and advisory upgrade CTA.
    - HD-3: Top Sources Ranked Table with coverage gap chips.
    - HD-4: Slide-over Drawer for Coverage Gaps (`coverage-gap-drawer.tsx`).
    - HD-5: Drill-down Sheet for individual source details (`source-drilldown-sheet.tsx`).
    - Empty state component when total activity is zero.
    - Export button triggering CSV/JSON file download.

- [x] Task 5 — Automated Verification & Testing (AC: 1..6)
  - [x] 5.1 Backend unit tests in `nowing_backend/tests/unit/services/test_workspace_health.py`:
    - Daily rollup calculation correctness (memories, queries, credits).
    - Source coverage gap detection formula.
    - Permission gating (full access with `analytics:read` vs public snapshot with `memory:read` vs 403).
    - Public snapshot field masking verification.
    - Advisory upgrade tier progression logic (Free → Team → Growth → Enterprise).
  - [x] 5.2 Backend API integration tests in `nowing_backend/tests/integration/routes/test_workspace_health_routes.py`:
    - Sub-500ms pre-aggregated response validation.
    - Today live overlay integration.
    - CSV and JSON export endpoints.
  - [x] 5.3 Frontend Playwright E2E spec in `nowing_web/tests/analytics/workspace-health-dashboard.spec.ts`:
    - Metric cards and sparkline rendering.
    - Time range toggle and data refresh.
    - Coverage gap drawer open/close.
    - Quota progress bar alert states.

---

## Dev Notes

### Architecture Compliance (AD-52, INV-29.3)
- **Pre-aggregation (AD-52):** Avoid live table scans over large tables (`Memory`, `TokenUsage`) on dashboard load. Reads must target `workspace_health_daily` rows indexed by `(workspace_id, date)` with current-day live overlay.
- **Tenant Isolation (INV-29.3):** Every SQL query MUST enforce `WHERE workspace_id = :workspace_id`. Cross-workspace metric aggregation is strictly prohibited.
- **Permission Matrix Alignment:**
  - `analytics:read`: Full health dashboard, financial credit metrics, cost-per-turn, active member identities.
  - `memory:read`: Public snapshot (counts and trends only; credit, cost, and identity fields are strictly masked to `None`).
  - Neither permission: HTTP 403 Forbidden.
- **Advisory Quotas (HD-2):** Quota progress bars compare against `WorkspaceLimit` (`max_memory_count`, `max_monthly_credits`, `max_storage_bytes`). Reaching 80% displays an amber alert with upgrade CTA, but does NOT block operations.

### Files to Touch
- **Backend:**
  - `nowing_backend/app/models/workspaces.py` (or `app/models/workspace_health.py`)
  - `nowing_backend/app/schemas/workspace_health.py`
  - `nowing_backend/app/services/workspace_health_service.py`
  - `nowing_backend/app/routes/workspace_health_routes.py`
  - `nowing_backend/app/routes/__init__.py`
  - `nowing_backend/app/tasks/workspace_health_tasks.py`
- **Frontend:**
  - `nowing_web/contracts/types/workspace-health.types.ts`
  - `nowing_web/lib/apis/workspace-health-api.service.ts`
  - `nowing_web/lib/query-client/cache-keys.ts`
  - `nowing_web/components/layout/providers/LayoutDataProvider.tsx`
  - `nowing_web/app/dashboard/[workspace_id]/health/page.tsx`
  - `nowing_web/components/analytics/workspace-health-dashboard.tsx`
  - `nowing_web/components/analytics/coverage-gap-drawer.tsx`
  - `nowing_web/components/analytics/source-drilldown-sheet.tsx`

---

## Challenge Log (grill-me)

### Q1 — Already implemented?
- **Workspace Analytics / Health:** Không có bảng `workspace_health_daily`, không có model `WorkspaceHealthDaily`, không có `workspace_health_routes.py`.
- **Existing Telemetry vs Health:** `admin_health.py` thuộc Story 25.7 là platform-admin probe status giám sát external services (LLM, Redis, Supabase) theo AD-25.7, hoàn toàn tách biệt với workspace tenant health analytics (AD-52).
- **Existing Usage Service:** `usage_service.py` chỉ tổng hợp `TokenUsage` theo model/feature, không đo lường DAU/WAU, tốc độ tăng trưởng memory, query volume theo loại (`nowing_recall`, `nowing_remember`, `nowing_research`), hay source coverage gap.
- **Clean:** Không có logic trùng lặp.

### Q2 — Simpler alternative?
- **Tái sử dụng hạ tầng hiện có:**
  - Tái sử dụng `WorkspaceLimit` và `workspace_limits.py` để tra cứu quota giới hạn (`max_memory_count`, `max_monthly_credits`, `max_storage_bytes`) mà không cần tạo bảng quota mới.
  - Tái sử dụng `TokenUsage`, `Memory`, `WorkspaceMembership`, `Run` làm bảng gốc cho daily rollup.
  - Tái sử dụng `date-range-picker.tsx` và mẫu `SummaryCard` từ `nowing_web/components/usage/` để đồng nhất giao diện và tiết kiệm thời gian phát triển.
- **Clean:** Tận dụng triệt để các model và util hiện có, chỉ tạo bảng tổng hợp `workspace_health_daily` để đạt chuẩn hiệu năng `< 500ms` theo AD-52.

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] **Boundary (Ngưỡng 80% & 100%):** So sánh quota phải xử lý `>= 80.0%` (amber warning) và `>= 100.0%` (red alert). Nếu plan có limit là `None` (unlimited như Enterprise / self-hosted), tính toán `utilization_pct = None` và không kích hoạt cảnh báo vượt hạn mức.
- [ ] **Boundary (Max Date Range):** Giới hạn `custom` range tối đa 365 ngày để ngăn ngừa tấn công DoS hoặc truy vấn quét bảng quá dài.
- [ ] **Null/Zero Division:** Khi tổng số lượt truy vấn bằng 0 (`recall + remember + research == 0`), tính toán `cost_per_turn_micros = 0` thay vì gây lỗi `ZeroDivisionError`.
- [ ] **Null/Empty Workspace:** Workspace mới tạo (0 memories, 0 queries, 0 token usage) phải trả về payload hợp lệ với các giá trị 0 và mảng rỗng `top_sources = []`, UI hiển thị Empty State onboarding thân thiện thay vì lỗi đồ thị trống.
- [ ] **Concurrent / Idempotency:** Rollup `refresh_workspace_health_daily` có thể được trigger đồng thời; sử dụng `ON CONFLICT (workspace_id, date) DO UPDATE SET ...` để đảm bảo tính bất biến và không phát sinh lỗi khóa chính.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] **Celery Worker / Cron Task Lag:** Nếu worker bị delay hoặc chưa chạy, `workspace_health_daily` có thể thiếu bản ghi của một số ngày trong quá khứ. API phải tự động lấp đầy các ngày thiếu bằng giá trị 0 hoặc truy vấn fallback để sparkline không bị đứt đoạn.
- [ ] **BigInt Precision Overflow:** `credits_consumed_micros` có thể đạt hàng tỷ micros. Pydantic schema và TypeScript interface cần đảm bảo parse chuẩn xác dạng number/BigInt mà không bị mất độ chính xác dấu phẩy động.
- [ ] **Case-insensitivity on Source Type:** Giá trị `source_type` trong `Memory` có thể không đồng nhất viết hoa/thường (e.g. `"reddit"` vs `"Reddit"`). Cần chuẩn hóa bằng `.lower()` khi GROUP BY trong SQL.

### Triage
- **Clean — Non-critical gaps only.** Tất cả các edge case và failure mode đã được ghi nhận và đưa vào kế hoạch kiểm thử ATDD skeleton. Tiến hành sang bước `test-first-atdd`.

---

## Dev Agent Record

### Agent Model Used
Claude Sonnet 5

### Completion Notes List
- Comprehensive story implementation adhering to AD-52, INV-29.3, and UX Contract Epic 29 §2 (HD-1..HD-5).
- Created `workspace_health_daily` ORM model, unique composite index on `(workspace_id, date)`, and Alembic migration `d4e7f1a2b5c8_add_workspace_health_daily_table.py`.
- Built `WorkspaceHealthService` implementing daily rollups, sub-500ms pre-aggregation merged with live UTC day overlay, 14-day sparklines, 7-day change percentages, source drilldown, coverage gaps detection, and advisory quota telemetry.
- Implemented Celery beat scheduled task `refresh_workspace_health_daily` running at 00:05 UTC nightly.
- Created REST API router `workspace_health_routes.py` with endpoints for summary, drilldown, coverage gaps, and streaming CSV/JSON exports with strict RBAC (`ANALYTICS_READ`, `MEMORY_READ`, and 403 Forbidden).
- Implemented frontend TypeScript contracts, TanStack query cache keys, and API service `workspace-health-api.service.ts`.
- Integrated sidebar navigation item "Health & Analytics" in `LayoutDataProvider.tsx`.
- Built complete UI dashboard at `/dashboard/[workspace_id]/health` with 6 metric cards, mathematical SVG sparklines (HD-1), quota progress bars (HD-2), top sources ranked table (HD-3), coverage gaps drawer (HD-4), and source drill-down sheet (HD-5).
- Added comprehensive backend unit tests (`test_workspace_health.py` - 6 tests passing) and integration route tests (`test_workspace_health_routes.py` - 7 tests passing).
- Created Playwright E2E test suite in `nowing_web/tests/analytics/workspace-health-dashboard.spec.ts` (8 tests passing).

### Post-Review Fixes (2026-09-07)
- **Coverage-gap semantics (HD-3/HD-4):** `SearchSourceConnector.connector_type` (enum like `SLACK_CONNECTOR`) does NOT match `Memory.source_type` (`MemorySourceType`: document/chat_message/scraper_run/…). Rewired both `_build_top_sources` and `_count_coverage_gaps`/`get_coverage_gaps` to count non-archived `Document` rows joined via `Document.connector_id → search_source_connectors.id`. Coverage gap = connector with zero `Document` in trailing 30 days.
- **Live "today" overlay without writes:** `_rollup_for_workspace_date(..., persist: bool = True)` — the read path now calls it with `persist=False` to avoid read-path DB writes; only the Celery nightly task persists.
- **Weighted cost-per-turn 7d change:** computed as `sum(credits)//sum(queries)` per window (not sum of daily averages).
- **`total_members` as-of-date:** added `total_members` column (model + migration + `WorkspaceHealthDailyPoint` + `WorkspaceHealthSummaryResponse` + FE schema) computed from `WorkspaceMembership.joined_at <= day_end`; added a dedicated "Total Members" metric card (sky-500 sparkline).
- **Idempotent upsert:** `pg_insert(WorkspaceHealthDaily).on_conflict_do_update(index_elements=["workspace_id","date"])`.
- **Per-workspace savepoints in nightly task:** `async with session.begin_nested()` + `session.commit()` per workspace so one failing workspace cannot roll back the whole batch; `expires` beat option raised to 3600.
- **Public snapshot masking (INV-29.3):** `active_members_dau/wau`, `credits_consumed_micros`, `cost_per_turn_micros`, `quota_progress`, and per-source `cost_micros` forced to `None` for `memory:read`-only users; source drilldown `cost_micros=None` (per-source cost attribution not tracked yet).
- **Export hardening:** `downloadHealthExport` throws when the returned blob is empty (`blob.size === 0`).
- **Sparkline a11y:** added `role="img"` + `<title>Trend sparkline</title>` inside the `<svg>`.
- **i18n nav label:** sidebar item uses `tNav("health_analytics")` with the key added to all 7 locale files (en/vi/es/pt/ko/hi/zh).
- **Celery task SQL fix:** wrapped `SELECT id FROM workspaces ORDER BY id` in `sqlalchemy.text()` for SQLAlchemy 2.0.
- **E2E assertions aligned to rendered copy:** `formatUsd(45_000 micros)` → `$0.04` (not `< $0.01`); quota warning/alert are Badge labels (`Warning (80%+)`, `Quota Exceeded`, `Recommended tier: Team`) not raw `%` text; coverage gap drawer heading is `Knowledge Coverage Gaps` and the gap source name renders capitalized (`google drive`), scoped to the dialog to avoid strict-mode collision with the sources table cell.

### Verification (2026-09-07)
- `pytest tests/unit/services/test_workspace_health.py tests/integration/routes/test_workspace_health_routes.py` → **13 passed**
- `npx tsc --noEmit` (nowing_web) → **clean**
- `npx @biomejs/biome check` on all touched files → **clean** (1 pre-existing unrelated warning in `LayoutDataProvider.tsx` — `isNewChatRoot` unused, out of story scope)
- `npx playwright test tests/analytics/workspace-health-dashboard.spec.ts` → **8/8 passed** (chromium)
- `npx next build` → **success**, `/dashboard/[workspace_id]/health` route present

### File List
- `_bmad-output/implementation-artifacts/stories/29-2-workspace-health-adoption-analytics-dashboard.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `nowing_backend/alembic/versions/d4e7f1a2b5c8_add_workspace_health_daily_table.py`
- `nowing_backend/app/models/workspace_health.py`
- `nowing_backend/app/models/workspaces.py`
- `nowing_backend/app/db/__init__.py`
- `nowing_backend/app/schemas/workspace_health.py`
- `nowing_backend/app/services/workspace_health_service.py`
- `nowing_backend/app/routes/workspace_health_routes.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/tasks/celery_tasks/workspace_health_tasks.py`
- `nowing_backend/app/celery_app.py`
- `nowing_backend/tests/unit/services/test_workspace_health.py`
- `nowing_backend/tests/integration/routes/test_workspace_health_routes.py`
- `nowing_web/contracts/types/workspace-health.types.ts`
- `nowing_web/lib/apis/workspace-health-api.service.ts`
- `nowing_web/lib/query-client/cache-keys.ts`
- `nowing_web/components/layout/providers/LayoutDataProvider.tsx`
- `nowing_web/components/analytics/sparkline.tsx`
- `nowing_web/components/analytics/coverage-gap-drawer.tsx`
- `nowing_web/components/analytics/source-drilldown-sheet.tsx`
- `nowing_web/components/analytics/workspace-health-dashboard.tsx`
- `nowing_web/app/dashboard/[workspace_id]/health/page.tsx`
- `nowing_web/tests/analytics/workspace-health-dashboard.spec.ts`
