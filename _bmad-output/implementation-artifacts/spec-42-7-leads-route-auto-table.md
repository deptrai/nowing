---
title: 'Story 42.7 — Leads route + auto-table + empty state'
type: feature
created: '2026-11-17'
status: 'done'
review_loop_iteration: 1
followup_review_recommended: true
baseline_revision: '501ba1adb'
review_loop_iteration: 0
warnings: ['multiple-goals', 'oversized', 'has-migration']
deferred: []
context: []
---

## <intent-contract>

**Goal (IA fix):** `/dashboard/{id}/leads` là real route mount leads canvas (không
còn redirect sang `new-chat?mode=leads`); mọi lead đi qua
`LeadBatchService.ingest_batch` đều có `table_id` — absent/stale → get-or-create
default `WorkspaceTable` keyed `client_id`, race-safe; existing orphan leads được
backfill một lần trong migration; empty state có CTA "săn qua chat".

### Always

- **`workspace_tables` thêm cột `key`** (Text, nullable) + `UNIQUE(workspace_id, key)`
  — migration alembic mới. `key` chỉ set cho auto-created default tables
  (`key = client_id` từ ingest, hoặc `"default"`); user-created tables giữ `key=NULL`
  (UNIQUE cho phép nhiều NULL).
- **Get-or-create race-safe:** `INSERT ... ON CONFLICT (workspace_id, key) DO NOTHING`
  rồi `SELECT` lại — 2 ingest đồng thời không tạo 2 tables. Không dùng
  `get_or_create` ORM pattern (race window).
- **Trong `ingest_batch`:** nhóm lead rows theo `client_id` → resolve 1
  `WorkspaceTable` per (workspace_id, client_id) → gán `table_id` cho mọi row có
  `table_id` absent HOẶC `table_id` trỏ tới row không tồn tại (stale → fallback
  default table, KHÔNG crash FK).
- **Backfill one-shot trong cùng migration:** mỗi workspace có leads `table_id IS
  NULL` → tạo default table (`key='default'`, name hợp lý) →
  `UPDATE leads SET table_id=<default>` . Data migration dùng `op.execute`/SQL thuần.
- **FE route thật:** `nowing_web/app/dashboard/[workspace_id]/leads/page.tsx`
  mount `NowingSplitCanvas` standalone (`workspaceId`, `hasActiveThread={false}`,
  không `chatSlot`) — thay redirect hiện tại.
- **Nav link:** thêm item Leads vào `navItems` trong `LayoutDataProvider`
  (~:303-350), url `/dashboard/{workspaceId}/leads`, i18n key mới, icon phù hợp
  (`Users`/`Table` từ lucide — check imports có sẵn).
- **Empty state CTA:** khi workspace chưa có lead → hiển thị state rỗng với CTA
  "Chưa có lead — săn qua chat" link tới `/dashboard/{id}/new-chat` (gợi ý prompt
  lead-gen nếu component hỗ trợ `onSendPrompt`).

### Never

- KHÔNG đổi semantic `table_id` do caller truyền (table_id hợp lệ vẫn được giữ).
- KHÔNG backfill qua background job/endpoint — chỉ migration one-shot.
- KHÔNG tạo `key` UNIQUE trên toàn bảng — phải composite `(workspace_id, key)`.
- KHÔNG mount `NowingSplitCanvas` với chat runtime đầy đủ (AssistantRuntimeProvider
  thread runtime) trong `/leads` — standalone canvas không cần thread.
- KHÔNG đổi `on_conflict_do_update` dedupe `(workspace_id, value_hmac)` của leads.
- KHÔNG sửa `lead_generation.py` tool contract (`table_id` param vẫn là override).

### Decisions

- **D1 key = client_id:** AC literal "keyed `client_id`" → `key` column lưu
  `client_id`; client_id `"default"` (fallback hiện tại :112) → key `"default"`.
- **D2 name cho auto-table:** dùng `client_id` nếu có ý nghĩa, else `"Leads"` —
  tối giản, FE có thể đổi tên sau (rename không scope story này).
- **D3 stale table_id → fallback default + ghi lead vào default** (không recreate
  table với id cũ — id đó do user xóa).
- **D4 FE mount tối thiểu:** page.tsx server component truyền `workspace_id` →
  client wrapper mount `NowingSplitCanvas` — verify props tối thiểu render được
  (`workspaceId` duy nhất bắt buộc; các prop khác có default).
- **D5 empty state ở level canvas/matrix** (trong `NowingSplitCanvas` hoặc
  `NowingLeadMatrix`), không phải page-level — vì canvas tự fetch `useLeads`.

## </intent-contract>

## Code Map

| Mục | Path:anchor | Ghi chú |
|---|---|---|
| Lead prepare/upsert | `nowing_backend/app/services/lead_batch_service.py:100-120,340-420` | `:113` table_id passthrough; `_build_batch_upsert_stmt` coalesce :184-185 |
| WorkspaceTable | `nowing_backend/app/models/workspaces.py:650-678` | thiếu `key` column + UNIQUE |
| Lead.table_id | `nowing_backend/app/models/leads/main.py:176-182` | FK SET NULL → orphan = NULL |
| Migrations | `nowing_backend/alembic/versions/` | revision mới sau head hiện tại (check `alembic heads`) |
| Ingest callers | `app/agents/.../lead_generation.py:79,159` + save_leads/websets/orchestrator | truyền table_id optional |
| FE route | `nowing_web/app/dashboard/[workspace_id]/leads/page.tsx:1-6` | hiện chỉ redirect |
| Canvas | `nowing_web/components/leads/NowingSplitCanvas.tsx` (~:44-52 props) | props optional, mount standalone |
| Nav items | `nowing_web/components/layout/providers/LayoutDataProvider.tsx:303-350` | thêm entry + isActive |
| useLeads | `nowing_web/lib/hooks/use-leads.ts` | canvas fetch |
| Tests | `nowing_backend/tests/unit/services/test_lead_batch_service.py` + migration tests nếu có convention | |

## Tasks & Acceptance

### Execution

- [ ] T1 Migration: `key` column + `UNIQUE(workspace_id, key)` + backfill orphans
- [ ] T2 `ingest_batch`: group-by-client_id → get-or-create (ON CONFLICT DO NOTHING
      + reselect) → gán table_id; stale table_id → default
- [ ] T3 FE `/leads` page mount canvas + nav item + i18n key
- [ ] T4 Empty state CTA trong canvas khi 0 leads
- [ ] T5 Tests: service auto-table (create/reuse/race-simulated/stale), migration
      backfill (nếu có test convention), FE smoke nếu có test setup

### Acceptance

- A1 `ingest_batch` table_id absent → default table get-or-create, lead.table_id set
- A2 2 ingest cùng client_id concurrent → đúng 1 table (ON CONFLICT DO NOTHING)
- A3 table_id stale/deleted → lead vào default table, không FK error
- A4 `/dashboard/{id}/leads` render canvas trực tiếp, có nav link, empty CTA
- A5 Migration backfill: pre-migration orphans → post-migration có table

## Verification

```bash
cd nowing_backend && .venv/bin/python -m pytest tests/unit/services/test_lead_batch_service.py tests/unit/routes/test_lead_batch_ingest.py tests/integration/lead_batch/ -x -q
cd nowing_web && pnpm tsc --noEmit  # hoặc lint config hiện có
alembic heads  # single head sau migration mới
```

## Spec Change Log

- 2026-11-17 — Initial (step-02, spec-author: coordinator)

## Review Triage Log

### 2026-11-17 — Review pass

4 layers (blind-hunter N=7, edge-case-hunter 15, verification-gap 5, intent-alignment) — hội tụ mạnh trên 2 lỗi HIGH. Verdicts:

- [high] [patch] **str `table_id` bị nuốt** — `isinstance(table_id, UUID)` ở `lead_batch_service.py:311,332`, mọi caller thực tế (`save_leads` `table_id: str|None`, orchestrator) truyền str → override silently vô hiệu, response vẫn link `#table_id=` cũ. Fix: coerce `UUID(str(table_id))` try/except → invalid → default. + test `table_id=str(uuid4())`. *(BH-F1, EC-1/claim, IA-Never-1, VG-2)*
- [high] [patch] **Dead modals standalone** — `LeadDetailFlyoutDrawer`/`CompanyGraphDrawer`/`ReverseIcpModal`/`DncManagementModal` chỉ render nhánh non-standalone nhưng callbacks vẫn wire → dead-click trên `/leads`. Fix: hoist overlays ra ngoài conditional; `FloatingBulkActionBar`/`ContextualDock` tự gate `hasActiveThread` — giữ nguyên (by design). *(BH-F2, EC-7, IA-extra-1, VG-1)*
- [medium] [patch] **Unresolved key giữ stale `table_id` → FK crash** — `if table_id is None: continue` khi re-SELECT miss → UUID row đã xóa vào upsert. Fix: gán `lead["table_id"] = key_to_id.get(key, default_id)` vô điều kiện (None ≥ crash). *(BH-F6, EC-2/claim)*
- [medium] [patch] **`client_id` unbounded → `name` String(200) + key btree crash** — `name = k` raw; key Text >~2.7KB vỡ index. Fix: normalize trong `_prepare_lead_record` (`str(...) or "default"`, casefold cho key) + bound key/name (hash hoặc truncate, deterministic). Cùng fix `client_id=""` lệch nhóm + non-str TypeError. *(BH-F5/F8, EC-3/EC-4/EC-5)*
- [medium] [patch] **Empty-state CTA fire sai** — không check `loading`/error/active-filters: flicker khi load, hiện "Chưa có lead" khi server-filter rỗng hoặc API fail. Fix: gate CTA trên `!loading && !error && no active filters`. *(BH-F3/F4, EC-8)*
- [medium] [patch] **Dock useEffect collapse sidebar trong standalone** — `NowingSplitCanvas.tsx:104-133` chạy vô điều kiện → `setLeftWidth(0)` + sidebar collapse trên `/leads`, không UI restore. Fix: gate `!isStandalone`. *(EC-9)*
- [medium] [patch] **`ingest_stream_leads_to_db` không adopt auto-table** (`lead_stream_service.py:195-209`, gọi từ scraper tasks) — orphan `table_id IS NULL` tiếp tục sinh vĩnh viễn, kể cả cửa sổ deploy. Fix: gọi `_resolve_lead_table_ids` trước upsert (session có sẵn). *(VG-4, EC-6)*
- [medium] [patch] **Migration 250 backfill thiếu test** — convention `tests/integration/db/test_migration_*_roundtrip.py` tồn tại; lỗi predicate sẽ khóa vĩnh viễn mà không gate nào bắt. Fix: thêm `test_migration_250_roundtrip.py`. *(VG-3)*
- [low] [patch] **Get-or-create trước DNC filter** (`lead_batch_service.py:422` trước `batch_filter_leads:425`) → batch 100% blacklist tạo WorkspaceTable rỗng. Fix: move resolve sau DNC filter, chạy trên survivors. *(BH-F7)*
- [low] [patch] **`split-canvas.spec.ts:76-79` assert redirect cũ** → fail khi e2e chạy. Rewrite assert `/leads` mount canvas + interaction mở drawer. *(VG-1, other)*
- [low] [patch] **Test `existing_key` không assert resolved `table_id`** — `reselect_rows` không seed → key_to_id rỗng → lead NULL vẫn pass. Seed + assert. *(EC-10)*
- [low] [patch] **CTA `<a>` → `next/link`**; `isLeadsActive` `includes("/leads")` → `endsWith`. *(IA-3, BH-F9, EC-claim-low)*
- [low] [reject] `?mode=leads` trên new-chat vẫn là deep-link hợp lệ trong chat — không phải orphan. *(EC-11)*
- [low] [defer] `_AutoTableFakeSession` route-SELECT bằng chuỗi cột — brittle nhưng chạy đúng; assert đếm statement bị xóa — coverage mới đủ. *(BH-F10, EC-12)*
- [low] [reject] `UUID` import thiếu trong test file — `from __future__ import annotations` → runtime-safe, cosmetic. *(IA-4)*

## Auto Run Result

- **Implement** (subagent, fresh context): T1 migration 250 (`key` col + UNIQUE(workspace_id,key) + one-shot orphan backfill), T2 `_resolve_lead_table_ids` (get-or-create race-safe, group theo client_id, stale→default), T3 FE `/leads` mount standalone + nav item + i18n 7 locales, T4 empty-state CTA, T5 `TestAutoTableResolution` 6 tests.
- **Review pass 1**: 4 layers → 2 high + 6 medium + 4 low patched (12/12 applied): str `table_id` coerce (Never-rule fix), hoisted 4 overlays cho standalone, stale-FK guard, client_id normalize/bound/casefold, CTA gating, dock-effect gating, `ingest_stream_leads_to_db` adopt resolver, migration roundtrip test, resolve sau DNC filter, e2e spec rewrite, test seed fix, link/endsWith.
- **Verification**: `pytest tests/unit/services/test_lead_batch_service.py tests/unit/routes/test_lead_batch_ingest.py tests/integration/lead_batch/ tests/integration/db/test_migration_250_roundtrip.py -q` → **60 passed**; `pnpm tsc --noEmit` → clean; `alembic heads` → single head `250`.
- **Deferred**: 1 item (fake-session SQL-string routing brittleness). `followup_review_recommended: true` (2 high patched).
- **Rủi ro còn lại**: Playwright spec chưa chạy local (cần dev server); `ingest_stream_leads_to_db` dùng lazy import để tránh circular import; deploy cần `alembic upgrade head` trước code mới (backfill one-shot).

## Design Notes

- Race-safe pattern giống `_build_batch_upsert_stmt` (pg_insert + on_conflict) —
  dùng `postgresql.insert(WorkspaceTable).on_conflict_do_nothing(index_elements=...)`.
- UNIQUE index với nhiều NULL key OK trong Postgres (user tables không key).
- Nếu `NowingSplitCanvas` yêu cầu providers (jotai atoms đã global), check imports
  — implementer verify render được trong dashboard layout hiện có.
- i18n: check `nowing_web/messages/` hoặc i18n config cho key mới
  (`nav.leads` / `leads.empty_cta`).
