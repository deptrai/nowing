"""Integration tests for composite workspace/client RLS on memories.

Story 18.8: the ``memories`` table has FORCE row-level security enabled with a
composite tenant predicate (workspace_id + client_id) plus a row-capability
``app.memory_id`` token and an ``app.internal_service`` bypass.

These tests run as a non-superuser role (``nowing_app``) so RLS is actually
enforced; the superuser test fixture used by other suites would otherwise
bypass policies.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.tenant_context import set_request_tenant_context
from app.db import Memory, MemorySourceType, MemoryType, User, Workspace
from app.services.memory.repository import MemoryRepository

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
async def _rls_enabled(db_session: AsyncSession) -> None:
    """Create policies and the test app role once per test transaction."""
    statements = [
        """
        DO $$
        BEGIN
            CREATE ROLE nowing_app NOLOGIN NOBYPASSRLS;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END
        $$;
        """,
        "GRANT USAGE ON SCHEMA public TO nowing_app;",
        "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nowing_app;",
        "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO nowing_app;",
        "DROP POLICY IF EXISTS memories_tenant_read_policy ON memories;",
        "DROP POLICY IF EXISTS memories_tenant_write_policy ON memories;",
        "DROP POLICY IF EXISTS memories_internal_service_policy ON memories;",
        """
        CREATE POLICY memories_tenant_read_policy ON memories
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING (
                memories.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
                AND memories.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
                OR memories.id::text = current_setting('app.memory_id', true)
                OR current_setting('app.internal_service', true) = 'true'
            );
        """,
        """
        CREATE POLICY memories_tenant_write_policy ON memories
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING (
                memories.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
                AND memories.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
            )
            WITH CHECK (
                memories.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
                AND memories.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')
            );
        """,
        """
        CREATE POLICY memories_internal_service_policy ON memories
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING (current_setting('app.internal_service', true) = 'true')
            WITH CHECK (current_setting('app.internal_service', true) = 'true');
        """,
        "ALTER TABLE memories ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE memories FORCE ROW LEVEL SECURITY;",
    ]
    for stmt in statements:
        await db_session.execute(text(stmt))


async def _as_app_user(session: AsyncSession) -> None:
    """Switch the current transaction to the unprivileged app role."""
    await session.execute(text("SET LOCAL ROLE nowing_app"))


def _unit_embedding() -> list[float]:
    from app.config import config

    dim = config.embedding_model_instance.dimension
    return [1.0] + [0.0] * (dim - 1)


def _make_memory(
    *,
    workspace_id: int | None,
    client_id: str | None,
    user: User,
    content: str = "test memory",
) -> Memory:
    return Memory(
        workspace_id=workspace_id,
        client_id=client_id,
        created_by_id=user.id,
        content=content,
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        tags=[],
        confidence=1.0,
        embedding=_unit_embedding(),
    )


async def _count_memories(session: AsyncSession) -> int:
    result = await session.execute(select(Memory))
    return len(result.scalars().all())


async def test_rls_no_guc_only_sees_unscoped_rows(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """Without tenant GUCs only user-scoped (workspace=NULL, client=NULL) rows
    are visible."""
    internal = _make_memory(workspace_id=db_workspace.id, client_id=None, user=db_user)
    client_a = _make_memory(
        workspace_id=db_workspace.id, client_id="client-a", user=db_user
    )
    user_scoped = _make_memory(workspace_id=None, client_id=None, user=db_user)

    db_session.add_all([internal, client_a, user_scoped])
    await db_session.flush()

    await _as_app_user(db_session)
    count = await _count_memories(db_session)

    assert count == 1
    only = (await db_session.execute(select(Memory))).scalar_one()
    assert only.workspace_id is None
    assert only.client_id is None


async def test_rls_correct_workspace_and_client(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """Setting the right workspace/client GUC returns exactly that scope."""
    internal = _make_memory(workspace_id=db_workspace.id, client_id=None, user=db_user)
    client_a = _make_memory(
        workspace_id=db_workspace.id, client_id="client-a", user=db_user
    )
    client_b = _make_memory(
        workspace_id=db_workspace.id, client_id="client-b", user=db_user
    )

    db_session.add_all([internal, client_a, client_b])
    await db_session.flush()

    await _as_app_user(db_session)
    await set_request_tenant_context(
        db_session, workspace_id=db_workspace.id, client_id="client-a"
    )

    rows = (await db_session.execute(select(Memory))).scalars().all()
    assert len(rows) == 1
    assert rows[0].client_id == "client-a"


async def test_rls_wrong_client_is_hidden(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """A workspace/client token for one client must not see another client."""
    client_a = _make_memory(
        workspace_id=db_workspace.id, client_id="client-a", user=db_user
    )
    client_b = _make_memory(
        workspace_id=db_workspace.id, client_id="client-b", user=db_user
    )

    db_session.add_all([client_a, client_b])
    await db_session.flush()

    await _as_app_user(db_session)
    await set_request_tenant_context(
        db_session, workspace_id=db_workspace.id, client_id="client-b"
    )

    rows = (await db_session.execute(select(Memory))).scalars().all()
    assert len(rows) == 1
    assert rows[0].client_id == "client-b"


async def test_rls_null_client_sees_internal_workspace_rows(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """A NULL client GUC only matches workspace rows with no client_id."""
    internal = _make_memory(workspace_id=db_workspace.id, client_id=None, user=db_user)
    client_a = _make_memory(
        workspace_id=db_workspace.id, client_id="client-a", user=db_user
    )

    db_session.add_all([internal, client_a])
    await db_session.flush()

    await _as_app_user(db_session)
    await set_request_tenant_context(
        db_session, workspace_id=db_workspace.id, client_id=None
    )

    rows = (await db_session.execute(select(Memory))).scalars().all()
    assert len(rows) == 1
    assert rows[0].client_id is None
    assert rows[0].workspace_id == db_workspace.id


async def test_rls_internal_service_bypass(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """``app.internal_service = 'true'`` bypasses tenant scoping."""
    client_a = _make_memory(
        workspace_id=db_workspace.id, client_id="client-a", user=db_user
    )
    client_b = _make_memory(
        workspace_id=db_workspace.id, client_id="client-b", user=db_user
    )
    user_scoped = _make_memory(workspace_id=None, client_id=None, user=db_user)

    db_session.add_all([client_a, client_b, user_scoped])
    await db_session.flush()

    await _as_app_user(db_session)
    await set_request_tenant_context(
        db_session, workspace_id=999_999, client_id="wrong-client"
    )
    await db_session.execute(
        text("SELECT set_config('app.internal_service', 'true', true)")
    )

    rows = (await db_session.execute(select(Memory))).scalars().all()
    assert len(rows) == 3


async def test_rls_memory_id_token_reads_single_row(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """``app.memory_id`` token lets a caller read a specific row regardless of
    the tenant GUC."""
    client_a = _make_memory(
        workspace_id=db_workspace.id, client_id="client-a", user=db_user
    )
    client_b = _make_memory(
        workspace_id=db_workspace.id, client_id="client-b", user=db_user
    )

    db_session.add_all([client_a, client_b])
    await db_session.flush()

    await _as_app_user(db_session)
    # Use a deliberately wrong tenant so that only the memory_id token can
    # match client_a; client_b should remain hidden by the workspace predicate.
    await set_request_tenant_context(
        db_session,
        workspace_id=999_999,
        client_id=None,
        memory_id=client_a.id,
    )

    result = await db_session.execute(select(Memory))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].id == client_a.id


async def test_repository_respects_rls_on_create(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """MemoryRepository.create_memory sets tenant GUCs and the new row is
    visible with the same tenant."""
    await _as_app_user(db_session)
    repo = MemoryRepository(session=db_session)

    memory = await repo.create_memory(
        workspace_id=db_workspace.id,
        content="created under client-a",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        client_id="client-a",
        created_by_id=db_user.id,
        embedding=_unit_embedding(),
        commit=False,
    )

    # With the same GUC still on the session, the new row should be visible.
    rows = (await db_session.execute(select(Memory))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == memory.id
    assert rows[0].client_id == "client-a"


async def test_repository_create_with_wrong_client_is_isolated(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
) -> None:
    """Creating with one client and then querying with a different client
    returns no rows."""
    await _as_app_user(db_session)
    repo = MemoryRepository(session=db_session)

    await repo.create_memory(
        workspace_id=db_workspace.id,
        content="created under client-a",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
        client_id="client-a",
        created_by_id=db_user.id,
        embedding=_unit_embedding(),
        commit=False,
    )

    await set_request_tenant_context(
        db_session, workspace_id=db_workspace.id, client_id="client-b"
    )

    rows = (await db_session.execute(select(Memory))).scalars().all()
    assert len(rows) == 0
