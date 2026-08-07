"""Unit tests for canonical PII redaction helpers and persistence wiring."""

from __future__ import annotations

import hashlib
import types
from typing import Any

import pytest

from app.canonical.services.canonical_persist_service import (
    create_persist_outbox,
    record_merge_history,
)
from app.canonical.services.canonical_pii import (
    redact_canonical_data,
    redact_source_snapshot,
)


class _FakeSession:
    """Minimal async session stand-in for unit tests."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.info: dict[str, Any] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return None


def _fake_entity(entity_type: str = "bds_listing") -> Any:
    return types.SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        workspace_id=1,
        entity_type=entity_type,
        version=2,
    )


def test_bds_canonical_data_no_contact() -> None:
    """BDS PII is removed; phone_key becomes a one-way digest."""
    phone_key = "901234567"
    data = {
        "title": "Nhà phố Quận 7",
        "contact": "0xxx4567",
        "phone": "0901234567",
        "phone_key": phone_key,
        "owner_phone": "0901111111",
        "seller_phone": "0902222222",
        "seller_name": "Nguyễn Văn A",
        "owner_name": "Trần Thị B",
        "email_contact": "a@example.com",
        "address_key": "quan-7-tan-phong",
        "price_value": 5_000_000_000,
    }

    redacted = redact_canonical_data("bds_listing", data)

    assert "contact" not in redacted
    assert "phone" not in redacted
    assert "owner_phone" not in redacted
    assert "seller_phone" not in redacted
    assert "seller_name" not in redacted
    assert "owner_name" not in redacted
    assert "email_contact" not in redacted
    assert redacted["address_key"] == data["address_key"]
    assert redacted["price_value"] == data["price_value"]
    assert redacted["phone_key"] == hashlib.sha256(
        phone_key.encode("utf-8")
    ).hexdigest()


def test_bds_source_snapshot_drops_matching_keys() -> None:
    """Source snapshots keep no phone-derived keys at all."""
    snapshot = redact_source_snapshot(
        "bds_listing",
        {
            "title": "Nhà",
            "contact": "0xxx1234",
            "phone_key": "901234567",
            "address_key": "quan-7",
        },
    )
    assert "contact" not in snapshot
    assert "phone_key" not in snapshot
    assert "address_key" not in snapshot
    assert snapshot["title"] == "Nhà"


def test_jobs_canonical_data_no_jd() -> None:
    """Job description/requirement are masked and contact/email removed."""
    raw_jd = "Contact Nguyễn Văn A at 0901234567 or email test@example.com."
    data = {
        "title": "Senior Data Engineer",
        "company": "ACB",
        "job_description": raw_jd,
        "job_requirement": "Call 0901234567.",
        "contact": "0901234567",
        "email": "test@example.com",
    }

    redacted = redact_canonical_data("vn_job", data)

    assert "contact" not in redacted
    assert "email" not in redacted
    assert "0901234567" not in redacted["job_description"]
    assert "test@example.com" not in redacted["job_description"]
    assert "Nguyễn Văn A" not in redacted["job_description"]
    assert "0901234567" not in redacted["job_requirement"]
    assert redacted["title"] == data["title"]
    assert redacted["company"] == data["company"]


@pytest.mark.asyncio
async def test_merge_history_no_pii() -> None:
    """record_merge_history stores redacted canonical data."""
    session = _FakeSession()
    entity = _fake_entity("bds_listing")
    previous_data = {"phone_key": "901234567"}
    new_data = {
        "contact": "0xxx1234",
        "phone_key": "901234567",
    }

    history = await record_merge_history(
        session,
        entity=entity,
        previous_data=previous_data,
        new_data=new_data,
        operation="merge",
    )

    assert "contact" not in history.new_data
    assert history.new_data["phone_key"] == hashlib.sha256(
        b"901234567"
    ).hexdigest()
    assert history.previous_data["phone_key"] == hashlib.sha256(
        b"901234567"
    ).hexdigest()


@pytest.mark.asyncio
async def test_outbox_no_pii() -> None:
    """create_persist_outbox stores a redacted payload."""
    session = _FakeSession()
    payload = {
        "workspace_id": 1,
        "entity_type": "bds_listing",
        "fingerprint": "fp-1",
        "data": {
            "contact": "0xxx1234",
            "phone_key": "901234567",
            "title": "Nhà",
        },
    }

    outbox = await create_persist_outbox(
        session,
        workspace_id=1,
        entity_type="bds_listing",
        payload=payload,
    )

    assert outbox.payload["data"]["phone_key"] == hashlib.sha256(
        b"901234567"
    ).hexdigest()
    assert "contact" not in outbox.payload["data"]
    assert outbox.payload["data"]["title"] == "Nhà"
