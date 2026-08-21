# ATDD Checklist: Story 25.3 - Affiliate Partner Payout Desk & Anti-Fraud Engine

**Status:** GREEN / VERIFIED (All Acceptance Criteria Met & Verified on Live Browser)  
**Story Spec:** [`_bmad-output/implementation-artifacts/stories/25-3-affiliate-partner-payout-desk-anti-fraud-engine.md`](../implementation-artifacts/stories/25-3-affiliate-partner-payout-desk-anti-fraud-engine.md)  
**Architectural Invariants:** `INV-25.2` (Immutable Audit Trail), `INV-25.4` (Atomic Credit Balance / Payout Locks), `INV-25.8` (Fail-Closed Admin Gate)

---

## 🎯 Acceptance Criteria & Test Matrix

| AC | Requirement | Test Level | Target File | Test Method | Status |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **AC-1** | Payout Approval Desk Data Matrix & 10% PIT Tax Deduction (>= 2,000,000 VND threshold) | Unit | `tests/unit/services/test_affiliate_anti_fraud.py` | `test_payout_approval_desk_tax_deduction` | 🟢 Green |
| **AC-1 / AC-4** | Bank Account Holder Name Normalization & Match Badge (100% Match vs Name Mismatch) | Unit | `tests/unit/services/test_affiliate_anti_fraud.py` | `test_bank_account_holder_name_normalization_and_match` | 🟢 Green |
| **AC-2** | Anti-Fraud Risk Engine & Self-Referral Ring Detection (< 1h account creation CTE query) | Unit | `tests/unit/services/test_affiliate_anti_fraud.py` | `test_anti_fraud_self_referral_ring_detection` | 🟢 Green |
| **AC-2** | Normal Organic Affiliate Low Risk Evaluation (< 30 risk score) | Unit | `tests/unit/services/test_affiliate_anti_fraud.py` | `test_low_risk_payout_evaluation` | 🟢 Green |
| **AC-4** | Supported `PayoutRejectionReason` Enum Validation | Unit | `tests/unit/services/test_affiliate_anti_fraud.py` | `test_payout_rejection_reason_enum_values` | 🟢 Green |
| **AC-1** | Payout Listing API with Status Filter & Pagination | Integration | `tests/integration/routes/test_admin_affiliates.py` | `test_get_affiliate_payouts_list` | 🟢 Green |
| **AC-2** | Payout Risk Evaluation Endpoint & Cache Merging | Integration | `tests/integration/routes/test_admin_affiliates.py` | `test_evaluate_payout_risk_endpoint` | 🟢 Green |
| **AC-3** | Idempotent Napas VietQR Payout Execution & Audit Trail (INV-25.2) | Integration | `tests/integration/routes/test_admin_affiliates.py` | `test_approve_affiliate_payout_with_audit` | 🟢 Green |
| **AC-4** | Payout Rejection with Ledger Rollback (`hold_balance` -> `balance`) | Integration | `tests/integration/routes/test_admin_affiliates.py` | `test_reject_affiliate_payout_with_rollback` | 🟢 Green |

---

## 📋 Implementation Checklist

### 1. Backend Service (`app/services/affiliate_anti_fraud_service.py`)
- [x] Implement `calculate_payout_net_amount(gross_amount_vnd: int) -> tuple[int, int]` (10% PIT if >= 2,000,000 VND).
- [x] Implement `normalize_account_holder_name(name: str) -> str` (accent stripping, uppercase, whitespace trim).
- [x] Implement `verify_bank_name_match(account_holder: str, beneficiary_name: str | None) -> tuple[bool, bool]`.
- [x] Define `PayoutRejectionReason(StrEnum)` with `NAME_MISMATCH`, `SUSPECTED_FRAUD_RING`, `INVALID_ACCOUNT`.
- [x] Implement `AffiliateAntiFraudService.evaluate_payout_risk(payout_id: uuid.UUID)` with recursive query / CTE for self-referral rings (< 1h).

### 2. Backend Admin API (`app/routes/admin_affiliates_routes.py` & schemas)
- [x] Implement `GET /api/v1/admin/affiliates/payouts` with pagination & status filtering.
- [x] Implement `POST /api/v1/admin/affiliates/payouts/{id}/evaluate`.
- [x] Implement `POST /api/v1/admin/affiliates/payouts/{id}/approve` with Redis lock `lock:payout:{id}`, `PartnerPayoutService.execute_payout_with_lock`, `VietQRPayoutClient`, state transition to `processing`, and `AuditEvent` logging.
- [x] Implement `POST /api/v1/admin/affiliates/payouts/{id}/reject` with `PayoutRejectionReason` and balance rollback from `hold_balance_micros` back to `balance_micros`.

### 3. Frontend Admin Desk (`nowing_web/app/admin/affiliates/payouts/page.tsx`)
- [x] Build Affiliate Payout Data Matrix with Partner name, Gross amount, 10% PIT tax deduction, Net amount, Name match badge, Risk pill.
- [x] Build `AffiliatePayoutDetailModal.tsx` with 1-click VietQR dispatch and rejection reason dialog.
- [x] Update `admin-affiliates-api.service.ts` to connect to real endpoints.

---

## 🧪 Verification Results

- **Unit Tests:** `uv run pytest tests/unit/services/test_affiliate_anti_fraud.py -q` ➔ **5 passed (100% green)**.
- **Integration Tests:** `uv run pytest tests/integration/routes/test_admin_affiliates.py -q` ➔ **4 passed (100% green)**.
- **Backend Lint:** `uv run ruff check` ➔ **All checks passed (0 errors)**.
- **Frontend Typecheck:** `pnpm tsc --noEmit` ➔ **Clean (0 errors)**.
- **Frontend Linter:** `pnpm exec biome check` ➔ **0 errors, 0 warnings**.
- **Live Browser Automation (Google Chrome Headed Mode):**
  - Table Overview: [`admin_affiliate_payouts_desk.png`](file:///Users/luisphan/.gemini/antigravity/brain/19a31587-eda5-446f-b789-96835623ae8e/admin_affiliate_payouts_desk.png)
  - Detail Modal: [`admin_affiliate_payout_modal.png`](file:///Users/luisphan/.gemini/antigravity/brain/19a31587-eda5-446f-b789-96835623ae8e/admin_affiliate_payout_modal.png)
