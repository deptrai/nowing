"""Revert and manual conflict resolution for canonical entities."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import (
    RevertNotPossibleError,
    resolve_canonical_conflict,
    revert_canonical_entity,
    upsert_canonical_entity,
)
from app.db import CanonicalEntity, CanonicalMergeHistory, Workspace

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


async def _seed_entity(
    db_session: AsyncSession, workspace: Workspace
) -> CanonicalEntity:
    await upsert_canonical_entity(
        db_session,
        workspace_id=workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="revert-f1",
        title="Nhà phố Quận 7",
        data={"price_value": 5_000_000_000, "area_value": 100.0},
        search_text="nha pho quan 7",
        source_name="batdongsan",
        source_record_id="r1",
        actor="system",
    )
    merged = await upsert_canonical_entity(
        db_session,
        workspace_id=workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="revert-f1",
        title="Nhà phố Quận 7 - mới",
        data={"price_value": 5_200_000_000, "area_value": 100.0},
        search_text="nha pho quan 7 moi",
        source_name="muaban",
        source_record_id="r2",
        actor="system",
    )
    return merged


async def test_revert_restores_previous_data_and_records_new_history(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Reverting to a history entry restores data and adds a revert audit row."""
    entity = await _seed_entity(db_session, db_workspace)
    assert entity.version == 2
    assert entity.canonical_data == {"price_value": 5_200_000_000, "area_value": 100.0}

    # Find the merge (second) history entry to revert to; it holds the v1 data.
    histories = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    assert len(histories) == 2
    target_history_id = histories[1].id

    reverted = await revert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_id=entity.id,
        target_history_id=target_history_id,
        actor="admin-1",
    )

    assert reverted.version == 3
    # Reverting to the merge row restores its previous_data (v1 data).
    assert reverted.canonical_data == {
        "price_value": 5_000_000_000,
        "area_value": 100.0,
    }
    assert reverted.embedding_status == "pending"

    histories = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    assert len(histories) == 3
    revert_history = histories[2]
    assert revert_history.operation == "revert"
    assert revert_history.previous_version == 2
    assert revert_history.new_version == 3
    assert revert_history.previous_data == {
        "price_value": 5_200_000_000,
        "area_value": 100.0,
    }
    assert revert_history.new_data == {
        "price_value": 5_000_000_000,
        "area_value": 100.0,
    }
    assert revert_history.actor == "admin-1"
    assert revert_history.method == "revert_to_history"


async def test_revert_fails_when_entity_has_newer_version(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Revert must not overwrite changes committed after the selected history."""
    entity = await _seed_entity(db_session, db_workspace)
    histories = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    target_history_id = histories[0].id

    # Simulate an intervening change by bumping the version manually.
    entity.canonical_data = {"price_value": 5_300_000_000}
    entity.version = 3
    await db_session.flush()

    with pytest.raises(RevertNotPossibleError):
        await revert_canonical_entity(
            db_session,
            workspace_id=db_workspace.id,
            entity_id=entity.id,
            target_history_id=target_history_id,
        )


async def test_resolve_conflict_updates_data_and_clears_matching_conflict(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Manual conflict resolution writes a field and records a resolve history row."""
    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="resolve-f1",
        title="Conflict listing",
        data={"price_value": 5_000_000_000},
        search_text="conflict",
        source_name="batdongsan",
        source_record_id="c1",
        conflict_flags=[{"type": "price_conflict", "field": "price_value"}],
    )
    assert entity.version == 1

    resolved = await resolve_canonical_conflict(
        db_session,
        workspace_id=db_workspace.id,
        entity_id=entity.id,
        field="price_value",
        value=5_150_000_000,
        actor="admin-2",
    )

    assert resolved.version == 2
    assert resolved.canonical_data == {"price_value": 5_150_000_000}
    assert resolved.conflict_flags == []
    assert resolved.embedding_status == "pending"

    histories = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    assert len(histories) == 2
    resolve_history = histories[1]
    assert resolve_history.operation == "resolve"
    assert resolve_history.previous_version == 1
    assert resolve_history.new_version == 2
    assert resolve_history.new_data == {"price_value": 5_150_000_000}
    assert resolve_history.conflicts == [
        {"type": "price_conflict", "field": "price_value"}
    ]
    assert resolve_history.actor == "admin-2"


async def test_resolve_conflict_keeps_unrelated_conflicts(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Resolving one field should not remove unrelated conflict flags."""
    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="resolve-f2",
        title="Multiple conflicts",
        data={"price_value": 5_000_000_000, "area_value": 50.0},
        search_text="multi conflict",
        source_name="batdongsan",
        source_record_id="c2",
        conflict_flags=[
            {"type": "price_conflict", "field": "price_value"},
            {"type": "area_conflict", "field": "area_value"},
        ],
    )

    await resolve_canonical_conflict(
        db_session,
        workspace_id=db_workspace.id,
        entity_id=entity.id,
        field="price_value",
        value=5_100_000_000,
    )

    await db_session.refresh(entity)
    assert entity.conflict_flags == [{"type": "area_conflict", "field": "area_value"}]
