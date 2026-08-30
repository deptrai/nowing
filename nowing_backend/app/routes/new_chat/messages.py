"""Message Endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
from app.db import (
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    Permission,
    TokenUsage,
    get_async_session,
)
from app.routes.new_chat.shared import (
    _perf_log,
    check_thread_access,
)
from app.schemas.new_chat import (
    NewChatMessageRead,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

@router.post("/threads/{thread_id}/messages", response_model=NewChatMessageRead)
async def append_message(
    thread_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    .. deprecated:: 2026-05
       Replaced by the **SSE-based message ID handshake**. The streaming
       generator (`stream_new_chat` / `stream_resume_chat`) now persists
       both the user and assistant rows server-side via
       ``persist_user_turn`` / ``persist_assistant_shell`` and emits
       ``data-user-message-id`` / ``data-assistant-message-id`` SSE events
       so the frontend can rename its optimistic IDs in real time. The
       new FE bundle no longer calls this route.

       This handler is retained as a **silent no-op for legacy / cached
       FE bundles**: the underlying ``INSERT ... ON CONFLICT DO NOTHING``
       pattern means a stale bundle hitting this route after the SSE
       handshake already wrote the row simply returns the existing row
       (200 OK) without raising or duplicating data. After a 2-week soak
       (target: ``[persist_user_turn] outcome=race_recovered`` rate ~0)
       this entire route — and the FE ``appendMessage`` function — is
       earmarked for removal.

    Append a message to a thread.
    This is used by ThreadHistoryAdapter.append() to persist messages.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_UPDATE permission.
    """
    try:
        # Capture ``user.id`` as a primitive UUID up front. The auth
        # dependency hands us a ``User`` ORM
        # row bound to ``session``; if the outer ``except
        # IntegrityError`` block below ever fires (an unexpected
        # constraint like a foreign key violation — the common
        # ``(thread_id, turn_id, role)`` race is now handled silently
        # by ``ON CONFLICT DO NOTHING`` so it never raises) it calls
        # ``session.rollback()``, which expires every attached ORM
        # row including this user. Any later ``user.id`` access would
        # then trigger a lazy PK reload — which on async SQLAlchemy
        # fails with ``MissingGreenlet`` because the reload happens
        # outside the awaitable greenlet boundary. Reading ``id``
        # once here pins the value as a plain UUID so all downstream
        # uses (TokenUsage insert, response build) are immune.
        user_uuid = user.id

        # Parse raw body - extract only role and content, ignoring extra fields
        raw_body = await request.json()
        role = raw_body.get("role")
        content = raw_body.get("content")

        if not role:
            raise HTTPException(status_code=400, detail="Missing required field: role")
        if content is None:
            raise HTTPException(
                status_code=400, detail="Missing required field: content"
            )

        # Validate role early (before any DB work)
        role_str = role.lower() if isinstance(role, str) else role
        try:
            message_role = NewChatMessageRole(role_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {role}. Must be 'user', 'assistant', or 'system'.",
            ) from None

        # Get thread
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

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Create message. ``turn_id`` is the per-turn correlation id from
        # ``configurable.turn_id`` (added in migration 136) — when the
        # client streams it back to ``appendMessage``, we persist it so
        # C1's edit-from-arbitrary-position can later map this message
        # back to the LangGraph checkpoint that produced its turn.
        raw_turn_id = raw_body.get("turn_id")
        turn_id_value = (
            str(raw_turn_id).strip()
            if isinstance(raw_turn_id, str) and raw_turn_id.strip()
            else None
        )

        # Update thread's updated_at timestamp (always — both insert
        # and recovery paths represent thread activity).
        thread.updated_at = datetime.now(UTC)

        # Insert the new message via ``INSERT ... ON CONFLICT DO NOTHING``
        # keyed on the ``(thread_id, turn_id, role)`` partial unique
        # index from migration 141 (``WHERE turn_id IS NOT NULL``).
        #
        # Why ON CONFLICT instead of ``session.add() + flush() + except
        # IntegrityError``:
        #   1. The conflict between this legacy FE ``appendMessage``
        #      round-trip and the server-side
        #      ``finalize_assistant_turn`` writer is a NORMAL,
        #      *expected* race — every assistant turn fires it. Using
        #      catch-and-recover means asyncpg raises
        #      ``UniqueViolationError`` -> SQLAlchemy wraps it as
        #      ``IntegrityError`` -> our handler catches and recovers.
        #      Functionally fine, but every ``raise`` event lights up
        #      VS Code's debugger (debugpy's ``justMyCode=false`` mode
        #      loses track of the catch frame across SQLAlchemy's
        #      async greenlet boundary, so even ``Raised Exceptions``
        #      being unchecked doesn't reliably suppress the pause).
        #      ON CONFLICT pushes the conflict resolution into Postgres
        #      where no Python exception is constructed at all.
        #   2. No ``session.rollback()`` -> no expiring of attached
        #      ORM rows -> no risk of ``MissingGreenlet`` from
        #      lazy-loading expired user/thread state later in the
        #      handler.
        #   3. Cleaner production logs (no SQLAlchemy ``IntegrityError``
        #      tracebacks emitted by uvicorn's logger between the
        #      ``raise`` and our ``except``).
        #
        # When ``turn_id_value`` is ``None`` the partial index doesn't
        # apply and the INSERT proceeds normally. Other constraint
        # violations (FK, NOT NULL, etc.) still raise ``IntegrityError``
        # and are caught by the outer ``except IntegrityError`` block
        # to preserve the legacy 400 behavior.
        #
        # Note on ``content``: when we recover the existing row, we
        # intentionally discard the FE's ``content`` payload from
        # ``raw_body`` and return the row's existing ``content``. The
        # streaming task is now the *authoritative writer* for
        # assistant ``ContentPart[]`` shape (mid-stream
        # ``AssistantContentBuilder`` -> ``finalize_assistant_turn``)
        # so the FE's later ``appendMessage`` is just a stale snapshot
        # of the same data — keeping the server-built rich content
        # (with full tool-call args / argsText / langchainToolCallId)
        # is correct, not lossy.
        insert_stmt = (
            pg_insert(NewChatMessage)
            .values(
                thread_id=thread_id,
                role=message_role,
                content=content,
                author_id=user_uuid,
                turn_id=turn_id_value,
            )
            .on_conflict_do_nothing(
                index_elements=["thread_id", "turn_id", "role"],
                index_where=sa_text("turn_id IS NOT NULL"),
            )
            .returning(NewChatMessage.id)
        )
        inserted_id = (await session.execute(insert_stmt)).scalar()

        if inserted_id is None:
            # Conflict on partial unique index — server-side stream
            # already wrote this row. Look it up and reuse it.
            if turn_id_value is None:
                # Defensive: ON CONFLICT only fires for ``turn_id IS
                # NOT NULL`` rows, so this branch should be
                # unreachable. Preserve the legacy 400 just in case
                # Postgres ever surprises us.
                raise HTTPException(
                    status_code=400,
                    detail="Database constraint violation. Please check your input data.",
                ) from None
            lookup = await session.execute(
                select(NewChatMessage).filter(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.turn_id == turn_id_value,
                    NewChatMessage.role == message_role,
                )
            )
            existing_message = lookup.scalars().first()
            if existing_message is None:
                # Conflict reported but the row vanished between
                # INSERT and SELECT — extremely unlikely (would
                # require a concurrent DELETE within the same
                # transaction visibility), but preserve safe
                # behavior.
                raise HTTPException(
                    status_code=400,
                    detail="Database constraint violation. Please check your input data.",
                ) from None
            db_message = existing_message
            # Perf signal: counts how often the legacy FE round-trip
            # races the server-side ``finalize_assistant_turn``. A
            # rising rate after the rework is OK (it's exactly the
            # ghost-thread fix's recovery path firing); a sudden drop
            # to zero would mean the FE isn't posting appendMessage
            # at all (different bug).
            _perf_log.info(
                "[append_message] outcome=recovered_via_unique_index "
                "thread_id=%s turn_id=%s role=%s message_id=%s",
                thread_id,
                turn_id_value,
                message_role.value,
                db_message.id,
            )
        else:
            # INSERT succeeded — load the full ORM row so the
            # response can include server-side-defaulted columns
            # (``created_at``, etc.) and the relationship surface
            # stays consistent with the recovery path.
            inserted_row = await session.get(NewChatMessage, inserted_id)
            if inserted_row is None:
                # Should be impossible: we just inserted it in this
                # same transaction. Fail loud if it happens.
                raise HTTPException(
                    status_code=500,
                    detail="Inserted message could not be loaded.",
                ) from None
            db_message = inserted_row

        # Persist token usage if provided (for assistant messages).
        # ``cost_micros`` is the provider USD cost reported by LiteLLM,
        # forwarded by the FE through the appendMessage round-trip so
        # the historical TokenUsage row matches the credit debit applied
        # at finalize time.
        #
        # De-dup: ``finalize_assistant_turn`` may also race to write a
        # token_usage row for this same ``message_id`` (cross-session,
        # cross-shielded). Use ``INSERT ... ON CONFLICT DO NOTHING`` keyed
        # on the ``uq_token_usage_message_id`` partial unique index
        # (migration 142). The loser silently drops its insert; exactly
        # one row results regardless of which writer commits first.
        token_usage_data = raw_body.get("token_usage")
        if token_usage_data and message_role == NewChatMessageRole.ASSISTANT:
            insert_stmt = (
                pg_insert(TokenUsage)
                .values(
                    usage_type="chat",
                    prompt_tokens=token_usage_data.get("prompt_tokens", 0),
                    completion_tokens=token_usage_data.get("completion_tokens", 0),
                    total_tokens=token_usage_data.get("total_tokens", 0),
                    cost_micros=token_usage_data.get("cost_micros", 0),
                    model_breakdown=token_usage_data.get("usage"),
                    call_details=token_usage_data.get("call_details"),
                    thread_id=thread_id,
                    message_id=db_message.id,
                    workspace_id=thread.workspace_id,
                    user_id=user_uuid,
                )
                .on_conflict_do_nothing(
                    index_elements=["message_id"],
                    index_where=sa_text("message_id IS NOT NULL"),
                )
            )
            await session.execute(insert_stmt)

        await session.commit()

        # Build response manually to avoid lazy-loading the token_usage
        # relationship after commit (which would trigger MissingGreenlet).
        return NewChatMessageRead(
            id=db_message.id,
            thread_id=db_message.thread_id,
            role=db_message.role,
            content=db_message.content,
            created_at=db_message.created_at,
            author_id=db_message.author_id,
            token_usage=None,
            turn_id=db_message.turn_id,
        )

    except HTTPException:
        raise
    except IntegrityError:
        # Any IntegrityError that escaped the inline handler above
        # comes from a *different* constraint (foreign key, etc.) —
        # preserve the legacy 400 path.
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
            detail=f"An unexpected error occurred while appending the message: {e!s}",
        ) from None

@router.get("/threads/{thread_id}/messages", response_model=list[NewChatMessageRead])
async def list_messages(
    thread_id: int,
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    List messages in a thread with pagination.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_READ permission.
    """
    try:
        # Verify thread exists and user has access
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
            "You don't have permission to read chats in this workspace",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Get messages
        query = (
            select(NewChatMessage)
            .options(selectinload(NewChatMessage.token_usage))
            .filter(NewChatMessage.thread_id == thread_id)
            .order_by(NewChatMessage.created_at)
            .offset(skip)
            .limit(limit)
        )

        result = await session.execute(query)
        return result.scalars().all()

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching messages: {e!s}",
        ) from None

__all__ = ["router"]
