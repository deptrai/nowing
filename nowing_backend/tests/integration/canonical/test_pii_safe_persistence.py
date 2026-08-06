"""Integration tests for PII-safe canonical persistence across domains."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import (
    create_persist_outbox,
    upsert_canonical_entity,
)
from app.db import (
    CanonicalEntitySource,
    CanonicalMergeHistory,
    CanonicalPersistOutbox,
    Workspace,
)

pytestmark = [pytest.mark.integration, pytest.mark.canonical]


def _no_op_apply_async(*args: object, **kwargs: object) -> None:
    """Prevent Celery broker round-trips in tests."""
    return None


async def test_bds_canonical_data_no_contact(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    """A BDS listing with PII is persisted with phone_key digested and PII dropped."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    phone_key = "901234567"
    raw_phone = "0901234567"
    data = {
        "title": "Nhà phố Quận 7",
        "contact": "0xxx4567",
        "phone": raw_phone,
        "phone_key": phone_key,
        "owner_phone": "0901111111",
        "seller_phone": "0902222222",
        "seller_name": "Nguyễn Văn A",
        "owner_name": "Trần Thị B",
        "address_key": "quan-7-tan-phong",
        "price_value": 5_000_000_000,
    }

    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="bds_listing",
        fingerprint="bds-pii-1",
        title="Nhà phố Quận 7",
        data=data,
        search_text="nha pho quan 7",
        source_name="batdongsan",
        source_record_id="bds-1",
        source_snapshot={**data, "source_title": "Nhà phố Quận 7"},
    )

    # Canonical data must be PII-free except for the one-way digest.
    canonical = entity.canonical_data
    assert "contact" not in canonical
    assert "phone" not in canonical
    assert "owner_phone" not in canonical
    assert "seller_phone" not in canonical
    assert "seller_name" not in canonical
    assert "owner_name" not in canonical
    assert canonical["phone_key"] == hashlib.sha256(
        phone_key.encode("utf-8")
    ).hexdigest()
    assert canonical["address_key"] == data["address_key"]

    # Source snapshot must not retain any PII-derived matching keys.
    source = await db_session.scalar(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.canonical_entity_id == entity.id
        )
    )
    assert source is not None
    snapshot = source.source_snapshot
    assert "contact" not in snapshot
    assert "phone" not in snapshot
    assert "phone_key" not in snapshot
    assert "address_key" not in snapshot
    assert raw_phone not in str(snapshot)
    assert "Nguyễn Văn A" not in str(snapshot)


async def test_jobs_canonical_data_no_jd(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    """A job listing with PII in JD text is redacted before storage."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    raw_jd = "Contact Nguyễn Văn A at 0901234567 or email test@example.com."
    data = {
        "title": "Senior Data Engineer",
        "company": "ACB",
        "job_description": raw_jd,
        "job_requirement": "Must have 3 years of Python experience.",
        "contact": "0901234567",
        "email": "test@example.com",
    }

    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_job",
        fingerprint="job-pii-1",
        title="Senior Data Engineer",
        data=data,
        search_text="senior data engineer acb",
        source_name="vietnamworks",
        source_record_id="vw-1",
        source_snapshot={**data, "source_url": "https://vietnamworks.com/1"},
    )

    canonical = entity.canonical_data
    assert "contact" not in canonical
    assert "email" not in canonical
    assert "0901234567" not in canonical["job_description"]
    assert "test@example.com" not in canonical["job_description"]
    assert "Nguyễn Văn A" not in canonical["job_description"]
    assert raw_jd != canonical["job_description"]
    assert canonical["title"] == data["title"]

    source = await db_session.scalar(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.canonical_entity_id == entity.id
        )
    )
    assert source is not None
    snapshot = source.source_snapshot
    assert "contact" not in snapshot
    assert "email" not in snapshot
    assert "0901234567" not in str(snapshot)
    assert "test@example.com" not in str(snapshot)
    assert "Nguyễn Văn A" not in str(snapshot)


async def test_merge_history_no_pii(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    """Merge history rows never contain raw PII values."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    phone_key = "901234567"
    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="bds_listing",
        fingerprint="bds-pii-history",
        title="Nhà",
        data={
            "phone_key": phone_key,
            "contact": "0xxx1234",
            "price_value": 1_000_000_000,
        },
        search_text="nha",
        source_name="batdongsan",
        source_record_id="bds-h1",
    )

    # Trigger a merge with a second source.
    await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="bds_listing",
        fingerprint="bds-pii-history",
        title="Nhà mới",
        data={
            "phone_key": phone_key,
            "contact": "0xxx1234",
            "price_value": 1_100_000_000,
        },
        search_text="nha moi",
        source_name="chotot_bds",
        source_record_id="bds-h2",
    )

    histories = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    assert len(histories) == 2

    for history in histories:
        for data in (history.previous_data, history.new_data):
            assert "contact" not in data
            if data.get("phone_key"):
                assert data["phone_key"] == hashlib.sha256(
                    phone_key.encode("utf-8")
                ).hexdigest()


async def test_outbox_no_pii(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """Persist outbox payloads are redacted before storage."""
    phone_key = "901234567"
    payload = {
        "workspace_id": db_workspace.id,
        "entity_type": "bds_listing",
        "fingerprint": "bds-pii-outbox",
        "data": {
            "contact": "0xxx1234",
            "phone": "0901234567",
            "phone_key": phone_key,
            "seller_name": "Nguyễn Văn A",
            "title": "Nhà",
        },
    }

    outbox = await create_persist_outbox(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="bds_listing",
        payload=payload,
    )

    stored = await db_session.scalar(
        select(CanonicalPersistOutbox).where(CanonicalPersistOutbox.id == outbox.id)
    )
    assert stored is not None
    payload_data = stored.payload["data"]
    assert "contact" not in payload_data
    assert "phone" not in payload_data
    assert "seller_name" not in payload_data
    assert payload_data["phone_key"] == hashlib.sha256(
        phone_key.encode("utf-8")
    ).hexdigest()
    assert payload_data["title"] == "Nhà"
