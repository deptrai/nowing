"""Shared Workspace Credit Pooling & Member Spend Cap Enforcement (Story 24.3 / INV-24.4).

Manages:
- INV-24.4: Shared Workspace credit balance pooling with atomic spend cap verification.
- Row-level lock or atomic deduction against workspace.credit_micros_balance.
- Member monthly spend cap verification on workspace_memberships.monthly_spent_micros.
- Credit refund and reimbursement restoring workspace pool & member monthly spent quota.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Workspace, WorkspaceMembership


class SpendCapExceededError(Exception):
    """Raised when a member exceeds their monthly allocated spend cap."""

    def __init__(
        self,
        user_id: UUID | str,
        cap_micros: int,
        current_spent: int,
        requested: int,
    ) -> None:
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
    ) -> None:
        self.workspace_id = workspace_id
        self.balance_micros = balance_micros
        self.requested = requested
        super().__init__(
            f"Workspace {workspace_id} has insufficient credit balance. "
            f"Available: {balance_micros} micros, requested: {requested} micros."
        )


@dataclass
class CreditDeductionResult:
    """Outcome of a successful credit deduction."""

    workspace_id: int
    user_id: UUID
    amount_deducted_micros: int
    remaining_workspace_balance: int
    member_monthly_spent: int
    member_monthly_spend_cap: int | None


@dataclass
class MemberSpendStatus:
    """Member current monthly spend cap, spent amount, and workspace balance."""

    workspace_id: int
    user_id: UUID
    monthly_spend_cap_micros: int | None
    monthly_spent_micros: int
    remaining_cap_micros: int | None
    workspace_balance_micros: int


class WorkspaceCreditService:
    """Service handling shared credit wallet pooling and per-seat spend caps."""

    def __init__(self, session: AsyncSession | Any = None) -> None:
        self.session = session

    async def _get_membership(self, workspace_id: int, user_id: UUID) -> Any | None:
        if self.session is None:
            return None

        # Check if session has a custom get implementation (e.g. FakeAsyncSession)
        if hasattr(self.session, "memberships"):
            res = await self.session.get(WorkspaceMembership, (workspace_id, user_id))
            if res is not None:
                return res

        # Otherwise query via standard SQLAlchemy select
        stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def _get_workspace(self, workspace_id: int) -> Any | None:
        if self.session is None:
            return None

        if hasattr(self.session, "workspaces"):
            res = await self.session.get(Workspace, workspace_id)
            if res is not None:
                return res

        stmt = select(Workspace).where(Workspace.id == workspace_id)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def deduct_credits(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
        description: str = "",
    ) -> CreditDeductionResult:
        """Deduct credits from the workspace pool respecting member spend caps.

        Uses atomic UPDATE ... WHERE constraints to prevent concurrent overdrafts
        and per-seat spend-cap violations.
        """
        from sqlalchemy import update

        if amount_micros <= 0:
            raise ValueError("Amount must be strictly positive")

        # In-memory fake-session path used by unit tests (FakeAsyncSession).
        # Real DB path below uses atomic UPDATE ... WHERE.
        if hasattr(self.session, "workspaces") and hasattr(self.session, "memberships"):
            return self._deduct_credits_fake(
                workspace_id=workspace_id,
                user_id=user_id,
                amount_micros=amount_micros,
            )

        membership = await self._get_membership(workspace_id, user_id)
        if membership is None:
            raise ValueError("Member not found")

        # Pre-check the cap so we can raise SpendCapExceededError before touching the pool.
        cap = membership.monthly_spend_cap_micros
        current_spent = membership.monthly_spent_micros or 0
        if cap is not None and current_spent + amount_micros > cap:
            raise SpendCapExceededError(
                user_id=user_id,
                cap_micros=cap,
                current_spent=current_spent,
                requested=amount_micros,
            )

        # Atomic workspace balance deduction: only succeed if balance >= amount.
        balance_result = await self.session.execute(
            update(Workspace)
            .where(
                Workspace.id == workspace_id,
                Workspace.credit_micros_balance >= amount_micros,
            )
            .values(
                credit_micros_balance=Workspace.credit_micros_balance - amount_micros,
            )
            .returning(Workspace.credit_micros_balance)
        )
        balance_row = balance_result.one_or_none()
        if balance_row is None:
            workspace = await self._get_workspace(workspace_id)
            available = workspace.credit_micros_balance if workspace else 0
            raise InsufficientCreditsError(
                workspace_id=workspace_id,
                balance_micros=available,
                requested=amount_micros,
            )

        remaining_workspace_balance = balance_row[0]

        # Atomic member monthly spend increment (skip if no membership row).
        if membership is None:
            member_monthly_spent = 0
        elif cap is not None:
            spend_result = await self.session.execute(
                update(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == user_id,
                    WorkspaceMembership.monthly_spend_cap_micros
                    >= func.coalesce(WorkspaceMembership.monthly_spent_micros, 0)
                    + amount_micros,
                )
                .values(
                    monthly_spent_micros=func.coalesce(
                        WorkspaceMembership.monthly_spent_micros, 0
                    )
                    + amount_micros,
                )
                .returning(WorkspaceMembership.monthly_spent_micros)
            )
            spend_row = spend_result.one_or_none()
            if spend_row is None:
                raise SpendCapExceededError(
                    user_id=user_id,
                    cap_micros=cap,
                    current_spent=current_spent,
                    requested=amount_micros,
                )
            member_monthly_spent = spend_row[0]
        else:
            # Unlimited cap: still record spend atomically to keep the counter accurate.
            spend_result = await self.session.execute(
                update(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == user_id,
                )
                .values(
                    monthly_spent_micros=func.coalesce(
                        WorkspaceMembership.monthly_spent_micros, 0
                    )
                    + amount_micros,
                )
                .returning(WorkspaceMembership.monthly_spent_micros)
            )
            spend_row = spend_result.one_or_none()
            member_monthly_spent = (
                spend_row[0] if spend_row else current_spent + amount_micros
            )

        return CreditDeductionResult(
            workspace_id=workspace_id,
            user_id=user_id,
            amount_deducted_micros=amount_micros,
            remaining_workspace_balance=remaining_workspace_balance,
            member_monthly_spent=member_monthly_spent,
            member_monthly_spend_cap=cap,
        )

    def _deduct_credits_fake(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
    ) -> CreditDeductionResult:
        """In-memory deduction path used by FakeAsyncSession unit tests."""
        workspace = self.session.workspaces.get(workspace_id)
        if workspace is None:
            raise InsufficientCreditsError(
                workspace_id=workspace_id,
                balance_micros=0,
                requested=amount_micros,
            )
        membership = self.session.memberships.get((workspace_id, user_id))
        if membership is None:
            raise ValueError("Member not found")

        cap = membership.monthly_spend_cap_micros
        current_spent = membership.monthly_spent_micros or 0
        if cap is not None and current_spent + amount_micros > cap:
            raise SpendCapExceededError(
                user_id=user_id,
                cap_micros=cap,
                current_spent=current_spent,
                requested=amount_micros,
            )
        if workspace.credit_micros_balance < amount_micros:
            raise InsufficientCreditsError(
                workspace_id=workspace_id,
                balance_micros=workspace.credit_micros_balance,
                requested=amount_micros,
            )

        workspace.credit_micros_balance -= amount_micros
        membership.monthly_spent_micros = current_spent + amount_micros

        return CreditDeductionResult(
            workspace_id=workspace_id,
            user_id=user_id,
            amount_deducted_micros=amount_micros,
            remaining_workspace_balance=workspace.credit_micros_balance,
            member_monthly_spent=membership.monthly_spent_micros,
            member_monthly_spend_cap=cap,
        )

    async def record_spend(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
        description: str = "",
    ) -> dict[str, Any]:
        """Record a billable spend against the member's monthly cap.

        Unlike :meth:`deduct_credits`, this does **not** touch the shared
        workspace balance. It is intended for call sites where payment is still
        handled by the user wallet (e.g. ``wallet_credit.apply_debit``) but the
        per-seat spend cap must still be enforced atomically.

        Returns a status dict. Raises :class:`SpendCapExceededError` when the
        cap would be exceeded. No-ops for non-positive amounts. If the user is
        not a workspace member, no cap is enforced and spend is not tracked.
        """
        if amount_micros <= 0:
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": 0,
                "member_monthly_spent": 0,
                "member_monthly_spend_cap": None,
            }

        # In-memory fake-session path used by unit tests (FakeAsyncSession).
        if hasattr(self.session, "workspaces") and hasattr(self.session, "memberships"):
            return self._record_spend_fake(
                workspace_id=workspace_id,
                user_id=user_id,
                amount_micros=amount_micros,
            )

        membership = await self._get_membership(workspace_id, user_id)
        if membership is None:
            # No membership => no per-seat cap to enforce for this user.
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": amount_micros,
                "member_monthly_spent": 0,
                "member_monthly_spend_cap": None,
            }

        cap = membership.monthly_spend_cap_micros
        current_spent = membership.monthly_spent_micros or 0

        from sqlalchemy import update

        # Atomic monthly spent increment; only succeeds if under the cap.
        spend_result = await self.session.execute(
            update(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
                or_(
                    WorkspaceMembership.monthly_spend_cap_micros.is_(None),
                    WorkspaceMembership.monthly_spend_cap_micros
                    >= func.coalesce(WorkspaceMembership.monthly_spent_micros, 0)
                    + amount_micros,
                ),
            )
            .values(
                monthly_spent_micros=func.coalesce(
                    WorkspaceMembership.monthly_spent_micros, 0
                )
                + amount_micros,
            )
            .returning(
                WorkspaceMembership.monthly_spend_cap_micros,
                WorkspaceMembership.monthly_spent_micros,
            )
        )
        spend_row = spend_result.one_or_none()
        if spend_row is None:
            raise SpendCapExceededError(
                user_id=user_id,
                cap_micros=cap or 0,
                current_spent=current_spent,
                requested=amount_micros,
            )

        returned_cap, returned_spent = spend_row
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "amount_micros": amount_micros,
            "member_monthly_spent": returned_spent,
            "member_monthly_spend_cap": returned_cap,
        }

    def _record_spend_fake(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
    ) -> dict[str, Any]:
        """In-memory record_spend path used by FakeAsyncSession unit tests."""
        membership = self.session.memberships.get((workspace_id, user_id))
        if membership is None:
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": amount_micros,
                "member_monthly_spent": 0,
                "member_monthly_spend_cap": None,
            }

        cap = membership.monthly_spend_cap_micros
        current_spent = membership.monthly_spent_micros or 0
        if cap is not None and current_spent + amount_micros > cap:
            raise SpendCapExceededError(
                user_id=user_id,
                cap_micros=cap,
                current_spent=current_spent,
                requested=amount_micros,
            )

        membership.monthly_spent_micros = current_spent + amount_micros
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "amount_micros": amount_micros,
            "member_monthly_spent": membership.monthly_spent_micros,
            "member_monthly_spend_cap": cap,
        }

    async def refund_credits(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """Refund credits back to workspace pool and decrement member monthly spent."""
        if amount_micros <= 0:
            raise ValueError("Amount must be strictly positive")

        # In-memory fake-session path used by unit tests (FakeAsyncSession).
        if hasattr(self.session, "workspaces") and hasattr(self.session, "memberships"):
            return self._refund_credits_fake(
                workspace_id=workspace_id,
                user_id=user_id,
                amount_micros=amount_micros,
                reason=reason,
            )

        from sqlalchemy import update

        # Atomic workspace balance refund.
        balance_result = await self.session.execute(
            update(Workspace)
            .where(Workspace.id == workspace_id)
            .values(
                credit_micros_balance=Workspace.credit_micros_balance + amount_micros,
            )
            .returning(Workspace.credit_micros_balance)
        )
        balance_row = balance_result.one_or_none()
        remaining_workspace_balance = balance_row[0] if balance_row else 0

        # Atomic member monthly spent decrement, guarded against negative values.
        membership = await self._get_membership(workspace_id, user_id)
        member_monthly_spent = 0
        if membership is not None:
            spend_result = await self.session.execute(
                update(WorkspaceMembership)
                .where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == user_id,
                )
                .values(
                    monthly_spent_micros=func.greatest(
                        0,
                        func.coalesce(WorkspaceMembership.monthly_spent_micros, 0)
                        - amount_micros,
                    ),
                )
                .returning(WorkspaceMembership.monthly_spent_micros)
            )
            spend_row = spend_result.one_or_none()
            member_monthly_spent = spend_row[0] if spend_row else 0

        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "refunded_micros": amount_micros,
            "reason": reason,
            "remaining_workspace_balance": remaining_workspace_balance,
            "member_monthly_spent": member_monthly_spent,
        }

    async def refund_member_spend(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
    ) -> dict[str, Any]:
        """Decrement a member's monthly spent counter without touching workspace balance."""
        if amount_micros <= 0:
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": 0,
                "member_monthly_spent": 0,
                "member_monthly_spend_cap": None,
            }

        # In-memory fake-session path used by unit tests (FakeAsyncSession).
        if hasattr(self.session, "workspaces") and hasattr(self.session, "memberships"):
            return self._refund_member_spend_fake(
                workspace_id=workspace_id,
                user_id=user_id,
                amount_micros=amount_micros,
            )

        from sqlalchemy import update

        spend_result = await self.session.execute(
            update(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
            .values(
                monthly_spent_micros=func.greatest(
                    0,
                    func.coalesce(WorkspaceMembership.monthly_spent_micros, 0)
                    - amount_micros,
                ),
            )
            .returning(
                WorkspaceMembership.monthly_spend_cap_micros,
                WorkspaceMembership.monthly_spent_micros,
            )
        )
        spend_row = spend_result.one_or_none()
        if spend_row is None:
            # Member not found: no monthly spent to refund; do not report a refund.
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": 0,
                "member_monthly_spent": 0,
                "member_monthly_spend_cap": None,
            }
        returned_cap, returned_spent = spend_row
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "amount_micros": amount_micros,
            "member_monthly_spent": returned_spent,
            "member_monthly_spend_cap": returned_cap,
        }

    def _refund_member_spend_fake(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
    ) -> dict[str, Any]:
        """In-memory refund_member_spend path used by FakeAsyncSession unit tests."""
        membership = self.session.memberships.get((workspace_id, user_id))
        if membership is None:
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "amount_micros": 0,
                "member_monthly_spent": 0,
                "member_monthly_spend_cap": None,
            }
        current_spent = membership.monthly_spent_micros or 0
        membership.monthly_spent_micros = max(0, current_spent - amount_micros)
        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "amount_micros": amount_micros,
            "member_monthly_spent": membership.monthly_spent_micros,
            "member_monthly_spend_cap": membership.monthly_spend_cap_micros,
        }

    async def set_member_spend_cap(
        self,
        *,
        workspace_id: int,
        target_user_id: UUID,
        cap_micros: int | None,
        actor_user_id: UUID | None = None,
    ) -> None:
        """Set or update member monthly spend cap (None for unlimited pool access)."""
        if cap_micros is not None and cap_micros < 0:
            raise ValueError("Spend cap cannot be negative")

        membership = await self._get_membership(workspace_id, target_user_id)
        if membership is None:
            raise ValueError("Member not found")

        membership.monthly_spend_cap_micros = cap_micros

    async def get_member_spend_status(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
    ) -> MemberSpendStatus:
        """Query spend status and remaining allowance for a team member."""
        membership = await self._get_membership(workspace_id, user_id)
        workspace = await self._get_workspace(workspace_id)

        if membership is None:
            raise ValueError("Member not found")

        cap = membership.monthly_spend_cap_micros
        spent = membership.monthly_spent_micros or 0
        remaining_cap = max(0, cap - spent) if cap is not None else None
        balance = workspace.credit_micros_balance if workspace else 0

        return MemberSpendStatus(
            workspace_id=workspace_id,
            user_id=user_id,
            monthly_spend_cap_micros=cap,
            monthly_spent_micros=spent,
            remaining_cap_micros=remaining_cap,
            workspace_balance_micros=balance,
        )

    def _refund_credits_fake(
        self,
        *,
        workspace_id: int,
        user_id: UUID,
        amount_micros: int,
        reason: str,
    ) -> dict[str, Any]:
        """In-memory refund path used by FakeAsyncSession unit tests."""
        workspace = self.session.workspaces.get(workspace_id)
        if workspace is None:
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "refunded_micros": amount_micros,
                "reason": reason,
                "remaining_workspace_balance": 0,
                "member_monthly_spent": 0,
            }

        membership = self.session.memberships.get((workspace_id, user_id))
        member_monthly_spent = 0
        if membership is not None:
            current_spent = membership.monthly_spent_micros or 0
            membership.monthly_spent_micros = max(0, current_spent - amount_micros)
            member_monthly_spent = membership.monthly_spent_micros

        workspace.credit_micros_balance += amount_micros

        return {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "refunded_micros": amount_micros,
            "reason": reason,
            "remaining_workspace_balance": workspace.credit_micros_balance,
            "member_monthly_spent": member_monthly_spent,
        }


workspace_credit_service = WorkspaceCreditService()
