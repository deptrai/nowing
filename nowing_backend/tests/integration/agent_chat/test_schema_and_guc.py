"""Integration tests for Story 18.1 public agent-chat DB schema and tenant context.

Pattern 6 (SQL Mock Not Executed): these tests run real SQL against Postgres,
query the real catalog, and verify transaction-local GUCs. They will be red
until the Epic 18 schema migrations and tenant-context helper are implemented.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.utils.pat import generate_pat, hash_pat, token_prefix

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------


async def _table_exists(db_session, table_name: str) -> bool:
    result = await db_session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": table_name},
    )
    return result.scalar() is not None


async def _columns_of(db_session, table_name: str) -> set[str]:
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": table_name},
    )
    return {row[0] for row in result.all()}


async def _udt_of(db_session, table_name: str, column_name: str) -> str | None:
    result = await db_session.execute(
        text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :tname AND column_name = :cname"
        ),
        {"tname": table_name, "cname": column_name},
    )
    return result.scalar()


async def _constraints_on(db_session, table_name: str) -> set[str]:
    result = await db_session.execute(
        text(
            """
            SELECT conname
            FROM pg_constraint
            JOIN pg_class ON pg_constraint.conrelid = pg_class.oid
            WHERE pg_class.relname = :name
            """
        ),
        {"name": table_name},
    )
    return {row[0] for row in result.all()}


# ---------------------------------------------------------------------------
# 1. Schema readiness — personal_access_tokens scope columns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pat_scope_columns_exist(db_session):
    """personal_access_tokens has the PAT scope columns required by AD-29."""
    columns = await _columns_of(db_session, "personal_access_tokens")
    expected = {"workspace_id", "client_id", "agent_id", "scopes", "token_kind"}
    missing = expected - columns
    assert not missing, f"personal_access_tokens missing columns: {missing}"


@pytest.mark.asyncio
async def test_pat_scope_column_types(db_session):
    """PAT scope columns have the expected UDT types."""
    assert (await _udt_of(db_session, "personal_access_tokens", "scopes")) == "jsonb"
    assert (await _udt_of(db_session, "personal_access_tokens", "token_kind")) in (
        "text",
        "varchar",
    )
    assert (await _udt_of(db_session, "personal_access_tokens", "client_id")) in (
        "text",
        "varchar",
        "citext",
    )


@pytest.mark.asyncio
async def test_pat_check_constraints_exist(db_session):
    """personal_access_tokens has the agent_chat scope check constraints."""
    constraints = await _constraints_on(db_session, "personal_access_tokens")
    # The exact conname may vary by migration; we assert by substring.
    assert any(
        "agent_chat" in c or "token_kind" in c for c in constraints
    ), "missing token_kind=agent_chat check constraint"
    assert any(
        "agent_id" in c or "client_id" in c for c in constraints
    ), "missing agent_id requires client_id check constraint"


@pytest.mark.asyncio
async def test_pat_agent_chat_requires_workspace_client_and_scopes(db_session, db_user):
    """Inserting token_kind='agent_chat' without workspace_id/client_id/scopes fails."""
    columns = await _columns_of(db_session, "personal_access_tokens")
    missing = {"workspace_id", "client_id", "agent_id", "scopes", "token_kind"} - columns
    assert not missing, f"personal_access_tokens missing columns: {missing}"

    token = generate_pat()
    await db_session.execute(
        text(
            "INSERT INTO personal_access_tokens (user_id, token_hash, token_prefix, "
            "label, expires_at, token_kind, workspace_id, client_id, agent_id, scopes) "
            "VALUES (:user_id, :token_hash, :token_prefix, :label, NULL, "
            "'agent_chat', NULL, NULL, NULL, '[]')"
        ),
        {
            "user_id": db_user.id,
            "token_hash": hash_pat(token),
            "token_prefix": token_prefix(token),
            "label": "scope-incomplete-pat",
        },
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_pat_agent_requires_client_id(db_session, db_user):
    """Inserting agent_id without client_id fails the check constraint."""
    columns = await _columns_of(db_session, "personal_access_tokens")
    missing = {"workspace_id", "client_id", "agent_id", "scopes", "token_kind"} - columns
    assert not missing, f"personal_access_tokens missing columns: {missing}"

    token = generate_pat()
    await db_session.execute(
        text(
            "INSERT INTO personal_access_tokens (user_id, token_hash, token_prefix, "
            "label, expires_at, token_kind, workspace_id, client_id, agent_id, scopes) "
            "VALUES (:user_id, :token_hash, :token_prefix, :label, NULL, "
            "'agent_chat', 1, NULL, 'bdsai-listing-assistant', '[\"agent_chat:thread:create\"]')"
        ),
        {
            "user_id": db_user.id,
            "token_hash": hash_pat(token),
            "token_prefix": token_prefix(token),
            "label": "agent-without-client",
        },
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ---------------------------------------------------------------------------
# 2. vertical_clients table and constraints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vertical_clients_table_exists(db_session):
    """vertical_clients table exists for client_id normalization."""
    assert await _table_exists(db_session, "vertical_clients")


@pytest.mark.asyncio
async def test_vertical_clients_client_id_is_citext_unique(db_session):
    """client_id is CITEXT and has a unique constraint."""
    assert await _table_exists(db_session, "vertical_clients")
    columns = await _columns_of(db_session, "vertical_clients")
    assert "client_id" in columns
    udt = await _udt_of(db_session, "vertical_clients", "client_id")
    assert udt in ("citext", "text", "varchar")
    constraints = await _constraints_on(db_session, "vertical_clients")
    assert any(
        "client_id" in c and ("unique" in c or "uniq" in c or c.endswith("_key"))
        for c in constraints
    ), "vertical_clients.client_id missing unique constraint"


@pytest.mark.asyncio
async def test_vertical_clients_rejects_duplicate_client_id(db_session):
    """Duplicate client_id raises IntegrityError."""
    if not await _table_exists(db_session, "vertical_clients"):
        pytest.fail("vertical_clients table does not exist")
    await db_session.execute(
        text(
            "INSERT INTO vertical_clients (id, client_id, display_name, is_active) "
            "VALUES (:id, :client_id, :display_name, true)"
        ),
        {
            "id": str(uuid.uuid4()),
            "client_id": "bdsai.vn",
            "display_name": "BDS AI",
        },
    )
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO vertical_clients (id, client_id, display_name, is_active) "
                "VALUES (:id, :client_id, :display_name, true)"
            ),
            {
                "id": str(uuid.uuid4()),
                "client_id": "bdsai.vn",
                "display_name": "BDS AI Duplicate",
            },
        )


# ---------------------------------------------------------------------------
# 3. agent_configs table and constraints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_configs_table_exists(db_session):
    """agent_configs table exists for AD-30 AgentConfig registry."""
    assert await _table_exists(db_session, "agent_configs")


@pytest.mark.asyncio
async def test_agent_configs_required_columns(db_session):
    """agent_configs has client_id, name/slug, is_active, enabled_tools."""
    assert await _table_exists(db_session, "agent_configs")
    columns = await _columns_of(db_session, "agent_configs")
    expected = {"client_id", "name", "slug", "is_active", "enabled_tools"}
    missing = expected - columns
    assert not missing, f"agent_configs missing columns: {missing}"


# ---------------------------------------------------------------------------
# 4. client_id columns on chat/research tables
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_chat_threads_has_client_id(db_session):
    """new_chat_threads has a client_id column for tenant isolation."""
    columns = await _columns_of(db_session, "new_chat_threads")
    assert "client_id" in columns


@pytest.mark.asyncio
async def test_research_threads_has_client_id(db_session):
    """research_threads has a client_id column for tenant isolation."""
    columns = await _columns_of(db_session, "research_threads")
    assert "client_id" in columns


# ---------------------------------------------------------------------------
# 5. Transaction-local GUCs (tenant context)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_current_client_id_set_local_within_transaction(db_session):
    """SET LOCAL app.current_client_id is visible within the same transaction."""
    await db_session.execute(
        text("SELECT set_config('app.current_client_id', 'bdsai.vn', true)")
    )
    result = await db_session.execute(
        text("SELECT current_setting('app.current_client_id', true)")
    )
    assert result.scalar() == "bdsai.vn"


@pytest.mark.asyncio
async def test_app_current_client_id_cleared_on_rollback(db_session):
    """GUC set with SET LOCAL is cleared when the transaction rolls back."""
    await db_session.execute(
        text("SELECT set_config('app.current_client_id', 'bdsai.vn', true)")
    )
    await db_session.rollback()
    result = await db_session.execute(
        text("SELECT current_setting('app.current_client_id', true)")
    )
    assert result.scalar() in (None, "")


@pytest.mark.asyncio
async def test_app_workspace_id_cleared_on_rollback(db_session):
    """Existing app.workspace_id GUC also clears on rollback (pool safety)."""
    await db_session.execute(
        text("SELECT set_config('app.workspace_id', '42', true)")
    )
    await db_session.rollback()
    result = await db_session.execute(
        text("SELECT current_setting('app.workspace_id', true)")
    )
    assert result.scalar() in (None, "")


@pytest.mark.asyncio
async def test_guc_isolation_between_connections(async_engine):
    """A GUC set on one connection is not visible on another (pool safety, L3)."""
    async with async_engine.connect() as conn1, conn1.begin():
        await conn1.execute(
            text("SELECT set_config('app.current_client_id', 'bdsai.vn', true)")
        )
        result = await conn1.execute(
            text("SELECT current_setting('app.current_client_id', true)")
        )
        assert result.scalar() == "bdsai.vn"

        # Second connection from the pool must not see the GUC.
        async with async_engine.connect() as conn2:
            result2 = await conn2.execute(
                text("SELECT current_setting('app.current_client_id', true)")
            )
            assert result2.scalar() in (None, "")
