"""Service for managing In-App Broadcast Announcements (Story 25.6)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AuditEvent, BroadcastAnnouncement, Workspace
from app.schemas.broadcasts import BroadcastStatus

MAX_TARGET_WORKSPACE_IDS = 100


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Attach UTC to naive datetimes for safe comparison."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


logger = logging.getLogger(__name__)


class BroadcastService:
    """Provides announcement CRUD, status calculation, workspace targeting, and audit logging."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _validate_target_workspaces(
        self, ws_ids: list[int], *, required: bool = False
    ) -> list[int]:
        """Validate workspace IDs are positive, deduplicated, bounded, and exist."""
        ws_ids = list(dict.fromkeys(ws_ids))

        if len(ws_ids) > MAX_TARGET_WORKSPACE_IDS:
            raise ValueError(
                f"target_workspace_ids must not exceed {MAX_TARGET_WORKSPACE_IDS} items"
            )

        if any(ws_id <= 0 for ws_id in ws_ids):
            raise ValueError("workspace IDs must be positive integers")

        if required and not ws_ids:
            raise ValueError(
                "target_workspace_ids must contain at least one workspace ID when target_all is false"
            )

        if ws_ids:
            stmt = select(Workspace.id).where(Workspace.id.in_(ws_ids))
            existing_res = await self.session.execute(stmt)
            existing_ids = set(existing_res.scalars().all())
            missing = set(ws_ids) - existing_ids
            if missing:
                raise ValueError(f"Workspace IDs do not exist: {sorted(missing)}")

        return ws_ids

    @staticmethod
    def compute_status(
        *,
        is_active: bool,
        starts_at: datetime,
        expires_at: datetime | None,
        now: datetime | None = None,
    ) -> BroadcastStatus:
        """Compute status based on active flag and start/expiry windows."""
        current_time = now or datetime.now(UTC)

        # Ensure timezone-aware comparison
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)

        if is_active and starts_at > current_time:
            return "scheduled"
        if expires_at and expires_at <= current_time:
            return "expired"
        if not is_active:
            return "inactive"
        return "active"

    async def list_broadcasts(self) -> dict[str, Any]:
        """List all broadcasts with derived status for admin console."""
        stmt = select(BroadcastAnnouncement).order_by(
            BroadcastAnnouncement.created_at.desc()
        )
        rows = (await self.session.execute(stmt)).scalars().all()

        now = datetime.now(UTC)
        items = []
        for r in rows:
            status_val = self.compute_status(
                is_active=r.is_active,
                starts_at=r.starts_at,
                expires_at=r.expires_at,
                now=now,
            )
            items.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "message": r.message,
                    "banner_type": r.banner_type,
                    "target_all": r.target_all,
                    "target_workspace_ids": r.target_workspace_ids or [],
                    "starts_at": r.starts_at,
                    "expires_at": r.expires_at,
                    "dismissible": r.dismissible,
                    "is_active": r.is_active,
                    "status": status_val,
                    "created_by_user_id": r.created_by_user_id,
                    "updated_by_user_id": r.updated_by_user_id,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
            )

        return {"items": items, "total": len(items)}

    async def create_broadcast(
        self,
        *,
        title: str,
        message: str,
        banner_type: str = "info",
        target_all: bool = True,
        target_workspace_ids: list[int] | None = None,
        starts_at: datetime | None = None,
        expires_at: datetime | None = None,
        dismissible: bool = True,
        is_active: bool = True,
        actor_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        endpoint: str | None = None,
    ) -> BroadcastAnnouncement:
        """Create a new broadcast announcement with validation and audit logging."""
        ws_ids = await self._validate_target_workspaces(
            target_workspace_ids or [], required=not target_all
        )

        start_time = _ensure_aware(starts_at) or datetime.now(UTC)
        end_time = _ensure_aware(expires_at)
        if end_time and end_time <= start_time:
            raise ValueError("expires_at must be strictly after starts_at")

        announcement = BroadcastAnnouncement(
            title=title,
            message=message,
            banner_type=banner_type,
            target_all=target_all,
            target_workspace_ids=ws_ids,
            starts_at=start_time,
            expires_at=end_time,
            dismissible=dismissible,
            is_active=is_active,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        self.session.add(announcement)
        await self.session.flush()

        audit = AuditEvent(
            action="broadcast.create",
            actor_id=actor_id,
            subject_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            diff_payload={
                "broadcast_id": str(announcement.id),
                "title": title,
                "banner_type": banner_type,
                "target_all": target_all,
                "target_workspace_ids": ws_ids,
                "starts_at": start_time.isoformat() if start_time else None,
                "expires_at": end_time.isoformat() if end_time else None,
                "dismissible": dismissible,
                "is_active": is_active,
                "endpoint": endpoint,
            },
        )
        self.session.add(audit)
        await self.session.flush()

        return announcement

    async def update_broadcast(
        self,
        *,
        broadcast_id: uuid.UUID,
        update_data: dict[str, Any],
        actor_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        endpoint: str | None = None,
    ) -> BroadcastAnnouncement | None:
        """Update an existing broadcast announcement and log diff."""
        announcement = await self.session.get(BroadcastAnnouncement, broadcast_id)
        if not announcement:
            return None

        # Validate target workspace IDs if updated
        target_all = update_data.get("target_all", announcement.target_all)
        raw_ws_ids = update_data.get(
            "target_workspace_ids", announcement.target_workspace_ids
        )
        ws_ids = await self._validate_target_workspaces(
            raw_ws_ids or [], required=not target_all
        )

        new_starts = _ensure_aware(update_data.get("starts_at", announcement.starts_at))
        new_expires = _ensure_aware(
            update_data.get("expires_at", announcement.expires_at)
        )
        if new_expires and new_starts and new_expires <= new_starts:
            raise ValueError("expires_at must be strictly after starts_at")

        # Apply the validated workspace list when it was part of the request
        if "target_workspace_ids" in update_data:
            announcement.target_workspace_ids = ws_ids

        diff = {}
        for k, v in update_data.items():
            if not hasattr(announcement, k):
                continue

            # Allow explicit null to clear nullable fields only
            if v is None and k == "expires_at":
                old_val = getattr(announcement, k)
                if old_val != v:
                    diff[k] = {"old": str(old_val), "new": str(v)}
                    setattr(announcement, k, v)
                continue

            if v is None:
                # Skip other unset/null fields; do not clear non-nullable columns
                continue

            old_val = getattr(announcement, k)
            if old_val != v:
                diff[k] = {"old": str(old_val), "new": str(v)}
                setattr(announcement, k, v)

        announcement.updated_by_user_id = actor_id
        announcement.updated_at = datetime.now(UTC)

        audit = AuditEvent(
            action="broadcast.update",
            actor_id=actor_id,
            subject_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            diff_payload={
                "broadcast_id": str(broadcast_id),
                "diff": diff,
                "endpoint": endpoint,
            },
        )
        self.session.add(audit)
        await self.session.flush()

        return announcement

    async def delete_broadcast(
        self,
        *,
        broadcast_id: uuid.UUID,
        actor_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        endpoint: str | None = None,
    ) -> bool:
        """Delete a broadcast announcement and record audit log."""
        announcement = await self.session.get(BroadcastAnnouncement, broadcast_id)
        if not announcement:
            return False

        title = announcement.title
        await self.session.delete(announcement)

        audit = AuditEvent(
            action="broadcast.delete",
            actor_id=actor_id,
            subject_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            diff_payload={
                "broadcast_id": str(broadcast_id),
                "title": title,
                "endpoint": endpoint,
            },
        )
        self.session.add(audit)
        await self.session.flush()

        return True

    async def get_active_broadcasts(
        self, workspace_id: int | None = None
    ) -> list[BroadcastAnnouncement]:
        """Fetch active announcements matching current time and optional workspace filter."""
        now = datetime.now(UTC)

        stmt = select(BroadcastAnnouncement).where(
            BroadcastAnnouncement.is_active.is_(True),
            BroadcastAnnouncement.starts_at <= now,
            or_(
                BroadcastAnnouncement.expires_at.is_(None),
                BroadcastAnnouncement.expires_at > now,
            ),
        )

        if workspace_id is not None:
            stmt = stmt.where(
                or_(
                    BroadcastAnnouncement.target_all.is_(True),
                    BroadcastAnnouncement.target_workspace_ids.contains([workspace_id]),
                )
            )
        else:
            stmt = stmt.where(BroadcastAnnouncement.target_all.is_(True))

        return list((await self.session.execute(stmt)).scalars().all())
