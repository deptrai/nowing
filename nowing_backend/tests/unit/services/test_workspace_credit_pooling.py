"""Unit tests for Workspace Credit Pooling & Member Spend Cap Enforcement (Story 24.3 / INV-24.4).

Verifies:
- INV-24.4: Shared Workspace credit balance pooling with atomic spend cap verification.
- Deduction within member spend cap succeeds and deducts from shared workspace balance.
- Deduction exceeding member spend cap raises SpendCapExceededError and prevents pool deduction.
- Deduction exceeding workspace balance raises InsufficientCreditsError (no overdraft).
- Member with no spend cap (None) draws directly from shared workspace pool.
- Member spend cap configuration, negative cap validation, and spend status queries.
- Credit refund / reimbursement restores both workspace pool and member monthly spent quota.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

# Try importing domain service / models or fall back to stub definitions for Red-Phase
try:
    from app.services.workspace_credit_service import (
        CreditDeductionResult,
        InsufficientCreditsError,
        MemberSpendStatus,
        SpendCapExceededError,
        WorkspaceCreditService,
    )
except ImportError:
    # Stubs to define expected contracts for Red-Phase execution
    class SpendCapExceededError(Exception):
        """Raised when a member exceeds their monthly allocated spend cap."""

        def __init__(
            self,
            user_id: UUID | str,
            cap_micros: int,
            current_spent: int,
            requested: int,
        ):
            self.user_id = user_id
            self.cap_micros = cap_micros
            self.current_spent = current_spent
            self.requested = requested
            super().__init__(
                f"Member {user_id} exceeded monthly spend cap of {cap_micros} micros. "
                f"Current spent: {current_spent}, requested: {requested}."
            )

    class InsufficientCreditsError(Exception):
        """Raised when workspace has insufficient pooled credit balance."""

        def __init__(
            self,
            workspace_id: int,
            balance_micros: int,
            requested: int,
        ):
            self.workspace_id = workspace_id
            self.balance_micros = balance_micros
            self.requested = requested
            super().__init__(
                f"Workspace {workspace_id} has insufficient credit balance. "
                f"Available: {balance_micros} micros, requested: {requested} micros."
            )

    @dataclass
    class CreditDeductionResult:
        workspace_id: int
        user_id: UUID
        amount_deducted_micros: int
        remaining_workspace_balance: int
        member_monthly_spent: int
        member_monthly_spend_cap: int | None

    @dataclass
    class MemberSpendStatus:
        workspace_id: int
        user_id: UUID
        monthly_spend_cap_micros: int | None
        monthly_spent_micros: int
        remaining_cap_micros: int | None
        workspace_balance_micros: int

    class WorkspaceCreditService:
        """Stub WorkspaceCreditService to be implemented in Story 24.3."""

        def __init__(self, session: Any = None) -> None:
            self.session = session

        async def deduct_credits(
            self,
            *,
            workspace_id: int,
            user_id: UUID,
            amount_micros: int,
            description: str = "",
        ) -> CreditDeductionResult:
            raise NotImplementedError("To be implemented in Story 24.3")

        async def refund_credits(
            self,
            *,
            workspace_id: int,
            user_id: UUID,
            amount_micros: int,
            reason: str = "",
        ) -> dict[str, Any]:
            raise NotImplementedError("To be implemented in Story 24.3")

        async def set_member_spend_cap(
            self,
            *,
            workspace_id: int,
            target_user_id: UUID,
            cap_micros: int | None,
            actor_user_id: UUID | None = None,
        ) -> None:
            raise NotImplementedError("To be implemented in Story 24.3")

        async def get_member_spend_status(
            self,
            *,
            workspace_id: int,
            user_id: UUID,
        ) -> MemberSpendStatus:
            raise NotImplementedError("To be implemented in Story 24.3")


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test Fixtures & Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeWorkspace:
    id: int
    credit_micros_balance: int = 1_000_000


@dataclass
class FakeWorkspaceMembership:
    workspace_id: int
    user_id: UUID
    role_id: int | None = 1
    is_owner: bool = False
    monthly_spend_cap_micros: int | None = 500_000
    monthly_spent_micros: int = 0


class FakeAsyncSession:
    """In-memory stub async session for unit testing."""

    def __init__(self) -> None:
        self.workspaces: dict[int, FakeWorkspace] = {}
        self.memberships: dict[tuple[int, UUID], FakeWorkspaceMembership] = {}
        self.committed = False
        self.rolled_back = False

    async def get(self, model: Any, ident: Any) -> Any:
        if hasattr(ident, "__len__") and len(ident) == 2:
            return self.memberships.get(tuple(ident))
        return self.workspaces.get(ident)

    async def execute(self, stmt: Any) -> Any:
        return MagicMock()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    def add(self, obj: Any) -> None:
        if isinstance(obj, FakeWorkspace):
            self.workspaces[obj.id] = obj
        elif isinstance(obj, FakeWorkspaceMembership):
            self.memberships[(obj.workspace_id, obj.user_id)] = obj


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deduct_credits_success_within_spend_cap():
    """Test successful credit deduction when member spend is within monthly cap."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id, credit_micros_balance=1_000_000
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=300_000,
        monthly_spent_micros=100_000,
    )

    service = WorkspaceCreditService(session=session)
    result = await service.deduct_credits(
        workspace_id=workspace_id,
        user_id=user_id,
        amount_micros=150_000,
        description="Batch lead phone waterfall enrichment",
    )

    assert result.workspace_id == workspace_id
    assert result.user_id == user_id
    assert result.amount_deducted_micros == 150_000
    assert result.remaining_workspace_balance == 850_000
    assert result.member_monthly_spent == 250_000
    assert result.member_monthly_spend_cap == 300_000


@pytest.mark.asyncio
async def test_deduct_credits_fails_when_member_spend_cap_exceeded():
    """Test SpendCapExceededError is raised and pool is NOT deducted when member cap exceeded."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id, credit_micros_balance=5_000_000
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=200_000,
        monthly_spent_micros=180_000,
    )

    service = WorkspaceCreditService(session=session)

    # Attempting to spend 50_000 would bring total to 230_000 > 200_000 cap
    with pytest.raises(SpendCapExceededError) as exc_info:
        await service.deduct_credits(
            workspace_id=workspace_id,
            user_id=user_id,
            amount_micros=50_000,
            description="AI enrichment request",
        )

    assert exc_info.value.user_id == user_id
    assert exc_info.value.cap_micros == 200_000
    assert exc_info.value.current_spent == 180_000
    assert exc_info.value.requested == 50_000
    # Invariant: Workspace balance MUST remain untouched
    assert session.workspaces[workspace_id].credit_micros_balance == 5_000_000
    assert session.memberships[(workspace_id, user_id)].monthly_spent_micros == 180_000


@pytest.mark.asyncio
async def test_deduct_credits_fails_when_workspace_balance_insufficient():
    """Test InsufficientCreditsError is raised when pooled balance is less than required."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id, credit_micros_balance=80_000
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=1_000_000,
        monthly_spent_micros=0,
    )

    service = WorkspaceCreditService(session=session)

    with pytest.raises(InsufficientCreditsError) as exc_info:
        await service.deduct_credits(
            workspace_id=workspace_id,
            user_id=user_id,
            amount_micros=100_000,
            description="Large bulk export enrichment",
        )

    assert exc_info.value.workspace_id == workspace_id
    assert exc_info.value.balance_micros == 80_000
    assert exc_info.value.requested == 100_000
    # Invariant: No negative balance (no overdraft)
    assert session.workspaces[workspace_id].credit_micros_balance == 80_000
    assert session.memberships[(workspace_id, user_id)].monthly_spent_micros == 0


@pytest.mark.asyncio
async def test_deduct_credits_unlimited_member_spends_from_pool():
    """Test member with monthly_spend_cap_micros=None has uncapped spending up to workspace balance."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id, credit_micros_balance=2_000_000
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=None,  # Uncapped
        monthly_spent_micros=500_000,
    )

    service = WorkspaceCreditService(session=session)
    result = await service.deduct_credits(
        workspace_id=workspace_id,
        user_id=user_id,
        amount_micros=400_000,
        description="Uncapped member operation",
    )

    assert result.remaining_workspace_balance == 1_600_000
    assert result.member_monthly_spent == 900_000
    assert result.member_monthly_spend_cap is None


@pytest.mark.asyncio
async def test_deduct_credits_zero_or_negative_amount_validation():
    """Test that zero or negative deduction requests raise ValueError."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id, credit_micros_balance=1_000_000
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=500_000,
        monthly_spent_micros=0,
    )

    service = WorkspaceCreditService(session=session)

    with pytest.raises(ValueError, match="Amount must be strictly positive"):
        await service.deduct_credits(
            workspace_id=workspace_id,
            user_id=user_id,
            amount_micros=0,
        )

    with pytest.raises(ValueError, match="Amount must be strictly positive"):
        await service.deduct_credits(
            workspace_id=workspace_id,
            user_id=user_id,
            amount_micros=-50_000,
        )


@pytest.mark.asyncio
async def test_set_member_spend_cap_updates_membership():
    """Test admin/owner setting member monthly spend cap."""
    workspace_id = 100
    target_user_id = uuid4()
    session = FakeAsyncSession()
    session.memberships[(workspace_id, target_user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=target_user_id,
        monthly_spend_cap_micros=200_000,
        monthly_spent_micros=50_000,
    )

    service = WorkspaceCreditService(session=session)
    await service.set_member_spend_cap(
        workspace_id=workspace_id,
        target_user_id=target_user_id,
        cap_micros=1_000_000,
    )

    assert (
        session.memberships[(workspace_id, target_user_id)].monthly_spend_cap_micros
        == 1_000_000
    )


@pytest.mark.asyncio
async def test_set_member_spend_cap_rejects_negative_value():
    """Test that setting a negative spend cap raises ValueError."""
    workspace_id = 100
    target_user_id = uuid4()
    session = FakeAsyncSession()
    session.memberships[(workspace_id, target_user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=target_user_id,
        monthly_spend_cap_micros=200_000,
    )

    service = WorkspaceCreditService(session=session)
    with pytest.raises(ValueError, match="Spend cap cannot be negative"):
        await service.set_member_spend_cap(
            workspace_id=workspace_id,
            target_user_id=target_user_id,
            cap_micros=-100_000,
        )


@pytest.mark.asyncio
async def test_get_member_spend_status():
    """Test query for member spend status and remaining allowance."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id, credit_micros_balance=2_500_000
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=400_000,
        monthly_spent_micros=150_000,
    )

    service = WorkspaceCreditService(session=session)
    status = await service.get_member_spend_status(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert status.workspace_id == workspace_id
    assert status.user_id == user_id
    assert status.monthly_spend_cap_micros == 400_000
    assert status.monthly_spent_micros == 150_000
    assert status.remaining_cap_micros == 250_000
    assert status.workspace_balance_micros == 2_500_000


@pytest.mark.asyncio
async def test_refund_credits_restores_pool_and_decrements_member_spent():
    """Test refunding credits restores pooled balance and decrements member spent quota."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id, credit_micros_balance=800_000
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=500_000,
        monthly_spent_micros=200_000,
    )

    service = WorkspaceCreditService(session=session)
    res = await service.refund_credits(
        workspace_id=workspace_id,
        user_id=user_id,
        amount_micros=50_000,
        reason="Invalid lead phone auto-refund",
    )

    assert session.workspaces[workspace_id].credit_micros_balance == 850_000
    assert session.memberships[(workspace_id, user_id)].monthly_spent_micros == 150_000
    assert res.get("refunded_micros") == 50_000


@pytest.mark.asyncio
async def test_record_spend_increments_monthly_spent_without_touching_balance():
    """record_spend tracks spend for cap enforcement while leaving the shared pool untouched."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id,
        credit_micros_balance=1_000_000,
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=500_000,
        monthly_spent_micros=100_000,
    )

    service = WorkspaceCreditService(session=session)
    res = await service.record_spend(
        workspace_id=workspace_id,
        user_id=user_id,
        amount_micros=50_000,
    )

    assert session.memberships[(workspace_id, user_id)].monthly_spent_micros == 150_000
    assert session.workspaces[workspace_id].credit_micros_balance == 1_000_000
    assert res["member_monthly_spent"] == 150_000
    assert res["amount_micros"] == 50_000


@pytest.mark.asyncio
async def test_record_spend_allows_unlimited_when_cap_is_none():
    """Members with no cap can record spend without hitting a ceiling."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id,
        credit_micros_balance=1_000_000,
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=None,
        monthly_spent_micros=0,
    )

    service = WorkspaceCreditService(session=session)
    res = await service.record_spend(
        workspace_id=workspace_id,
        user_id=user_id,
        amount_micros=900_000,
    )

    assert session.memberships[(workspace_id, user_id)].monthly_spent_micros == 900_000
    assert res["member_monthly_spend_cap"] is None


@pytest.mark.asyncio
async def test_record_spend_rejects_amount_exceeding_cap():
    """record_spend raises SpendCapExceededError when the cap would be breached."""
    workspace_id = 100
    user_id = uuid4()
    session = FakeAsyncSession()
    session.workspaces[workspace_id] = FakeWorkspace(
        id=workspace_id,
        credit_micros_balance=1_000_000,
    )
    session.memberships[(workspace_id, user_id)] = FakeWorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_spend_cap_micros=500_000,
        monthly_spent_micros=400_000,
    )

    service = WorkspaceCreditService(session=session)
    with pytest.raises(SpendCapExceededError):
        await service.record_spend(
            workspace_id=workspace_id,
            user_id=user_id,
            amount_micros=150_000,
        )
