"""Chat Streaming Endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.chat.multi_agent_chat.main_agent.middleware.busy_mutex import (
    request_cancel,
)
from app.auth.agent_chat import _resolve_agent_config
from app.auth.context import AuthContext
from app.db import (
    AgentConfig,
    NewChatThread,
    Permission,
    Workspace,
    get_async_session,
)
from app.routes.new_chat.shared import (
    _build_turn_status_payload,
    _raise_if_thread_busy_for_start,
    _resolve_filesystem_selection,
    _set_retry_after_headers,
    check_thread_access,
)
from app.schemas.new_chat import (
    CancelActiveTurnResponse,
    NewChatRequest,
    TurnStatusResponse,
)
from app.tasks.chat.streaming.flows import (
    stream_new_chat,
)
from app.tasks.chat.streaming.flows.new_chat.auto_pin import resolve_initial_auto_pin
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

@router.post("/new_chat")
async def handle_new_chat(
    request: NewChatRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Stream chat responses from the deep agent.

    This endpoint handles the new chat functionality with streaming responses
    using Server-Sent Events (SSE) format compatible with Vercel AI SDK.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_CREATE permission.
    """
    try:
        # Get workspace first; workspace is not RLS-protected, so it can be
        # loaded before any tenant GUC is set.
        workspace_result = await session.execute(
            select(Workspace).filter(Workspace.id == request.workspace_id)
        )
        workspace = workspace_result.scalars().first()

        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Authorize the workspace before we set request-derived tenant scope.
        await check_permission(
            session,
            auth,
            workspace.id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to chat in this workspace",
        )

        # Set workspace + user GUC for the thread lookup.  client_id is *not*
        # set before the thread is verified (AD-29/AD-31 ordering).  The user
        # GUC lets the owner see their own client-scoped rows even when the
        # body omits client_id.
        await set_request_tenant_context(
            session,
            workspace.id,
            None,
            None,
            user_id=str(user.id),
        )

        # Verify thread exists in the workspace.  The explicit workspace filter
        # prevents cross-workspace existence probing; the client/user RLS policy
        # restricts visibility to the owner or the claimed client scope.
        result = await session.execute(
            select(NewChatThread).filter(
                NewChatThread.id == request.chat_id,
                NewChatThread.workspace_id == request.workspace_id,
            )
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)
        _raise_if_thread_busy_for_start(request.chat_id)
        filesystem_selection = _resolve_filesystem_selection(
            mode=request.filesystem_mode,
            client_platform=request.client_platform,
            local_mounts=request.local_filesystem_mounts,
        )

        # Use the converged model-connections role for chat operations.
        # Positive IDs load Model + Connection rows; negative IDs load
        # virtual GLOBAL models; 0 means Auto.
        llm_config_id = (
            workspace.chat_model_id if workspace.chat_model_id is not None else 0
        )

        # Fail-closed pivot checks (AD-31).  An unscoped legacy thread cannot
        # be claimed by body client_id/agent_id.  A client-scoped thread may
        # accept a matching client_id or an agent_id that belongs to that
        # client, but only after the registry resolves it.
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
        # If the body supplies an agent_id for a client-scoped thread, use it
        # and let the registry fail-closed lookup below validate it.
        effective_agent_id = (
            request.agent_id
            if thread.client_id is not None and request.agent_id is not None
            else thread.agent_id
        )

        # Re-apply tenant GUCs with the resolved client/agent scope.
        await set_request_tenant_context(
            session,
            workspace.id,
            effective_client_id,
            effective_agent_id,
            user_id=str(user.id),
        )

        # Fail-fast resolution of the registry AgentConfig.  The actual merge
        # into the runtime config happens inside ``stream_new_chat`` so the
        # streaming session can re-merge after a mid-turn rate-limit recovery.
        agent_config_override: AgentConfig | None = None
        if effective_agent_id:
            agent_config_override = await _resolve_agent_config(
                session,
                client_id=effective_client_id,  # type: ignore[arg-type]
                agent_id=effective_agent_id,
            )

        # Resolve the concrete LLM config id before loading the bundle. Auto
        # (0 or null) may repin to a concrete model based on workspace settings.
        pin_result = await resolve_initial_auto_pin(
            session,
            chat_id=thread.id,
            workspace_id=workspace.id,
            user_id=str(user.id),
            selected_llm_config_id=llm_config_id,
            requires_image_input=bool(request.user_images),
            requested_llm_config_id=llm_config_id,
        )
        if pin_result.error is not None:
            message, _error_code, _error_kind = pin_result.error
            raise HTTPException(status_code=500, detail=message)
        resolved_llm_config_id = pin_result.llm_config_id

        llm, agent_config, llm_load_error = await load_llm_bundle(
            session,
            config_id=resolved_llm_config_id,
            workspace_id=workspace.id,
        )
        if llm_load_error:
            raise HTTPException(status_code=500, detail=llm_load_error)

        # Release the read-transaction so we don't hold ACCESS SHARE locks
        # on workspaces/documents for the entire duration of the stream.
        # expire_on_commit=False keeps loaded ORM attrs usable.
        await session.commit()
        # Close the dependency session now so its connection returns to
        # the pool before streaming begins.  Without this, Starlette's
        # BaseHTTPMiddleware cancels the scope on client disconnect and
        # the dependency generator's __aexit__ never runs, orphaning the
        # connection (the "Exception terminating connection" errors).
        await session.close()

        image_urls = (
            [p.as_data_url() for p in request.user_images]
            if request.user_images
            else None
        )

        mentioned_documents_payload = (
            [doc.model_dump() for doc in request.mentioned_documents]
            if request.mentioned_documents
            else None
        )
        mentioned_connectors_payload = (
            [doc.model_dump() for doc in request.mentioned_connectors]
            if request.mentioned_connectors
            else None
        )

        return StreamingResponse(
            stream_new_chat(
                user_query=request.user_query,
                workspace_id=request.workspace_id,
                chat_id=request.chat_id,
                user_id=str(user.id),
                llm_config_id=llm_config_id,
                mentioned_document_ids=request.mentioned_document_ids,
                mentioned_folder_ids=request.mentioned_folder_ids,
                mentioned_connector_ids=request.mentioned_connector_ids,
                mentioned_connectors=mentioned_connectors_payload,
                mentioned_documents=mentioned_documents_payload,
                mentioned_thread_ids=request.mentioned_thread_ids,
                mode=request.mode,
                needs_history_bootstrap=thread.needs_history_bootstrap,
                thread_visibility=thread.visibility,
                current_user_display_name=user.display_name or "A team member",
                disabled_tools=request.disabled_tools,
                filesystem_selection=filesystem_selection,
                request_id=getattr(http_request.state, "request_id", "unknown"),
                user_image_data_urls=image_urls,
                auth_context=auth,
                client_id=effective_client_id,
                agent_id=effective_agent_id,
                platform_metadata=request.platform_metadata,
                llm=llm,
                agent_config=agent_config,
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
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {e!s}",
        ) from None

@router.post(
    "/threads/{thread_id}/cancel-active-turn",
    response_model=CancelActiveTurnResponse,
)
async def cancel_active_turn(
    thread_id: int,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """Signal cancellation for the currently running turn on ``thread_id``."""
    result = await session.execute(
        select(NewChatThread).filter(NewChatThread.id == thread_id)
    )
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await check_permission(
        session,
        auth,
        thread.workspace_id,
        Permission.CHATS_UPDATE.value,
        "You don't have permission to update chats in this workspace",
    )
    await check_thread_access(session, thread, user)

    status_payload = _build_turn_status_payload(thread_id)
    if status_payload["status"] == "idle":
        return CancelActiveTurnResponse(
            status="idle",
            error_code="NO_ACTIVE_TURN",
        )

    request_cancel(str(thread_id))
    response.status_code = 202
    updated_payload = _build_turn_status_payload(thread_id)
    retry_after_ms = int(updated_payload.get("retry_after_ms") or 0)
    retry_after_at = (
        int(updated_payload["retry_after_at"])
        if "retry_after_at" in updated_payload
        else None
    )
    if retry_after_ms > 0:
        _set_retry_after_headers(response, retry_after_ms)
    return CancelActiveTurnResponse(
        status="cancelling",
        error_code="TURN_CANCELLING",
        retry_after_ms=retry_after_ms if retry_after_ms > 0 else None,
        retry_after_at=retry_after_at,
    )

@router.get(
    "/threads/{thread_id}/turn-status",
    response_model=TurnStatusResponse,
)
async def get_turn_status(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    result = await session.execute(
        select(NewChatThread).filter(NewChatThread.id == thread_id)
    )
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await check_permission(
        session,
        auth,
        thread.workspace_id,
        Permission.CHATS_READ.value,
        "You don't have permission to view chats in this workspace",
    )
    await check_thread_access(session, thread, user)

    status_payload = _build_turn_status_payload(thread_id)
    return TurnStatusResponse(
        status=status_payload["status"],  # type: ignore[arg-type]
        active_turn_id=None,
        retry_after_ms=status_payload.get("retry_after_ms"),  # type: ignore[arg-type]
        retry_after_at=status_payload.get("retry_after_at"),  # type: ignore[arg-type]
    )

__all__ = ["router"]
