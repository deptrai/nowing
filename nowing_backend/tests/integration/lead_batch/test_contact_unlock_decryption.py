"""Integration tests for contact unlock PII response and masking (Story 26.4)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import BillingEvent, Lead, VerifiedContact
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = [pytest.mark.integration]


def _encrypt(value: str) -> str:
    return VerifiedContactEncryption().encrypt(value)


@pytest.mark.asyncio
async def test_unlock_returns_decrypted_phone_and_email(
    client, db_user, db_workspace, db_session
):
    """Pattern 1/6: unlock response contains decrypted PII only after billing."""
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
        phone_hmac="phone-hash",
        email_hmac="email-hash",
        value_hmac="contact-hmac",
        is_unlocked=False,
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_unlocked"] is True
    assert body["cost_micros"] == 1500
    assert body["phone"] == phone
    assert body["email"] == email

    billing_event = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.event_type == "contact_unlock",
            )
        )
    ).scalar_one_or_none()
    assert billing_event is not None
    assert billing_event.user_id == db_user.id


@pytest.mark.asyncio
async def test_unlock_does_not_leak_decrypted_pii_when_billing_fails(
    client, db_user, db_workspace, db_session
):
    """Pattern 2/5: insufficient credits → 402 and no PII in response."""
    db_user.credit_micros_balance = 0
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

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name=_encrypt("Alice"),
        phone=_encrypt("+84908123456"),
        email=_encrypt("alice@acme.com"),
        phone_hmac="phone-hash",
        email_hmac="email-hash",
        value_hmac="contact-hmac",
        is_unlocked=False,
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
    )
    assert resp.status_code == 402
    assert "phone" not in resp.json()
    assert "email" not in resp.json()


@pytest.mark.asyncio
async def test_lead_list_masks_unlocked_false_contacts(
    client, db_user, db_workspace, db_session
):
    """Pattern 1/6: lead list returns masked PII when contact is not unlocked."""
    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        domain="acme.com",
        value_hmac="lead-hmac",
        source="test",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name=_encrypt("Alice Nguyen"),
        title=_encrypt("CEO"),
        phone=_encrypt("+84908123456"),
        email=_encrypt("alice@acme.com"),
        phone_hmac="phone-hash",
        email_hmac="email-hash",
        value_hmac="contact-hmac",
        is_unlocked=False,
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads",
    )
    assert resp.status_code == 200
    body = resp.json()
    lead_item = next(
        (item for item in body["items"] if item["id"] == str(lead.id)), None
    )
    assert lead_item is not None
    # Masked phone and email; exact mask format depends on mask_phone/mask_email.
    assert "***" in lead_item["phone"]
    assert "***" in lead_item["email"]
    # Name should not be the full plaintext.
    assert lead_item["name"] != "Alice Nguyen"
