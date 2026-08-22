"""Integration tests for Zalo Outbound Pipeline, ZNS Gateway, and Telegram Alerts (Story 21.6 / AD-41)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    Lead,
    User,
    VerifiedContact,
    Workspace,
    ZaloConnection,
    ZaloMessageLog,
)
from app.gateway.zalo.client import ZaloClient
from app.gateway.zalo.webhook import handle_zalo_webhook_event
from app.routes.outbound_routes import (
    ZaloConnectionCreate,
    ZaloDraftRequest,
    ZnsSendRequest,
    generate_zalo_draft,
    send_zns_message,
    upsert_workspace_zalo_connection,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _make_auth(user: User, workspace: Workspace) -> AuthContext:
    return AuthContext.session(user=user)


async def test_zalo_draft_generation_pipeline(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """Test generating assisted Zalo draft and creating audit log."""
    lead = Lead(
        id=uuid4(),
        workspace_id=db_workspace.id,
        source="batdongsan",
        company_name="Nguyễn Văn An",
        location="Quận 1, TP.HCM",
        industry="Bất động sản",
        status="new",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        id=uuid4(),
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        phone="0987654321",
    )
    db_session.add(contact)
    await db_session.flush()

    auth = _make_auth(db_user, db_workspace)

    # Call endpoint handler
    resp = await generate_zalo_draft(
        lead_id=lead.id,
        workspace_id=db_workspace.id,
        payload=ZaloDraftRequest(custom_context="Liên hệ vào giờ hành chính"),
        auth=auth,
        session=db_session,
    )

    assert resp.lead_id == lead.id
    assert resp.clean_phone == "0987654321"
    assert resp.zalo_url == "https://zalo.me/0987654321"
    assert "BĐS" in resp.draft
    assert "Quận 1, TP.HCM" in resp.draft
    assert "Liên hệ vào giờ hành chính" in resp.draft

    # Verify message log was saved in DB
    log_stmt = select(ZaloMessageLog).where(ZaloMessageLog.lead_id == lead.id)
    log_res = await db_session.execute(log_stmt)
    log = log_res.scalar_one_or_none()

    assert log is not None
    assert log.workspace_id == db_workspace.id
    assert log.recipient_phone == "0987654321"
    assert log.message_type == "assisted_draft"
    assert log.status == "generated"


async def test_zalo_connection_upsert_and_encryption(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """Test creating Zalo OA connection with token encryption and reading it back."""
    auth = _make_auth(db_user, db_workspace)

    payload = ZaloConnectionCreate(
        oa_id="oa_test_12345",
        oa_name="Nowing Official OA",
        app_id="app_test_67890",
        access_token="secret_access_token_abc",
        refresh_token="secret_refresh_token_xyz",
        webhook_secret="webhook_secret_key",
        expires_in_seconds=3600,
    )

    # Upsert connection
    created = await upsert_workspace_zalo_connection(
        workspace_id=db_workspace.id,
        payload=payload,
        auth=auth,
        session=db_session,
    )

    assert created.oa_id == "oa_test_12345"
    assert created.oa_name == "Nowing Official OA"
    assert created.is_active is True

    # Read back from DB and verify encryption
    stmt = select(ZaloConnection).where(ZaloConnection.id == created.id)
    res = await db_session.execute(stmt)
    conn = res.scalar_one()

    # Raw field in DB should not match plaintext if SECRET_KEY is active
    assert conn.oa_id == "oa_test_12345"

    # Client instantiation should decrypt properly
    client = ZaloClient.from_connection(conn)
    assert client.oa_id == "oa_test_12345"
    assert client.access_token == "secret_access_token_abc"
    assert client.refresh_token == "secret_refresh_token_xyz"


async def test_zns_send_consent_guardrail_and_dispatch(
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    """Test Decree 356 consent enforcement and ZNS delivery."""
    lead = Lead(
        id=uuid4(),
        workspace_id=db_workspace.id,
        source="system",
        company_name="Trần Thị B",
        status="open",
        consent_status="unconsented",
    )
    db_session.add(lead)
    await db_session.flush()

    contact = VerifiedContact(
        id=uuid4(),
        workspace_id=db_workspace.id,
        lead_id=lead.id,
        phone="0901234567",
    )
    db_session.add(contact)
    await db_session.flush()

    # Create active Zalo connection
    conn = ZaloConnection(
        id=uuid4(),
        workspace_id=db_workspace.id,
        oa_id="oa_zns_test",
        access_token_encrypted="fake_token",
        is_active=True,
    )
    db_session.add(conn)
    await db_session.flush()

    auth = _make_auth(db_user, db_workspace)

    # 1. When consent_confirmed is False and lead has no consent -> 400 Bad Request
    with pytest.raises(HTTPException) as exc_info:
        await send_zns_message(
            lead_id=lead.id,
            workspace_id=db_workspace.id,
            payload=ZnsSendRequest(
                template_id="tpl_appointment_01",
                template_data={"name": "Trần Thị B"},
                consent_confirmed=False,
            ),
            auth=auth,
            session=db_session,
        )
    assert exc_info.value.status_code == 400
    assert "Decree 356" in exc_info.value.detail

    # 2. When consent_confirmed is True -> Dispatches via ZaloClient.send_zns
    with patch("app.routes.outbound_routes.ZaloClient") as mock_client_cls:
        mock_instance = AsyncMock()
        mock_instance.ensure_valid_token.return_value = "fake_token"
        mock_instance.send_zns.return_value = {
            "error": 0,
            "message": "Success",
            "data": {"msg_id": "zns_123456"},
        }
        mock_client_cls.from_connection.return_value = mock_instance

        resp = await send_zns_message(
            lead_id=lead.id,
            workspace_id=db_workspace.id,
            payload=ZnsSendRequest(
                template_id="tpl_appointment_01",
                template_data={"name": "Trần Thị B"},
                consent_confirmed=True,
            ),
            auth=auth,
            session=db_session,
        )

        assert resp.status == "sent"
        assert resp.msg_id == "zns_123456"
        assert resp.recipient_phone == "84901234567"


async def test_zalo_inbound_webhook_event_and_telegram_alert(
    db_session: AsyncSession,
    db_workspace: Workspace,
) -> None:
    """Test webhook event processing and buying intent detection."""
    conn = ZaloConnection(
        id=uuid4(),
        workspace_id=db_workspace.id,
        oa_id="oa_webhook_test",
        is_active=True,
    )
    db_session.add(conn)
    await db_session.flush()

    event_payload = {
        "event_name": "user_send_text",
        "oa_id": "oa_webhook_test",
        "sender": {"id": "0918889999"},
        "message": {
            "msg_id": "msg_ext_777",
            "text": "Chào Nowing, cho mình xin báo giá dịch vụ với ạ",
        },
        "timestamp": 1723700000,
    }

    with patch("app.gateway.zalo.telegram_alerts.send_telegram_lead_alert") as mock_telegram:
        mock_telegram.return_value = {"sent": True, "message_id": "tg_msg_101"}

        result = await handle_zalo_webhook_event(db_session, conn, event_payload)

        assert result["status"] == "ok"
        assert result["has_intent"] is True

        # Verify log entry in DB
        log_stmt = select(ZaloMessageLog).where(
            ZaloMessageLog.recipient_zalo_id == "0918889999"
        )
        log_res = await db_session.execute(log_stmt)
        log = log_res.scalar_one_or_none()

        assert log is not None
        assert log.message_type == "webhook_inbound"
        assert log.status == "received"
        assert "báo giá" in log.content
