"""Service for querying and exporting security audit trail logs (Story 25.6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db import AuditEvent, User


class AdminAuditLogService:
    """Provides filtered, paginated query access to immutable audit_events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_audit_events(
        self,
        *,
        action: str | None = None,
        actor_id: uuid.UUID | None = None,
        actor_email: str | None = None,
        subject_id: uuid.UUID | None = None,
        subject_email: str | None = None,
        ticket_ref: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query audit events with user email outerjoins and filters."""
        clamped_limit = max(1, min(200, limit))
        clamped_offset = max(0, offset)

        actor_user = aliased(User, name="actor_user")
        subject_user = aliased(User, name="subject_user")

        # Build base filter conditions
        conditions = []
        if action:
            conditions.append(AuditEvent.action == action)
        if actor_id:
            conditions.append(AuditEvent.actor_id == actor_id)
        if subject_id:
            conditions.append(AuditEvent.subject_id == subject_id)
        if ticket_ref:
            conditions.append(AuditEvent.ticket_ref.ilike(f"%{ticket_ref}%"))
        if start_date:
            conditions.append(AuditEvent.created_at >= start_date)
        if end_date:
            conditions.append(AuditEvent.created_at <= end_date)
        if actor_email:
            conditions.append(actor_user.email.ilike(f"%{actor_email}%"))
        if subject_email:
            conditions.append(subject_user.email.ilike(f"%{subject_email}%"))

        # Count total matching rows
        count_stmt = (
            select(func.count(AuditEvent.id))
            .outerjoin(actor_user, AuditEvent.actor_id == actor_user.id)
            .outerjoin(subject_user, AuditEvent.subject_id == subject_user.id)
        )
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        # Query items
        stmt = (
            select(
                AuditEvent.id,
                AuditEvent.action,
                AuditEvent.actor_id,
                AuditEvent.subject_id,
                AuditEvent.ticket_ref,
                AuditEvent.ip_address,
                AuditEvent.user_agent,
                AuditEvent.diff_payload,
                AuditEvent.created_at,
                actor_user.email.label("actor_email"),
                subject_user.email.label("subject_email"),
            )
            .outerjoin(actor_user, AuditEvent.actor_id == actor_user.id)
            .outerjoin(subject_user, AuditEvent.subject_id == subject_user.id)
        )
        if conditions:
            stmt = stmt.where(*conditions)

        stmt = (
            stmt.order_by(AuditEvent.created_at.desc())
            .limit(clamped_limit)
            .offset(clamped_offset)
        )

        rows = (await self.session.execute(stmt)).all()

        items = []
        for r in rows:
            diff = getattr(r, "diff_payload", None) or {}
            endpoint = diff.get("endpoint") if isinstance(diff, dict) else None
            items.append(
                {
                    "id": getattr(r, "id", None),
                    "action": getattr(r, "action", None),
                    "actor_id": getattr(r, "actor_id", None),
                    "subject_id": getattr(r, "subject_id", None),
                    "actor_email": getattr(r, "actor_email", None),
                    "subject_email": getattr(r, "subject_email", None),
                    "ticket_ref": getattr(r, "ticket_ref", None),
                    "ip_address": getattr(r, "ip_address", None),
                    "user_agent": getattr(r, "user_agent", None),
                    "diff_payload": getattr(r, "diff_payload", None),
                    "created_at": getattr(r, "created_at", None),
                    "endpoint": endpoint,
                }
            )

        return {
            "items": items,
            "total": total,
            "limit": clamped_limit,
            "offset": clamped_offset,
        }
