"""Integration tests for Story 26.1 batch lead ingestion (AC-1, AC-2, AC-4)."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from app.db import Lead, VerifiedContact, WorkspaceDncRecord

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_batch_ingest_persists_lead_and_verified_contact(
    client, db_session, db_workspace, lead_batch_payload
):
    """Pattern 6: SQL executes and Lead + VerifiedContact rows are inserted."""
    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/batch-ingest",
        json=lead_batch_payload,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested_count"] == 1
    assert body["skipped_blacklisted_count"] == 0
    assert body["failed_count"] == 0
    assert len(body["lead_ids"]) == 1

    lead_id = body["lead_ids"][0]
    lead = (
        await db_session.execute(select(Lead).where(Lead.id == lead_id))
    ).scalar_one_or_none()
    assert lead is not None
    assert lead.workspace_id == db_workspace.id
    assert lead.company_name == lead_batch_payload["leads"][0]["company_name"]
    assert lead.value_hmac is not None

    contact = (
        await db_session.execute(
            select(VerifiedContact).where(
                VerifiedContact.lead_id == lead_id,
                VerifiedContact.workspace_id == db_workspace.id,
            )
        )
    ).scalar_one_or_none()
    assert contact is not None
    assert contact.email is not None


@pytest.mark.asyncio
async def test_batch_ingest_dedups_by_value_hmac(
    client, db_session, db_workspace, lead_batch_payload
):
    """Pattern 6: duplicate value_hmac in overlapping batches results in one Lead row."""
    await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/batch-ingest",
        json=lead_batch_payload,
    )
    await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/batch-ingest",
        json=lead_batch_payload,
    )

    count = (
        await db_session.execute(
            select(func.count(Lead.id)).where(Lead.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_batch_ingest_marks_dnc_lead_blacklisted(
    client, db_session, db_workspace, lead_batch_payload
):
    """Pattern 6: DNC record blocks lead and sets status='blacklisted', no VerifiedContact."""
    from app.config import config
    from app.lead_intelligence.dnc.normalizer import (
        hash_phone_hmac,
        normalize_email,
    )

    lead = lead_batch_payload["leads"][0]
    email = normalize_email(lead["email"])
    dnc = WorkspaceDncRecord(
        workspace_id=db_workspace.id,
        record_type="email",
        value=email,
        value_hmac=hash_phone_hmac(email, secret_key=config.SECRET_KEY),
    )
    db_session.add(dnc)
    await db_session.flush()

    await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/batch-ingest",
        json=lead_batch_payload,
    )

    lead_row = (
        await db_session.execute(
            select(Lead).where(Lead.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert lead_row.status == "blacklisted"

    contact_count = (
        await db_session.execute(
            select(func.count(VerifiedContact.id)).where(
                VerifiedContact.workspace_id == db_workspace.id
            )
        )
    ).scalar_one()
    assert contact_count == 0


@pytest.mark.asyncio
async def test_batch_ingest_concurrent_no_deadlock(
    client, db_session, db_workspace, lead_batch_payload
):
    """Pattern 3/6: 20 concurrent overlapping batches produce 0 deadlock and 1 unique lead."""
    tasks = [
        client.post(
            f"/api/v1/workspaces/{db_workspace.id}/leads/batch-ingest",
            json=lead_batch_payload,
        )
        for _ in range(20)
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    for resp in responses:
        assert not isinstance(resp, Exception), resp
        assert resp.status_code == 200

    count = (
        await db_session.execute(
            select(func.count(Lead.id)).where(Lead.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_batch_ingest_non_member_forbidden(
    client_as_other, db_workspace, lead_batch_payload
):
    """Pattern 3: non-workspace member cannot call batch ingest."""
    resp = await client_as_other.post(
        f"/api/v1/workspaces/{db_workspace.id}/leads/batch-ingest",
        json=lead_batch_payload,
    )
    assert resp.status_code == 403
