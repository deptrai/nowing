"""Explicit, fail-closed tenant context for canonical tables.

The workspace ID is always passed as a function argument; there is no thread-local
or process-global fallback.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_canonical_workspace_id(session: AsyncSession, workspace_id: int) -> None:
    """Set the tenant workspace for the current transaction only.

    ``SET LOCAL`` means the value is scoped to the current SQL transaction and
    is cleared on commit/rollback, so a pooled connection can never leak the
    context to the next caller.
    """
    # ponytail: set_config() is the parameter-safe equivalent of SET LOCAL.
    await session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": str(workspace_id)},
    )
    # Keep a matching marker on the session so higher-level code can assert the
    # context is explicit before touching canonical rows.
    session.info["canonical_workspace_id"] = workspace_id


@asynccontextmanager
async def canonical_workspace_context(
    session: AsyncSession, workspace_id: int
) -> AsyncGenerator[AsyncSession, Any]:
    """Context manager that sets and clears the canonical workspace context."""
    await set_canonical_workspace_id(session, workspace_id)
    try:
        yield session
    finally:
        session.info.pop("canonical_workspace_id", None)


def get_canonical_workspace_id(session: AsyncSession) -> int | None:
    """Return the workspace ID explicitly bound to this session, if any."""
    return session.info.get("canonical_workspace_id")


async def set_request_tenant_context(
    session: AsyncSession,
    workspace_id: int | None = None,
    client_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    memory_id: int | None = None,
    user_id: str | None = None,
) -> None:
    """Set workspace + client + agent GUCs for the current transaction only.

    ``SET LOCAL`` scopes the values to the SQL transaction, so a pooled
    connection cannot leak tenant context to the next request.

    ``None`` is written as an empty string so a prior GUC is cleared.  The
    memory RLS policy uses ``NULLIF(..., '')`` on ``app.workspace_id`` and
    ``app.current_client_id`` to treat the empty string as SQL ``NULL``, which
    matches user-scoped / unscoped rows with ``IS NOT DISTINCT FROM``.
    """
    # ponytail: set_config() is the parameter-safe equivalent of SET LOCAL.
    # Write an empty string for ``None`` so a prior value is cleared; the RLS
    # ``NULLIF`` wrapper converts it back to SQL NULL for IS NOT DISTINCT FROM.
    await session.execute(
        text("SELECT set_config('app.workspace_id', :wid, true)"),
        {"wid": "" if workspace_id is None else str(workspace_id)},
    )
    await session.execute(
        text("SELECT set_config('app.current_client_id', :cid, true)"),
        {"cid": client_id or ""},
    )
    await session.execute(
        text("SELECT set_config('app.current_agent_id', :aid, true)"),
        {"aid": agent_id or ""},
    )
    await session.execute(
        text("SELECT set_config('app.run_id', :rid, true)"),
        {"rid": run_id or ""},
    )
    await session.execute(
        text("SELECT set_config('app.memory_id', :mid, true)"),
        {"mid": "" if memory_id is None else str(memory_id)},
    )
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": user_id or ""},
    )
    # Tests sometimes pass a fake session without .info; the GUCs are the
    # source of truth for RLS anyway, so tolerate the missing attribute.
    if hasattr(session, "info"):
        session.info["canonical_workspace_id"] = workspace_id
        session.info["current_client_id"] = client_id
        session.info["current_agent_id"] = agent_id
        session.info["current_run_id"] = run_id
        session.info["current_memory_id"] = memory_id
        session.info["current_user_id"] = user_id
