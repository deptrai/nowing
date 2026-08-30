"""Agent Tools Endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.agent_chat import _resolve_agent_config
from app.auth.context import AuthContext
from app.db import (
    get_async_session,
)
from app.schemas.new_chat import (
    AgentToolInfo,
)
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context

router = APIRouter()

@router.get("/agent/tools", response_model=list[AgentToolInfo])
async def list_agent_tools(
    _auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
    client_id: str | None = None,
    agent_id: str | None = None,
):
    """Return the list of built-in agent tools with their metadata.

    Hidden (WIP) tools are excluded from the response. When ``client_id`` and
    ``agent_id`` are supplied, the list is filtered by the agent's allowlist and
    denylist (AC-18.4 introspection parity).
    """
    from app.agents.chat.multi_agent_chat.shared.tools.catalog import TOOL_CATALOG

    if client_id and agent_id:
        await set_request_tenant_context(
            session, workspace_id=None, client_id=client_id, agent_id=agent_id
        )
        try:
            registry = await _resolve_agent_config(session, client_id, agent_id)
        except HTTPException:
            # Fall back to the unfiltered catalog rather than leaking whether
            # the agent exists; auth context is already verified.
            registry = None
        if registry:
            enabled = set(registry.enabled_tools or [])
            disabled = set(registry.disabled_tools or [])
            return [
                AgentToolInfo(
                    name=t.name,
                    description=t.description,
                    enabled_by_default=t.enabled_by_default,
                )
                for t in TOOL_CATALOG
                if not t.hidden
                and (not enabled or t.name in enabled)
                and t.name not in disabled
            ]

    return [
        AgentToolInfo(
            name=t.name,
            description=t.description,
            enabled_by_default=t.enabled_by_default,
        )
        for t in TOOL_CATALOG
        if not t.hidden
    ]

__all__ = ["router"]
