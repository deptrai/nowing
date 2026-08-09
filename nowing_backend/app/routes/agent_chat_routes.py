"""Public agent-chat API routes (Story 18.1)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.auth.agent_chat import (
    AgentChatContext,
    require_agent_chat_pat as _require_agent_chat_pat,
)
from app.canonical.tenant_context import set_request_tenant_context
from app.config import config
from app.db import NewChatThread, ResearchThread, get_async_session
from app.schemas.agent_chat import (
    AgentChatMessageCreate,
    AgentChatThreadCreate,
    AgentChatThreadCreated,
)
from app.services.agent_chat.audit import log_public_call as audit
from app.tasks.chat.streaming.flows.new_chat.orchestrator import stream_new_chat

AGENT_CHAT_PUBLIC_ENABLED: bool = config.AGENT_CHAT_PUBLIC_ENABLED

router = APIRouter(prefix="/workspaces/{workspace_id}/agent-chat")


def _client_id(auth: AgentChatContext | Any) -> str:
    return getattr(auth, "effective_client_id", None) or getattr(
        getattr(auth, "pat", None), "client_id", None
    )


def _agent_id(auth: AgentChatContext | Any) -> str:
    return getattr(auth, "effective_agent_id", None) or getattr(
        getattr(auth, "pat", None), "agent_id", None
    )


def _pat_id(auth: AgentChatContext | Any) -> int | str:
    return getattr(auth, "pat_id", None) or getattr(
        getattr(auth, "pat", None), "id", ""
    )


def _actor_user_id(auth: AgentChatContext | Any) -> str:
    return str(getattr(getattr(auth, "user", None), "id", ""))


async def require_agent_chat_pat(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> AgentChatContext:
    """FastAPI dependency wrapper around the scoped PAT auth function."""
    if not AGENT_CHAT_PUBLIC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent_chat public surface disabled",
        )
    return await _require_agent_chat_pat(request, session, None)


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def create_thread(
    request: Request,
    workspace_id: int,
    body: AgentChatThreadCreate = Body(...),
    auth: AgentChatContext = Depends(require_agent_chat_pat),
    session: AsyncSession = Depends(get_async_session),
) -> Response:
    if not AGENT_CHAT_PUBLIC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent_chat public surface disabled",
        )

    client_id = _client_id(auth)
    agent_id = _agent_id(auth)

    # The body must not widen beyond the PAT scope.
    if body.client_id != client_id or body.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="client_id or agent_id outside PAT scope",
        )

    await set_request_tenant_context(session, workspace_id, client_id, agent_id)

    run_id = uuid.uuid4()

    research_thread = ResearchThread(
        workspace_id=workspace_id,
        client_id=client_id,
        title="New Chat",
        created_by_id=auth.user.id,
    )
    session.add(research_thread)

    chat_thread = NewChatThread(
        workspace_id=workspace_id,
        client_id=client_id,
        title="New Chat",
        created_by_id=auth.user.id,
        source="agent_chat_public",
    )
    session.add(chat_thread)

    await session.commit()
    await session.refresh(research_thread)
    await session.refresh(chat_thread)

    chat_thread.research_thread_id = research_thread.id
    await session.commit()

    await audit(
        actor_user_id=_actor_user_id(auth),
        pat_id=_pat_id(auth),
        workspace_id=workspace_id,
        client_id=client_id,
        agent_id=agent_id,
        route=f"POST {request.url.path}",
        status=201,
        run_id=run_id,
    )

    return Response(
        content=AgentChatThreadCreated(
            thread_id=chat_thread.id,
            research_thread_id=research_thread.id,
            run_id=str(run_id),
        ).model_dump_json(),
        media_type="application/json",
        status_code=status.HTTP_201_CREATED,
        headers={"X-Run-Id": str(run_id)},
    )


async def _stream_response(
    user_query: str,
    workspace_id: int,
    chat_id: int,
    auth: AgentChatContext,
    client_id: str,
    agent_id: str,
    run_id: uuid.UUID,
) -> StreamingResponse:
    """Wrap stream_new_chat and handle TimeoutError gracefully."""

    async def _generator():
        try:
            async for chunk in stream_new_chat(
                user_query=user_query,
                workspace_id=workspace_id,
                chat_id=chat_id,
                user_id=_actor_user_id(auth),
                auth_context=auth,
                client_id=client_id,
                agent_id=agent_id,
                request_id=str(run_id),
            ):
                yield chunk
        except TimeoutError:
            # ponytail: emit a single degraded SSE frame so clients get a
            # partial, parseable response instead of a connection drop.
            yield b'data: {"type":"error","degraded":true}\n\n'

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Run-Id": str(run_id),
        },
    )


@router.post("/threads/{thread_id}/messages")
async def send_message(
    request: Request,
    workspace_id: int,
    thread_id: int,
    body: AgentChatMessageCreate = Body(...),
    auth: AgentChatContext = Depends(require_agent_chat_pat),
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    if not AGENT_CHAT_PUBLIC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent_chat public surface disabled",
        )

    client_id = _client_id(auth)
    agent_id = _agent_id(auth)

    await set_request_tenant_context(session, workspace_id, client_id, agent_id)

    result = await session.execute(
        select(NewChatThread).where(NewChatThread.id == thread_id)
    )
    thread = result.scalars().first()
    if thread is None:
        status_code = status.HTTP_404_NOT_FOUND
        await audit(
            actor_user_id=_actor_user_id(auth),
            pat_id=_pat_id(auth),
            workspace_id=workspace_id,
            client_id=client_id,
            agent_id=agent_id,
            route=f"POST {request.url.path}",
            status=status_code,
        )
        raise HTTPException(status_code=status_code, detail="thread not found")

    if thread.workspace_id != workspace_id or thread.client_id != client_id:
        status_code = status.HTTP_403_FORBIDDEN
        await audit(
            actor_user_id=_actor_user_id(auth),
            pat_id=_pat_id(auth),
            workspace_id=workspace_id,
            client_id=client_id,
            agent_id=agent_id,
            route=f"POST {request.url.path}",
            status=status_code,
        )
        raise HTTPException(
            status_code=status_code,
            detail="thread does not belong to this workspace or client",
        )

    run_id = uuid.uuid4()

    response = await _stream_response(
        user_query=body.content,
        workspace_id=workspace_id,
        chat_id=thread_id,
        auth=auth,
        client_id=client_id,
        agent_id=agent_id,
        run_id=run_id,
    )

    # Audit is a background task so the stream is not blocked.
    async def _audit_after():
        await audit(
            actor_user_id=_actor_user_id(auth),
            pat_id=_pat_id(auth),
            workspace_id=workspace_id,
            client_id=client_id,
            agent_id=agent_id,
            route=f"POST {request.url.path}",
            status=200,
            run_id=run_id,
        )

    response.background = BackgroundTask(_audit_after)
    return response
