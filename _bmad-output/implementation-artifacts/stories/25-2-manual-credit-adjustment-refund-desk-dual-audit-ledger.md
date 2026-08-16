story_key: 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger
status: done
baseline_commit: be1122dd9ab3a0d92200ecfbc3c3545b736b04a0
epic: 25
story: 2
---

# Story 25.2: Manual Credit Adjustment & Refund Desk with Dual-Audit Ledger

Status: done

<!-- Note: Governed by INV-25.3, INV-25.2, INV-25.8, and Architecture Spine: epics.md (Epic 25) -->

## Story

As a Platform Operations Manager / Superadmin,  
I want to manually credit or debit tokens/credits to any workspace for compensation, off-platform bank top-ups, or partner promotions with strict 2-tier concurrency locks and immutable ledger auditing,  
So that customer billing disputes are resolved instantly without risk of double-spending, race conditions, or unauthorized internal credit minting.

---

## Acceptance Criteria

### AC-1 — Admin Manual Credit Adjustment Form & Validation
**Given** an authenticated Superadmin session on `/admin/credits` or `/admin/workspaces/{id}/credits`,  
**When** opening the adjustment modal,  
**Then** the form enforces mandatory fields:
- `workspace_id`: valid UUID/integer of target workspace.
- `amount_credits`: positive integer number of credits (e.g. 500 Credits = $5.00).
- `direction`: strictly `CREDIT` (top-up) or `DEBIT` (clawback/deduction).
- `reason`: mandatory explanation string (minimum 10 characters).
- `ticket_ref`: mandatory external reference (e.g. Zendesk/Jira ticket URL or bank transfer reference code).

### AC-2 — 2-Tier Concurrency Lock & Atomic Ledger Insertion
**Given** concurrent adjustment submissions or rapid double-clicks on the `Submit Adjustment` button,  
**When** processed by `ManualCreditAdjustmentService.adjust_credits()`,  
**Then** the backend enforces:
1. **Tier 1 (Redis Redlock):** acquires `lock:workspace_wallet:{workspace_id}` (TTL 10s) with `Idempotency-Key` tracking.
2. **Tier 2 (Postgres Lock):** locks the target wallet record via `SELECT * FROM workspace_wallets WHERE workspace_id = :id FOR UPDATE`.
3. Inserts an immutable transaction row into `credit_transactions` (`amount_micros`, `direction`, `reason`, `actor_admin_id`, `ticket_ref`).
4. Updates `workspace_wallets.credit_micros_balance` atomically in the same database transaction.

### AC-3 — Role-Based Staff Quota Guardrails
**Given** an operations staff member with a non-executive role (e.g. `Support Staff`),  
**When** attempting to grant a manual credit adjustment exceeding their daily threshold ($10 / 1,000 Credits per day),  
**Then** backend blocks execution with `HTTP 403 Forbidden` (`detail='Daily manual adjustment quota exceeded. Manager approval required.'`) and records the blocked attempt in `audit_events`.

### AC-4 — High-Density Credits Management & Audit Ledger UI
**Given** `/admin/credits`,  
**When** viewed by a Superadmin,  
**Then** it displays:
- Aggregate stats cards: Total Credits Minted, Total Manual Debits, Today's Adjustments Count, High-Value Adjustments Flag.
- High-density data table (36px row height, monospace numbers/dates) showing all manual credit adjustments with filters by date, admin, workspace, and reason.
- CSV Export action for monthly accounting and tax audits.

---

## Tasks / Subtasks

- [x] Task 1: Backend Manual Credit Adjustment Service & Ledger API (FastAPI)
  - [x] Implement `ManualCreditAdjustmentService.adjust_credits()` in `app/services/manual_credit_service.py`.
  - [x] Create API routes in `app/routes/admin_credits_routes.py`: `POST /api/v1/admin/credits/adjust` and `GET /api/v1/admin/credits/ledger`.
  - [x] Enforce `require_superuser` and daily quota limit check for non-manager admins.
- [x] Task 2: Concurrency & Lock Test Bench
  - [x] Add `tests/unit/services/test_manual_credits.py` with validation and idempotency tests (DB-backed coverage in `tests/integration/services/test_manual_credits.py`).
- [x] Task 3: Frontend Admin Credits Page & Modal UI
  - [x] Create `nowing_web/app/admin/credits/page.tsx` with high-density data matrix.
  - [x] Create `components/admin/ManualCreditModal.tsx` with live preview of USD value and validation.

### Review Findings (bmad-code-review 25.2)

- [x] [Review][Patch] Missing backend service and API route implementation [_bmad-output/implementation-artifacts/stories/25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md:60-63] — Implemented.
- [x] [Review][Patch] Missing frontend admin credits UI [_bmad-output/implementation-artifacts/stories/25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md:66-68] — Implemented.
- [x] [Review][Patch] Missing database schema / migrations [_bmad-output/implementation-artifacts/stories/25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md:38-41] — `credit_transactions` migration 222 and model created. `workspace_wallets` table was not created; see decision below.
- [x] [Review][Patch] Placeholder red-phase tests only [nowing_backend/tests/unit/services/test_manual_credits.py:1-32; nowing_backend/tests/integration/routes/test_admin_credits.py:1-16] — Real unit and integration tests implemented and passing.
- [x] [Review][Patch] Spec status / task completion mismatch [_bmad-output/implementation-artifacts/stories/25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger.md:1,10,60-68] — Story was marked `Status: review` in body and `ready-for-dev` in frontmatter while all tasks were checked `[x]`, despite zero implementation code. Status has been corrected to `in-progress` and tasks unchecked; the original disconnect misrepresented the actual state of the story.

#### Review 25.2 — 2026-08-16 (Blind Hunter + Edge Case Hunter + Acceptance Auditor)

##### Decision needed

- [x] [Review][Decision] `workspace_wallets` table vs existing `Workspace.credit_micros_balance` — Decision: keep existing `Workspace.credit_micros_balance` (from migration 221) and update the spec to reflect the actual wallet column. No separate `workspace_wallets` table needed. [manual_credit_service.py:186-188; 222_add_credit_transactions_table.py]
- [x] [Review][Decision] Role-based staff quota — Decision: keep `require_superuser` gate for now. The app has no support for non-superuser staff roles; the daily quota is applied to all superusers. A future role system can relax the gate. [admin_credits_routes.py:72; manual_credit_service.py:170-180]
- [x] [Review][Decision] Workspace-specific credits page — Decision: `/admin/credits` is sufficient for this story. The workspace-specific variant can be added if product later requires it. [nowing_web/app/admin/credits/page.tsx]

##### Patch

- [x] [Review][Patch] Route does not commit the session; ledger/wallet/audit writes may not persist [HIGH] — Fixed: `post_manual_credit_adjust` now calls `await session.commit()` for success and in the `ManualCreditQuotaExceededError` handler to persist the `AuditEvent`. [admin_credits_routes.py:82-111; manual_credit_service.py:221-222]
- [x] [Review][Patch] Daily quota race under concurrency [HIGH] — Fixed: added a per-admin `pg_advisory_xact_lock` (hashed from `actor_admin_id`) before the quota check so all manual-credit adjustments by the same admin serialize across workspaces. [manual_credit_service.py:169-180, 186-191]
- [x] [Review][Patch] Frontend double-click can create duplicate idempotency keys [HIGH] — Fixed: `ManualCreditModal` now stores the idempotency key in state and regenerates it only when the modal opens, not on every submit. [nowing_web/components/admin/ManualCreditModal.tsx:16-21, 54-66]
- [x] [Review][Patch] Ledger endpoint has no pagination [MEDIUM] — Fixed: added `limit` (default 50, max 100) and `offset` query parameters. [admin_credits_routes.py:115-142]
- [x] [Review][Patch] `Idempotency-Key` length not validated [MEDIUM] — Fixed: route now returns 400 if `Idempotency-Key` is empty or longer than 64 characters. [admin_credits_routes.py:75-79]
- [x] [Review][Patch] `reason` filter allows SQL wildcards [MEDIUM] — Fixed: `reason` filter now escapes `%` and `_` and uses `ESCAPE '\'`. [admin_credits_routes.py:132-133]
- [x] [Review][Patch] Postgres `FOR UPDATE` has no lock timeout [MEDIUM] — Fixed: `adjust_credits` sets `SET LOCAL lock_timeout = 5s` before the workspace `FOR UPDATE`. [manual_credit_service.py:186-188]
- [x] [Review][Patch] Missing "Today's Adjustments Count" stat card [MEDIUM] — Fixed: added `todayCount` stat card in the dashboard. [nowing_web/app/admin/credits/page.tsx:79-95]
- [x] [Review][Patch] CSV export does not quote all fields [LOW] — Fixed: all fields are now passed through `csvField`, which quotes and escapes commas/quotes/newlines. [nowing_web/app/admin/credits/page.tsx:19-44]
- [x] [Review][Patch] `AuditEvent` does not store `workspace_id` or `reason` [LOW] — Fixed: removed the unused `workspace_id` and `reason` parameters from `_record_audit`; `AuditEvent` captures `action`, `actor_id`, and `ticket_ref` for the blocked attempt. [manual_credit_service.py:226-241; app/db.py:5999-6002]
- [x] [Review][Patch] Weak idempotency-key fallback [LOW] — Fixed: fallback now uses `crypto.getRandomValues()` to build a v4 UUID before the last-resort `Date.now()` fallback. [nowing_web/components/admin/ManualCreditModal.tsx:16-21]

##### Defer

- [x] [Review][Defer] 50-thread concurrent double-submit stress test — The existing integration test covers same-key double-submit but not a 50-thread race. Add a dedicated concurrency stress test in a later gate. [tests/integration/routes/test_admin_credits.py:142-178; tests/unit/services/test_manual_credits.py]
- [x] [Review][Defer] Database CHECK constraint for `Workspace.credit_micros_balance >= 0` — The application-level check plus `FOR UPDATE` prevents negative balances under concurrency; a DB-level check is defense-in-depth and can be added later. [app/db.py:1892-1897; 221_add_multi_seat_crm_and_credit_pooling.py:29-38]

##### Dismissed

- React text nodes are auto-escaped, so `reason`/`ticket_ref` display is not an XSS vector.
- Direction pattern `^(CREDIT|DEBIT)$` is correct per AC-1; case sensitivity is intended.
- AC-3 only requires audit for blocked quota attempts, not every successful transaction.
- Tailwind `h-9` equals 36px, matching the AC-4 high-density row height.
- Workspace validation under the `FOR UPDATE` lock is safe; Redis lock is just a key and the DB query on a non-existent workspace returns no row.
- `migration 221` CRM tables are pre-existing and not caused by the 25.2 diff.

### Review Findings — Test Additions (2026-08-16)

#### Patch (cần xử lý)

- [x] [Review][Patch] `test_adjust_credits_concurrent_quota_guard` dùng hardcoded `600` thay vì constant `DAILY_CREDIT_QUOTA`, dễ break nếu quota thay đổi (`tests/integration/services/test_manual_credits.py:241`).
- [x] [Review][Patch] `test_adjust_credits_concurrent_quota_guard` tự dọn dữ liệu (User/Workspace/AuditEvent) thủ công, không dùng fixture rollback, dễ leak nếu test fail giữa chừng (`tests/integration/services/test_manual_credits.py:278-297`).
- [x] [Review][Patch] Thiếu test boundary 64 ký tự cho `Idempotency-Key` (hiện chỉ test 65 ký tự bị reject) (`tests/integration/routes/test_admin_credits.py:159`).
- [x] [Review][Patch] Thiếu test `limit > 100` và `limit = 100` cho `/ledger` (`tests/integration/routes/test_admin_credits.py:270-280`).
- [x] [Review][Patch] Test pagination không assert ordering `created_at DESC` theo route (`tests/integration/routes/test_admin_credits.py:270-280`).
- [x] [Review][Patch] Thiếu test `_` wildcard escaping (hiện chỉ test `%`) (`tests/integration/routes/test_admin_credits.py:283-307`).
- [x] [Review][Patch] `test_post_admin_credits_adjust_quota_guardrail` assert `AuditEvent` chưa kiểm tra `actor_id`/`subject_id` khớp admin (`tests/integration/routes/test_admin_credits.py:142-148`).

#### Defer (pre-existing / ngoài phạm vi diff)

- [x] [Review][Defer] Thiếu test AC-1 validation cho `reason` min length, `ticket_ref` missing, `workspace_id` format/negative, `amount_credits` zero/negative, `direction` invalid values — các trường hợp này đã có unit test cơ bản, chưa cần bổ sung ngay trong diff này.
- [x] [Review][Defer] Thiếu test trực tiếp Redis Redlock / Postgres `FOR UPDATE` / `lock_timeout` — khó assert từ bên ngoài, phụ thuộc implementation internals.
- [x] [Review][Defer] Thiếu test quota cho `DEBIT` và non-superuser role — hạ tầng role chưa hỗ trợ, đã ghi nhận trong quyết định story.
- [x] [Review][Defer] Thiếu test CSV export, aggregate stats cards, 36px row height — thuộc AC-4 UI, ngoài phạm vi test backend vừa thêm.
