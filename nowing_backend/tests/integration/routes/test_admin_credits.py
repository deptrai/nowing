"""Integration tests for /api/v1/admin/credits/* (Story 25.2)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CreditTransaction, Workspace

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_post_admin_credits_adjust_ac1_validation(
    admin_client: AsyncClient,
    db_workspace: Workspace,
) -> None:
    """AC-1: POST /adjust enforces mandatory fields."""
    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": f"idem-{uuid.uuid4()}"},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": -5,
            "direction": "CREDIT",
            "reason": "bad amount",
            "ticket_ref": "TICKET-1",
        },
    )
    assert res.status_code == 422, res.text

    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": f"idem-{uuid.uuid4()}"},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 10,
            "direction": "SIDeways",
            "reason": "bad direction",
            "ticket_ref": "TICKET-1",
        },
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_post_admin_credits_adjust_credit_and_ledger(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """AC-1/AC-2: POST credit creates ledger row; GET ledger returns it."""
    idem = f"idem-{uuid.uuid4()}"
    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": idem},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 500,
            "direction": "CREDIT",
            "reason": "Manual top-up for partner",
            "ticket_ref": "https://zendesk.example.com/tickets/100",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["direction"] == "CREDIT"
    assert data["amount_credits"] == 500
    assert data["new_balance_credits"] == 500

    await db_session.refresh(db_workspace)
    assert db_workspace.credit_micros_balance == 500 * 10_000

    res = await admin_client.get("/api/v1/admin/credits/ledger")
    assert res.status_code == 200, res.text
    ledger = res.json()
    assert len(ledger) == 1
    assert ledger[0]["amount_credits"] == 500
    assert ledger[0]["ticket_ref"] == "https://zendesk.example.com/tickets/100"


@pytest.mark.asyncio
async def test_post_admin_credits_adjust_debit_rejected_when_insufficient(
    admin_client: AsyncClient,
    db_workspace: Workspace,
) -> None:
    """AC-2: DEBIT cannot make the workspace balance negative."""
    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": f"idem-{uuid.uuid4()}"},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 100,
            "direction": "DEBIT",
            "reason": "Refund for overcharge",
            "ticket_ref": "TICKET-2",
        },
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_post_admin_credits_adjust_quota_guardrail(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """AC-3: Second grant exceeding the daily quota is rejected with 403."""
    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": f"idem-{uuid.uuid4()}"},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 600,
            "direction": "CREDIT",
            "reason": "First approved credit",
            "ticket_ref": "TICKET-3",
        },
    )
    assert res.status_code == 201, res.text

    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": f"idem-{uuid.uuid4()}"},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 600,
            "direction": "CREDIT",
            "reason": "Second grant over quota",
            "ticket_ref": "TICKET-4",
        },
    )
    assert res.status_code == 403, res.text
    assert "quota exceeded" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_post_admin_credits_adjust_idempotent_double_submit(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """AC-2: Rapid double-click with the same Idempotency-Key yields one ledger row."""
    idem = f"idem-{uuid.uuid4()}"
    payload = {
        "workspace_id": db_workspace.id,
        "amount_credits": 25,
        "direction": "CREDIT",
        "reason": "Partner promotion",
        "ticket_ref": "PROMO-1",
    }

    res_a = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": idem},
        json=payload,
    )
    res_b = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": idem},
        json=payload,
    )

    assert res_a.status_code == 201, res_a.text
    assert res_b.status_code == 201, res_b.text
    assert res_a.json()["transaction_id"] == res_b.json()["transaction_id"]

    tx_count = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.idempotency_key == idem)
    )
    assert len(tx_count.scalars().all()) == 1

    await db_session.refresh(db_workspace)
    assert db_workspace.credit_micros_balance == 25 * 10_000


@pytest.mark.asyncio
async def test_get_admin_credits_ledger_filter_by_workspace(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """AC-4: GET /ledger supports filtering by workspace, admin, and reason."""
    idem = f"idem-{uuid.uuid4()}"
    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": idem},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 100,
            "direction": "CREDIT",
            "reason": "Support compensation credit",
            "ticket_ref": "TICKET-5",
        },
    )
    assert res.status_code == 201, res.text

    res = await admin_client.get(
        f"/api/v1/admin/credits/ledger?workspace_id={db_workspace.id}"
    )
    assert res.status_code == 200, res.text
    assert len(res.json()) == 1

    res = await admin_client.get("/api/v1/admin/credits/ledger?reason=support")
    assert res.status_code == 200, res.text
    assert len(res.json()) == 1

    res = await admin_client.get("/api/v1/admin/credits/ledger?reason=missing")
    assert res.status_code == 200, res.text
    assert len(res.json()) == 0
