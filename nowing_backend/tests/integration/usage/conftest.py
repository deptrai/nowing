"""Fixtures for usage/credit dashboard integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app, limiter
from app.auth.context import AuthContext
from app.db import (
    CreditPurchase,
    CreditPurchaseStatus,
    IncentiveTaskType,
    PagePurchase,
    PagePurchaseStatus,
    TokenUsage,
    User,
    UserIncentiveTask,
    Workspace,
    get_async_session,
)
from app.users import get_auth_context

pytestmark = pytest.mark.integration

limiter.enabled = False


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    db_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as the workspace owner (db_user)."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def client_as_other(
    db_session: AsyncSession,
    db_other_user: User,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Authenticated as a non-member user."""

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_auth() -> AuthContext:
        return AuthContext.session(db_other_user)

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_auth_context] = override_auth

    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            follow_redirects=False,
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest_asyncio.fixture
async def db_other_user(db_session: AsyncSession) -> User:
    """A user who is not a member of db_workspace."""
    user = User(
        id=uuid4(),
        email="other@nowing.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def seed_token_usage(
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
):
    """Factory to create TokenUsage rows for the test workspace."""

    async def _make(
        *,
        usage_type: str = "chat",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
        total_tokens: int = 30,
        cost_micros: int = 1000,
        model_breakdown: dict | None = None,
        call_details: dict | None = None,
        created_at: datetime | None = None,
    ) -> TokenUsage:
        if model_breakdown is None:
            model_breakdown = {
                "openai/gpt-4": {
                    "model": "openai/gpt-4",
                    "model_ref": "openai/gpt-4",
                    "model_id": "gpt-4",
                    "display_name": "GPT-4",
                    "provider": "openai",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_micros": cost_micros,
                }
            }
        record = TokenUsage(
            usage_type=usage_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_micros=cost_micros,
            model_breakdown=model_breakdown,
            call_details=call_details,
            workspace_id=db_workspace.id,
            user_id=db_user.id,
            created_at=created_at or datetime.now(UTC),
        )
        db_session.add(record)
        await db_session.flush()
        return record

    return _make


@pytest_asyncio.fixture
async def seed_page_purchase(
    db_session: AsyncSession,
    db_user: User,
):
    """Factory to create PagePurchase rows for the test user."""

    async def _make(
        *,
        pages_granted: int = 100,
        amount_total: int = 1000,
        status: PagePurchaseStatus = PagePurchaseStatus.COMPLETED,
        created_at: datetime | None = None,
    ) -> PagePurchase:
        purchase = PagePurchase(
            user_id=db_user.id,
            stripe_checkout_session_id=f"cs_page_{uuid4().hex}",
            quantity=1,
            pages_granted=pages_granted,
            amount_total=amount_total,
            currency="usd",
            status=status,
            completed_at=created_at or datetime.now(UTC),
            created_at=created_at or datetime.now(UTC),
        )
        db_session.add(purchase)
        await db_session.flush()
        return purchase

    return _make


@pytest_asyncio.fixture
async def seed_credit_purchase(
    db_session: AsyncSession,
    db_user: User,
):
    """Factory to create CreditPurchase rows for the test user."""

    async def _make(
        *,
        quantity: int = 5,
        credit_micros_granted: int = 5_000_000,
        status: CreditPurchaseStatus = CreditPurchaseStatus.COMPLETED,
        created_at: datetime | None = None,
    ) -> CreditPurchase:
        purchase = CreditPurchase(
            user_id=db_user.id,
            stripe_checkout_session_id=f"cs_test_{uuid4().hex}",
            stripe_payment_intent_id=f"pi_test_{uuid4().hex}",
            quantity=quantity,
            credit_micros_granted=credit_micros_granted,
            amount_total=quantity * 100,
            currency="usd",
            source="checkout",
            status=status,
            completed_at=created_at or datetime.now(UTC),
            created_at=created_at or datetime.now(UTC),
        )
        db_session.add(purchase)
        await db_session.flush()
        return purchase

    return _make


@pytest_asyncio.fixture
async def seed_incentive_task(
    db_session: AsyncSession,
    db_user: User,
):
    """Factory to create UserIncentiveTask rows for the test user."""

    async def _make(
        *,
        task_type: IncentiveTaskType = IncentiveTaskType.GITHUB_STAR,
        credit_micros_awarded: int = 1_000_000,
        completed_at: datetime | None = None,
    ) -> UserIncentiveTask:
        task = UserIncentiveTask(
            user_id=db_user.id,
            task_type=task_type,
            credit_micros_awarded=credit_micros_awarded,
            completed_at=completed_at or datetime.now(UTC),
        )
        db_session.add(task)
        await db_session.flush()
        return task

    return _make
