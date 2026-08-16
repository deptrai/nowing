"""Integration tests for ManualCreditAdjustmentService (Story 25.2)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AuditEvent, CreditTransaction, User, Workspace
from app.services.manual_credit_service import (
    CREDIT_TO_MICROS,
    ManualCreditAdjustmentService,
    ManualCreditQuotaExceededError,
    ManualCreditValidationError,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_adjust_credits_credit_success(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> None:
    """AC-1/AC-2: A valid CREDIT adjustment updates the workspace balance and ledger."""
    svc = ManualCreditAdjustmentService(db_session)

    result = await svc.adjust_credits(
        workspace_id=db_workspace.id,
        amount_credits=50,
        direction="CREDIT",
        reason="Top-up for partner campaign",
        ticket_ref="https://zendesk.example.com/tickets/12345",
        actor_admin_id=db_user.id,
        idempotency_key=f"test-credit-{uuid.uuid4()}",
    )

    assert result["direction"] == "CREDIT"
    assert result["amount_credits"] == 50
    assert result["amount_micros"] == 50 * CREDIT_TO_MICROS

    await db_session.refresh(db_workspace)
    assert db_workspace.credit_micros_balance == 50 * CREDIT_TO_MICROS

    tx_count = await db_session.execute(
        select(CreditTransaction).where(
            CreditTransaction.workspace_id == db_workspace.id
        )
    )
    assert len(tx_count.scalars().all()) == 1


async def test_adjust_credits_debit_success(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> None:
    """AC-2: A valid DEBIT adjustment decreases the workspace balance."""
    db_workspace.credit_micros_balance = 100 * CREDIT_TO_MICROS
    await db_session.flush()

    svc = ManualCreditAdjustmentService(db_session)
    result = await svc.adjust_credits(
        workspace_id=db_workspace.id,
        amount_credits=30,
        direction="DEBIT",
        reason="Clawback for duplicate charge",
        ticket_ref="JIRA-9876",
        actor_admin_id=db_user.id,
        idempotency_key=f"test-debit-{uuid.uuid4()}",
    )

    assert result["direction"] == "DEBIT"
    assert result["amount_credits"] == 30

    await db_session.refresh(db_workspace)
    assert db_workspace.credit_micros_balance == 70 * CREDIT_TO_MICROS


async def test_adjust_credits_debit_insufficient(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> None:
    """AC-2: DEBIT must be rejected when the workspace balance is too low."""
    svc = ManualCreditAdjustmentService(db_session)

    with pytest.raises(ManualCreditValidationError):
        await svc.adjust_credits(
            workspace_id=db_workspace.id,
            amount_credits=10,
            direction="DEBIT",
            reason="Refund too large",
            ticket_ref="JIRA-9999",
            actor_admin_id=db_user.id,
            idempotency_key=f"test-debit-insufficient-{uuid.uuid4()}",
        )


async def test_adjust_credits_validation_errors(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> None:
    """AC-1: Mandatory fields and enums are enforced."""
    svc = ManualCreditAdjustmentService(db_session)
    base = {
        "workspace_id": db_workspace.id,
        "amount_credits": 10,
        "direction": "CREDIT",
        "reason": "Compensation",
        "ticket_ref": "TICKET-1",
        "actor_admin_id": db_user.id,
        "idempotency_key": f"test-validation-{uuid.uuid4()}",
    }

    with pytest.raises(ManualCreditValidationError):
        await svc.adjust_credits(**{**base, "amount_credits": -5})

    with pytest.raises(ManualCreditValidationError):
        await svc.adjust_credits(**{**base, "direction": "WRONG"})

    with pytest.raises(ManualCreditValidationError):
        await svc.adjust_credits(**{**base, "reason": "short"})

    with pytest.raises(ManualCreditValidationError):
        await svc.adjust_credits(**{**base, "ticket_ref": ""})


async def test_adjust_credits_staff_quota_guardrail(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> None:
    """AC-3: Daily credit-grant quota of 1,000 credits is enforced."""
    svc = ManualCreditAdjustmentService(db_session)

    await svc.adjust_credits(
        workspace_id=db_workspace.id,
        amount_credits=600,
        direction="CREDIT",
        reason="First approved credit grant",
        ticket_ref="TICKET-1",
        actor_admin_id=db_user.id,
        idempotency_key=f"test-quota-ok-{uuid.uuid4()}",
    )

    with pytest.raises(ManualCreditQuotaExceededError):
        await svc.adjust_credits(
            workspace_id=db_workspace.id,
            amount_credits=600,
            direction="CREDIT",
            reason="Second grant over quota",
            ticket_ref="TICKET-2",
            actor_admin_id=db_user.id,
            idempotency_key=f"test-quota-exceeded-{uuid.uuid4()}",
        )

    audit = await db_session.execute(
        select(CreditTransaction).where(
            CreditTransaction.actor_admin_id == db_user.id,
            CreditTransaction.direction == "CREDIT",
        )
    )
    assert len(audit.scalars().all()) == 1


async def test_adjust_credits_idempotency_double_submit(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> None:
    """AC-2: Two rapid submissions with the same idempotency key yield one ledger row."""
    svc = ManualCreditAdjustmentService(db_session)
    idempotency_key = f"test-idem-{uuid.uuid4()}"

    result_a = await svc.adjust_credits(
        workspace_id=db_workspace.id,
        amount_credits=25,
        direction="CREDIT",
        reason="Partner promotion top-up",
        ticket_ref="PROMO-1",
        actor_admin_id=db_user.id,
        idempotency_key=idempotency_key,
    )

    result_b = await svc.adjust_credits(
        workspace_id=db_workspace.id,
        amount_credits=25,
        direction="CREDIT",
        reason="Partner promotion top-up",
        ticket_ref="PROMO-1",
        actor_admin_id=db_user.id,
        idempotency_key=idempotency_key,
    )

    assert result_a["transaction_id"] == result_b["transaction_id"]

    all_tx = await db_session.execute(
        select(CreditTransaction).where(
            CreditTransaction.idempotency_key == idempotency_key
        )
    )
    assert len(all_tx.scalars().all()) == 1

    await db_session.refresh(db_workspace)
    assert db_workspace.credit_micros_balance == 25 * CREDIT_TO_MICROS


async def test_adjust_credits_concurrent_quota_guard(
    async_engine, db_user: User
) -> None:
    """AC-3: Two concurrent credit grants from the same admin cannot exceed the daily quota.

    This test exercises the per-admin pg_advisory_xact_lock by running two
    independent database sessions in parallel.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    admin = User(
        id=uuid.uuid4(),
        email=f"concurrent-{uuid.uuid4()}@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    workspace = Workspace(name="Concurrent quota test", user_id=admin.id)

    async with (
        async_engine.connect() as conn,
        AsyncSession(bind=conn, expire_on_commit=False) as session,
    ):
        session.add(admin)
        session.add(workspace)
        await session.commit()
        workspace_id = workspace.id
        admin_id = admin.id

    async def run_grant(key: str) -> dict | None:
        async with (
            async_engine.connect() as conn,
            AsyncSession(bind=conn, expire_on_commit=False) as session,
        ):
            svc = ManualCreditAdjustmentService(session)
            try:
                result = await svc.adjust_credits(
                    workspace_id=workspace_id,
                    amount_credits=600,
                    direction="CREDIT",
                    reason="Concurrent test",
                    ticket_ref="TICKET-CC",
                    actor_admin_id=admin_id,
                    idempotency_key=key,
                )
            except ManualCreditQuotaExceededError:
                await session.commit()
                raise
            else:
                await session.commit()
            return result

    keys = [f"concurrent-a-{uuid.uuid4()}", f"concurrent-b-{uuid.uuid4()}"]
    results = await asyncio.gather(
        *(asyncio.create_task(run_grant(k)) for k in keys),
        return_exceptions=True,
    )

    successes = [r for r in results if isinstance(r, dict)]
    quota_errors = [r for r in results if isinstance(r, ManualCreditQuotaExceededError)]
    assert len(successes) == 1, results
    assert len(quota_errors) == 1, results

    async with (
        async_engine.connect() as conn,
        AsyncSession(bind=conn, expire_on_commit=False) as session,
    ):
        all_tx = await session.execute(
            select(CreditTransaction).where(CreditTransaction.workspace_id == workspace_id)
        )
        assert len(all_tx.scalars().all()) == 1

        ws = await session.get(Workspace, workspace_id)
        assert ws is not None
        assert ws.credit_micros_balance == 600 * CREDIT_TO_MICROS

    async with (
        async_engine.connect() as conn,
        AsyncSession(bind=conn, expire_on_commit=False) as session,
    ):
        audit_events = await session.execute(
            select(AuditEvent).where(
                (AuditEvent.actor_id == admin_id) | (AuditEvent.subject_id == admin_id)
            )
        )
        for event in audit_events.scalars().all():
            await session.delete(event)

        ws = await session.get(Workspace, workspace_id)
        if ws is not None:
            await session.delete(ws)

        user = await session.get(User, admin_id)
        if user is not None:
            await session.delete(user)
        await session.commit()
