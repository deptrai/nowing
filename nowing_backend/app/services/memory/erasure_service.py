"""Service for GDPR Right-to-Delete and bulk memory deletion with audit trail logging (Story 28.5)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AuditEvent, Memory
from app.tenant_context import set_request_tenant_context

logger = logging.getLogger(__name__)


class MemoryErasureService:
    """Handles right-to-delete single and bulk memory erasures with audit logs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_memory(
        self,
        *,
        workspace_id: int,
        memory_id: int,
        actor: Any | None = None,
        reason: str | None = None,
    ) -> bool:
        """Erase a single memory row and write an audit event."""
        await set_request_tenant_context(
            self.session, workspace_id=workspace_id, memory_id=memory_id
        )
        result = await self.session.execute(
            select(Memory).where(
                Memory.id == memory_id,
                Memory.workspace_id == workspace_id,
            )
        )
        memory = result.scalar_one_or_none()
        if memory is None:
            return False

        actor_id = getattr(actor, "id", None)
        if isinstance(actor_id, str):
            try:
                actor_id = UUID(actor_id)
            except ValueError:
                actor_id = None

        await self.session.delete(memory)
        self._record_audit_event(
            action="memory_delete",
            workspace_id=workspace_id,
            actor_id=actor_id,
            diff_payload={"memory_id": memory_id, "reason": reason or "user_request"},
        )
        await self.session.commit()
        return True

    def _record_audit_event(
        self,
        *,
        action: str,
        workspace_id: int,
        actor_id: UUID | None,
        diff_payload: dict[str, Any],
    ) -> None:
        payload = dict(diff_payload)
        payload["workspace_id"] = workspace_id
        audit = AuditEvent(
            action=action,
            actor_id=actor_id,
            diff_payload=payload,
        )
        self.session.add(audit)

    async def count_matching_memories(
        self,
        *,
        workspace_id: int,
        source_type: str | None = None,
        source_id: int | None = None,
        source_entity_type: str | None = None,
    ) -> int:
        await set_request_tenant_context(self.session, workspace_id=workspace_id)
        stmt = select(func.count(Memory.id)).where(Memory.workspace_id == workspace_id)
        if source_type:
            stmt = stmt.where(Memory.source_type == source_type)
        if source_id is not None:
            stmt = stmt.where(Memory.source_id == source_id)
        if source_entity_type:
            stmt = stmt.where(Memory.source_entity_type == source_entity_type)
        res = await self.session.execute(stmt)
        return res.scalar() or 0

    async def bulk_delete_memories(
        self,
        *,
        workspace_id: int,
        source_type: str | None = None,
        source_id: int | None = None,
        source_entity_type: str | None = None,
        actor: Any | None = None,
        dry_run: bool = False,
        batch_size: int = 1000,
    ) -> dict[str, Any]:
        """Perform chunked deletion of matching memories with audit logging."""
        count = await self.count_matching_memories(
            workspace_id=workspace_id,
            source_type=source_type,
            source_id=source_id,
            source_entity_type=source_entity_type,
        )

        if dry_run:
            return {"dry_run": True, "affected_count": count}

        actor_id = getattr(actor, "id", None)
        if isinstance(actor_id, str):
            try:
                actor_id = UUID(actor_id)
            except ValueError:
                actor_id = None

        deleted_total = 0
        while True:
            # Select next batch of IDs to delete
            id_stmt = select(Memory.id).where(Memory.workspace_id == workspace_id)
            if source_type:
                id_stmt = id_stmt.where(Memory.source_type == source_type)
            if source_id is not None:
                id_stmt = id_stmt.where(Memory.source_id == source_id)
            if source_entity_type:
                id_stmt = id_stmt.where(Memory.source_entity_type == source_entity_type)

            id_stmt = id_stmt.limit(batch_size)
            id_res = await self.session.execute(id_stmt)
            ids = list(id_res.scalars().all())
            if not ids:
                break

            del_stmt = delete(Memory).where(Memory.id.in_(ids))
            await self.session.execute(del_stmt)
            await self.session.commit()
            deleted_total += len(ids)

        self._record_audit_event(
            action="bulk_delete",
            workspace_id=workspace_id,
            actor_id=actor_id,
            diff_payload={
                "affected_count": deleted_total,
                "source_type": source_type,
                "source_id": source_id,
                "source_entity_type": source_entity_type,
            },
        )
        await self.session.commit()

        return {"dry_run": False, "affected_count": deleted_total}
