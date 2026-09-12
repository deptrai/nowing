"""Persistence helpers for the kb_persistence middleware.

Folder/document upsert primitives, staged-move resolution, action-log
binding, and the snapshot/revision writers used by
``commit_staged_filesystem_state``.  Best-effort snapshot variants
(write/edit/move/mkdir) swallow failures; strict variants (rm/rmdir) share
the destructive op's SAVEPOINT so a snapshot failure aborts the delete.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fractional_indexing import generate_key_between
from langchain_core.callbacks import adispatch_custom_event
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.receipts.receipt import (
    Receipt,
    make_receipt,
)
from app.agents.chat.runtime.path_resolver import (
    DOCUMENTS_ROOT,
    parse_documents_path,
    safe_folder_segment,
    virtual_path_to_doc,
)
from app.db import (
    AgentActionLog,
    Chunk,
    Document,
    DocumentRevision,
    DocumentType,
    Folder,
    FolderRevision,
)
from app.indexing_pipeline.document_chunker import chunk_text
from app.utils.document_converters import (
    embed_texts,
    generate_content_hash,
    generate_unique_identifier_hash,
)

logger = logging.getLogger(__name__)


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Folder helpers
# ---------------------------------------------------------------------------


async def _ensure_folder_hierarchy(
    session: AsyncSession,
    *,
    workspace_id: int,
    created_by_id: str | None,
    folder_parts: list[str],
) -> int | None:
    """Ensure a chain of folder names exists under the workspace.

    Returns the leaf folder id, or ``None`` if ``folder_parts`` is empty
    (i.e. a document directly under ``/documents/``).
    """
    if not folder_parts:
        return None
    parent_id: int | None = None
    for raw in folder_parts:
        name = safe_folder_segment(str(raw))
        query = select(Folder).where(
            Folder.workspace_id == workspace_id,
            Folder.name == name,
        )
        if parent_id is None:
            query = query.where(Folder.parent_id.is_(None))
        else:
            query = query.where(Folder.parent_id == parent_id)
        result = await session.execute(query)
        folder = result.scalar_one_or_none()
        if folder is None:
            sibling_query = (
                select(Folder.position).order_by(Folder.position.desc()).limit(1)
            )
            sibling_query = sibling_query.where(Folder.workspace_id == workspace_id)
            if parent_id is None:
                sibling_query = sibling_query.where(Folder.parent_id.is_(None))
            else:
                sibling_query = sibling_query.where(Folder.parent_id == parent_id)
            sibling_result = await session.execute(sibling_query)
            last_position = sibling_result.scalar_one_or_none()
            folder = Folder(
                name=name,
                position=generate_key_between(last_position, None),
                parent_id=parent_id,
                workspace_id=workspace_id,
                created_by_id=created_by_id,
                updated_at=datetime.now(UTC),
            )
            session.add(folder)
            await session.flush()
        parent_id = folder.id
    return parent_id


async def _resolve_folder_id(
    session: AsyncSession,
    *,
    workspace_id: int,
    folder_parts: list[str],
) -> int | None:
    """Look up an existing folder chain without creating anything.

    Returns ``None`` if any segment is missing. Used by ``rmdir`` snapshot
    capture and by parent-folder lookup at ``rmdir`` commit time.
    """
    if not folder_parts:
        return None
    parent_id: int | None = None
    for raw in folder_parts:
        name = safe_folder_segment(str(raw))
        query = select(Folder).where(
            Folder.workspace_id == workspace_id,
            Folder.name == name,
        )
        query = (
            query.where(Folder.parent_id.is_(None))
            if parent_id is None
            else query.where(Folder.parent_id == parent_id)
        )
        result = await session.execute(query)
        folder = result.scalar_one_or_none()
        if folder is None:
            return None
        parent_id = folder.id
    return parent_id


def _split_folder_path(folder_path: str) -> list[str]:
    """Return the folder segments under ``/documents/`` for a path."""
    if not folder_path.startswith(DOCUMENTS_ROOT):
        return []
    rel = folder_path[len(DOCUMENTS_ROOT) :].strip("/")
    return [p for p in rel.split("/") if p]


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------


async def _create_document(
    session: AsyncSession,
    *,
    virtual_path: str,
    content: str,
    workspace_id: int,
    created_by_id: str | None,
) -> Document:
    """Create a NOTE Document + Chunks for ``virtual_path``."""
    folder_parts, title = parse_documents_path(virtual_path)
    if not title:
        raise ValueError(f"invalid /documents path '{virtual_path}'")
    folder_id = await _ensure_folder_hierarchy(
        session,
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        folder_parts=folder_parts,
    )
    unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.NOTE,
        virtual_path,
        workspace_id,
    )
    # Pre-check the path-derived unique_identifier_hash so a duplicate path
    # surfaces as a clean ValueError instead of an INSERT IntegrityError that
    # poisons the session. Content is intentionally not unique (cp a b).
    path_collision = await session.execute(
        select(Document.id).where(
            Document.workspace_id == workspace_id,
            Document.unique_identifier_hash == unique_identifier_hash,
        )
    )
    if path_collision.scalar_one_or_none() is not None:
        raise ValueError(
            f"a document already exists at path '{virtual_path}' "
            "(unique_identifier_hash collision)"
        )
    content_hash = generate_content_hash(content, workspace_id)
    doc = Document(
        title=title,
        document_type=DocumentType.NOTE,
        document_metadata={"virtual_path": virtual_path},
        content=content,
        content_hash=content_hash,
        unique_identifier_hash=unique_identifier_hash,
        source_markdown=content,
        workspace_id=workspace_id,
        folder_id=folder_id,
        created_by_id=created_by_id,
        updated_at=datetime.now(UTC),
    )
    session.add(doc)
    await session.flush()

    summary_embedding = (await asyncio.to_thread(embed_texts, [content]))[0]
    doc.embedding = summary_embedding
    chunks = chunk_text(content)
    if chunks:
        chunk_embeddings = await asyncio.to_thread(embed_texts, chunks)
        session.add_all(
            [
                Chunk(
                    document_id=doc.id,
                    content=text,
                    embedding=embedding,
                    position=i,
                )
                for i, (text, embedding) in enumerate(
                    zip(chunks, chunk_embeddings, strict=True)
                )
            ]
        )
    return doc


async def _update_document(
    session: AsyncSession,
    *,
    doc_id: int,
    content: str,
    virtual_path: str,
    workspace_id: int,
) -> Document | None:
    """Update an existing Document's content + chunks."""
    result = await session.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.workspace_id == workspace_id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        return None

    document.content = content
    document.source_markdown = content
    document.content_hash = generate_content_hash(content, workspace_id)
    document.updated_at = datetime.now(UTC)
    metadata = dict(document.document_metadata or {})
    metadata["virtual_path"] = virtual_path
    document.document_metadata = metadata
    document.unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.NOTE,
        virtual_path,
        workspace_id,
    )

    summary_embedding = (await asyncio.to_thread(embed_texts, [content]))[0]
    document.embedding = summary_embedding

    await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    chunks = chunk_text(content)
    if chunks:
        chunk_embeddings = await asyncio.to_thread(embed_texts, chunks)
        session.add_all(
            [
                Chunk(
                    document_id=document.id,
                    content=text,
                    embedding=embedding,
                    position=i,
                )
                for i, (text, embedding) in enumerate(
                    zip(chunks, chunk_embeddings, strict=True)
                )
            ]
        )
    return document


# ---------------------------------------------------------------------------
# Move helpers
# ---------------------------------------------------------------------------


async def _apply_move(
    session: AsyncSession,
    *,
    workspace_id: int,
    created_by_id: str | None,
    move: dict[str, Any],
    doc_id_by_path: dict[str, int],
    doc_id_path_tombstones: dict[str, int | None],
) -> dict[str, Any] | None:
    """Apply a single staged move; updates the in-memory mapping for chain resolution."""
    source = str(move.get("source") or "")
    dest = str(move.get("dest") or "")
    if not source or not dest or source == dest:
        return None

    if not source.startswith(DOCUMENTS_ROOT + "/") or not dest.startswith(
        DOCUMENTS_ROOT + "/"
    ):
        return None

    doc_id: int | None = doc_id_by_path.get(source)
    document: Document | None = None
    if doc_id is not None:
        result = await session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.workspace_id == workspace_id,
            )
        )
        document = result.scalar_one_or_none()
    if document is None:
        document = await virtual_path_to_doc(
            session,
            workspace_id=workspace_id,
            virtual_path=source,
        )
    if document is None:
        logger.info(
            "kb_persistence: skipping move %s -> %s (source not found)",
            source,
            dest,
        )
        return None

    folder_parts, new_title = parse_documents_path(dest)
    if not new_title:
        return None
    folder_id = await _ensure_folder_hierarchy(
        session,
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        folder_parts=folder_parts,
    )

    document.title = new_title
    document.folder_id = folder_id
    metadata = dict(document.document_metadata or {})
    metadata["virtual_path"] = dest
    document.document_metadata = metadata
    document.unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.NOTE,
        dest,
        workspace_id,
    )
    document.updated_at = datetime.now(UTC)

    doc_id_by_path.pop(source, None)
    doc_id_by_path[dest] = document.id
    doc_id_path_tombstones[source] = None
    doc_id_path_tombstones[dest] = document.id
    return {"id": document.id, "source": source, "dest": dest, "title": new_title}


# ---------------------------------------------------------------------------
# Action log binding helpers
# ---------------------------------------------------------------------------


async def _find_action_ids_batch(
    session: AsyncSession,
    *,
    thread_id: int | None,
    tool_call_ids: set[str],
) -> dict[str, int]:
    """Resolve ``tool_call_id -> AgentActionLog.id`` in a single query.

    Returns an empty dict when ``thread_id`` or ``tool_call_ids`` are
    missing — callers treat that as "no binding available" and write the
    revision with ``agent_action_id = NULL``.
    """
    if thread_id is None or not tool_call_ids:
        return {}
    rows = await session.execute(
        select(AgentActionLog.id, AgentActionLog.tool_call_id).where(
            AgentActionLog.thread_id == thread_id,
            AgentActionLog.tool_call_id.in_(list(tool_call_ids)),
        )
    )
    mapping: dict[str, int] = {}
    for row in rows.all():
        if row.tool_call_id and row.id:
            mapping[str(row.tool_call_id)] = int(row.id)
    return mapping


async def _mark_action_reversible(
    session: AsyncSession,
    *,
    action_id: int | None,
) -> None:
    """Flip ``agent_action_log.reversible = TRUE`` for ``action_id``.

    Pair with ``_dispatch_reversibility_update`` *after* the enclosing
    SAVEPOINT commits, so the UI never sees ``reversible=true`` for a row whose
    update later rolls back.
    """
    if action_id is None:
        return
    await session.execute(
        update(AgentActionLog)
        .where(AgentActionLog.id == action_id)
        .values(reversible=True)
    )


async def _dispatch_reversibility_update(action_id: int | None) -> None:
    """Emit an ``action_log_updated`` SSE event so the Revert button lights up.

    Best-effort (failures swallowed; the REST actions endpoint is
    authoritative). Inside :func:`commit_staged_filesystem_state` this is
    deferred until after the outer commit via ``deferred_dispatches``.
    """
    if action_id is None:
        return
    try:
        await adispatch_custom_event(
            "action_log_updated",
            {"id": int(action_id), "reversible": True},
        )
    except Exception:
        logger.debug(
            "kb_persistence.aafter_agent failed to dispatch action_log_updated",
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------
# Best-effort variants (write/edit/move/mkdir) swallow failures. Strict
# variants (rm/rmdir) share the destructive op's SAVEPOINT so a snapshot
# failure aborts the delete instead of making it silently irreversible.


def _doc_revision_payload(
    doc: Document,
    *,
    chunks_before: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Pre-mutation field map for ``DocumentRevision``."""
    metadata = dict(doc.document_metadata or {})
    return {
        "content_before": doc.content,
        "title_before": doc.title,
        "folder_id_before": doc.folder_id,
        "chunks_before": chunks_before,
        "metadata_before": metadata or None,
    }


async def _load_chunks_for_snapshot(
    session: AsyncSession, *, doc_id: int
) -> list[dict[str, str]]:
    rows = await session.execute(
        select(Chunk.content)
        .where(Chunk.document_id == doc_id)
        .order_by(Chunk.position, Chunk.id)
    )
    return [{"content": row.content} for row in rows.all() if row.content is not None]


async def _snapshot_document_pre_write(
    session: AsyncSession,
    *,
    doc: Document,
    action_id: int | None,
    workspace_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort snapshot ahead of an in-place ``write_file``/``edit_file``.

    When ``deferred_dispatches`` is provided, on success the action id
    is APPENDED to it and the SSE dispatch is left to the caller (so it
    can be flushed only after the outer ``session.commit()`` succeeds).
    """
    try:
        async with session.begin_nested():
            chunks = await _load_chunks_for_snapshot(session, doc_id=doc.id)
            payload = _doc_revision_payload(doc, chunks_before=chunks)
            rev = DocumentRevision(
                document_id=doc.id,
                workspace_id=workspace_id,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
                **payload,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "kb_persistence: pre-write snapshot for doc=%s failed: %s",
            doc.id,
            exc,
        )
        return None


async def _snapshot_document_pre_create(
    session: AsyncSession,
    *,
    action_id: int | None,
    workspace_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort placeholder revision for a fresh ``write_file`` create.

    ``document_id`` is patched in by the caller after the new doc is
    flushed and gets an ID; the placeholder lets us bind the action_id
    even though no parent row exists yet.
    """
    try:
        async with session.begin_nested():
            rev = DocumentRevision(
                document_id=None,
                workspace_id=workspace_id,
                content_before=None,
                title_before=None,
                folder_id_before=None,
                chunks_before=None,
                metadata_before=None,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("kb_persistence: pre-create snapshot failed: %s", exc)
        return None


async def _snapshot_document_pre_move(
    session: AsyncSession,
    *,
    doc: Document,
    action_id: int | None,
    workspace_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort snapshot ahead of a ``move_file``."""
    try:
        async with session.begin_nested():
            payload = _doc_revision_payload(doc, chunks_before=None)
            rev = DocumentRevision(
                document_id=doc.id,
                workspace_id=workspace_id,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
                **payload,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "kb_persistence: pre-move snapshot for doc=%s failed: %s",
            doc.id,
            exc,
        )
        return None


async def _snapshot_folder_pre_mkdir(
    session: AsyncSession,
    *,
    folder: Folder,
    action_id: int | None,
    workspace_id: int,
    turn_id: str | None = None,
    deferred_dispatches: list[int] | None = None,
) -> int | None:
    """Best-effort placeholder for an ``mkdir`` (revert deletes the folder).

    The "before" state is "did not exist", so all ``*_before`` fields are
    NULL — revert routes by ``tool_name == "mkdir"`` and DELETEs.
    """
    try:
        async with session.begin_nested():
            rev = FolderRevision(
                folder_id=folder.id,
                workspace_id=workspace_id,
                name_before=None,
                parent_id_before=None,
                position_before=None,
                created_by_turn_id=turn_id,
                agent_action_id=action_id,
            )
            session.add(rev)
            await session.flush()
            await _mark_action_reversible(session, action_id=action_id)
            rev_id = rev.id
        if deferred_dispatches is None:
            await _dispatch_reversibility_update(action_id)
        elif action_id is not None:
            deferred_dispatches.append(int(action_id))
        return rev_id
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "kb_persistence: pre-mkdir snapshot for folder=%s failed: %s",
            folder.id,
            exc,
        )
        return None


async def _resolve_action_ids(
    session: AsyncSession,
    *,
    thread_id: int | None,
    snapshot_enabled: bool,
    staged_dir_tool_calls: dict[str, str],
    pending_moves: list[dict[str, Any]],
    dirty_path_tool_calls: dict[str, str],
    file_delete_paths: dict[str, str],
    dir_delete_paths: dict[str, str],
) -> dict[str, int]:
    """Resolve all action-id bindings in one SELECT per turn, not per op."""
    if not (snapshot_enabled and thread_id is not None):
        return {}
    tool_call_ids: set[str] = set()
    tool_call_ids.update(tcid for tcid in staged_dir_tool_calls.values() if tcid)
    for move in pending_moves:
        tcid = str(move.get("tool_call_id") or "")
        if tcid:
            tool_call_ids.add(tcid)
    tool_call_ids.update(tcid for tcid in dirty_path_tool_calls.values() if tcid)
    tool_call_ids.update(tcid for tcid in file_delete_paths.values() if tcid)
    tool_call_ids.update(tcid for tcid in dir_delete_paths.values() if tcid)
    return await _find_action_ids_batch(
        session,
        thread_id=thread_id,
        tool_call_ids=tool_call_ids,
    )


def _build_commit_receipts(
    *,
    committed_creates: list[dict[str, Any]],
    committed_updates: list[dict[str, Any]],
    applied_moves: list[dict[str, Any]],
    staged_dirs: list[str],
    committed_deletes: list[dict[str, Any]],
    committed_folder_deletes: list[dict[str, Any]],
) -> list[Receipt]:
    """Build ground-truth Receipts for each committed mutation."""
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
    return receipts
