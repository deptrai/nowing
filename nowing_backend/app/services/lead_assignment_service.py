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
        if self.redis is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason="Redis is required for round-robin cursor",
            )

        lead = await self.session.get(Lead, (lead_id, workspace_id))
        if lead is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Lead {lead_id} not found",
            )
        if lead.status in ("lost", "won") or lead.assigned_to_user_id is not None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Lead {lead_id} is terminal or already assigned",
            )

        eligible = await self.get_eligible_members(workspace_id=workspace_id)
        if not eligible:
            raise NoEligibleAssigneeError(workspace_id=workspace_id)

        assignee = await self._select_next_assignee(
            workspace_id=workspace_id,
            eligible=eligible,
        )

        return await self._assign_to_member(
            workspace_id=workspace_id,
            lead=lead,
            target_user_id=assignee.user_id,
            actor_user_id=actor_user_id,
            assigned_by="auto_round_robin",
            reason=None,
            exclude_lead_id=None,
        )

    async def _select_next_assignee(
        self,
        *,
        workspace_id: int,
        eligible: list[MemberLeadCapacity],
    ) -> MemberLeadCapacity:
        """Advance the monotonic Redis cursor and return the selected member."""
        if self.redis is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason="Redis is required for round-robin cursor",
            )

        cursor_key = f"lead_assignment:cursor:{workspace_id}"
        raw_idx = await self.redis.incr(cursor_key)
        idx = (raw_idx - 1) % len(eligible)

        # If the cursor lands on a member whose local counter is already at capacity,
        # walk forward to the next member. The Redis slot is consumed regardless.
        tries = 0
        while eligible[idx].current_leads >= eligible[idx].max_capacity and tries < len(eligible):
            idx = (idx + 1) % len(eligible)
            tries += 1
        if tries == len(eligible):
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason="All eligible members are at lead capacity",
            )

        return eligible[idx]

    async def _assign_to_member(
        self,
        *,
        workspace_id: int,
        lead: Lead,
        target_user_id: UUID,
        actor_user_id: UUID | None,
        assigned_by: str,
        reason: str | None,
        exclude_lead_id: UUID | None,
    ) -> AssignmentResult:
        """Persist a lead assignment under an atomic capacity guard."""
        if self.session is None:
            raise NoEligibleAssigneeError(workspace_id=workspace_id)

        # Atomic capacity guard: lock the target membership row and re-count leads.
        membership = (
            await self.session.execute(
                select(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == target_user_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

        if membership is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Target member {target_user_id} not found",
            )
        if (
            membership.status != "ACTIVE"
            or not membership.is_accepting_leads
        ):
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Target member {target_user_id} is not accepting leads",
            )

        max_capacity = membership.lead_capacity if membership.lead_capacity is not None else 50

        count_filters = [
            Lead.workspace_id == workspace_id,
            Lead.assigned_to_user_id == target_user_id,
            Lead.status.notin_(["lost", "won"]),
        ]
        if exclude_lead_id is not None:
            count_filters.append(Lead.id != exclude_lead_id)

        count_stmt = select(func.count(Lead.id)).where(*count_filters)
        count_res = await self.session.execute(count_stmt)
        current_leads = count_res.scalar() or 0

        if current_leads >= max_capacity:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Target member {target_user_id} is at lead capacity ({current_leads}/{max_capacity})",
            )

        # Inactivate any existing active assignment records for this lead before
        # inserting the new one (prevents duplicate active LeadAssignment rows).
        existing = (
            await self.session.execute(
                select(LeadAssignment).where(
                    LeadAssignment.workspace_id == workspace_id,
                    LeadAssignment.lead_id == lead.id,
                    LeadAssignment.status == "assigned",
                )
            )
        ).scalars().all()
        for prior in existing:
            prior.status = "inactive"

        # Update the lead owner and record the audit trail.
        lead.assigned_to_user_id = target_user_id

        assignment = LeadAssignment(
            workspace_id=workspace_id,
            lead_id=lead.id,
            assigned_to_user_id=target_user_id,
            assigned_by_user_id=actor_user_id,
            assigned_by=assigned_by,
            status="assigned",
            reason=reason,
        )
        self.session.add(assignment)

        activity_type = "reassigned" if assigned_by == "manual_reassignment" else "assigned"
        title = (
            f"Chuyển lead cho nhân viên {target_user_id}"
            if assigned_by == "manual_reassignment"
            else f"Tự động phân bổ lead cho nhân viên {target_user_id}"
        )
        log = LeadActivityLog(
            workspace_id=workspace_id,
            lead_id=lead.id,
            actor_user_id=actor_user_id,
            activity_type=activity_type,
            title=title,
            details={
                "assigned_to_user_id": str(target_user_id),
                "assigned_by": assigned_by,
                "reason": reason,
            },
        )
        self.session.add(log)

        return AssignmentResult(
            lead_id=lead.id,
            workspace_id=workspace_id,
            assigned_to_user_id=target_user_id,
            assigned_by=assigned_by,
            status="assigned",
        )

    async def assign_leads_batch(
        self,
        *,
        workspace_id: int,
        lead_ids: list[UUID],
    ) -> BatchAssignmentResult:
        """Distribute a batch of leads atomically across active members."""
        if self.session is None:
            raise NoEligibleAssigneeError(workspace_id=workspace_id)
        if self.redis is None:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason="Redis is required for round-robin cursor",
            )

        eligible = await self.get_eligible_members(workspace_id=workspace_id)

        assignments: list[AssignmentResult] = []
        unassigned: list[UUID] = []

        for lead_id in lead_ids:
            lead = await self.session.get(Lead, (lead_id, workspace_id))
            if lead is None:
                unassigned.append(lead_id)
                continue
            if lead.status in ("lost", "won") or lead.assigned_to_user_id is not None:
                unassigned.append(lead_id)
                continue
            if not eligible:
                unassigned.append(lead_id)
                continue

            try:
                assignee = await self._select_next_assignee(
                    workspace_id=workspace_id,
                    eligible=eligible,
                )
            except NoEligibleAssigneeError:
                unassigned.append(lead_id)
                continue

            try:
                result = await self._assign_to_member(
                    workspace_id=workspace_id,
                    lead=lead,
                    target_user_id=assignee.user_id,
                    actor_user_id=None,
                    assigned_by="auto_round_robin",
                    reason=None,
                    exclude_lead_id=None,
                )
                assignments.append(result)
                # Update the in-memory counter so the next lead in the batch sees
                # the capacity change without an extra COUNT round-trip.
                assignee.current_leads += 1
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
        if lead.status in ("lost", "won"):
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason=f"Lead {lead_id} is terminal",
            )
        if lead.assigned_to_user_id == target_user_id:
            raise NoEligibleAssigneeError(
                workspace_id=workspace_id,
                reason="Cannot reassign lead to its current owner",
            )

        return await self._assign_to_member(
            workspace_id=workspace_id,
            lead=lead,
            target_user_id=target_user_id,
            actor_user_id=actor_user_id,
            assigned_by="manual_reassignment",
            reason=reason,
            exclude_lead_id=lead.id,
        )
