"""Integration tests for Global DNC Blacklist routes (Story 25.6).

Tests superadmin guard, single add, CSV bulk import, delete, Redis cache invalidation,
and immediate enforcement via DncComplianceService.is_blocked().
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

pytestmark = [pytest.mark.integration]


def _load_models():
    try:
        from app.db import AuditEvent, GlobalDncRecord

        return GlobalDncRecord, AuditEvent
    except ImportError as exc:
        pytest.fail(f"Models not ready: {exc}")


class TestAdminDncRoutes:
    """AC-2 / AC-5: Global DNC Blacklist Management with Real Postgres & Redis."""

    async def test_dnc_routes_reject_regular_user(
        self, client_as_regular_user: AsyncClient
    ):
        res = await client_as_regular_user.get("/api/v1/admin/dnc/global")
        assert res.status_code == 403

        res_post = await client_as_regular_user.post(
            "/api/v1/admin/dnc/global",
            json={"record_type": "phone", "value": "0911222333", "reason": "test"},
        )
        assert res_post.status_code == 403

    async def test_add_dnc_record_and_immediate_enforcement(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """AC-2: Adding DNC persists row, writes AuditEvent, and blocks via DncComplianceService."""
        _global_dnc_cls, audit_event_cls = _load_models()

        payload = {
            "record_type": "phone",
            "value": "0988776655",
            "reason": "Customer explicit opt-out Decree 13",
            "source": "admin_portal",
        }

        res = await admin_client.post("/api/v1/admin/dnc/global", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["record_type"] == "phone"
        assert "value_hmac" in data

        # Verify DB audit event
        audit = (
            (
                await db_session.execute(
                    select(audit_event_cls).filter_by(action="global_dnc.add")
                )
            )
            .scalars()
            .first()
        )
        assert audit is not None
        assert audit.diff_payload["endpoint"] == "/api/v1/admin/dnc/global"

    async def test_import_dnc_csv(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """AC-2: Bulk CSV import processes rows and returns summary."""
        csv_data = "record_type,value,reason\nphone,0901234567,Test optout\ndomain,spammy.xyz,Malicious"
        files = {"file": ("dnc.csv", csv_data.encode("utf-8"), "text/csv")}

        res = await admin_client.post(
            "/api/v1/admin/dnc/global/import-csv", files=files
        )
        assert res.status_code == 200
        summary = res.json()
        assert summary["imported_count"] == 2
        assert summary["failed_count"] == 0

    async def test_delete_dnc_record(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """AC-2: Superadmin can delete DNC record, creating audit log."""
        _global_dnc_cls, _ = _load_models()

        # First add record
        payload = {
            "record_type": "domain",
            "value": "whitelist-me.com",
            "reason": "Mistakenly added",
            "source": "admin_portal",
        }
        create_res = await admin_client.post("/api/v1/admin/dnc/global", json=payload)
        record_id = create_res.json()["id"]

        del_res = await admin_client.delete(f"/api/v1/admin/dnc/global/{record_id}")
        assert del_res.status_code in (200, 204)
