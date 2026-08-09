"""FastAPI dependency that authorizes public agent-chat requests via a scoped PAT."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Module references (not local copies) so tests can monkeypatch these seams.
import app.canonical.tenant_context as _tenant_context
import app.users as _users
import app.utils.rbac as _rbac
from app.auth.context import AuthContext
from app.config import config
from app.db import AgentConfig, PersonalAccessToken, User, VerticalClient


def _derive_scope_permission(request: Request) -> str:
    """Map an agent-chat route + method to the required PAT scope."""
    method = request.method.upper()
    path = request.url.path if request.url else request.scope.get("path", "")

    if method == "POST" and path.endswith("/messages"):
        return "agent_chat:message:create"
    if method == "POST" and path.endswith("/threads"):
        return "agent_chat:thread:create"
    if method == "GET":
        return "agent_chat:thread:read"
    return "agent_chat:unknown"


def _effective_client_id(pat: PersonalAccessToken, body_client_id: str | None) -> str:
    """Return the client_id that the request is allowed to act as."""
    if body_client_id is not None and body_client_id != (pat.client_id or ""):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="client_id outside pat scope",
        )
    if body_client_id is None and not pat.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id required",
        )
    return body_client_id if body_client_id is not None else pat.client_id


async def _resolve_vertical_client(
    session: AsyncSession, client_id: str
) -> VerticalClient:
    result = await session.execute(
        select(VerticalClient).where(
            VerticalClient.client_id == client_id,
            VerticalClient.is_active.is_(True),
        )
    )
    client = result.scalars().first()
    if client is None or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id not registered for workspace",
        )
    return client


async def _resolve_agent_config(
    session: AsyncSession,
    client_id: str,
    agent_id: str,
) -> AgentConfig:
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.client_id == client_id,
            AgentConfig.slug == agent_id,
            AgentConfig.is_active.is_(True),
        )
    )
    config = result.scalars().first()
    if config is None or not config.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent not found or inactive",
        )
    if config.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="agent_id not allowed for client_id",
        )
    return config


class AgentChatContext:
    """Principal returned by ``require_agent_chat_pat`` to route handlers."""

    def __init__(
        self,
        *,
        user: User,
        pat: PersonalAccessToken,
        workspace_id: int,
        client_id: str,
        agent_id: str,
    ) -> None:
        self.user = user
        self.pat = pat
        self.workspace_id = workspace_id
        self.effective_client_id = client_id
        self.effective_agent_id = agent_id

    @property
    def actor_user_id(self) -> str:
        return str(self.user.id)

    @property
    def pat_id(self) -> str:
        return str(self.pat.id)


async def require_agent_chat_pat(
    request: Request,
    session: AsyncSession,
    body,
) -> AgentChatContext:
    """FastAPI dependency: resolve and scope a public agent-chat PAT request."""
    if not getattr(config, "AGENT_CHAT_PUBLIC_ENABLED", True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent_chat public surface disabled",
        )

    auth_ctx: AuthContext
    try:
        auth_ctx = await _users.get_auth_context(request, session)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid credentials: {exc}",
        ) from exc

    if auth_ctx.method != "pat" or auth_ctx.pat is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="pat_scope_required: agent-chat requires a personal access token",
        )

    pat: PersonalAccessToken = auth_ctx.pat

    if pat.token_kind != "agent_chat":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="pat_scope_required: token_kind must be 'agent_chat'",
        )

    workspace_id = request.path_params.get("workspace_id")
    if workspace_id is None:
        workspace_id = request.query_params.get("workspace_id")
    try:
        workspace_id = int(workspace_id)
    except (TypeError, ValueError) as _exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workspace_id must be an integer",
        ) from _exc

    if pat.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace_id outside pat scope",
        )

    # get_auth_context already validates the PAT; do not rely on test fakes.
    if getattr(pat, "is_valid", None) is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="pat expired",
        )

    membership = await _rbac.get_user_membership(
        session, auth_ctx.user.id, workspace_id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace membership revoked",
        )

    required_scope = _derive_scope_permission(request)
    if required_scope not in (pat.scopes or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"permission missing: {required_scope}",
        )

    body_client_id = getattr(body, "client_id", None)
    body_agent_id = getattr(body, "agent_id", None)

    effective_client_id = _effective_client_id(pat, body_client_id)
    await _resolve_vertical_client(session, effective_client_id)

    effective_agent_id = body_agent_id or pat.agent_id
    if not effective_agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent_id required",
        )

    # Ensure the agent belongs to this client.
    await _resolve_agent_config(session, effective_client_id, effective_agent_id)

    # Set tenant GUCs before any business query runs.
    await _tenant_context.set_request_tenant_context(
        session, workspace_id, effective_client_id, effective_agent_id
    )

    return AgentChatContext(
        user=auth_ctx.user,
        pat=pat,
        workspace_id=workspace_id,
        client_id=effective_client_id,
        agent_id=effective_agent_id,
    )
