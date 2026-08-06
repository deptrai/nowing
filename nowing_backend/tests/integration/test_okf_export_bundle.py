"""A real export must be a conformant OKF bundle end-to-end (real DB).

Unit tests cover the pure serializer; this drives the whole export pipeline
(folder-path map, batching, ZIP writing) and asserts the emitted artifact -
concept files plus reserved ``index.md``/``log.md`` - passes ``validate_bundle``.
"""

import os
import zipfile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import (
    Chunk,
    Document,
    DocumentType,
    Folder,
    Memory,
    MemoryRelation,
    MemoryRelationType,
    MemorySourceType,
    MemoryType,
    User,
    Workspace,
)
from app.services.export_service import build_export_zip
from app.services.okf import validate_bundle

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension

pytestmark = pytest.mark.integration


async def _add_doc(
    session: AsyncSession,
    *,
    workspace: Workspace,
    user: User,
    title: str,
    folder_id: int | None,
    uid: str,
    document_type: DocumentType = DocumentType.NOTE,
) -> Document:
    doc = Document(
        title=title,
        document_type=document_type,
        document_metadata={"tags": ["team"], "url": "https://example.com/" + uid},
        content="body text",
        content_hash=uid,
        unique_identifier_hash=uid,
        source_markdown=f"# {title}\n\nBody.",
        workspace_id=workspace.id,
        created_by_id=user.id,
        folder_id=folder_id,
    )
    session.add(doc)
    await session.flush()
    return doc


async def _add_chunk(
    session: AsyncSession, document: Document, position: int, content: str
) -> Chunk:
    chunk = Chunk(
        content=content,
        position=position,
        document_id=document.id,
        embedding=[0.0] * _EMBEDDING_DIM,
    )
    session.add(chunk)
    await session.flush()
    return chunk


async def _add_memory(
    session: AsyncSession,
    workspace: Workspace,
    content: str,
    source_type: MemorySourceType = MemorySourceType.MANUAL,
    source_id: int | None = None,
) -> Memory:
    memory = Memory(
        workspace_id=workspace.id,
        content=content,
        embedding=[0.0] * _EMBEDDING_DIM,
        type=MemoryType.SEMANTIC,
        source_type=source_type,
        source_id=source_id,
        source_capability="search",
        source_input={"api_key": "sk-redact-me", "query": "okf"},
    )
    session.add(memory)
    await session.flush()
    return memory


async def _add_relation(
    session: AsyncSession,
    workspace: Workspace,
    from_memory: Memory,
    to_memory: Memory,
) -> MemoryRelation:
    relation = MemoryRelation(
        workspace_id=workspace.id,
        from_memory_id=from_memory.id,
        to_memory_id=to_memory.id,
        relation_type=MemoryRelationType.RELATED,
    )
    session.add(relation)
    await session.flush()
    return relation


async def test_export_bundle_is_okf_conformant(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    folder = Folder(name="Research", position="0", workspace_id=db_workspace.id)
    db_session.add(folder)
    await db_session.flush()

    root_doc = await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Root Note",
        folder_id=None,
        uid="okf-export-root",
    )
    nested_doc = await _add_doc(
        db_session,
        workspace=db_workspace,
        user=db_user,
        title="Nested Note",
        folder_id=folder.id,
        uid="okf-export-nested",
    )

    await _add_chunk(db_session, root_doc, 0, "First chunk.")
    await _add_chunk(db_session, nested_doc, 0, "Nested chunk.")

    memory = await _add_memory(
        db_session,
        db_workspace,
        "Document-derived memory",
        source_type=MemorySourceType.DOCUMENT,
        source_id=root_doc.id,
    )
    other = await _add_memory(
        db_session, db_workspace, "Other memory", source_type=MemorySourceType.MANUAL
    )
    await _add_relation(db_session, db_workspace, memory, other)

    result = await build_export_zip(db_session, db_workspace.id)
    try:
        with zipfile.ZipFile(result.zip_path) as zf:
            files = {name: zf.read(name).decode("utf-8") for name in zf.namelist()}
    finally:
        os.unlink(result.zip_path)

    # Directory structure: concepts nested by folder, plus reserved files.
    assert "Root Note.md" in files
    assert "Research/Nested Note.md" in files
    assert files["index.md"].startswith('---\nokf_version: "0.2"\n---')
    assert any(name.endswith("log.md") for name in files)

    # .okf reserved subdirectories
    assert any(
        name.startswith(".okf/chunks/") and name.endswith(".md") for name in files
    )
    assert any(
        name.startswith(".okf/memories/") and name.endswith(".md") for name in files
    )
    assert any(
        name.startswith(".okf/relations/") and name.endswith(".md") for name in files
    )
    assert any(
        name.startswith(".okf/citations/") and name.endswith(".md") for name in files
    )

    # No raw secrets leaked.
    bundle_text = "\n".join(files.values())
    assert "sk-redact-me" not in bundle_text
    assert "nw_pat_" not in bundle_text

    # The whole bundle conforms; reserved index/log files are exempt.
    assert validate_bundle(files) == {}
