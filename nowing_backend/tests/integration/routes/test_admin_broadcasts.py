"""Integration tests for In-App Broadcast Announcements routes (Story 25.6).

Tests superadmin CRUD, AuditEvent persistence, active broadcast querying, workspace targeting,
and fail-closed superadmin guard.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

pytestmark = [pytest.mark.integration]


def _load_models():
    try:
        from app.db import AuditEvent, BroadcastAnnouncement, Workspace

        return BroadcastAnnouncement, AuditEvent, Workspace
    except ImportError as exc:
        pytest.fail(f"Models not ready: {exc}")


class TestAdminBroadcastsRoutes:
    """AC-3 / AC-4 / AC-5: In-App Broadcast Announcements CRUD & Active Feed."""

    async def test_admin_broadcasts_rejects_regular_user(
        self, client_as_regular_user: AsyncClient
    ):
        res = await client_as_regular_user.get("/api/v1/admin/broadcasts")
        assert res.status_code == 403

        res_post = await client_as_regular_user.post(
            "/api/v1/admin/broadcasts",
            json={"title": "Test", "message": "Alert", "banner_type": "info"},
        )
        assert res_post.status_code == 403

    async def test_create_and_list_broadcast_admin(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """AC-3: Superadmin creates broadcast, verified in DB and list API."""
        _broadcast_cls, audit_event_cls, _ = _load_models()

        payload = {
            "title": "Scheduled Maintenance Notice",
            "message": "**Database upgrade** will take place Sunday at 02:00 UTC.",
            "banner_type": "maintenance",
            "target_all": True,
            "target_workspace_ids": [],
            "starts_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "dismissible": True,
            "is_active": True,
        }

        res = await admin_client.post("/api/v1/admin/broadcasts", json=payload)
        assert res.status_code == 201
        created = res.json()
        assert created["title"] == payload["title"]
        assert created["banner_type"] == "maintenance"
        assert created["status"] == "active"

        # Verify audit log
        audit = (
            (
                await db_session.execute(
                    select(audit_event_cls).filter_by(action="broadcast.create")
                )
            )
            .scalars()
            .first()
        )
        assert audit is not None
        assert audit.diff_payload["title"] == payload["title"]

        # List broadcasts
        list_res = await admin_client.get("/api/v1/admin/broadcasts")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert any(b["id"] == created["id"] for b in list_data["items"])

    async def test_active_broadcasts_public_endpoint_for_regular_user(
        self,
        admin_client: AsyncClient,
        client_as_regular_user: AsyncClient,
        db_session: AsyncSession,
    ):
        """AC-4: Regular authenticated user gets active broadcasts matching workspace."""
        # Create an active broadcast
        payload = {
            "title": "New Feature Available",
            "message": "Check out the AI workflow assistant!",
            "banner_type": "info",
            "target_all": True,
            "target_workspace_ids": [],
            "starts_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "dismissible": True,
            "is_active": True,
        }
        create_res = await admin_client.post("/api/v1/admin/broadcasts", json=payload)
        assert create_res.status_code == 201

        # Regular user queries active broadcasts
        res = await client_as_regular_user.get("/api/v1/broadcasts/active")
        assert res.status_code == 200
        active_items = res.json()
        assert any(b["title"] == payload["title"] for b in active_items)
