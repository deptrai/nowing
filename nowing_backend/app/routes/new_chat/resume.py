"""Resume Interrupted Chat Endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.agent_chat import _resolve_agent_config
from app.auth.context import AuthContext
from app.db import (
    NewChatThread,
    Permission,
    Workspace,
    get_async_session,
)
from app.routes.new_chat.shared import (
    _raise_if_thread_busy_for_start,
    _resolve_filesystem_selection,
    check_thread_access,
)
from app.schemas.new_chat import (
    ResumeRequest,
)
from app.tasks.chat.streaming.flows import (
    stream_resume_chat,
)
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

@router.post("/threads/{thread_id}/resume")
async def resume_chat(
    thread_id: int,
    request: ResumeRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    try:
        # Load workspace and authorize before the RLS-protected thread lookup.
        workspace_result = await session.execute(
            select(Workspace).filter(Workspace.id == request.workspace_id)
        )
        workspace = workspace_result.scalars().first()

        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        await check_permission(
            session,
            auth,
            workspace.id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to chat in this workspace",
        )

        # Set workspace + user GUC before the RLS-protected thread lookup.
        # client_id is not trusted before the thread is verified.
        await set_request_tenant_context(
            session,
            workspace.id,
            None,
            None,
            user_id=str(user.id),
        )

        result = await session.execute(
            select(NewChatThread).filter(
                NewChatThread.id == thread_id,
                NewChatThread.workspace_id == request.workspace_id,
            )
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_thread_access(session, thread, user)
        _raise_if_thread_busy_for_start(thread_id)
        filesystem_selection = _resolve_filesystem_selection(
            mode=request.filesystem_mode,
            client_platform=request.client_platform,
            local_mounts=request.local_filesystem_mounts,
        )

        llm_config_id = (
            workspace.chat_model_id if workspace.chat_model_id is not None else 0
        )

        decisions = [d.model_dump() for d in request.decisions]

        # Fail-closed pivot checks (AD-31).  Legacy threads cannot be claimed;
        # client-scoped threads may accept a matching client_id or an agent_id
        # that belongs to that client.
        if thread.client_id is None and (
            request.client_id is not None or request.agent_id is not None
        ):
            raise HTTPException(
                status_code=403,
                detail="client_id and agent_id are not accepted on legacy threads",
            )
        if request.client_id is not None and request.client_id != thread.client_id:
            raise HTTPException(
                status_code=403,
                detail="client_id does not match the thread",
            )

        effective_client_id = (
            request.client_id if request.client_id is not None else thread.client_id
        )
        effective_agent_id = (
            request.agent_id
            if thread.client_id is not None and request.agent_id is not None
            else thread.agent_id
        )

        # Set tenant GUCs so RLS-protected agent registry queries see the right scope.
        await set_request_tenant_context(
            session,
            thread.workspace_id,
            effective_client_id,
            effective_agent_id,
            user_id=str(user.id),
        )

        # Fail-fast resolution of the registry AgentConfig for resume.
        agent_config_override = None
        if effective_agent_id:
            agent_config_override = await _resolve_agent_config(
                session,
                client_id=effective_client_id,  # type: ignore[arg-type]
                agent_id=effective_agent_id,
            )

        # Release the read-transaction so we don't hold ACCESS SHARE locks
        # on workspaces/documents for the entire duration of the stream.
        await session.commit()
        await session.close()

        return StreamingResponse(
            stream_resume_chat(
                chat_id=thread_id,
                workspace_id=request.workspace_id,
                decisions=decisions,
                user_id=str(user.id),
                llm_config_id=llm_config_id,
                thread_visibility=thread.visibility,
                filesystem_selection=filesystem_selection,
                request_id=getattr(http_request.state, "request_id", "unknown"),
                disabled_tools=request.disabled_tools,
                mode=request.mode,
                auth_context=auth,
                client_id=effective_client_id,
                agent_id=effective_agent_id,
                platform_metadata=request.platform_metadata,
                agent_config_override=agent_config_override,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during resume: {e!s}",
        ) from None

__all__ = ["router"]
