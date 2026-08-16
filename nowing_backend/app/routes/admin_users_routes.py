from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.auth.impersonation import create_impersonation_token
from app.db import AuditEvent, User, get_async_session
from app.users import require_superuser

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    # Dummy implementation for ATDD scaffold
    pass

@router.post("/users/{user_id}/impersonate")
async def impersonate_user(
    user_id: str,
    ticket_ref: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_superuser),
):
    # If nested impersonation is blocked by require_superuser, we're good
    target_user = await session.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    token = create_impersonation_token(auth.user, target_user, ticket_ref)
    
    # Audit logging
    audit_event = AuditEvent(
        action="user.impersonate_start",
        actor_id=auth.user.id,
        subject_id=target_user.id,
        ticket_ref=ticket_ref,
    )
    session.add(audit_event)
    await session.commit()
    
    return {"access_token": token}

@router.post("/impersonate/exit")
async def exit_impersonation():
    pass
