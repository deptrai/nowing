"""Integration tests for HybridLLMRouter (Story 26.3 / AD-103).

Requires Postgres + Redis.
All tests are ATDD red-phase scaffolds and are skipped until implementation.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

pytestmark = [
    pytest.mark.integration,
]


def _load_router() -> Any:
    return importlib.import_module("app.services.hybrid_llm_router")


def _make_llm_response(
    content: str, model: str = "gemini/gemini-2.0-flash"
) -> MagicMock:
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
    return MagicMock(model=model, usage=usage, choices=[choice])


@pytest.fixture
def fake_redis() -> AsyncMock:
    """Async Redis double with INCR/INCRBY/EXPIRE/GET."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="0")
    redis.incr = AsyncMock(return_value=1)
    redis.incrby = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def sample_workspace(db_workspace) -> Any:
    return db_workspace


class TestHybridLLMRouterFreeTier:
    """AC-1: Gemini free tier uses $0 cost and records TokenUsage."""

    async def test_public_fast_extraction_records_zero_cost(
        self,
        db_session,
        sample_workspace,
        fake_redis,
        billable_session_factory,
        monkeypatch,
    ) -> None:
        mod = _load_router()
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        acompletion = AsyncMock(
            return_value=_make_llm_response('{"company_name":"Acme"}')
        )
        monkeypatch.setattr(mod, "acompletion", acompletion)

        router = mod.HybridLLMRouter()
        await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=sample_workspace.id,
                user_id=sample_workspace.user_id,
                task_type="fast_extraction",
                sensitivity="public",
                messages=[{"role": "user", "content": "extract"}],
                response_model={
                    "type": "object",
                    "properties": {"company_name": {"type": "string"}},
                },
            ),
            billable_session_factory=billable_session_factory,
        )

        from app.db import TokenUsage

        usages = (
            (
                await db_session.execute(
                    select(TokenUsage).where(
                        TokenUsage.workspace_id == sample_workspace.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(usages) == 1
        assert usages[0].cost_micros == 0


class TestHybridLLMRouterPIIFallback:
    """PII/business inputs bypass Gemini free tier."""

    @pytest.mark.parametrize("sensitivity", ["pii", "business"])
    async def test_pii_data_does_not_call_gemini(
        self,
        db_session,
        sample_workspace,
        fake_redis,
        billable_session_factory,
        monkeypatch,
        sensitivity,
    ) -> None:
        mod = _load_router()
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        gemini = AsyncMock(return_value=_make_llm_response('{"company_name":"Acme"}'))
        vllm = AsyncMock(return_value=_make_llm_response('{"company_name":"Acme"}'))

        async def _route(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                return await gemini(*args, **kwargs)
            return await vllm(*args, **kwargs)

        monkeypatch.setattr(mod, "acompletion", AsyncMock(side_effect=_route))

        http_client = AsyncMock()
        http_client.get = AsyncMock(return_value=MagicMock(status_code=200, text="ok"))
        monkeypatch.setattr(mod, "AsyncClient", MagicMock(return_value=http_client))

        router = mod.HybridLLMRouter()
        await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=sample_workspace.id,
                user_id=sample_workspace.user_id,
                task_type="fast_extraction",
                sensitivity=sensitivity,
                messages=[
                    {"role": "user", "content": "Liên hệ Nguyễn Văn A 0912345678"}
                ],
                response_model={"type": "object"},
            ),
            billable_session_factory=billable_session_factory,
        )

        assert not gemini.called
        assert vllm.called


class TestHybridLLMRouterPremiumBilling:
    """AC-3: DeepSeek debit and TokenUsage cost attribution."""

    async def test_deepseek_reasoning_debits_workspace_owner(
        self,
        db_session,
        sample_workspace,
        fake_redis,
        billable_session_factory,
        monkeypatch,
    ) -> None:
        mod = _load_router()
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        acompletion = AsyncMock(
            return_value=_make_llm_response(
                '{"verdict":"buy"}', model="deepseek/deepseek-v4-pro"
            )
        )
        monkeypatch.setattr(mod, "acompletion", acompletion)

        router = mod.HybridLLMRouter()
        await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=sample_workspace.id,
                user_id=sample_workspace.user_id,
                task_type="reasoning",
                sensitivity="public",
                messages=[{"role": "user", "content": "reason"}],
                response_model={"type": "object"},
            ),
            billable_session_factory=billable_session_factory,
        )

        from app.db import TokenUsage

        usage = (
            (
                await db_session.execute(
                    select(TokenUsage).where(
                        TokenUsage.workspace_id == sample_workspace.id
                    )
                )
            )
            .scalars()
            .one()
        )
        assert usage.user_id == sample_workspace.user_id
        assert usage.cost_micros > 0

    async def test_deepseek_insufficient_credits_returns_402(
        self, db_session, sample_workspace, fake_redis, monkeypatch
    ) -> None:
        mod = _load_router()
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        from app.services.billable_calls import QuotaInsufficientError

        async def _raise_quota(*args, **kwargs):
            raise QuotaInsufficientError(
                usage_type="reasoning", balance_micros=0, remaining_micros=0
            )

        monkeypatch.setattr("app.services.billable_calls.billable_call", _raise_quota)

        router = mod.HybridLLMRouter()
        with pytest.raises(QuotaInsufficientError):
            await router.ainvoke(
                mod.HybridLLMRequest(
                    workspace_id=sample_workspace.id,
                    user_id=sample_workspace.user_id,
                    task_type="reasoning",
                    sensitivity="public",
                    messages=[{"role": "user", "content": "reason"}],
                    response_model={"type": "object"},
                )
            )


class TestHybridLLMRouterFallbackChain:
    """vLLM unavailability / slow queue and Gemini quota exhaustion fall back."""

    async def test_vllm_down_falls_back_to_gemini_then_deepseek(
        self, db_session, sample_workspace, fake_redis, monkeypatch
    ) -> None:
        mod = _load_router()
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        gemini = AsyncMock(return_value=_make_llm_response('{"company_name":"Gemini"}'))
        deepseek = AsyncMock(
            return_value=_make_llm_response('{"company_name":"DeepSeek"}')
        )

        def _route(*args, **kwargs):
            model = kwargs.get("model", "")
            if "gemini" in model:
                return gemini(*args, **kwargs)
            if "deepseek" in model:
                return deepseek(*args, **kwargs)
            raise RuntimeError("unrouted model")

        monkeypatch.setattr(mod, "acompletion", AsyncMock(side_effect=_route))

        http_client = AsyncMock()
        http_client.get = AsyncMock(
            return_value=MagicMock(status_code=503, text="unavailable")
        )
        monkeypatch.setattr(mod, "AsyncClient", MagicMock(return_value=http_client))

        router = mod.HybridLLMRouter()
        result = await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=sample_workspace.id,
                user_id=sample_workspace.user_id,
                task_type="fast_extraction",
                sensitivity="public",
                messages=[{"role": "user", "content": "extract"}],
                response_model={"type": "object"},
            )
        )

        assert result.content == {"company_name": "Gemini"} or result.content == {
            "company_name": "DeepSeek"
        }

    async def test_gemini_quota_exhaustion_falls_back_to_vllm(
        self, db_session, sample_workspace, fake_redis, monkeypatch
    ) -> None:
        mod = _load_router()
        fake_redis.get = AsyncMock(return_value="1500")  # rpd exhausted
        monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))

        acompletion = AsyncMock(
            return_value=_make_llm_response(
                '{"company_name":"Local"}', model="openai/Qwen/Qwen3.8-27B"
            )
        )
        monkeypatch.setattr(mod, "acompletion", acompletion)

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
        result = await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=sample_workspace.id,
                user_id=sample_workspace.user_id,
                task_type="fast_extraction",
                sensitivity="public",
                messages=[{"role": "user", "content": "extract"}],
                response_model={"type": "object"},
            )
        )

        assert result.content == {"company_name": "Local"}
