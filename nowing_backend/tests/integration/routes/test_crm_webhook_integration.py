"""Integration tests for CRM Webhooks (Story 34.1, Epic 34 Retro Action Items).

Exercises real database transactions for:
- Salesforce deal change webhook:
  - Authenticated via X-Salesforce-Webhook-Secret header.
  - Updates Lead.status (mapped from Salesforce StageName).
  - Inserts CrmSyncLog row with direction="inbound", status="success".
  - Asserts full commit to PostgreSQL.
- HubSpot deal change webhook:
  - Authenticated via X-Hubspot-Signature-v3 header (HMAC-SHA256).
  - Updates Lead.status.
  - Inserts CrmSyncLog row.
  - Asserts full commit to PostgreSQL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CrmConnection, CrmSyncLog, Lead, VerifiedContact, Workspace

pytestmark = pytest.mark.integration


async def test_salesforce_webhook_full_transaction(
    client_as_regular_user,
    db_workspace: Workspace,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """Salesforce webhook updates Lead.status and commits CrmSyncLog on real DB."""
    # 1. Setup Active Salesforce Connection
    sf_conn = CrmConnection(
        workspace_id=db_workspace.id,
        provider="salesforce",
        status="active",
        credentials_encrypted="ENC_SF_DUMMY",
        sync_config={"writeback_enabled": True},
    )
    db_session.add(sf_conn)

    # 2. Setup Lead and linked VerifiedContact
    lead = Lead(
        workspace_id=db_workspace.id,
        source="web_search",
        company_name="Apex Holdings Corp",
        domain="apexholdings.vn",
        value_hmac=f"lead-hmac-{uuid4().hex[:8]}",
        status="contacted",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name="Nguyen Van A",
        email="vana@apexholdings.vn",
        value_hmac=f"vc-hmac-{uuid4().hex[:8]}",
        external_chat_ids={"salesforce_opp_id": "0065g00000XYZ123"},
    )
    db_session.add(contact)
    await db_session.commit()

    # 3. Configure shared webhook secret
    secret_val = "sf-webhook-super-secret-key-32chars"
    monkeypatch.setattr("app.config.config.SALESFORCE_WEBHOOK_SECRET", secret_val)

    # 4. Invoke Salesforce webhook with valid secret
    sf_payload = {
        "opportunity_id": "0065g00000XYZ123",
        "stage_name": "Closed Won",
    }
    res = await client_as_regular_user.post(
        "/api/v1/workspaces/webhooks/salesforce",
        json=sf_payload,
        headers={"X-Salesforce-Webhook-Secret": secret_val},
    )
    assert res.status_code == 200, res.text
    res_data = res.json()
    assert res_data["status"] == "ok"
    assert res_data["result"]["status"] == "updated"
    assert res_data["result"]["new_lead_status"] == "converted"
    assert res_data["result"]["lead_id"] == str(lead.id)

    # 5. Query Real DB: verify Lead.status committed as converted
    lead_stmt = select(Lead).where(
        Lead.id == lead.id,
        Lead.workspace_id == db_workspace.id,
    )
    lead_res = await db_session.execute(lead_stmt)
    updated_lead = lead_res.scalars().one()
    assert updated_lead.status == "converted"

    # 6. Query Real DB: verify CrmSyncLog row committed
    log_stmt = select(CrmSyncLog).where(
        CrmSyncLog.workspace_id == db_workspace.id,
        CrmSyncLog.entity_id == lead.id,
    )
    log_res = await db_session.execute(log_stmt)
    sync_log = log_res.scalars().first()
    assert sync_log is not None
    assert sync_log.connection_id == sf_conn.id
    assert sync_log.direction == "inbound"
    assert sync_log.entity_type == "lead"
    assert sync_log.status == "success"


async def test_salesforce_webhook_unauthorized_rejection(
    client_as_regular_user,
    db_workspace: Workspace,
    monkeypatch,
) -> None:
    """Salesforce webhook rejects invalid secret or missing header with 401."""
    monkeypatch.setattr(
        "app.config.config.SALESFORCE_WEBHOOK_SECRET", "correct-sf-secret"
    )

    # Missing header
    res_missing = await client_as_regular_user.post(
        "/api/v1/workspaces/webhooks/salesforce",
        json={"opportunity_id": "opp123", "stage_name": "Closed Won"},
    )
    assert res_missing.status_code == 401
    assert "Invalid Salesforce webhook secret" in res_missing.json()["detail"]

    # Wrong header
    res_wrong = await client_as_regular_user.post(
        "/api/v1/workspaces/webhooks/salesforce",
        json={"opportunity_id": "opp123", "stage_name": "Closed Won"},
        headers={"X-Salesforce-Webhook-Secret": "wrong-secret"},
    )
    assert res_wrong.status_code == 401


async def test_hubspot_webhook_full_transaction(
    client_as_regular_user,
    db_workspace: Workspace,
    db_session: AsyncSession,
    monkeypatch,
) -> None:
    """HubSpot webhook updates Lead.status and commits CrmSyncLog on real DB."""
    # 1. Setup Active HubSpot Connection
    hs_conn = CrmConnection(
        workspace_id=db_workspace.id,
        provider="hubspot",
        status="active",
        credentials_encrypted="ENC_HS_DUMMY",
        sync_config={"writeback_enabled": True},
    )
    db_session.add(hs_conn)

    # 2. Setup Lead and linked VerifiedContact
    lead = Lead(
        workspace_id=db_workspace.id,
        source="web_search",
        company_name="Nexus Real Estate Ltd",
        domain="nexusbds.vn",
        value_hmac=f"lead-hmac-{uuid4().hex[:8]}",
        status="new",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        name="Tran Thi B",
        email="thib@nexusbds.vn",
        value_hmac=f"vc-hmac-{uuid4().hex[:8]}",
        external_chat_ids={"hubspot_deal_id": "99887766"},
    )
    db_session.add(contact)
    await db_session.commit()

    # 3. Configure shared webhook secret
    hs_secret = "hs-webhook-signature-secret-key-456"
    monkeypatch.setattr("app.config.config.HUBSPOT_WEBHOOK_SECRET", hs_secret)

    # 4. Prepare payload and HMAC-SHA256 signature
    hs_payload = [
        {
            "subscriptionType": "deal.propertyChange",
            "propertyName": "dealstage",
            "objectId": 99887766,
            "propertyValue": "qualifiedtobuy",
        }
    ]
    body_bytes = json.dumps(hs_payload).encode()
    timestamp = str(int(time.time() * 1000))
    request_uri = f"{str(client_as_regular_user.base_url).rstrip('/')}/api/v1/workspaces/webhooks/hubspot"
    source = f"POST{request_uri}".encode() + body_bytes + timestamp.encode()
    sig = base64.b64encode(
        hmac.new(hs_secret.encode(), source, hashlib.sha256).digest()
    ).decode()

    # 5. Invoke HubSpot webhook
    res = await client_as_regular_user.post(
        "/api/v1/workspaces/webhooks/hubspot",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hubspot-Signature-v3": sig,
            "X-Hubspot-Request-Timestamp": timestamp,
        },
    )
    assert res.status_code == 200, res.text
    res_data = res.json()
    assert res_data["status"] == "ok"
    assert res_data["processed"] == 1
    assert res_data["results"][0]["status"] == "updated"
    assert res_data["results"][0]["new_lead_status"] == "qualified"

    # 6. Verify Lead.status in Real DB
    lead_stmt = select(Lead).where(
        Lead.id == lead.id,
        Lead.workspace_id == db_workspace.id,
    )
    lead_res = await db_session.execute(lead_stmt)
    updated_lead = lead_res.scalars().one()
    assert updated_lead.status == "qualified"

    # 7. Verify CrmSyncLog in Real DB
    log_stmt = select(CrmSyncLog).where(
        CrmSyncLog.workspace_id == db_workspace.id,
        CrmSyncLog.entity_id == lead.id,
    )
    log_res = await db_session.execute(log_stmt)
    sync_log = log_res.scalars().first()
    assert sync_log is not None
    assert sync_log.connection_id == hs_conn.id
    assert sync_log.direction == "inbound"
    assert sync_log.entity_type == "lead"
    assert sync_log.status == "success"
