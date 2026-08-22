---
baseline_commit: cbe10c1ce43d9a3bf1508ecc50e5c56a284f5120
story_key: 3-7-followup
status: done
---

# Story 3.7-followup: Củng cố Retention (Retention Hardening) `(Tech Debt)`

**Status:** `done`  
**Epic:** 3 — Knowledge Base & Search  
**Priority:** P2  
**Effort:** 1–2 ngày  
**Trigger:** Khi có concurrent retention updates.

**Source:** `_bmad-output/planning-artifacts/epics.md` §Story 3.7-followup (dòng 479–491)  
**Related PRD:** `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §OQ-3 (Open Questions)  
**Related Architecture:** `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — `AD-DEFER-4` (Data retention & lifecycle per workspace, trạng thái `PARTIAL`: schema đã có, phần legal/right-to-delete cho `Memory` còn mở)  
**Baseline:** `cbe10c1` trên `develop`

---

## Story

As a platform engineer,  
I want retention settings có DB-level guards + concurrent safety + test robustness,  
So that retention không corrupt dưới concurrent access và tests không pass for wrong reasons.

---

## Acceptance Criteria

> Trích nguyên văn từ `_bmad-output/planning-artifacts/epics.md`, giữ định dạng BDD.

1. **Given** concurrent retention update trên cùng workspace, **When** 2 requests update `document_retention_days` cùng lúc, **Then** dùng `SELECT FOR UPDATE` tránh last-write-wins.
2. **Given** `test_archived_document_excluded_from_hybrid_search`, **When** chạy, **Then** có negative assertion verify cả 2 chunks tồn tại trong DB trước khi assert search filter.
3. **Given** `test-archived-sync.spec.ts`, **When** backend không chạy, **Then** test skip với clear message thay vì fail.
4. **Given** `data-retention.spec.ts`, **When** test fail mid-execution, **Then** workspace cleanup chạy trong `finally` block.

---

## Tasks / Subtasks

- [ ] **Backend — harden `PUT /workspaces/{id}` chống race condition trên retention fields**
  - [ ] Thêm `SELECT FOR UPDATE` khi load `Workspace` row trong `update_workspace` (`nowing_backend/app/routes/workspaces_routes.py:261`).
  - [ ] Giữ nguyên validation hiện có: `auto_archive_enabled=true` yêu cầu `document_retention_days` là số nguyên dương (`> 0`) và không vượt quá `36500`.
  - [ ] Bảo toàn logic `setattr` update chung cho các trường workspace khác.
- [ ] **Backend tests — bổ sung negative assertion cho `test_archived_document_excluded_from_hybrid_search`**
  - [ ] Trước khi gọi `hybrid_search`, assert `chunk_count == 2` trong DB (`Chunk` thuộc cả 2 documents `visible` và `archived`).
- [ ] **E2E — `test-archived-sync.spec.ts` skip rõ ràng khi backend không chạy**
  - [ ] Kiểm tra `/health` của backend ở `beforeAll` hoặc đầu mỗi test; gọi `test.skip(..., 'Backend not running')` thay vì để test fail.
- [ ] **E2E — `data-retention.spec.ts` chạy workspace cleanup trong `finally`**
  - [ ] Bọc body mỗi test trong `try { ... } finally { await deleteWorkspace(...) }` (hoặc dùng `afterEach`/`afterAll` với captured `workspaceId`).
- [ ] **Lint & verify**
  - [ ] `cd nowing_backend && uv run ruff check app/routes/workspaces_routes.py app/retriever/documents_hybrid_search.py app/retriever/chunks_hybrid_search.py tests/integration/workspaces/test_data_retention.py tests/integration/workspaces/test_data_retention_concurrency.py`
  - [ ] `cd nowing_backend && uv run pytest tests/integration/workspaces/test_data_retention.py tests/integration/workspaces/test_data_retention_concurrency.py -q`
  - [ ] `cd nowing_web && pnpm tsc --noEmit`
  - [ ] `cd nowing_web && pnpm exec biome check tests/zero/test-archived-sync.spec.ts tests/workspace-settings/data-retention.spec.ts`
  - [ ] `cd nowing_web && pnpm test:e2e tests/zero/test-archived-sync.spec.ts tests/workspace-settings/data-retention.spec.ts` (khi backend + Zero cache đang chạy)

---

## Dev Notes

### Tại sao là follow-up của `3-7`?

Story `3-7` đã hoàn thành migration, schema, route, lifecycle task, UI, Zero sync và các test cơ bản. Tuy nhiên, trong quá trình code review adversarial và `_bmad-output/planning-artifacts/sprint-change-proposal-defer-tech-debt-2026-08-08.md`, nhóm phát hiện 4 item chưa đóng:

| # | Defer item | File/line hiện tại | Hậu quả nếu không xử lý |
|---|------------|--------------------|--------------------------|
| 1 | Race condition khi concurrent update retention | `workspaces_routes.py:281–283` select thường, không lock | Last-write-wins trên `document_retention_days`/`auto_archive_enabled` |
| 2 | Thiếu negative assertion trong hybrid-search test | `tests/integration/workspaces/test_data_retention.py:482–521` | Test có thể pass vì DB rỗng thay vì filter thực sự hoạt động |
| 3 | `test-archived-sync.spec.ts` không skip khi backend down | `tests/zero/test-archived-sync.spec.ts:22–66` | Test fail ở setup, làm nhiễu CI/local run khi không có backend |
| 4 | `data-retention.spec.ts` không dọn workspace khi test fail giữa chừng | `tests/workspace-settings/data-retention.spec.ts:19–247` | Rác workspace tích lũy trong test DB |

Story này chỉ củng cố — không thêm feature mới, không thay đổi PRD/Architecture.

### Trạng thái hiện tại của retention implementation (từ `3-7`)

**Data model (`nowing_backend/app/db.py`):**

- `Workspace.document_retention_days` (`dòng 1957`) — `Integer`, nullable.
- `Workspace.auto_archive_enabled` (`dòng 1958–1960`) — `Boolean`, default `false`, có index.
- `Workspace.document_retention_action` (`dòng 1961–1966`) — `String(20)`, default `"archive"`.
- `Document.archived_at` (`dòng 1548`) — `TIMESTAMP(timezone=True)`, nullable, index.
- Composite index `ix_documents_archived_at_workspace_id` (`dòng 1510`).

**Route & validation (`nowing_backend/app/routes/workspaces_routes.py:261–319`):**

- `update_workspace` đã kiểm tra `Permission.SETTINGS_UPDATE`.
- Validation app-layer đã tồn tại: `auto_archive_enabled=true` cần `document_retention_days` là số nguyên dương và `<= 36500`.
- Update dùng `setattr` chung trên `update_data`.

**Hybrid search / citation guardrails:**

- `documents_hybrid_search.py:244` — `Document.archived_at.is_(None)` trong `base_conditions`.
- `chunks_hybrid_search.py:106, 174, 269` — `Document.archived_at.is_(None)` ở các query chunk.

**Celery lifecycle task (`nowing_backend/app/tasks/celery_tasks/document_retention_task.py`):**

- `apply_document_retention_policies` chạy hàng ngày (`celery_app.py:345–348`).
- Với mỗi workspace `auto_archive_enabled=true` và `document_retention_days > 0`, set `archived_at=now()` cho documents cũ hơn retention window.
- Nếu `document_retention_action == "delete"`, đặt `status={"state": "deleting"}` và dispatch `delete_document_task`.

**Web UI:**

- `nowing_web/app/dashboard/[workspace_id]/workspace-settings/data-retention/page.tsx` — thin server component.
- `nowing_web/components/settings/data-retention-manager.tsx` — client component quản lý state, validation UI, gọi `updateWorkspace`.
- `nowing_web/zero/queries/documents.ts:8` — `where("archivedAt", "IS", null)` để loại archived docs khỏi real-time list.

**Migration:**

- `nowing_backend/alembic/versions/176_add_document_retention.py` đã thêm các cột, index, và reconcile `zero_publication`.

### Điểm cần chạm `SELECT FOR UPDATE`

Trong `nowing_backend/app/routes/workspaces_routes.py:281–284`, hiện tại:

```python
result = await session.execute(
    select(Workspace).filter(Workspace.id == workspace_id)
)
db_workspace = result.scalars().first()
```

Cần thay bằng:

```python
result = await session.execute(
    select(Workspace)
    .filter(Workspace.id == workspace_id)
    .with_for_update()
)
db_workspace = result.scalars().first()
```

Hoặc dùng `session.get` với `with_for_update` nếu project dùng SQLAlchemy >= 2.0 và `AsyncSession.get` hỗ trợ:

```python
db_workspace = await session.get(
    Workspace, workspace_id, with_for_update=True
)
```

**Chú ý:**

- Lock hàng `workspaces` được giữ cho đến khi `await session.commit()` (dòng 306) hoặc `await session.rollback()` (dòng 316) chạy.
- `SELECT FOR UPDATE` trong `AsyncSession` yêu cầu transaction đang mở. `get_async_session` (`app/db.py:4189–4191`) cung cấp session từ `async_session_maker()`, tự động bắt đầu transaction khi có query.
- Vẫn cần giữ validation hiện có (dòng 291–302):

```python
if update_data.get("auto_archive_enabled"):
    days = update_data.get("document_retention_days")
    if not isinstance(days, int) or days <= 0:
        raise HTTPException(status_code=400, detail="...")
    if days > 36500:
        raise HTTPException(status_code=400, detail="...")
```

- Nếu muốn thêm DB-level guard thực sự (ngoài app validation), có thể bổ sung `CheckConstraint` trên `Workspace` hoặc migration mới:

```sql
CHECK (NOT auto_archive_enabled OR document_retention_days > 0)
```

**Khuyến nghị:** Story này tập trung vào `SELECT FOR UPDATE` + test robustness; DB CHECK constraint là defense-in-depth tùy chọn, nếu làm thì cần migration backward-compatible.

### Negative assertion trong hybrid search test

Trong `nowing_backend/tests/integration/workspaces/test_data_retention.py:482–521`, test hiện tại thêm `visible` + `archived` documents và 2 chunks, rồi gọi `hybrid_search` và assert `archived.id not in doc_ids`. Để tránh trường hợp test pass vì `hybrid_search` trả về kết quả rỗng (do chunks chưa được flush hoặc query sai), cần assert số lượng chunk trong DB trước khi search:

```python
from sqlalchemy import func, select

# ... sau khi db_session.add_all([_make_chunk(...), _make_chunk(...)])
# và await db_session.flush()

chunk_count = (
    await db_session.execute(
        select(func.count(Chunk.id)).where(
            Chunk.document_id.in_([visible.id, archived.id])
        )
    )
).scalar()
assert chunk_count == 2, f"Expected 2 chunks, found {chunk_count}"
```

`Chunk` đã được import ở dòng 20 của file test. Assertion này đảm bảo nếu hybrid search không trả về `archived` thì đúng là do filter `archived_at.is_(None)`, không phải do DB thiếu dữ liệu.

### Cách skip Playwright E2E khi backend không chạy

Trong `nowing_web/tests/zero/test-archived-sync.spec.ts`, thêm health check ở `test.beforeAll` hoặc đầu mỗi test:

```typescript
import { expect, test } from "@playwright/test";

const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ?? "http://localhost:8000";

test.describe("Zero sync — archived_at", () => {
	test.beforeAll(async ({ request }) => {
		const health = await request.get(`${backendUrl}/health`).catch(() => null);
		test.skip(!health || !health.ok(), "Backend not running — skipping Zero archived sync test");
	});

	// ... existing test
});
```

Hoặc nếu muốn gọn, thêm ngay đầu test body:

```typescript
const health = await request.get(`${backendUrl}/health`).catch(() => null);
test.skip(!health || !health.ok(), "Backend not running");
```

Lưu ý: `request` fixture của Playwright gọi được từ `test.beforeAll` và trả về `APIResponse`. Phải skip trước khi sử dụng `page` hoặc tạo workspace.

### Vị trí `finally` cleanup trong `data-retention.spec.ts`

Hiện tại mỗi test gọi `await deleteWorkspace(...)` ở cuối. Nếu assertion ở giữa throw, workspace không được dọn. Có 2 cách:

**Cách 1: `try/finally` trong mỗi test (khuyến nghị, explicit):**

```typescript
test("owner can open data retention tab...", async ({ page, request }) => {
	const ownerToken = await acquireTestToken(request);
	const workspace = await createWorkspace(request, ownerToken, `ATDD Data Retention ${Date.now()}`);
	const workspaceId = workspace.id;

	try {
		// ... test body ...
	} finally {
		await deleteWorkspace(request, ownerToken, workspaceId).catch(() => {});
	}
});
```

**Cách 2: `test.afterEach` với biến scoped:**

```typescript
let workspaceToClean: { id: number; token: string } | null = null;

test.afterEach(async ({ request }) => {
	if (workspaceToClean) {
		await deleteWorkspace(request, workspaceToClean.token, workspaceToClean.id).catch(() => {});
		workspaceToClean = null;
	}
});
```

Khuyến nghị cách 1 vì không chia sẻ state giữa các test và rõ ràng trong ATDD.

---

## Review Findings

- Các finding dẫn đến story này xuất phát từ `_bmad-output/planning-artifacts/sprint-change-proposal-defer-tech-debt-2026-08-08.md` §Section 4 (Epic 3 — Add Story 3.7-followup: Retention Hardening).
- `AD-DEFER-4` trong `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` ghi nhận: schema + enforcement doc retention đã có; phần legal/right-to-delete cho `Memory` còn mở — **không thuộc scope** của story follow-up này.
- Story `3-7` gốc đã `done`; baseline file của nó là `92ba8f83`, còn baseline của follow-up là `cbe10c1` (HEAD hiện tại).

---

### Code Review Findings — 2026-08-23

All acceptance criteria PASS, nhưng review tìm thấy issues cần xử lý trước khi coi story done.

#### Decision Needed

- [x] [Review][Decision] Có nên lock mọi `PUT /workspaces/{id}` hay chỉ khi payload chạm retention fields? — `workspaces_routes.py:281-283` dùng `with_for_update()` vô điều kiện, có thể tăng lock contention với các update khác (name, QnA, v.v.).
- [x] [Review][Decision] Có bổ sung `CHECK` constraint DB-level cho retention invariant? — `app/db.py:1957-1966` / `alembic/versions/176_add_document_retention.py:22-47` chưa có, cần migration mới nếu làm.
- [x] [Review][Decision] Có lock `Workspace` row trong lifecycle task `document_retention_task.py`? — `document_retention_task.py:28-44` đọc `document_retention_days`/`action` không lock, race với `update_workspace` đang chạy.

#### Patch

- [x] [Review][Patch] Validation trạng thái cuối cho retention fields — `workspaces_routes.py:289-305` chỉ validate khi `auto_archive_enabled` có trong payload, cho phép workspace đã bật bị set `document_retention_days=null`/`36501` hoặc `document_retention_action=null` gây 500.
- [x] [Review][Patch] Rollback `AsyncSession` trước khi raise `HTTPException` sau `SELECT FOR UPDATE` — `workspaces_routes.py:281-302, 313-314` giữ row lock đến teardown, block concurrent updates.
- [x] [Review][Patch] Thêm lock timeout hoặc `nowait` cho `SELECT FOR UPDATE` — `workspaces_routes.py:281-283` hiện không có timeout, có thể treo vô hạn.
- [x] [Review][Patch] Backend URL fallback không nhất quán trong `test-archived-sync.spec.ts` — `test-archived-sync.spec.ts:24-28` vs `66-69` dùng 2 chuỗi fallback khác nhau.
- [x] [Review][Patch] Làm chặt negative assertion hybrid-search — `test_data_retention.py:515-543` nên assert tổng `chunk_count == 2` và trạng thái `archived_at` của 2 documents trước khi search.
- [x] [Review][Patch] Thêm `test_data_retention_concurrency.py` vào lint/verify commands — `3-7-followup-retention-hardening.md:54-55` chưa include file mới.
- [x] [Review][Patch] Cleanup `data-retention.spec.ts` không nuốt lỗi — `data-retention.spec.ts:58-60` dùng `.catch(() => {})` silent, nên log hoặc re-throw kết hợp.

#### Defer (pre-existing / ngoài scope strict)

- [x] [Review][Defer] `WorkspaceWithStats` list endpoint trả default retention values — `workspaces_routes.py:201-215` pre-existing từ `3-7`, cần update `read_workspaces`.
- [x] [Review][Defer] Lifecycle task không idempotent dưới concurrent Celery workers — `document_retention_task.py:28-59` pre-existing, cần bulk `UPDATE ... RETURNING id`.
- [x] [Review][Defer] Concurrency test chưa chứng minh `with_for_update` cần thiết — `test_data_retention_concurrency.py:100-120` cần test hook phức tạp hơn.
- [x] [Review][Defer] `data-retention.spec.ts` cần skip khi backend down — `data-retention.spec.ts:19-174` nên có shared `beforeAll` health check.
- [x] [Review][Defer] Cleanup `data-retention.spec.ts` để lại member user — `data-retention.spec.ts:63-128, 172-173` pre-existing pattern, nên xóa user sau khi xóa workspace.

#### Dismiss

- (không có — tất cả findings đều có cơ sở thực hoặc được merge)

## Next Steps / Completion Note

1. Implement 4 task groups ở trên.
2. Chạy verification commands trong phần **Tasks / Subtasks**.
3. Khi tất cả test pass, chuyển `sprint-status.yaml` `3-7-followup` từ `ready-for-dev` → `in-progress` → `review` → `done` theo quy trình BMAD.
4. Không cần migration mới nếu chỉ thêm `SELECT FOR UPDATE` và sửa test. Nếu quyết định bổ sung `CHECK` constraint DB-level, tạo migration Alembic mới (revision tiếp theo sau `176`) và cập nhật `nowing_backend/app/db.py` `Workspace.__table_args__`.

---

*Meta: Document generated for `Luisphan` — `document_output_language: Việt Nam` | `communication_language: Việt Nam`.*
