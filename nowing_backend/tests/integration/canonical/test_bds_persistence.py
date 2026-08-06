"""Integration tests for BDS aggregator persistence to canonical storage."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    CanonicalEntity,
    CanonicalEntitySource,
    CanonicalPersistOutbox,
    Workspace,
)
from app.services.bds_aggregator.orchestrator import aggregate
from app.services.bds_aggregator.schemas import VnBdsAggregateInput

pytestmark = [pytest.mark.integration, pytest.mark.canonical]


def _no_op_apply_async(*args, **kwargs) -> None:
    """Prevent Celery broker round-trips in tests."""
    return None


def _make_fake_source_executor(
    source: str,
    source_record_id: str,
    phone: str = "0901234567",
) -> callable:
    """Return a fake source scraper that returns one raw listing."""

    async def _execute(child_dict: dict) -> dict:
        return {
            "items": [
                {
                    "id": source_record_id,
                    "title": "Nhà phố Quận 7",
                    "price": "5 tỷ",
                    "area": "100m2",
                    "district": "Quận 7",
                    "ward": "Phường Tân Phong",
                    "location": "Đường Nguyễn Thị Thập",
                    "city": "Hồ Chí Minh",
                    "phone": phone,
                }
            ],
            "cost_micros": 3500,
            "degraded": False,
        }

    return _execute


async def test_aggregate_persists_bds_listing(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
):
    """aggregate() with a workspace persists a BĐS listing and source."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh",
        sources=["batdongsan"],
        max_items_per_source=1,
    )
    source_executors = {
        "batdongsan": _make_fake_source_executor("batdongsan", "bds-123"),
    }

    output = await aggregate(
        payload,
        source_executors=source_executors,
        workspace_id=db_workspace.id,
        session=db_session,
    )

    assert output.persistence_status == "ok"
    assert output.persistence_message is None
    assert output.total_items == 1

    listing = output.items[0]
    assert listing.canonical_id

    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "bds_listing",
            CanonicalEntity.fingerprint == listing.canonical_id,
        )
    )
    assert entity is not None
    assert entity.fingerprint == listing.canonical_id
    assert entity.source_count == 1
    assert entity.search_text

    source = await db_session.scalar(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.canonical_entity_id == entity.id,
            CanonicalEntitySource.source_name == "batdongsan",
        )
    )
    assert source is not None
    assert source.source_record_id == "bds-123"
    # Source snapshot must be redacted: no contact or phone-derived keys.
    snapshot = source.source_snapshot
    assert "contact" not in snapshot
    assert "phone_key" not in snapshot
    assert "phone" not in snapshot
    assert "address_key" not in snapshot


async def test_aggregate_persistence_is_idempotent(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
):
    """Calling aggregate twice with the same source does not duplicate rows."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh",
        sources=["batdongsan"],
        max_items_per_source=1,
    )
    source_executors = {
        "batdongsan": _make_fake_source_executor("batdongsan", "bds-123"),
    }

    for _ in range(2):
        output = await aggregate(
            payload,
            source_executors=source_executors,
            workspace_id=db_workspace.id,
            session=db_session,
        )
        assert output.persistence_status == "ok"

    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "bds_listing",
        )
    )
    assert entity is not None
    assert entity.source_count == 1

    source_count = (
        (
            await db_session.execute(
                select(CanonicalEntitySource).where(
                    CanonicalEntitySource.canonical_entity_id == entity.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(source_count) == 1


async def test_aggregate_persists_multiple_sources(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
):
    """A merged listing with two sources gets source_count=2 from the DB."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh",
        sources=["batdongsan", "chotot_bds"],
        max_items_per_source=1,
    )
    source_executors = {
        "batdongsan": _make_fake_source_executor("batdongsan", "bds-123"),
        "chotot_bds": _make_fake_source_executor("chotot_bds", "ct-456"),
    }

    output = await aggregate(
        payload,
        source_executors=source_executors,
        workspace_id=db_workspace.id,
        session=db_session,
    )

    assert output.persistence_status == "ok"
    assert output.total_items == 1
    assert output.items[0].source_count == 2

    entity = await db_session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.workspace_id == db_workspace.id,
            CanonicalEntity.entity_type == "bds_listing",
        )
    )
    assert entity is not None
    assert entity.source_count == 2


async def test_aggregate_failure_stages_outbox(
    db_session: AsyncSession,
    db_workspace: Workspace,
    monkeypatch,
):
    """Persistence failure returns results and stages a durable outbox row."""
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )

    async def _failing_upsert(*args, **kwargs) -> None:
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setattr(
        "app.services.bds_aggregator.orchestrator.upsert_canonical_entity",
        _failing_upsert,
    )

    payload = VnBdsAggregateInput(
        city="Hồ Chí Minh",
        sources=["batdongsan"],
        max_items_per_source=1,
    )
    source_executors = {
        "batdongsan": _make_fake_source_executor("batdongsan", "bds-123"),
    }

    output = await aggregate(
        payload,
        source_executors=source_executors,
        workspace_id=db_workspace.id,
        session=db_session,
    )

    assert output.persistence_status == "failed"
    assert output.persistence_message is not None
    assert output.total_items == 1

    outbox = await db_session.scalar(
        select(CanonicalPersistOutbox).where(
            CanonicalPersistOutbox.workspace_id == db_workspace.id,
            CanonicalPersistOutbox.entity_type == "bds_listing",
        )
    )
    assert outbox is not None
    assert outbox.status == "pending"
    assert "simulated persistence failure" in (outbox.error or "")
