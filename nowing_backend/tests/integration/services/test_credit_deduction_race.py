"""Integration tests for Shared Workspace Credit Pooling Concurrency & Race Condition Prevention (Story 24.3 / INV-24.4).

Verifies:
- INV-24.4: Shared Workspace credit balance row lock (SELECT FOR UPDATE) prevents race condition overdrafts.
- 10 concurrent deduction tasks against a limited pool: exactly N succeed, remainder fail with InsufficientCreditsError.
- Final workspace credit balance never drops below 0 (zero overdraft guarantee).
- Per-seat monthly spend cap race: concurrent member spends strictly adhere to monthly_spend_cap_micros.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db import User, Workspace, WorkspaceMembership
from app.routes.workspaces_routes import create_default_roles_and_membership
from app.services.workspace_credit_service import (
    InsufficientCreditsError,
    SpendCapExceededError,
    WorkspaceCreditService,
)

pytestmark = pytest.mark.integration


async def _setup_race_workspace(
    async_engine: AsyncEngine,
    workspace_balance: int,
    member_spend_cap: int | None,
) -> tuple[Workspace, User]:
    """Create a workspace + owner with committed state visible to other connections.

    The integration test fixture uses savepoints, so data seeded in ``db_session`` is
    not visible to new connections. We therefore create and commit the race fixture
    data in a standalone transaction.
    """
    async with AsyncSession(
        async_engine, expire_on_commit=False
    ) as session, session.begin():
        user = User(
            id=uuid.uuid4(),
            email=f"race-{uuid.uuid4()}@nowing.net",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        workspace = Workspace(
            name="Race Workspace",
            user_id=user.id,
            credit_micros_balance=workspace_balance,
        )
        session.add(workspace)
        await session.flush()

        await create_default_roles_and_membership(session, workspace.id, user.id)

        membership = (
            await session.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.user_id == user.id,
                )
            )
        ).scalars().one()
        membership.monthly_spend_cap_micros = member_spend_cap
        membership.monthly_spent_micros = 0

    return workspace, user


async def _cleanup_race_workspace(
    async_engine: AsyncEngine, workspace: Workspace, user: User
) -> None:
    async with AsyncSession(
        async_engine, expire_on_commit=False
    ) as session, session.begin():
        ws = await session.get(Workspace, workspace.id)
        if ws is not None:
            await session.delete(ws)
        u = await session.get(User, user.id)
        if u is not None:
            await session.delete(u)


async def test_concurrent_workspace_credit_deductions_prevent_overdraft(
    async_engine: AsyncEngine,
) -> None:
    """AC-4 & INV-24.4: 10 concurrent tasks each requesting 100k micros against a 500k balance pool.

    Assertions:
    - Exactly 5 tasks succeed.
    - Exactly 5 tasks fail with InsufficientCreditsError.
    - Final Workspace.credit_micros_balance == 0 (Strictly No Overdraft).
    """
    workspace, user = await _setup_race_workspace(
        async_engine,
        workspace_balance=500_000,
        member_spend_cap=2_000_000,
    )

    try:
        session_factory = async_sessionmaker(
            async_engine, expire_on_commit=False, class_=AsyncSession
        )

        async def _attempt_deduction(task_idx: int) -> str:
            async with session_factory() as session:
                service = WorkspaceCreditService(session=session)
                try:
                    await service.deduct_credits(
                        workspace_id=workspace.id,
                        user_id=user.id,
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

        results = await asyncio.gather(*[_attempt_deduction(i) for i in range(10)])

        successes = results.count("SUCCESS")
        insufficients = results.count("INSUFFICIENT")

        assert successes == 5, f"Expected exactly 5 successes, got {successes}. Results: {results}"
        assert insufficients == 5, f"Expected exactly 5 InsufficientCreditsError, got {insufficients}"

        async with session_factory() as verify_session:
            refreshed_ws = await verify_session.get(Workspace, workspace.id)
            assert refreshed_ws is not None
            assert refreshed_ws.credit_micros_balance == 0, (
                f"Overdraft detected! Final balance: {refreshed_ws.credit_micros_balance}"
            )
    finally:
        await _cleanup_race_workspace(async_engine, workspace, user)


async def test_concurrent_member_spend_cap_race_prevents_cap_overdraft(
    async_engine: AsyncEngine,
) -> None:
    """AC-4 & INV-24.4: 5 concurrent tasks each requesting 100k against a 250k member spend cap.

    Assertions:
    - Exactly 2 tasks succeed (200k spent).
    - Exactly 3 tasks fail with SpendCapExceededError.
    - Final WorkspaceMembership.monthly_spent_micros == 200_000 (<= 250_000 cap).
    """
    workspace, user = await _setup_race_workspace(
        async_engine,
        workspace_balance=10_000_000,
        member_spend_cap=250_000,
    )

    try:
        session_factory = async_sessionmaker(
            async_engine, expire_on_commit=False, class_=AsyncSession
        )

        async def _attempt_member_deduction(task_idx: int) -> str:
            async with session_factory() as session:
                service = WorkspaceCreditService(session=session)
                try:
                    await service.deduct_credits(
                        workspace_id=workspace.id,
                        user_id=user.id,
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

        results = await asyncio.gather(*[_attempt_member_deduction(i) for i in range(5)])

        successes = results.count("SUCCESS")
        cap_exceeded = results.count("CAP_EXCEEDED")

        assert successes == 2, f"Expected 2 successes, got {successes}. Results: {results}"
        assert cap_exceeded == 3, f"Expected 3 cap exceeded errors, got {cap_exceeded}"

        async with session_factory() as verify_session:
            refreshed_mem = await verify_session.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace.id,
                    WorkspaceMembership.user_id == user.id,
                )
            )
            mem_row = refreshed_mem.scalars().first()
            assert mem_row is not None
            assert mem_row.monthly_spent_micros == 200_000
            assert mem_row.monthly_spent_micros <= mem_row.monthly_spend_cap_micros
    finally:
        await _cleanup_race_workspace(async_engine, workspace, user)
