"""Shared fixtures for phone_waterfall unit tests."""

from __future__ import annotations

import pytest

from app.config import config


@pytest.fixture(autouse=True)
def ensure_test_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure SECRET_KEY is always configured for TokenEncryption & VerifiedContactEncryption."""
    test_key = "test-secret-key-must-be-long-enough-12345678"
    monkeypatch.setattr(config, "SECRET_KEY", test_key)
