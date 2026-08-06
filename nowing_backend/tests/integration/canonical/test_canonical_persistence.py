"""Integration tests for canonical persistence, tenancy and provenance."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import (
    create_persist_outbox,
    upsert_canonical_entity,
)
from app.canonical.tenant_context import set_canonical_workspace_id
from app.db import (
    CanonicalEntitySource,
    CanonicalMergeHistory,
    CanonicalPersistOutbox,
    User,
    Workspace,
)

pytestmark = [pytest.mark.integration, pytest.mark.canonical]

_MIGRATION_193_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "193_add_canonical_entities.py"
)


def _load_migration_193():
    spec = importlib.util.spec_from_file_location("_migration_193", _MIGRATION_193_PATH)
    assert spec and spec.loader, "could not load migration 193 spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration_upgrade(sync_conn, module) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    ctx = MigrationContext.configure(connection=sync_conn)
    with Operations.context(ctx):
        module.upgrade()


def _run_migration_downgrade(sync_conn, module) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    ctx = MigrationContext.configure(connection=sync_conn)
    with Operations.context(ctx):
        module.downgrade()


async def _table_exists(session: AsyncSession, table: str) -> bool:
    result = await session.execute(text("SELECT to_regclass(:t)"), {"t": table})
    return result.scalar() is not None


async def _index_exists(session: AsyncSession, table: str, index: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :i"),
        {"t": table, "i": index},
    )
    return result.scalar() == 1


async def _rls_enabled(session: AsyncSession, table: str) -> bool:
    result = await session.execute(
        text(
            "SELECT relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname = :t"
        ),
        {"t": table},
    )
    row = result.first()
    return bool(row and row[0]) and bool(row and row[1])


async def _drop_canonical_tables(session: AsyncSession) -> None:
    for table in (
        "canonical_persist_outbox",
        "canonical_merge_history",
        "canonical_entity_sources",
        "canonical_entities",
    ):
        await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
    await session.flush()


@pytest.fixture
async def another_workspace(db_session: AsyncSession, db_user: User) -> Workspace:
    space = Workspace(name="Other Space", user_id=db_user.id)
    db_session.add(space)
    await db_session.flush()
    return space


async def test_migration_upgrade_and_downgrade(db_session: AsyncSession):
    """Migration 193 creates tables, indexes and RLS; downgrade removes them."""
    module = _load_migration_193()
    await _drop_canonical_tables(db_session)

    conn = await db_session.connection()
    await conn.run_sync(lambda sc: _run_migration_upgrade(sc, module))

    for table in (
        "canonical_entities",
        "canonical_entity_sources",
        "canonical_merge_history",
        "canonical_persist_outbox",
    ):
        assert await _table_exists(db_session, table)

    assert await _index_exists(
        db_session,
        "canonical_entities",
        "uq_canonical_entities_workspace_type_fingerprint",
    )
    assert await _index_exists(
        db_session,
        "canonical_entities",
        "ix_canonical_entities_workspace_type_last_seen",
    )
    assert await _index_exists(
        db_session, "canonical_entities", "ix_canonical_entities_search_text"
    )
    assert await _index_exists(
        db_session, "canonical_entities", "ix_canonical_entities_embedding"
    )
    assert await _index_exists(
        db_session,
        "canonical_entity_sources",
        "uq_canonical_entity_sources_workspace_type_source_record",
    )
    assert await _index_exists(
        db_session,
        "canonical_merge_history",
        "ix_canonical_merge_history_entity_created",
    )
    assert await _index_exists(
        db_session,
        "canonical_persist_outbox",
        "ix_canonical_persist_outbox_status_next_attempt",
    )

    for table in (
        "canonical_entities",
        "canonical_entity_sources",
        "canonical_merge_history",
        "canonical_persist_outbox",
    ):
        assert await _rls_enabled(db_session, table)

    await conn.run_sync(lambda sc: _run_migration_downgrade(sc, module))

    for table in (
        "canonical_persist_outbox",
        "canonical_merge_history",
        "canonical_entity_sources",
        "canonical_entities",
    ):
        assert not await _table_exists(db_session, table)


async def test_upsert_and_version_merge(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Upsert creates a canonical entity and merges on repeated fingerprint."""
    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="f1",
        title="Nhà phố Quận 7",
        data={"price_value": 5_000_000_000, "area_value": 100.0},
        search_text="nha pho quan 7 5 ty 100m2",
        source_name="batdongsan",
        source_record_id="12345",
        source_snapshot={"title": "Nhà phố Quận 7"},
        source_url="https://example.com/1",
        source_fingerprint="src-f1",
        confidence_score=0.85,
        conflict_flags=[{"type": "price_conflict", "reason": "ok"}],
    )

    assert entity.version == 1
    assert entity.source_count == 1
    assert entity.embedding_status == "pending"

    history = await db_session.scalar(
        select(CanonicalMergeHistory).where(
            CanonicalMergeHistory.canonical_entity_id == entity.id
        )
    )
    assert history is not None
    assert history.operation == "create"
    assert history.previous_version == 0
    assert history.new_version == 1

    # Second upsert with same fingerprint merges and bumps version.
    merged = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="f1",
        title="Nhà phố Quận 7 - mới",
        data={"price_value": 5_200_000_000, "area_value": 100.0},
        search_text="nha pho quan 7 5.2 ty 100m2",
        source_name="muaban",
        source_record_id="67890",
        source_snapshot={"title": "Nhà phố Quận 7"},
        source_url="https://example.com/2",
        source_fingerprint="src-f2",
        confidence_score=0.9,
        conflict_flags=[],
    )

    assert merged.id == entity.id
    assert merged.version == 2
    assert merged.source_count == 2
    assert merged.embedding_status == "pending"

    history_rows = (
        await db_session.scalars(
            select(CanonicalMergeHistory)
            .where(CanonicalMergeHistory.canonical_entity_id == entity.id)
            .order_by(CanonicalMergeHistory.created_at)
        )
    ).all()
    assert len(history_rows) == 2
    assert history_rows[1].operation == "merge"
    assert history_rows[1].previous_version == 1
    assert history_rows[1].new_version == 2


async def test_source_uniqueness_constraint(
    db_session: AsyncSession, db_workspace: Workspace
):
    """The same source record cannot back two entities in the same workspace/domain."""
    await set_canonical_workspace_id(db_session, db_workspace.id)

    e1 = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="f2",
        title="A",
        data={},
        search_text="a",
        source_name="batdongsan",
        source_record_id="same-id",
    )

    # Same source record, new fingerprint: the source row moves to the new entity.
    e2 = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="f3",
        title="B",
        data={},
        search_text="b",
        source_name="batdongsan",
        source_record_id="same-id",
    )

    source = await db_session.scalar(
        select(CanonicalEntitySource).where(
            CanonicalEntitySource.source_record_id == "same-id"
        )
    )
    assert source is not None
    assert source.canonical_entity_id == e2.id

    # e1 lost its only source.
    await db_session.refresh(e1)
    assert e1.source_count == 0


async def test_persist_outbox(db_session: AsyncSession, db_workspace: Workspace):
    """Outbox rows are tenant-scoped and retrievable by status/attempt index."""
    outbox = await create_persist_outbox(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        payload={"fingerprint": "f4", "title": "X"},
        error="retryable",
        next_attempt_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    assert outbox.status == "pending"
    assert outbox.retry_count == 0

    row = await db_session.scalar(
        select(CanonicalPersistOutbox).where(
            CanonicalPersistOutbox.status == "pending",
            CanonicalPersistOutbox.workspace_id == db_workspace.id,
        )
    )
    assert row is not None
    assert row.id == outbox.id


async def test_rls_fails_closed_across_workspaces(
    db_session: AsyncSession,
    db_workspace: Workspace,
    another_workspace: Workspace,
):
    """A non-owner role with one workspace context cannot read another workspace."""
    # create_all-bootstrapped tables do not include RLS, so replay the migration.
    module = _load_migration_193()
    await _drop_canonical_tables(db_session)
    conn = await db_session.connection()
    await conn.run_sync(lambda sc: _run_migration_upgrade(sc, module))

    await set_canonical_workspace_id(db_session, db_workspace.id)

    _ = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="rls-f1",
        title="Workspace A",
        data={},
        search_text="a",
        source_name="batdongsan",
        source_record_id="100",
    )

    # Create a second entity in another workspace.
    await set_canonical_workspace_id(db_session, another_workspace.id)
    _ = await upsert_canonical_entity(
        db_session,
        workspace_id=another_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="rls-f1",
        title="Workspace B",
        data={},
        search_text="b",
        source_name="batdongsan",
        source_record_id="100",
    )

    # Use raw SQL as a non-owner app role.
    await db_session.execute(
        text(
            "DO $$\n"
            "BEGIN\n"
            "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'test_app_user') THEN\n"
            "    CREATE ROLE test_app_user NOLOGIN NOBYPASSRLS;\n"
            "  END IF;\n"
            "END\n"
            "$$;"
        )
    )
    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO test_app_user"))
    for table in (
        "canonical_entities",
        "canonical_entity_sources",
        "canonical_merge_history",
        "canonical_persist_outbox",
    ):
        await db_session.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO test_app_user")
        )
    await db_session.execute(text("SET LOCAL ROLE test_app_user"))

    # With workspace A context, the app role sees only workspace A rows.
    await db_session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": str(db_workspace.id)},
    )
    rows = (
        await db_session.execute(
            text(
                "SELECT canonical_title FROM canonical_entities WHERE entity_type = 'vn_bds.listing'"
            )
        )
    ).fetchall()
    assert [r[0] for r in rows] == ["Workspace A"]

    # Switch to workspace B context and cross-check using the same connection.
    await db_session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": str(another_workspace.id)},
    )
    rows = (
        await db_session.execute(
            text(
                "SELECT canonical_title FROM canonical_entities WHERE entity_type = 'vn_bds.listing'"
            )
        )
    ).fetchall()
    assert [r[0] for r in rows] == ["Workspace B"]

    # No workspace context at all should fail closed (zero rows).
    await db_session.execute(text("SELECT set_config('app.workspace_id', '', true)"))
    rows = (
        await db_session.execute(
            text(
                "SELECT canonical_title FROM canonical_entities WHERE entity_type = 'vn_bds.listing'"
            )
        )
    ).fetchall()
    assert rows == []

    # Reset role so the rest of the test transaction can clean up.
    await db_session.execute(text("SET LOCAL ROLE NONE"))


async def test_unique_constraint_on_entity_fingerprint(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Two entities in the same workspace and type must have different fingerprints."""
    await set_canonical_workspace_id(db_session, db_workspace.id)

    await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="uq-f1",
        title="One",
        data={},
        search_text="one",
        source_name="batdongsan",
        source_record_id="u1",
    )

    # A different domain with the same fingerprint is allowed.
    job = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_jobs.listing",
        fingerprint="uq-f1",
        title="One job",
        data={},
        search_text="one job",
        source_name="topcv",
        source_record_id="j1",
    )
    assert job is not None
    assert job.entity_type == "vn_jobs.listing"


async def test_merge_history_conflicts_shape(
    db_session: AsyncSession, db_workspace: Workspace
):
    """Merge history stores ConflictFlag-shaped JSONB, not free-form strings."""
    conflict = {
        "type": "price_conflict",
        "reason": "Source prices differ by 25%",
        "price_range": {"min": 1_000_000_000, "max": 1_250_000_000},
        "price_sources": {"a": 1_000_000_000, "b": 1_250_000_000},
    }

    entity = await upsert_canonical_entity(
        db_session,
        workspace_id=db_workspace.id,
        entity_type="vn_bds.listing",
        fingerprint="conflict-f1",
        title="C",
        data={},
        search_text="c",
        source_name="batdongsan",
        source_record_id="c1",
        conflict_flags=[conflict],
    )

    history = await db_session.scalar(
        select(CanonicalMergeHistory).where(
            CanonicalMergeHistory.canonical_entity_id == entity.id
        )
    )
    assert history is not None
    assert history.conflicts == [conflict]
