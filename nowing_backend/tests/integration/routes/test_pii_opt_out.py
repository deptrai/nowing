"""Integration tests for PII opt-out route (Story 26.4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db import (
    BillingEvent,
    Lead,
    User,
    VerifiedContact,
    WorkspaceDncRecord,
    WorkspaceMembership,
)
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_email,
    normalize_phone_e164,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = [pytest.mark.integration]


def _encrypt(value: str) -> str:
    return VerifiedContactEncryption().encrypt(value)


def _phone_hash(phone: str) -> str:
    e164 = normalize_phone_e164(phone)
    assert e164
    return hash_phone_hmac(e164)


def _email_hash(email: str) -> str:
    norm = normalize_email(email)
    assert norm
    return hash_phone_hmac(norm)


@pytest.mark.asyncio
async def test_opt_out_purges_and_refunds_unlocked_contact(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """Pattern 1/4/6: opt-out purges PII, refunds credit, writes DNC + BillingEvent."""
    db_user.credit_micros_balance = 5_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        domain="acme.com",
        value_hmac="lead-hmac",
        source="test",
    )
    db_session.add(lead)
    await db_session.flush()

    phone = "+84908123456"
    email = "alice@acme.com"
    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name=_encrypt("Alice"),
        title=_encrypt("CEO"),
        phone=_encrypt(phone),
        email=_encrypt(email),
        phone_hmac=_phone_hash(phone),
        email_hmac=_email_hash(email),
        value_hmac="contact-hmac",
        is_unlocked=False,
        consent=True,
        consent_status="opted_in",
        legal_basis="consent",
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    # Unlock first so there is a BillingEvent to refund.
    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost_micros"] == 1500

    user_before = await db_session.get(User, db_user.id)
    assert user_before.credit_micros_balance == 3500

    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
        json={
            "record_type": "phone",
            "value": phone,
            "reason": "Right to be forgotten",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["purged_contact_count"] == 1
    assert body["refunded_micros"] == 1500
    assert body["dnc_record_id"]

    # DB state
    refreshed = (
        await db_session.execute(
            select(VerifiedContact).where(VerifiedContact.id == contact.id)
        )
    ).scalar_one()
    assert refreshed.is_unlocked is False
    assert refreshed.consent is False
    assert refreshed.consent_status == "withdrawn"
    assert refreshed.legal_basis == "opt_out"
    assert refreshed.name is None
    assert refreshed.title is None
    assert refreshed.phone is None
    assert refreshed.email is None
    assert any(
        log.get("access_type") == "opt_out_purged"
        for log in refreshed.pii_access_audit_logs
    )

    user_after = await db_session.get(User, db_user.id)
    assert user_after.credit_micros_balance == 5000

    membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    assert membership.monthly_spent_micros == 0

    refund_event = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.event_type == "contact_unlock_refund",
            )
        )
    ).scalar_one_or_none()
    assert refund_event is not None
    assert refund_event.cost_micros == -1500
    assert refund_event.user_id == db_user.id

    dnc_record = (
        await db_session.execute(
            select(WorkspaceDncRecord).where(
                WorkspaceDncRecord.workspace_id == db_workspace.id,
                WorkspaceDncRecord.record_type == "phone",
                WorkspaceDncRecord.value_hmac == _phone_hash(phone),
            )
        )
    ).scalar_one_or_none()
    assert dnc_record is not None
    assert dnc_record.source == "opt_out"


@pytest.mark.asyncio
async def test_opt_out_without_unlocked_contact_refunds_zero(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """Pattern 3/6: contact never unlocked → purge but no refund."""
    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        domain="acme.com",
        value_hmac="lead-hmac",
        source="test",
    )
    db_session.add(lead)
    await db_session.flush()

    phone = "+84908123456"
    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name=_encrypt("Alice"),
        phone=_encrypt(phone),
        email=None,
        phone_hmac=_phone_hash(phone),
        email_hmac=None,
        value_hmac="contact-hmac",
        is_unlocked=False,
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
        json={
            "record_type": "phone",
            "value": phone,
            "reason": "Right to be forgotten",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["purged_contact_count"] == 1
    assert body["refunded_micros"] == 0


@pytest.mark.asyncio
async def test_opt_out_respects_15_percent_refund_cap(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """Pattern 4: refund cap exhausted → only purge, no refund."""
    db_user.credit_micros_balance = 100_000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        domain="acme.com",
        value_hmac="lead-hmac",
        source="test",
    )
    db_session.add(lead)
    await db_session.flush()

    phone = "+84908123456"
    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name=_encrypt("Alice"),
        phone=_encrypt(phone),
        email=None,
        phone_hmac=_phone_hash(phone),
        email_hmac=None,
        value_hmac="contact-hmac",
        is_unlocked=True,
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    # Seed one unlock BillingEvent; pretend 15% cap already reached via a refund event.
    db_session.add(
        BillingEvent(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            event_entity_type="verified_contact",
            event_type="contact_unlock_refund",
            event_id=contact.id,
            cost_micros=-1500,
            currency="USD",
            cost_basis="actual",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
        json={
            "record_type": "phone",
            "value": phone,
            "reason": "Right to be forgotten",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["purged_contact_count"] == 1
    assert body["refunded_micros"] == 0


@pytest.mark.asyncio
async def test_opt_out_returns_400_for_invalid_phone(
    client_as_regular_user, db_workspace
):
    """Pattern 5: malformed phone returns clear 400."""
    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
        json={"record_type": "phone", "value": "not-a-phone"},
    )
    assert resp.status_code == 400
    assert "phone" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_member_cannot_opt_out(client_as_other, db_workspace):
    """Pattern 3: non-member gets 403."""
    resp = await client_as_other.post(
        f"/api/v1/workspaces/{db_workspace.id}/pii-opt-out",
        json={"record_type": "phone", "value": "+84908123456"},
    )
    assert resp.status_code == 403
