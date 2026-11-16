"""Unit tests for dev quota bypass (spec 42.8).

Bypass matrix: NOWING_DEV_BYPASS_QUOTA=1 + self-hosted + non-prod env → on.
Cloud deployment, production env, DEBUG=true → off.
"""

from __future__ import annotations

import pytest

from app.config import dev_quota_bypass_active
from app.services.token_quota_service import QuotaResult, TokenQuotaService


@pytest.fixture(autouse=True)
def _reset_warn_latch(monkeypatch):
    """Reset warn latch giữa các test để mỗi test kiểm chứng độc lập."""
    import app.config.quota as quota_mod

    monkeypatch.setattr(quota_mod, "_DEV_QUOTA_BYPASS_WARNED", False)
    yield
    quota_mod._DEV_QUOTA_BYPASS_WARNED = False


@pytest.fixture
def self_hosted(monkeypatch):
    """Mock config.is_self_hosted() → True (patch predicate trên class)."""
    from app.config import Config

    monkeypatch.setattr(Config, "is_self_hosted", classmethod(lambda cls: True))


class TestDevQuotaBypassMatrix:
    def test_on_self_hosted_dev(self, self_hosted, monkeypatch):
        """BYPASS_OK: flag=1 + self-hosted + env missing → active."""
        monkeypatch.setenv("NOWING_DEV_BYPASS_QUOTA", "1")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("APP_ENV", raising=False)
        assert dev_quota_bypass_active() is True

    def test_off_cloud(self, monkeypatch):
        """BYPASS_CLOUD: DEPLOYMENT_MODE=cloud → flag ignored."""
        from app.config import Config

        monkeypatch.setattr(Config, "is_self_hosted", classmethod(lambda cls: False))
        monkeypatch.setenv("NOWING_DEV_BYPASS_QUOTA", "1")
        assert dev_quota_bypass_active() is False

    def test_off_self_hosted_production(self, self_hosted, monkeypatch):
        """BYPASS_PROD: self-hosted + ENVIRONMENT=production → flag ignored."""
        monkeypatch.setenv("NOWING_DEV_BYPASS_QUOTA", "1")
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert dev_quota_bypass_active() is False

    def test_off_flag_unset(self, self_hosted, monkeypatch):
        """Flag unset → không bypass kể cả khi self-hosted dev."""
        monkeypatch.delenv("NOWING_DEV_BYPASS_QUOTA", raising=False)
        assert dev_quota_bypass_active() is False

    def test_off_debug_only(self, self_hosted, monkeypatch):
        """DEBUG_ONLY: DEBUG=true không tự bypass."""
        monkeypatch.delenv("NOWING_DEV_BYPASS_QUOTA", raising=False)
        monkeypatch.setenv("DEBUG", "true")
        assert dev_quota_bypass_active() is False

    def test_off_prod_alias(self, self_hosted, monkeypatch):
        """ENVIRONMENT=prod (alias) → cũng bị chặn."""
        monkeypatch.setenv("NOWING_DEV_BYPASS_QUOTA", "1")
        monkeypatch.setenv("APP_ENV", "prod")
        assert dev_quota_bypass_active() is False


class TestWarnLatch:
    def test_warn_logged_once(self, self_hosted, monkeypatch, caplog):
        """Bypass active → warning log đúng 1 lần dù gọi nhiều lần."""
        import logging

        monkeypatch.setenv("NOWING_DEV_BYPASS_QUOTA", "1")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        with caplog.at_level(logging.WARNING, logger="app.config.quota"):
            assert dev_quota_bypass_active() is True
            assert dev_quota_bypass_active() is True
        warns = [r for r in caplog.records if "dev quota bypass active" in r.message]
        assert len(warns) == 1


class TestQuotaSeam:
    @pytest.mark.asyncio
    async def test_credit_reserve_bypass_allows_without_db(self, self_hosted, monkeypatch):
        """credit_reserve khi bypass → allow sớm, không chạm DB."""
        monkeypatch.setenv("NOWING_DEV_BYPASS_QUOTA", "1")
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        class _FailingSession:  # mọi DB access đều là bug
            def execute(self, *a, **k):
                raise AssertionError("credit_reserve must early-return under bypass")

        result = await TokenQuotaService.credit_reserve(
            _FailingSession(), user_id="u1", request_id="r1", reserve_micros=1000
        )
        assert isinstance(result, QuotaResult)
        assert result.allowed is True
        assert result.status.value == "ok"

    @pytest.mark.asyncio
    async def test_credit_get_usage_bypass_zero_usage(self, self_hosted, monkeypatch):
        """credit_get_usage khi bypass → zero-usage, allowed=True."""
        monkeypatch.setenv("NOWING_DEV_BYPASS_QUOTA", "1")
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        class _FailingSession:
            def execute(self, *a, **k):
                raise AssertionError("credit_get_usage must early-return under bypass")

        result = await TokenQuotaService.credit_get_usage(_FailingSession(), user_id="u1")
        assert isinstance(result, QuotaResult)
        assert result.allowed is True
        assert result.balance == 0

    @pytest.mark.asyncio
    async def test_credit_reserve_no_bypass_hits_db(self, self_hosted, monkeypatch):
        """Không bypass → chạy path bình thường (user None → BLOCKED)."""
        monkeypatch.delenv("NOWING_DEV_BYPASS_QUOTA", raising=False)

        class _FakeResult:
            def unique(self):
                return self

            def scalar_one_or_none(self):
                return None

        class _FakeSession:
            async def execute(self, *a, **k):
                return _FakeResult()

        result = await TokenQuotaService.credit_reserve(
            _FakeSession(), user_id="u1", request_id="r1", reserve_micros=1000
        )
        assert result.allowed is False
        assert result.status.value == "blocked"
