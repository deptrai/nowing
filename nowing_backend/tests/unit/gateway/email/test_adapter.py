"""Red-phase unit tests for app.gateway.email.adapter (Story 6.10)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit]


def test_parse_sendgrid_payload_returns_normalized_inbound_event():
    """AC-1 P1: SendGrid MIME multipart payload parsed to ParsedInboundEvent."""
    from app.gateway.email.adapter import EmailAdapter

    raw_payload = {
        "email": "Content-Type: multipart/alternative; boundary=boundary123\n\n--boundary123\n"
        "Content-Type: text/plain\n\nTheo dõi giá cổ phiếu VCB\n"
        "--boundary123\nContent-Type: text/html\n\n<html><body>VCB</body></html>\n"
        "--boundary123--",
        "headers": {
            "Message-Id": "<msg-1@example.com>",
            "From": "user@example.com",
            "To": "task+1@nowing.ai",
            "Subject": "VCB 30 days",
        },
    }

    adapter = EmailAdapter()
    event = adapter.parse_inbound(raw_payload)

    assert event.platform == "email"
    assert event.event_kind == "inbound"
    assert event.external_message_id == "<msg-1@example.com>"
    assert event.external_user_id == "user@example.com"
    assert event.external_peer_id == "task+1@nowing.ai"
    assert event.text == "Theo dõi giá cổ phiếu VCB"
    assert event.metadata["subject"] == "VCB 30 days"
    assert event.metadata["attachments"] == []


def test_parse_mailgun_payload_returns_normalized_inbound_event():
    """AC-1 P1: Mailgun parsed JSON payload normalized to ParsedInboundEvent."""
    from app.gateway.email.adapter import EmailAdapter

    raw_payload = {
        "Message-Id": "<msg-2@example.com>",
        "sender": "user@example.com",
        "recipient": "task+2@nowing.ai",
        "subject": "Report VCB",
        "body-plain": "Theo dõi giá cổ phiếu VCB trong 30 ngày",
        "body-html": "<p>Theo dõi giá cổ phiếu VCB trong 30 ngày</p>",
        "attachments": [],
    }

    adapter = EmailAdapter()
    event = adapter.parse_inbound(raw_payload)

    assert event.platform == "email"
    assert event.event_kind == "inbound"
    assert event.external_message_id == "<msg-2@example.com>"
    assert event.external_user_id == "user@example.com"
    assert event.external_peer_id == "task+2@nowing.ai"
    assert event.text == "Theo dõi giá cổ phiếu VCB trong 30 ngày"
    assert event.metadata["subject"] == "Report VCB"


def test_parse_email_preserves_fields_not_raw_tokens():
    """AC-1 P1: parsed event contains expected fields, not raw provider tokens."""
    from app.gateway.email.adapter import EmailAdapter

    raw = {
        "email": "From: a@b\nTo: task+1@nowing.ai\nSubject: x\n\nbody",
        "dkim": "secret-token-must-not-be-stored",
        "SPF": "pass",
    }

    event = EmailAdapter().parse_inbound(raw)

    assert event.raw_payload.get("dkim") is None
    assert event.text == "body"


def test_extract_workspace_id_from_to_address():
    """AC-2 P4: numeric workspace_id extracted from task+123@nowing.ai."""
    from app.gateway.email.adapter import _extract_workspace_id

    assert _extract_workspace_id("task+123@nowing.ai") == 123


def test_extract_workspace_id_rejects_non_numeric_alias():
    """AC-2 P3/P4: non-numeric alias in To address returns None (manual review)."""
    from app.gateway.email.adapter import _extract_workspace_id

    assert _extract_workspace_id("task+ abc @nowing.ai") is None
    assert _extract_workspace_id("task@nowing.ai") is None


def test_extract_base_email_strips_plus_tag():
    """AC-2 P3: From address user+tag@example.com matches base email."""
    from app.gateway.email.adapter import _normalize_email

    assert _normalize_email("User+Tag@Example.COM") == "user@example.com"


def test_select_first_matching_workspace_recipient():
    """AC-1/AC-2 P3: multiple To recipients, select first matching task+{id}@nowing.ai."""
    from app.gateway.email.adapter import _select_recipient

    recipients = ["other@example.com", "task+5@nowing.ai", "task+6@nowing.ai"]
    assert _select_recipient(recipients, domain="nowing.ai") == "task+5@nowing.ai"


def test_html_only_email_falls_back_to_stripped_text():
    """AC-2/AC-4 P3: empty body_text and present body_html extracts text fallback."""
    from app.gateway.email.adapter import EmailAdapter

    raw = {
        "Message-Id": "<msg-html@example.com>",
        "sender": "user@example.com",
        "recipient": "task+1@nowing.ai",
        "subject": "HTML only",
        "body-plain": "",
        "body-html": "<p>Theo dõi <b>VCB</b> 30 ngày</p>",
    }

    event = EmailAdapter().parse_inbound(raw)

    assert event.text == "Theo dõi VCB 30 ngày"


def test_email_body_too_large_returns_413():
    """AC-1 P3: body > MAX_EMAIL_SIZE_BYTES returns 413 Payload Too Large."""
    from app.gateway.email.adapter import EmailAdapter

    adapter = EmailAdapter()
    with pytest.raises(Exception) as exc_info:  # noqa: B017
        adapter.parse_inbound({"body-plain": "x" * (31 * 1024 * 1024)})

    assert "413" in str(exc_info.value)


def test_attachment_list_returns_empty_list_when_missing():
    """AC-1 P2: missing attachments becomes []."""
    from app.gateway.email.adapter import EmailAdapter

    event = EmailAdapter().parse_inbound({
        "Message-Id": "<no-attach@example.com>",
        "sender": "user@example.com",
        "recipient": "task+1@nowing.ai",
        "subject": "No attach",
        "body-plain": "body",
    })

    assert event.metadata.get("attachments") == []
