"""Merge history records versions and source sets for canonical entities."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.db import CanonicalMergeHistory, Workspace

pytestmark = [pytest.mark.integration, pytest.mark.canonical]


def _no_op_apply_async(*args: Any, **kwargs: Any) -> None:
    """Prevent Celery broker round-trips in tests."""
    return None


@pytest.fixture(autouse=True)
def _patch_backfill(monkeypatch):
    monkeypatch.setattr(
        "app.canonical.services.canonical_persist_service.backfill_canonical_embedding.apply_async",
        _no_op_apply_async,
    )


async def test_merge_history_records_versions_and_source_sets(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Each merge is audited with before/after versions and source sets."""
    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="mh-f1",
        title="Nhà phố Quận 7",
        data={"price_value": 5_000_000_000, "area_value": 100.0},
        search_text="nha pho quan 7 5 ty 100m2",
        source_name="batdongsan",
        source_record_id="src-1",
        source_snapshot={"title": "Nhà phố Quận 7"},
        actor="system",
    )

    assert entity.version == 1
    history_rows = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    assert len(history_rows) == 1
    create_history = history_rows[0]
    assert create_history.operation == "create"
    assert create_history.previous_version == 0
    assert create_history.new_version == 1
    assert create_history.previous_source_ids == []
    assert create_history.new_source_ids == [
        {"source_name": "batdongsan", "source_record_id": "src-1"}
    ]

    # Second upsert merges and changes the source set.
    merged = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="mh-f1",
        title="Nhà phố Quận 7 - mới",
        data={"price_value": 5_200_000_000, "area_value": 100.0},
        search_text="nha pho quan 7 5.2 ty 100m2",
        source_name="muaban",
        source_record_id="src-2",
        source_snapshot={"title": "Nhà phố Quận 7"},
        actor="system",
    )

    assert merged.id == entity.id
    assert merged.version == 2
    assert merged.source_count == 2

    history_rows = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    assert len(history_rows) == 2
    merge_history = history_rows[1]
    assert merge_history.operation == "merge"
    assert merge_history.previous_version == 1
    assert merge_history.new_version == 2
    assert merge_history.previous_source_ids == [
        {"source_name": "batdongsan", "source_record_id": "src-1"}
    ]
    assert merge_history.new_source_ids == [
        {"source_name": "muaban", "source_record_id": "src-2"},
        {"source_name": "batdongsan", "source_record_id": "src-1"},
    ]
