"""Unit tests for BroadcastService (Story 25.6).

These tests mock the database session so they run isolated without live Postgres.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def _load_service():
    try:
        from app.services.broadcast_service import BroadcastService

        return BroadcastService
    except ImportError as exc:
        pytest.fail(f"BroadcastService not implemented yet: {exc}")


class _Row:
    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _MockResult:
    def __init__(self, rows: list[_Row] | None = None, scalar_value: Any = None):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def all(self) -> list[_Row]:
        return self._rows

    def scalars(self) -> _MockResult:
        return self

    def scalar_one_or_none(self) -> Any:
        return self._scalar_value


@pytest.fixture
def service():
    service_cls = _load_service()
    session = AsyncMock()
    return service_cls(session)


@pytest.mark.asyncio
async def test_compute_derived_status(service) -> None:
    """AC-3: Status is computed from is_active, starts_at, and expires_at."""
    now = datetime.now(UTC)

    # Inactive
    assert (
        service.compute_status(
            is_active=False,
            starts_at=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=1),
        )
        == "inactive"
    )

    # Scheduled (starts in future)
    assert (
        service.compute_status(
            is_active=True,
            starts_at=now + timedelta(hours=2),
            expires_at=now + timedelta(hours=4),
        )
        == "scheduled"
    )

    # Expired
    assert (
        service.compute_status(
            is_active=True,
            starts_at=now - timedelta(hours=4),
            expires_at=now - timedelta(hours=1),
        )
        == "expired"
    )

    # Active with expiry
    assert (
        service.compute_status(
            is_active=True,
            starts_at=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=2),
        )
        == "active"
    )

    # Active without expiry
    assert (
        service.compute_status(
            is_active=True,
            starts_at=now - timedelta(hours=1),
            expires_at=None,
        )
        == "active"
    )


@pytest.mark.asyncio
async def test_create_broadcast_validates_target_workspaces(service) -> None:
    """AC-3: When target_all=False, validates that target_workspace_ids exist."""
    admin_id = uuid.uuid4()

    # Mock DB query for workspace existence returning missing workspace ID
    service.session.execute = AsyncMock(return_value=_MockResult(rows=[_Row(id=10)]))

    with pytest.raises(ValueError, match="Workspace IDs do not exist"):
        await service.create_broadcast(
            title="Maintenance Alert",
            message="Database maintenance in progress.",
            banner_type="maintenance",
            target_all=False,
            target_workspace_ids=[10, 99],  # 99 does not exist
            actor_id=admin_id,
            ip_address="127.0.0.1",
            user_agent="AdminBrowser/1.0",
            endpoint="/api/v1/admin/broadcasts",
        )


@pytest.mark.asyncio
async def test_create_broadcast_persists_and_audits(service) -> None:
    """AC-3: Successfully creates BroadcastAnnouncement and writes AuditEvent."""
    admin_id = uuid.uuid4()
    service.session.add = MagicMock()
    service.session.flush = AsyncMock()

    broadcast = await service.create_broadcast(
        title="Welcome Promo",
        message="Get 50% discount on credit packages!",
        banner_type="promo",
        target_all=True,
        target_workspace_ids=[],
        starts_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        dismissible=True,
        is_active=True,
        actor_id=admin_id,
        ip_address="127.0.0.1",
        user_agent="AdminBrowser/1.0",
        endpoint="/api/v1/admin/broadcasts",
    )

    assert broadcast is not None
    assert service.session.add.call_count >= 2  # BroadcastAnnouncement + AuditEvent


@pytest.mark.asyncio
async def test_get_active_broadcasts_filters_by_workspace(service) -> None:
    """AC-4: Active broadcast evaluation filters for target_all or workspace_id in target_workspace_ids."""
    now = datetime.now(UTC)
    mock_announcement = _Row(
        id=uuid.uuid4(),
        title="Global Announcement",
        message="System update complete",
        banner_type="info",
        target_all=True,
        target_workspace_ids=[],
        starts_at=now - timedelta(minutes=5),
        expires_at=None,
        dismissible=True,
        is_active=True,
        created_at=now - timedelta(minutes=5),
    )

    service.session.execute = AsyncMock(
        return_value=_MockResult(rows=[mock_announcement])
    )

    results = await service.get_active_broadcasts(workspace_id=101)
    assert len(results) == 1
    assert results[0].title == "Global Announcement"
