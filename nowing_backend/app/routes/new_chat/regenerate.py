"""Chat Regeneration Endpoint."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.agent_chat import _resolve_agent_config
from app.auth.context import AuthContext
from app.db import (
    AgentConfig,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    Permission,
    Workspace,
    get_async_session,
    shielded_async_session,
)
from app.routes.new_chat.shared import (
    _find_pre_turn_checkpoint_id,
    _logger,
    _raise_if_thread_busy_for_start,
    _resolve_filesystem_selection,
    _revert_turns_for_regenerate,
    check_thread_access,
)
from app.schemas.new_chat import (
    RegenerateRequest,
)
from app.tasks.chat.streaming.flows import (
    stream_new_chat,
)
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context
from app.utils.rbac import check_permission
from app.utils.user_message_multimodal import (
    split_langchain_human_content,
    split_persisted_user_content_parts,
)

router = APIRouter()

@router.post("/threads/{thread_id}/regenerate")
async def regenerate_response(
    thread_id: int,
    request: RegenerateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Regenerate the AI response for a chat thread.

    This endpoint supports two operations:
    1. **Edit**: Provide a new `user_query` to replace the last user message and regenerate
    2. **Reload**: Leave `user_query` empty (or None) to regenerate with the same query

    Both operations:
    - Rewind the LangGraph checkpointer to the state before the last AI response
    - Delete the last user message and AI response from the database
    - Stream a new response from that checkpoint

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_UPDATE permission.
    """
    from langchain_core.messages import HumanMessage

    from app.agents.chat.runtime.checkpointer import get_checkpointer

    try:
        # Authorize the workspace before any tenant-scoped query.
        await check_permission(
            session,
            auth,
            request.workspace_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this workspace",
        )

        # Set workspace + user GUC before the RLS-protected thread lookup.
        # client_id/agent_id are not trusted before the thread is verified.
        await set_request_tenant_context(
            session,
            request.workspace_id,
            None,
            None,
            user_id=str(user.id),
        )

        # Verify thread exists in the workspace.  The explicit workspace filter
        # prevents cross-workspace existence probing; the client/user RLS policy
        # restricts visibility to the owner or the claimed client scope.
        result = await session.execute(
            select(NewChatThread).filter(
                NewChatThread.id == thread_id,
                NewChatThread.workspace_id == request.workspace_id,
            )
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)
        _raise_if_thread_busy_for_start(thread_id)
        filesystem_selection = _resolve_filesystem_selection(
            mode=request.filesystem_mode,
            client_platform=request.client_platform,
            local_mounts=request.local_filesystem_mounts,
        )

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

        # Re-apply tenant GUCs with the verified thread scope.
        await set_request_tenant_context(
            session,
            thread.workspace_id,
            effective_client_id,
            effective_agent_id,
            user_id=str(user.id),
        )

        # Fail-fast resolution of the registry AgentConfig for regenerate.
        agent_config_override: AgentConfig | None = None
        if effective_agent_id:
            agent_config_override = await _resolve_agent_config(
                session,
                client_id=effective_client_id,  # type: ignore[arg-type]
                agent_id=effective_agent_id,
            )

        # Get the checkpointer and state history
        checkpointer = await get_checkpointer()

        config = {"configurable": {"thread_id": str(thread_id)}}

        # Collect checkpoint tuples from the async iterator
        # CheckpointTuple has: config, checkpoint (dict with channel_values), metadata, parent_config
        checkpoint_tuples = []
        async for cp_tuple in checkpointer.alist(config):
            checkpoint_tuples.append(cp_tuple)

        if not checkpoint_tuples:
            raise HTTPException(
                status_code=400, detail="No conversation history found for this thread"
            )

        # Find the checkpoint to rewind to
        # Checkpoints are in reverse chronological order (newest first)
        # We need to find a checkpoint before the last user message was added
        #
        # The checkpointer stores states after each node execution.
        # For a typical conversation flow:
        # - User sends message -> state 1 (with HumanMessage)
        # - Agent responds -> state 2 (with HumanMessage + AIMessage)
        #
        # To regenerate, we need the state BEFORE the last HumanMessage was processed

        target_checkpoint_id = None
        user_query_to_use = request.user_query
        regenerate_image_urls: list[str] = []

        # ---------------------------------------------------------------
        # Edit-from-arbitrary-position. When the client passes
        # ``from_message_id`` we look up its persisted ``turn_id`` (added
        # in migration 136) and pick the checkpoint immediately before
        # that turn started.
        #
        # Legacy graceful-degradation contract:
        #   * Rows persisted BEFORE migration 136 have ``turn_id IS NULL``.
        #     Returning 400 in that case is the wrong UX — the user is
        #     editing an old message in an existing thread and just wants
        #     it to work. We instead skip the checkpoint rewind (the
        #     stream falls back to the latest state) and skip the revert
        #     pass (no chat_turn_id available to walk). Deletion still
        #     uses ``created_at``, so the messages-after-cursor slice is
        #     correct on both legacy and post-136 rows.
        # ---------------------------------------------------------------
        from_message_turn_id: str | None = None
        from_message_created_at: datetime | None = None
        legacy_from_message: bool = False
        if request.from_message_id is not None:
            from_msg_row = await session.execute(
                select(NewChatMessage).filter(
                    NewChatMessage.id == request.from_message_id,
                    NewChatMessage.thread_id == thread_id,
                )
            )
            from_msg = from_msg_row.scalars().first()
            if from_msg is None:
                raise HTTPException(
                    status_code=404,
                    detail="from_message_id not found in this thread.",
                )
            from_message_created_at = from_msg.created_at
            if not from_msg.turn_id:
                # Legacy row — surface the degradation in logs but let
                # the request proceed with the slice-based delete and a
                # cold-start checkpoint.
                legacy_from_message = True
                _logger.warning(
                    "[regenerate] from_message_id=%s on thread=%s has no "
                    "turn_id (legacy row pre-migration-136). Falling back "
                    "to slice-based delete without checkpoint rewind. "
                    "revert_actions=%s will be ignored.",
                    request.from_message_id,
                    thread_id,
                    request.revert_actions,
                )
            else:
                from_message_turn_id = from_msg.turn_id

                # Walk oldest-to-newest and pick the LAST checkpoint whose
                # ``turn_id`` differs from the edited turn — that's the state
                # immediately before this turn started running. We read from
                # ``metadata`` (the durable surface) rather than
                # ``config["configurable"]`` so the lookup works across
                # checkpointer implementations.
                target_checkpoint_id = _find_pre_turn_checkpoint_id(
                    checkpoint_tuples,
                    turn_id=from_message_turn_id,
                )
                if target_checkpoint_id is None and len(checkpoint_tuples) > 0:
                    # Fall back to the oldest checkpoint — better than
                    # 400ing when the agent didn't checkpoint pre-turn
                    # (e.g. very first turn of the thread).
                    target_checkpoint_id = checkpoint_tuples[-1].config["configurable"][
                        "checkpoint_id"
                    ]

        # Look through checkpoints to find the right one
        # We want to find the checkpoint just before the last HumanMessage.
        # We enter this branch when:
        #   * the client did NOT pin ``from_message_id`` (legacy reload/edit), OR
        #   * the client pinned ``from_message_id`` but the row is a
        #     legacy pre-migration-136 row with no ``turn_id`` (we
        #     downgraded to the same heuristic as a regular reload).
        # We DO skip it when a real turn_id pinned ``target_checkpoint_id``
        # — that's the C1 happy path and the heuristic below would just
        # re-derive a worse target.
        if request.from_message_id is None or legacy_from_message:
            for i, cp_tuple in enumerate(checkpoint_tuples):
                # Access the checkpoint's channel_values which contains "messages"
                checkpoint_data = cp_tuple.checkpoint
                channel_values = checkpoint_data.get("channel_values", {})
                state_messages = channel_values.get("messages", [])

                if state_messages:
                    last_msg = state_messages[-1]
                    # Find a checkpoint where the last message is NOT a HumanMessage
                    # This means we're at a state before the user's last message
                    if not isinstance(last_msg, HumanMessage):
                        # If no new user_query provided (reload), extract from a later checkpoint
                        if user_query_to_use is None and i > 0:
                            # Get the user query from a more recent checkpoint
                            for prev_cp_tuple in checkpoint_tuples[:i]:
                                prev_checkpoint_data = prev_cp_tuple.checkpoint
                                prev_channel_values = prev_checkpoint_data.get(
                                    "channel_values", {}
                                )
                                prev_messages = prev_channel_values.get("messages", [])
                                for msg in reversed(prev_messages):
                                    if isinstance(msg, HumanMessage):
                                        q, imgs = split_langchain_human_content(
                                            msg.content
                                        )
                                        user_query_to_use = q
                                        regenerate_image_urls = imgs
                                        break
                                if user_query_to_use is not None and (
                                    str(user_query_to_use).strip()
                                    or regenerate_image_urls
                                ):
                                    break

                        target_checkpoint_id = cp_tuple.config["configurable"][
                            "checkpoint_id"
                        ]
                        break

        # If we couldn't find a good checkpoint, try alternative approaches
        if target_checkpoint_id is None and checkpoint_tuples:
            if len(checkpoint_tuples) == 1:
                # Only one checkpoint - get the user query from it if not provided
                if user_query_to_use is None:
                    checkpoint_data = checkpoint_tuples[0].checkpoint
                    channel_values = checkpoint_data.get("channel_values", {})
                    state_messages = channel_values.get("messages", [])
                    for msg in state_messages:
                        if isinstance(msg, HumanMessage):
                            q, imgs = split_langchain_human_content(msg.content)
                            user_query_to_use = q
                            regenerate_image_urls = imgs
                            break
            else:
                # Use the oldest checkpoint
                target_checkpoint_id = checkpoint_tuples[-1].config["configurable"][
                    "checkpoint_id"
                ]

        # If we still don't have a user query, get it from the database
        if user_query_to_use is None:
            # Get the last user message from the database
            last_user_msg_result = await session.execute(
                select(NewChatMessage)
                .filter(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.role == NewChatMessageRole.USER,
                )
                .order_by(NewChatMessage.created_at.desc())
                .limit(1)
            )
            last_user_msg = last_user_msg_result.scalars().first()
            if last_user_msg:
                content = last_user_msg.content
                if isinstance(content, str):
                    user_query_to_use = content
                elif isinstance(content, list):
                    plain, imgs = split_persisted_user_content_parts(content)
                    user_query_to_use = plain
                    regenerate_image_urls = imgs

        if isinstance(user_query_to_use, list):
            user_query_to_use, regenerate_image_urls = split_langchain_human_content(
                user_query_to_use
            )

        if request.user_images is not None:
            regenerate_image_urls = [p.as_data_url() for p in request.user_images]

        if user_query_to_use is None:
            raise HTTPException(
                status_code=400,
                detail="Could not determine user query for regeneration. Please provide a user_query.",
            )
        if not str(user_query_to_use).strip() and not regenerate_image_urls:
            raise HTTPException(
                status_code=400,
                detail="Could not determine user query for regeneration. Please provide a user_query.",
            )

        # Get the messages to delete AFTER streaming succeeds.
        # This prevents data loss if streaming fails.
        #
        # When ``from_message_id`` is set we slice from that message
        # forward (using ``created_at`` so we also catch any tool/system
        # messages persisted into the same turn). Otherwise
        # we keep the legacy "last 2 messages" rewind.
        if request.from_message_id is not None and from_message_created_at is not None:
            last_messages_result = await session.execute(
                select(NewChatMessage)
                .filter(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.created_at >= from_message_created_at,
                )
                .order_by(NewChatMessage.created_at.desc())
            )
        else:
            last_messages_result = await session.execute(
                select(NewChatMessage)
                .filter(NewChatMessage.thread_id == thread_id)
                .order_by(NewChatMessage.created_at.desc())
                .limit(2)
            )
        messages_to_delete = list(last_messages_result.scalars().all())

        message_ids_to_delete = [msg.id for msg in messages_to_delete]

        # When revert_actions is requested, collect the set of
        # ``chat_turn_id``s present in the slice we're about to delete.
        # Each one will be reverted (best-effort) BEFORE the regenerate
        # stream begins. Legacy rows have ``turn_id=None`` and silently
        # contribute nothing — we already logged the degradation above.
        revert_turn_ids: list[str] = []
        if (
            request.revert_actions
            and request.from_message_id is not None
            and not legacy_from_message
        ):
            seen_turns: set[str] = set()
            for msg in messages_to_delete:
                tid = msg.turn_id
                if tid and tid not in seen_turns:
                    seen_turns.add(tid)
                    revert_turn_ids.append(tid)

        # Get workspace for LLM config
        workspace_result = await session.execute(
            select(Workspace).filter(Workspace.id == request.workspace_id)
        )
        workspace = workspace_result.scalars().first()

        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")

        llm_config_id = (
            workspace.chat_model_id if workspace.chat_model_id is not None else 0
        )

        # Release the read-transaction so we don't hold ACCESS SHARE locks
        # on workspaces/documents for the entire duration of the stream.
        # expire_on_commit=False keeps loaded ORM attrs (including messages_to_delete PKs) usable.
        await session.commit()
        await session.close()

        # Create a wrapper generator that deletes messages only AFTER streaming succeeds
        # This prevents data loss if streaming fails (network error, LLM error, etc.)
        async def stream_with_cleanup():
            streaming_completed = False
            # Best-effort revert pass BEFORE the regenerate stream begins.
            # Each turn is reverted independently (per-row SAVEPOINTs
            # inside the route helper) and the per-action results are surfaced
            # on a single ``data-revert-results`` SSE event so the frontend
            # can render any failed rows alongside the new turn. Failures here
            # do NOT abort the regeneration — partial rollback is documented
            # behaviour.
            if revert_turn_ids:
                revert_results = await _revert_turns_for_regenerate(
                    thread_id=thread_id,
                    chat_turn_ids=revert_turn_ids,
                    requester_user_id=str(user.id),
                )
                envelope = {
                    "type": "data-revert-results",
                    "data": revert_results,
                }
                yield f"data: {json.dumps(envelope, default=str)}\n\n".encode()
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
            try:
                async for chunk in stream_new_chat(
                    user_query=str(user_query_to_use),
                    workspace_id=request.workspace_id,
                    chat_id=thread_id,
                    user_id=str(user.id),
                    llm_config_id=llm_config_id,
                    mentioned_document_ids=request.mentioned_document_ids,
                    mentioned_folder_ids=request.mentioned_folder_ids,
                    mentioned_connector_ids=request.mentioned_connector_ids,
                    mentioned_connectors=mentioned_connectors_payload,
                    mentioned_documents=mentioned_documents_payload,
                    mentioned_thread_ids=request.mentioned_thread_ids,
                    checkpoint_id=target_checkpoint_id,
                    needs_history_bootstrap=thread.needs_history_bootstrap,
                    thread_visibility=thread.visibility,
                    current_user_display_name=user.display_name or "A team member",
                    disabled_tools=request.disabled_tools,
                    mode=request.mode,
                    filesystem_selection=filesystem_selection,
                    request_id=getattr(http_request.state, "request_id", "unknown"),
                    user_image_data_urls=regenerate_image_urls or None,
                    auth_context=auth,
                    client_id=effective_client_id,
                    agent_id=effective_agent_id,
                    platform_metadata=request.platform_metadata,
                    agent_config_override=agent_config_override,
                    flow="regenerate",
                ):
                    yield chunk
                streaming_completed = True
            finally:
                # Only delete old messages if streaming completed successfully.
                # Uses a fresh session since stream_new_chat manages its own.
                if streaming_completed and message_ids_to_delete:
                    try:
                        async with shielded_async_session() as cleanup_session:
                            for msg_id in message_ids_to_delete:
                                _res = await cleanup_session.execute(
                                    select(NewChatMessage).filter(
                                        NewChatMessage.id == msg_id
                                    )
                                )
                                _msg = _res.scalars().first()
                                if _msg:
                                    await cleanup_session.delete(_msg)
                            await cleanup_session.commit()

                            from app.services.public_chat_service import (
                                delete_affected_snapshots,
                            )

                            await delete_affected_snapshots(
                                cleanup_session, thread_id, message_ids_to_delete
                            )
                    except Exception as cleanup_error:
                        _logger.warning(
                            "[regenerate] Failed to delete old messages: %s",
                            cleanup_error,
                        )

        # Return streaming response with checkpoint_id for rewinding
        return StreamingResponse(
            stream_with_cleanup(),
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
            detail=f"An unexpected error occurred during regeneration: {e!s}",
        ) from None

__all__ = ["router"]
