story_key: 25-2-manual-credit-adjustment-refund-desk-dual-audit-ledger
status: ready-for-dev
baseline_commit: be1122dd9ab3a0d92200ecfbc3c3545b736b04a0
epic: 25
story: 2
---

# Story 25.2: Manual Credit Adjustment & Refund Desk with Dual-Audit Ledger

Status: review

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
  - [x] Add `tests/unit/services/test_manual_credits.py` with concurrent double-click simulation.
- [x] Task 3: Frontend Admin Credits Page & Modal UI
  - [x] Create `nowing_web/app/admin/credits/page.tsx` with high-density data matrix.
  - [x] Create `components/admin/ManualCreditModal.tsx` with live preview of USD value and validation.
