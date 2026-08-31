"""Red-phase unit tests for app.gateway.email.sender (Story 6.10)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.skip("TDD red phase - Story 6.10 not implemented")]


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_reply_uses_original_from_as_to_and_smtp_from(mocker):
    """AC-7 P1: reply To=original From, From=SMTP_FROM, Reply-To=task+workspace_id."""
    from app.gateway.email.sender import send_email_reply

    smtp_mock = mocker.patch("app.gateway.email.sender._send_email_smtp")

    send_email_reply(
        original_from="user@example.com",
        original_subject="VCB",
        original_message_id="<orig-1@example.com>",
        workspace_id=1,
        body="Summary\nLink: https://nowing.ai/d/abc\n",
        degradation_reasons=[],
    )

    smtp_mock.assert_called_once()
    args = smtp_mock.call_args.kwargs
    assert args["to_email"] == "user@example.com"
    assert args["from_email"] == "task@nowing.ai"
    assert args["reply_to"] == "task+1@nowing.ai"
    assert args["subject"] == "Re: VCB"
    assert args["headers"]["In-Reply-To"] == "<orig-1@example.com>"


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_reply_includes_degradation_reasons():
    """AC-7 P1: reply includes degradation reasons when degraded."""
    from app.gateway.email.sender import build_reply_body

    body = build_reply_body(
        summary="Done",
        deliverable_link="https://nowing.ai/d/abc",
        degradation_reasons=["missing attachment"],
    )

    assert "Done" in body
    assert "https://nowing.ai/d/abc" in body
    assert "missing attachment" in body


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_smtp_exception_sets_status_replied_failed(mocker):
    """AC-7 P2: smtplib.SMTPException sets inbound_email_event.status=replied_failed."""
    from app.gateway.email.sender import send_email_reply

    mocker.patch("app.gateway.email.sender._send_email_smtp", side_effect=Exception("SMTP error"))
    audit_mock = mocker.patch("app.gateway.email.sender.audit")

    result = send_email_reply(
        original_from="user@example.com",
        original_subject="VCB",
        original_message_id="<orig-1@example.com>",
        workspace_id=1,
        body="Summary",
    )

    assert result["status"] == "replied_failed"
    audit_mock.assert_called_once()
    assert audit_mock.call_args.kwargs["action"] == "email_reply_failed"


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_missing_smtp_host_logs_warning(mocker):
    """AC-7 P2: missing SMTP_HOST logs warning but mission still completes."""
    from app.gateway.email.sender import send_email_reply

    mocker.patch("app.gateway.email.sender.config.SMTP_HOST", None)
    warning_mock = mocker.patch("app.gateway.email.sender.logger.warning")

    result = send_email_reply(
        original_from="user@example.com",
        original_subject="VCB",
        original_message_id="<orig-1@example.com>",
        workspace_id=1,
        body="Summary",
    )

    warning_mock.assert_called_once()
    assert result is not None


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_invalid_from_address_skips_send():
    """AC-7 P3: invalid From address does not attempt send."""
    from app.gateway.email.sender import send_email_reply

    result = send_email_reply(
        original_from="not-an-email",
        original_subject="VCB",
        original_message_id="<orig-1@example.com>",
        workspace_id=1,
        body="Summary",
    )

    assert result["attempted"] is False


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_reply_body_truncated_when_too_large():
    """AC-7 P3: reply body > MAX_REPLY_BODY_BYTES is truncated."""
    from app.gateway.email.sender import build_reply_body

    large_reason = "x" * 1024 * 1024
    body = build_reply_body("Done", "https://nowing.ai/d/abc", [large_reason])

    assert len(body.encode("utf-8")) <= 2 * 1024 * 1024
