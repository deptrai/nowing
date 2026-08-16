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
- Commission Amount (VND), 10% PIT Tax Deduction (for amounts $\ge$ 2,000,000 VND), Net Payout Amount.
- Bank Account Name Match badge (`100% Match` vs `🔴 Name Mismatch`).
- Fraud Risk Score Pill (`🟢 Low 0-29`, `🟡 Mid 30-69`, `🔴 High 70-100`).

### AC-2 — Anti-Fraud Risk Engine & Self-Referral Ring Detection
**Given** a pending affiliate payout request,  
**When** evaluated by `AffiliateAntiFraudService.evaluate_risk(payout_id)`,  
**Then** the engine checks:
1. **Device / IP Clustered Referrals:** Recursive CTE query for referred users sharing identical browser fingerprints, IP subnets, or credit card BINs with the affiliate.
2. **Rapid Self-Referral Ring:** Referral accounts created within 1 hour of affiliate registration that immediately made qualifying purchases.
3. If risk score $\ge 70$, status flags `🔴 High Risk`, disables 1-click quick payout, and requires mandatory secondary supervisor review.

### AC-3 — Idempotent 1-Click Napas 24/7 VietQR Execution
**Given** an approved low-risk payout request,  
**When** clicking `⚡ Approve & Dispatch VietQR`,  
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

- [ ] Task 1: Backend Affiliate Anti-Fraud Service & Payout API
  - [ ] Implement `AffiliateAntiFraudService.evaluate_payout_risk()` with recursive CTE fraud detection in `app/services/affiliate_anti_fraud_service.py`.
  - [ ] Create API routes in `app/routes/admin_affiliates_routes.py`: `GET /api/v1/admin/affiliates/payouts`, `POST /api/v1/admin/affiliates/payouts/{id}/approve`, `POST /api/v1/admin/affiliates/payouts/{id}/reject`.
- [ ] Task 2: Unit & Integration Tests
  - [ ] Add `tests/unit/services/test_affiliate_anti_fraud.py` (fraud ring scenarios, name match edge cases).
  - [ ] Add `tests/integration/routes/test_admin_affiliate_payouts.py`.
- [ ] Task 3: Frontend Payout Approval Desk UI
  - [ ] Create `nowing_web/app/admin/affiliates/payouts/page.tsx` with high-density table and fraud score pills.
  - [ ] Create `components/admin/PayoutDetailModal.tsx` with Napas verification preview.
