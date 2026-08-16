"""Unit tests for Zalo OA Webhook HMAC signature verification and replay defense (INV-23.7, INV-23.8)."""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest


@pytest.mark.unit
def test_zalo_webhook_hmac_signature_valid():
    """Verify that a valid HMAC-SHA256 signature calculated from raw bytes passes validation."""
    from app.gateway.zalo.webhook import verify_zalo_signature  # Red-phase import

    secret = "test_oa_secret_123"
    raw_body = b'{"event_name": "user_send_text", "timestamp": "1723800000", "sender": {"id": "123"}}'
    valid_signature = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    is_valid = verify_zalo_signature(
        raw_body=raw_body,
        signature=valid_signature,
        secret=secret,
    )
    assert is_valid is True


@pytest.mark.unit
def test_zalo_webhook_hmac_signature_invalid_fails():
    """Verify that an invalid HMAC signature fails validation."""
    from app.gateway.zalo.webhook import verify_zalo_signature  # Red-phase import

    secret = "test_oa_secret_123"
    raw_body = b'{"event_name": "user_send_text", "timestamp": "1723800000"}'
    fake_signature = "bad_signature_hash_000000000000000000000000000000000000000000000000"

    is_valid = verify_zalo_signature(
        raw_body=raw_body,
        signature=fake_signature,
        secret=secret,
    )
    assert is_valid is False


@pytest.mark.unit
def test_zalo_webhook_timestamp_replay_defense():
    """Verify that incoming webhook requests with timestamp delta > 300s are rejected."""
    from app.gateway.zalo.webhook import check_timestamp_freshness  # Red-phase import

    now = int(time.time())

    # Fresh timestamp (within 300 seconds)
    assert check_timestamp_freshness(timestamp=now - 60, max_drift_seconds=300) is True

    # Expired timestamp (older than 300 seconds -> replay attack)
    assert check_timestamp_freshness(timestamp=now - 301, max_drift_seconds=300) is False

    # Future timestamp beyond allowed threshold
    assert check_timestamp_freshness(timestamp=now + 301, max_drift_seconds=300) is False
