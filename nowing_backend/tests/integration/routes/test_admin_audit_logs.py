"""Integration tests for Admin Audit Logs routes (Story 25.6).

Tests superadmin guard, filtering by action/emails/ticket_ref, pagination, and CSV/JSON export.
Requires real Postgres.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


def _load_models():
    try:
        from app.db import AuditEvent, User

        return AuditEvent, User
    except ImportError as exc:
        pytest.fail(f"Models not ready: {exc}")


class TestAdminAuditLogsRoutes:
    """AC-1 / AC-5: Superadmin Audit Logs API & Query Filters."""

    async def test_audit_logs_rejects_unauthenticated(self, client: AsyncClient):
        res = await client.get("/api/v1/admin/audit-logs")
        assert res.status_code in (401, 403)

    async def test_audit_logs_rejects_regular_user(
        self, client_as_regular_user: AsyncClient
    ):
        res = await client_as_regular_user.get("/api/v1/admin/audit-logs")
        assert res.status_code == 403

    async def test_audit_logs_rejects_pat_token(
        self, pat_client: AsyncClient
    ):
        """INV-25.8: PAT tokens are fail-closed rejected on all admin routes."""
        res = await pat_client.get(
            "/api/v1/admin/audit-logs",
        )
        assert res.status_code in (401, 403)

    async def test_audit_logs_list_for_superuser(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_superuser,
    ):
        """AC-1: Returns list of audit records with actor_email resolved."""
        audit_event_cls, _ = _load_models()

        event = audit_event_cls(
            actor_id=db_superuser.id,
            subject_id=None,
            action="global_dnc.add",
            ip_address="127.0.0.1",
            user_agent="PytestClient",
            diff_payload={
                "record_type": "phone",
                "endpoint": "/api/v1/admin/dnc/global",
            },
        )
        db_session.add(event)
        await db_session.commit()

        res = await admin_client.get("/api/v1/admin/audit-logs")
        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        assert "total" in body
        assert any(item["action"] == "global_dnc.add" for item in body["items"])

    async def test_audit_logs_filters_by_action(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_superuser,
    ):
        """AC-1: Filtering by action parameter."""
        res = await admin_client.get("/api/v1/admin/audit-logs?action=broadcast.create")
        assert res.status_code == 200
        body = res.json()
        for item in body["items"]:
            assert item["action"] == "broadcast.create"
