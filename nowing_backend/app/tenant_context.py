"""Explicit, fail-closed tenant context for RLS-protected tables.

The workspace / client / agent / run / memory / user IDs are always passed as
function arguments; there is no thread-local or process-global fallback.

Originally part of ``app.canonical.tenant_context``; moved here because the
tenant GUC helpers are shared across the codebase (runs, chat, automations,
lead intelligence, etc.) and outlived the canonical-entity package.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_request_tenant_context(
    session: AsyncSession,
    workspace_id: int | None = None,  # pragma: no mutate
    client_id: str | None = None,  # pragma: no mutate
    agent_id: str | None = None,  # pragma: no mutate
    run_id: str | None = None,  # pragma: no mutate
    memory_id: int | None = None,  # pragma: no mutate
    user_id: str | None = None,  # pragma: no mutate
    is_lead_admin: str | None = None,  # pragma: no mutate
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
        {"cid": "" if client_id is None else str(client_id)},
    )
    await session.execute(
        text("SELECT set_config('app.current_agent_id', :aid, true)"),
        {"aid": "" if agent_id is None else str(agent_id)},
    )
    await session.execute(
        text("SELECT set_config('app.run_id', :rid, true)"),
        {"rid": "" if run_id is None else str(run_id)},
    )
    await session.execute(
        text("SELECT set_config('app.memory_id', :mid, true)"),
        {"mid": "" if memory_id is None else str(memory_id)},
    )
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": "" if user_id is None else str(user_id)},
    )
    await session.execute(
        text("SELECT set_config('app.is_lead_admin', :ila, true)"),
        {"ila": "" if is_lead_admin is None else str(is_lead_admin)},
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
        session.info["is_lead_admin"] = is_lead_admin
