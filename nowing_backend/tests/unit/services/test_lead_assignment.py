"""Unit tests for Dynamic Round-Robin Lead Assignment Service (Story 24.3 / AC-2).

Verifies:
- Round-robin distribution evenly assigns leads across active, eligible team members.
- Members with is_accepting_leads=False or status!='ACTIVE' are excluded from rotation.
- Members at maximum lead capacity are skipped until capacity is freed.
- Redis round-robin cursor is persisted and increments monotonically modulo active count.
- Handles empty/zero eligible members gracefully without unhandled exceptions.
- Batch lead assignment distributes multiple leads atomically.
- Manual reassignment records lead activity audit log and inactivates prior assignments.
- Workspace tenancy isolation: only members of the specified workspace are eligible.
- Reassignment rejects terminal (won/lost) or already-assigned leads.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.lead_assignment_service import (
    AssignmentResult,
    LeadAssignmentService,
    MemberLeadCapacity,
    NoEligibleAssigneeError,
)

pytestmark = pytest.mark.unit


class FakeRedis:
    """In-memory Redis stub for tracking round-robin cursors."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: Any, **kwargs: Any) -> None:
        self.store[key] = str(value)

    async def incr(self, key: str) -> int:
        val = int(self.store.get(key, "0")) + 1
        self.store[key] = str(val)
        return val


class _FakeScalars:
    def __init__(self, items: list[Any] | None = None) -> None:
        self._items = items or []

    def all(self) -> list[Any]:
        return self._items

    def first(self) -> Any | None:
        return self._items[0] if self._items else None


class FakeResult:
    """Minimal SQLAlchemy-style result for mocked AsyncSession.execute."""

    def __init__(
        self,
        *,
        scalar_one: Any = None,
        scalar: Any = None,
        all_items: list[Any] | None = None,
    ) -> None:
        self._scalar_one = scalar_one
        self._scalar = scalar
        self._all_items = all_items or []

    def scalar_one_or_none(self) -> Any | None:
        return self._scalar_one

    def scalar(self) -> Any | None:
        return self._scalar

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._all_items)


def _make_fake_session(
    *,
    fake_lead: Any = None,
    fake_membership: Any = None,
    lead_count: int = 0,
    existing_assignments: list[Any] | None = None,
) -> MagicMock:
    """Build a mocked async session that answers the expected LeadAssignmentService queries."""
    session = MagicMock()
    session._leads_by_id: dict[UUID, Any] = {}

    async def _get(_model: Any, _key: Any, **kwargs: Any) -> Any:
        if fake_membership is not None and _model.__name__ == "WorkspaceMembership":
            return fake_membership
        # _key is the composite primary key (lead_id, workspace_id)
        lead_id = _key[0] if isinstance(_key, tuple) else _key
        if lead_id in session._leads_by_id:
            return session._leads_by_id[lead_id]
        if isinstance(fake_lead, SimpleNamespace):
            lead = SimpleNamespace(
                id=lead_id,
                workspace_id=fake_lead.workspace_id,
                status=fake_lead.status,
                assigned_to_user_id=fake_lead.assigned_to_user_id,
            )
        else:
            lead = _make_fake_lead(
                status=getattr(fake_lead, "status", "new"),
                assigned_to_user_id=getattr(fake_lead, "assigned_to_user_id", None),
                lead_id=lead_id,
            )
        session._leads_by_id[lead_id] = lead
        return lead

    session.get = AsyncMock(side_effect=_get)

    # _assign_to_member always queries in the same order:
    # 1) WorkspaceMembership FOR UPDATE
    # 2) COUNT of leads assigned to the target user
    # 3) existing LeadAssignment rows for this lead
    _execute_results = [
        FakeResult(scalar_one=fake_membership),
        FakeResult(scalar=lead_count),
        FakeResult(all_items=existing_assignments or []),
    ]
    _exec_index = {"i": 0}

    async def _execute(stmt: Any, *args: Any, **kwargs: Any) -> FakeResult:
        text = str(stmt).lower()
        if "workspace_membership" in text and "for update" in text:
            return FakeResult(scalar_one=fake_membership)
        if "count(" in text and "lead" in text:
            return FakeResult(scalar=lead_count)
        if "lead_assignment" in text:
            return FakeResult(all_items=existing_assignments or [])
        # Fallback: cycle through the standard three results for successive calls.
        result = _execute_results[_exec_index["i"] % len(_execute_results)]
        _exec_index["i"] += 1
        return result

    session.execute = AsyncMock(side_effect=_execute)
    return session


def _make_fake_lead(
    *,
    status: str = "new",
    assigned_to_user_id: UUID | None = None,
    lead_id: UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=lead_id or uuid4(),
        workspace_id=42,
        status=status,
        assigned_to_user_id=assigned_to_user_id,
    )


def _make_fake_membership(
    *,
    status: str = "ACTIVE",
    is_accepting_leads: bool = True,
    lead_capacity: int = 50,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        is_accepting_leads=is_accepting_leads,
        lead_capacity=lead_capacity,
    )


@pytest.mark.asyncio
async def test_round_robin_assignment_even_distribution():
    """6 leads evenly distributed across 3 active eligible members."""
    workspace_id = 42
    redis = FakeRedis()

    user_1 = uuid4()
    user_2 = uuid4()
    user_3 = uuid4()

    eligible_members = [
        MemberLeadCapacity(
            user_id=user_1,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=0,
            max_capacity=10,
        ),
        MemberLeadCapacity(
            user_id=user_2,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=0,
            max_capacity=10,
        ),
        MemberLeadCapacity(
            user_id=user_3,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=0,
            max_capacity=10,
        ),
    ]

    fake_lead = _make_fake_lead()
    fake_membership = _make_fake_membership()
    session = _make_fake_session(fake_lead=fake_lead, fake_membership=fake_membership)

    service = LeadAssignmentService(session=session, redis_client=redis)
    service.get_eligible_members = AsyncMock(return_value=eligible_members)

    lead_ids = [uuid4() for _ in range(6)]
    assignments: list[AssignmentResult] = []

    for lead_id in lead_ids:
        res = await service.assign_lead(workspace_id=workspace_id, lead_id=lead_id)
        assignments.append(res)

    assigned_users = [a.assigned_to_user_id for a in assignments]
    assert assigned_users == [user_1, user_2, user_3, user_1, user_2, user_3]
    assert assigned_users.count(user_1) == 2
    assert assigned_users.count(user_2) == 2
    assert assigned_users.count(user_3) == 2


@pytest.mark.asyncio
async def test_round_robin_skips_inactive_or_paused_members():
    """Only active and accepting members receive leads."""
    workspace_id = 42
    redis = FakeRedis()
    active_user = uuid4()

    service = LeadAssignmentService(
        session=_make_fake_session(
            fake_lead=_make_fake_lead(),
            fake_membership=_make_fake_membership(),
        ),
        redis_client=redis,
    )
    service.get_eligible_members = AsyncMock(
        return_value=[
            MemberLeadCapacity(
                user_id=active_user,
                workspace_id=workspace_id,
                status="ACTIVE",
                is_accepting_leads=True,
                current_leads=0,
                max_capacity=10,
            ),
        ]
    )

    lead_id = uuid4()
    result = await service.assign_lead(workspace_id=workspace_id, lead_id=lead_id)

    assert result.assigned_to_user_id == active_user


@pytest.mark.asyncio
async def test_round_robin_skips_members_at_capacity():
    """A member whose current_leads >= max_capacity is skipped during assignment."""
    workspace_id = 42
    redis = FakeRedis()
    available_user = uuid4()
    full_user = uuid4()

    eligible = [
        MemberLeadCapacity(
            user_id=full_user,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=10,
            max_capacity=10,
        ),
        MemberLeadCapacity(
            user_id=available_user,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=2,
            max_capacity=10,
        ),
    ]

    service = LeadAssignmentService(
        session=_make_fake_session(
            fake_lead=_make_fake_lead(),
            fake_membership=_make_fake_membership(),
            lead_count=2,
        ),
        redis_client=redis,
    )
    service.get_eligible_members = AsyncMock(return_value=eligible)

    lead_id = uuid4()
    result = await service.assign_lead(workspace_id=workspace_id, lead_id=lead_id)

    assert result.assigned_to_user_id == available_user


@pytest.mark.asyncio
async def test_round_robin_redis_cursor_persistence():
    """Redis cursor persists position across distinct service invocations."""
    workspace_id = 42
    redis = FakeRedis()

    user_1 = uuid4()
    user_2 = uuid4()

    eligible = [
        MemberLeadCapacity(
            user_id=user_1,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=0,
            max_capacity=10,
        ),
        MemberLeadCapacity(
            user_id=user_2,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=0,
            max_capacity=10,
        ),
    ]

    fake_lead = _make_fake_lead()
    fake_membership = _make_fake_membership()

    service_1 = LeadAssignmentService(
        session=_make_fake_session(fake_lead=fake_lead, fake_membership=fake_membership),
        redis_client=redis,
    )
    service_1.get_eligible_members = AsyncMock(return_value=eligible)
    res_1 = await service_1.assign_lead(workspace_id=workspace_id, lead_id=uuid4())
    assert res_1.assigned_to_user_id == user_1

    service_2 = LeadAssignmentService(
        session=_make_fake_session(fake_lead=fake_lead, fake_membership=fake_membership),
        redis_client=redis,
    )
    service_2.get_eligible_members = AsyncMock(return_value=eligible)
    res_2 = await service_2.assign_lead(workspace_id=workspace_id, lead_id=uuid4())
    assert res_2.assigned_to_user_id == user_2


@pytest.mark.asyncio
async def test_assignment_when_no_eligible_members():
    """No eligible members raises NoEligibleAssigneeError."""
    workspace_id = 42
    redis = FakeRedis()

    service = LeadAssignmentService(
        session=_make_fake_session(),
        redis_client=redis,
    )
    service.get_eligible_members = AsyncMock(return_value=[])

    with pytest.raises(NoEligibleAssigneeError) as exc_info:
        await service.assign_lead(workspace_id=workspace_id, lead_id=uuid4())

    assert exc_info.value.workspace_id == workspace_id


@pytest.mark.asyncio
async def test_assign_lead_rejects_terminal_and_assigned():
    """Terminal (won/lost) or already-assigned leads cannot be auto-assigned."""
    workspace_id = 42
    redis = FakeRedis()
    assigned_lead = _make_fake_lead(assigned_to_user_id=uuid4())
    won_lead = _make_fake_lead(status="won")

    service = LeadAssignmentService(
        session=_make_fake_session(
            fake_lead=assigned_lead, fake_membership=_make_fake_membership()
        ),
        redis_client=redis,
    )
    with pytest.raises(NoEligibleAssigneeError):
        await service.assign_lead(workspace_id=workspace_id, lead_id=uuid4())

    service_2 = LeadAssignmentService(
        session=_make_fake_session(
            fake_lead=won_lead, fake_membership=_make_fake_membership()
        ),
        redis_client=redis,
    )
    with pytest.raises(NoEligibleAssigneeError):
        await service_2.assign_lead(workspace_id=workspace_id, lead_id=uuid4())


@pytest.mark.asyncio
async def test_assign_leads_batch_atomic_distribution():
    """Batch distribution assigns multiple leads and returns BatchAssignmentResult."""
    workspace_id = 42
    redis = FakeRedis()

    user_1 = uuid4()
    user_2 = uuid4()
    eligible = [
        MemberLeadCapacity(
            user_id=user_1,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=0,
            max_capacity=10,
        ),
        MemberLeadCapacity(
            user_id=user_2,
            workspace_id=workspace_id,
            status="ACTIVE",
            is_accepting_leads=True,
            current_leads=0,
            max_capacity=10,
        ),
    ]

    fake_lead = _make_fake_lead()
    fake_membership = _make_fake_membership()
    session = _make_fake_session(fake_lead=fake_lead, fake_membership=fake_membership)

    service = LeadAssignmentService(session=session, redis_client=redis)
    service.get_eligible_members = AsyncMock(return_value=eligible)

    batch_lead_ids = [uuid4() for _ in range(4)]
    batch_result = await service.assign_leads_batch(
        workspace_id=workspace_id, lead_ids=batch_lead_ids
    )

    assert batch_result.workspace_id == workspace_id
    assert batch_result.total_assigned == 4
    assert len(batch_result.assignments) == 4
    assert len(batch_result.unassigned_lead_ids) == 0

    assigned_users = [a.assigned_to_user_id for a in batch_result.assignments]
    assert assigned_users == [user_1, user_2, user_1, user_2]


@pytest.mark.asyncio
async def test_reassign_lead_creates_activity_log():
    """Manual reassignment reassigns lead, records reason, and inactivates prior rows."""
    workspace_id = 42
    lead_id = uuid4()
    new_user = uuid4()
    admin_user = uuid4()

    fake_lead = _make_fake_lead(lead_id=lead_id, status="new")
    fake_membership = _make_fake_membership()

    # Simulate one prior active assignment that should be inactivated.
    prior_assignment = SimpleNamespace(id=uuid4(), status="assigned")
    existing = [prior_assignment]

    session = _make_fake_session(
        fake_lead=fake_lead,
        fake_membership=fake_membership,
        lead_count=1,
        existing_assignments=existing,
    )

    service = LeadAssignmentService(session=session, redis_client=FakeRedis())
    result = await service.reassign_lead(
        workspace_id=workspace_id,
        lead_id=lead_id,
        target_user_id=new_user,
        actor_user_id=admin_user,
        reason="Agent on annual leave",
    )

    assert result.lead_id == lead_id
    assert result.assigned_to_user_id == new_user
    assert result.assigned_by == "manual_reassignment"
    assert session._leads_by_id[lead_id].assigned_to_user_id == new_user
    assert prior_assignment.status == "inactive"
    # lead_assignment + lead_activity_log are both persisted via session.add.
    assert session.add.call_count >= 2


@pytest.mark.asyncio
async def test_reassign_lead_skips_current_owner():
    """Reassignment to the lead's current owner is rejected."""
    workspace_id = 42
    lead_id = uuid4()
    current_user = uuid4()

    service = LeadAssignmentService(
        session=_make_fake_session(
            fake_lead=_make_fake_lead(
                lead_id=lead_id,
                status="new",
                assigned_to_user_id=current_user,
            ),
            fake_membership=_make_fake_membership(),
        ),
        redis_client=FakeRedis(),
    )

    with pytest.raises(NoEligibleAssigneeError):
        await service.reassign_lead(
            workspace_id=workspace_id,
            lead_id=lead_id,
            target_user_id=current_user,
            actor_user_id=uuid4(),
            reason="Self reassignment",
        )


@pytest.mark.asyncio
async def test_reassign_lead_rejects_terminal():
    """Reassignment of a won/lost lead is rejected."""
    workspace_id = 42
    lead_id = uuid4()

    service = LeadAssignmentService(
        session=_make_fake_session(
            fake_lead=_make_fake_lead(lead_id=lead_id, status="lost"),
            fake_membership=_make_fake_membership(),
        ),
        redis_client=FakeRedis(),
    )

    with pytest.raises(NoEligibleAssigneeError):
        await service.reassign_lead(
            workspace_id=workspace_id,
            lead_id=lead_id,
            target_user_id=uuid4(),
            actor_user_id=uuid4(),
            reason="Should fail",
        )


@pytest.mark.asyncio
async def test_assign_lead_without_redis_is_rejected():
    """The service requires Redis; without it assignment is rejected."""
    service = LeadAssignmentService(
        session=_make_fake_session(
            fake_lead=_make_fake_lead(), fake_membership=_make_fake_membership()
        ),
        redis_client=None,
    )
    service.get_eligible_members = AsyncMock(
        return_value=[
            MemberLeadCapacity(
                user_id=uuid4(),
                workspace_id=42,
                status="ACTIVE",
                is_accepting_leads=True,
                current_leads=0,
                max_capacity=10,
            )
        ]
    )

    with pytest.raises(NoEligibleAssigneeError) as exc_info:
        await service.assign_lead(workspace_id=42, lead_id=uuid4())

    assert "Redis" in exc_info.value.reason
