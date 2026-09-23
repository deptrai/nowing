---
story_key: 23-3-automated-vietqr-affiliate-payout-reconciliation
status: done
epic: 23
---

# Story 23.3: Automated VietQR Affiliate Payout Reconciliation

**Status:** `done`  
**Epic:** Epic 23 — Lead Capture & Outreach Infrastructure

## Story

As an affiliate partner,  
I want instant 24/7 bank payouts via VietQR / Napas 24/7,  
so that I receive funds as soon as a payout request is approved.

## Acceptance Criteria

- **Given** an approved affiliate payout request with valid Napas 24/7 bank account details, **When** admin or automated policy triggers payout execution, **Then** the database locks the row, moves funds to `hold_balance`, calls the gateway API with an idempotent `tx_reference`, and transitions state to `processing`.
- **Given** a webhook callback confirming bank transfer success, **When** signature and checksum match the gateway secret key, **Then** `hold_balance` is deducted, `total_paid_micros` is credited, `PartnerPayout.status` becomes `completed`, and an automated email receipt is dispatched.
- **Given** a transient network failure or timeout, **When** the reconciliation background worker runs, **Then** it queries the gateway transaction status API (`GET /transactions/{tx_ref}`) before attempting any retry, preventing duplicate payouts.

## Dev Notes

- Double-entry ledger: `available_balance` vs `hold_balance`; only credit `total_paid_micros` on gateway success.
- Tax TNCN: 10% withheld for payouts > 2,000,000 VNĐ per TT 111/2013/TT-BTC.
- Row locking with `SELECT ... FOR UPDATE`.

## Verification

- Service: `app/services/partner_payout_service.py` / `payout_reconciliation_service.py`
- Webhook: `/api/v1/partners/payouts/webhook`
- Tests: reconciliation idempotency, TNCN calculation, webhook signature
