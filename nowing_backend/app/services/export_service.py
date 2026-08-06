"""Service for exporting knowledge base content as an OKF ZIP archive."""

import asyncio
import logging
import os
import tempfile
import zipfile
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    Chunk,
    Document,
    Folder,
    Memory,
    MemoryRelation,
    MemorySourceType,
)
from app.services.folder_service import get_folder_subtree_ids
from app.services.okf import (
    INDEX_FILENAME,
    LOG_FILENAME,
    ConceptRef,
    LogEntry,
    SubdirRef,
    chunk_to_concept,
    citation_to_concept,
    document_to_concept,
    folder_to_index,
    folder_to_log,
    memory_to_concept,
    okf_memory_type,
    okf_relation_type,
    okf_type,
    redact_secrets,
    relation_to_concept,
)

logger = logging.getLogger(__name__)

# Root index.md declares the targeted OKF version in frontmatter - the one place
# the spec permits frontmatter in an index file.
_ROOT_INDEX_FRONTMATTER = '---\nokf_version: "0.2"\n---\n\n'

_RESERVED_STEMS = {"index", "log"}

_OKF_CHUNK_DIR = ".okf/chunks"
_OKF_MEMORY_DIR = ".okf/memories"
_OKF_RELATION_DIR = ".okf/relations"
_OKF_CITATION_DIR = ".okf/citations"


def _sanitize_filename(title: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in title).strip()
    return safe[:80] or "concept"


def _build_folder_path_map(folders: list[Folder]) -> dict[int, str]:
    """Build a mapping of folder_id -> full path string (e.g. 'Research/AI')."""
    id_to_folder = {f.id: f for f in folders}
    cache: dict[int, str] = {}

    def resolve(folder_id: int) -> str:
        if folder_id in cache:
            return cache[folder_id]
        folder = id_to_folder[folder_id]
        safe_name = _sanitize_filename(folder.name)
        if folder.parent_id is None or folder.parent_id not in id_to_folder:
            cache[folder_id] = safe_name
        else:
            cache[folder_id] = f"{resolve(folder.parent_id)}/{safe_name}"
        return cache[folder_id]

    for f in folders:
        resolve(f.id)

    return cache


def _unique_file_path(
    base_name: str, dir_path: str, used_paths: dict[str, int]
) -> tuple[str, str]:
    """Return a unique (base_name, relative_file_path) inside a directory."""
    if base_name.lower() in _RESERVED_STEMS:
        base_name = f"{base_name}_"
    file_path = f"{dir_path}/{base_name}.md" if dir_path else f"{base_name}.md"

    while file_path in used_paths:
        used_paths[file_path] += 1
        suffix = used_paths[file_path]
        base_name = f"{base_name}_{suffix}"
        file_path = f"{dir_path}/{base_name}.md" if dir_path else f"{base_name}.md"

    used_paths[file_path] = used_paths.get(file_path, 0) + 1
    return base_name, file_path


def _add_dir_entry(
    dir_concepts: dict[str, list[ConceptRef]],
    dir_logs: dict[str, list[LogEntry]],
    dir_path: str,
    title: str,
    filename: str,
    type_str: str,
    description: str | None,
    timestamp: str | None,
) -> None:
    """Accumulate a ConceptRef and a LogEntry for a directory."""
    dir_concepts.setdefault(dir_path, []).append(
        ConceptRef(
            title=title,
            filename=filename,
            type=type_str,
            description=description,
        )
    )
    dir_logs.setdefault(dir_path, []).append(LogEntry(title=title, timestamp=timestamp))


def _build_index_files(
    dir_concepts: dict[str, list[ConceptRef]],
) -> list[tuple[str, str]]:
    """Build ``index.md`` files for every directory (and ancestor) with content."""
    all_dirs: set[str] = {""}
    for dir_path in dir_concepts:
        all_dirs.add(dir_path)
        parts = dir_path.split("/") if dir_path else []
        for i in range(1, len(parts)):
            all_dirs.add("/".join(parts[:i]))

    children_by_dir: dict[str, list[str]] = {}
    for dir_path in all_dirs:
        if not dir_path:
            continue
        parent = dir_path.rsplit("/", 1)[0] if "/" in dir_path else ""
        children_by_dir.setdefault(parent, []).append(dir_path)

    index_files: list[tuple[str, str]] = []
    for dir_path in all_dirs:
        subdirs = [
            SubdirRef(name=child.rsplit("/", 1)[-1])
            for child in children_by_dir.get(dir_path, [])
        ]
        body = folder_to_index(
            concepts=dir_concepts.get(dir_path, []),
            subdirectories=subdirs,
        )
        if not body:
            continue
        if dir_path:
            index_files.append((f"{dir_path}/{INDEX_FILENAME}", body))
        else:
            index_files.append((INDEX_FILENAME, _ROOT_INDEX_FRONTMATTER + body))

    return index_files


def _build_log_files(
    dir_logs: dict[str, list[LogEntry]],
) -> list[tuple[str, str]]:
    """Build ``log.md`` files for every directory that holds concepts."""
    log_files: list[tuple[str, str]] = []
    for dir_path, entries in dir_logs.items():
        body = folder_to_log(entries)
        if not body:
            continue
        path = f"{dir_path}/{LOG_FILENAME}" if dir_path else LOG_FILENAME
        log_files.append((path, body))
    return log_files


def _timestamp(model: Document | Memory | Chunk | MemoryRelation) -> str | None:
    when = getattr(model, "updated_at", None) or getattr(model, "created_at", None)
    return when.isoformat() if when else None


def _write_zip_batch(zip_path: str, mode: str, entries: list[tuple[str, str]]) -> None:
    with zipfile.ZipFile(zip_path, mode, zipfile.ZIP_DEFLATED) as zf:
        for path, content in entries:
            zf.writestr(path, content)


async def resolve_document_markdown(
    session: AsyncSession, document: Document
) -> str | None:
    """Resolve markdown content using the 3-tier fallback:
    1. source_markdown  2. blocknote_document conversion  3. chunk concatenation
    """
    if document.source_markdown is not None:
        return document.source_markdown

    if document.blocknote_document:
        from app.utils.blocknote_to_markdown import blocknote_to_markdown

        md = blocknote_to_markdown(document.blocknote_document)
        if md:
            return md

    chunk_result = await session.execute(
        select(Chunk.content)
        .filter(Chunk.document_id == document.id)
        .order_by(Chunk.position, Chunk.id)
    )
    chunks = chunk_result.scalars().all()
    if chunks:
        return "\n\n".join(chunks)

    return None


@dataclass
class ExportResult:
    zip_path: str
    export_name: str
    zip_size: int
    skipped_docs: list[str] = field(default_factory=list)


async def build_export_zip(
    session: AsyncSession,
    workspace_id: int,
    folder_id: int | None = None,
) -> ExportResult:
    """Build a ZIP archive of OKF concepts preserving folder structure.

    Returns an ExportResult with the path to the temp ZIP file.
    The caller is responsible for streaming and cleaning up the file.

    Raises ValueError if folder_id is provided but not found.
    """
    if folder_id is not None:
        folder = await session.get(Folder, folder_id)
        if not folder or folder.workspace_id != workspace_id:
            raise ValueError("Folder not found")
        target_folder_ids = set(await get_folder_subtree_ids(session, folder_id))
    else:
        target_folder_ids = None

    folder_query = select(Folder).where(Folder.workspace_id == workspace_id)
    if target_folder_ids is not None:
        folder_query = folder_query.where(Folder.id.in_(target_folder_ids))
    folder_result = await session.execute(folder_query)
    folders = list(folder_result.scalars().all())

    folder_path_map = _build_folder_path_map(folders)

    batch_size = 100

    base_doc_query = select(Document).where(Document.workspace_id == workspace_id)
    if target_folder_ids is not None:
        base_doc_query = base_doc_query.where(Document.folder_id.in_(target_folder_ids))
    base_doc_query = base_doc_query.order_by(Document.id)

    fd, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    used_paths: dict[str, int] = {}
    skipped_docs: list[str] = []
    is_first_batch = True

    # dir path -> concepts it holds, accumulated across batches for index.md.
    dir_concepts: dict[str, list[ConceptRef]] = {}
    # dir path -> log entries it holds, accumulated across batches for log.md.
    dir_logs: dict[str, list[LogEntry]] = {}

    # Track exported documents so chunks and memory document-sources can resolve.
    doc_id_to_bundle_path: dict[int, str] = {}
    doc_id_to_description: dict[int, str | None] = {}

    try:
        # ------------------------------------------------------------------
        # Documents
        # ------------------------------------------------------------------
        offset = 0
        while True:
            batch_query = base_doc_query.limit(batch_size).offset(offset)
            batch_result = await session.execute(batch_query)
            documents = list(batch_result.scalars().all())
            if not documents:
                break

            entries: list[tuple[str, str]] = []

            for doc in documents:
                status = doc.status or {}
                state = (
                    status.get("state", "ready")
                    if isinstance(status, dict)
                    else "ready"
                )
                if state in ("pending", "processing"):
                    skipped_docs.append(doc.title or "Untitled")
                    continue

                markdown = await resolve_document_markdown(session, doc)
                if not markdown or not markdown.strip():
                    continue

                if doc.folder_id and doc.folder_id in folder_path_map:
                    dir_path = folder_path_map[doc.folder_id]
                else:
                    dir_path = ""

                base_name = _sanitize_filename(doc.title or "Untitled")
                base_name, file_path = _unique_file_path(
                    base_name, dir_path, used_paths
                )

                concept = document_to_concept(doc, body=markdown)
                entries.append((file_path, concept))

                doc_id_to_bundle_path[doc.id] = file_path

                redacted_metadata = redact_secrets(
                    doc.document_metadata
                    if isinstance(doc.document_metadata, dict)
                    else {}
                )
                description = redacted_metadata.get("description")
                if isinstance(description, str) and description.strip():
                    doc_id_to_description[doc.id] = description.strip()
                else:
                    doc_id_to_description[doc.id] = None

                _add_dir_entry(
                    dir_concepts,
                    dir_logs,
                    dir_path,
                    title=doc.title or "Untitled",
                    filename=f"{base_name}.md",
                    type_str=okf_type(doc.document_type),
                    description=doc_id_to_description[doc.id],
                    timestamp=_timestamp(doc),
                )

            if entries:
                mode = "w" if is_first_batch else "a"
                await asyncio.to_thread(_write_zip_batch, tmp_path, mode, entries)
                is_first_batch = False

            offset += batch_size

        # ------------------------------------------------------------------
        # Chunks
        # ------------------------------------------------------------------
        doc_ids = list(doc_id_to_bundle_path.keys())
        if doc_ids:
            offset = 0
            while True:
                chunk_batch = (
                    select(Chunk)
                    .where(Chunk.document_id.in_(doc_ids))
                    .order_by(Chunk.document_id, Chunk.position, Chunk.id)
                    .limit(batch_size)
                    .offset(offset)
                )
                chunk_result = await session.execute(chunk_batch)
                chunks = list(chunk_result.scalars().all())
                if not chunks:
                    break

                entries: list[tuple[str, str]] = []
                for chunk in chunks:
                    document_path = doc_id_to_bundle_path.get(chunk.document_id)
                    if not document_path:
                        continue

                    base_name = f"chunk_{chunk.id}"
                    base_name, file_path = _unique_file_path(
                        base_name, _OKF_CHUNK_DIR, used_paths
                    )

                    concept = chunk_to_concept(chunk, document_path=document_path)
                    entries.append((file_path, concept))

                    _add_dir_entry(
                        dir_concepts,
                        dir_logs,
                        _OKF_CHUNK_DIR,
                        title=f"Chunk {chunk.position}",
                        filename=f"{base_name}.md",
                        type_str="Chunk",
                        description=doc_id_to_description.get(chunk.document_id),
                        timestamp=_timestamp(chunk),
                    )

                if entries:
                    mode = "w" if is_first_batch else "a"
                    await asyncio.to_thread(_write_zip_batch, tmp_path, mode, entries)
                    is_first_batch = False

                offset += batch_size

        # ------------------------------------------------------------------
        # Memories + citations
        # ------------------------------------------------------------------
        memory_query = (
            select(Memory)
            .where(Memory.workspace_id == workspace_id)
            .order_by(Memory.id)
        )
        memory_id_to_bundle_path: dict[int, str] = {}
        offset = 0
        while True:
            memory_batch = memory_query.limit(batch_size).offset(offset)
            memory_result = await session.execute(memory_batch)
            memories = list(memory_result.scalars().all())
            if not memories:
                break

            entries: list[tuple[str, str]] = []
            for memory in memories:
                source_path: str | None = None
                if memory.source_type == MemorySourceType.DOCUMENT and memory.source_id:
                    source_path = doc_id_to_bundle_path.get(memory.source_id)

                memory_concept = memory_to_concept(memory, source_path=source_path)

                base_name = f"memory_{memory.id}"
                base_name, file_path = _unique_file_path(
                    base_name, _OKF_MEMORY_DIR, used_paths
                )
                entries.append((file_path, memory_concept))
                memory_id_to_bundle_path[memory.id] = file_path

                _add_dir_entry(
                    dir_concepts,
                    dir_logs,
                    _OKF_MEMORY_DIR,
                    title=_memory_title(memory),
                    filename=f"{base_name}.md",
                    type_str=okf_memory_type(memory),
                    description=None,
                    timestamp=_timestamp(memory),
                )

                # Synthesize a citation concept when provenance is available.
                citation_source: str | None = source_path
                if not citation_source:
                    if memory.source_run_id is not None:
                        citation_source = f"run_{memory.source_run_id}"
                    elif (
                        memory.source_type == MemorySourceType.CHAT_MESSAGE
                        and memory.source_id
                    ):
                        citation_source = f"chat_{memory.source_id}"

                if citation_source:
                    citation = citation_to_concept(memory, source_path=citation_source)
                    cit_base = f"citation_{memory.id}"
                    _, cit_path = _unique_file_path(
                        cit_base, _OKF_CITATION_DIR, used_paths
                    )
                    entries.append((cit_path, citation))

                    _add_dir_entry(
                        dir_concepts,
                        dir_logs,
                        _OKF_CITATION_DIR,
                        title=citation_source,
                        filename=cit_path.rsplit("/", 1)[-1],
                        type_str="Citation",
                        description=None,
                        timestamp=_timestamp(memory),
                    )

            if entries:
                mode = "w" if is_first_batch else "a"
                await asyncio.to_thread(_write_zip_batch, tmp_path, mode, entries)
                is_first_batch = False

            offset += batch_size

        # ------------------------------------------------------------------
        # Memory relations
        # ------------------------------------------------------------------
        relation_query = (
            select(MemoryRelation)
            .where(MemoryRelation.workspace_id == workspace_id)
            .order_by(MemoryRelation.id)
        )
        offset = 0
        while True:
            relation_batch = relation_query.limit(batch_size).offset(offset)
            relation_result = await session.execute(relation_batch)
            relations = list(relation_result.scalars().all())
            if not relations:
                break

            entries: list[tuple[str, str]] = []
            for relation in relations:
                from_path = memory_id_to_bundle_path.get(relation.from_memory_id)
                to_path = memory_id_to_bundle_path.get(relation.to_memory_id)

                concept = relation_to_concept(
                    relation, from_path=from_path, to_path=to_path
                )

                base_name = f"relation_{relation.id}"
                base_name, file_path = _unique_file_path(
                    base_name, _OKF_RELATION_DIR, used_paths
                )
                entries.append((file_path, concept))

                _add_dir_entry(
                    dir_concepts,
                    dir_logs,
                    _OKF_RELATION_DIR,
                    title=f"{okf_relation_type(relation)} Relation",
                    filename=f"{base_name}.md",
                    type_str=okf_relation_type(relation),
                    description=None,
                    timestamp=_timestamp(relation),
                )

            if entries:
                mode = "w" if is_first_batch else "a"
                await asyncio.to_thread(_write_zip_batch, tmp_path, mode, entries)
                is_first_batch = False

            offset += batch_size

        # ------------------------------------------------------------------
        # Index + log files (written once after all concepts are known)
        # ------------------------------------------------------------------
        index_files = _build_index_files(dir_concepts)
        if index_files:
            mode = "w" if is_first_batch else "a"
            await asyncio.to_thread(_write_zip_batch, tmp_path, mode, index_files)
            is_first_batch = False

        log_files = _build_log_files(dir_logs)
        if log_files:
            mode = "w" if is_first_batch else "a"
            await asyncio.to_thread(_write_zip_batch, tmp_path, mode, log_files)

        export_name = "knowledge-base"
        if folder_id is not None and folder_id in folder_path_map:
            export_name = _sanitize_filename(folder_path_map[folder_id].split("/")[0])

        return ExportResult(
            zip_path=tmp_path,
            export_name=export_name,
            zip_size=os.path.getsize(tmp_path),
            skipped_docs=skipped_docs,
        )

    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _memory_title(memory: Memory) -> str:
    """Stable memory title for index/log entries."""
    content = (memory.content or "").replace("\n", " ").strip()
    if not content:
        return "Memory"
    if len(content) <= 80:
        return content
    return content[:80].rstrip() + "..."
