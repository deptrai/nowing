"""Integration tests for Vietnam Phone & Contact Waterfall Engine & Auto-Refund (Story 21.3 / AD-25, AD-36, AD-42, AD-49)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    BillingEvent,
    Lead,
    PhoneWaterfallLog,
    User,
    VerifiedContact,
    Workspace,
)
from app.services.billing_service import BillingService
from app.services.phone_waterfall_service import (
    PHONE_RESOLUTION_COST_MICROS,
    PhoneWaterfallService,
)

pytestmark = pytest.mark.integration


async def test_phone_waterfall_integration_tier_1_batdongsan_persist_and_billing(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    # Setup initial balance
    db_user.credit_micros_balance = 5_000_000
    db_session.add(db_user)

    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        client_id="bds",
        source="batdongsan",
        company_name="Bất Động Sản Landmark",
        source_url="https://batdongsan.com.vn/ban-nha-quan-1-pr999999",
    )
    db_session.add(lead)
    await db_session.flush()

    service = PhoneWaterfallService(db_session)

    with (
        patch("app.services.phone_waterfall_service.get_redis", return_value=None),
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
            workspace_id=db_workspace.id,
            client_id="bds",
            lead_id=lead.id,
            user_id=db_user.id,
        )

        assert result.status == "success"
        assert result.phone == "0908123456"
        assert result.phone_masked == "0908***456"
        assert result.tier_reached == 1
        assert result.provider_used == "batdongsan"
        assert result.cost_micros == PHONE_RESOLUTION_COST_MICROS
        assert result.carrier == "MobiFone"

        # Verify DB records
        contacts_query = await db_session.execute(
            select(VerifiedContact).where(VerifiedContact.lead_id == lead.id)
        )
        contact = contacts_query.scalar_one_or_none()
        assert contact is not None
        assert contact.is_valid is True
        assert contact.phone != "0908123456"  # Must be encrypted ciphertext

        # Verify PhoneWaterfallLog
        logs_query = await db_session.execute(
            select(PhoneWaterfallLog).where(PhoneWaterfallLog.lead_id == lead.id)
        )
        log = logs_query.scalar_one_or_none()
        assert log is not None
        assert log.status == "success"
        assert log.phone_masked == "0908***456"
        assert log.tier_reached == 1
        assert log.provider_used == "batdongsan"
        assert log.cost_micros == PHONE_RESOLUTION_COST_MICROS

        # Verify BillingEvent
        events_query = await db_session.execute(
            select(BillingEvent).where(BillingEvent.user_id == db_user.id)
        )
        events = list(events_query.scalars().all())
        assert len(events) >= 1
        enrichment_event = next(
            e for e in events if e.event_type == "contact_enrichment"
        )
        assert enrichment_event.cost_micros == PHONE_RESOLUTION_COST_MICROS


async def test_phone_waterfall_integration_auto_refund_within_sla(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    db_user.credit_micros_balance = 5_000_000
    db_session.add(db_user)

    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        client_id="bds",
        source="batdongsan",
        company_name="Bất Động Sản Landmark",
        source_url="https://batdongsan.com.vn/ban-nha-quan-1-pr888888",
    )
    db_session.add(lead)
    await db_session.flush()

    service = PhoneWaterfallService(db_session)

    with (
        patch("app.services.phone_waterfall_service.get_redis", return_value=None),
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
        await service.resolve_lead_phone(
            workspace_id=db_workspace.id,
            client_id="bds",
            lead_id=lead.id,
            user_id=db_user.id,
        )

    # Balance was debited by 1,500,000 micros (3,500,000 remaining)
    assert db_user.credit_micros_balance == 3_500_000

    billing = BillingService(db_session)
    with patch("app.services.billing_service.get_redis", return_value=None):
        refund_res = await billing.auto_refund_lead(
            workspace_id=db_workspace.id,
            lead_id=lead.id,
            user_id=db_user.id,
            reason="dead_number",
        )

        assert refund_res["refunded"] is True
        assert refund_res["refund_micros"] == 1_500_000
        assert refund_res["refund_credits"] == 1.5

        # Balance restored to 5,000,000
        assert db_user.credit_micros_balance == 5_000_000

        # Verified contact marked invalid
        contact_res = await db_session.execute(
            select(VerifiedContact).where(VerifiedContact.lead_id == lead.id)
        )
        contact = contact_res.scalar_one()
        assert contact.is_valid is False
        assert contact.verification_status == "invalid"
        assert contact.invalid_reason == "dead_number"

        # Log marked refunded
        log_res = await db_session.execute(
            select(PhoneWaterfallLog).where(PhoneWaterfallLog.lead_id == lead.id)
        )
        log = log_res.scalar_one()
        assert log.status == "refunded"
        assert log.refund_reason == "dead_number"

        # Check refund billing event
        events_query = await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.user_id == db_user.id,
                BillingEvent.event_type == "lead_refund",
            )
        )
        refund_event = events_query.scalar_one()
        assert refund_event.cost_micros == -1_500_000

        # Re-attempting refund should fail
        with pytest.raises(HTTPException) as exc_info:
            await billing.auto_refund_lead(
                workspace_id=db_workspace.id,
                lead_id=lead.id,
                user_id=db_user.id,
            )
        assert exc_info.value.status_code == 400
        assert "already refunded" in exc_info.value.detail


async def test_phone_waterfall_integration_fail_charges_zero(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    initial_balance = 5_000_000
    db_user.credit_micros_balance = initial_balance
    db_session.add(db_user)

    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        client_id=None,
        source="manual",
        company_name="Anonymous No Phone Inc",
        source_url="",
    )
    db_session.add(lead)
    await db_session.flush()

    service = PhoneWaterfallService(db_session)

    with patch("app.services.phone_waterfall_service.get_redis", return_value=None):
        result = await service.resolve_lead_phone(
            workspace_id=db_workspace.id,
            client_id=None,
            lead_id=lead.id,
            user_id=db_user.id,
            raw_text="No contact info in text",
        )

        assert result.status == "failed"
        assert result.phone is None
        assert result.cost_micros == 0
        assert result.degraded is True
        assert db_user.credit_micros_balance == initial_balance

        # Log entry has 0 cost
        logs_query = await db_session.execute(
            select(PhoneWaterfallLog).where(PhoneWaterfallLog.lead_id == lead.id)
        )
        log = logs_query.scalar_one()
        assert log.status == "failed"
        assert log.cost_micros == 0
