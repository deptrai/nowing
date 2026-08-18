"""Red-phase ATDD integration tests for contact relock (Story 26.5).

Covers the POST .../contacts/{contact_id}/relock endpoint:
refund, audit log, 60s window, 15% accidental-relock budget, idempotency,
cross-workspace isolation, and concurrent safety.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import (
    BillingEvent,
    Lead,
    User,
    VerifiedContact,
    WorkspaceMembership,
)
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_phone_e164,
)
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]


def _encrypt(value: str) -> str:
    return VerifiedContactEncryption().encrypt(value)


def _phone_hash(phone: str) -> str:
    e164 = normalize_phone_e164(phone)
    assert e164
    return hash_phone_hmac(e164)


def _email_hash(email: str) -> str:
    from app.lead_intelligence.dnc.normalizer import normalize_email

    norm = normalize_email(email)
    assert norm
    return hash_phone_hmac(norm)


async def _create_unlocked_contact(
    db_session,
    db_user: User,
    db_workspace,
    *,
    unlocked_at: datetime | None = None,
) -> tuple[Lead, VerifiedContact]:
    """Factory for a lead with an unlocked verified contact and original BillingEvent."""
    lead = Lead(
        workspace_id=db_workspace.id,
        company_name="Acme",
        domain="acme.com",
        value_hmac=f"lead-hmac-{uuid4().hex[:8]}",
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
        value_hmac=f"contact-hmac-{uuid4().hex[:8]}",
        is_unlocked=True,
        is_valid=True,
        consent_status="opted_in",
        pii_access_audit_logs=[
            {
                "access_type": "unlock",
                "actor_id": str(db_user.id),
                "timestamp": (unlocked_at or datetime.now(UTC)).isoformat(),
                "reason": "contact_unlock",
            }
        ],
    )
    db_session.add(contact)
    await db_session.flush()

    unlock_ts = unlocked_at or datetime.now(UTC)
    db_session.add(
        BillingEvent(
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
    )

    membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    membership.monthly_spent_micros += 1500

    db_user.credit_micros_balance -= 1500
    await db_session.flush()
    return lead, contact


@pytest.mark.asyncio
async def test_relock_refunds_and_sets_is_unlocked_false(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: relock returns is_unlocked=False, refunds wallet, writes audit log."""
    lead, contact = await _create_unlocked_contact(db_session, db_user, db_workspace)
    balance_before = db_user.credit_micros_balance
    membership = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    spent_before = membership.monthly_spent_micros

    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/relock"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contact_id"] == str(contact.id)
    assert body["is_unlocked"] is False
    assert body["cost_micros"] == 0

    refreshed = await db_session.get(VerifiedContact, contact.id)
    assert refreshed.is_unlocked is False
    assert any(
        log.get("access_type") == "relock" and log.get("reason") == "accidental_unlock"
        for log in refreshed.pii_access_audit_logs
    )

    user_after = await db_session.get(User, db_user.id)
    assert user_after.credit_micros_balance == balance_before + 1500

    membership_after = (
        await db_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
    ).scalar_one()
    assert membership_after.monthly_spent_micros == spent_before - 1500

    relock_event = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.workspace_id == db_workspace.id,
                BillingEvent.event_id == contact.id,
                BillingEvent.event_type == "contact_relock",
            )
        )
    ).scalar_one()
    assert relock_event.cost_micros == -1500
    assert relock_event.user_id == db_user.id


@pytest.mark.asyncio
async def test_relock_is_idempotent(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: second relock returns the same result and does not refund again."""
    lead, contact = await _create_unlocked_contact(db_session, db_user, db_workspace)

    first = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/relock"
    )
    assert first.status_code == 200
    balance_after_first = db_user.credit_micros_balance

    second = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/relock"
    )
    assert second.status_code == 200
    assert second.json() == first.json()

    events = (
        (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_id == contact.id,
                    BillingEvent.event_type == "contact_relock",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    user_after = await db_session.get(User, db_user.id)
    assert user_after.credit_micros_balance == balance_after_first


@pytest.mark.asyncio
async def test_relock_403_after_60s_window(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: relock after 60s window returns 403 with clear message."""
    unlocked_at = datetime.now(UTC) - timedelta(seconds=61)
    lead, contact = await _create_unlocked_contact(
        db_session, db_user, db_workspace, unlocked_at=unlocked_at
    )

    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/relock"
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"].lower()
    assert "window" in detail or "expired" in detail


@pytest.mark.asyncio
async def test_relock_403_when_accidental_relock_budget_exhausted(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: relock beyond 15% accidental-relock budget is rejected."""
    leads_and_contacts: list[tuple[Lead, VerifiedContact]] = []
    for _ in range(20):
        lead, contact = await _create_unlocked_contact(
            db_session, db_user, db_workspace
        )
        leads_and_contacts.append((lead, contact))

    # Burn through the 15% budget (3 relocks for 20 unlocked leads).
    for i in range(3):
        lead, contact = leads_and_contacts[i]
        resp = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/relock"
        )
        assert resp.status_code == 200

    # The 4th relock should exceed the 15% cap.
    lead, contact = leads_and_contacts[3]
    resp = await client_as_regular_user.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}/contacts/{contact.id}/relock"
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"].lower()
    assert "budget" in detail or "hết hạn mức" in detail


@pytest.mark.asyncio
async def test_relock_403_for_non_member(client_as_other, db_workspace):
    """P0: non-member cannot relock a contact in another workspace."""
    lead_id = uuid4()
    contact_id = uuid4()
    resp = await client_as_other.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead_id}/contacts/{contact_id}/relock"
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_concurrent_relock_does_not_double_refund(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: two concurrent relock requests produce exactly one refund event."""
    lead, contact = await _create_unlocked_contact(db_session, db_user, db_workspace)
    balance_before = db_user.credit_micros_balance

    url = (
        f"/api/v1/workspaces/{db_workspace.id}/leads/{lead.id}"
        f"/contacts/{contact.id}/relock"
    )
    results = await asyncio.gather(
        client_as_regular_user.post(url),
        client_as_regular_user.post(url),
    )
    assert all(r.status_code == 200 for r in results)

    events = (
        (
            await db_session.execute(
                select(BillingEvent).where(
                    BillingEvent.workspace_id == db_workspace.id,
                    BillingEvent.event_id == contact.id,
                    BillingEvent.event_type == "contact_relock",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    user_after = await db_session.get(User, db_user.id)
    assert user_after.credit_micros_balance == balance_before + 1500


@pytest.mark.asyncio
async def test_lead_list_masks_phone_and_includes_contact_metadata(
    client_as_regular_user, db_user, db_workspace, db_session
):
    """P0: LeadRead masks PII and exposes contact_id, is_unlocked, is_valid, consent_status."""
    lead, contact = await _create_unlocked_contact(db_session, db_user, db_workspace)
    contact.is_unlocked = False
    await db_session.flush()

    resp = await client_as_regular_user.get(
        f"/api/v1/workspaces/{db_workspace.id}/leads"
    )
    assert resp.status_code == 200
    body = resp.json()
    item = next((i for i in body["items"] if i["id"] == str(lead.id)), None)
    assert item is not None
    assert item["contact_id"] == str(contact.id)
    assert item["is_unlocked"] is False
    assert item["is_valid"] is True
    assert item["consent_status"] == "opted_in"
    assert item["phone"] == "0908***456"
    assert item["email"] == "a***@acme.com"
