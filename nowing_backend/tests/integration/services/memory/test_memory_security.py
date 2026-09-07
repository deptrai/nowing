"""Security tests for memory encryption-at-rest (Story 28.2 AC-3 / AC-6).

These tests run against a real Postgres session so RLS and tenant isolation
are exercised.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Memory,
    MemorySourceType,
    MemoryType,
    Workspace,
)
from app.services.memory.repository import MemoryRepository
from app.tenant_context import set_request_tenant_context


def _memory_tenant_predicate(table: str) -> str:
    """Same predicate used by alembic migration for memories."""
    return f"""
        {table}.workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int
        AND {table}.client_id IS NOT DISTINCT FROM NULLIF(current_setting('app.current_client_id', true), '')::citext
    """


def _memory_id_predicate(table: str) -> str:
    return f"{table}.id::text = current_setting('app.memory_id', true)"


def _internal_service_predicate(_table: str) -> str:
    return "current_setting('app.internal_service', true) = 'true'"


async def _create_rls_policies(session: AsyncSession, table: str) -> None:
    """Create RLS policies matching the alembic migration so tests can run
    against a metadata-created schema."""
    # Ensure the non-superuser application role exists.
    await session.execute(
        text("""
        DO $$
        BEGIN
            CREATE ROLE nowing_app NOLOGIN NOBYPASSRLS;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END
        $$;
        """)
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO nowing_app"))
    await session.execute(text(f"GRANT ALL ON {table} TO nowing_app"))
    await session.execute(
        text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    )
    await session.execute(
        text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    )
    await session.execute(
        text(f"DROP POLICY IF EXISTS {table}_tenant_read_policy ON {table}")
    )
    await session.execute(
        text(f"DROP POLICY IF EXISTS {table}_tenant_write_policy ON {table}")
    )
    await session.execute(
        text(f"DROP POLICY IF EXISTS {table}_internal_service_policy ON {table}")
    )
    await session.execute(
        text(f"""
        CREATE POLICY {table}_tenant_read_policy ON {table}
            AS PERMISSIVE
            FOR SELECT
            TO PUBLIC
            USING (
                {_memory_tenant_predicate(table)}
                OR {_memory_id_predicate(table)}
                OR {_internal_service_predicate(table)}
            );
        """)
    )
    await session.execute(
        text(f"""
        CREATE POLICY {table}_tenant_write_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_memory_tenant_predicate(table)})
            WITH CHECK ({_memory_tenant_predicate(table)});
        """)
    )
    await session.execute(
        text(f"""
        CREATE POLICY {table}_internal_service_policy ON {table}
            AS PERMISSIVE
            FOR ALL
            TO PUBLIC
            USING ({_internal_service_predicate(table)})
            WITH CHECK ({_internal_service_predicate(table)});
        """)
    )


@pytest_asyncio.fixture
async def _managed_encryption():
    """Set managed key env for this test module."""
    old_flag = os.environ.get("MEMORY_ENCRYPTION_V1")
    old_provider = os.environ.get("NOWING_ENCRYPTION_KEY_PROVIDER")
    old_key = os.environ.get("MANAGED_ENCRYPTION_MASTER_KEY")
    os.environ["MEMORY_ENCRYPTION_V1"] = "true"
    os.environ["NOWING_ENCRYPTION_KEY_PROVIDER"] = "managed"
    os.environ["MANAGED_ENCRYPTION_MASTER_KEY"] = "x" * 32
    yield
    if old_flag is None:
        os.environ.pop("MEMORY_ENCRYPTION_V1", None)
    else:
        os.environ["MEMORY_ENCRYPTION_V1"] = old_flag
    if old_provider is None:
        os.environ.pop("NOWING_ENCRYPTION_KEY_PROVIDER", None)
    else:
        os.environ["NOWING_ENCRYPTION_KEY_PROVIDER"] = old_provider
    if old_key is None:
        os.environ.pop("MANAGED_ENCRYPTION_MASTER_KEY", None)
    else:
        os.environ["MANAGED_ENCRYPTION_MASTER_KEY"] = old_key


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_tenant_read_blocked_before_decryption(
    db_session: AsyncSession,
    _managed_encryption,
):
    """AC-3: an unauthorized tenant must not see plaintext or raw ciphertext."""
    # Create a user and two workspaces via fixtures to satisfy NOT NULL.
    import app.db as app_db
    from tests.integration.conftest import create_default_roles_and_membership
    user = app_db.User(
        id=uuid.uuid4(),
        email="security-test@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    ws_a = Workspace(name="tenant-a", user_id=user.id)
    ws_b = Workspace(name="tenant-b", user_id=user.id)
    db_session.add(ws_a)
    db_session.add(ws_b)
    await db_session.flush()
    await create_default_roles_and_membership(db_session, ws_a.id, user.id)
    await create_default_roles_and_membership(db_session, ws_b.id, user.id)
    await db_session.flush()

    repo_a = MemoryRepository(db_session)
    await set_request_tenant_context(
        db_session, workspace_id=ws_a.id, client_id=None
    )
    memory = await repo_a.create_memory(
        workspace_id=ws_a.id,
        content="secret tenant A fact",
        type=MemoryType.SEMANTIC,
        source_type=MemorySourceType.MANUAL,
    )

    # Tenant B tries to read the same memory id.
    await set_request_tenant_context(
        db_session, workspace_id=ws_b.id, client_id=None
    )
    # Switch to the application role (non-superuser) so RLS applies.
    await _create_rls_policies(db_session, "memories")
    await db_session.execute(text("SET ROLE nowing_app"))
    result = await db_session.execute(
        select(Memory).where(Memory.id == memory.id)
    )
    loaded = result.scalar_one_or_none()

    # RLS must hide the row entirely.
    assert loaded is None
