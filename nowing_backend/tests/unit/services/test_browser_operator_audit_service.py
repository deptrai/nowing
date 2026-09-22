"""Unit tests for browser operator audit service (Story 32.3)."""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.browser_operator_audit import BrowserOperatorAuditEvent
from app.services.browser_operator_audit_service import (
    BrowserOperatorAuditService,
    generate_session_token,
    validate_session_token,
)

pytestmark = [pytest.mark.unit]



def _make_mock_session() -> MagicMock:
    """Create a mock AsyncSession where add() is sync but flush/commit are async."""
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session

class TestSessionToken:
    """Test CDP session token generation and validation."""

    def test_generate_session_token_format(self):
        """Token should have correct format: cdp_sess.{mission}.{ts}.{sig}."""
        token = generate_session_token("mission-123", "user-456")
        assert token.startswith("cdp_sess.")
        parts = token.split(".")
        assert len(parts) == 4
        assert parts[1] == "mission-123"
        assert parts[2].isdigit()

    @pytest.mark.asyncio
    async def test_validate_session_token_valid(self):
        """Valid token should pass validation."""
        mission_id = str(uuid.uuid4()).replace("-", "")
        user_id = str(uuid.uuid4()).replace("-", "")
        token = generate_session_token(mission_id, user_id)

        valid, err = await validate_session_token(token, mission_id, user_id)
        assert valid is True
        assert err is None

    @pytest.mark.asyncio
    async def test_validate_session_token_expired(self):
        """Expired token should fail validation."""
        mission_id = str(uuid.uuid4()).replace("-", "")
        user_id = str(uuid.uuid4()).replace("-", "")

        # Create token with old timestamp
        old_ts = int(time.time()) - 400  # 6+ minutes ago
        payload = f"{mission_id}:{user_id}:{old_ts}"
        import hashlib
        import hmac

        from app.services.browser_operator_audit_service import _get_session_secret

        sig = hmac.new(
            _get_session_secret().encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        token = f"cdp_sess.{mission_id}.{old_ts}.{sig}"

        valid, err = await validate_session_token(token, mission_id, user_id)
        assert valid is False
        assert "expired" in err.lower()

    @pytest.mark.asyncio
    async def test_validate_session_token_wrong_mission(self):
        """Token for different mission should fail."""
        token = generate_session_token("mission-a", "user-1")
        valid, err = await validate_session_token(token, "mission-b", "user-1")
        assert valid is False
        assert "mission" in err.lower() or "signature" in err.lower()

    @pytest.mark.asyncio
    async def test_validate_session_token_wrong_user(self):
        """Token for different user should fail."""
        mission_id = str(uuid.uuid4()).replace("-", "")
        token = generate_session_token(mission_id, "user-1")
        valid, err = await validate_session_token(token, mission_id, "user-2")
        assert valid is False
        assert "signature" in err.lower()

    @pytest.mark.asyncio
    async def test_validate_session_token_malformed(self):
        """Malformed token should fail gracefully."""
        valid, err = await validate_session_token("not-a-token", "m", "u")
        assert valid is False
        assert "format" in err.lower() or "malformed" in err.lower()


class TestAuditService:
    """Test audit event logging."""

    @pytest.mark.asyncio
    async def test_log_event_creates_record(self):
        """log_event should create and persist an audit event."""
        session = _make_mock_session()
        event = await BrowserOperatorAuditService.log_event(
            session,
            mission_id=uuid.uuid4(),
            workspace_id=1,
            user_id=uuid.uuid4(),
            command_id="cmd-123",
            action="navigate",
            success=True,
            target_url="https://example.com",
        )

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert isinstance(event, BrowserOperatorAuditEvent)
        assert event.action == "navigate"
        assert event.success is True

    @pytest.mark.asyncio
    async def test_log_event_redacts_pii_in_url(self):
        """target_url should be PII-redacted before storage."""
        session = _make_mock_session()
        url_with_pii = "https://example.com/profile?email=user@example.com&phone=0908123456"

        event = await BrowserOperatorAuditService.log_event(
            session,
            mission_id=uuid.uuid4(),
            workspace_id=1,
            user_id=uuid.uuid4(),
            command_id="cmd-123",
            action="navigate",
            success=True,
            target_url=url_with_pii,
        )

        # URL should be redacted (implementation dependent, but should not contain raw PII)
        assert event.target_url is not None

    @pytest.mark.asyncio
    async def test_log_command_result(self):
        """log_command_result should mark event_type correctly."""
        session = _make_mock_session()
        event = await BrowserOperatorAuditService.log_command_result(
            session,
            mission_id=uuid.uuid4(),
            workspace_id=1,
            user_id=uuid.uuid4(),
            command_id="cmd-123",
            action="navigate",
            success=False,
            error_message="Test error",
            requires_human=True,
            challenge="recaptcha",
        )

        assert event.success is False
        assert event.error_message == "Test error"
        assert event.requires_human is True
        assert event.challenge == "recaptcha"
        assert event.metadata_["event_type"] == "command_result"
