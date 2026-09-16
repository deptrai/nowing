"""Unit tests for TelegramChannelService (Story 34.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.leads.social import SocialMonitoredTarget
from app.services.telegram_channel_service import (
    TelegramChannelService,
    _clean_channel_target,
)

pytestmark = [pytest.mark.unit]


class TestCleanChannelTarget:
    """Test channel target string cleaning."""

    def test_clean_username_with_at(self):
        target_id, url = _clean_channel_target("@mychannel")
        assert target_id == "mychannel"
        assert url == "https://t.me/mychannel"

    def test_clean_tme_url(self):
        target_id, url = _clean_channel_target("https://t.me/joinchannel?start=123")
        assert target_id == "joinchannel"
        assert url == "https://t.me/joinchannel"

    def test_clean_plain_name(self):
        target_id, url = _clean_channel_target("simple_channel")
        assert target_id == "simple_channel"
        assert url == "https://t.me/simple_channel"


class TestTelegramChannelService:
    """Test CRUD operations on monitored Telegram channels."""

    @pytest.mark.asyncio
    async def test_add_channel_creates_new_target(self):
        """add_channel inserts a new SocialMonitoredTarget."""
        session = AsyncMock()

        # Mock no existing channel
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        service = TelegramChannelService(session)
        res = await service.add_channel(
            workspace_id=1,
            target="@testleads",
            name="Test Leads Channel",
        )

        assert res["status"] == "created"
        assert res["target_id"] == "testleads"
        assert res["is_active"] is True
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_channel_reactivates_if_existing(self):
        """add_channel reactivates inactive existing channel."""
        session = AsyncMock()

        existing = MagicMock(spec=SocialMonitoredTarget)
        existing.id = 42
        existing.target_id = "testleads"
        existing.target_name = "Test Leads"
        existing.is_active = False

        scalars_mock = MagicMock()
        scalars_mock.first.return_value = existing
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        service = TelegramChannelService(session)
        res = await service.add_channel(
            workspace_id=1,
            target="@testleads",
        )

        assert res["status"] == "already_monitored"
        assert existing.is_active is True

    @pytest.mark.asyncio
    async def test_toggle_channel_flips_active_state(self):
        """toggle_channel flips is_active from True to False."""
        session = AsyncMock()

        target = MagicMock(spec=SocialMonitoredTarget)
        target.id = 10
        target.target_id = "mychannel"
        target.is_active = True

        scalars_mock = MagicMock()
        scalars_mock.first.return_value = target
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        service = TelegramChannelService(session)
        res = await service.toggle_channel(workspace_id=1, target_id=10)

        assert res["is_active"] is False

    @pytest.mark.asyncio
    async def test_delete_channel_removes_record(self):
        """delete_channel removes the target and returns True."""
        session = AsyncMock()

        target = MagicMock(spec=SocialMonitoredTarget)
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = target
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock

        service = TelegramChannelService(session)
        deleted = await service.delete_channel(workspace_id=1, target_id=10)

        assert deleted is True
        session.delete.assert_called_once_with(target)
