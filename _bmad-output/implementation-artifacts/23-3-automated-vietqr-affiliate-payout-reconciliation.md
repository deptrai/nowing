story_key: 23-3-automated-vietqr-affiliate-payout-reconciliation
status: done
baseline_commit: 14d9eb4729cfa97ba8d6c70281b37a1c49618a80
epic: 23
story: 3
---

# Story 23.3: Automated VietQR Affiliate Payout Reconciliation

Status: done

<!-- Note: Governed by FR-91, INV-23.10, INV-23.11, and Architecture Spine: architecture-epic23-lead-infrastructure.md -->

## Story

As a platform administrator and finance manager,
I want automated 24/7 VietQR / Napas bank payout reconciliation with DB row-level locking, idempotent transaction references, and automated 10% PIT (Thuế TNCN) deduction,
So that affiliate partners receive instant commission withdrawals without double-spending, duplicate bank transfers, or accounting reconciliation errors.

---

## Acceptance Criteria

### AC-1 — Double-Entry Ledger & Idempotent Row-Locked Payout Execution
**Given** an affiliate payout request in `pending` status,
**When** admin approves or auto-payout policy executes the request,
**Then** the backend acquires an explicit database row lock (`SELECT * FROM partner_payouts WHERE id = :id FOR UPDATE`),
**And** moves funds from `partner.available_balance_micros` to `partner.hold_balance_micros`,
**And** generates an idempotent transaction reference (`tx_reference = f"NOWING-PAY-{payout.id}-{int(time.time())}"`),
**And** dispatches the transfer via Napas 24/7 VietQR payment gateway API, updating status to `processing`.

### AC-2 — Thuế TNCN (PIT) 10% Automated Calculation (TT 111/2013/TT-BTC)
**Given** a payout request amount > 2,000,000 VNĐ (or equivalent `amount_micros`),
**When** creating or processing the payout transaction,
**Then** the system automatically calculates `pit_tax_micros = int(amount_micros * 0.10)` and `net_amount_micros = amount_micros - pit_tax_micros`,
**And** records `tax_deducted_micros` and `tax_code` in the `PartnerPayout` record, generating a downloadable tax deduction certificate statement.

### AC-3 — Bank Webhook Confirmation & Cryptographic HMAC Audit Receipt
**Given** an incoming bank transfer completion webhook callback from the payment gateway,
**When** the webhook signature is validated against the gateway secret,
**Then** `hold_balance_micros` is deducted, `total_paid_micros` is credited, `status` transitions to `completed`,
**And** an email receipt is dispatched to the partner containing:
  - Napas Transaction Number & Bank Reference Code
  - Beneficiary Account Name & Masked Account Number
  - Net Amount Transferred (VNĐ) & PIT Tax Deducted
  - SHA256 HMAC cryptographic audit verification hash.

### AC-4 — Two-Generals Problem Timeout & Auto-Reconciliation Worker
**Given** a payout request stuck in `processing` status due to a transient network timeout or gateway outage,
**When** the Celery Beat task `reconcile_pending_payouts` executes (runs every 2 minutes),
**Then** the worker queries the gateway status endpoint (`GET /v1/payouts/{tx_reference}`) before attempting any state transition:
  - If gateway reports `SUCCESS` -> finalize to `completed`.
  - If gateway reports `FAILED` -> revert `hold_balance_micros` back to `available_balance_micros` and mark `failed`.
  - If gateway reports `NOT_FOUND` and transaction age > 15 minutes -> safely mark `failed` and unlock funds.
  - **Never blindly retry transfer execution** to prevent duplicate money transfer.

---

## Tasks / Subtasks

- [x] **Task 1: Payout Reconciliation Engine (`nowing_backend/app/services/partner_payout_service.py`)**
  - [x] Implement `execute_payout_with_lock(session, payout_id)` using `SELECT ... FOR UPDATE`.
  - [x] Implement double-entry balance transfer (`available_balance` -> `hold_balance`).
  - [x] Implement 10% PIT tax deduction logic for payouts > 2,000,000 VNĐ.
  - [x] Generate unique, idempotent `tx_reference`.

- [x] **Task 2: VietQR / Napas Gateway Client (`nowing_backend/app/services/vietqr_payout_client.py`)**
  - [x] Implement `VietQRPayoutClient` with API endpoints:
    - `POST /v1/transfers` (initiate payout)
    - `GET /v1/transfers/{tx_reference}` (query transaction status)
  - [x] HMAC-SHA256 signature signing and verification.

- [x] **Task 3: Webhook & Background Polling Worker**
  - [x] Webhook endpoint `POST /api/v1/partners/payouts/webhook` in `app/routes/partner_routes.py`.
  - [x] Celery Beat periodic task `app/tasks/celery_tasks/partner_payout_reconciliation_task.py`.
  - [x] Audit receipt with cryptographic HMAC-SHA256 signature.

- [x] **Task 4: Frontend Payout History Ledger Updates (`nowing_web/app/(home)/partners/dashboard/`)**
  - [x] Create `PayoutHistoryTable.tsx` with:
    - Status badges (`Pending`, `Processing` with spinner, `Completed` with checkmark, `Failed`).
    - Napas transaction reference pill with copy-to-clipboard.
    - Tax deduction breakdown (`Gross`, `-10% TT111`, `Net Received`).
    - Cryptographic Audit Receipt modal.

- [x] **Task 5: Automated Testing & Chaos Scenarios**
  - [x] Unit tests: Double-entry ledger math, PIT tax deduction rules, idempotent reference generator (9/9 pass).
  - [x] Integration tests: Concurrent payout approval attempts on PostgreSQL, Webhook settlement, Two-Generals refund on gateway failure (4/4 pass).

### Review Findings

- [x] [Review][Patch] Fix AttributeError: 'TaxCalculationResult' object has no attribute 'tax_code' [`partner_payout_service.py:30` & `partner_service.py:519`]
- [x] [Review][Patch] Fix Double Balance Deduction and premature total_paid_micros increment in request_payout [`partner_service.py:473`]
- [x] [Review][Patch] Fix Infinite Refund Replay Attack on duplicate FAILED webhooks by adding status guard [`partner_payout_service.py:167`]
- [x] [Review][Patch] Fix parameter keyword mismatches (db_session vs session, secret_key vs webhook_secret) [`partner_routes.py:180` & `partner_payout_reconciliation_task.py:35,66`]
- [x] [Review][Patch] Enforce Fail-Closed Webhook authentication when webhook secret is unconfigured [`partner_routes.py:159`]
- [x] [Review][Patch] Handle Two-Generals NOT_FOUND status (>15m) and generate HMAC audit seal in auto-reconciliation worker [`partner_payout_service.py:240`]
- [x] [Review][Patch] Fix TT 111/2013/TT-BTC legal threshold comparison to >= 2,000,000 VND [`partner_payout_service.py:63`]
- [x] [Review][Patch] Add defensive null fallbacks in PayoutHistoryTable.tsx and fix typo in dashboard page [`PayoutHistoryTable.tsx:224` & `page.tsx:453`]

---

## Dev Agent Guardrails & Architectural Invariants

- **INV-23.10 (Payout DB Row Lock):** Bắt buộc dùng `SELECT * FROM partner_payouts WHERE id = :id FOR UPDATE` trước khi chuyển trạng thái tiền.
- **INV-23.11 (No Blind Retry on Timeout):** Khi gặp timeout cổng thanh toán, cấm gọi lại API chuyển tiền. Phải gọi API tra cứu trạng thái giao dịch (`GET /transfers/{tx_ref}`).

---

## Verification Commands

```bash
# 1. Run Payout Service Tests
cd nowing_backend
uv run pytest tests/unit/services/test_partner_payout_service.py tests/integration/services/test_partner_payout_reconciliation.py -q

# 2. Lint & Format
ruff check app/services/partner_payout_service.py app/routes/partner_routes.py app/tasks/payout_tasks.py
ruff format app/services/partner_payout_service.py app/routes/partner_routes.py app/tasks/payout_tasks.py

# 3. Frontend Typecheck & Biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check app/partners/dashboard/components/PayoutHistoryTable.tsx
```
