"""Concurrent merge updates on the same canonical entity."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.canonical.services.canonical_persist_service import (
    ConcurrentUpdateError,
    upsert_canonical_entity,
)
from app.db import CanonicalEntity, User, Workspace
from tests.conftest import TEST_DATABASE_URL

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


@pytest_asyncio.fixture
async def race_canonical_setup() -> AsyncGenerator[tuple[uuid.UUID, int], Any]:
    """Create a user and workspace via the live engine for cross-session tests."""
    user_id = uuid.uuid4()
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
        connect_args={"prepared_statement_cache_size": 0},
    )

    async with AsyncSession(engine) as setup:
        user = User(
            id=user_id,
            email=f"canon-race-{uuid.uuid4()}@nowing.test",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        space = Workspace(name="Canonical Race Space", user_id=user_id)
        setup.add_all([user, space])
        await setup.flush()
        await setup.commit()
        await setup.refresh(space)
        space_id = space.id

    yield user_id, space_id

    async with AsyncSession(engine) as cleanup:
        await cleanup.execute(
            text("DELETE FROM canonical_merge_history WHERE workspace_id = :wid"),
            {"wid": space_id},
        )
        await cleanup.execute(
            text("DELETE FROM canonical_entity_sources WHERE workspace_id = :wid"),
            {"wid": space_id},
        )
        await cleanup.execute(
            text("DELETE FROM canonical_entities WHERE workspace_id = :wid"),
            {"wid": space_id},
        )
        await cleanup.execute(
            text("DELETE FROM workspace_memberships WHERE workspace_id = :wid"),
            {"wid": space_id},
        )
        await cleanup.execute(
            text("DELETE FROM workspace_roles WHERE workspace_id = :wid"),
            {"wid": space_id},
        )
        await cleanup.execute(
            text("DELETE FROM workspaces WHERE id = :wid"),
            {"wid": space_id},
        )
        await cleanup.execute(
            text('DELETE FROM "user" WHERE id = :uid'),
            {"uid": user_id},
        )
        await cleanup.commit()

    await engine.dispose()


async def test_concurrent_upsert_one_wins_one_fails(
    race_canonical_setup,
):
    """Two sessions with expected_version=1 race; exactly one succeeds."""
    _, space_id = race_canonical_setup
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
        connect_args={"prepared_statement_cache_size": 0},
    )

    # Seed the entity in a dedicated session.
    async with AsyncSession(engine) as seed, seed.begin():
        entity = await upsert_canonical_entity(
            seed,
            workspace_id=space_id,
            entity_type="vn_bds.listing",
            fingerprint="race-fp",
            title="Race listing",
            data={"price_value": 5_000_000_000},
            search_text="race listing",
            source_name="batdongsan",
            source_record_id="race-1",
        )
        entity_id = entity.id

    async def _call(name: str) -> Any:
        async with AsyncSession(engine) as s, s.begin():
            entity = await upsert_canonical_entity(
                s,
                workspace_id=space_id,
                entity_type="vn_bds.listing",
                fingerprint="race-fp",
                title=f"Race listing {name}",
                data={"price_value": (5_100_000_000 if name == "a" else 5_200_000_000)},
                search_text=f"race listing {name}",
                source_name="batdongsan" if name == "a" else "muaban",
                source_record_id=f"race-{name}",
                expected_version=1,
            )
            # Eagerly read fields before the session closes.
            return {
                "id": entity.id,
                "version": entity.version,
                "source_count": entity.source_count,
            }

    results = await asyncio.gather(_call("a"), _call("b"), return_exceptions=True)

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, f"expected one success, got {len(successes)}"
    assert len(failures) == 1, f"expected one failure, got {len(failures)}"
    assert isinstance(failures[0], ConcurrentUpdateError)
    assert successes[0]["version"] == 2
    assert successes[0]["source_count"] == 2

    # Verify no lost update and final state is exactly the winner's.
    async with AsyncSession(engine) as verify:
        winner = await verify.get(CanonicalEntity, entity_id)
        assert winner is not None
        assert winner.version == 2
        assert winner.source_count == 2

    await engine.dispose()
