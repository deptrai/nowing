import pytest

@pytest.mark.unit
class TestAffiliateAntiFraudService:
    
    def test_payout_approval_desk_data_mapping_and_tax_deduction(self):
        """
        AC-1: Payout Approval Desk data mapping and 10% PIT tax deduction calculation for amounts >= 2,000,000 VND.
        """
        pytest.fail("Not implemented: AC-1 data mapping and tax calculation")

    def test_anti_fraud_risk_engine_and_self_referral_ring_detection(self):
        """
        AC-2: Anti-Fraud Risk Engine & Self-Referral Ring Detection (CTE queries flagging shared IP subnet, browser fingerprints, and < 1h account creation).
        """
        pytest.fail("Not implemented: AC-2 risk engine logic")

    def test_high_risk_score_blocking_one_click_payout(self):
        """
        AC-3: High risk score (>= 70) blocking 1-click payout and requiring secondary supervisor review.
        """
        pytest.fail("Not implemented: AC-3 high risk blocking")

    def test_idempotent_napas_vietqr_payout_execution(self):
        """
        AC-4: Idempotent Napas 24/7 VietQR payout execution with distributed lock `lock:payout:{id}`.
        """
        pytest.fail("Not implemented: AC-4 idempotent execution and lock")

    def test_payout_rejection_with_reason_and_ledger_rollback(self):
        """
        AC-5: Payout rejection with mandatory reason and ledger rollback.
        """
        pytest.fail("Not implemented: AC-5 payout rejection rollback")
