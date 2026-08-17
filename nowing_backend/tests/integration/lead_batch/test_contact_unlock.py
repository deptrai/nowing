"""Integration tests for Story 26.1 contact unlock billing (AC-6)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db import BillingEvent, Lead, User, VerifiedContact

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_contact_unlock_debits_and_sets_unlocked(
    client, db_user, db_workspace, db_session
):
    """Pattern 4/6: unlock debits 1500 micros, sets is_unlocked, writes BillingEvent and audit log."""
    db_user.credit_micros_balance = 5000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        value_hmac="abc",
        source="test",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name="Alice",
        phone="encrypted-phone",
        email="encrypted-email",
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

    # Refresh user and contact
    user = await db_session.get(User, db_user.id)
    assert user.credit_micros_balance == 3500

    refreshed = (
        await db_session.execute(
            select(VerifiedContact).where(VerifiedContact.id == contact.id)
        )
    ).scalar_one()
    assert refreshed.is_unlocked is True
    assert len(refreshed.pii_access_audit_logs) == 1

    billing_event = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.cost_micros == 1500,
            )
        )
    ).scalar_one_or_none()
    assert billing_event is not None


@pytest.mark.asyncio
async def test_contact_unlock_insufficient_credits(
    client, db_user, db_workspace, db_session
):
    """Pattern 3/4: unlock fails when balance is below 1500 and is_unlocked stays False."""
    db_user.credit_micros_balance = 1000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        value_hmac="abc",
        source="test",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name="Alice",
        phone="encrypted-phone",
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

    refreshed = (
        await db_session.execute(
            select(VerifiedContact).where(VerifiedContact.id == contact.id)
        )
    ).scalar_one()
    assert refreshed.is_unlocked is False

    billing_count = (
        await db_session.execute(
            select(BillingEvent).where(BillingEvent.workspace_id == db_workspace.id)
        )
    ).scalar_one_or_none()
    assert billing_count is None


@pytest.mark.asyncio
async def test_contact_unlock_idempotent(
    client, db_user, db_workspace, db_session
):
    """Pattern 3/6: second unlock returns without double debit."""
    db_user.credit_micros_balance = 5000
    db_user.credit_micros_reserved = 0
    await db_session.flush()

    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        value_hmac="abc",
        source="test",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name="Alice",
        phone="encrypted-phone",
        value_hmac="contact-hmac",
        is_unlocked=False,
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
    )
    resp2 = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/unlock"
    )
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["cost_micros"] == 0

    user = await db_session.get(User, db_user.id)
    assert user.credit_micros_balance == 3500

    billing_count = (
        await db_session.execute(
            select(func.count(BillingEvent.id)).where(
                BillingEvent.workspace_id == db_workspace.id
            )
        )
    ).scalar_one()
    assert billing_count == 1


@pytest.mark.asyncio
async def test_contact_unlock_non_member_forbidden(client_as_other, db_workspace):
    """Pattern 3: non-member cannot unlock contact."""
    lead_id = uuid4()
    contact_id = uuid4()
    resp = await client_as_other.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead_id}/contacts/{contact_id}/unlock"
    )
    assert resp.status_code == 403
