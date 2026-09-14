"""Unit tests for centralized XACT_* error map (AD-10 / Story 36.3).

Ensures pure logic behavior without Celery worker or Celery imports.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

from app.proprietary.platforms.xactions import error_map
from app.proprietary.platforms.xactions.error_map import (
    TaskBehavior,
    clamp_cooldown,
    clamp_countdown,
    resolve_task_behavior,
)
from app.proprietary.platforms.xactions.mcp_client import XActionsMcpError


class TestClampCountdown:
    def test_clamp_countdown_normal_in_range(self):
        assert clamp_countdown(45) == 45

    def test_clamp_countdown_none_returns_default(self):
        assert clamp_countdown(None) == 30

    def test_clamp_countdown_below_lo(self):
        assert clamp_countdown(3) == 5

    def test_clamp_countdown_above_hi(self):
        assert clamp_countdown(99999) == 3600

    def test_clamp_countdown_zero_returns_default(self):
        assert clamp_countdown(0) == 30

    def test_clamp_countdown_negative_returns_default(self):
        assert clamp_countdown(-10) == 30

    def test_clamp_countdown_string_numeric(self):
        assert clamp_countdown("45") == 45

    def test_clamp_countdown_string_invalid(self):
        assert clamp_countdown("not-a-number") == 30

    def test_clamp_countdown_nan_returns_default(self):
        assert clamp_countdown(float("nan")) == 30

    def test_clamp_countdown_inf_returns_default(self):
        assert clamp_countdown(float("inf")) == 30
        assert clamp_countdown(float("-inf")) == 30

    def test_clamp_countdown_bool_returns_default(self):
        assert clamp_countdown(True) == 30
        assert clamp_countdown(False) == 30

    def test_clamp_countdown_overflow(self):
        assert clamp_countdown(10**1000) == 30

    def test_clamp_countdown_custom_parameters(self):
        assert clamp_countdown(None, default=15, lo=10, hi=100) == 15
        assert clamp_countdown(5, default=15, lo=10, hi=100) == 10
        assert clamp_countdown(200, default=15, lo=10, hi=100) == 100


class TestClampCooldown:
    def test_clamp_cooldown_normal_in_range(self):
        assert clamp_cooldown(1200) == 1200

    def test_clamp_cooldown_none_returns_default(self):
        assert clamp_cooldown(None) == 600

    def test_clamp_cooldown_below_lo(self):
        assert clamp_cooldown(10) == 60

    def test_clamp_cooldown_above_hi(self):
        assert clamp_cooldown(100000) == 86400

    def test_clamp_cooldown_zero_returns_default(self):
        assert clamp_cooldown(0) == 600

    def test_clamp_cooldown_negative_returns_default(self):
        assert clamp_cooldown(-50) == 600

    def test_clamp_cooldown_string_numeric(self):
        assert clamp_cooldown("1200") == 1200

    def test_clamp_cooldown_string_invalid(self):
        assert clamp_cooldown("bad") == 600

    def test_clamp_cooldown_nan_returns_default(self):
        assert clamp_cooldown(float("nan")) == 600

    def test_clamp_cooldown_inf_returns_default(self):
        assert clamp_cooldown(float("inf")) == 600
        assert clamp_cooldown(float("-inf")) == 600

    def test_clamp_cooldown_bool_returns_default(self):
        assert clamp_cooldown(True) == 600
        assert clamp_cooldown(False) == 600

    def test_clamp_cooldown_overflow(self):
        assert clamp_cooldown(10**1000) == 600

    def test_clamp_cooldown_custom_parameters(self):
        assert clamp_cooldown(None, default=300, lo=100, hi=1000) == 300
        assert clamp_cooldown(50, default=300, lo=100, hi=1000) == 100
        assert clamp_cooldown(5000, default=300, lo=100, hi=1000) == 1000


class TestCanonicalCodesMapping:
    def test_rate_limit_4291(self):
        err = XActionsMcpError("Rate limit exceeded", code="XACT_4291", retry_after=45)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.RETRY
        assert decision.countdown == 45
        assert decision.max_retries == 5
        assert decision.exhausted_behavior == TaskBehavior.HALT
        assert decision.write_dlq is False
        assert "Rate limit exceeded" in decision.reason

    def test_rate_limit_4291_no_retry_after(self):
        err = XActionsMcpError("Rate limit", code="XACT_4291", retry_after=None)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.RETRY
        assert decision.countdown == 30
        assert decision.max_retries == 5

    def test_rate_limit_4291_large_retry_after(self):
        err = XActionsMcpError("Rate limit", code="XACT_4291", retry_after=99999)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.RETRY
        assert decision.countdown == 3600

    def test_account_hibernation(self):
        err = XActionsMcpError("Account hibernated", code="ACCOUNT_HIBERNATION", retry_after=1200)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 1200
        assert "Account hibernated" in decision.reason

    def test_proxy_exhausted(self):
        err = XActionsMcpError("Proxy exhausted", code="PROXY_EXHAUSTED")
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 600
        assert "Proxy exhausted" in decision.reason

    def test_5030_temporary_unavailable(self):
        err = XActionsMcpError("Service unavailable", code="XACT_5030", retry_after=300)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 300
        assert "Service unavailable" in decision.reason

    def test_auth_fatal_4010(self):
        err = XActionsMcpError("Invalid credentials", code="XACT_4010")
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.HALT
        assert "Invalid credentials" in decision.reason

    def test_signer_crash_5000(self):
        err = XActionsMcpError("Signer crashed", code="XACT_5000")
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.RETRY
        assert decision.countdown == 60
        assert decision.max_retries == 3
        assert decision.exhausted_behavior == TaskBehavior.HALT
        assert decision.write_dlq is True
        assert "Signer crashed" in decision.reason

    def test_bad_request_4001_with_suggested_action(self):
        err = XActionsMcpError(
            "Bad query params",
            code="XACT_4001",
            retry_after=400,
            suggested_action="check workspace config",
        )
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 400
        assert decision.suggested_action == "check workspace config"
        assert "Bad query params" in decision.reason
        # suggested_action is surfaced via decision.suggested_action (logged
        # once by _pause_target), not duplicated inside decision.reason.
        assert "check workspace config" not in decision.reason

    def test_bad_request_4001_without_suggested_action(self):
        err = XActionsMcpError("Bad query", code="XACT_4001")
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 600
        assert decision.suggested_action is None
        assert "Bad query" in decision.reason


class TestEdgeCasesAndCoercion:
    def test_case_insensitive_and_whitespace(self):
        err = XActionsMcpError("rate limit", code="  xact_4291  ", retry_after=50)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.RETRY
        assert decision.countdown == 50

    def test_unmapped_code_defaults_to_pause(self):
        err = XActionsMcpError("Unknown error", code="XACT_9999", retry_after=180)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 180
        assert "unmapped code XACT_9999" in decision.reason
        assert "Unknown error" in decision.reason

    def test_none_code_defaults_to_pause(self):
        err = XActionsMcpError("No code error", code=None)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 600
        assert "unmapped code None" in decision.reason

    def test_int_code_defaults_to_pause_no_crash(self):
        err = MagicMock(code=5001, message="Integer code", retry_after=None)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 600
        assert "unmapped code 5001" in decision.reason

    def test_empty_string_code_defaults_to_pause(self):
        err = MagicMock(code="", message="Empty code", retry_after=None)
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 600

    def test_arbitrary_exception_without_code_attr(self):
        err = RuntimeError("Plain runtime error")
        decision = resolve_task_behavior(err)
        assert decision.behavior == TaskBehavior.PAUSE
        assert decision.cooldown_seconds == 600
        assert "Plain runtime error" in decision.reason

    def test_custom_default_raise(self):
        err = RuntimeError("Unhandled")
        decision = resolve_task_behavior(err, default=TaskBehavior.RAISE)
        assert decision.behavior == TaskBehavior.RAISE
        assert decision.cooldown_seconds is None


class TestCeleryIndependence:
    def test_error_map_does_not_import_celery(self):
        source = inspect.getsource(error_map)
        assert "celery" not in source
        assert "task.retry" not in source
        for attr_name, attr_val in vars(error_map).items():
            mod = getattr(attr_val, "__module__", "")
            if mod:
                assert not mod.startswith("celery"), f"{attr_name} has module {mod}"
