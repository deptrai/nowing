"""Integration tests for /api/v1/admin/credits/* (Story 25.2)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AuditEvent, CreditTransaction, User, Workspace

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

    res = await admin_client.get(
        f"/api/v1/admin/credits/ledger?workspace_id={db_workspace.id}"
    )
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
    db_superuser: User,
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

    audit = await db_session.execute(
        select(AuditEvent).where(
            AuditEvent.action == "manual_credit_quota_exceeded",
            AuditEvent.ticket_ref == "TICKET-4",
            (AuditEvent.actor_id == db_superuser.id)
            | (AuditEvent.subject_id == db_superuser.id),
        )
    )
    audit_event = audit.scalar_one_or_none()
    assert audit_event is not None
    assert audit_event.actor_id == db_superuser.id


@pytest.mark.asyncio
async def test_post_admin_credits_adjust_idempotency_key_too_long(
    admin_client: AsyncClient,
    db_workspace: Workspace,
) -> None:
    """AC-1: Idempotency-Key longer than 64 characters is rejected with 400."""
    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": "x" * 65},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 100,
            "direction": "CREDIT",
            "reason": "Key too long",
            "ticket_ref": "TICKET-KEY",
        },
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_post_admin_credits_adjust_idempotency_key_64_chars_ok(
    admin_client: AsyncClient,
    db_workspace: Workspace,
) -> None:
    """AC-1: Idempotency-Key at the 64-character boundary is accepted."""
    res = await admin_client.post(
        "/api/v1/admin/credits/adjust",
        headers={"Idempotency-Key": "x" * 64},
        json={
            "workspace_id": db_workspace.id,
            "amount_credits": 100,
            "direction": "CREDIT",
            "reason": "Boundary key length test",
            "ticket_ref": "TICKET-KEY64",
        },
    )
    assert res.status_code == 201, res.text


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


@pytest.mark.asyncio
async def test_get_admin_credits_ledger_pagination(
    admin_client: AsyncClient,
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """AC-4: GET /ledger honors limit and offset."""
    for i, (amount, reason) in enumerate(
        [(50, "page one item"), (75, "page two item")], start=1
    ):
        res = await admin_client.post(
            "/api/v1/admin/credits/adjust",
            headers={"Idempotency-Key": f"idem-paging-{i}-{uuid.uuid4()}"},
            json={
                "workspace_id": db_workspace.id,
                "amount_credits": amount,
                "direction": "CREDIT",
                "reason": reason,
                "ticket_ref": f"TICKET-PAGE-{i}",
            },
        )
        assert res.status_code == 201, res.text

    res = await admin_client.get("/api/v1/admin/credits/ledger?limit=2")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 2
    assert data[0]["amount_credits"] == 75
    assert data[1]["amount_credits"] == 50
    assert data[0]["created_at"] >= data[1]["created_at"]

    res = await admin_client.get("/api/v1/admin/credits/ledger?limit=1")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 1
    assert data[0]["amount_credits"] == 75

    res = await admin_client.get("/api/v1/admin/credits/ledger?limit=1&offset=1")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 1
    assert data[0]["amount_credits"] == 50

    res = await admin_client.get("/api/v1/admin/credits/ledger?limit=1&offset=2")
    assert res.status_code == 200, res.text
    assert len(res.json()) == 0

    res = await admin_client.get("/api/v1/admin/credits/ledger?limit=100")
    assert res.status_code == 200, res.text
    assert len(res.json()) == 2

    res = await admin_client.get("/api/v1/admin/credits/ledger?limit=101")
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_get_admin_credits_ledger_reason_wildcard_escaped(
    admin_client: AsyncClient,
    db_workspace: Workspace,
) -> None:
    """AC-4: The reason filter escapes SQL wildcards so % is matched literally."""
    for i, reason in enumerate(["support case", "supp%ort case"], start=1):
        res = await admin_client.post(
            "/api/v1/admin/credits/adjust",
            headers={"Idempotency-Key": f"idem-wild-{i}-{uuid.uuid4()}"},
            json={
                "workspace_id": db_workspace.id,
                "amount_credits": 10,
                "direction": "CREDIT",
                "reason": reason,
                "ticket_ref": f"TICKET-WILD-{i}",
            },
        )
        assert res.status_code == 201, res.text

    res = await admin_client.get("/api/v1/admin/credits/ledger?reason=supp%25ort%20case")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 1
    assert data[0]["reason"] == "supp%ort case"


@pytest.mark.asyncio
async def test_get_admin_credits_ledger_reason_underscore_escaped(
    admin_client: AsyncClient,
    db_workspace: Workspace,
) -> None:
    """AC-4: The reason filter escapes SQL wildcards so _ is matched literally."""
    for i, reason in enumerate(["support case", "supp_ort case"], start=1):
        res = await admin_client.post(
            "/api/v1/admin/credits/adjust",
            headers={"Idempotency-Key": f"idem-und-{i}-{uuid.uuid4()}"},
            json={
                "workspace_id": db_workspace.id,
                "amount_credits": 10,
                "direction": "CREDIT",
                "reason": reason,
                "ticket_ref": f"TICKET-UND-{i}",
            },
        )
        assert res.status_code == 201, res.text

    res = await admin_client.get("/api/v1/admin/credits/ledger?reason=supp_ort%20case")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 1
    assert data[0]["reason"] == "supp_ort case"
