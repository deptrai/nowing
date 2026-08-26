"""Admin routes for Security Audit Trail Logs (Story 25.6)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import AuditEvent, get_async_session
from app.rate_limiter import get_real_client_ip
from app.schemas.admin_audit_logs import AuditEventListResponse
from app.services.admin_audit_log_service import AdminAuditLogService
from app.users import require_superuser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/audit-logs", tags=["admin"])


@router.get(
    "",
    response_model=AuditEventListResponse,
    summary="List paginated security audit trail logs with actor/subject email resolution",
)
async def list_audit_logs(
    request: Request,
    auth: Annotated[AuthContext, Depends(require_superuser)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    action: Annotated[str | None, Query(description="Filter by action string")] = None,
    actor_id: Annotated[
        uuid.UUID | None, Query(description="Filter by actor user ID")
    ] = None,
    actor_email: Annotated[str | None, Query(description="Search actor email")] = None,
    subject_id: Annotated[
        uuid.UUID | None, Query(description="Filter by subject user ID")
    ] = None,
    subject_email: Annotated[
        str | None, Query(description="Search subject email")
    ] = None,
    ticket_ref: Annotated[
        str | None, Query(description="Search ticket reference")
    ] = None,
    start_date: Annotated[
        datetime | None, Query(description="Start timestamp (ISO 8601)")
    ] = None,
    end_date: Annotated[
        datetime | None, Query(description="End timestamp (ISO 8601)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> AuditEventListResponse:
    """Return paginated, immutable audit trail events for superadmins."""
    # Normalize naive datetimes to UTC and validate ordering
    if start_date and start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=UTC)
    if end_date and end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must not be later than end_date",
        )

    service = AdminAuditLogService(session)
    result = await service.list_audit_events(
        action=action,
        actor_id=actor_id,
        actor_email=actor_email,
        subject_id=subject_id,
        subject_email=subject_email,
        ticket_ref=ticket_ref,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    # Log the sensitive read itself (INV-25.2)
    audit = AuditEvent(
        action="audit_log.view",
        actor_id=auth.user_id,
        subject_id=None,
        ip_address=get_real_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        diff_payload={
            "endpoint": str(request.url.path),
            "filters": {
                "action": action,
                "actor_id": str(actor_id) if actor_id else None,
                "actor_email": actor_email,
                "subject_id": str(subject_id) if subject_id else None,
                "subject_email": subject_email,
                "ticket_ref": ticket_ref,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "limit": limit,
            "offset": offset,
            "returned_total": result["total"],
        },
    )
    session.add(audit)
    await session.commit()

    return AuditEventListResponse(**result)
