"""Pattern 6 integration tests for HybridLLMRouter (Story 26.3).

Verifies SQL actually executes against Postgres:
- TokenUsage rows are persisted with the correct cost and workspace/user scoping.
- DeepSeek premium debits credit_wallet and releases the reservation.
- Insufficient credit blocks the call without persisting rows or debits.
- PII/business inputs bypass Gemini and route to vLLM/DeepSeek.
- Route endpoints persist TokenUsage through the real request/response path.

These tests are RED until ``HybridLLMRouter`` is implemented.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import TokenUsage, User, Workspace

pytestmark = [pytest.mark.integration]


def _load_router() -> Any:
    """Lazy import so the test module can be collected before the source exists."""
    return importlib.import_module("app.services.hybrid_llm_router")


def _make_litellm_response(
    content: str,
    *,
    model: str = "gemini/gemini-2.0-flash",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> MagicMock:
    usage = MagicMock(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    choice = MagicMock(
        message=MagicMock(
            content=content,
            reasoning_content=None,
        )
    )
    return MagicMock(model=model, usage=usage, choices=[choice])


@pytest.fixture
def mock_litellm_geminiflash() -> AsyncMock:
    return AsyncMock(
        return_value=_make_litellm_response(
            '{"company_name":"Acme"}',
            model="gemini/gemini-2.0-flash",
        )
    )


@pytest.fixture
def mock_litellm_deepseek() -> AsyncMock:
    return AsyncMock(
        return_value=_make_litellm_response(
            '{"verdict":"buy"}',
            model="deepseek/deepseek-v4-pro",
            prompt_tokens=100,
            completion_tokens=50,
        )
    )


@pytest.fixture
def mock_litellm_vllm() -> AsyncMock:
    response = _make_litellm_response(
        '{"company_name":"Local"}',
        model="openai/Qwen/Qwen3.8-27B",
    )
    return AsyncMock(return_value=response)


@pytest.fixture
def mock_vllm_healthy() -> AsyncMock:
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
    return http_client


def _hybrid_request(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    request = {
        "task_type": "fast_extraction",
        "sensitivity": "public",
        "messages": [{"role": "user", "content": "extract company name"}],
        "response_model": {
            "type": "object",
            "properties": {"company_name": {"type": "string"}},
            "required": ["company_name"],
        },
    }
    if overrides:
        request.update(overrides)
    return request


@pytest.mark.asyncio
async def test_public_fast_extraction_persists_zero_cost_token_usage(
    db_session,
    db_user,
    db_workspace,
    fake_redis,
    mock_litellm_geminiflash,
    billable_session_factory,
    monkeypatch,
) -> None:
    """Free-tier Gemini call writes a TokenUsage row with cost_micros=0."""
    mod = _load_router()
    monkeypatch.setattr(
        "app.services.billable_calls.shielded_async_session", billable_session_factory
    )
    monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(mod, "acompletion", mock_litellm_geminiflash)

    router = mod.HybridLLMRouter()
    response = await router.ainvoke(
        mod.HybridLLMRequest(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            **_hybrid_request(),
        )
    )

    assert response.content == {"company_name": "Acme"}
    assert response.tier == "gemini_free"

    usage = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalar_one()

    assert usage.user_id == db_user.id
    assert usage.cost_micros == 0
    assert usage.total_tokens == 15


@pytest.mark.asyncio
async def test_deepseek_reasoning_debits_credit_wallet_and_persists_cost(
    db_session,
    db_user,
    db_workspace,
    fake_redis,
    mock_litellm_deepseek,
    billable_session_factory,
    monkeypatch,
) -> None:
    """Premium DeepSeek call reserves, debits, and releases; TokenUsage has cost > 0."""
    # Seed a balance the router can reserve against.
    db_user.credit_micros_balance = 1_000_000
    db_user.credit_micros_reserved = 0

    mod = _load_router()
    monkeypatch.setattr(
        "app.services.billable_calls.shielded_async_session", billable_session_factory
    )
    monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(mod, "acompletion", mock_litellm_deepseek)
    # Test asserts a deterministic 5000 micro cost regardless of live litellm pricing.
    monkeypatch.setattr(
        mod.HybridLLMRouter,
        "_compute_cost_micros",
        lambda self, model, prompt_tokens, completion_tokens: 5000,
    )

    router = mod.HybridLLMRouter()
    response = await router.ainvoke(
        mod.HybridLLMRequest(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            task_type="reasoning",
            sensitivity="public",
            messages=[{"role": "user", "content": "reason"}],
            response_model={"type": "object"},
        )
    )

    assert response.tier != "gemini_free"

    # Re-read the user row to verify balance / reservation SQL.
    user = (
        await db_session.execute(select(User).where(User.id == db_user.id))
    ).scalar_one()
    assert user.credit_micros_balance == 1_000_000 - 5000
    assert user.credit_micros_reserved == 0

    usage = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert usage.cost_micros == 5000
    assert usage.total_tokens == 150


@pytest.mark.asyncio
async def test_insufficient_credit_blocks_and_leaves_no_row(
    db_session,
    db_user,
    db_workspace,
    fake_redis,
    mock_litellm_deepseek,
    billable_session_factory,
    monkeypatch,
) -> None:
    """A reasoning call with no balance is rejected before the LLM or TokenUsage."""
    db_user.credit_micros_balance = 0
    db_user.credit_micros_reserved = 0

    mod = _load_router()
    monkeypatch.setattr(
        "app.services.billable_calls.shielded_async_session", billable_session_factory
    )
    monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(mod, "acompletion", mock_litellm_deepseek)

    from app.services.billable_calls import QuotaInsufficientError

    router = mod.HybridLLMRouter()
    with pytest.raises(QuotaInsufficientError):
        await router.ainvoke(
            mod.HybridLLMRequest(
                workspace_id=db_workspace.id,
                user_id=db_user.id,
                task_type="reasoning",
                sensitivity="public",
                messages=[{"role": "user", "content": "reason"}],
                response_model={"type": "object"},
            )
        )

    usages = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).all()
    assert len(usages) == 0

    user = (
        await db_session.execute(select(User).where(User.id == db_user.id))
    ).scalar_one()
    assert user.credit_micros_balance == 0
    assert user.credit_micros_reserved == 0


@pytest.mark.asyncio
async def test_pii_input_routes_around_gemini_and_persists_local_usage(
    db_session,
    db_user,
    db_workspace,
    fake_redis,
    mock_litellm_vllm,
    mock_vllm_healthy,
    billable_session_factory,
    monkeypatch,
) -> None:
    """PII/business content must not be sent to Gemini even when quota is healthy."""
    mod = _load_router()
    monkeypatch.setattr(
        "app.services.billable_calls.shielded_async_session", billable_session_factory
    )
    monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(mod, "acompletion", mock_litellm_vllm)
    monkeypatch.setattr(mod, "AsyncClient", MagicMock(return_value=mock_vllm_healthy))

    router = mod.HybridLLMRouter()
    response = await router.ainvoke(
        mod.HybridLLMRequest(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            task_type="fast_extraction",
            sensitivity="business",
            messages=[{"role": "user", "content": "Liên hệ Nguyễn Văn A 0912345678"}],
            response_model={"type": "object"},
        )
    )

    assert response.tier != "gemini_free"
    assert response.content == {"company_name": "Local"}

    usage = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert usage.user_id == db_user.id


@pytest.mark.asyncio
async def test_workspace_isolation_for_token_usage(
    db_session,
    db_user,
    db_workspace,
    fake_redis,
    mock_litellm_geminiflash,
    billable_session_factory,
    monkeypatch,
) -> None:
    """A call for workspace A only creates a TokenUsage row for workspace A."""
    other_user = User(
        id=uuid4(),
        email="other@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    other_workspace = Workspace(name="Other Space", user_id=other_user.id)
    db_session.add(other_user)
    db_session.add(other_workspace)
    await db_session.flush()

    mod = _load_router()
    monkeypatch.setattr(
        "app.services.billable_calls.shielded_async_session", billable_session_factory
    )
    monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(mod, "acompletion", mock_litellm_geminiflash)

    router = mod.HybridLLMRouter()
    await router.ainvoke(
        mod.HybridLLMRequest(
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            **_hybrid_request(),
        )
    )

    rows = (
        (
            await db_session.execute(
                select(TokenUsage).where(
                    TokenUsage.workspace_id.in_([db_workspace.id, other_workspace.id])
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].workspace_id == db_workspace.id


@pytest.mark.asyncio
async def test_public_route_persists_token_usage_for_workspace_owner(
    client,
    db_workspace,
    db_session,
    fake_redis,
    mock_litellm_geminiflash,
    monkeypatch,
) -> None:
    """POST /api/v1/workspaces/{id}/hybrid-llm/invoke writes the usage row."""
    mod = _load_router()
    monkeypatch.setattr(mod, "get_redis_client", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(mod, "acompletion", mock_litellm_geminiflash)

    resp = await client.post(
        f"/api/v1/workspaces/{db_workspace.id}/hybrid-llm/invoke",
        json=_hybrid_request(),
    )
    assert resp.status_code == 200

    usage = (
        await db_session.execute(
            select(TokenUsage).where(TokenUsage.workspace_id == db_workspace.id)
        )
    ).scalar_one()
    assert usage.user_id == db_workspace.user_id
    assert usage.cost_micros == 0
