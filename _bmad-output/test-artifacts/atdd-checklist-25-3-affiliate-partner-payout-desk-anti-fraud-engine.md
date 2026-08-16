# ATDD Checklist: Story 25.3 - Affiliate Partner Payout Desk & Anti-Fraud Engine

## Unit Tests (`nowing_backend/tests/unit/services/test_affiliate_anti_fraud.py`)
- [x] `test_payout_approval_desk_data_mapping_and_tax_deduction` (AC-1)
- [x] `test_anti_fraud_risk_engine_and_self_referral_ring_detection` (AC-2)
- [x] `test_high_risk_score_blocking_one_click_payout` (AC-3)
- [x] `test_idempotent_napas_vietqr_payout_execution` (AC-4)
- [x] `test_payout_rejection_with_reason_and_ledger_rollback` (AC-5)

## Integration Tests (`nowing_backend/tests/integration/routes/test_admin_affiliates.py`)
- [x] `test_get_affiliate_payouts_list` (`GET /api/v1/admin/affiliates/payouts`)
- [x] `test_approve_affiliate_payout` (`POST /api/v1/admin/affiliates/payouts/{id}/approve`)
- [x] `test_reject_affiliate_payout` (`POST /api/v1/admin/affiliates/payouts/{id}/reject`)

## Verification Steps
- [x] Run `pytest tests/unit/services/test_affiliate_anti_fraud.py -m unit`
- [x] Run `pytest tests/integration/routes/test_admin_affiliates.py -m integration`
