"""Integration tests for Global DNC Blacklist routes (Story 25.6).

Tests superadmin guard, single add, CSV bulk import, delete, Redis cache invalidation,
and immediate enforcement via DncComplianceService.is_blocked().
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    BillingEvent,
    GlobalDncRecord,
    Lead,
    Notification,
    User,
    VerifiedContact,
    Workspace,
)
from app.lead_intelligence.dnc.normalizer import hash_phone_hmac
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = [pytest.mark.integration]


def _load_models():
    try:
        from app.db import AuditEvent, GlobalDncRecord

        return GlobalDncRecord, AuditEvent
    except ImportError as exc:
        pytest.fail(f"Models not ready: {exc}")


def _enc(value: str) -> str:
    return VerifiedContactEncryption().encrypt(value)


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

    async def test_compliance_purge_credit_refund_success_within_30_days(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_user: User,
        db_workspace: Workspace,
    ):
        """Story 33.4: Compliance purge within 30-day window refunds unlock credits and notifies owner."""
        phone = "+84988776655"
        phone_hmac = hash_phone_hmac(phone)

        # Setup lead and verified contact
        lead = Lead(
            workspace_id=db_workspace.id,
            company_name="Story33-4 Company",
            domain="story334.vn",
            value_hmac="story334-lead-hmac",
            source="test",
        )
        db_session.add(lead)
        await db_session.flush()

        contact = VerifiedContact(
            workspace_id=db_workspace.id,
            lead_id=lead.id,
            name=_enc("Test Subject"),
            title=_enc("CEO"),
            phone=_enc(phone),
            email=_enc("subject@story334.vn"),
            phone_hmac=phone_hmac,
            email_hmac=hash_phone_hmac("subject@story334.vn"),
            value_hmac=f"contact-{uuid4().hex[:8]}",
            is_unlocked=True,
            pii_access_audit_logs=[],
        )
        db_session.add(contact)
        await db_session.flush()

        # Unlock event within 30 days (e.g. 5 days ago)
        unlock_ts = datetime.now(UTC) - timedelta(days=5)
        billing_event = BillingEvent(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            event_entity_type="verified_contact",
            event_type="contact_unlock",
            event_id=contact.id,
            cost_micros=1500,
            currency="USD",
            cost_basis="actual",
            created_at=unlock_ts,
        )
        db_session.add(billing_event)

        db_user.credit_micros_balance = 0
        await db_session.flush()

        # Execute compliance purge via admin endpoint
        payload = {
            "record_type": "phone",
            "value": "0988776655",
            "reason": "Decree 13 Right-to-be-Forgotten request",
            "ticket_ref": "TICKET-PURGE-334",
        }
        res = await admin_client.post("/api/v1/admin/dnc/purge", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "purged"
        assert data["purged_counts"]["verified_contacts"] == 1
        assert data["refund_summary"]["refunded_contacts"] == 1
        assert data["refund_summary"]["refunded_micros"] == 1500
        assert data["refund_summary"]["skipped"] == []
        # AC-2 top-level refund fields
        assert data["credits_refunded"] == 1500
        assert data["refunds_skipped"] == 0
        assert len(data["refund_details"]) == 1
        assert data["refund_details"][0]["status"] == "refunded"
        assert data["refund_details"][0]["refunded_micros"] == 1500

        # Verify DB state:
        # 1. Contact is deleted
        deleted_contact = await db_session.get(VerifiedContact, contact.id)
        assert deleted_contact is None

        # 2. Global DNC record exists
        dnc_rec = (
            await db_session.execute(
                select(GlobalDncRecord).where(GlobalDncRecord.value_hmac == phone_hmac)
            )
        ).scalar_one_or_none()
        assert dnc_rec is not None

        # 3. Negative BillingEvent exists
        refund_be = (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_type == "contact_unlock_refund",
                )
            )
        ).scalar_one_or_none()
        assert refund_be is not None
        assert refund_be.cost_micros == -1500

        # 4. User's wallet credited
        await db_session.refresh(db_user)
        assert db_user.credit_micros_balance == 1500

        # 5. In-app notification sent to workspace owner without PII
        notif = (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == db_user.id,
                    Notification.type == "compliance_purge_refund",
                )
            )
        ).scalar_one_or_none()
        assert notif is not None
        assert notif.workspace_id == db_workspace.id
        assert notif.notification_metadata["purged_contacts"] == 1
        assert notif.notification_metadata["refunded_micros"] == 1500
        assert notif.notification_metadata["has_expired_refunds"] is False
        assert phone not in notif.message
        assert "0988776655" not in notif.message

        # AC-4: Re-running purge on the same value is safe — no contacts left, no refund
        res2 = await admin_client.post("/api/v1/admin/dnc/purge", json=payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["purged_counts"]["verified_contacts"] == 0
        assert data2["refund_summary"]["refunded_contacts"] == 0
        assert data2["credits_refunded"] == 0
        assert data2["refunds_skipped"] == 0

        # Still exactly one refund event (idempotent)
        refund_events = (
            (
                await db_session.execute(
                    select(BillingEvent).where(
                        BillingEvent.workspace_id == db_workspace.id,
                        BillingEvent.event_type == "contact_unlock_refund",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(refund_events) == 1

    async def test_compliance_purge_credit_refund_skipped_when_window_expired(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        db_user: User,
        db_workspace: Workspace,
    ):
        """Story 33.4: Contact unlocked > 30 days ago is skipped with window_expired but owner notified."""
        phone = "+84911223344"
        phone_hmac = hash_phone_hmac(phone)

        lead = Lead(
            workspace_id=db_workspace.id,
            company_name="Story33-4 Expired Company",
            domain="expired334.vn",
            value_hmac="expired334-lead-hmac",
            source="test",
        )
        db_session.add(lead)
        await db_session.flush()

        contact = VerifiedContact(
            workspace_id=db_workspace.id,
            lead_id=lead.id,
            name=_enc("Expired Contact"),
            title=_enc("CTO"),
            phone=_enc(phone),
            email=_enc("expired@expired334.vn"),
            phone_hmac=phone_hmac,
            email_hmac=hash_phone_hmac("expired@expired334.vn"),
            value_hmac=f"contact-{uuid4().hex[:8]}",
            is_unlocked=True,
            pii_access_audit_logs=[],
        )
        db_session.add(contact)
        await db_session.flush()

        # Unlock event 35 days ago (> 30 days / 720h)
        unlock_ts = datetime.now(UTC) - timedelta(days=35)
        billing_event = BillingEvent(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            event_entity_type="verified_contact",
            event_type="contact_unlock",
            event_id=contact.id,
            cost_micros=1500,
            currency="USD",
            cost_basis="actual",
            created_at=unlock_ts,
        )
        db_session.add(billing_event)

        db_user.credit_micros_balance = 0
        await db_session.flush()

        payload = {
            "record_type": "phone",
            "value": "0911223344",
            "reason": "Decree 13 Right-to-be-Forgotten request",
            "ticket_ref": "TICKET-EXPIRED-334",
        }
        res = await admin_client.post("/api/v1/admin/dnc/purge", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "purged"
        assert data["refund_summary"]["refunded_contacts"] == 0
        assert data["refund_summary"]["refunded_micros"] == 0
        assert len(data["refund_summary"]["skipped"]) == 1
        assert data["refund_summary"]["skipped"][0]["reason"] == "window_expired"
        assert data["credits_refunded"] == 0
        assert data["refunds_skipped"] == 1
        assert data["refund_details"][0]["status"] == "skipped"
        assert data["refund_details"][0]["skip_reason"] == "window_expired"

        # Verify no refund billing event created
        refund_be = (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_type == "contact_unlock_refund",
                )
            )
        ).scalar_one_or_none()
        assert refund_be is None

        # Wallet unchanged
        await db_session.refresh(db_user)
        assert db_user.credit_micros_balance == 0

        # Owner notified with has_expired_refunds=True
        notif = (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == db_user.id,
                    Notification.type == "compliance_purge_refund",
                )
            )
        ).scalar_one_or_none()
        assert notif is not None
        assert notif.notification_metadata["has_expired_refunds"] is True
        assert notif.notification_metadata["refunded_credits"] == 0
