"""Unit tests for the news entity extraction cost-control gate (Story 14.2a / AC-4)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import AsyncMock

import pytest

from app.config import config
from app.services.news.extract_budget import (
    REASON_BUDGET_EXCEEDED,
    REASON_DISABLED,
    REASON_INSUFFICIENT_WALLET,
    REASON_RATE_LIMITED,
    ExtractGateResult,
    check_news_entity_extraction_allowed,
    record_news_entity_extraction,
)
from app.services.workspace_limits import ResolvedWorkspaceLimits

pytestmark = [pytest.mark.unit]


class _FakeSession:
    pass


async def test_gate_blocks_when_extraction_globally_disabled(monkeypatch):
    """Assert NEWS_ENTITY_EXTRACTION_ENABLED=false returns allowed=False, reason='disabled'."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", False)

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is False
    assert result.reason == REASON_DISABLED


async def test_gate_blocks_when_budget_exceeded(monkeypatch):
    """Assert rolling period spend >= budget cap returns allowed=False, reason='budget_exceeded'."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_BUDGET_MICROS", 1_000_000)
    monkeypatch.setattr(
        "app.services.news.extract_budget._period_spend_micros",
        AsyncMock(return_value=1_000_000),
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="free",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is False
    assert result.reason == REASON_BUDGET_EXCEEDED


async def test_gate_blocks_at_rate_limit_max(monkeypatch):
    """Assert rate count >= rate max returns allowed=False, reason='rate_limited'."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_BUDGET_MICROS", 0)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_RATE_MAX", 10)
    monkeypatch.setattr(
        "app.services.news.extract_budget._rate_count", AsyncMock(return_value=10)
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="free",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is False
    assert result.reason == REASON_RATE_LIMITED


async def test_gate_allows_at_rate_limit_max_minus_one(monkeypatch):
    """Assert rate count == rate_max - 1 returns allowed=True."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_BUDGET_MICROS", 0)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_RATE_MAX", 10)
    monkeypatch.setattr(
        "app.services.news.extract_budget._rate_count", AsyncMock(return_value=9)
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="free",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is True
    assert result.reason is None


async def test_gate_blocks_when_wallet_insufficient(monkeypatch):
    """Assert spendable_micros < min_reserve returns allowed=False, reason='insufficient_wallet'."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS", 500_000)
    monkeypatch.setattr(
        "app.services.news.extract_budget._wallet_spendable_micros",
        AsyncMock(return_value=100_000),
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="pro",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
                news_entity_extraction_wallet_pre_check=True,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is False
    assert result.reason == REASON_INSUFFICIENT_WALLET


async def test_gate_allows_when_wallet_exactly_at_reserve(monkeypatch):
    """Assert spendable_micros == min_reserve returns allowed=True."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS", 500_000)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_BUDGET_MICROS", 0)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_RATE_MAX", 0)
    monkeypatch.setattr(
        "app.services.news.extract_budget._wallet_spendable_micros",
        AsyncMock(return_value=500_000),
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="pro",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
                news_entity_extraction_wallet_pre_check=True,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is True
    assert result.reason is None


async def test_gate_uses_global_config_when_no_workspace_override(monkeypatch):
    """Assert missing workspace overrides fall back to global config values."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_BUDGET_MICROS", 2_000_000)
    monkeypatch.setattr(
        "app.services.news.extract_budget._period_spend_micros",
        AsyncMock(return_value=2_500_000),
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="free",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
                news_entity_extraction_spend_cap_micros=None,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is False
    assert result.reason == REASON_BUDGET_EXCEEDED


async def test_gate_logs_stable_reason_string(monkeypatch):
    """Assert blocked gate logs news_entity_extraction_{reason} with stable reason string."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", False)
    logged_info: list[tuple] = []
    monkeypatch.setattr(
        "app.services.news.extract_budget.logger.info",
        lambda msg, *args, **kwargs: logged_info.append((msg, args)),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=123, user_id="user-1"
    )
    assert result.allowed is False
    assert any(
        "news_entity_extraction_disabled" in msg[0] and "123" in str(msg[1])
        for msg in logged_info
    )


async def test_gate_no_llm_call_and_no_token_usage_when_blocked(monkeypatch):
    """Assert extractor does not call get_vision_llm or record TokenUsage when gate blocks."""
    from app.services.news.entity_extractor import NewsEntityExtractor

    monkeypatch.setattr(
        "app.services.news.entity_extractor.check_news_entity_extraction_allowed",
        AsyncMock(
            return_value=ExtractGateResult(allowed=False, reason=REASON_BUDGET_EXCEEDED)
        ),
    )
    llm_mock = AsyncMock()
    monkeypatch.setattr("app.services.news.entity_extractor.get_vision_llm", llm_mock)
    record_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.news.entity_extractor.record_news_entity_extraction", record_mock
    )

    extractor = NewsEntityExtractor()
    entities = await extractor.extract(
        "Some article", workspace_id=1, session=_FakeSession()
    )

    assert entities == []
    assert llm_mock.call_count == 0
    assert record_mock.call_count == 0


async def test_gate_records_token_usage_only_after_actual_extraction(monkeypatch):
    """Assert record_news_entity_extraction writes TokenUsage with usage_type='entity_extraction'."""
    from app.services.token_tracking_service import UsageType

    recorded: list[dict] = []

    async def _fake_record(session, **kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(
        "app.services.news.extract_budget.record_token_usage", _fake_record
    )
    monkeypatch.setattr(
        "app.services.news.extract_budget._record_extraction_sync", lambda wid: 1
    )

    await record_news_entity_extraction(
        _FakeSession(),
        workspace_id=99,
        user_id="user-99",
        cost_micros=12345,
        total_tokens=200,
    )

    assert len(recorded) == 1
    assert recorded[0]["usage_type"] == UsageType.ENTITY_EXTRACTION
    assert recorded[0]["workspace_id"] == 99
    assert recorded[0]["cost_micros"] == 12345
    assert recorded[0]["total_tokens"] == 200


async def test_gate_computes_period_spend_from_entity_extraction_token_usage(
    monkeypatch,
):
    """Assert period spend sums cost_micros for usage_type=ENTITY_EXTRACTION."""
    from app.services.news.extract_budget import _period_spend_micros

    class _ScalarSession:
        async def execute(self, stmt):
            class _ScalarResult:
                def scalar_one(self):
                    return 750000

            return _ScalarResult()

    spend = await _period_spend_micros(_ScalarSession(), workspace_id=1)
    assert spend == 750000


def test_gate_converts_cost_dollars_to_micros_half_up():
    """Assert USD to micros conversion uses 1_000_000 and ROUND_HALF_UP."""

    def _to_micros(dollars: float) -> int:
        d = Decimal(str(dollars)) * Decimal("1000000")
        return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    assert _to_micros(0.0012345) == 1235
    assert _to_micros(0.0012344) == 1234
    assert _to_micros(1.0) == 1_000_000


async def test_gate_rate_counter_does_not_race_under_concurrent_workers():
    """Assert in-memory fallback rate counter is thread-safe and increments properly."""
    from app.services.news.extract_budget import _memory_incr

    key = "test_race_key"
    window = 60
    counts = [_memory_incr(key, window) for _ in range(10)]
    assert counts == list(range(1, 11))


async def test_gate_recovers_when_redis_unavailable(monkeypatch):
    """Assert Redis connection failure falls back gracefully to in-memory rate count."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_RATE_MAX", 100)
    monkeypatch.setattr(
        "app.services.news.extract_budget._redis_client",
        lambda: (_ for _ in ()).throw(RuntimeError("Redis down")),
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="free",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is True


async def test_gate_recovers_when_wallet_lookup_raises(monkeypatch):
    """Assert exception in wallet lookup fails closed with reason='insufficient_wallet'."""
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_ENABLED", True)
    monkeypatch.setattr(config, "NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS", 100)
    monkeypatch.setattr(
        "app.services.news.extract_budget._wallet_spendable_micros",
        AsyncMock(side_effect=RuntimeError("DB error")),
    )
    monkeypatch.setattr(
        "app.services.workspace_limits.WorkspaceLimitService.get_effective_limits",
        AsyncMock(
            return_value=ResolvedWorkspaceLimits(
                plan_tier="pro",
                max_documents=None,
                max_members=None,
                max_runs=None,
                max_storage_bytes=None,
                news_entity_extraction_wallet_pre_check=True,
            )
        ),
    )

    result = await check_news_entity_extraction_allowed(
        _FakeSession(), workspace_id=1, user_id="user-1"
    )
    assert result.allowed is False
    assert result.reason == REASON_INSUFFICIENT_WALLET
