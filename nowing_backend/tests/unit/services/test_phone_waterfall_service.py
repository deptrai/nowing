"""Unit tests for Vietnam Phone & Contact Waterfall Engine & Legacy 11-to-10 Conversion (Story 21.3 / Story 24.2 / INV-24.3).

Tests:
1. 2018 Telecom 11-to-10 Digit Conversion (Viettel, Vinaphone, Mobifone, Vietnamobile, Gmobile)
2. Normalization, Masking, Hashing & Anti-ReDoS Bounds (<50ms)
3. Carrier Prefix & Name Mapping
4. PII Vault Encryption
5. 3-Tier Waterfall Execution (Tier 1: Batdongsan, Tier 2: Chợ Tốt / Zalo UID, Tier 3: Masothue Rep Phone & Carrier HLR)
6. Fail-Closed DNC Compliance (Workspace & Global DNC Lists, 0 credit debit on blocked)
7. Redis Caching & Auto-Refund SLA Tests
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db import (
    Lead,
    PhoneWaterfallLog,
    User,
    VerifiedContact,
)
from app.lead_intelligence.dnc.service import DncCheckResult
from app.services.billing_service import BillingService
from app.services.phone_waterfall_service import (
    PHONE_RESOLUTION_COST_MICROS,
    PhoneWaterfallService,
    get_carrier_name,
    hash_phone,
    mask_phone,
    normalize_vn_phone,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

# ─────────────────────────────────────────────────────────────
# 1. 2018 Telecom Legacy 11-to-10 Digit Conversion Tests (Story 24.2 / AC-2)
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestLegacy11DigitConversion:
    """Validate 2018 Vietnam telecom conversion of 11-digit mobile numbers to standard 10-digit format."""

    def test_viettel_11_to_10_conversion(self):
        """Viettel 0162->032, 0163->033, 0164->034, 0165->035, 0166->036, 0167->037, 0168->038, 0169->039."""
        assert normalize_vn_phone("01621234567") == "0321234567"
        assert normalize_vn_phone("01639876543") == "0339876543"
        assert normalize_vn_phone("01641112222") == "0341112222"
        assert normalize_vn_phone("01653334444") == "0353334444"
        assert normalize_vn_phone("01665556666") == "0365556666"
        assert normalize_vn_phone("01677778888") == "0377778888"
        assert normalize_vn_phone("01689990000") == "0389990000"
        assert normalize_vn_phone("01691234567") == "0391234567"

    def test_vinaphone_11_to_10_conversion(self):
        """Vinaphone 0123->083, 0124->084, 0125->085, 0127->081, 0129->082."""
        assert normalize_vn_phone("01234567890") == "0834567890"
        assert normalize_vn_phone("01245678901") == "0845678901"
        assert normalize_vn_phone("01256789012") == "0856789012"
        assert normalize_vn_phone("01278901234") == "0818901234"
        assert normalize_vn_phone("01290123456") == "0820123456"

    def test_mobifone_11_to_10_conversion(self):
        """MobiFone 0120->070, 0121->079, 0122->077, 0126->076, 0128->078."""
        assert normalize_vn_phone("01201234567") == "0701234567"
        assert normalize_vn_phone("01212345678") == "0792345678"
        assert normalize_vn_phone("01223456789") == "0773456789"
        assert normalize_vn_phone("01264567890") == "0764567890"
        assert normalize_vn_phone("01285678901") == "0785678901"

    def test_vietnamobile_and_gmobile_11_to_10_conversion(self):
        """Vietnamobile 0186->056, 0188->058 | Gmobile 0199->059."""
        assert normalize_vn_phone("01861234567") == "0561234567"
        assert normalize_vn_phone("01881234567") == "0581234567"
        assert normalize_vn_phone("01991234567") == "0591234567"

    def test_international_prefix_with_legacy_11_digits(self):
        """International format (+84 / 84) with 11-digit legacy prefixes."""
        assert normalize_vn_phone("+841689990000") == "0389990000"
        assert normalize_vn_phone("841234567890") == "0834567890"
        assert normalize_vn_phone("+84 120 123 4567") == "0701234567"

    def test_punctuated_legacy_11_digits(self):
        """Legacy numbers formatted with dots, dashes, and spaces."""
        assert normalize_vn_phone("0168.999.0000") == "0389990000"
        assert normalize_vn_phone("0123-456-7890") == "0834567890"
        assert normalize_vn_phone("0128 567 8901") == "0785678901"


# ─────────────────────────────────────────────────────────────
# 2. Standard Normalization, Masking, Hashing & ReDoS Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestStandardPhoneNormalization:
    """Validate standard 10-digit formats and security protections."""

    def test_normalize_vn_phone_standard_formats(self):
        assert normalize_vn_phone("0908123456") == "0908123456"
        assert normalize_vn_phone("+84908123456") == "0908123456"
        assert normalize_vn_phone("84908123456") == "0908123456"
        assert normalize_vn_phone("090.812.3456") == "0908123456"
        assert normalize_vn_phone("090 812 3456") == "0908123456"
        assert normalize_vn_phone("0987-654-321") == "0987654321"
        assert normalize_vn_phone("0389 123 456") == "0389123456"
        assert normalize_vn_phone("0778 888 999") == "0778888999"

    def test_normalize_vn_phone_vietnamese_words(self):
        assert (
            normalize_vn_phone("không chín không tám một hai ba bốn năm sáu")
            == "0908123456"
        )
        assert (
            normalize_vn_phone("khong chin tam bay sau nam bon ba hai mot") == "0987654321"
        )

    def test_normalize_vn_phone_invalid_prefixes_or_lengths(self):
        # Landline or invalid short numbers
        assert normalize_vn_phone("0243888888") is None
        assert normalize_vn_phone("19001560") is None
        assert normalize_vn_phone("123456") is None
        assert normalize_vn_phone("0999999999999") is None  # Too long (>11 digits)
        assert normalize_vn_phone("") is None
        assert normalize_vn_phone(None) is None

    def test_anti_redos_execution_time(self):
        evil_text = "0" * 5000 + " chín " * 500 + " !@#$%^&*() " * 100
        start = time.perf_counter()
        _ = normalize_vn_phone(evil_text, timeout_sec=0.05)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1  # Must execute or abort well within bound (<100ms max in test env)

    def test_mask_phone(self):
        assert mask_phone("0908123456") == "0908***456"
        assert mask_phone("0987654321") == "0987***321"
        assert mask_phone("") == ""
        assert mask_phone(None) == ""

    def test_hash_phone(self, monkeypatch):
        from app.config import config

        test_key = "test-secret-key-must-be-long-enough-12345678"
        monkeypatch.setattr(config, "SECRET_KEY", test_key)
        expected = hmac.new(
            test_key.encode("utf-8"),
            b"0908123456",
            hashlib.sha256,
        ).hexdigest()
        assert hash_phone("0908123456") == expected
        assert hash_phone(None) is None

    def test_carrier_name(self):
        assert get_carrier_name("0981234567") == "Viettel"
        assert get_carrier_name("0861234567") == "Viettel"
        assert get_carrier_name("0911234567") == "VNPT / Vinaphone"
        assert get_carrier_name("0881234567") == "VNPT / Vinaphone"
        assert get_carrier_name("0901234567") == "MobiFone"
        assert get_carrier_name("0791234567") == "MobiFone"
        assert get_carrier_name("0921234567") == "Vietnamobile"
        assert get_carrier_name("0991234567") == "Gmobile"
        assert get_carrier_name("0551234567") == "Wintel"
        assert get_carrier_name("0871234567") == "Itelecom"


# ─────────────────────────────────────────────────────────────
# 3. PII Vault Encryption Tests (INV-21.3)
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPiiEncryption:
    """Validate Fernet symmetric encryption of phone numbers at rest."""

    def test_phone_encryption(self):
        enc = VerifiedContactEncryption("test-secret-key-must-be-long-enough-12345678")
        raw = "0908123456"
        ciphertext = enc.encrypt(raw)
        assert ciphertext != raw
        assert len(ciphertext) > 20
        decrypted = enc.decrypt(ciphertext)
        assert decrypted == raw


# ─────────────────────────────────────────────────────────────
# 4. 3-Tier Waterfall Execution Tests (Story 21.3 / Story 24.2)
# Tier 1: Listing Phone (Batdongsan)
# Tier 2: Chợ Tốt / Zalo UID
# Tier 3: Masothue Legal Rep Phone & Passive Carrier HLR
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestWaterfallTierExecution:
    """Validate 3-tier waterfall phone resolution and fallbacks."""

    @pytest.mark.asyncio
    async def test_waterfall_tier_1_batdongsan_success(self):
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="bds",
            source="batdongsan",
            company_name="Bất Động Sản Test",
            source_url="https://batdongsan.com.vn/ban-nha-quan-1-pr123456",
        )
        session.get.return_value = lead

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=None),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock),
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock),
            patch(
                "app.services.scraper_platform_account_service.ScraperPlatformAccountRotator.get_credentials",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch(
                "app.services.phone_waterfall_service.fetch_detail_phone",
                new_callable=AsyncMock,
                return_value=("0908 123 456", "0908 123 456"),
            ),
        ):
            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id="bds",
                lead_id=lead_id,
                user_id=user_id,
            )

            assert result.status == "success"
            assert result.phone == "0908123456"
            assert result.phone_masked == "0908***456"
            assert result.tier_reached == 1
            assert result.provider_used == "batdongsan"
            assert result.cost_micros == PHONE_RESOLUTION_COST_MICROS
            assert result.carrier == "MobiFone"

    @pytest.mark.asyncio
    async def test_waterfall_tier_2_chotot_fallback(self):
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="chotot",
            source="chotot",
            company_name="Chợ Tốt Xe",
            source_url="https://xe.chotot.com/mua-ban-oto/10543210.htm",
        )
        session.get.return_value = lead

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=None),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock),
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock),
            patch(
                "app.services.phone_waterfall_service.chotot_fetch_phone",
                new_callable=AsyncMock,
                return_value="0987654321",
            ),
        ):
            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id="chotot",
                lead_id=lead_id,
                user_id=user_id,
            )

            assert result.status == "success"
            assert result.phone == "0987654321"
            assert result.phone_masked == "0987***321"
            assert result.tier_reached == 2
            assert result.provider_used == "chotot"
            assert result.cost_micros == PHONE_RESOLUTION_COST_MICROS
            assert result.carrier == "Viettel"

    @pytest.mark.asyncio
    async def test_waterfall_tier_3_masothue_rep_phone_fallback(self):
        """Tier 3: When listing phone and Zalo UID fail, resolve via Masothue Legal Rep phone."""
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        # Lead from company with no listing URL
        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="b2b",
            source="b2b_sourcing",
            company_name="CÔNG TY CỔ PHẦN FPT",
            source_url=None,
        )
        session.get.return_value = lead

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=None),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock),
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock),
            # Mock Corporate Verification returning rep_phone
            patch(
                "app.services.corporate_verification_service.CorporateVerificationService.verify_company",
                new_callable=AsyncMock,
            ) as mock_corp_verify,
        ):
            from app.services.corporate_verification_service import (
                CorporateMatchResult,
                CorporateProfile,
            )
            mock_corp_verify.return_value = CorporateMatchResult(
                tax_id="0101248141",
                is_verified=True,
                confidence=0.98,
                profile=CorporateProfile(
                    tax_id="0101248141",
                    company_name="CÔNG TY CỔ PHẦN FPT",
                    legal_representative="Nguyễn Văn Khoa",
                    charter_capital_vnd=13_000_000_000_000,
                    company_status="Đang hoạt động",
                    rep_phone="0981234567",
                ),
            )

            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id="b2b",
                lead_id=lead_id,
                user_id=user_id,
            )

            assert result.status == "success"
            assert result.phone == "0981234567"
            assert result.tier_reached == 3
            assert result.carrier == "Viettel"
            assert result.cost_micros == PHONE_RESOLUTION_COST_MICROS

    @pytest.mark.asyncio
    async def test_waterfall_all_tiers_failed_charges_zero(self):
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id=None,
            source="unknown",
            company_name="Anonymous Company",
            source_url="",
        )
        session.get.return_value = lead

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=None),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock),
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock) as mock_debit,
        ):
            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id=None,
                lead_id=lead_id,
                user_id=user_id,
                raw_text="Không có số điện thoại nào ở đây",
            )

            assert result.status == "failed"
            assert result.phone is None
            assert result.cost_micros == 0
            assert result.degraded is True
            assert result.degradation_reason == "phone_not_found"
            mock_debit.assert_not_called()


# ─────────────────────────────────────────────────────────────
# 5. Fail-Closed DNC Compliance Tests (INV-24.3 / Story 21.14)
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestWaterfallDncCompliance:
    """Validate in-stream fail-closed DNC check during phone waterfall resolution."""

    @pytest.mark.asyncio
    async def test_waterfall_phone_blocked_by_workspace_dnc_charges_zero_and_masks(self):
        """When resolved candidate phone is in Workspace DNC, resolution stops and charges 0 credits."""
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="bds",
            source="batdongsan",
            company_name="DNC Listed Landlord",
            source_url="https://batdongsan.com.vn/ban-nha-pr8888",
        )
        session.get.return_value = lead

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=None),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock),
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock) as mock_debit,
            patch(
                "app.services.phone_waterfall_service.fetch_detail_phone",
                new_callable=AsyncMock,
                return_value=("0908 123 456", "0908 123 456"),
            ),
            # Mock DNC service returning blocked
            patch(
                "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
                new_callable=AsyncMock,
            ) as mock_dnc_check,
        ):
            mock_dnc_check.return_value = DncCheckResult(
                is_blocked=True,
                reason="workspace_dnc",
                dnc_record_id=uuid4(),
            )

            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id="bds",
                lead_id=lead_id,
                user_id=user_id,
            )

            assert result.status == "blocked_by_dnc"
            assert result.phone is None  # Plaintext phone is NEVER exposed
            assert result.cost_micros == 0  # 0 credits charged
            mock_debit.assert_not_called()

    @pytest.mark.asyncio
    async def test_waterfall_phone_blocked_by_global_dnc_stops_resolution(self):
        """When resolved candidate phone is in Global National DNC, stops resolution immediately."""
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="bds",
            source="batdongsan",
            company_name="National DNC Contact",
            source_url="https://batdongsan.com.vn/ban-nha-pr7777",
        )
        session.get.return_value = lead

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=None),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock),
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock) as mock_debit,
            patch(
                "app.services.phone_waterfall_service.fetch_detail_phone",
                new_callable=AsyncMock,
                return_value=("0912 345 678", "0912 345 678"),
            ),
            patch(
                "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
                new_callable=AsyncMock,
            ) as mock_dnc_check,
        ):
            mock_dnc_check.return_value = DncCheckResult(
                is_blocked=True,
                reason="global_dnc",
                dnc_record_id=uuid4(),
            )

            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id="bds",
                lead_id=lead_id,
                user_id=user_id,
            )

            assert result.status == "blocked_by_dnc"
            assert result.cost_micros == 0
            mock_debit.assert_not_called()

    @pytest.mark.asyncio
    async def test_waterfall_dnc_service_exception_fails_closed(self):
        """When DNC service raises an unexpected timeout or error, waterfall FAILS CLOSED."""
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id="bds",
            source="batdongsan",
            company_name="Fail Closed Contact",
            source_url="https://batdongsan.com.vn/ban-nha-pr6666",
        )
        session.get.return_value = lead

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=None),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock),
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock) as mock_debit,
            patch(
                "app.services.phone_waterfall_service.fetch_detail_phone",
                new_callable=AsyncMock,
                return_value=("0987 654 321", "0987 654 321"),
            ),
            patch(
                "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
                side_effect=TimeoutError("DNC Registry connection timed out"),
            ),
        ):
            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id="bds",
                lead_id=lead_id,
                user_id=user_id,
            )

            # Fail-closed: Must NOT reveal number or charge credits on DNC failure
            assert result.status in ("blocked_by_dnc", "failed")
            assert result.phone is None
            assert result.cost_micros == 0
            mock_debit.assert_not_called()


# ─────────────────────────────────────────────────────────────
# 6. Auto-Refund SLA & Redis Caching Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestAutoRefundAndCaching:
    """Validate 24h refund SLA and Redis cache bypass of charges."""

    @pytest.mark.asyncio
    async def test_waterfall_redis_cache_hit_skips_billing(self):
        session = AsyncMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(
            id=lead_id,
            workspace_id=workspace_id,
            client_id=None,
            source="batdongsan",
            company_name="Bất Động Sản",
            source_url="https://batdongsan.com.vn/ban-nha-pr999",
        )
        session.get.return_value = lead

        fake_redis = AsyncMock()
        cached_envelope = json.dumps(
            {
                "phone": "0908123456",
                "phone_masked": "0908***456",
                "phone_hash": "dummyhash",
                "tier_reached": 1,
                "provider_used": "batdongsan",
                "confidence": 0.98,
                "carrier": "MobiFone",
            }
        )
        fake_redis.get.return_value = cached_envelope

        service = PhoneWaterfallService(session)

        with (
            patch("app.services.phone_waterfall_service.get_redis", return_value=fake_redis),
            patch("app.services.phone_waterfall_service.wallet_credit.check_balance", new_callable=AsyncMock) as mock_check,
            patch("app.services.phone_waterfall_service.wallet_credit.apply_debit", new_callable=AsyncMock) as mock_debit,
        ):
            result = await service.resolve_lead_phone(
                workspace_id=workspace_id,
                client_id=None,
                lead_id=lead_id,
                user_id=user_id,
            )

            assert result.status == "success"
            assert result.is_cached is True
            assert result.cost_micros == 0  # No charge on cache hit
            assert result.phone == "0908123456"
            mock_check.assert_not_called()
            mock_debit.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_refund_lead_success_within_24h(self):
        session = AsyncMock()
        session.add = MagicMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(id=lead_id, workspace_id=workspace_id, client_id="bds")
        session.get.side_effect = lambda model, pk: (
            lead
            if model == Lead
            else (
                User(id=user_id, credit_micros_balance=5000000) if model == User else None
            )
        )

        log_entry = PhoneWaterfallLog(
            id=uuid4(),
            workspace_id=workspace_id,
            lead_id=lead_id,
            tier_reached=1,
            provider_used="batdongsan",
            status="success",
            cost_micros=1500000,
            phone_hash="abc123hash",
            created_at=datetime.now(UTC) - timedelta(hours=2),  # 2 hours ago (<24h SLA)
        )

        execute_mock = AsyncMock()
        mock_log_res = MagicMock()
        mock_log_res.scalar_one_or_none.return_value = log_entry

        mock_payer_res = MagicMock()
        mock_payer_res.scalar_one_or_none.return_value = user_id

        mock_contacts_res = MagicMock()
        mock_contact = VerifiedContact(
            id=uuid4(),
            workspace_id=workspace_id,
            lead_id=lead_id,
            is_valid=True,
            verification_status="verified",
        )
        mock_contacts_res.scalars.return_value.all.return_value = [mock_contact]

        execute_mock.side_effect = [mock_log_res, mock_payer_res, mock_contacts_res]
        session.execute = execute_mock

        billing = BillingService(session)

        with patch("app.services.billing_service.get_redis", return_value=AsyncMock()):
            refund_res = await billing.auto_refund_lead(
                workspace_id=workspace_id,
                lead_id=lead_id,
                user_id=user_id,
                reason="reported_invalid_phone",
            )

            assert refund_res["refunded"] is True
            assert refund_res["refund_micros"] == 1500000
            assert refund_res["refund_credits"] == 1.5
            assert log_entry.status == "refunded"
            assert mock_contact.is_valid is False
            assert mock_contact.verification_status == "invalid"

    @pytest.mark.asyncio
    async def test_auto_refund_lead_expired_sla_raises_400(self):
        session = AsyncMock()
        lead_id = uuid4()
        user_id = uuid4()
        workspace_id = 1

        lead = Lead(id=lead_id, workspace_id=workspace_id)
        session.get.return_value = lead

        log_entry = PhoneWaterfallLog(
            id=uuid4(),
            workspace_id=workspace_id,
            lead_id=lead_id,
            status="success",
            cost_micros=1500000,
            created_at=datetime.now(UTC) - timedelta(hours=26),  # 26 hours ago (>24h SLA)
        )

        mock_log_res = MagicMock()
        mock_log_res.scalar_one_or_none.return_value = log_entry
        session.execute.return_value = mock_log_res

        billing = BillingService(session)

        with pytest.raises(HTTPException) as exc_info:
            await billing.auto_refund_lead(
                workspace_id=workspace_id,
                lead_id=lead_id,
                user_id=user_id,
            )

        assert exc_info.value.status_code == 400
        assert "Auto-refund SLA expired" in exc_info.value.detail
