"""End-of-turn persistence for the cloud-mode Nowing filesystem.

Runs ``aafter_agent`` once per turn (cloud only), committing staged folder
creates, moves, writes/edits, and ``rm``/``rmdir`` to Postgres in one ordered
pass. Order matters: moves resolve before writes (so write-then-move lands at
the final path), and file deletes run before directory deletes (so a same-turn
``rm /a/x.md`` + ``rmdir /a`` works).

When ``flags.enable_action_log`` is on, each destructive op also snapshots a
``DocumentRevision`` / ``FolderRevision`` for revert. For ``rm``/``rmdir`` the
snapshot and DELETE share a SAVEPOINT, so a failed snapshot aborts the delete
rather than making the data silently irreversible.

The commit body is a free function (``commit_staged_filesystem_state``) so the
stream-task fallback can run the identical routine when ``aafter_agent`` was
skipped (e.g. client disconnect).

The persistence helpers (folder/document upserts, move resolution, action-log
binding, snapshot writers) live in ``._helpers`` and are re-exported here so
existing ``kb_persistence.middleware._<helper>`` import/patch paths keep
working.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.callbacks import dispatch_custom_event
from langgraph.config import get_config
from langgraph.runtime import Runtime
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.agents.chat.multi_agent_chat.main_agent.middleware.kb_persistence._helpers import (
    _apply_move,
    _basename,
    _create_document,
    _dispatch_reversibility_update,
    _doc_revision_payload,
    _ensure_folder_hierarchy,
    _find_action_ids_batch,
    _load_chunks_for_snapshot,
    _mark_action_reversible,
    _resolve_folder_id,
    _snapshot_document_pre_create,
    _snapshot_document_pre_move,
    _snapshot_document_pre_write,
    _snapshot_folder_pre_mkdir,
    _split_folder_path,
    _update_document,
)
from app.agents.chat.multi_agent_chat.shared.feature_flags import get_flags
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.multi_agent_chat.shared.receipts.receipt import (
    Receipt,
    make_receipt,
)
from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    NowingFilesystemState,
)
from app.agents.chat.multi_agent_chat.shared.state.reducers import _CLEAR
from app.agents.chat.runtime.path_resolver import (
    DOCUMENTS_ROOT,
    virtual_path_to_doc,
)
from app.db import (
    Document,
    DocumentRevision,
    DocumentType,
    Folder,
    FolderRevision,
    shielded_async_session,
)

logger = logging.getLogger(__name__)


_TEMP_PREFIX = "temp_"


# ---------------------------------------------------------------------------
# Commit body
# ---------------------------------------------------------------------------


async def commit_staged_filesystem_state(
    state: dict[str, Any] | AgentState,
    *,
    workspace_id: int,
    created_by_id: str | None,
    filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
    thread_id: int | None = None,
    dispatch_events: bool = True,
) -> dict[str, Any] | None:
    """Commit all staged filesystem changes; return the state delta for reducers.

    Shared between :class:`KnowledgeBasePersistenceMiddleware.aafter_agent` and
    the stream-task fallback. See the module docstring for ordering and the
    action-log snapshot/revert semantics.
    """
    if filesystem_mode != FilesystemMode.CLOUD:
        return None

    state_dict: dict[str, Any] = (
        dict(state)
        if isinstance(state, dict)
        else dict(getattr(state, "values", {}) or {})
    )

    files: dict[str, Any] = state_dict.get("files") or {}
    staged_dirs: list[str] = list(state_dict.get("staged_dirs") or [])
    staged_dir_tool_calls: dict[str, str] = dict(
        state_dict.get("staged_dir_tool_calls") or {}
    )
    pending_moves: list[dict[str, Any]] = list(state_dict.get("pending_moves") or [])
    pending_deletes: list[dict[str, Any]] = list(
        state_dict.get("pending_deletes") or []
    )
    pending_dir_deletes: list[dict[str, Any]] = list(
        state_dict.get("pending_dir_deletes") or []
    )
    dirty_paths: list[str] = list(state_dict.get("dirty_paths") or [])
    dirty_path_tool_calls: dict[str, str] = dict(
        state_dict.get("dirty_path_tool_calls") or {}
    )
    doc_id_by_path: dict[str, int] = dict(state_dict.get("doc_id_by_path") or {})
    kb_anon_doc = state_dict.get("kb_anon_doc")

    if kb_anon_doc:
        temp_paths = [
            p
            for p in files
            if isinstance(p, str) and _basename(p).startswith(_TEMP_PREFIX)
        ]
        return {
            "dirty_paths": [_CLEAR],
            "staged_dirs": [_CLEAR],
            "staged_dir_tool_calls": {_CLEAR: True},
            "pending_moves": [_CLEAR],
            "pending_deletes": [_CLEAR],
            "pending_dir_deletes": [_CLEAR],
            "dirty_path_tool_calls": {_CLEAR: True},
            "files": dict.fromkeys(temp_paths),
        }

    if not (
        staged_dirs
        or pending_moves
        or dirty_paths
        or pending_deletes
        or pending_dir_deletes
    ):
        return None

    flags = get_flags()
    snapshot_enabled = flags.enable_action_log

    # De-dup deletes per-path, keeping the latest tool_call_id (likeliest revert).
    file_delete_paths: dict[str, str] = {}
    for entry in pending_deletes:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if path:
            file_delete_paths[path] = str(entry.get("tool_call_id") or "")
    dir_delete_paths: dict[str, str] = {}
    for entry in pending_dir_deletes:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if path:
            dir_delete_paths[path] = str(entry.get("tool_call_id") or "")

    committed_creates: list[dict[str, Any]] = []
    committed_updates: list[dict[str, Any]] = []
    committed_deletes: list[dict[str, Any]] = []
    committed_folder_deletes: list[dict[str, Any]] = []
    discarded: list[str] = []
    applied_moves: list[dict[str, Any]] = []
    doc_id_path_tombstones: dict[str, int | None] = {}
    tree_changed = False
    # Reversibility-flip dispatches are drained only after the outer commit
    # succeeds (and abandoned on rollback), so the UI never sees reversible=true
    # for a snapshot that didn't durably land.
    deferred_dispatches: list[int] = []

    try:
        async with shielded_async_session() as session:
            # Resolve all action-id bindings in one SELECT per turn, not per op.
            action_id_by_call: dict[str, int] = {}
            if snapshot_enabled and thread_id is not None:
                tool_call_ids: set[str] = set()
                tool_call_ids.update(
                    tcid for tcid in staged_dir_tool_calls.values() if tcid
                )
                for move in pending_moves:
                    tcid = str(move.get("tool_call_id") or "")
                    if tcid:
                        tool_call_ids.add(tcid)
                tool_call_ids.update(
                    tcid for tcid in dirty_path_tool_calls.values() if tcid
                )
                tool_call_ids.update(
                    tcid for tcid in file_delete_paths.values() if tcid
                )
                tool_call_ids.update(tcid for tcid in dir_delete_paths.values() if tcid)
                action_id_by_call = await _find_action_ids_batch(
                    session,
                    thread_id=thread_id,
                    tool_call_ids=tool_call_ids,
                )

            def _action_id_for(tool_call_id: str | None) -> int | None:
                if not snapshot_enabled or not tool_call_id:
                    return None
                return action_id_by_call.get(str(tool_call_id))

            turn_id_for_revision = (
                next(iter(action_id_by_call), None) if action_id_by_call else None
            )

            # 1. staged_dirs -> Folder rows (snapshot post-flush for the FK).
            for folder_path in staged_dirs:
                if not isinstance(folder_path, str):
                    continue
                if not folder_path.startswith(DOCUMENTS_ROOT):
                    continue
                folder_parts_full = _split_folder_path(folder_path)
                if not folder_parts_full:
                    continue
                folder_id = await _ensure_folder_hierarchy(
                    session,
                    workspace_id=workspace_id,
                    created_by_id=created_by_id,
                    folder_parts=folder_parts_full,
                )
                tree_changed = True

                if snapshot_enabled and folder_id is not None:
                    tcid = staged_dir_tool_calls.get(folder_path)
                    action_id = _action_id_for(tcid)
                    if action_id is not None:
                        result = await session.execute(
                            select(Folder).where(Folder.id == folder_id)
                        )
                        folder_row = result.scalar_one_or_none()
                        if folder_row is not None:
                            await _snapshot_folder_pre_mkdir(
                                session,
                                folder=folder_row,
                                action_id=action_id,
                                workspace_id=workspace_id,
                                turn_id=tcid,
                                deferred_dispatches=deferred_dispatches,
                            )

            # 2. pending_moves (snapshot pre-move for in-place restore on revert).
            for move in pending_moves:
                source = str(move.get("source") or "")
                if snapshot_enabled and source:
                    tcid = str(move.get("tool_call_id") or "")
                    action_id = _action_id_for(tcid)
                    if action_id is not None:
                        doc_id_pre = doc_id_by_path.get(source)
                        document_pre: Document | None = None
                        if doc_id_pre is not None:
                            res_pre = await session.execute(
                                select(Document).where(
                                    Document.id == doc_id_pre,
                                    Document.workspace_id == workspace_id,
                                )
                            )
                            document_pre = res_pre.scalar_one_or_none()
                        if document_pre is None:
                            document_pre = await virtual_path_to_doc(
                                session,
                                workspace_id=workspace_id,
                                virtual_path=source,
                            )
                        if document_pre is not None:
                            await _snapshot_document_pre_move(
                                session,
                                doc=document_pre,
                                action_id=action_id,
                                workspace_id=workspace_id,
                                turn_id=tcid,
                                deferred_dispatches=deferred_dispatches,
                            )

                applied = await _apply_move(
                    session,
                    workspace_id=workspace_id,
                    created_by_id=created_by_id,
                    move=move,
                    doc_id_by_path=doc_id_by_path,
                    doc_id_path_tombstones=doc_id_path_tombstones,
                )
                if applied:
                    applied_moves.append(applied)
                    tree_changed = True

            move_alias = {
                m["source"]: m["dest"] for m in pending_moves if m.get("source")
            }

            def _final_path(path: str) -> str:
                seen: set[str] = set()
                while path in move_alias and path not in seen:
                    seen.add(path)
                    path = move_alias[path]
                return path

            # 3. dirty_paths -> writes/edits. Paths queued for rm this turn are
            # skipped so a write+rm sequence doesn't recreate the doc.
            kb_dirty_seen: set[str] = set()
            kb_dirty: list[str] = []
            kb_dirty_origin: dict[str, str] = {}
            for raw in dirty_paths:
                if not isinstance(raw, str):
                    continue
                final = _final_path(raw)
                if not final.startswith(DOCUMENTS_ROOT + "/"):
                    continue
                if final in kb_dirty_seen:
                    continue
                if final in file_delete_paths:
                    discarded.append(final)
                    continue
                kb_dirty_seen.add(final)
                kb_dirty.append(final)
                kb_dirty_origin[final] = raw

            for path in kb_dirty:
                basename = _basename(path)
                if basename.startswith(_TEMP_PREFIX):
                    discarded.append(path)
                    continue
                file_data = files.get(path)
                if not isinstance(file_data, dict):
                    continue
                content = "\n".join(file_data.get("content") or [])
                doc_id = doc_id_by_path.get(path)
                # Look up tool_call_id by final path or its pre-rename origin.
                origin = kb_dirty_origin.get(path, path)
                tcid = dirty_path_tool_calls.get(path) or dirty_path_tool_calls.get(
                    origin
                )
                action_id = _action_id_for(tcid)

                if doc_id is None:
                    # doc_id_by_path is per-thread and empty in a new chat, so a
                    # write to a path already in the DB must update in place, not
                    # INSERT (which would hit the path-derived unique hash).
                    existing = await virtual_path_to_doc(
                        session,
                        workspace_id=workspace_id,
                        virtual_path=path,
                    )
                    if existing is not None:
                        doc_id = existing.id
                        doc_id_by_path[path] = existing.id
                if doc_id is not None:
                    if snapshot_enabled and action_id is not None:
                        result_doc = await session.execute(
                            select(Document).where(
                                Document.id == doc_id,
                                Document.workspace_id == workspace_id,
                            )
                        )
                        existing_doc = result_doc.scalar_one_or_none()
                        if existing_doc is not None:
                            await _snapshot_document_pre_write(
                                session,
                                doc=existing_doc,
                                action_id=action_id,
                                workspace_id=workspace_id,
                                turn_id=tcid,
                                deferred_dispatches=deferred_dispatches,
                            )
                    updated = await _update_document(
                        session,
                        doc_id=doc_id,
                        content=content,
                        virtual_path=path,
                        workspace_id=workspace_id,
                    )
                    if updated is not None:
                        committed_updates.append(
                            {
                                "id": updated.id,
                                "title": updated.title,
                                "documentType": DocumentType.NOTE.value,
                                "workspaceId": workspace_id,
                                "folderId": updated.folder_id,
                                "createdById": str(created_by_id)
                                if created_by_id
                                else None,
                                "virtualPath": path,
                            }
                        )
                else:
                    # Fresh create, wrapped in a SAVEPOINT so a residual
                    # IntegrityError (e.g. pre-migration-133 content_hash UNIQUE)
                    # rolls back only this create, not the whole turn.
                    placeholder_revision_id: int | None = None
                    if snapshot_enabled and action_id is not None:
                        placeholder_revision_id = await _snapshot_document_pre_create(
                            session,
                            action_id=action_id,
                            workspace_id=workspace_id,
                            turn_id=tcid,
                            deferred_dispatches=deferred_dispatches,
                        )
                    try:
                        async with session.begin_nested():
                            new_doc = await _create_document(
                                session,
                                virtual_path=path,
                                content=content,
                                workspace_id=workspace_id,
                                created_by_id=created_by_id,
                            )
                    except ValueError as exc:
                        logger.warning(
                            "kb_persistence: skipping %s create: %s", path, exc
                        )
                        # Create never happened; drop its placeholder revision.
                        if placeholder_revision_id is not None:
                            await session.execute(
                                delete(DocumentRevision).where(
                                    DocumentRevision.id == placeholder_revision_id
                                )
                            )
                        continue
                    except IntegrityError as exc:
                        msg = str(exc.orig) if exc.orig is not None else str(exc)
                        logger.error(
                            "kb_persistence: IntegrityError creating %s: %s. "
                            "If this mentions content_hash, run alembic "
                            "upgrade to apply migration 133 which drops the "
                            "global UNIQUE constraint on documents.content_hash.",
                            path,
                            msg,
                        )
                        if placeholder_revision_id is not None:
                            await session.execute(
                                delete(DocumentRevision).where(
                                    DocumentRevision.id == placeholder_revision_id
                                )
                            )
                        continue
                    doc_id_by_path[path] = new_doc.id
                    if placeholder_revision_id is not None:
                        await session.execute(
                            update(DocumentRevision)
                            .where(DocumentRevision.id == placeholder_revision_id)
                            .values(document_id=new_doc.id)
                        )
                    committed_creates.append(
                        {
                            "id": new_doc.id,
                            "title": new_doc.title,
                            "documentType": DocumentType.NOTE.value,
                            "workspaceId": workspace_id,
                            "folderId": new_doc.folder_id,
                            "createdById": str(created_by_id)
                            if created_by_id
                            else None,
                            "virtualPath": path,
                        }
                    )
                    tree_changed = True

            # 4. pending_deletes -> rm. Strict: snapshot + DELETE share a
            # SAVEPOINT, so a failed snapshot rolls the delete back too.
            for raw_path, tcid in file_delete_paths.items():
                final = _final_path(raw_path)
                if not final.startswith(DOCUMENTS_ROOT + "/"):
                    continue
                action_id = _action_id_for(tcid)

                doc_id_for_delete = doc_id_by_path.get(final)
                document_to_delete: Document | None = None
                if doc_id_for_delete is not None:
                    result = await session.execute(
                        select(Document).where(
                            Document.id == doc_id_for_delete,
                            Document.workspace_id == workspace_id,
                        )
                    )
                    document_to_delete = result.scalar_one_or_none()
                if document_to_delete is None:
                    document_to_delete = await virtual_path_to_doc(
                        session,
                        workspace_id=workspace_id,
                        virtual_path=final,
                    )
                if document_to_delete is None:
                    logger.info(
                        "kb_persistence: skipping rm %s (target not found)", final
                    )
                    continue

                doc_pk = document_to_delete.id
                doc_title = document_to_delete.title
                doc_folder_id = document_to_delete.folder_id

                try:
                    async with session.begin_nested():
                        if snapshot_enabled and action_id is not None:
                            chunks = await _load_chunks_for_snapshot(
                                session, doc_id=doc_pk
                            )
                            payload = _doc_revision_payload(
                                document_to_delete, chunks_before=chunks
                            )
                            rev = DocumentRevision(
                                document_id=doc_pk,
                                workspace_id=workspace_id,
                                created_by_turn_id=tcid,
                                agent_action_id=action_id,
                                **payload,
                            )
                            session.add(rev)
                            await session.flush()
                            await _mark_action_reversible(session, action_id=action_id)
                        await session.execute(
                            delete(Document).where(Document.id == doc_pk)
                        )
                except Exception as exc:
                    logger.exception(
                        "kb_persistence: strict rm SAVEPOINT for path=%s failed: %s",
                        final,
                        exc,
                    )
                    continue

                # Defer the reversibility flip until after the outer commit.
                if snapshot_enabled and action_id is not None:
                    deferred_dispatches.append(int(action_id))

                doc_id_by_path.pop(final, None)
                doc_id_path_tombstones[final] = None
                committed_deletes.append(
                    {
                        "id": doc_pk,
                        "title": doc_title,
                        "documentType": DocumentType.NOTE.value,
                        "workspaceId": workspace_id,
                        "folderId": doc_folder_id,
                        "createdById": str(created_by_id) if created_by_id else None,
                        "virtualPath": final,
                    }
                )
                tree_changed = True

            # 5. pending_dir_deletes -> rmdir. Strict, and re-checks emptiness
            # against post-step-4 DB state.
            for raw_path, tcid in dir_delete_paths.items():
                final = _final_path(raw_path)
                if not final.startswith(DOCUMENTS_ROOT + "/"):
                    continue
                action_id = _action_id_for(tcid)

                folder_parts = _split_folder_path(final)
                if not folder_parts:
                    continue
                folder_id = await _resolve_folder_id(
                    session,
                    workspace_id=workspace_id,
                    folder_parts=folder_parts,
                )
                if folder_id is None:
                    logger.info(
                        "kb_persistence: skipping rmdir %s (folder not found)", final
                    )
                    continue

                docs_in_folder = await session.execute(
                    select(Document.id)
                    .where(Document.folder_id == folder_id)
                    .where(Document.workspace_id == workspace_id)
                    .limit(1)
                )
                if docs_in_folder.scalar_one_or_none() is not None:
                    logger.warning(
                        "kb_persistence: refusing rmdir %s — non-empty at commit time",
                        final,
                    )
                    continue
                child_folders = await session.execute(
                    select(Folder.id)
                    .where(Folder.parent_id == folder_id)
                    .where(Folder.workspace_id == workspace_id)
                    .limit(1)
                )
                if child_folders.scalar_one_or_none() is not None:
                    logger.warning(
                        "kb_persistence: refusing rmdir %s — has child folders "
                        "at commit time",
                        final,
                    )
                    continue

                folder_to_delete_res = await session.execute(
                    select(Folder).where(Folder.id == folder_id)
                )
                folder_to_delete = folder_to_delete_res.scalar_one_or_none()
                if folder_to_delete is None:
                    continue

                folder_pk = folder_to_delete.id
                folder_name = folder_to_delete.name
                folder_parent_id = folder_to_delete.parent_id
                folder_position = folder_to_delete.position

                try:
                    async with session.begin_nested():
                        if snapshot_enabled and action_id is not None:
                            rev = FolderRevision(
                                folder_id=folder_pk,
                                workspace_id=workspace_id,
                                name_before=folder_name,
                                parent_id_before=folder_parent_id,
                                position_before=folder_position,
                                created_by_turn_id=tcid,
                                agent_action_id=action_id,
                            )
                            session.add(rev)
                            await session.flush()
                            await _mark_action_reversible(session, action_id=action_id)
                        await session.execute(
                            delete(Folder).where(Folder.id == folder_pk)
                        )
                except Exception as exc:
                    logger.exception(
                        "kb_persistence: strict rmdir SAVEPOINT for path=%s failed: %s",
                        final,
                        exc,
                    )
                    continue

                # Defer the reversibility flip until after the outer commit.
                if snapshot_enabled and action_id is not None:
                    deferred_dispatches.append(int(action_id))

                committed_folder_deletes.append(
                    {
                        "id": folder_pk,
                        "name": folder_name,
                        "workspaceId": workspace_id,
                        "parentId": folder_parent_id,
                        "virtualPath": final,
                    }
                )
                tree_changed = True

            await session.commit()
    except Exception:  # pragma: no cover - rollback safety net
        logger.exception("kb_persistence: commit failed (workspace=%s)", workspace_id)
        # Outer commit raised: everything above rolled back, so drop the
        # deferred dispatches.
        deferred_dispatches.clear()
        return None

    # Commit succeeded; flush deferred reversibility flips (de-duped, since
    # write-then-rm in one turn appends an id per snapshot site).
    if deferred_dispatches and dispatch_events:
        for action_id in dict.fromkeys(deferred_dispatches):
            try:
                await _dispatch_reversibility_update(action_id)
            except Exception:
                logger.debug(
                    "kb_persistence: deferred reversibility dispatch failed for action_id=%s",
                    action_id,
                    exc_info=True,
                )

    if dispatch_events:
        for payload in committed_creates:
            try:
                dispatch_custom_event("document_created", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch document_created event"
                )
        for payload in committed_updates:
            try:
                dispatch_custom_event("document_updated", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch document_updated event"
                )
        for payload in committed_deletes:
            try:
                dispatch_custom_event("document_deleted", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch document_deleted event"
                )
        for payload in committed_folder_deletes:
            try:
                dispatch_custom_event("folder_deleted", payload)
            except Exception:
                logger.exception(
                    "kb_persistence: failed to dispatch folder_deleted event"
                )

    temp_paths = [
        p for p in files if isinstance(p, str) and _basename(p).startswith(_TEMP_PREFIX)
    ]

    # Tombstone committed-delete paths so a stale state["files"] entry can't
    # survive into the next turn and make a now-empty folder look non-empty.
    deleted_file_paths = [
        str(payload.get("virtualPath") or "")
        for payload in committed_deletes
        if payload.get("virtualPath")
    ]

    doc_id_update: dict[str, int | None] = {**doc_id_path_tombstones}
    for payload in committed_creates:
        doc_id_update[str(payload.get("virtualPath") or "")] = int(payload["id"])

    delta: dict[str, Any] = {
        "dirty_paths": [_CLEAR],
        "staged_dirs": [_CLEAR],
        "staged_dir_tool_calls": {_CLEAR: True},
        "pending_moves": [_CLEAR],
        "pending_deletes": [_CLEAR],
        "pending_dir_deletes": [_CLEAR],
        "dirty_path_tool_calls": {_CLEAR: True},
    }

    # One Receipt per committed mutation: ground truth (post-savepoint) for the
    # orchestrator's <verification> teaching. KB writes have no public URL.
    receipts: list[Receipt] = []

    def _kb_receipt(
        *,
        type: str,
        operation: str,
        path: str,
        external_id: int | None = None,
    ) -> None:
        if not path:
            return
        preview = path.rsplit("/", 1)[-1] or path
        receipts.append(
            make_receipt(
                route="knowledge_base",
                type=type,
                operation=operation,
                status="success",
                external_id=str(external_id) if external_id is not None else path,
                preview=preview,
            )
        )

    for payload in committed_creates:
        path = str(payload.get("virtualPath") or "")
        _kb_receipt(
            type="file",
            operation="write_file",
            path=path,
            external_id=payload.get("id"),
        )
    for payload in committed_updates:
        path = str(payload.get("virtualPath") or "")
        _kb_receipt(
            type="file",
            operation="edit_file",
            path=path,
            external_id=payload.get("id"),
        )
    for payload in applied_moves:
        path = str(payload.get("virtualPath") or "")
        _kb_receipt(
            type="file",
            operation="move_file",
            path=path,
            external_id=payload.get("id"),
        )
    for path in staged_dirs:
        _kb_receipt(type="folder", operation="mkdir", path=path)
    for payload in committed_deletes:
        path = str(payload.get("virtualPath") or "")
        _kb_receipt(
            type="file",
            operation="rm",
            path=path,
            external_id=payload.get("id"),
        )
    for payload in committed_folder_deletes:
        path = str(payload.get("virtualPath") or "")
        _kb_receipt(
            type="folder",
            operation="rmdir",
            path=path,
            external_id=payload.get("id"),
        )
    if receipts:
        delta["receipts"] = receipts
    files_delta: dict[str, Any] = {}
    if temp_paths:
        files_delta.update(dict.fromkeys(temp_paths))
    for path in deleted_file_paths:
        files_delta[path] = None
    if files_delta:
        delta["files"] = files_delta
    if doc_id_update:
        delta["doc_id_by_path"] = doc_id_update
    if tree_changed:
        delta["tree_version"] = int(state_dict.get("tree_version") or 0) + 1

    _ = turn_id_for_revision  # diagnostic-only; silence unused lint

    logger.info(
        "kb_persistence: commit (workspace=%s) creates=%d updates=%d "
        "moves=%d staged_dirs=%d deletes=%d folder_deletes=%d discarded=%d",
        workspace_id,
        len(committed_creates),
        len(committed_updates),
        len(applied_moves),
        len(staged_dirs),
        len(committed_deletes),
        len(committed_folder_deletes),
        len(discarded),
    )
    return delta


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class KnowledgeBasePersistenceMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """End-of-turn cloud persistence for the Nowing filesystem agent."""

    tools = ()
    state_schema = NowingFilesystemState

    def __init__(
        self,
        *,
        workspace_id: int,
        created_by_id: str | None,
        filesystem_mode: FilesystemMode,
        thread_id: int | None = None,
    ) -> None:
        self.workspace_id = workspace_id
        self.created_by_id = created_by_id
        self.filesystem_mode = filesystem_mode
        self.thread_id = thread_id

    async def aafter_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        if self.filesystem_mode != FilesystemMode.CLOUD:
            return None
        return await commit_staged_filesystem_state(
            state,
            workspace_id=self.workspace_id,
            created_by_id=self.created_by_id,
            filesystem_mode=self.filesystem_mode,
            thread_id=self._resolve_thread_id(),
        )

    def _resolve_thread_id(self) -> int | None:
        """Resolve the live thread id from the active ``RunnableConfig``.

        ``aafter_agent`` only receives a ``Runtime`` (which does NOT carry the
        config), so we read ``configurable.thread_id`` via
        :func:`langgraph.config.get_config` — the same node-context pattern used
        by ``BusyMutexMiddleware``. Resolving at runtime (rather than using the
        value captured at ``__init__``) lets one cached compiled graph commit
        staged writes against the correct thread across many chats. Falls back
        to the constructor value for legacy/test runtimes.
        """
        try:
            config = get_config()
        except Exception:
            config = None
        if isinstance(config, dict):
            value = (config.get("configurable") or {}).get("thread_id")
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return self.thread_id


__all__ = [
    "KnowledgeBasePersistenceMiddleware",
    "commit_staged_filesystem_state",
]
