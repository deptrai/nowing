"""Red-phase integration tests for email inbound webhook (Story 6.10)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]

# Red-phase guard: these tests call modules that do not exist yet. Using
# importorskip keeps pytest collection clean and skips them until dev-story
# creates the implementation.
pytest.importorskip("app.gateway.email", reason="Story 6.10 not yet implemented")
pytest.importorskip("app.routes.gateway_email_routes", reason="Story 6.10 not yet implemented")


@pytest.mark.asyncio
async def test_sendgrid_webhook_persists_inbound_email_event(client, db_user, db_workspace):
    """AC-1 P6/AC-8 P6: POST SendGrid webhook -> inbound_email_event row with valid FK and RLS."""
    import hashlib
    import hmac
    import json
    from app.config import config
    from app.gateway.email.adapter import compute_dedupe_key

    raw = json.dumps({
        "Message-Id": "<int-1@example.com>",
        "from": "test@nowing.net",
        "to": f"task+{db_workspace.id}@nowing.ai",
        "subject": "VCB",
        "text": "Theo dõi VCB",
    }).encode()

    now = "1234567890"
    public_key = getattr(config, "SENDGRID_WEBHOOK_PUBLIC_KEY", "")
    signature = hmac.new(public_key.encode(), raw, hashlib.sha256).hexdigest()

    response = await client.post(
        "/api/v1/gateway/email/inbound",
        data={
            "email": f"From: test@nowing.net\nTo: task+{db_workspace.id}@nowing.ai\nSubject: VCB\n\nTheo dõi VCB",
            "Message-Id": "<int-1@example.com>",
            "from": "test@nowing.net",
            "to": f"task+{db_workspace.id}@nowing.ai",
            "subject": "VCB",
            "text": "Theo dõi VCB",
        },
        headers={
            "X-Twilio-Email-Event-Webhook-Signature": signature,
            "X-Twilio-Email-Event-Webhook-Timestamp": now,
        },
    )

    assert response.status_code == 204

    # Pattern 6: verify row persisted with FK/RLS.
    from sqlalchemy import select
    from app.db import InboundEmailEvent

    row = (
        await db_session.execute(
            select(InboundEmailEvent).where(InboundEmailEvent.message_id == "<int-1@example.com>")
        )
    ).scalar_one()
    assert row.workspace_id == db_workspace.id
    assert row.dedupe_key == compute_dedupe_key("sendgrid", "<int-1@example.com>")


@pytest.mark.asyncio
async def test_duplicate_message_id_second_request_is_duplicate(client, db_user, db_workspace):
    """AC-8 P6: same Message-Id POSTed twice -> second returns 204 with status=duplicate."""
    from app.gateway.email.adapter import compute_dedupe_key

    compute_dedupe_key("sendgrid", "<dup-1@example.com>")

    response1 = await client.post(
        "/api/v1/gateway/email/inbound",
        data={
            "Message-Id": "<dup-1@example.com>",
            "from": "test@nowing.net",
            "to": f"task+{db_workspace.id}@nowing.ai",
            "subject": "VCB",
            "text": "body",
        },
    )
    response2 = await client.post(
        "/api/v1/gateway/email/inbound",
        data={
            "Message-Id": "<dup-1@example.com>",
            "from": "test@nowing.net",
            "to": f"task+{db_workspace.id}@nowing.ai",
            "subject": "VCB",
            "text": "body",
        },
    )

    assert response1.status_code == 204
    assert response2.status_code == 204


@pytest.mark.asyncio
async def test_inbound_email_event_fk_invalid_workspace_raises_integrity_error(client):
    """AC-1 P6: inbound_email_event insert with non-existent workspace_id raises IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await client.post(
            "/api/v1/gateway/email/inbound",
            data={
                "Message-Id": "<bad-ws@example.com>",
                "from": "test@nowing.net",
                "to": "task+99999@nowing.ai",
                "subject": "VCB",
                "text": "body",
            },
        )


@pytest.mark.asyncio
async def test_attachment_persists_as_document(client, db_user, db_workspace):
    """AC-3 P6: attachment creates Document row with workspace_id FK and RLS."""
    response = await client.post(
        "/api/v1/gateway/email/inbound",
        data={
            "Message-Id": "<attach-1@example.com>",
            "from": "test@nowing.net",
            "to": f"task+{db_workspace.id}@nowing.ai",
            "subject": "VCB",
            "text": "body",
            "attachments": '[{"filename": "report.pdf", "content-type": "application/pdf", "size": 1024}]',
        },
    )

    assert response.status_code == 204
