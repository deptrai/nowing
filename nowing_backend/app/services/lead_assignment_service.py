"""Dynamic Round-Robin Lead Assignment Service (Story 24.3 / AC-2 / INV-24.4).

Manages:
- Automated Round-Robin lead distribution across active workspace members.
- Excludes deactivated (status!='ACTIVE'), paused (is_accepting_leads=False), or capped members.
- Redis-persisted monotonic round-robin cursor per workspace.
- Batch lead assignment and manual reassignment with activity audit logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Lead, LeadActivityLog, LeadAssignment, WorkspaceMembership


class NoEligibleAssigneeError(Exception):
    """Raised when no active member is eligible to receive leads in the workspace."""

    def __init__(self, workspace_id: int, reason: str = "No eligible members") -> None:
        self.workspace_id = workspace_id
        self.reason = reason
        super().__init__(f"No eligible assignee for workspace {workspace_id}: {reason}")


@dataclass
class MemberLeadCapacity:
    """Represents a member's lead load and capacity for distribution."""

    user_id: UUID
    workspace_id: int
    status: str = "ACTIVE"
    is_accepting_leads: bool = True
    current_leads: int = 0
    max_capacity: int = 50


@dataclass
class AssignmentResult:
    """Outcome of assigning a lead to a team member."""

    lead_id: UUID
    workspace_id: int
    assigned_to_user_id: UUID | None
    assigned_by: str = "auto_round_robin"
    status: str = "assigned"


@dataclass
class BatchAssignmentResult:
    """Outcome of a batch lead assignment operation."""

    workspace_id: int
    total_assigned: int
    assignments: list[AssignmentResult] = field(default_factory=list)
    unassigned_lead_ids: list[UUID] = field(default_factory=list)


class LeadAssignmentService:
    """Service distributing leads fairly across workspace sales representatives."""

    def __init__(
        self,
        session: AsyncSession | Any = None,
        redis_client: Any = None,
    ) -> None:
        self.session = session
        self.redis = redis_client
        self._in_memory_cursors: dict[int, int] = {}

    async def get_eligible_members(
        self,
        *,
        workspace_id: int,
    ) -> list[MemberLeadCapacity]:
        """Query active and available members sorted deterministically by user_id."""
        if self.session is None:
            return []

        # Query all active memberships that are accepting leads
        stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.status == "ACTIVE",
            WorkspaceMembership.is_accepting_leads.is_(True),
        )
        res = await self.session.execute(stmt)
        memberships = res.scalars().all()

        user_ids = [m.user_id for m in memberships]

        # Single aggregated count for all members; exclude terminal stages (lost/won).
        counts: dict[UUID, int] = dict.fromkeys(user_ids, 0)
        if user_ids:
            count_stmt = (
                select(Lead.assigned_to_user_id, func.count(Lead.id))
                .where(
                    Lead.workspace_id == workspace_id,
                    Lead.assigned_to_user_id.in_(user_ids),
                    Lead.status.notin_(["lost", "won"]),
                )
                .group_by(Lead.assigned_to_user_id)
            )
            count_res = await self.session.execute(count_stmt)
            for uid, cnt in count_res.all():
                counts[uid] = cnt

        eligible: list[MemberLeadCapacity] = []
        for m in sorted(memberships, key=lambda x: str(x.user_id)):
            active_count = counts.get(m.user_id, 0)
            max_cap = m.lead_capacity if m.lead_capacity is not None else 50
            if active_count < max_cap:
                eligible.append(
                    MemberLeadCapacity(
                        user_id=m.user_id,
                        workspace_id=workspace_id,
                        status=m.status or "ACTIVE",
                        is_accepting_leads=m.is_accepting_leads,
                        current_leads=active_count,
                        max_capacity=max_cap,
                    )
                )

        return eligible

    async def assign_lead(
        self,
        *,
        workspace_id: int,
        lead_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> AssignmentResult:
        """Assign a single lead using round-robin distribution."""
        if self.session is None:
            raise NoEligibleAssigneeError(workspace_id=workspace_id)

        lead = await self.session.get(Lead, (lead_id, workspace_id))
        if lead is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Lead {lead_id} not found",
            )

        eligible = await self.get_eligible_members(workspace_id=workspace_id)
        if not eligible:
            raise NoEligibleAssigneeError(workspace_id=workspace_id)

        # Monotonic cursor increment via Redis (or in-memory fallback)
        cursor_key = f"lead_assignment:cursor:{workspace_id}"
        if self.redis is not None:
            raw_idx = await self.redis.incr(cursor_key)
            idx = (raw_idx - 1) % len(eligible)
        else:
            current = self._in_memory_cursors.get(workspace_id, 0) + 1
            self._in_memory_cursors[workspace_id] = current
            idx = (current - 1) % len(eligible)

        assignee = eligible[idx]

        # Update the lead owner and record the audit trail.
        lead.assigned_to_user_id = assignee.user_id

        assignment = LeadAssignment(
            workspace_id=workspace_id,
            lead_id=lead_id,
            assigned_to_user_id=assignee.user_id,
            assigned_by_user_id=actor_user_id,
            assigned_by="auto_round_robin",
            status="assigned",
        )
        self.session.add(assignment)

        log = LeadActivityLog(
            workspace_id=workspace_id,
            lead_id=lead_id,
            actor_user_id=actor_user_id,
            activity_type="assigned",
            title=f"Tự động phân bổ lead cho nhân viên {assignee.user_id}",
            details={
                "assigned_to_user_id": str(assignee.user_id),
                "assigned_by": "auto_round_robin",
            },
        )
        self.session.add(log)

        return AssignmentResult(
            lead_id=lead_id,
            workspace_id=workspace_id,
            assigned_to_user_id=assignee.user_id,
            assigned_by="auto_round_robin",
            status="assigned",
        )

    async def assign_leads_batch(
        self,
        *,
        workspace_id: int,
        lead_ids: list[UUID],
    ) -> BatchAssignmentResult:
        """Distribute a batch of leads atomically across active members."""
        assignments: list[AssignmentResult] = []
        unassigned: list[UUID] = []

        for lead_id in lead_ids:
            try:
                res = await self.assign_lead(
                    workspace_id=workspace_id,
                    lead_id=lead_id,
                )
                assignments.append(res)
            except NoEligibleAssigneeError:
                unassigned.append(lead_id)

        return BatchAssignmentResult(
            workspace_id=workspace_id,
            total_assigned=len(assignments),
            assignments=assignments,
            unassigned_lead_ids=unassigned,
        )

    async def reassign_lead(
        self,
        *,
        workspace_id: int,
        lead_id: UUID,
        target_user_id: UUID,
        actor_user_id: UUID,
        reason: str = "manual_reassignment",
    ) -> AssignmentResult:
        """Manually reassign a lead to a specific team member and log reason."""
        if self.session is None:
            raise NoEligibleAssigneeError(workspace_id=workspace_id)

        lead = await self.session.get(Lead, (lead_id, workspace_id))
        if lead is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Lead {lead_id} not found",
            )

        # Validate the target member is active and accepting leads.
        target_membership = await self.session.get(
            WorkspaceMembership, (workspace_id, target_user_id)
        )
        if target_membership is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Target member {target_user_id} not found",
            )
        if (
            target_membership.status != "ACTIVE"
            or not target_membership.is_accepting_leads
        ):
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Target member {target_user_id} is not accepting leads",
            )

        # Check manual reassignment would not exceed the member's lead capacity.
        count_stmt = select(func.count(Lead.id)).where(
            Lead.workspace_id == workspace_id,
            Lead.assigned_to_user_id == target_user_id,
            Lead.status.notin_(["lost", "won"]),
        )
        count_res = await self.session.execute(count_stmt)
        current_leads = count_res.scalar() or 0
        max_capacity = (
            target_membership.lead_capacity
            if target_membership.lead_capacity is not None
            else 50
        )
        if current_leads >= max_capacity:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Target member {target_user_id} is at lead capacity ({current_leads}/{max_capacity})",
            )

        lead.assigned_to_user_id = target_user_id

        assignment = LeadAssignment(
            workspace_id=workspace_id,
            lead_id=lead_id,
            assigned_to_user_id=target_user_id,
            assigned_by_user_id=actor_user_id,
            assigned_by="manual_reassignment",
            status="assigned",
            reason=reason,
        )
        self.session.add(assignment)

        log = LeadActivityLog(
            workspace_id=workspace_id,
            lead_id=lead_id,
            actor_user_id=actor_user_id,
            activity_type="reassigned",
            title=f"Chuyển lead cho nhân viên {target_user_id}",
            details={
                "target_user_id": str(target_user_id),
                "actor_user_id": str(actor_user_id),
                "reason": reason,
            },
        )
        self.session.add(log)

        return AssignmentResult(
            lead_id=lead_id,
            workspace_id=workspace_id,
            assigned_to_user_id=target_user_id,
            assigned_by="manual_reassignment",
            status="assigned",
        )


lead_assignment_service = LeadAssignmentService()
