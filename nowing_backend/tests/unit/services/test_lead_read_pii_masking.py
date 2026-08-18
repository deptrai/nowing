"""Red-phase ATDD unit tests for LeadRead PII masking (Story 26.5)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.routes.leads_routes import _map_lead_to_read

pytestmark = [
    pytest.mark.unit,
]


def test_lead_read_masks_pii_when_contact_is_locked() -> None:
    """P0: LeadRead masks phone, email, name when is_unlocked=False."""
    lead = _make_lead()
    contact = _make_contact({"is_unlocked": False})
    lead.verified_contacts = [contact]

    result = _map_lead_to_read(lead)

    assert result.contact_id == contact.id
    assert result.is_unlocked is False
    assert result.is_valid is True
    assert result.consent_status == "opted_in"
    assert result.phone == "0908***456"
    assert result.email == "a***@acme.com"
    assert result.name == "N***n"


def test_lead_read_decrypts_pii_when_contact_is_unlocked() -> None:
    """P0: LeadRead returns decrypted phone, email, name when is_unlocked=True."""
    lead = _make_lead()
    contact = _make_contact({"is_unlocked": True})
    lead.verified_contacts = [contact]

    result = _map_lead_to_read(lead)

    assert result.is_unlocked is True
    assert result.phone == "0908123456"
    assert result.email == "alice@acme.com"
    assert result.name == "Nguyễn Văn"


def test_lead_read_shows_dnc_or_invalid_badge() -> None:
    """P0: locked contact with withdrawn consent or invalid is rendered safely."""
    lead = _make_lead()
    contact = _make_contact(
        {
            "is_unlocked": False,
            "is_valid": False,
            "consent_status": "withdrawn",
        }
    )
    lead.verified_contacts = [contact]

    result = _map_lead_to_read(lead)

    assert result.is_unlocked is False
    assert result.is_valid is False
    assert result.consent_status == "withdrawn"
    assert result.phone == "0908***456"


def test_lead_read_handles_lead_without_verified_contacts() -> None:
    """P1: Lead without contacts leaves contact fields empty."""
    lead = _make_lead()
    lead.verified_contacts = []

    result = _map_lead_to_read(lead)

    assert result.contact_id is None
    assert result.is_unlocked is False
    assert result.phone is None
    assert result.email is None
    assert result.name is None


def _make_lead(overrides: dict | None = None) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "workspace_id": 1,
        "company_name": "Acme",
        "source": "test",
        "source_url": None,
        "domain": "acme.com",
        "industry": None,
        "company_size": None,
        "location": None,
        "tech_stack": [],
        "fit_score": None,
        "intent_score": None,
        "composite_score": None,
        "status": "new",
        "stage_id": None,
        "assigned_to_user_id": None,
        "version": 1,
        "intent": None,
        "name": None,
        "email": None,
        "phone": None,
        "price_estimate": None,
        "content_snippet": None,
        "author": None,
        "enriched": False,
        "tax_id": None,
        "legal_representative": None,
        "charter_capital_vnd": None,
        "company_status": None,
        "is_zalo_active": False,
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_contact(overrides: dict | None = None) -> SimpleNamespace:
    defaults = {
        "id": uuid4(),
        "workspace_id": 1,
        "lead_id": uuid4(),
        "name": "Nguyễn Văn",
        "title": "CEO",
        "email": "alice@acme.com",
        "phone": "0908123456",
        "is_unlocked": False,
        "is_valid": True,
        "consent_status": "opted_in",
        "value_hmac": "contact-hmac",
        "phone_hmac": "phone-hmac",
        "email_hmac": "email-hmac",
    }
    if overrides:
        defaults.update(overrides)
    return SimpleNamespace(**defaults)
