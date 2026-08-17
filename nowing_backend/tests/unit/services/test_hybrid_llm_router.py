"""Unit tests for HybridLLMRouter (Story 26.3 / AD-103).

ATDD red phase: all tests are intentionally skipped until the implementation
is written. Removing the skip marker should cause failures until the feature is
green.
"""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skip(
        reason="ATDD red phase — Story 26.3 HybridLLMRouter not yet implemented"
    ),
]


def _load_router() -> Any:
    """Lazy loader so the test module can be collected before the source exists."""
    return importlib.import_module("app.services.hybrid_llm_router")


def _make_llm_response(
    content: str, model: str = "gemini/gemini-2.0-flash"
) -> MagicMock:
    """Build a minimal LiteLLM response double for unit tests."""
    usage = MagicMock(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    choice = MagicMock(
        message=MagicMock(
            content=content,
            reasoning_content=None,
        )
    )
    response = MagicMock(
        model=model,
        usage=usage,
        choices=[choice],
    )
    return response


class TestHybridLLMRouterTierSelection:
    """AC-1/AC-2/AC-3: tier selection based on task, sensitivity, quota, health."""

    @pytest.mark.parametrize(
        ("task_type", "sensitivity", "expected_tier"),
        [
            ("fast_extraction", "public", "gemini_free"),
            ("tool_dispatch", "public", "gemini_free"),
            ("fast_extraction", "business", "local_vllm_or_deepseek"),
            ("fast_extraction", "pii", "local_vllm_or_deepseek"),
            ("reasoning", "public", "deepseek_pro"),
            ("complex_extraction", "business", "deepseek_flash_or_pro"),
        ],
    )
    async def test_select_tier(
        self, task_type: str, sensitivity: str, expected_tier: str
    ) -> None:
        """Tier selector returns the right first attempt tier for each scenario."""
        mod = _load_router()
        router = mod.HybridLLMRouter()
        tier = await router._select_tier(
            task_type=task_type,
            sensitivity=sensitivity,
            gemini_quota_ok=True,
            vllm_healthy=True,
            peak=False,
            force_deep_reasoning=False,
        )
        assert tier == expected_tier

    async def test_pii_or_business_always_skips_gemini(self) -> None:
        """Even with full Gemini quota and healthy vLLM, PII/business bypasses free tier."""
        mod = _load_router()
        router = mod.HybridLLMRouter()

        for sensitivity in ("pii", "business"):
            tier = await router._select_tier(
                task_type="fast_extraction",
                sensitivity=sensitivity,
                gemini_quota_ok=True,
                vllm_healthy=True,
                peak=False,
                force_deep_reasoning=False,
            )
            assert tier != "gemini_free"

    async def test_peak_hours_prefers_deepseek_flash_for_reasoning(self) -> None:
        """During peak, reasoning defaults to Flash unless forced."""
        mod = _load_router()
        router = mod.HybridLLMRouter()

        tier = await router._select_tier(
            task_type="reasoning",
            sensitivity="public",
            gemini_quota_ok=True,
            vllm_healthy=True,
            peak=True,
            force_deep_reasoning=False,
        )
        assert tier in {"deepseek_flash", "deepseek_flash_or_pro"}

    async def test_force_deep_reasoning_keeps_pro_during_peak(self) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()

        tier = await router._select_tier(
            task_type="reasoning",
            sensitivity="public",
            gemini_quota_ok=True,
            vllm_healthy=True,
            peak=True,
            force_deep_reasoning=True,
        )
        assert tier == "deepseek_pro"


class TestHybridLLMRouterPIIDetection:
    """PII detection reuses app.services.pii.redact and caller sensitivity."""

    async def test_public_text_without_pii_is_not_sensitive(self) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()
        assert not router._is_sensitive("public tender notice", sensitivity="public")

    async def test_phone_number_marks_text_sensitive(self) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()
        assert router._is_sensitive("call 0912345678", sensitivity="public")

    async def test_email_marks_text_sensitive(self) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()
        assert router._is_sensitive("contact a@b.com", sensitivity="public")

    async def test_caller_sensitivity_pii_or_business_overrides_redact(self) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()
        # Even if redact finds nothing, caller-marked pii/business is sensitive.
        assert router._is_sensitive("plain public text", sensitivity="pii")
        assert router._is_sensitive("plain public text", sensitivity="business")


class TestGeminiQuota:
    """AC-1: Redis-based cross-process rate limit for Gemini free tier."""

    @pytest.fixture
    def fake_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="0")
        redis.incr = AsyncMock(return_value=1)
        redis.incrby = AsyncMock(return_value=1)
        redis.expire = AsyncMock(return_value=True)
        return redis

    async def test_check_gemini_quota_passes_when_under_limits(
        self, fake_redis: AsyncMock, monkeypatch
    ) -> None:
        mod = _load_router()
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        router = mod.HybridLLMRouter()
        ok = await router._check_gemini_quota()
        assert ok is True

    async def test_check_gemini_quota_fails_when_rpm_exceeded(
        self, fake_redis: AsyncMock, monkeypatch
    ) -> None:
        mod = _load_router()
        fake_redis.get = AsyncMock(return_value="15")  # at RPM limit
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        router = mod.HybridLLMRouter()
        ok = await router._check_gemini_quota()
        assert ok is False

    async def test_check_gemini_quota_fails_when_rpd_exceeded(
        self, fake_redis: AsyncMock, monkeypatch
    ) -> None:
        mod = _load_router()
        fake_redis.get = AsyncMock(side_effect=["0", "1500"])  # rpm, rpd
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        router = mod.HybridLLMRouter()
        ok = await router._check_gemini_quota()
        assert ok is False

    async def test_consume_gemini_quota_updates_per_minute_keys(
        self, fake_redis: AsyncMock, monkeypatch
    ) -> None:
        mod = _load_router()
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        router = mod.HybridLLMRouter()
        await router._consume_gemini_quota(prompt_tokens=10, completion_tokens=5)

        assert fake_redis.incr.called
        assert fake_redis.incrby.called
        # Keys must be per-minute, not per-hour.
        rpm_key = fake_redis.incr.call_args[0][0]
        assert "hybrid:gemini:rpm:" in rpm_key
        assert ":" in rpm_key.split("hybrid:gemini:rpm:")[-1]


class TestVllmHealth:
    """AC-2: vLLM health and queue latency gate."""

    async def test_vllm_healthy_when_health_and_models_fast(self, monkeypatch) -> None:
        mod = _load_router()
        http_client = AsyncMock()
        http_client.get = AsyncMock(
            side_effect=[
                MagicMock(status_code=200, text="ok"),
                MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"data": [{"id": "Qwen/Qwen3.8-27B"}]}),
                ),
            ]
        )
        monkeypatch.setattr(mod, "AsyncClient", MagicMock(return_value=http_client))

        router = mod.HybridLLMRouter()
        healthy = await router._vllm_health()
        assert healthy is True

    async def test_vllm_unhealthy_when_health_fails(self, monkeypatch) -> None:
        mod = _load_router()
        http_client = AsyncMock()
        http_client.get = AsyncMock(
            return_value=MagicMock(status_code=503, text="unavailable")
        )
        monkeypatch.setattr(mod, "AsyncClient", MagicMock(return_value=http_client))

        router = mod.HybridLLMRouter()
        healthy = await router._vllm_health()
        assert healthy is False

    async def test_vllm_unhealthy_when_queue_exceeds_8s(self, monkeypatch) -> None:
        mod = _load_router()
        http_client = AsyncMock()
        # /health returns 200 but very slow (simulated by a slow side_effect).
        http_client.get = AsyncMock(
            side_effect=lambda *args, **kwargs: (
                MagicMock(status_code=200, text="ok")
                if args[0].endswith("/health")
                else MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={"data": []}),
                )
            )
        )
        monkeypatch.setattr(mod, "AsyncClient", MagicMock(return_value=http_client))

        router = mod.HybridLLMRouter()
        healthy = await router._vllm_health()
        assert healthy is False


class TestModelInvocationAndJSON:
    """AC-1/AC-2/AC-3: provider calls, JSON schema, fallback, reasoning."""

    @pytest.fixture
    def sample_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"company_name": {"type": "string"}},
            "required": ["company_name"],
            "additionalProperties": False,
        }

    async def test_invoke_gemini_uses_json_object_response_format(
        self, monkeypatch
    ) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()

        acompletion = AsyncMock(
            return_value=_make_llm_response('{"company_name":"Acme"}')
        )
        monkeypatch.setattr(mod, "acompletion", acompletion)

        await router._invoke_gemini(
            messages=[{"role": "user", "content": "extract"}],
            response_schema={
                "type": "json_object",
                "response_schema": self.sample_schema(),
            },
        )

        call_kwargs = acompletion.call_args.kwargs
        assert call_kwargs["model"] == "gemini/gemini-2.0-flash"
        assert call_kwargs["response_format"]["type"] == "json_object"

    async def test_invoke_vllm_uses_json_schema_response_format(
        self, monkeypatch
    ) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()

        acompletion = AsyncMock(
            return_value=_make_llm_response('{"company_name":"Acme"}')
        )
        monkeypatch.setattr(mod, "acompletion", acompletion)

        await router._invoke_vllm(
            messages=[{"role": "user", "content": "extract"}],
            response_schema={
                "type": "json_schema",
                "json_schema": {
                    "name": "extract",
                    "schema": self.sample_schema(),
                    "strict": True,
                },
            },
        )

        call_kwargs = acompletion.call_args.kwargs
        assert "Qwen" in call_kwargs["model"] or "qwen" in call_kwargs["model"].lower()
        assert call_kwargs["response_format"]["type"] == "json_schema"

    async def test_invoke_deepseek_uses_reasoning_effort_and_captures_reasoning(
        self, monkeypatch
    ) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()

        response = _make_llm_response(
            '{"verdict":"buy"}', model="deepseek/deepseek-v4-pro"
        )
        response.choices[0].message.reasoning_content = "chain of thought"
        acompletion = AsyncMock(return_value=response)
        monkeypatch.setattr(mod, "acompletion", acompletion)

        result = await router._invoke_deepseek(
            messages=[{"role": "user", "content": "reason"}],
            response_schema={
                "type": "json_schema",
                "json_schema": {
                    "name": "reason",
                    "schema": {"type": "object"},
                    "strict": True,
                },
            },
            model="deepseek/deepseek-v4-pro",
        )

        call_kwargs = acompletion.call_args.kwargs
        assert "deepseek" in call_kwargs["model"]
        assert "reasoning_effort" in call_kwargs or "thinking" in call_kwargs
        assert result.reasoning_content == "chain of thought"

    async def test_invalid_json_falls_back_to_next_tier(self, monkeypatch) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()

        # First call returns invalid JSON, second (vLLM fallback) succeeds.
        gemini_call = AsyncMock(return_value=_make_llm_response("not json"))
        vllm_call = AsyncMock(
            return_value=_make_llm_response('{"company_name":"Acme"}')
        )

        def _acompletion_side_effect(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                return gemini_call(*args, **kwargs)
            return vllm_call(*args, **kwargs)

        monkeypatch.setattr(
            mod, "acompletion", AsyncMock(side_effect=_acompletion_side_effect)
        )

        result = await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=1,
                user_id=uuid4(),
                task_type="fast_extraction",
                sensitivity="public",
                messages=[{"role": "user", "content": "extract"}],
                response_model={
                    "type": "object",
                    "properties": {"company_name": {"type": "string"}},
                },
            )
        )

        assert result.content == {"company_name": "Acme"}
        assert result.tier != "gemini_free"  # fell back


class TestPeakHour:
    """Off-peak / peak pricing window."""

    @pytest.mark.parametrize(
        ("hour", "expected_peak"),
        [
            (22, True),
            (1, True),
            (6, False),
            (12, False),
            (18, False),
        ],
    )
    def test_is_peak_hour(self, hour: int, expected_peak: bool) -> None:
        mod = _load_router()
        when = datetime(2026, 8, 18, hour, 0, 0, tzinfo=UTC)
        assert mod.is_peak_hour(when) is expected_peak


class TestAInvokeFreeAndPremium:
    """Cost attribution and billing behavior."""

    async def test_free_tier_records_zero_cost(self, monkeypatch) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()

        acompletion = AsyncMock(
            return_value=_make_llm_response('{"company_name":"Acme"}')
        )
        monkeypatch.setattr(mod, "acompletion", acompletion)
        record = AsyncMock()
        monkeypatch.setattr(
            "app.services.token_tracking_service.record_token_usage", record
        )

        await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=1,
                user_id=uuid4(),
                task_type="fast_extraction",
                sensitivity="public",
                messages=[{"role": "user", "content": "extract"}],
                response_model={"type": "object"},
            )
        )

        call_kwargs = record.await_args.kwargs
        assert call_kwargs["cost_micros"] == 0

    async def test_deepseek_records_cost_and_debits_owner(self, monkeypatch) -> None:
        mod = _load_router()
        router = mod.HybridLLMRouter()

        acompletion = AsyncMock(
            return_value=_make_llm_response(
                '{"verdict":"buy"}', model="deepseek/deepseek-v4-pro"
            )
        )
        monkeypatch.setattr(mod, "acompletion", acompletion)

        billable_call = AsyncMock()
        monkeypatch.setattr("app.services.billable_calls.billable_call", billable_call)

        await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=1,
                user_id=uuid4(),
                task_type="reasoning",
                sensitivity="public",
                messages=[{"role": "user", "content": "reason"}],
                response_model={"type": "object"},
            )
        )

        assert billable_call.called
        assert billable_call.call_args.kwargs["billing_tier"] == "premium"
