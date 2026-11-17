"""Unit tests for DSH configuration guards (Story 32.3)."""

from __future__ import annotations

import importlib

import pytest

import app.config.dsh as dsh_config

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _restore_dsh_config(monkeypatch):
    """Ensure app.config.dsh is cleanly reloaded in original dev state after each test."""
    yield
    monkeypatch.delenv("CDP_SESSION_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    importlib.reload(dsh_config)


def test_dsh_config_production_fails_when_secret_missing(monkeypatch):
    """In production environment, missing CDP_SESSION_SECRET must raise ValueError."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CDP_SESSION_SECRET", "")

    with pytest.raises(
        ValueError, match="CDP_SESSION_SECRET cannot be empty or default"
    ):
        importlib.reload(dsh_config)


def test_dsh_config_production_fails_when_secret_is_dev_default(monkeypatch):
    """In production environment, default CDP_SESSION_SECRET must raise ValueError."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CDP_SESSION_SECRET", dsh_config.CDP_SESSION_DEV_DEFAULT)

    with pytest.raises(
        ValueError, match="CDP_SESSION_SECRET cannot be empty or default"
    ):
        importlib.reload(dsh_config)


def test_dsh_config_production_succeeds_with_valid_secret(monkeypatch):
    """In production environment, a non-default secret should load without error."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CDP_SESSION_SECRET", "super-secure-production-cdp-secret")

    reloaded = importlib.reload(dsh_config)
    assert reloaded.CDP_SESSION_SECRET == "super-secure-production-cdp-secret"


def test_dsh_config_development_allows_default_secret(monkeypatch):
    """In development environment, default CDP_SESSION_SECRET must not raise."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("CDP_SESSION_SECRET", dsh_config.CDP_SESSION_DEV_DEFAULT)

    reloaded = importlib.reload(dsh_config)
    assert reloaded.CDP_SESSION_SECRET == dsh_config.CDP_SESSION_DEV_DEFAULT
