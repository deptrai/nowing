"""Unit tests for 3-tier waterfall execution and fallbacks (Story 21.3 / Story 24.2 / INV-24.3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db import Lead
from app.services.phone_waterfall_service import (
    PHONE_RESOLUTION_COST_MICROS,
    PhoneWaterfallService,
)


@pytest.mark.unit
class TestWaterfallTierExecution:
    """Validate 3-tier waterfall phone resolution and fallbacks.

    Tier 1: Listing Phone (Batdongsan)
    Tier 2: Chợ Tốt / Zalo UID
    Tier 3: Masothue Legal Rep Phone & Passive Carrier HLR
    """

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
            patch(
                "app.services.phone_waterfall_service.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.phone_waterfall_service.wallet_credit.apply_debit",
                new_callable=AsyncMock,
            ),
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
            patch(
                "app.services.phone_waterfall_service.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.phone_waterfall_service.wallet_credit.apply_debit",
                new_callable=AsyncMock,
            ),
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
            patch(
                "app.services.phone_waterfall_service.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.phone_waterfall_service.wallet_credit.apply_debit",
                new_callable=AsyncMock,
            ),
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
            patch(
                "app.services.phone_waterfall_service.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.phone_waterfall_service.wallet_credit.apply_debit",
                new_callable=AsyncMock,
            ) as mock_debit,
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
