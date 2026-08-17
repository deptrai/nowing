from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.schemas.hybrid_llm import HybridLLMRequest, HybridLLMResponse
from app.services.hybrid_llm_router import HybridLLMRouter


class _SessionFactory:
    """Wraps an existing AsyncSession so it can be used as a billable session factory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, *exc: Any) -> None:
        return None


class HybridLLMService:
    """Business service that wires a request into the HybridLLMRouter."""

    def __init__(self, db_session: AsyncSession, auth_context: AuthContext) -> None:
        self.db_session = db_session
        self.auth_context = auth_context

    async def invoke(self, request: HybridLLMRequest) -> HybridLLMResponse:
        if not request.user_id:
            request.user_id = self.auth_context.user.id

        def _factory() -> _SessionFactory:
            return _SessionFactory(self.db_session)

        return await HybridLLMRouter().ainvoke(
            request, billable_session_factory=_factory
        )
