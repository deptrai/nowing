"""Unit tests for Affiliate Anti-Fraud Service & Payout Approval Desk (Story 25.3 / ATDD Red Phase)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.admin_affiliate_payouts import PayoutRejectionReason
from app.services.affiliate_anti_fraud_service import (
    AffiliateAntiFraudService,
    calculate_payout_net_amount,
    micros_to_vnd,
    normalize_account_holder_name,
    verify_bank_name_match,
)
from app.services.partner_service import micros_to_vnd as ps_micros_to_vnd


@pytest.mark.unit
class TestAffiliateAntiFraudService:

    def test_payout_approval_desk_tax_deduction(self):
        """AC-1: Gross amount >= 2,000,000 VND incurs 10% PIT tax deduction."""
        # Case 1: Gross 5,000,000 VND -> 10% PIT = 500,000 VND -> Net = 4,500,000 VND
        gross_1 = 5_000_000
        net_1, tax_1 = calculate_payout_net_amount(gross_1)
        assert tax_1 == 500_000
        assert net_1 == 4_500_000

        # Case 2: Gross 1,500,000 VND (< 2M threshold) -> 0% PIT -> Net = 1,500,000 VND
        gross_2 = 1_500_000
        net_2, tax_2 = calculate_payout_net_amount(gross_2)
        assert tax_2 == 0
        assert net_2 == 1_500_000

        # Case 3: Exactly 2,000,000 VND -> 10% PIT = 200,000 VND -> Net = 1,800,000 VND
        gross_3 = 2_000_000
        net_3, tax_3 = calculate_payout_net_amount(gross_3)
        assert tax_3 == 200_000
        assert net_3 == 1_800_000

    def test_micros_to_vnd_matches_partner_service(self):
        """Ensure the anti-fraud service uses the same USD -> VND conversion as the rest of the domain."""
        amount_micros = 78_740_157  # ~2,000,000 VND
        assert micros_to_vnd(amount_micros) == ps_micros_to_vnd(amount_micros)
        assert micros_to_vnd(amount_micros) == 2_000_000

    def test_high_amount_threshold_uses_correct_conversion(self):
        """Risk engine must evaluate the high-amount threshold in real VND, not micros/1000."""
        # 78,740,157 micros is ~2,000,000 VND, far below the 50,000,000 VND threshold.
        assert micros_to_vnd(78_740_157) < 50_000_000

    def test_bank_account_holder_name_normalization_and_match(self):
        """AC-1 / AC-4: Bank Account Holder Name Match badge (100% Match vs Name Mismatch)."""
        # Case 1: Matching with accent / case difference
        assert normalize_account_holder_name("NGUYEN VAN MINH") == "NGUYEN VAN MINH"
        assert normalize_account_holder_name("Nguyễn Văn Minh") == "NGUYEN VAN MINH"
        assert normalize_account_holder_name("  nguyen  van minh  ") == "NGUYEN VAN MINH"

        match_1, is_verified_1 = verify_bank_name_match("Nguyễn Văn Minh", "NGUYEN VAN MINH")
        assert match_1 is True
        assert is_verified_1 is True

        # Case 2: Mismatch
        match_2, is_verified_2 = verify_bank_name_match("Trần Thị Hoa", "NGUYEN VAN MINH")
        assert match_2 is False
        assert is_verified_2 is True

        # Case 3: Missing provider beneficiary name
        match_3, is_verified_3 = verify_bank_name_match("Nguyễn Văn Minh", None)
        assert match_3 is False
        assert is_verified_3 is False

    @pytest.mark.asyncio
    async def test_anti_fraud_self_referral_ring_detection(self):
        """AC-2: Detect referral accounts created within 1h of affiliate that immediately made purchases."""
        mock_session = AsyncMock()
        payout_id = uuid.uuid4()
        partner_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Setup mock payout record
        mock_payout = MagicMock()
        mock_payout.id = payout_id
        mock_payout.partner_id = partner_id
        mock_payout.amount_micros = 78_740_157
        mock_payout.payout_details = {
            "bank_bin": "970422",
            "account_number": "123456789",
            "account_holder": "NGUYEN VAN MINH",
        }

        mock_partner = MagicMock()
        mock_partner.id = partner_id
        mock_partner.user_id = user_id
        mock_partner.created_at = datetime.now(UTC) - timedelta(hours=2)

        # Mock rapid referral within 30 minutes of affiliate creation
        mock_referral_user = MagicMock()
        mock_referral_user.id = uuid.uuid4()
        mock_referral_user.created_at = mock_partner.created_at + timedelta(minutes=25)

        service = AffiliateAntiFraudService(session=mock_session)

        # Mock repository/query helper
        service._get_payout = AsyncMock(return_value=mock_payout)
        service._get_partner = AsyncMock(return_value=mock_partner)
        service._detect_rapid_self_referral_ring = AsyncMock(
            return_value=[
                {
                    "referred_user_id": str(mock_referral_user.id),
                    "created_within_minutes": 25,
                    "commission_micros": 78_740_157,
                }
            ]
        )

        result = await service.evaluate_payout_risk(payout_id)
        assert "risk_score" in result
        assert result["risk_score"] >= 70
        assert result["risk_level"] == "high"
        assert any("self-referral" in r.lower() or "1 giờ" in r.lower() for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_low_risk_payout_evaluation(self):
        """AC-2: Normal organic affiliate referral yields low risk score (< 30)."""
        mock_session = AsyncMock()
        payout_id = uuid.uuid4()

        mock_payout = MagicMock()
        mock_payout.id = payout_id
        mock_payout.partner_id = uuid.uuid4()
        mock_payout.amount_micros = 1_000_000
        mock_payout.payout_details = {
            "bank_bin": "970422",
            "account_number": "987654321",
            "account_holder": "TRAN THI HOA",
        }

        service = AffiliateAntiFraudService(session=mock_session)
        service._get_payout = AsyncMock(return_value=mock_payout)
        service._get_partner = AsyncMock(return_value=MagicMock())
        service._detect_rapid_self_referral_ring = AsyncMock(return_value=[])

        result = await service.evaluate_payout_risk(payout_id)
        assert result["risk_score"] < 30
        assert result["risk_level"] == "low"

    def test_payout_rejection_reason_enum_values(self):
        """AC-4: Validate supported PayoutRejectionReason enum entries."""
        assert PayoutRejectionReason.NAME_MISMATCH.value == "name_mismatch"
        assert PayoutRejectionReason.SUSPECTED_FRAUD_RING.value == "suspected_fraud_ring"
        assert PayoutRejectionReason.INVALID_ACCOUNT.value == "invalid_account"
