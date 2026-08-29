"""Unit tests for fail-closed DNC compliance during phone waterfall resolution (INV-24.3 / Story 21.14)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db import Lead
from app.lead_intelligence.dnc.service import DncCheckResult
from app.services.phone_waterfall_service import PhoneWaterfallService


@pytest.mark.unit
class TestWaterfallDncCompliance:
    """Validate in-stream fail-closed DNC check during phone waterfall resolution."""

    @pytest.mark.asyncio
    async def test_waterfall_phone_blocked_by_workspace_dnc_charges_zero_and_masks(
        self,
    ):
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
            patch(
                "app.services.phone_waterfall_service.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.phone_waterfall_service.wallet_credit.apply_debit",
                new_callable=AsyncMock,
            ) as mock_debit,
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
            patch(
                "app.services.phone_waterfall_service.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.phone_waterfall_service.wallet_credit.apply_debit",
                new_callable=AsyncMock,
            ) as mock_debit,
            patch(
                "app.services.scraper_platform_account_service.ScraperPlatformAccountRotator.get_credentials",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
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
            patch(
                "app.services.phone_waterfall_service.wallet_credit.check_balance",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.phone_waterfall_service.wallet_credit.apply_debit",
                new_callable=AsyncMock,
            ) as mock_debit,
            patch(
                "app.services.scraper_platform_account_service.ScraperPlatformAccountRotator.get_credentials",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
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
