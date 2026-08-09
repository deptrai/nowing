"""FastAPI dependency that authorizes public agent-chat requests via a scoped PAT."""

from __future__ import annotations

import re

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
from app.services.agent_chat.audit import log_public_call as _audit

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-._]{0,62}$")

AGENT_CHAT_SCOPES: frozenset[str] = frozenset(
    {
        "agent_chat:thread:create",
        "agent_chat:message:create",
        "agent_chat:thread:read",
    }
)


def _validate_slug(value: str, field: str) -> str:
    if not _SLUG_RE.fullmatch(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} must be a lowercase slug (a-z, 0-9, -, ., _)",
        )
    return value


def validate_scopes(scopes: list[str]) -> None:
    """Validate that every supplied scope is in the known agent-chat catalog."""
    unknown = [s for s in scopes if s not in AGENT_CHAT_SCOPES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown scopes: {', '.join(unknown)}",
        )


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
    if body_client_id is not None:
        _validate_slug(body_client_id, "client_id")
        if body_client_id != (pat.client_id or ""):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="client_id outside pat scope",
            )
    if not pat.client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id required",
        )
    return _validate_slug(
        body_client_id if body_client_id is not None else pat.client_id,
        "client_id",
    )


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
    if config.client_id == client_id:
        # Fail closed: do not reveal that the agent exists under another client.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent not found or inactive",
        )
    return config


def _route_label(request: Request) -> str:
    """Return a low-cardinality route template for audit/metrics."""
    route = request.scope.get("route")
    if route is not None:
        return f"{request.method} {route.path}"
    return f"{request.method} {request.url.path}"


def _parse_workspace_id(value) -> int:
    """Best-effort parse of workspace_id for audit records."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


async def _audit_rejection(
    request: Request,
    session: AsyncSession,
    status_code: int,
    *,
    actor_user_id: str = "",
    pat_id: int | str = "",
    workspace_id: int | str = 0,
    client_id: str | None = None,
    agent_id: str | None = None,
) -> None:
    """Audit a rejected public agent-chat call without leaking PII."""
    await _audit(
        actor_user_id=actor_user_id,
        pat_id=pat_id,
        workspace_id=_parse_workspace_id(workspace_id),
        client_id=client_id,
        agent_id=agent_id,
        route=_route_label(request),
        status=status_code,
    )


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
    workspace_id_raw = request.path_params.get("workspace_id")

    if not getattr(config, "AGENT_CHAT_PUBLIC_ENABLED", False):
        await _audit_rejection(
            request,
            session,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            workspace_id=workspace_id_raw,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent_chat public surface disabled",
        )

    auth_ctx: AuthContext
    try:
        auth_ctx = await _users.get_auth_context(request, session)
    except HTTPException as exc:
        await _audit_rejection(
            request,
            session,
            exc.status_code,
            workspace_id=workspace_id_raw,
        )
        raise
    except Exception as _exc:
        # Log the real exception internally; do not disclose it to the client.
        await _audit_rejection(
            request,
            session,
            status.HTTP_401_UNAUTHORIZED,
            workspace_id=workspace_id_raw,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        ) from _exc

    if auth_ctx.method != "pat" or auth_ctx.pat is None:
        await _audit_rejection(
            request,
            session,
            status.HTTP_403_FORBIDDEN,
            actor_user_id=str(auth_ctx.user.id),
            workspace_id=workspace_id_raw,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="pat_scope_required: agent-chat requires a personal access token",
        )

    pat: PersonalAccessToken = auth_ctx.pat

    if pat.token_kind != "agent_chat":
        await _audit_rejection(
            request,
            session,
            status.HTTP_403_FORBIDDEN,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id_raw,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="pat_scope_required: token_kind must be 'agent_chat'",
        )

    # Reject PATs with out-of-catalog scopes even if they were somehow inserted.
    validate_scopes(pat.scopes or [])

    try:
        workspace_id = int(workspace_id_raw)
    except (TypeError, ValueError) as _exc:
        await _audit_rejection(
            request,
            session,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id_raw,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workspace_id must be an integer",
        ) from _exc

    if pat.workspace_id != workspace_id:
        await _audit_rejection(
            request,
            session,
            status.HTTP_403_FORBIDDEN,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace_id outside pat scope",
        )

    # get_auth_context already validates the PAT; do not rely on test fakes.
    if getattr(pat, "is_valid", None) is False:
        await _audit_rejection(
            request,
            session,
            status.HTTP_401_UNAUTHORIZED,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="pat expired",
        )

    membership = await _rbac.get_user_membership(
        session, auth_ctx.user.id, workspace_id
    )
    if membership is None:
        await _audit_rejection(
            request,
            session,
            status.HTTP_403_FORBIDDEN,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace membership revoked",
        )

    required_scope = _derive_scope_permission(request)
    if required_scope not in (pat.scopes or []):
        await _audit_rejection(
            request,
            session,
            status.HTTP_403_FORBIDDEN,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"permission missing: {required_scope}",
        )

    body_client_id = getattr(body, "client_id", None)
    body_agent_id = getattr(body, "agent_id", None)

    effective_client_id = _effective_client_id(pat, body_client_id)
    effective_agent_id = body_agent_id or pat.agent_id
    if effective_agent_id:
        _validate_slug(effective_agent_id, "agent_id")

    if not effective_agent_id:
        await _audit_rejection(
            request,
            session,
            status.HTTP_404_NOT_FOUND,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id,
            client_id=effective_client_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent_id required",
        )

    # Set tenant GUCs before any lookup that may be protected by RLS.
    await _tenant_context.set_request_tenant_context(
        session, workspace_id, effective_client_id, effective_agent_id
    )

    try:
        await _resolve_vertical_client(session, effective_client_id)
    except HTTPException as exc:
        await _audit_rejection(
            request,
            session,
            exc.status_code,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id,
            client_id=effective_client_id,
        )
        raise

    # Ensure the agent belongs to this client.
    try:
        await _resolve_agent_config(session, effective_client_id, effective_agent_id)
    except HTTPException as exc:
        await _audit_rejection(
            request,
            session,
            exc.status_code,
            actor_user_id=str(auth_ctx.user.id),
            pat_id=getattr(pat, "id", ""),
            workspace_id=workspace_id,
            client_id=effective_client_id,
            agent_id=effective_agent_id,
        )
        raise

    return AgentChatContext(
        user=auth_ctx.user,
        pat=pat,
        workspace_id=workspace_id,
        client_id=effective_client_id,
        agent_id=effective_agent_id,
    )
