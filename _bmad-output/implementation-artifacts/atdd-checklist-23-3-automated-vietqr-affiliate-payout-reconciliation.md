---
stepsCompleted:
  - 'step-01-preflight-and-context'
  - 'step-02-generation-mode'
  - 'step-03-test-strategy'
  - 'step-04-generate-tests'
  - 'step-05-validate-and-complete'
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-08-16'
workflowType: 'testarch-atdd'
storyId: '23.3'
storyKey: '23-3-automated-vietqr-affiliate-payout-reconciliation'
storyFile: '_bmad-output/implementation-artifacts/23-3-automated-vietqr-affiliate-payout-reconciliation.md'
atddChecklistPath: '_bmad-output/implementation-artifacts/atdd-checklist-23-3-automated-vietqr-affiliate-payout-reconciliation.md'
generatedTestFiles:
  - 'nowing_backend/tests/unit/services/test_partner_payout_service.py'
  - 'nowing_backend/tests/integration/services/test_partner_payout_reconciliation.py'
inputDocuments:
  - '_bmad-output/implementation-artifacts/23-3-automated-vietqr-affiliate-payout-reconciliation.md'
  - '_bmad-output/planning-artifacts/architecture-epic23-lead-infrastructure.md'
  - '_bmad/custom/nowing-quality-pipeline.md'
---

# ATDD Checklist - Epic 23, Story 3: Automated VietQR Affiliate Payout Reconciliation

**Date:** 2026-08-16
**Author:** Luis (Master Test Architect)
**Primary Test Level:** Unit (Mock DB) + Integration (Real Postgres Row Locking)
**Worktree Path:** `/Users/luisphan/Documents/GitHub/nowing-23-3`
**Git Branch:** `feat/23-3-automated-vietqr-affiliate-payout-reconciliation`

---

## Story Summary

As a platform administrator and finance manager,
I want automated 24/7 VietQR / Napas bank payout reconciliation with DB row-level locking, idempotent transaction references, and automated 10% PIT (Thuế TNCN) deduction,
So that affiliate partners receive instant commission withdrawals without double-spending, duplicate bank transfers, or accounting reconciliation errors.

---

## Acceptance Criteria

1. **AC-1 — Double-Entry Ledger & Idempotent Row-Locked Payout Execution**: Backend acquires explicit row lock (`SELECT * FROM partner_payouts WHERE id = :id FOR UPDATE`), moves funds `available_balance_micros` -> `hold_balance_micros`, generates idempotent `tx_reference = f"NOWING-PAY-{payout.id}-{int(time.time())}"`, and sets status to `processing`.
2. **AC-2 — Thuế TNCN (PIT) 10% Automated Calculation (TT 111/2013/TT-BTC)**: Payout amounts > 2,000,000 VNĐ automatically calculate `pit_tax_micros = int(amount_micros * 0.10)` and `net_amount_micros = amount_micros - pit_tax_micros`, recording `tax_deducted_micros` and `tax_code`.
3. **AC-3 — Bank Webhook Confirmation & Cryptographic HMAC Audit Receipt**: Webhook callback with HMAC SHA256 signature verification deducts `hold_balance_micros`, credits `total_paid_micros`, marks status `completed`, and produces cryptographic HMAC audit receipt.
4. **AC-4 — Two-Generals Problem Timeout & Auto-Reconciliation Worker (INV-23.11)**: Celery Beat task `reconcile_pending_payouts` queries gateway status (`GET /v1/payouts/{tx_reference}`) on timeouts before transitioning state. Never blindly retries payout dispatches.

---

## Story Integration Metadata

- **Story ID:** `23.3`
- **Story Key:** `23-3-automated-vietqr-affiliate-payout-reconciliation`
- **Story File:** `_bmad-output/implementation-artifacts/23-3-automated-vietqr-affiliate-payout-reconciliation.md`
- **Checklist Path:** `_bmad-output/implementation-artifacts/atdd-checklist-23-3-automated-vietqr-affiliate-payout-reconciliation.md`
- **Generated Test Files:**
  - `nowing_backend/tests/unit/services/test_partner_payout_service.py`
  - `nowing_backend/tests/integration/services/test_partner_payout_reconciliation.py`

---

## Red-Phase Test Scaffolds Created

### Unit Tests (7 tests)
**File:** `nowing_backend/tests/unit/services/test_partner_payout_service.py`

- 🔴 **Test:** `test_execute_payout_acquires_row_lock_and_moves_to_hold`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-1 & INV-23.10 row locking and double-entry balance deduction.
- 🔴 **Test:** `test_execute_payout_fails_when_balance_insufficient`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-1 balance guardrails.
- 🔴 **Test:** `test_pit_tax_deduction_for_amounts_above_2m_vnd`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-2 10% PIT tax calculation for amounts > 2,000,000 VNĐ.
- 🔴 **Test:** `test_pit_tax_exemption_for_amounts_under_or_equal_2m_vnd`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-2 exemption for amounts <= 2,000,000 VNĐ.
- 🔴 **Test:** `test_hmac_sha256_webhook_signature_verification`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-3 HMAC-SHA256 signature validation against gateway secret.
- 🔴 **Test:** `test_webhook_confirmation_finalizes_balances_and_creates_receipt`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-3 hold balance clearance, total paid credit, receipt audit creation.
- 🔴 **Test:** `test_reconcile_worker_queries_gateway_status_on_timeout`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-4 & INV-23.11 safe query before transition on network timeout.
- 🔴 **Test:** `test_reconcile_worker_unlocks_funds_when_gateway_reports_failed`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** AC-4 safe refund of hold balance when gateway transaction failed.

### Integration Tests (2 tests)
**File:** `nowing_backend/tests/integration/services/test_partner_payout_reconciliation.py`

- 🔴 **Test:** `test_concurrent_payout_approval_prevents_double_spending`
  - **Status:** RED (Skipped pending real Postgres DB execution)
  - **Verifies:** Concurrency safety with `SELECT FOR UPDATE`.
- 🔴 **Test:** `test_bank_webhook_callback_success_updates_balances_and_audits`
  - **Status:** RED (Skipped pending implementation)
  - **Verifies:** Full-cycle webhook ingestion and ledger balance settlement.

---

## Red-Green-Refactor Workflow

### RED Phase (Complete) ✅
- All unit & integration test scaffolds generated with clear failure/skip reasons.
- Worktree initialized and isolated at `/Users/luisphan/Documents/GitHub/nowing-23-3`.

### GREEN Phase (Dev Team Next Step)
1. Implement `PartnerPayoutService` in `app/services/partner_payout_service.py`.
2. Implement `VietQRPayoutClient` in `app/services/vietqr_payout_client.py`.
3. Add webhook endpoint `POST /api/v1/partners/payouts/webhook` in `app/routes/partner_routes.py`.
4. Add Celery Beat periodic task `reconcile_pending_payouts` in `app/tasks/payout_tasks.py`.
5. Remove `pytest.mark.skip` one by one and achieve 100% green tests.

---

## Next steps in Nowing quality pipeline

**Vừa xong:** `bmad-testarch-atdd` — Khởi tạo git worktree `/Users/luisphan/Documents/GitHub/nowing-23-3` (branch `feat/23-3-automated-vietqr-affiliate-payout-reconciliation`) và hoàn tất scaffolding Red-phase ATDD tests cho Story 23.3.

**Bước tiếp theo (BẮT BUỘC):**
- [4.6] `bmad-nowing-integration-test` — Viết và verify integration tests với PostgreSQL thực tế (`SELECT FOR UPDATE` concurrency).
- [4.7] `bmad-dev-story` — Triển khai code logic Story 23.3 để chuyển toàn bộ red tests thành green.

**Bước tiếp theo (recommended):**
- [4.8] `bmad-code-review` — 3-layer adversarial code review sau khi dev xong.

**Còn lại trong pipeline:** 6 bước — xem `_bmad/custom/nowing-quality-pipeline.md`.
