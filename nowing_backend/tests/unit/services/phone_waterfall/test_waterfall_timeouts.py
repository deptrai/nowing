"""Unit tests for 60s hard timeout enforcement on phone waterfall resolution (Story 21.3 / Story 24.2 / AD-108)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.db import Lead
from app.services.phone_waterfall_service import PhoneWaterfallService


@pytest.mark.unit
class TestPhoneWaterfall60sTimeout:
    """Every external phone-resolution network / browser call must terminate at 60s."""

    @pytest.mark.asyncio
    async def test_tier_1_batdongsan_61s_hang_terminated(self, monkeypatch):
        from app.services import phone_waterfall_service as pws

        monkeypatch.setattr(pws, "_PHONE_RESOLVE_TIMEOUT_SECONDS", 0.1)
        monkeypatch.setattr(pws, "get_redis", lambda: None)

        class FakeRotator:
            def __init__(self, *args, **kwargs):
                pass

            async def get_credentials(self, wait=False, timeout=2.0):
                return (None, None)

            async def record_use(self, *args, **kwargs):
                pass

        monkeypatch.setattr(pws, "ScraperPlatformAccountRotator", FakeRotator)
        monkeypatch.setattr(
            pws, "ScraperPlatformAccountService", lambda session: AsyncMock()
        )

        async def _hang(*args, **kwargs):
            await asyncio.sleep(61)

        monkeypatch.setattr(
            pws,
            "fetch_detail_phone",
            AsyncMock(side_effect=_hang),
        )

        session = AsyncMock()
        service = PhoneWaterfallService(session)
        start = asyncio.get_event_loop().time()
        result = await service._resolve_tier_1_batdongsan(
            "https://batdongsan.com.vn/ban-nha-pr12345", None
        )
        elapsed = asyncio.get_event_loop().time() - start

        assert result.phone is None
        assert result.raw_response.get("reason") == "batdongsan_phone_not_found"
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_tier_2_chotot_61s_hang_terminated(self, monkeypatch):
        from app.services import phone_waterfall_service as pws

        monkeypatch.setattr(pws, "_PHONE_RESOLVE_TIMEOUT_SECONDS", 0.1)

        async def _hang(*args, **kwargs):
            await asyncio.sleep(61)

        monkeypatch.setattr(
            pws,
            "chotot_fetch_phone",
            AsyncMock(side_effect=_hang),
        )

        session = AsyncMock()
        service = PhoneWaterfallService(session)
        start = asyncio.get_event_loop().time()
        result = await service._resolve_tier_2_chotot(
            "https://www.nhatot.com/12345678.htm", None
        )
        elapsed = asyncio.get_event_loop().time() - start

        assert result.phone is None
        assert result.raw_response.get("reason") == "chotot_phone_not_found"
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_tier_3_masothue_61s_hang_terminated(self, monkeypatch):
        from app.services import (
            corporate_verification_service as cvs,
            phone_waterfall_service as pws,
        )

        monkeypatch.setattr(pws, "_PHONE_RESOLVE_TIMEOUT_SECONDS", 0.1)

        class FakeCorpService:
            async def verify_company(self, **kwargs):
                await asyncio.sleep(61)

        monkeypatch.setattr(
            cvs, "CorporateVerificationService", lambda session: FakeCorpService()
        )

        lead_id = uuid4()
        lead = Lead(
            id=lead_id,
            workspace_id=1,
            company_name="Công ty TNHH Test",
            tax_id="0123456789",
        )

        session = AsyncMock()
        service = PhoneWaterfallService(session)
        start = asyncio.get_event_loop().time()
        result = await service._resolve_tier_3_masothue_and_carrier(
            lead=lead, source_url=None, raw_text=None
        )
        elapsed = asyncio.get_event_loop().time() - start

        assert result.phone is None
        assert result.raw_response.get("reason") == "no_text_for_carrier_hlr"
        assert elapsed < 2.0
