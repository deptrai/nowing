from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, get_async_session
from app.schemas.hybrid_llm import HybridLLMRequest, HybridLLMResponse
from app.services.hybrid_llm_service import HybridLLMService
from app.users import get_auth_context
from app.utils.rbac import check_permission

hybrid_public_router = APIRouter(tags=["hybrid-llm"])
hybrid_internal_router = APIRouter(tags=["hybrid-llm-internal"])


def _verify_dsh_worker_secret(request: Request) -> bool:
    header = request.headers.get("X-Dsh-Worker-Secret", "")
    expected = config.DSH_WORKER_SECRET
    return bool(expected) and bool(header) and hmac.compare_digest(header, expected)


async def require_dsh_worker(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    if not _verify_dsh_worker_secret(request):
        raise HTTPException(status_code=403, detail="Invalid DSH worker secret")
    if auth.pat is None:
        raise HTTPException(status_code=403, detail="DSH worker requires a PAT")
    return auth


def _require_pat_workspace_scope(auth: AuthContext, workspace_id: int) -> None:
    if auth.pat is None or auth.pat.workspace_id is None:
        raise HTTPException(
            status_code=403, detail="DSH worker PAT must be workspace-scoped"
        )
    if auth.pat.workspace_id != workspace_id:
        raise HTTPException(
            status_code=403, detail="PAT workspace does not match request workspace"
        )


@hybrid_public_router.post(
    "/workspaces/{workspace_id}/hybrid-llm/invoke",
    response_model=HybridLLMResponse,
    status_code=status.HTTP_200_OK,
)
async def invoke_hybrid_llm_public(
    request: Request,
    workspace_id: int,
    body: HybridLLMRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> HybridLLMResponse:
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CHATS_CREATE.value,
        )
    except Exception:
        raise HTTPException(status_code=403, detail="forbidden") from None

    body.workspace_id = workspace_id
    body.user_id = auth.user.id

    service = HybridLLMService(session, auth)
    return await service.invoke(body)


@hybrid_internal_router.post(
    "/hybrid-llm/invoke",
    response_model=HybridLLMResponse,
    status_code=status.HTTP_200_OK,
)
async def invoke_hybrid_llm_internal(
    request: Request,
    body: HybridLLMRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_dsh_worker),
) -> HybridLLMResponse:
    _require_pat_workspace_scope(auth, body.workspace_id)
    body.user_id = auth.user.id

    service = HybridLLMService(session, auth)
    return await service.invoke(body)
