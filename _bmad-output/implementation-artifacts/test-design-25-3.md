---
story: "25.3"
mode: epic-level
status: draft
last_updated: "2026-08-21T23:45:00+07:00"
---

# Test Design — Story 25.3: Affiliate Partner Payout Desk & Anti-Fraud Engine

## 1. Mode & Scope

- **Mode:** Epic-Level Test Design
- **Target:** Story 25.3 under Epic 25 (Platform Administration & Multi-Tenant Operations)
- **Why epic-level:** The story has concrete acceptance criteria, touches real money movement, and requires a focused coverage/risk plan rather than a full system-level PRD/ADR review.
- **Loaded inputs:**
  - `_bmad-output/implementation-artifacts/stories/25-3-affiliate-partner-payout-desk-anti-fraud-engine.md`
  - `nowing_backend/app/routes/admin_affiliates_routes.py`
  - `nowing_backend/app/services/affiliate_anti_fraud_service.py`
  - `nowing_backend/app/services/partner_payout_service.py`
  - `nowing_backend/tests/unit/services/test_affiliate_anti_fraud.py`
  - `nowing_backend/tests/integration/routes/test_admin_affiliates.py`
  - `nowing_backend/tests/unit/services/test_partner_payout_service.py`
  - `nowing_web/app/admin/affiliates/payouts/page.tsx`
  - `nowing_web/components/admin/AffiliatePayoutDetailModal.tsx`
  - `nowing_web/lib/apis/admin-affiliates-api.service.ts`

## 2. Context Summary

### Tech Stack
- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL + Redis (for distributed locking)
- **Frontend:** Next.js 16 + React + shadcn/ui + TanStack Query
- **Test frameworks:** pytest (backend), Playwright (frontend e2e under `nowing_web/tests/`), ruff, biome, tsc

### Existing Test Coverage
- `tests/unit/services/test_affiliate_anti_fraud.py` — risk scoring, tax conversion, name match
- `tests/integration/routes/test_admin_affiliates.py` — list, evaluate, approve, reject flows (real Postgres)
- `tests/unit/services/test_partner_payout_service.py` — row-locking, PIT tax, idempotency
- `tests/integration/services/test_partner_payout_reconciliation.py` — webhook reconciliation
- **Gap:** No Playwright E2E covering the `/admin/affiliates/payouts` UI; no dedicated `tests/integration/services/test_admin_affiliate_payouts.py` service test.

### P0 Surface
This story moves real partner balance and initiates bank transfers. The P0 gates from the story are:
- `bmad-nowing-integration-test` (real Postgres)
- `bmad-nowing-mutation-gate` on `affiliate_anti_fraud_service.py` and `admin_affiliates_routes.py`
- `bmad-nowing-human-review-gate` (money movement)
- `bmad-nowing-web-e2e-gate` (recommended)

## 3. Risk & Testability Assessment

| ID | Risk | Category | P | I | Score | Mitigation / Test Evidence |
|---|---|---|---|---|---|---|
| R1 | High-risk or name-mismatch payout approved and dispatched | BUS/SEC | 2 | 3 | **6** | Route-level integration tests assert 409/403 rejections; UI disables approve button; add E2E |
| R2 | Duplicate payout due to race condition or lock bypass | BUS/DATA | 2 | 3 | **6** | 2-tier Redis + DB lock tests; concurrency integration test with two parallel approve requests |
| R3 | Wrong VND amount causes over/under payment | BUS | 2 | 3 | **6** | Unit tests for `micros_to_vnd`, PIT tax net calculation; integration tests assert displayed/net amount |
| R4 | Self-referral ring not detected / false positive | BUS | 2 | 3 | **6** | Unit tests for CTE logic (within 1h, with commission/purchase); integration tests with seeded referrals |
| R5 | Audit event missing/incomplete for approve/reject/evaluate | SEC/COMP | 2 | 3 | **6** | Integration tests assert `AuditEvent` rows with correct actor/subject/diff_payload |
| R6 | Webhook settlement not finalizing payout (`completed`) | BUS | 2 | 3 | **6** | Use existing `test_partner_payout_reconciliation.py`; extend to cover settlement audit hash |
| R7 | Frontend approve button enabled when it should be disabled | BUS | 2 | 2 | **4** | Playwright E2E for high-risk and name-mismatch states |
| R8 | `tx_reference` not deterministic on retry | TECH | 2 | 2 | **4** | Integration test repeats approve with same idempotency key; assert one balance transfer |
| R9 | Mutation gate baseline blocked by unrelated test failures | OPS | 2 | 2 | **4** | Run focused mutation gate with `--test-files` pointing to affiliate tests |

**Testability notes:**
- API is mockable: `VietQRPayoutClient`, Redis, and `PartnerPayoutService` can be patched.
- Integration tests already use real Postgres and admin fixtures.
- Frontend components are testable via Playwright; admin auth flow exists.
- Concurrency tests require careful Redis/DB isolation but are feasible.

## 4. Coverage Plan

### AC-1 — Payout Desk Data Matrix
- **P0** — API: list returns correct VND amounts, tax, name match badge, risk pill.
- **P1** — UI E2E: table renders columns, pagination loads more, status filter works.
- **P2** — API: status enum validation rejects unknown values.

### AC-2 — Anti-Fraud Risk Engine
- **P0** — Unit: self-referral ring detected only when referral created within 1h AND credited commission/purchase in window.
- **P0** — Unit: `risk_score >= 70` returns `risk_level = "high"` and disables quick payout.
- **P1** — Unit: name match normalized comparison (diacritics, case, Đ/D).
- **P2** — Unit: no false positive when no qualifying commission exists.
- **P2** — Phase 2 TODO: device/IP/BIN deferred until schema columns exist.

### AC-3 — Idempotent 1-Click VietQR Execution
- **P0** — Integration: approve acquires Redis lock `lock:payout:{id}`, calls `execute_payout_with_lock`, dispatches `VietQRPayoutClient.initiate_payout`, transitions to `processing`, writes `AuditEvent`.
- **P0** — Integration: approve rejects high-risk (`risk_score >= 70`) and `Name Mismatch`.
- **P0** — Integration: deterministic `tx_reference` generated from `payout.created_at` / `requested_at` epoch.
- **P1** — Concurrency: two parallel approve requests do not double-transfer balance.
- **P1** — Integration: name match verified from `initiate_payout` response and cached in `payout_details`.
- **P2** — Integration: webhook `handle_webhook_confirmation` finalizes to `completed`, updates `hold_balance_micros` and `total_paid_micros`, generates HMAC.

### AC-4 — Rejection & Reason Logging
- **P0** — Integration: reject with `PayoutRejectionReason` transitions to `rejected`, rolls back `hold_balance_micros` to `balance_micros` when held, writes `AuditEvent`.
- **P1** — Integration: reject preserves existing `payout_details` bank fields and only merges `rejection_reason`.

### NFR / Quality
- **P1** — Mutation gate: run `scripts/mutation-gate.py --services services/affiliate_anti_fraud_service,routes/admin_affiliates_routes --test-files tests/unit/services/test_affiliate_anti_fraud.py,tests/integration/routes/test_admin_affiliates.py`.
- **P1** — ruff + tsc + biome clean on changed files.
- **P2** — Performance: list endpoint `limit=100, offset` pagination smoke test with 150+ payout rows.
- **P2** — Security: non-superuser requests are fail-closed (existing `require_superuser` tests).

## 5. Execution Strategy

- **PR gate:** `ruff`, `pytest tests/unit/services/test_affiliate_anti_fraud.py tests/integration/routes/test_admin_affiliates.py`, `pnpm tsc --noEmit`, `biome check`.
- **Nightly/Weekly:** full integration suite, focused mutation gate, Playwright E2E admin-payouts flow.
- **Pre-release:** human-review-gate for money movement, mutation gate ≥ 80% or documented waivers.

## 6. Resource Estimates

| Priority | Effort |
|---|---|
| P0 tests & fixes | ~8–12h |
| P1 tests (concurrency, E2E, mutation gate focused) | ~12–20h |
| P2 (performance, extended reconciliation) | ~6–10h |
| Total | **~26–42h** |

## 7. Quality Gates

- P0 tests pass 100%.
- P1 pass rate ≥ 95%.
- Backend lint (ruff) and frontend lint/typecheck (biome/tsc) clean.
- Mutation gate on `admin_affiliates_routes` and `affiliate_anti_fraud_service` run with focused tests; survive mutants for risk/lock/gating logic.
- Human review for money-movement code before release.
- Coverage gaps documented as waivers if not completed.

## 8. Immediate Action Items

1. ✅ Add `tests/integration/services/test_admin_affiliate_payouts.py` covering approve/reject/idempotency/concurrency at service level.
2. ✅ Add Playwright E2E spec for `/admin/affiliates/payouts` (list, evaluate, approve disabled for high-risk, reject).
3. Run focused mutation gate with the command documented in R9.
4. Verify the manual `coalesce(..., -1)` change in `affiliate_anti_fraud_service.py` does not regress the "commission required" heuristic (currently tests pass).
