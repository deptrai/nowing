"""Thread Endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    ChatComment,
    ChatVisibility,
    NewChatMessage,
    NewChatThread,
    Permission,
    Workspace,
    get_async_session,
)
from app.routes.new_chat.shared import (
    _try_delete_sandbox,
    check_thread_access,
)
from app.schemas.new_chat import (
    NewChatMessageRead,
    NewChatThreadCreate,
    NewChatThreadRead,
    NewChatThreadUpdate,
    NewChatThreadVisibilityUpdate,
    NewChatThreadWithMessages,
    ThreadHistoryLoadResponse,
    ThreadListItem,
    ThreadListResponse,
    TokenUsageSummary,
)
from app.tasks.chat.streaming.flows.new_chat.chat_modes import (
    is_chat_mode_enabled,
    resolve_chat_mode,
)
from app.tenant_context import set_request_tenant_context
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    workspace_id: int,
    limit: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    List all accessible threads for the current user in a workspace.
    Returns threads and archived_threads for ThreadListPrimitive.

    A user can see threads that are:
    - Created by them (regardless of visibility)
    - Shared with the workspace (visibility = SEARCH_SPACE)
    - Legacy threads with no creator (created_by_id is NULL) - only if user is workspace owner

    Args:
        workspace_id: The workspace to list threads for
        limit: Optional limit on number of threads to return (applies to active threads only)

    Requires CHATS_READ permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this workspace",
        )

        # Check if user is the workspace owner (for legacy thread visibility)
        workspace_query = select(Workspace).filter(Workspace.id == workspace_id)
        workspace_result = await session.execute(workspace_query)
        workspace = workspace_result.scalar_one_or_none()
        is_workspace_owner = workspace and workspace.user_id == user.id

        # Build filter conditions:
        # 1. Created by the current user (any visibility)
        # 2. Shared with the workspace (visibility = SEARCH_SPACE)
        # 3. Legacy threads (created_by_id is NULL) - only visible to workspace owner
        filter_conditions = [
            NewChatThread.created_by_id == user.id,
            NewChatThread.visibility == ChatVisibility.SEARCH_SPACE,
        ]

        # Only include legacy threads for the workspace owner
        if is_workspace_owner:
            filter_conditions.append(NewChatThread.created_by_id.is_(None))

        query = (
            select(NewChatThread)
            .filter(
                NewChatThread.workspace_id == workspace_id,
                or_(*filter_conditions),
            )
            .order_by(NewChatThread.updated_at.desc())
        )

        result = await session.execute(query)
        all_threads = result.scalars().all()

        # Separate active and archived threads
        threads = []
        archived_threads = []

        for thread in all_threads:
            # Legacy threads (no creator) are treated as own threads for owner
            is_own_thread = thread.created_by_id == user.id or (
                thread.created_by_id is None and is_workspace_owner
            )
            item = ThreadListItem(
                id=thread.id,
                title=thread.title,
                archived=thread.archived,
                project_id=thread.project_id,
                visibility=thread.visibility,
                created_by_id=thread.created_by_id,
                is_own_thread=is_own_thread,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
            )
            if thread.archived:
                archived_threads.append(item)
            else:
                threads.append(item)

        # Apply limit to active threads if specified
        if limit is not None and limit > 0:
            threads = threads[:limit]

        return ThreadListResponse(threads=threads, archived_threads=archived_threads)

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching threads: {e!s}",
        ) from None

@router.get("/threads/search", response_model=list[ThreadListItem])
async def search_threads(
    workspace_id: int,
    title: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Search accessible threads by title in a workspace.

    A user can search threads that are:
    - Created by them (regardless of visibility)
    - Shared with the workspace (visibility = SEARCH_SPACE)
    - Legacy threads with no creator (created_by_id is NULL) - only if user is workspace owner

    Args:
        workspace_id: The workspace to search in
        title: The search query (case-insensitive partial match)

    Requires CHATS_READ permission.
    """
    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this workspace",
        )

        # Check if user is the workspace owner (for legacy thread visibility)
        workspace_query = select(Workspace).filter(Workspace.id == workspace_id)
        workspace_result = await session.execute(workspace_query)
        workspace = workspace_result.scalar_one_or_none()
        is_workspace_owner = workspace and workspace.user_id == user.id

        # Build filter conditions
        filter_conditions = [
            NewChatThread.created_by_id == user.id,
            NewChatThread.visibility == ChatVisibility.SEARCH_SPACE,
        ]

        # Only include legacy threads for the workspace owner
        if is_workspace_owner:
            filter_conditions.append(NewChatThread.created_by_id.is_(None))

        # Search accessible threads by title (case-insensitive)
        query = (
            select(NewChatThread)
            .filter(
                NewChatThread.workspace_id == workspace_id,
                NewChatThread.title.ilike(f"%{title}%"),
                or_(*filter_conditions),
            )
            .order_by(NewChatThread.updated_at.desc())
        )

        result = await session.execute(query)
        threads = result.scalars().all()

        return [
            ThreadListItem(
                id=thread.id,
                title=thread.title,
                archived=thread.archived,
                visibility=thread.visibility,
                created_by_id=thread.created_by_id,
                # Legacy threads (no creator) are treated as own threads for owner
                is_own_thread=(
                    thread.created_by_id == user.id
                    or (thread.created_by_id is None and is_workspace_owner)
                ),
                created_at=thread.created_at,
                updated_at=thread.updated_at,
            )
            for thread in threads
        ]

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while searching threads: {e!s}",
        ) from None

@router.post("/threads", response_model=NewChatThreadRead)
async def create_thread(
    thread: NewChatThreadCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Create a new chat thread.

    The thread is created with the specified visibility (defaults to PRIVATE).
    The current user is recorded as the creator of the thread.

    Requires CHATS_CREATE permission.
    """
    try:
        await check_permission(
            session,
            auth,
            thread.workspace_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to create chats in this workspace",
        )

        # Internal web threads are unscoped; reject any body attempt to claim a
        # vertical client or agent.  PAT-scoped public thread creation is the
        # only path that may bind client_id/agent_id.
        if thread.client_id is not None or thread.agent_id is not None:
            raise HTTPException(
                status_code=403,
                detail="client_id and agent_id are not accepted on internal threads",
            )

        # Chat modes (web_builder, presentation_studio, meeting_minutes) are
        # gated by a global feature flag and per-workspace setting (AD-120).
        chat_mode = resolve_chat_mode(thread.platform_metadata)
        if chat_mode.mode_id != "default":
            ws = (
                await session.execute(
                    select(Workspace).where(Workspace.id == thread.workspace_id)
                )
            ).scalars().first()
            if not is_chat_mode_enabled(
                chat_mode, workspace=ws, app_config=config
            ):
                raise HTTPException(
                    status_code=403,
                    detail=chat_mode.error_message,
                )

        # Set tenant GUCs before the insert so the 18.1 RLS WITH CHECK clause
        # on new_chat_threads allows client-scoped rows (here: unscoped/NULL).
        await set_request_tenant_context(
            session,
            thread.workspace_id,
            None,
            None,
        )

        now = datetime.now(UTC)
        db_thread = NewChatThread(
            title=thread.title,
            archived=thread.archived,
            visibility=thread.visibility,
            workspace_id=thread.workspace_id,
            project_id=thread.project_id,
            created_by_id=user.id,
            platform_metadata=thread.platform_metadata,
            updated_at=now,
        )
        session.add(db_thread)
        await session.commit()
        await session.refresh(db_thread)
        return db_thread

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while creating the thread: {e!s}",
        ) from None

@router.get("/threads/{thread_id}", response_model=ThreadHistoryLoadResponse)
async def get_thread_messages(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Get a thread with all its messages.
    This is used by ThreadHistoryAdapter.load() to restore conversation.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_READ permission.
    """
    try:
        # Get thread first
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Check permission to read chats in this workspace
        await check_permission(
            session,
            auth,
            thread.workspace_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this workspace",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Get messages with their authors and token usage loaded
        messages_result = await session.execute(
            select(NewChatMessage)
            .options(
                selectinload(NewChatMessage.author),
                selectinload(NewChatMessage.token_usage),
            )
            .filter(NewChatMessage.thread_id == thread_id)
            .order_by(NewChatMessage.created_at)
        )
        db_messages = messages_result.scalars().all()

        # Return messages in the format expected by assistant-ui
        messages = [
            NewChatMessageRead(
                id=msg.id,
                thread_id=msg.thread_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                author_id=msg.author_id,
                author_display_name=msg.author.display_name if msg.author else None,
                author_avatar_url=msg.author.avatar_url if msg.author else None,
                token_usage=TokenUsageSummary.model_validate(msg.token_usage)
                if msg.token_usage
                else None,
                turn_id=msg.turn_id,
            )
            for msg in db_messages
        ]

        return ThreadHistoryLoadResponse(messages=messages)

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching the thread: {e!s}",
        ) from None

@router.get("/threads/{thread_id}/full", response_model=NewChatThreadWithMessages)
async def get_thread_full(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Get full thread details with all messages.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_READ permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread)
            .options(
                selectinload(NewChatThread.messages).selectinload(
                    NewChatMessage.token_usage
                ),
            )
            .filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            auth,
            thread.workspace_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this workspace",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Check if thread has any comments
        comment_count = await session.scalar(
            select(func.count())
            .select_from(ChatComment)
            .join(NewChatMessage, ChatComment.message_id == NewChatMessage.id)
            .where(NewChatMessage.thread_id == thread.id)
        )

        return {
            **thread.__dict__,
            "messages": thread.messages,
            "has_comments": (comment_count or 0) > 0,
        }

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching the thread: {e!s}",
        ) from None

@router.put("/threads/{thread_id}", response_model=NewChatThreadRead)
async def update_thread(
    thread_id: int,
    thread_update: NewChatThreadUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Update a thread (title, archived status).
    Used for renaming and archiving threads.

    - PRIVATE threads: Only the creator can update
    - SEARCH_SPACE threads: Any member with CHATS_UPDATE permission can update

    Requires CHATS_UPDATE permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        db_thread = result.scalars().first()

        if not db_thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            auth,
            db_thread.workspace_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this workspace",
        )

        # For PRIVATE threads, only the creator can update
        # For SEARCH_SPACE threads, any member with permission can update
        if db_thread.visibility == ChatVisibility.PRIVATE:
            await check_thread_access(session, db_thread, user, require_ownership=True)

        # Update fields
        update_data = thread_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_thread, key, value)

        db_thread.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(db_thread)
        return db_thread

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating the thread: {e!s}",
        ) from None

@router.delete("/threads/{thread_id}", response_model=dict)
async def delete_thread(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Delete a thread and all its messages.

    - PRIVATE threads: Only the creator can delete
    - SEARCH_SPACE threads: Any member with CHATS_DELETE permission can delete

    Requires CHATS_DELETE permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        db_thread = result.scalars().first()

        if not db_thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            auth,
            db_thread.workspace_id,
            Permission.CHATS_DELETE.value,
            "You don't have permission to delete chats in this workspace",
        )

        # For PRIVATE threads, only the creator can delete
        # For SEARCH_SPACE threads, any member with permission can delete
        # Legacy threads (created_by_id is NULL) have no recorded creator,
        # so we skip strict ownership and fall through to legacy handling
        # which allows the workspace owner to delete them
        if db_thread.visibility == ChatVisibility.PRIVATE:
            await check_thread_access(
                session,
                db_thread,
                user,
                require_ownership=(db_thread.created_by_id is not None),
            )

        await session.delete(db_thread)
        await session.commit()

        _try_delete_sandbox(thread_id)

        return {"message": "Thread deleted successfully"}

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete thread due to existing dependencies."
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while deleting the thread: {e!s}",
        ) from None

@router.patch("/threads/{thread_id}/visibility", response_model=NewChatThreadRead)
async def update_thread_visibility(
    thread_id: int,
    visibility_update: NewChatThreadVisibilityUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Update the visibility/sharing settings of a thread.

    Only the creator of the thread can change its visibility.
    - PRIVATE: Only the creator can access the thread (default)
    - SEARCH_SPACE: All members of the workspace can access the thread

    Requires CHATS_UPDATE permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        db_thread = result.scalars().first()

        if not db_thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            auth,
            db_thread.workspace_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this workspace",
        )

        # Only the creator can change visibility
        await check_thread_access(session, db_thread, user, require_ownership=True)

        # Update visibility
        db_thread.visibility = visibility_update.visibility
        db_thread.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(db_thread)
        return db_thread

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating thread visibility: {e!s}",
        ) from None

__all__ = ["router"]
