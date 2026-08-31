"""Red-phase unit tests for app.gateway.email.auth (Story 6.10)."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.skip("TDD red phase - Story 6.10 not implemented")]


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_sendgrid_signature_valid():
    """AC-1 P2: valid SendGrid webhook signature passes verification."""
    from app.gateway.email.auth import verify_sendgrid_signature

    public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAy...
-----END PUBLIC KEY-----"""

    is_valid = verify_sendgrid_signature(
        public_key=public_key,
        signature="valid-sig",
        timestamp="1234567890",
        raw_body=b"{}",
    )
    assert is_valid is True


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_sendgrid_signature_invalid_fails():
    """AC-1 P2: signature mismatch returns False and logs audit event."""
    from app.gateway.email.auth import verify_sendgrid_signature

    public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAy...
-----END PUBLIC KEY-----"""

    is_valid = verify_sendgrid_signature(
        public_key=public_key,
        signature="invalid-sig",
        timestamp="1234567890",
        raw_body=b"{}",
    )
    assert is_valid is False


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_mailgun_signature_valid():
    """AC-1 P2: valid Mailgun signature passes HMAC verification."""
    from app.gateway.email.auth import verify_mailgun_signature

    signing_key = "test-key"
    timestamp = str(int(time.time()))
    token = "token123"
    expected = hmac.new(
        signing_key.encode(),
        f"{timestamp}{token}".encode(),
        hashlib.sha256,
    ).hexdigest()

    is_valid = verify_mailgun_signature(
        signing_key=signing_key,
        signature=expected,
        timestamp=timestamp,
        token=token,
    )
    assert is_valid is True


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_mailgun_replay_attack_rejected():
    """AC-1 P2: Mailgun timestamp older than 15 minutes rejected."""
    from app.gateway.email.auth import verify_mailgun_signature

    old_ts = str(int(time.time()) - 16 * 60)
    signature = hmac.new(b"test-key", f"{old_ts}token".encode(), hashlib.sha256).hexdigest()

    is_valid = verify_mailgun_signature(
        signing_key="test-key",
        signature=signature,
        timestamp=old_ts,
        token="token",
    )
    assert is_valid is False


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_compute_dedupe_key_sha256():
    """AC-1 P4: dedupe_key = SHA-256(provider + message_id)."""
    from app.gateway.email.auth import compute_dedupe_key

    expected = hashlib.sha256(b"sendgrid<msg-1@example.com>").hexdigest()
    assert compute_dedupe_key("sendgrid", "<msg-1@example.com>") == expected


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_fallback_dedupe_key_with_rounded_timestamp():
    """AC-8 P4: fallback dedupe key from provider+from+to+subject+body+minute-rounded ts."""
    from app.gateway.email.auth import compute_fallback_dedupe_key

    key = compute_fallback_dedupe_key(
        provider="sendgrid",
        from_address="user@example.com",
        to_address="task+1@nowing.ai",
        subject="VCB",
        body_text="body",
        created_minute_ts=1600000000,
    )
    expected = hashlib.sha256(
        b"sendgriduser@example.comtask+1@nowing.aiVCBbody1600000000"
    ).hexdigest()
    assert key == expected


@pytest.mark.skip("TDD red phase - Story 6.10 not implemented")
def test_audit_event_logged_on_signature_failure(mocker):
    """AC-1 P5: audit_events row written with action email_webhook_verification_failed."""
    from app.gateway.email.auth import verify_sendgrid_signature

    audit_mock = mocker.patch("app.gateway.email.auth.audit")

    verify_sendgrid_signature(
        public_key="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
        signature="bad",
        timestamp="1",
        raw_body=b"{}",
    )

    audit_mock.assert_called_once()
    assert audit_mock.call_args.kwargs["action"] == "email_webhook_verification_failed"
    assert audit_mock.call_args.kwargs["provider"] == "sendgrid"
