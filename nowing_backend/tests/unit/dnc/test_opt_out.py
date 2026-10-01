"""Unit tests for register_contact_opt_out (Story 38.4 / Decree 91 / PDPD)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lead_intelligence.dnc.normalizer import hash_phone_hmac
from app.lead_intelligence.dnc.service import register_contact_opt_out

pytestmark = pytest.mark.unit


@pytest.fixture
def session():
    sess = AsyncMock()
    # Mock scalar_one_or_none to return None initially (not exists)
    res = MagicMock()
    res.scalar_one_or_none.return_value = None
    sess.execute.return_value = res
    sess.add = MagicMock()
    sess.flush = AsyncMock()
    return sess


class TestRegisterContactOptOut:
    """Verify phone, email, and domain normalization and DNC persistence."""

    async def test_normalizes_vietnamese_local_phone_to_e164(self, session):
        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.invalidate_workspace_cache",
            AsyncMock(),
        ):
            record = await register_contact_opt_out(
                session,
                workspace_id=15,
                contact_type="phone",
                value="0901234567",
                secret_key="test_secret",
            )

        assert record is not None
        assert record.value == "+84901234567"
        assert record.record_type == "phone"
        assert record.workspace_id == 15
        expected_hmac = hash_phone_hmac("+84901234567", secret_key="test_secret")
        assert record.value_hmac == expected_hmac
        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()

    async def test_normalizes_email_to_lowercase(self, session):
        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.invalidate_workspace_cache",
            AsyncMock(),
        ):
            record = await register_contact_opt_out(
                session,
                workspace_id=15,
                contact_type="email",
                value="  CEO@Nowing.Net  ",
                reason="email_unsubscribe",
                secret_key="test_secret",
            )

        assert record is not None
        assert record.value == "ceo@nowing.net"
        assert record.reason == "email_unsubscribe"

    async def test_normalizes_domain_strips_protocol_and_path(self, session):
        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.invalidate_workspace_cache",
            AsyncMock(),
        ):
            record = await register_contact_opt_out(
                session,
                workspace_id=15,
                contact_type="domain",
                value="https://Sub.Competitor.VN/pricing?ref=x",
                secret_key="test_secret",
            )

        assert record is not None
        assert record.value == "sub.competitor.vn"

    async def test_invalid_phone_returns_none_and_does_not_persist(self, session):
        record = await register_contact_opt_out(
            session,
            workspace_id=15,
            contact_type="phone",
            value="not_a_phone",
        )
        assert record is None
        session.add.assert_not_called()

    async def test_empty_value_returns_none(self, session):
        assert (
            await register_contact_opt_out(session, 15, "phone", "")
        ) is None

    async def test_idempotent_when_already_exists(self, session):
        """Pre-existing DNC record is returned without re-adding."""
        existing_record = MagicMock()
        existing_record.value = "+84901234567"

        res = MagicMock()
        res.scalar_one_or_none.return_value = existing_record
        session.execute.return_value = res

        record = await register_contact_opt_out(
            session,
            workspace_id=15,
            contact_type="phone",
            value="+84901234567",
        )
        assert record is existing_record
        session.add.assert_not_called()

    async def test_cache_invalidation_failure_does_not_break_registration(
        self, session
    ):
        """DB record must persist even if Redis cache invalidation fails."""
        with patch(
            "app.lead_intelligence.dnc.service.DncComplianceService.invalidate_workspace_cache",
            AsyncMock(side_effect=RuntimeError("Redis down")),
        ):
            record = await register_contact_opt_out(
                session,
                workspace_id=15,
                contact_type="phone",
                value="+84901234567",
            )

        assert record is not None
        session.add.assert_called_once()
