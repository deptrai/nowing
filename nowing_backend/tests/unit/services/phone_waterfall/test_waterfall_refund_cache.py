"""Unit tests for phone waterfall Redis caching and auto-refund SLA within 24h (Story 21.3 / Story 24.2 / INV-24.3)."""

from __future__ import annotations

import json
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
from app.services.phone_waterfall_service import PhoneWaterfallService


@pytest.mark.unit
class TestAutoRefundAndCaching:
    """Validate 24h refund SLA and Redis cache bypass of charges."""

    @pytest.mark.asyncio
    async def test_waterfall_redis_cache_hit_skips_billing(self, monkeypatch):
        from app.config import config
        from app.services.pii.verified_contact_encryption import (
            VerifiedContactEncryption,
        )

        test_key = "test-secret-key-must-be-long-enough-12345678"
        monkeypatch.setattr(config, "SECRET_KEY", test_key)

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

        encryption = VerifiedContactEncryption()
        fake_redis = AsyncMock()
        cached_envelope = json.dumps(
            {
                "phone": encryption.encrypt("0908123456"),
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
                "app.services.phone_waterfall_service.get_redis",
                return_value=fake_redis,
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
                User(id=user_id, credit_micros_balance=5000000)
                if model == User
                else None
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
            created_at=datetime.now(UTC)
            - timedelta(hours=26),  # 26 hours ago (>24h SLA)
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
