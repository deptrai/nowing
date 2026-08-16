"""Integration tests for Shared Workspace Credit Pooling Concurrency & Race Condition Prevention (Story 24.3 / INV-24.4).

Verifies:
- INV-24.4: Shared Workspace credit balance row lock (SELECT FOR UPDATE) prevents race condition overdrafts.
- 10 concurrent deduction tasks against a limited pool: exactly N succeed, remainder fail with InsufficientCreditsError.
- Final workspace credit balance never drops below 0 (zero overdraft guarantee).
- Per-seat monthly spend cap race: concurrent member spends strictly adhere to monthly_spend_cap_micros.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import config
from app.db import (
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)

# Domain exceptions and service
try:
    from app.services.workspace_credit_service import (
        CreditDeductionResult,
        InsufficientCreditsError,
        SpendCapExceededError,
        WorkspaceCreditService,
    )
except ImportError:
    class SpendCapExceededError(Exception):
        pass

    class InsufficientCreditsError(Exception):
        pass

    class WorkspaceCreditService:
        def __init__(self, session: Any = None) -> None:
            self.session = session

        async def deduct_credits(
            self,
            *,
            workspace_id: int,
            user_id: Any,
            amount_micros: int,
            description: str = "",
        ) -> Any:
            raise NotImplementedError("To be implemented in Story 24.3")

pytestmark = pytest.mark.integration


async def test_concurrent_workspace_credit_deductions_prevent_overdraft(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """AC-4 & INV-24.4: 10 concurrent tasks each requesting 100k micros against a 500k balance pool.

    Assertions:
    - Exactly 5 tasks succeed.
    - Exactly 5 tasks fail with InsufficientCreditsError.
    - Final Workspace.credit_micros_balance == 0 (Strictly No Overdraft).
    """
    # 1. Initialize Workspace credit balance to 500_000 micros (zsh.50)
    db_workspace.credit_micros_balance = 500_000
    db_session.add(db_workspace)

    # 2. Ensure membership with ample spend cap
    membership = await db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == db_workspace.id,
            WorkspaceMembership.user_id == db_user.id,
        )
    )
    m_row = membership.scalars().first()
    if m_row:
        m_row.monthly_spend_cap_micros = 2_000_000
        m_row.monthly_spent_micros = 0
        db_session.add(m_row)
    await db_session.commit()

    # 3. Create independent DB sessions for concurrent execution
    engine = create_async_engine(config.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    success_count = 0
    failure_count = 0

    async def _attempt_deduction(task_idx: int) -> str:
        nonlocal success_count, failure_count
        async with session_factory() as session:
            service = WorkspaceCreditService(session=session)
            try:
                await service.deduct_credits(
                    workspace_id=db_workspace.id,
                    user_id=db_user.id,
                    amount_micros=100_000,
                    description=f"Concurrent task {task_idx}",
                )
                await session.commit()
                return "SUCCESS"
            except InsufficientCreditsError:
                await session.rollback()
                return "INSUFFICIENT"
            except Exception as e:
                await session.rollback()
                return f"ERROR: {type(e).__name__}"

    # 4. Launch 10 concurrent deduction tasks
    results = await asyncio.gather(*[_attempt_deduction(i) for i in range(10)])

    successes = results.count("SUCCESS")
    insufficients = results.count("INSUFFICIENT")

    # Invariant: Exactly 5 succeed and 5 fail due to balance limitation
    assert successes == 5, f"Expected exactly 5 successes, got {successes}. Results: {results}"
    assert insufficients == 5, f"Expected exactly 5 InsufficientCreditsError, got {insufficients}"

    # 5. Check final workspace balance in a fresh session
    async with session_factory() as verify_session:
        refreshed_ws = await verify_session.get(Workspace, db_workspace.id)
        assert refreshed_ws is not None
        assert refreshed_ws.credit_micros_balance == 0, (
            f"Overdraft detected! Final balance: {refreshed_ws.credit_micros_balance}"
        )

    await engine.dispose()


async def test_concurrent_member_spend_cap_race_prevents_cap_overdraft(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """AC-4 & INV-24.4: 5 concurrent tasks each requesting 100k against a 250k member spend cap.

    Assertions:
    - Exactly 2 tasks succeed (200k spent).
    - Exactly 3 tasks fail with SpendCapExceededError.
    - Final WorkspaceMembership.monthly_spent_micros == 200_000 (<= 250_000 cap).
    """
    # 1. Initialize large workspace balance and 250_000 member cap
    db_workspace.credit_micros_balance = 10_000_000
    db_session.add(db_workspace)

    membership = await db_session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == db_workspace.id,
            WorkspaceMembership.user_id == db_user.id,
        )
    )
    m_row = membership.scalars().first()
    if m_row:
        m_row.monthly_spend_cap_micros = 250_000
        m_row.monthly_spent_micros = 0
        db_session.add(m_row)
    await db_session.commit()

    engine = create_async_engine(config.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _attempt_member_deduction(task_idx: int) -> str:
        async with session_factory() as session:
            service = WorkspaceCreditService(session=session)
            try:
                await service.deduct_credits(
                    workspace_id=db_workspace.id,
                    user_id=db_user.id,
                    amount_micros=100_000,
                    description=f"Member spend task {task_idx}",
                )
                await session.commit()
                return "SUCCESS"
            except SpendCapExceededError:
                await session.rollback()
                return "CAP_EXCEEDED"
            except Exception as e:
                await session.rollback()
                return f"ERROR: {type(e).__name__}"

    # 2. Launch 5 concurrent tasks
    results = await asyncio.gather(*[_attempt_member_deduction(i) for i in range(5)])

    successes = results.count("SUCCESS")
    cap_exceeded = results.count("CAP_EXCEEDED")

    assert successes == 2, f"Expected 2 successes, got {successes}. Results: {results}"
    assert cap_exceeded == 3, f"Expected 3 cap exceeded errors, got {cap_exceeded}"

    # 3. Verify final membership spend
    async with session_factory() as verify_session:
        refreshed_mem = await verify_session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == db_workspace.id,
                WorkspaceMembership.user_id == db_user.id,
            )
        )
        mem_row = refreshed_mem.scalars().first()
        assert mem_row is not None
        assert mem_row.monthly_spent_micros == 200_000
        assert mem_row.monthly_spent_micros <= mem_row.monthly_spend_cap_micros

    await engine.dispose()
