"""Shared helpers for new chat routes."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.chat.multi_agent_chat.main_agent.middleware.busy_mutex import (
    get_cancel_state,
    is_cancel_requested,
    manager,
)
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    ClientPlatform,
    FilesystemMode,
    FilesystemSelection,
    LocalFilesystemMount,
)
from app.config import config
from app.db import (
    ChatVisibility,
    NewChatThread,
    User,
    Workspace,
    shielded_async_session,
)
from app.schemas.new_chat import (
    LocalFilesystemMountPayload,
)
from app.utils.perf import get_perf_logger

_logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()
_background_tasks: set[asyncio.Task] = set()
TURN_CANCELLING_INITIAL_DELAY_MS = 200
TURN_CANCELLING_BACKOFF_FACTOR = 2
TURN_CANCELLING_MAX_DELAY_MS = 1500





def _resolve_filesystem_selection(
    *,
    mode: str,
    client_platform: str,
    local_mounts: list[LocalFilesystemMountPayload] | None,
) -> FilesystemSelection:
    """Validate and normalize filesystem mode settings from request payload."""
    try:
        resolved_mode = FilesystemMode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filesystem_mode") from exc
    try:
        resolved_platform = ClientPlatform(client_platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_platform") from exc

    if resolved_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
        if not config.ENABLE_DESKTOP_LOCAL_FILESYSTEM:
            raise HTTPException(
                status_code=400,
                detail="Desktop local filesystem mode is disabled on this deployment.",
            )
        if resolved_platform != ClientPlatform.DESKTOP:
            raise HTTPException(
                status_code=400,
                detail="desktop_local_folder mode is only available on desktop runtime.",
            )
        normalized_mounts: list[tuple[str, str]] = []
        seen_mounts: set[str] = set()
        for mount in local_mounts or []:
            mount_id = mount.mount_id.strip()
            root_path = mount.root_path.strip()
            if not mount_id or not root_path:
                continue
            if mount_id in seen_mounts:
                continue
            seen_mounts.add(mount_id)
            normalized_mounts.append((mount_id, root_path))
        if not normalized_mounts:
            raise HTTPException(
                status_code=400,
                detail=(
                    "local_filesystem_mounts must include at least one mount for "
                    "desktop_local_folder mode."
                ),
            )
        return FilesystemSelection(
            mode=resolved_mode,
            client_platform=resolved_platform,
            local_mounts=tuple(
                LocalFilesystemMount(mount_id=mount_id, root_path=root_path)
                for mount_id, root_path in normalized_mounts
            ),
        )

    return FilesystemSelection(
        mode=FilesystemMode.CLOUD,
        client_platform=resolved_platform,
    )


def _compute_turn_cancelling_retry_delay(attempt: int) -> int:
    """Bounded exponential delay for TURN_CANCELLING retry hints."""
    if attempt < 1:
        attempt = 1
    delay = TURN_CANCELLING_INITIAL_DELAY_MS * (
        TURN_CANCELLING_BACKOFF_FACTOR ** (attempt - 1)
    )
    return min(delay, TURN_CANCELLING_MAX_DELAY_MS)


def _build_turn_status_payload(thread_id: int) -> dict[str, object]:
    lock = manager.lock_for(str(thread_id))
    if not lock.locked():
        return {"status": "idle"}

    if is_cancel_requested(str(thread_id)):
        cancel_state = get_cancel_state(str(thread_id))
        attempt = cancel_state[0] if cancel_state else 1
        retry_after_ms = _compute_turn_cancelling_retry_delay(attempt)
        retry_after_at = int(datetime.now(UTC).timestamp() * 1000) + retry_after_ms
        return {
            "status": "cancelling",
            "retry_after_ms": retry_after_ms,
            "retry_after_at": retry_after_at,
        }

    return {"status": "busy"}


def _set_retry_after_headers(response: Response, retry_after_ms: int) -> None:
    response.headers["retry-after-ms"] = str(retry_after_ms)
    response.headers["Retry-After"] = str(max(1, (retry_after_ms + 999) // 1000))


def _raise_if_thread_busy_for_start(thread_id: int) -> None:
    status_payload = _build_turn_status_payload(thread_id)
    status = status_payload["status"]
    if status == "idle":
        return
    if status == "cancelling":
        retry_after_ms = int(status_payload.get("retry_after_ms") or 0)
        detail = {
            "errorCode": "TURN_CANCELLING",
            "message": "A previous response is still stopping. Please try again in a moment.",
            "retry_after_ms": retry_after_ms if retry_after_ms > 0 else None,
            "retry_after_at": status_payload.get("retry_after_at"),
        }
        headers = (
            {
                "retry-after-ms": str(retry_after_ms),
                "Retry-After": str(max(1, (retry_after_ms + 999) // 1000)),
            }
            if retry_after_ms > 0
            else None
        )
        raise HTTPException(status_code=409, detail=detail, headers=headers)

    raise HTTPException(
        status_code=409,
        detail={
            "errorCode": "THREAD_BUSY",
            "message": "Another response is still finishing for this thread. Please try again in a moment.",
        },
    )


def _find_pre_turn_checkpoint_id(
    checkpoint_tuples: list,
    *,
    turn_id: str,
) -> str | None:
    """Locate the LangGraph checkpoint immediately before ``turn_id`` started.

    ``checkpoint_tuples`` arrives newest-first from
    ``checkpointer.alist(config)``. We walk OLDEST-first (``reversed``)
    and remember the most recent checkpoint that does NOT belong to the
    edited turn. As soon as we cross into the edited turn (a checkpoint
    whose ``turn_id`` matches), we return the previously-tracked
    checkpoint — that's the state immediately before ``turn_id`` began.

    The naive "newest-first, return first non-matching" approach is
    INCORRECT when later turns exist after ``turn_id``: their
    checkpoints also satisfy ``cp_turn_id != turn_id`` and would be
    returned before the real pre-turn boundary is reached.

    Reads from ``cp_tuple.metadata`` (the durable surface promoted from
    ``configurable`` at write time) rather than ``config["configurable"]``
    so the lookup is portable across checkpointer implementations.

    Returns ``None`` when no eligible pre-turn checkpoint exists (e.g.
    the edited turn is the very first turn of the thread). Callers fall
    back to the oldest available checkpoint in that case.
    """

    last_pre_turn_target: str | None = None
    for cp_tuple in reversed(checkpoint_tuples):  # oldest -> newest
        metadata = getattr(cp_tuple, "metadata", None) or {}
        cp_turn_id = metadata.get("turn_id") if isinstance(metadata, dict) else None
        if cp_turn_id == turn_id:
            # Crossed into the edited turn; the previous tracked
            # checkpoint is the rewind target. May be ``None`` if we hit
            # the edited turn on the very first iteration.
            return last_pre_turn_target
        try:
            last_pre_turn_target = cp_tuple.config["configurable"]["checkpoint_id"]
        except (KeyError, TypeError):
            continue
    return last_pre_turn_target


async def _revert_turns_for_regenerate(
    *,
    thread_id: int,
    chat_turn_ids: list[str],
    requester_user_id: str,
) -> dict:
    """Best-effort revert pass for every ``chat_turn_id`` in ``chat_turn_ids``.

    Runs BEFORE the regenerate stream so the frontend can surface
    partial-rollback feedback alongside the new assistant turn. Each
    turn's actions are reverted in their own SAVEPOINTs (handled
    inside :mod:`app.routes.agent_revert_route`'s helpers) so a single
    failure never poisons the batch.

    Sequencing inside the request: revert THEN regenerate. The
    operation is NOT atomic and partial state IS surfaced — see the
    plan's "Sequencing inside the request" note.
    """

    from app.routes.agent_revert_route import (
        RevertTurnActionResult,
        _classify_outcome,
        _OutcomeRollbackError,
        _was_already_reverted,
        _was_already_reverted_batch,
    )
    from app.services.revert_service import (
        can_revert,
        revert_action,
    )

    aggregated_results: list[dict] = []
    # Exhaustive counters keep the response invariant
    # ``total == sum(counters)`` true for ``data-revert-results``.
    counts = {
        "reverted": 0,
        "already_reverted": 0,
        "not_reversible": 0,
        "permission_denied": 0,
        "failed": 0,
        "skipped": 0,
    }

    # Local import keeps the route module's existing imports tidy and
    # avoids a circular dependency at module-load time.
    from app.db import AgentActionLog as _AgentActionLog

    async with shielded_async_session() as session:
        for chat_turn_id in chat_turn_ids:
            rows_stmt = (
                select(_AgentActionLog)
                .where(
                    _AgentActionLog.thread_id == thread_id,
                    _AgentActionLog.chat_turn_id == chat_turn_id,
                )
                .order_by(
                    _AgentActionLog.created_at.desc(),
                    _AgentActionLog.id.desc(),
                )
            )
            rows = (await session.execute(rows_stmt)).scalars().all()

            # Batch idempotency probe across the turn (single SELECT
            # instead of one per row).
            eligible_ids = [r.id for r in rows if r.reverse_of is None]
            already_reverted_map = await _was_already_reverted_batch(
                session, action_ids=eligible_ids
            )

            for action in rows:
                if action.reverse_of is not None:
                    counts["skipped"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="skipped",
                            message="Row is itself a revert action; skipped.",
                        ).model_dump()
                    )
                    continue

                existing_revert_id = already_reverted_map.get(action.id)
                if existing_revert_id is not None:
                    counts["already_reverted"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="already_reverted",
                            new_action_id=existing_revert_id,
                        ).model_dump()
                    )
                    continue

                if not can_revert(
                    requester_user_id=requester_user_id,
                    action=action,
                    is_admin=False,
                ):
                    counts["permission_denied"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="permission_denied",
                            message="You are not allowed to revert this action.",
                        ).model_dump()
                    )
                    continue

                try:
                    async with session.begin_nested():
                        outcome = await revert_action(
                            session,
                            action=action,
                            requester_user_id=requester_user_id,
                        )
                        if outcome.status != "ok":
                            raise _OutcomeRollbackError(outcome)
                except _OutcomeRollbackError as rollback:
                    outcome = rollback.outcome
                    classified = _classify_outcome(outcome)
                    if classified == "permission_denied":
                        counts["permission_denied"] += 1
                    else:
                        counts["not_reversible"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status=classified,
                            message=outcome.message,
                        ).model_dump()
                    )
                    continue
                except IntegrityError:
                    # Concurrent revert won the race against the
                    # pre-flight ``_was_already_reverted`` SELECT.
                    # Surface the winning revert id so the client can
                    # treat this as a successful idempotent op.
                    existing_revert_id = await _was_already_reverted(
                        session, action_id=action.id
                    )
                    counts["already_reverted"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="already_reverted",
                            new_action_id=existing_revert_id,
                        ).model_dump()
                    )
                    continue
                except Exception as err:  # pragma: no cover — defensive
                    _logger.exception(
                        "Unexpected revert failure during regenerate batch "
                        "for action_id=%s",
                        action.id,
                    )
                    counts["failed"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="failed",
                            error=str(err) or err.__class__.__name__,
                        ).model_dump()
                    )
                    continue

                counts["reverted"] += 1
                aggregated_results.append(
                    RevertTurnActionResult(
                        action_id=action.id,
                        tool_name=action.tool_name,
                        status="reverted",
                        message=outcome.message,
                        new_action_id=outcome.new_action_id,
                    ).model_dump()
                )

        try:
            await session.commit()
        except Exception:
            _logger.exception(
                "[regenerate-revert] Final commit failed; rolling back batch."
            )
            await session.rollback()

    has_partial = (
        counts["failed"] > 0
        or counts["not_reversible"] > 0
        or counts["permission_denied"] > 0
    )

    return {
        "status": "partial" if has_partial else "ok",
        "chat_turn_ids": chat_turn_ids,
        "total": len(aggregated_results),
        "reverted": counts["reverted"],
        "already_reverted": counts["already_reverted"],
        "not_reversible": counts["not_reversible"],
        "permission_denied": counts["permission_denied"],
        "failed": counts["failed"],
        "skipped": counts["skipped"],
        "results": aggregated_results,
    }


def _try_delete_sandbox(thread_id: int) -> None:
    """Fire-and-forget sandbox + local file deletion so the HTTP response isn't blocked."""
    from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.sandbox import (
        delete_local_sandbox_files,
        delete_sandbox,
        is_sandbox_enabled,
    )

    if not is_sandbox_enabled():
        return

    async def _bg() -> None:
        try:
            await delete_sandbox(thread_id)
        except Exception:
            _logger.warning(
                "Background sandbox delete failed for thread %s",
                thread_id,
                exc_info=True,
            )
        try:
            delete_local_sandbox_files(thread_id)
        except Exception:
            _logger.warning(
                "Local sandbox file cleanup failed for thread %s",
                thread_id,
                exc_info=True,
            )

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_bg())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        pass


async def check_thread_access(
    session: AsyncSession,
    thread: NewChatThread,
    user: User,
    require_ownership: bool = False,
) -> bool:
    """
    Check if a user has access to a thread based on visibility rules.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE (any member can access) - for read/update operations only
    - Thread is a legacy thread (created_by_id is NULL) - only if user is workspace owner

    Args:
        session: Database session
        thread: The thread to check access for
        user: The user requesting access
        require_ownership: If True, ONLY the creator can perform this action (e.g., changing visibility).
                          This is checked FIRST, before visibility rules.

    Returns:
        True if access is granted

    Raises:
        HTTPException: If access is denied
    """
    is_owner = thread.created_by_id == user.id
    is_legacy = thread.created_by_id is None

    # If ownership is required (e.g., changing visibility), ONLY the creator can do it
    # This check comes first to ensure ownership-required operations are always creator-only
    if require_ownership:
        if not is_owner:
            raise HTTPException(
                status_code=403,
                detail="Only the creator of this chat can perform this action",
            )
        return True

    # Shared threads (SEARCH_SPACE) are accessible by any member for read/update operations
    if thread.visibility == ChatVisibility.SEARCH_SPACE:
        return True

    # For legacy threads (created before visibility feature),
    # only the workspace owner can access
    if is_legacy:
        workspace_query = select(Workspace).filter(Workspace.id == thread.workspace_id)
        workspace_result = await session.execute(workspace_query)
        workspace = workspace_result.scalar_one_or_none()
        is_workspace_owner = workspace and workspace.user_id == user.id

        if is_workspace_owner:
            return True
        # Legacy threads are not accessible to non-owners
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this chat",
        )

    # For read access: owner can access their own private threads
    if is_owner:
        return True

    # Private thread and user is not the owner
    raise HTTPException(
        status_code=403,
        detail="You don't have access to this private chat",
    )


# =============================================================================
