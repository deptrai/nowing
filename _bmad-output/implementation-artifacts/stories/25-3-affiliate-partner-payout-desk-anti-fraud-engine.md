story_key: 25-3-affiliate-partner-payout-desk-anti-fraud-engine
status: ready-for-dev
baseline_commit: be1122dd9ab3a0d92200ecfbc3c3545b736b04a0
epic: 25
story: 3
---

# Story 25.3: Affiliate Partner Payout Desk & Anti-Fraud Engine

Status: ready-for-dev

<!-- Note: Governed by INV-25.4, INV-25.2, INV-25.8, and Architecture Spine: epics.md (Epic 25) -->

## Story

As a Finance Administrator / Superadmin,  
I want a dedicated Affiliate Partner Payout Approval Desk with automated fraud risk scoring (IP/device clustering, self-referral rings) and 1-click VietQR Napas 24/7 bank transfer execution,  
So that genuine affiliate partners receive their commission in seconds while fraudulent referral rings and abusive payouts are automatically detected and blocked.

---

## Acceptance Criteria

### AC-1 — Affiliate Payout Approval Desk Data Matrix
**Given** an authenticated Superadmin on `/admin/affiliates/payouts`,  
**When** loaded,  
**Then** it displays all payout requests (`status = pending | processing | completed | rejected`) with:
- Partner Name, Email, Bank Code, Account Number, Account Name.
- Commission Amount (VND), 10% PIT Tax Deduction (for amounts ≥ 2,000,000 VND), Net Payout Amount.
- Bank Account Name Match badge (`100% Match` vs `Name Mismatch`).
- Fraud Risk Score Pill (`🟢 Low 0-29`, `🟡 Mid 30-69`, `🔴 High 70-100`).

### AC-2 — Anti-Fraud Risk Engine & Self-Referral Ring Detection
**Given** a pending affiliate payout request,  
**When** evaluated by `AffiliateAntiFraudService.evaluate_payout_risk(payout_id)`,  
**Then** the engine checks:
1. **Device / IP Clustered Referrals:** Recursive CTE query for referred users sharing identical browser fingerprints, IP subnets, or credit card BINs with the affiliate.
2. **Rapid Self-Referral Ring:** Referral accounts created within 1 hour of affiliate registration that immediately made qualifying purchases.
3. If risk score ≥ 70, status flags `High Risk`, disables 1-click quick payout, and requires mandatory secondary supervisor review.

### AC-3 — Idempotent 1-Click Napas 24/7 VietQR Execution
**Given** an approved low-risk payout request,  
**When** clicking `Approve & Dispatch VietQR`,  
**Then** backend:
1. Acquires distributed lock `lock:payout:{payout_id}`.
2. Calls VietQR / Napas payout gateway with unique `idempotency_key = payout_{id}_{created_at_ts}`.
3. On gateway `200 Success`, atomically updates `partner_payouts.status = 'completed'`, stores cryptographic transaction reference (`napas_trans_id`), and decrements partner pending balance.
4. Generates an immutable entry in `audit_events` and dispatches confirmation email/notification.

### AC-4 — Payout Rejection & Reason Logging
**Given** a fraudulent or mismatched payout request,  
**When** admin clicks `Reject Payout`,  
**Then** admin must select a rejection reason (`NAME_MISMATCH`, `SUSPECTED_FRAUD_RING`, `INVALID_ACCOUNT`), the request transitions to `rejected`, and commission balance reverts to partner escrow with an audit record.

---

## Tasks / Subtasks

- [ ] Task 1: Backend Affiliate Anti-Fraud Service
  - [ ] Implement `AffiliateAntiFraudService.evaluate_payout_risk()` in `app/services/affiliate_anti_fraud_service.py`.
  - [ ] Build recursive CTE for self-referral ring detection across `partner_referrals`, `affiliate_partners`, `credit_purchases`.
  - [ ] Add IP subnet and browser fingerprint clustering from available metadata.
  - [ ] Return structured risk object: `risk_score`, `risk_level`, `reasons[]`.

- [ ] Task 2: Backend Admin Affiliate Payout API
  - [ ] Create `app/routes/admin_affiliates_routes.py`:
    - `GET /api/v1/admin/affiliates/payouts` — list pending/processing/completed/rejected with pagination, filters.
    - `POST /api/v1/admin/affiliates/payouts/{id}/evaluate` — run anti-fraud and cache score.
    - `POST /api/v1/admin/affiliates/payouts/{id}/approve` — lock, execute VietQR, transition to `processing`.
    - `POST /api/v1/admin/affiliates/payouts/{id}/reject` — reject with reason, revert `hold_balance_micros` to `balance_micros`.
  - [ ] Wire router into `app/routes/__init__.py` with `require_superuser` guard (INV-25.8).
  - [ ] Add admin Pydantic schemas in `app/schemas/admin_affiliate_payouts.py`.

- [ ] Task 3: Backend Payout Execution & Idempotency
  - [ ] Reuse `PartnerPayoutService.execute_payout_with_lock()` in `app/services/partner_payout_service.py`.
  - [ ] Add `rejection_reason` handling in `payout_details` or `partner_payouts` schema (see Dev Notes).
  - [ ] Write `audit_events` with `actor_id`, `subject_id` for every approve/reject/evaluate (INV-25.2).

- [ ] Task 4: Backend Bank Name Match Verification
  - [ ] Extend `VietQRPayoutClient` (`app/services/vietqr_payout_client.py`) or call an existing bank-account lookup endpoint to verify beneficiary name matches `payout_details.account_name`.
  - [ ] Cache match result in `payout_details` and surface `100% Match` / `Name Mismatch` badge.

- [ ] Task 5: Unit & Integration Tests
  - [ ] Replace scaffolds in `tests/integration/routes/test_admin_affiliates.py` with real tests.
  - [ ] Add `tests/unit/services/test_affiliate_anti_fraud.py` (self-referral ring, rapid purchase, IP cluster).
  - [ ] Add `tests/integration/services/test_admin_affiliate_payouts.py` for approve/reject/idempotency/audit.

- [ ] Task 6: Frontend Payout Approval Desk
  - [ ] Create `nowing_web/app/admin/affiliates/payouts/page.tsx` high-density data table.
  - [ ] Create `nowing_web/components/admin/AffiliatePayoutDetailModal.tsx` with Napas preview, fraud score, approve/reject buttons.
  - [ ] Reuse existing admin layout at `nowing_web/app/admin/admin-shell.tsx`.

---

## Dev Notes

### Existing Code to Reuse (Do Not Reinvent)

- **Partner model & tables** are already in `app/db.py`:
  - `AffiliatePartner` (`affiliate_partners`) — `balance_micros`, `hold_balance_micros`, `total_paid_micros`, `payout_details` JSONB.
  - `PartnerPayout` (`partner_payouts`) — `amount_micros`, `tax_deducted_micros`, `net_amount_micros`, `status`, `tx_reference`, `napas_ref`, `hmac_audit_hash`, `payout_details`.
  - `PartnerReferral` (`partner_referrals`) — `partner_id`, `referred_user_id`, `attribution_source`, `landing_page`.
  - `PartnerCommission` (`partner_commissions`) — `partner_id`, `referral_id`, `credit_purchase_id`, `commission_micros`.
  - `AuditEvent` (`audit_events`) — `action`, `actor_id`, `subject_id`, `ticket_ref`, `ip_address`, `user_agent`, `diff_payload`.

- **Partner services already implemented (Story 21.18 / 23.3):**
  - `app/services/partner_service.py` — `request_payout`, `list_payouts`, `list_referrals`, `apply_partner`, `credit_partner_commission`.
  - `app/services/partner_payout_service.py` — `calculate_pit_tax`, `execute_payout_with_lock`, `handle_webhook_confirmation`, `reconcile_payout_status`.
  - `app/services/vietqr_payout_client.py` — `initiate_payout`, `query_transfer_status`, `verify_webhook_signature`.
  - `app/routes/partner_routes.py` — public `/partners/*` routes (apply, request payout, list payouts, webhook).

- **Admin route patterns (copy from):**
  - `app/routes/admin_credits_routes.py` — `require_superuser`, Pydantic request/response models, `AuditEvent` writes, idempotency header handling.
  - `app/routes/admin_users_routes.py` — admin list endpoints, superuser guards.
  - `app/services/manual_credit_service.py` — Redis + Postgres 2-tier lock pattern (`_workspace_redis_lock`, `SELECT FOR UPDATE`, `pg_advisory_xact_lock`).

- **Payout execution is already safe:** `PartnerPayoutService.execute_payout_with_lock` uses `SELECT ... FOR UPDATE` on `partner_payouts` and `affiliate_partners`, calculates PIT tax, generates `tx_reference`, and moves balance to `hold_balance_micros`. The admin approve route should call this, then `VietQRPayoutClient.initiate_payout`.

### Gaps & Implementation Hints

- `AffiliateAntiFraudService` is currently a stub (`app/services/affiliate_anti_fraud_service.py`):
  ```python
  class AffiliateAntiFraudService:
      @staticmethod
      def evaluate_payout_risk(payout_id: int) -> dict:
          return {"risk_score": 10, "status": "Low Risk"}
  ```
  Replace with real logic.

- No admin affiliate routes exist yet; only scaffold tests in `tests/integration/routes/test_admin_affiliates.py`.

- `VietQRPayoutClient` does **not** have an account-name verification method. If the VietQR provider does not expose name verification, implement a deterministic fallback with `payout_details.account_name` and mark the badge as `Name Mismatch` when the name cannot be verified. Do not block payouts solely on missing verification unless explicitly configured.

- `partner_payouts` table has no dedicated `rejection_reason` column. Store the rejection reason inside `payout_details` (e.g. `{"rejection_reason": "SUSPECTED_FRAUD_RING"}`) or add a migration. If adding a column, create an Alembic migration and keep the change backward-compatible.

- Risk score must be computed at load time or on demand. If computed on demand, cache the result in `payout_details` (`{"risk_score": 75, "risk_level": "high", "reasons": [...]}`) to avoid recomputing on every admin page load.

- Bank name matching and fraud risk are **advisory** unless `risk_score >= 70`, which must disable the `Approve & Dispatch` button and require supervisor review.

### Security & Compliance

- **INV-25.8:** All `/admin/*` routes must use `require_superuser` (`User.is_superuser == True`). PAT must be rejected fail-closed at `require_session_context`.
- **INV-25.2:** Every approve/reject/evaluate action must write an `AuditEvent` with `actor_id` (admin), `subject_id` (partner user), `ip_address`, `user_agent`, and a `diff_payload` capturing the status transition and risk score.
- **INV-25.4:** Fraud detection must run before any `Approve & Dispatch`; high-risk requests cannot be one-click approved.
- **INV-25.3:** Payouts involve balance movement. Use 2-tier locking (Redis `lock:payout:{payout_id}` + `SELECT FOR UPDATE` on `partner_payouts` and `affiliate_partners`) or reuse `PartnerPayoutService.execute_payout_with_lock`.

### API & Schema Conventions

- Follow FastAPI `APIRouter(prefix="/admin/affiliates", tags=["admin"])` pattern.
- Pydantic response models should live in `app/schemas/admin_affiliate_payouts.py` (new file) and reuse `PartnerPayoutItem` fields where possible.
- Include `limit`/`offset` query params on list endpoints (max 100).
- Admin list endpoint should filter by `status` (default `pending`).

### Frontend Conventions

- Admin pages use `nowing_web/app/admin/admin-shell.tsx` and high-density 36px row tables (see `/admin/users` and `/admin/workspaces` from Story 25.1).
- Use Radix UI / shadcn patterns for modals and dropdowns.
- Fraud score pills: `bg-green-100 text-green-800`, `bg-yellow-100 text-yellow-800`, `bg-red-100 text-red-800`.
- Buttons: `Approve & Dispatch VietQR` primary, `Reject Payout` destructive. Disable approve when `risk_score >= 70` or `Name Mismatch` is not explicitly acknowledged.

### Testing Conventions

- Unit tests: `tests/unit/services/test_affiliate_anti_fraud.py` — test CTE logic, risk score thresholds, name match edge cases.
- Integration route tests: `tests/integration/routes/test_admin_affiliates.py` — use `admin_token_headers` fixture, assert `require_superuser` fail-closed for non-superusers, assert audit events created.
- Integration service tests: `tests/integration/services/test_admin_affiliate_payouts.py` — test idempotency, balance reversion on reject, status transitions.
- Mock `VietQRPayoutClient` in tests; do not call real Napas gateway.

### P0 Surface Assessment

This story touches **partner balance / payout money movement**, which is a P0-adjacent surface. Per `nowing-quality-pipeline.md`:
- Integration tests on real Postgres are **P0-gated**.
- Human-review gate is **P0-gated** because it touches money movement and partner balances.
- Mutation gate is **P0-gated** for `app/services/affiliate_anti_fraud_service.py`, `app/services/partner_payout_service.py`, and `app/routes/admin_affiliates_routes.py` if token/credit logic is touched.

### Project Structure Notes

- New files:
  - `nowing_backend/app/routes/admin_affiliates_routes.py`
  - `nowing_backend/app/schemas/admin_affiliate_payouts.py`
  - `nowing_backend/app/services/affiliate_anti_fraud_service.py` (replace stub)
  - `nowing_backend/tests/integration/routes/test_admin_affiliates.py` (replace scaffold)
  - `nowing_backend/tests/unit/services/test_affiliate_anti_fraud.py`
  - `nowing_backend/tests/integration/services/test_admin_affiliate_payouts.py` (optional but recommended)
  - `nowing_web/app/admin/affiliates/payouts/page.tsx`
  - `nowing_web/components/admin/AffiliatePayoutDetailModal.tsx`
  - `nowing_web/lib/apis/admin-affiliate-payouts-api.service.ts` (optional)

- Files to update:
  - `nowing_backend/app/routes/__init__.py` — include new admin affiliates router.
  - `nowing_backend/app/db.py` — only if adding a `rejection_reason` column (otherwise store in `payout_details`).
  - `nowing_backend/app/services/vietqr_payout_client.py` — add name verification if API available.

### References

- Epic context: `_bmad-output/planning-artifacts/epics.md` lines 3205–3306 (Epic 25, INV-25.1–INV-25.8, Story 25.3 AC).
- Existing partner domain: `nowing_backend/app/services/partner_service.py`, `nowing_backend/app/services/partner_payout_service.py`, `nowing_backend/app/services/vietqr_payout_client.py`, `nowing_backend/app/routes/partner_routes.py`.
- Data model: `nowing_backend/app/db.py` (`AffiliatePartner`, `PartnerPayout`, `PartnerReferral`, `PartnerCommission`, `AuditEvent`).
- Admin route pattern: `nowing_backend/app/routes/admin_credits_routes.py`, `nowing_backend/app/routes/admin_users_routes.py`.
- Security guards: `nowing_backend/app/users.py` (`require_superuser`, `require_session_context`), `nowing_backend/app/auth/impersonation.py`.
- 2-tier lock pattern: `nowing_backend/app/services/manual_credit_service.py`.
- Frontend admin shell: `nowing_web/app/admin/admin-shell.tsx`.

## Dev Agent Record

### Agent Model Used

N/A — story context file.

### Debug Log References

- `app/services/affiliate_anti_fraud_service.py` is a stub; implement real CTE-based detection.
- `tests/integration/routes/test_admin_affiliates.py` is a scaffold (`assert True`); replace with real tests.

### Completion Notes List

- [ ] Anti-fraud service replaced and unit-tested.
- [ ] Admin affiliates routes created and registered.
- [ ] Frontend payout desk and detail modal created.
- [ ] Integration tests pass (real Postgres).
- [ ] Audit events written for approve/reject/evaluate.
- [ ] Story status updated to `done` after code-review and human-review gates.

### File List

- `_bmad-output/implementation-artifacts/stories/25-3-affiliate-partner-payout-desk-anti-fraud-engine.md` (this file)
- `nowing_backend/app/services/affiliate_anti_fraud_service.py`
- `nowing_backend/app/routes/admin_affiliates_routes.py`
- `nowing_backend/app/schemas/admin_affiliate_payouts.py`
- `nowing_backend/app/routes/__init__.py`
- `nowing_backend/app/services/vietqr_payout_client.py`
- `nowing_backend/tests/integration/routes/test_admin_affiliates.py`
- `nowing_backend/tests/unit/services/test_affiliate_anti_fraud.py`
- `nowing_web/app/admin/affiliates/payouts/page.tsx`
- `nowing_web/components/admin/AffiliatePayoutDetailModal.tsx`
