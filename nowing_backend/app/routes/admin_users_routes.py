import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.auth.impersonation import create_impersonation_token
from app.auth.session_cookies import write_session
from app.config import config
from app.db import AuditEvent, User, Workspace, WorkspaceMembership, get_async_session
from app.schemas.workspace import WorkspaceWithStats
from app.users import SECRET, get_auth_context, get_jwt_strategy, require_superuser

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    # ponytail: minimal user directory for AC-1; full search/filter/stats TBD
    result = await session.execute(
        select(User).order_by(User.email).limit(1000)
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "is_verified": u.is_verified,
        }
        for u in users
    ]


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(
    request: Request,
    response: Response,
    user_id: uuid.UUID,
    ticket_ref: Annotated[str, ...],
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    if not ticket_ref or len(ticket_ref) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ticket_ref must be between 1 and 255 characters",
        )

    if user_id == auth.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot impersonate yourself",
        )

    target_user = await session.get(User, user_id)
    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_impersonation_token(auth.user, target_user, ticket_ref)

    audit_event = AuditEvent(
        action="user.impersonate_start",
        actor_id=auth.user.id,
        subject_id=target_user.id,
        ticket_ref=ticket_ref,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(audit_event)
    await session.commit()

    # ponytail: set the session cookie so the web UI immediately acts as the target user
    write_session(response, token, None, request)

    return {"access_token": token}


@router.post("/impersonate/exit")
async def exit_impersonation(
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
):
    if not auth.is_impersonation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active impersonation session",
        )

    # Reissue a normal session for the original admin and clear the impersonation cookie
    token = (
        request.cookies.get(config.SESSION_COOKIE_NAME)
        or _bearer_from_header(request.headers.get("authorization"))
    )
    admin_id = _admin_id_from_token(token)
    admin_user = await session.get(User, admin_id) if admin_id else None
    if admin_user:
        new_token = await get_jwt_strategy().write_token(admin_user)
        write_session(response, new_token, None, request)

    audit_event = AuditEvent(
        action="user.impersonate_exit",
        actor_id=admin_id or auth.user.id,
        subject_id=auth.user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(audit_event)
    await session.commit()

    return {"status": "impersonation_ended"}


def _bearer_from_header(header: str | None) -> str | None:
    if not header:
        return None
    scheme, _, credential = header.partition(" ")
    return credential if scheme.lower() == "bearer" and credential else None


def _admin_id_from_token(token: str | None) -> uuid.UUID | None:
    if token is None:
        return None
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_aud": False})
        return uuid.UUID(payload.get("impersonated_by"))
    except Exception:
        return None


@router.get("/workspaces", response_model=list[WorkspaceWithStats])
async def list_workspaces(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    # ponytail: minimal admin workspace directory for AC-1; full search/filter TBD
    result = await session.execute(select(Workspace).order_by(Workspace.id.asc()).limit(1000))
    workspaces = result.scalars().all()

    out = []
    for space in workspaces:
        member_count = (
            await session.execute(
                select(func.count(WorkspaceMembership.id)).filter(
                    WorkspaceMembership.workspace_id == space.id
                )
            )
        ).scalar() or 1

        out.append(
            WorkspaceWithStats(
                id=space.id,
                name=space.name,
                description=space.description,
                vertical=space.vertical,
                created_at=space.created_at,
                user_id=space.user_id,
                citations_enabled=space.citations_enabled,
                api_access_enabled=space.api_access_enabled,
                qna_custom_instructions=space.qna_custom_instructions,
                member_count=member_count,
                is_owner=False,
            )
        )

    return out
