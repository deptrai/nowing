# Story 6.9: Frontend — Admin Gift Requests UI `/admin/gift-requests`

Status: done

## Story

As a Superuser (admin),
I want trang `/admin/gift-requests` để xem, approve, reject gift requests pending,
So that khi Stripe fallback, tôi có dashboard để xử lý nhanh, copy gift code và gửi cho người mua.

## Acceptance Criteria

1. Trang `/admin/gift-requests` mirror pattern của `/admin/subscription-requests` — superuser-only, non-superuser thấy "Access denied".
2. Fetch `GET /api/v1/admin/gift-requests?status=pending` khi load, render table gồm các cột: User email, Plan, Duration, Created At, Actions.
3. Tabs filter trạng thái: `Pending | Approved | Rejected | All` — default `Pending`. Khi đổi tab, refetch list với query param tương ứng.
4. Nút **Approve** trên mỗi row: confirm dialog → POST → copy gift_code vào clipboard → toast success → refetch.
5. Nút **Reject** trên mỗi row: prompt reason → POST → toast → refetch.
6. Row approved hiển thị cột `gift_code` với nút **Copy**.
7. Sidebar admin menu thêm link "Gift Requests" trong `LayoutDataProvider.tsx`.
8. Contracts: thêm Zod schema `giftRequestItem`, `giftRequestListResponse`, `giftRequestApproveResponse` vào `nowing_web/contracts/types/stripe.types.ts`.

## Tasks / Subtasks

- [x] Contracts (AC: 8)
  - [x] Thêm schemas vào `nowing_web/contracts/types/stripe.types.ts`:
    - `giftRequestItem`, `giftRequestListResponse`, `giftRequestApproveResponse`
  - [x] Export types `GiftRequestItem`, `GiftRequestListResponse`, `GiftRequestApproveResponse`.

- [x] Page component (AC: 1, 2, 3, 4, 5, 6)
  - [x] Tạo `nowing_web/app/admin/gift-requests/page.tsx`.
  - [x] Thêm state `activeStatus: "pending" | "approved" | "rejected" | "all"`, tabs UI.
  - [x] `handleApprove`: POST → clipboard → toast → refetch.
  - [x] `handleReject`: prompt reason → POST → toast + refetch.
  - [x] Render cột `Duration`, cột `Gift Code` với nút Copy cho row approved.
  - [x] Access denied guard (403 → `accessDenied` state → UI).

- [x] Sidebar menu (AC: 7)
  - [x] Edit `LayoutDataProvider.tsx` — thêm "Gift Requests" entry sau `/admin/subscription-requests`, isActive guard.

- [x] Verify
  - [x] `npx tsc --noEmit` → 0 errors trong Story 6.9 files.
  - [x] Backend no regression: `uv run pytest tests/unit/` → **408 passed**.
  - [x] `Query(alias="status")` fix preserves `?status=` API contract.

## Dev Notes

### Dependency

- Story 6.8 (backend endpoints).
- `nowing_web/lib/auth-utils.ts` — `authenticatedFetch`, `isAuthenticated`, `redirectToLogin`.
- Pattern reference: `nowing_web/app/admin/subscription-requests/page.tsx`.

### Bug fix: Query alias

Backend patch Story 6.8 review đổi Python param `status` → `status_filter` để fix module shadowing. Dùng `Query(alias="status")` trong FastAPI để preserve external `?status=` contract — frontend không cần thay đổi.

### Out of Scope

- Email notification (admin copy-paste thủ công).
- Pagination (defer — volume nhỏ).
- Bulk approve (defer).

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- `npx tsc --noEmit` → 0 errors trong các files Story 6.9.
- `uv run pytest tests/unit/ -q ...` → **408 passed**, 1 pre-existing dexscreener error.
- `Query(alias="status")` + `Query` validators cho limit/offset thêm vào `admin_routes.py`.

### Completion Notes List

- Thêm 3 Zod schemas + 3 export types vào `contracts/types/stripe.types.ts`.
- `app/admin/gift-requests/page.tsx`: status tabs (pending/approved/rejected/all), handleApprove (clipboard+toast), handleReject (prompt+POST), copyCode button, 403/accessDenied guard.
- `LayoutDataProvider.tsx`: "Gift Requests" sidebar entry visible chỉ cho superuser, isActive guard tại `/admin/gift-requests`.
- `admin_routes.py`: thêm `Query` import, `Query(alias="status")` fix, `Query` validation cho limit/offset (patch breaking change từ Story 6.8 review).

### File List

- `nowing_web/contracts/types/stripe.types.ts` (modified — thêm `giftRequestItem`, `giftRequestListResponse`, `giftRequestApproveResponse`)
- `nowing_web/app/admin/gift-requests/page.tsx` (new — admin gift requests UI page)
- `nowing_web/components/layout/providers/LayoutDataProvider.tsx` (modified — Gift Requests sidebar entry)
- `nowing_backend/app/routes/admin_routes.py` (modified — `Query(alias="status")` fix, Query validators)

### Change Log

- 2026-04-17: Story 6.9 implemented — Zod contracts, admin UI page, sidebar entry, Query alias fix để preserve API contract.
- 2026-04-17: Code review completed (3-layer adversarial: Blind Hunter + Edge Case Hunter + Acceptance Auditor). Acceptance Auditor: all 8 ACs PASS. Applied 7 patches (F1, F2, F4, F6, F7, F10, F12). 5 findings deferred to `deferred-work.md`. 3 reviewer concerns dismissed as false positives (enum case, XSS, Query alias).

## Review Findings (2026-04-17)

### Applied (7 patches)

- [x] **F1 High — AbortController on fetchRequests**: tab-switch race overwrote newer list with stale data. Added `AbortController` scoped to `activeStatus` effect; `signal.aborted` guards on state updates; passes `signal` to `authenticatedFetch`. [nowing_web/app/admin/gift-requests/page.tsx](nowing_web/app/admin/gift-requests/page.tsx)
- [x] **F2 High — Disable all row action buttons while any in flight**: `actionInProgress === req.id` allowed clicking Approve on row A then row B before A resolved → double-approve. Changed to `actionInProgress !== null`.
- [x] **F4 Medium — Persistent toast on clipboard failure**: clipboard rejection (insecure HTTP/iframe/permissions) fell back to default ~4s sonner toast, admin could miss the code. Added `{ duration: Infinity }` + "copy manually" hint on fallback branch.
- [x] **F6 Medium — Replace Vietnamese "tháng" in English admin UI**: hardcoded Vietnamese string leaked into English page. Replaced with `month` / `months` pluralization.
- [x] **F7 Medium — Move `logger.info` after `db_session.commit()`**: log was emitted before commit in both `approve_gift_request` and `reject_gift_request` — a crash between log and commit would log a code that was never persisted. Reordered both functions.
- [x] **F10 Low — Clear stale rows on error/403 paths**: `setRequests([])` added at top of `fetchRequests` so 401/403/error paths don't flash stale rows from prior tab.
- [x] **F12 Low — Surface `err.detail` on list-fetch error**: list fetch swallowed backend error detail. Now reads `err.detail ?? "Failed to load gift requests."`.

### Deferred (5 findings → `deferred-work.md`)

- F3 — Approve network-drop UX (refetch + tab switch hint)
- F5 — Wire Zod `safeParse` into fetchRequests (refactor)
- F8 — `count` field misleading (pagination future)
- F9 — Sidebar `isActive` exact-match refactor (cosmetic)
- F11 — Unknown `plan_id` fallback (covered once F5 lands)

### Dismissed (false positives)

- **"`GiftRequestStatus(status_filter)` ValueError on uppercase enum → 500"** — `GiftRequestStatus` is `StrEnum` with lowercase values; `GiftRequestStatus("pending")` works. Verified by Edge Case Hunter.
- **"XSS via `user_email` / `plan_id` / reason"** — React auto-escapes all `{}` interpolation; no `dangerouslySetInnerHTML` used. Safe.
- **"`Query(alias='status')` semantics incorrect"** — Correct pattern; preserves external `?status=` contract while renaming Python var to avoid `fastapi.status` module shadow.

### Verification

- `npx tsc --noEmit` — 0 errors in Story 6.9 files (CLEAN).
- `uv run pytest tests/unit/` — 507 passed (pre-existing dexscreener/document_hashing errors unrelated to Story 6.9).
