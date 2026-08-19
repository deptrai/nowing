"""Integration Tests: CRM Connection, OAuth, Dedup, Write-Back & Audit Logs (Story 21.5)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import CrmConnection, Lead, Memory, MemorySourceType, Workspace

pytestmark = pytest.mark.integration


async def test_crm_oauth_connect_and_callback_flow(
    client_as_regular_user,
    db_workspace: Workspace,
    db_session: AsyncSession,
) -> None:
    """AC-1 & AC-2: Initiate CRM OAuth connect, receive auth_url with PKCE state, and handle callback."""
    # 1. Connect endpoint
    payload = {
        "provider": "hubspot",
        "sync_config": {
            "dedup_enabled": True,
            "writeback_enabled": True,
        },
    }
    with patch("app.config.config.HUBSPOT_CLIENT_ID", "mock_hubspot_id"), \
         patch("app.config.config.HUBSPOT_CLIENT_SECRET", "mock_hubspot_secret"), \
         patch("app.config.config.HUBSPOT_REDIRECT_URI", "http://localhost:3000/auth/crm/hubspot/callback"), \
         patch("app.config.config.SECRET_KEY", "test-secret-key-that-is-at-least-32-chars-long!"):
        res = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/crm/hubspot/connect",
            json=payload,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "auth_url" in data
        assert "app.hubspot.com" in data["auth_url"]
        assert "state=" in data["auth_url"]

        # Verify CrmConnection is in pending status
        conn_stmt = select(CrmConnection).where(
            CrmConnection.workspace_id == db_workspace.id,
            CrmConnection.provider == "hubspot",
            CrmConnection.status == "pending",
        )
        conn_res = await db_session.execute(conn_stmt)
        pending_conn = conn_res.scalars().first()
        assert pending_conn is not None

        # 2. Extract state from auth_url and trigger callback
        state = data["auth_url"].split("state=")[1].split("&")[0]

        mock_token_response = {
            "access_token": "mock_access_token_123",
            "refresh_token": "mock_refresh_token_456",
            "expires_in": 3600,
            "scope": "contacts",
        }

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_token_response
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            callback_res = await client_as_regular_user.get(
                f"/api/v1/auth/crm/hubspot/callback?code=mock_code&state={state}",
            )
            assert callback_res.status_code == 200, callback_res.text
            cb_data = callback_res.json()
            assert cb_data["status"] == "active"
            assert cb_data["provider"] == "hubspot"
            assert cb_data["workspace_id"] == db_workspace.id

        # 3. Verify listing connections
        list_res = await client_as_regular_user.get(
            f"/api/v1/workspaces/{db_workspace.id}/crm/connections",
        )
        assert list_res.status_code == 200
        connections = list_res.json()
        assert len(connections) >= 1
        assert any(c["id"] == cb_data["id"] for c in connections)


async def test_crm_dedup_and_writeback_lifecycle(
    client_as_regular_user,
    db_workspace: Workspace,
    db_session: AsyncSession,
) -> None:
    """AC-3, AC-4, AC-7 & AC-10: Test dedup, write-back sync, audit log, and memory context."""
    from app.lead_intelligence.crm.oauth import _get_token_encryption

    with patch("app.config.config.SECRET_KEY", "test-secret-key-that-is-at-least-32-chars-long!"):
        enc = _get_token_encryption()
        encrypted_creds = enc.encrypt_token(
            json.dumps({"provider": "salesforce", "access_token": "token123"})
        )

        # 1. Create active connection
        connection = CrmConnection(
            workspace_id=db_workspace.id,
            provider="salesforce",
            status="active",
            credentials_encrypted=encrypted_creds,
            sync_config={
                "dedup_enabled": True,
                "writeback_enabled": True,
                "field_mapping": {
                    "company_name": "Company",
                    "domain": "Website",
                },
            },
        )
        db_session.add(connection)

        # 2. Create sample lead
        lead = Lead(
            workspace_id=db_workspace.id,
            source="web_search",
            company_name="Vingroup Joint Stock",
            domain="vingroup.net",
            value_hmac=f"lead-hmac-{uuid4().hex[:8]}",
            industry="Real Estate",
            company_size="10000+",
            location="Hanoi, Vietnam",
        )
        db_session.add(lead)
        await db_session.commit()
        await db_session.refresh(connection)
        await db_session.refresh(lead)

        # 3. Test Dedup Endpoint (Phase 1)
        dedup_payload = {"lead_ids": [str(lead.id)]}
        dedup_res = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/crm/connections/{connection.id}/dedup",
            json=dedup_payload,
        )
        assert dedup_res.status_code == 200, dedup_res.text
        dedup_data = dedup_res.json()
        assert len(dedup_data["results"]) == 1
        assert dedup_data["results"][0]["degraded"] is False

        # 4. Test Write-Back Endpoint (Phase 2)
        sync_payload = {
            "entity_type": "lead",
            "direction": "nowing_to_crm",
            "entity_ids": [str(lead.id)],
        }
        sync_res = await client_as_regular_user.post(
            f"/api/v1/workspaces/{db_workspace.id}/crm/connections/{connection.id}/sync",
            json=sync_payload,
        )
        assert sync_res.status_code == 200, sync_res.text
        sync_data = sync_res.json()
        assert len(sync_data["results"]) == 1
        assert sync_data["results"][0]["degraded"] is False

        # 5. Verify CrmSyncLog rows
        logs_res = await client_as_regular_user.get(
            f"/api/v1/workspaces/{db_workspace.id}/crm/connections/{connection.id}/sync-logs?limit=10&offset=0",
        )
        assert logs_res.status_code == 200, logs_res.text
        logs = logs_res.json()
        assert len(logs) >= 2
        assert any(item["entity_id"] == str(lead.id) and item["status"] == "success" for item in logs)

        # 6. Verify Context Memory row
        mem_stmt = select(Memory).where(
            Memory.workspace_id == db_workspace.id,
            Memory.source_type == MemorySourceType.CRM_CONNECTION,
            Memory.source_uuid == connection.id,
        )
        mem_res = await db_session.execute(mem_stmt)
        memories = mem_res.scalars().all()
        assert len(memories) >= 1
        assert "Vingroup Joint Stock" in memories[0].content


async def test_crm_disconnect_endpoint(
    client_as_regular_user,
    db_workspace: Workspace,
    db_session: AsyncSession,
) -> None:
    """AC-9: Disconnect CRM connection."""
    connection = CrmConnection(
        workspace_id=db_workspace.id,
        provider="pipedrive",
        status="active",
        credentials_encrypted="ENC_DUMMY",
        sync_config={},
    )
    db_session.add(connection)
    await db_session.commit()
    await db_session.refresh(connection)

    del_res = await client_as_regular_user.delete(
        f"/api/v1/workspaces/{db_workspace.id}/crm/connections/{connection.id}",
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "disconnected"

    # Verify status changed in DB
    await db_session.refresh(connection)
    assert connection.status == "disconnected"
