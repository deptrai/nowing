"""Service-level integration tests for PII opt-out (Story 26.4)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import BillingEvent, Lead, User, VerifiedContact, WorkspaceDncRecord
from app.lead_intelligence.dnc.normalizer import (
    hash_phone_hmac,
    normalize_email,
    normalize_phone_e164,
)
from app.services.pii.opt_out_service import OptOutService
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

pytestmark = [pytest.mark.integration]


def _encrypt(value: str) -> str:
    return VerifiedContactEncryption().encrypt(value)


def _phone_hash(phone: str) -> str:
    return hash_phone_hmac(normalize_phone_e164(phone))


def _email_hash(email: str) -> str:
    return hash_phone_hmac(normalize_email(email))


@pytest.mark.asyncio
async def test_opt_out_service_finds_contact_by_phone_hmac(
    db_session, db_user, db_workspace
):
    """Pattern 6: blind index lookup works without decrypting entire table."""
    db_user.credit_micros_balance = 10_000
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
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    service = OptOutService(db_session)
    result = await service.process_opt_out(
        workspace_id=db_workspace.id,
        record_type="phone",
        value=phone,
        actor_user_id=db_user.id,
        ip_address="127.0.0.1",
    )

    assert result.purged_contact_count == 1
    assert result.dnc_record_id is not None

    dnc_record = (
        await db_session.execute(
            select(WorkspaceDncRecord).where(
                WorkspaceDncRecord.workspace_id == db_workspace.id,
                WorkspaceDncRecord.record_type == "phone",
            )
        )
    ).scalar_one_or_none()
    assert dnc_record is not None
    assert dnc_record.value == normalize_phone_e164(phone)


@pytest.mark.asyncio
async def test_opt_out_service_finds_contact_by_email_hmac(
    db_session, db_user, db_workspace
):
    """Pattern 6: email blind index also matches."""
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
        phone=_encrypt(phone),
        email=_encrypt(email),
        phone_hmac=_phone_hash(phone),
        email_hmac=_email_hash(email),
        value_hmac="contact-hmac",
        is_unlocked=False,
        pii_access_audit_logs=[],
    )
    db_session.add(contact)
    await db_session.flush()

    service = OptOutService(db_session)
    result = await service.process_opt_out(
        workspace_id=db_workspace.id,
        record_type="email",
        value=email,
        actor_user_id=db_user.id,
    )

    assert result.purged_contact_count == 1


@pytest.mark.asyncio
async def test_opt_out_service_refunds_exactly_1500_micros(
    db_session, db_user, db_workspace
):
    """Pattern 4/6: refund amount and wallet math."""
    db_user.credit_micros_balance = 10_000
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
        )
    )
    await db_session.flush()

    service = OptOutService(db_session)
    result = await service.process_opt_out(
        workspace_id=db_workspace.id,
        record_type="phone",
        value=phone,
        actor_user_id=db_user.id,
    )

    assert result.refunded_micros == 1500

    user = await db_session.get(User, db_user.id)
    assert user.credit_micros_balance == 11_500

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


@pytest.mark.asyncio
async def test_opt_out_service_rollback_on_credit_failure(
    db_session, db_user, db_workspace, monkeypatch
):
    """Pattern 2/6: partial work must not persist if credit refund fails."""
    db_user.credit_micros_balance = 10_000
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
        )
    )
    await db_session.flush()

    monkeypatch.setattr(
        "app.services.pii.opt_out_service.OptOutService._refund_credit",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("credit service down")),
    )

    service = OptOutService(db_session)
    with pytest.raises(RuntimeError, match="credit service down"):
        await service.process_opt_out(
            workspace_id=db_workspace.id,
            record_type="phone",
            value=phone,
            actor_user_id=db_user.id,
        )

    # Everything rolled back because db_session savepoint is rolled back automatically.
    user = await db_session.get(User, db_user.id)
    assert user.credit_micros_balance == 10_000
    assert contact.is_unlocked is True
