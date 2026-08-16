import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.auth.impersonation import create_impersonation_token
from app.db import AuditEvent, User, get_async_session
from app.users import get_auth_context, require_superuser

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

    return {"access_token": token}


@router.post("/impersonate/exit")
async def exit_impersonation(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
):
    if not auth.is_impersonation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active impersonation session",
        )

    audit_event = AuditEvent(
        action="user.impersonate_exit",
        actor_id=auth.user.id,
        subject_id=auth.user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(audit_event)
    await session.commit()

    return {"status": "impersonation_ended"}
