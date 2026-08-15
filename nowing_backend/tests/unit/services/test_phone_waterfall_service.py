"""Unit tests for Vietnam Phone & Contact Waterfall Engine (Story 21.3 / AD-25, AD-36, AD-42, AD-49)."""

from __future__ import annotations

import hashlib
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
# 1. Normalization, Masking, Hashing & ReDoS Tests
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_normalize_vn_phone_standard_formats():
    assert normalize_vn_phone("0908123456") == "0908123456"
    assert normalize_vn_phone("+84908123456") == "0908123456"
    assert normalize_vn_phone("84908123456") == "0908123456"
    assert normalize_vn_phone("090.812.3456") == "0908123456"
    assert normalize_vn_phone("090 812 3456") == "0908123456"
    assert normalize_vn_phone("0987-654-321") == "0987654321"
    assert normalize_vn_phone("0389 123 456") == "0389123456"
    assert normalize_vn_phone("0778 888 999") == "0778888999"


@pytest.mark.unit
def test_normalize_vn_phone_vietnamese_words():
    assert (
        normalize_vn_phone("không chín không tám một hai ba bốn năm sáu")
        == "0908123456"
    )
    assert (
        normalize_vn_phone("khong chin tam bay sau nam bon ba hai mot") == "0987654321"
    )


@pytest.mark.unit
def test_normalize_vn_phone_invalid_prefixes_or_lengths():
    # Landline or invalid prefixes
    assert normalize_vn_phone("0243888888") is None
    assert normalize_vn_phone("19001560") is None
    assert normalize_vn_phone("123456") is None
    assert normalize_vn_phone("0123456789") is None  # 012 is legacy 11-digit prefix
    assert normalize_vn_phone("") is None
    assert normalize_vn_phone(None) is None


@pytest.mark.unit
def test_anti_redos_execution_time():
    evil_text = "0" * 5000 + " chín " * 500 + " !@#$%^&*() " * 100
    start = time.perf_counter()
    _ = normalize_vn_phone(evil_text, timeout_sec=0.05)
    elapsed = time.perf_counter() - start
    assert (
        elapsed < 0.1
    )  # Must execute or abort well within bound (<100ms max in test env)


@pytest.mark.unit
def test_mask_phone():
    assert mask_phone("0908123456") == "0908***456"
    assert mask_phone("0987654321") == "0987***321"
    assert mask_phone("") == ""
    assert mask_phone(None) == ""


@pytest.mark.unit
def test_hash_phone():
    expected = hashlib.sha256(b"0908123456").hexdigest()
    assert hash_phone("0908123456") == expected
    assert hash_phone(None) is None


@pytest.mark.unit
def test_carrier_name():
    assert get_carrier_name("0981234567") == "Viettel"
    assert get_carrier_name("0861234567") == "Viettel"
    assert get_carrier_name("0911234567") == "VNPT / Vinaphone"
    assert get_carrier_name("0881234567") == "VNPT / Vinaphone"
    assert get_carrier_name("0901234567") == "MobiFone"
    assert get_carrier_name("0791234567") == "MobiFone"
    assert get_carrier_name("0921234567") == "Vietnamobile"
    assert get_carrier_name("0991234567") == "Gmobile"
    assert get_carrier_name("0123456789") == "Unknown"


# ─────────────────────────────────────────────────────────────
# 2. PII Encryption Tests
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_phone_encryption():
    enc = VerifiedContactEncryption("test-secret-key-must-be-long-enough-12345678")
    raw = "0908123456"
    ciphertext = enc.encrypt(raw)
    assert ciphertext != raw
    assert len(ciphertext) > 20
    decrypted = enc.decrypt(ciphertext)
    assert decrypted == raw


# ─────────────────────────────────────────────────────────────
# 3. Waterfall 3-Tier Execution Tests
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
@pytest.mark.asyncio
async def test_waterfall_tier_1_batdongsan_success():
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_waterfall_tier_2_chotot_fallback():
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_waterfall_tier_3_carrier_hlr_fallback():
    session = AsyncMock()
    session.add = MagicMock()
    lead_id = uuid4()
    user_id = uuid4()
    workspace_id = 1

    lead = Lead(
        id=lead_id,
        workspace_id=workspace_id,
        client_id=None,
        source="facebook",
        company_name="Chính chủ bán đất",
        source_url="https://facebook.com/groups/post/123",
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
    ):
        result = await service.resolve_lead_phone(
            workspace_id=workspace_id,
            client_id=None,
            lead_id=lead_id,
            user_id=user_id,
            raw_text="Cần bán gấp lô đất liên hệ chính chủ O912.345.678 gặp A. Tuấn",
        )

        assert result.status == "success"
        assert result.phone == "0912345678"
        assert result.phone_masked == "0912***678"
        assert result.tier_reached == 3
        assert result.provider_used == "carrier_hlr"
        assert result.cost_micros == PHONE_RESOLUTION_COST_MICROS
        assert result.carrier == "VNPT / Vinaphone"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_waterfall_all_tiers_failed_charges_zero():
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_waterfall_redis_cache_hit_skips_billing():
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
        patch(
            "app.services.phone_waterfall_service.get_redis", return_value=fake_redis
        ),
        patch(
            "app.services.phone_waterfall_service.wallet_credit.check_balance",
            new_callable=AsyncMock,
        ) as mock_check,
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
        )

        assert result.status == "success"
        assert result.is_cached is True
        assert result.cost_micros == 0  # No charge on cache hit
        assert result.phone == "0908123456"
        mock_check.assert_not_called()
        mock_debit.assert_not_called()


# ─────────────────────────────────────────────────────────────
# 4. Auto-Refund SLA Tests
# ─────────────────────────────────────────────────────────────
@pytest.mark.unit
@pytest.mark.asyncio
async def test_auto_refund_lead_success_within_24h():
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auto_refund_lead_expired_sla_raises_400():
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auto_refund_already_refunded_raises_400():
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
        status="refunded",
        cost_micros=1500000,
        refunded_at=datetime.now(UTC),
        created_at=datetime.now(UTC) - timedelta(hours=1),
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
    assert "already refunded" in exc_info.value.detail
