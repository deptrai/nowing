"""Integration tests for B2B Corporate Verification & Phone Waterfall Pipeline (Story 24.2 / INV-24.3 / INV-21.3).

Tests end-to-end integration:
1. Lead entity enrichment with Masothue Corporate Tax ID (MST), Legal Rep, and Charter Capital
2. Tier 3 Masothue Rep Phone resolution and 2018 11-to-10 digit conversion in database
3. Vault symmetric encryption in VerifiedContact & PII isolation
4. In-stream DNC compliance check blocking unauthorized outreach
5. Circuit Breaker resilience and Redis 7-day caching behavior in database session
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
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
from app.lead_intelligence.dnc.service import DncCheckResult
from app.services.corporate_verification_service import (
    CorporateMatchResult,
    CorporateVerificationService,
)
from app.services.phone_waterfall_service import (
    PHONE_RESOLUTION_COST_MICROS,
    PhoneWaterfallService,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
from tests.fixtures.masothue_mock import (
    MockMasothueClient,
)

pytestmark = pytest.mark.integration


# ─────────────────────────────────────────────────────────────
# 1. High-Confidence B2B Corporate Verification & Waterfall Integration
# ─────────────────────────────────────────────────────────────

async def test_corporate_verification_pipeline_high_confidence_and_tier_3_phone(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Lead with high-confidence corporate match is auto-linked with MST, capital, and Tier 3 rep phone."""
    db_user.credit_micros_balance = 10_000_000
    db_session.add(db_user)

    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        source="b2b_sourcing",
        company_name="CÔNG TY CỔ PHẦN FPT",
        location="Cầu Giấy, Hà Nội",
    )
    db_session.add(lead)
    await db_session.flush()

    client_mock = MockMasothueClient()
    corp_service = CorporateVerificationService(db_session, masothue_client=client_mock, redis_client=None)

    # 1. Run Corporate Verification (bypass Redis so stale name cache doesn't mask the fresh location)
    with patch(
        "app.services.corporate_verification_service.get_redis",
        return_value=None,
    ):
        corp_res: CorporateMatchResult = await corp_service.verify_lead_corporate_info(
            workspace_id=db_workspace.id,
            lead_id=lead.id,
        )

    assert corp_res.is_verified is True
    assert corp_res.confidence >= 0.85
    assert corp_res.requires_manual_confirmation is False
    assert corp_res.tax_id == "0101248141"
    assert corp_res.legal_representative == "Nguyễn Văn Khoa"
    assert corp_res.charter_capital_vnd == 13_000_000_000_000

    # 2. Run Phone Waterfall Service (Tier 3 Masothue Rep Phone)
    fake_redis = AsyncMock()
    fake_redis.get.return_value = None
    fake_redis.mget.return_value = (None, None)
    phone_service = PhoneWaterfallService(
        db_session, masothue_client=client_mock, redis_client=fake_redis
    )

    with (
        patch("app.services.phone_waterfall_service.get_redis", return_value=None),
        patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
            new_callable=AsyncMock,
            return_value=DncCheckResult(is_blocked=False),
        ),
    ):
        phone_res = await phone_service.resolve_lead_phone(
            workspace_id=db_workspace.id,
            client_id=None,
            lead_id=lead.id,
            user_id=db_user.id,
        )

        assert phone_res.status == "success"
        assert phone_res.phone == "0981234567"
        assert phone_res.phone_masked == "0981***567"
        assert phone_res.tier_reached == 3
        assert phone_res.carrier == "Viettel"
        assert phone_res.cost_micros == PHONE_RESOLUTION_COST_MICROS

    # 3. Verify Database Persistence & Vault Encryption
    contact_query = await db_session.execute(
        select(VerifiedContact).where(VerifiedContact.lead_id == lead.id)
    )
    contact = contact_query.scalar_one_or_none()
    assert contact is not None
    assert contact.is_valid is True
    assert contact.phone != "0981234567"  # Must be encrypted ciphertext

    # Decrypt to ensure integrity
    enc = VerifiedContactEncryption()
    assert enc.decrypt(contact.phone) == "0981234567"

    # Verify PhoneWaterfallLog
    log_query = await db_session.execute(
        select(PhoneWaterfallLog).where(PhoneWaterfallLog.lead_id == lead.id)
    )
    log_entry = log_query.scalar_one_or_none()
    assert log_entry is not None
    assert log_entry.status == "success"
    assert log_entry.phone_masked == "0981***567"
    assert log_entry.cost_micros == PHONE_RESOLUTION_COST_MICROS

    # Verify BillingEvent
    billing_query = await db_session.execute(
        select(BillingEvent).where(BillingEvent.event_id == log_entry.id)
    )
    billing_event = billing_query.scalar_one_or_none()
    assert billing_event is not None
    assert billing_event.cost_micros == PHONE_RESOLUTION_COST_MICROS


# ─────────────────────────────────────────────────────────────
# 2. Legacy 11-Digit Conversion in Full Pipeline
# ─────────────────────────────────────────────────────────────

async def test_corporate_verification_pipeline_legacy_11_digit_rep_phone_conversion(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Legacy 11-digit rep phone in registry (01234567890) is converted to 10-digit (0834567890)."""
    db_user.credit_micros_balance = 5_000_000
    db_session.add(db_user)

    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        source="b2b_sourcing",
        company_name="CÔNG TY TNHH CÔNG NGHỆ ALPHA VIỆT NAM",
        location="Thanh Xuân, Hà Nội",
    )
    db_session.add(lead)
    await db_session.flush()

    client_mock = MockMasothueClient()
    corp_service = CorporateVerificationService(db_session, masothue_client=client_mock, redis_client=None)

    # 1. Run Corporate Verification
    corp_res = await corp_service.verify_lead_corporate_info(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
    )
    assert corp_res.is_verified is True
    assert corp_res.tax_id == "0108999888"

    # 2. Run Phone Waterfall Service
    fake_redis = AsyncMock()
    fake_redis.get.return_value = None
    fake_redis.mget.return_value = (None, None)
    phone_service = PhoneWaterfallService(
        db_session, masothue_client=client_mock, redis_client=fake_redis
    )

    with (
        patch("app.services.phone_waterfall_service.get_redis", return_value=None),
        patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
            new_callable=AsyncMock,
            return_value=DncCheckResult(is_blocked=False),
        ),
    ):
        phone_res = await phone_service.resolve_lead_phone(
            workspace_id=db_workspace.id,
            client_id=None,
            lead_id=lead.id,
            user_id=db_user.id,
        )

        # Converted 01234567890 -> 0834567890
        assert phone_res.status == "success"
        assert phone_res.phone == "0834567890"
        assert phone_res.phone_masked == "0834***890"
        assert phone_res.carrier == "VNPT / Vinaphone"


# ─────────────────────────────────────────────────────────────
# 3. Low Confidence Match Pipeline (< 0.85 Threshold)
# ─────────────────────────────────────────────────────────────

async def test_corporate_verification_pipeline_low_confidence_flags_manual(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Low confidence corporate match (<0.85) is flagged for manual confirmation and not auto-linked."""
    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        source="b2b_sourcing",
        company_name="CÔNG TY TNHH Á CHÂU",
        location="Quận 1, TP Hồ Chí Minh",  # Location differs from Bình Dương registry
    )
    db_session.add(lead)
    await db_session.flush()

    client_mock = MockMasothueClient()
    corp_service = CorporateVerificationService(db_session, masothue_client=client_mock, redis_client=None)

    corp_res = await corp_service.verify_lead_corporate_info(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
    )

    assert corp_res.confidence < 0.85
    assert corp_res.requires_manual_confirmation is True
    assert corp_res.is_verified is False


# ─────────────────────────────────────────────────────────────
# 4. In-Stream DNC Blocked Pipeline (Fail-Closed)
# ─────────────────────────────────────────────────────────────

async def test_corporate_verification_pipeline_dnc_blocked_stops_charge(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """When corporate rep phone is in DNC registry, resolution halts with 0 credits debited."""
    initial_balance = 5_000_000
    db_user.credit_micros_balance = initial_balance
    db_session.add(db_user)

    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        source="b2b_sourcing",
        company_name="CÔNG TY CỔ PHẦN VNG",
        location="Quận 7, TP Hồ Chí Minh",
    )
    db_session.add(lead)
    await db_session.flush()

    client_mock = MockMasothueClient()
    corp_service = CorporateVerificationService(db_session, masothue_client=client_mock, redis_client=None)
    await corp_service.verify_lead_corporate_info(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
    )

    fake_redis = AsyncMock()
    fake_redis.get.return_value = None
    fake_redis.mget.return_value = (None, None)
    phone_service = PhoneWaterfallService(
        db_session, masothue_client=client_mock, redis_client=fake_redis
    )

    with (
        patch("app.services.phone_waterfall_service.get_redis", return_value=None),
        patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.check_phone",
            new_callable=AsyncMock,
            return_value=DncCheckResult(is_blocked=True, reason="workspace_dnc"),
        ),
    ):
        phone_res = await phone_service.resolve_lead_phone(
            workspace_id=db_workspace.id,
            client_id=None,
            lead_id=lead.id,
            user_id=db_user.id,
        )

        assert phone_res.status == "blocked_by_dnc"
        assert phone_res.phone is None
        assert phone_res.cost_micros == 0

        # Balance remains unchanged
        assert db_user.credit_micros_balance == initial_balance


# ─────────────────────────────────────────────────────────────
# 5. Circuit Breaker Resilience in Pipeline
# ─────────────────────────────────────────────────────────────

async def test_corporate_verification_pipeline_circuit_breaker_resilience(
    db_session: AsyncSession, db_workspace: Workspace
):
    """When circuit breaker is OPEN, pipeline gracefully degrades without unhandled crashes."""
    lead = Lead(
        id=uuid.uuid4(),
        workspace_id=db_workspace.id,
        source="b2b_corp",
        company_name="CÔNG TY CỔ PHẦN FPT",
        location="Cầu Giấy, Hà Nội",
    )
    db_session.add(lead)
    await db_session.flush()

    fake_redis = AsyncMock()
    # Breaker open in Redis
    fake_redis.get.side_effect = lambda key: "open" if "circuit_breaker" in key else None

    client_mock = MockMasothueClient()
    corp_service = CorporateVerificationService(db_session, masothue_client=client_mock, redis_client=fake_redis)

    corp_res = await corp_service.verify_lead_corporate_info(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
    )

    assert corp_res.degraded is True
    assert corp_res.degradation_reason == "circuit_breaker_open"
    assert corp_res.is_verified is False
    assert client_mock.call_count == 0
