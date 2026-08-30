"""Local folder indexing entry points and helpers."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus, DocumentType, Folder
from app.indexing_pipeline.document_hashing import (
    compute_identifier_hash,
    compute_unique_identifier_hash,
)
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.services.etl_credit_service import EtlCreditService, InsufficientCreditsError
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import (
    check_document_by_unique_identifier,
)
from app.tasks.connector_indexers.local_folder.constants import (
    BATCH_CONCURRENCY,
    DEFAULT_EXCLUDE_PATTERNS,
    UPLOAD_BATCH_CONCURRENCY,
    HeartbeatCallbackType,
)
from app.tasks.connector_indexers.local_folder.credits import (
    _check_credits_or_skip,
    _compute_final_pages,
)
from app.tasks.connector_indexers.local_folder.document import _build_connector_doc
from app.tasks.connector_indexers.local_folder.filesystem import (
    _compute_file_content_hash,
    _compute_raw_file_hash,
    scan_folder,
)
from app.tasks.connector_indexers.local_folder.folders import (
    _cleanup_empty_folder_chain,
    _cleanup_empty_folders,
    _clear_indexing_flag,
    _mirror_folder_structure,
    _mirror_folder_structure_from_paths,
    _resolve_folder_for_file,
    _set_indexing_flag,
)
from app.utils.document_versioning import create_version_snapshot

logger = logging.getLogger(__name__)


def _get_session_maker() -> Any:
    """Return the Celery session maker used by batch mode."""
    from app.tasks.celery_tasks import get_celery_session_maker

    return get_celery_session_maker


async def index_local_folder(
    session: AsyncSession,
    workspace_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    exclude_patterns: list[str] | None = None,
    file_extensions: list[str] | None = None,
    root_folder_id: int | None = None,
    target_file_paths: list[str] | None = None,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    get_session_maker: Any = None,
    batch_concurrency: int = BATCH_CONCURRENCY,
) -> tuple[int, int, int | None, str | None]:
    """Index files from a local folder.

    Supports two modes:
    - Batch (target_file_paths set): processes 1..N files.
      Single-file uses the caller's session; multi-file fans out with per-file sessions.
    - Full scan (no target paths): walks entire folder, handles new/changed/deleted files.

    Returns (indexed_count, skipped_count, root_folder_id, error_or_warning_message).
    """
    task_logger = TaskLoggingService(session, workspace_id)

    log_entry = await task_logger.log_task_start(
        task_name="local_folder_indexing",
        source="local_folder_indexing_task",
        message=f"Starting local folder indexing for {folder_name}",
        metadata={
            "folder_path": folder_path,
            "user_id": str(user_id),
            "target_file_paths_count": len(target_file_paths)
            if target_file_paths
            else None,
        },
    )

    try:
        if not folder_path or not os.path.exists(folder_path):
            await task_logger.log_task_failure(
                log_entry,
                f"Folder path missing or does not exist: {folder_path}",
                "Folder not found",
                {},
            )
            return (
                0,
                0,
                root_folder_id,
                f"Folder path missing or does not exist: {folder_path}",
            )

        if exclude_patterns is None:
            exclude_patterns = DEFAULT_EXCLUDE_PATTERNS

        # ====================================================================
        # BATCH MODE (1..N files)
        # ====================================================================
        if target_file_paths:
            if root_folder_id:
                await _set_indexing_flag(session, root_folder_id)
            try:
                if len(target_file_paths) == 1:
                    indexed, skipped, err = await _index_single_file(
                        session=session,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        folder_path=folder_path,
                        folder_name=folder_name,
                        target_file_path=target_file_paths[0],
                        root_folder_id=root_folder_id,
                        task_logger=task_logger,
                        log_entry=log_entry,
                    )
                    return indexed, skipped, root_folder_id, err

                indexed, failed, err = await _index_batch_files(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    folder_path=folder_path,
                    folder_name=folder_name,
                    target_file_paths=target_file_paths,
                    root_folder_id=root_folder_id,
                    on_progress_callback=on_heartbeat_callback,
                    get_session_maker=get_session_maker,
                    batch_concurrency=batch_concurrency,
                )
                if err:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Batch indexing: {indexed} indexed, {failed} failed",
                        {"indexed": indexed, "failed": failed},
                    )
                else:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Batch indexing complete: {indexed} indexed",
                        {"indexed": indexed, "failed": failed},
                    )
                return indexed, failed, root_folder_id, err
            finally:
                if root_folder_id:
                    await _clear_indexing_flag(session, root_folder_id)

        # ====================================================================
        # FULL-SCAN MODE
        # ====================================================================

        await task_logger.log_task_progress(
            log_entry, "Mirroring folder structure", {"stage": "folder_mirror"}
        )

        folder_mapping, root_folder_id = await _mirror_folder_structure(
            session=session,
            folder_path=folder_path,
            folder_name=folder_name,
            workspace_id=workspace_id,
            user_id=user_id,
            root_folder_id=root_folder_id,
            exclude_patterns=exclude_patterns,
        )
        await session.flush()
        await _set_indexing_flag(session, root_folder_id)

        try:
            files = scan_folder(folder_path, file_extensions, exclude_patterns)
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry, f"Failed to scan folder: {e}", "Scan error", {}
            )
            await _clear_indexing_flag(session, root_folder_id)
            return 0, 0, root_folder_id, f"Failed to scan folder: {e}"

        logger.info(f"Found {len(files)} files in folder")

        indexed_count = 0
        skipped_count = 0
        failed_count = 0

        etl_credit_service = EtlCreditService(session)

        # ================================================================
        # PHASE 1: Pre-filter files (mtime / content-hash), version changed
        # ================================================================
        connector_docs: list[Any] = []
        file_meta_map: dict[str, dict] = {}
        seen_unique_hashes: set[str] = set()

        for file_info in files:
            try:
                relative_path = file_info["relative_path"]
                file_path_abs = file_info["path"]

                unique_identifier = f"{folder_name}:{relative_path}"
                unique_identifier_hash = compute_identifier_hash(
                    DocumentType.LOCAL_FOLDER_FILE.value,
                    unique_identifier,
                    workspace_id,
                )
                seen_unique_hashes.add(unique_identifier_hash)

                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    stored_mtime = (existing_document.document_metadata or {}).get(
                        "mtime"
                    )
                    current_mtime = file_info["modified_at"].timestamp()

                    if stored_mtime and abs(current_mtime - stored_mtime) < 1.0:
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        skipped_count += 1
                        continue

                    raw_hash = await asyncio.to_thread(
                        _compute_raw_file_hash, file_path_abs
                    )

                    stored_raw_hash = (existing_document.document_metadata or {}).get(
                        "raw_file_hash"
                    )
                    if stored_raw_hash and stored_raw_hash == raw_hash:
                        meta = dict(existing_document.document_metadata or {})
                        meta["mtime"] = current_mtime
                        existing_document.document_metadata = meta
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        skipped_count += 1
                        continue

                    try:
                        estimated_pages, _billable = await _check_credits_or_skip(
                            etl_credit_service, user_id, file_path_abs
                        )
                    except InsufficientCreditsError:
                        logger.warning(
                            f"Insufficient credits, skipping: {file_path_abs}"
                        )
                        failed_count += 1
                        continue

                    try:
                        content, content_hash = await _compute_file_content_hash(
                            file_path_abs,
                            file_info["relative_path"],
                            workspace_id,
                        )
                    except Exception as read_err:
                        logger.warning(f"Could not read {file_path_abs}: {read_err}")
                        skipped_count += 1
                        continue

                    if existing_document.content_hash == content_hash:
                        meta = dict(existing_document.document_metadata or {})
                        meta["mtime"] = current_mtime
                        meta["raw_file_hash"] = raw_hash
                        existing_document.document_metadata = meta
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        skipped_count += 1
                        continue

                    await create_version_snapshot(session, existing_document)
                else:
                    try:
                        estimated_pages, _billable = await _check_credits_or_skip(
                            etl_credit_service, user_id, file_path_abs
                        )
                    except InsufficientCreditsError:
                        logger.warning(
                            f"Insufficient credits, skipping: {file_path_abs}"
                        )
                        failed_count += 1
                        continue

                    try:
                        content, content_hash = await _compute_file_content_hash(
                            file_path_abs,
                            file_info["relative_path"],
                            workspace_id,
                        )
                    except Exception as read_err:
                        logger.warning(f"Could not read {file_path_abs}: {read_err}")
                        skipped_count += 1
                        continue

                    if not content.strip():
                        skipped_count += 1
                        continue

                    raw_hash = await asyncio.to_thread(
                        _compute_raw_file_hash, file_path_abs
                    )

                doc = _build_connector_doc(
                    title=file_info["name"],
                    content=content,
                    relative_path=relative_path,
                    folder_name=folder_name,
                    workspace_id=workspace_id,
                    user_id=user_id,
                )
                connector_docs.append(doc)
                file_meta_map[unique_identifier] = {
                    "relative_path": relative_path,
                    "mtime": file_info["modified_at"].timestamp(),
                    "estimated_pages": estimated_pages,
                    "content_length": len(content),
                    "raw_file_hash": raw_hash,
                }

            except Exception as e:
                logger.exception(f"Phase 1 error for {file_info.get('path')}: {e}")
                failed_count += 1

        # ================================================================
        # PHASE 1.5: Delete documents no longer on disk
        # ================================================================
        all_root_folder_ids = set(folder_mapping.values())
        all_db_folders = (
            (
                await session.execute(
                    select(Folder.id).where(
                        Folder.workspace_id == workspace_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        all_root_folder_ids.update(all_db_folders)

        all_folder_docs = (
            (
                await session.execute(
                    select(Document).where(
                        Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                        Document.workspace_id == workspace_id,
                        Document.folder_id.in_(list(all_root_folder_ids)),
                    )
                )
            )
            .scalars()
            .all()
        )

        for doc in all_folder_docs:
            if doc.unique_identifier_hash not in seen_unique_hashes:
                await session.delete(doc)

        await session.flush()

        # ================================================================
        # PHASE 2: Index via unified pipeline
        # ================================================================
        if connector_docs:
            pipeline = IndexingPipelineService(session)
            doc_map = {compute_unique_identifier_hash(cd): cd for cd in connector_docs}

            for cd in connector_docs:
                rel_path = (cd.metadata or {}).get("file_path", "")
                parent_dir = str(Path(rel_path).parent) if rel_path else ""
                if parent_dir == ".":
                    parent_dir = ""
                cd.folder_id = folder_mapping.get(parent_dir, folder_mapping.get(""))

            documents = await pipeline.prepare_for_indexing(connector_docs)

            for document in documents:
                connector_doc = doc_map.get(document.unique_identifier_hash)
                if connector_doc is None:
                    failed_count += 1
                    continue

                result = await pipeline.index(document, connector_doc)

                if DocumentStatus.is_state(result.status, DocumentStatus.READY):
                    indexed_count += 1

                    unique_id = connector_doc.unique_id
                    mtime_info = file_meta_map.get(unique_id, {})

                    doc_meta = dict(result.document_metadata or {})
                    doc_meta["mtime"] = mtime_info.get("mtime")
                    doc_meta["raw_file_hash"] = mtime_info.get("raw_file_hash")
                    result.document_metadata = doc_meta

                    est = mtime_info.get("estimated_pages", 1)
                    content_len = mtime_info.get("content_length", 0)
                    final_pages = _compute_final_pages(
                        etl_credit_service, est, content_len
                    )
                    await etl_credit_service.charge_credits(user_id, final_pages)
                else:
                    failed_count += 1

                if on_heartbeat_callback and indexed_count % 5 == 0:
                    await on_heartbeat_callback(indexed_count)

        # Cleanup empty folders
        existing_dirs = set()
        for dirpath, dirnames, _ in os.walk(folder_path):
            dirnames[:] = [d for d in dirnames if d not in exclude_patterns]
            rel = str(Path(dirpath).relative_to(folder_path))
            if rel == ".":
                rel = ""
            if rel and not any(part in exclude_patterns for part in Path(rel).parts):
                existing_dirs.add(rel)

        root_fid = folder_mapping.get("")
        if root_fid:
            from app.services.folder_service import get_folder_subtree_ids

            subtree_ids = await get_folder_subtree_ids(session, root_fid)
            await _cleanup_empty_folders(
                session,
                root_fid,
                workspace_id,
                existing_dirs,
                folder_mapping,
                subtree_ids=subtree_ids,
            )

        try:
            await session.commit()
        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e).lower():
                logger.warning(f"Duplicate key during commit: {e}")
                await session.rollback()
            else:
                raise

        warning_parts = []
        if failed_count > 0:
            warning_parts.append(f"{failed_count} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        await task_logger.log_task_success(
            log_entry,
            f"Completed local folder indexing for {folder_name}",
            {
                "indexed": indexed_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
        )

        await _clear_indexing_flag(session, root_folder_id)
        return indexed_count, skipped_count, root_folder_id, warning_message

    except SQLAlchemyError as e:
        logger.exception(f"Database error during local folder indexing: {e}")
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry, f"DB error: {e}", "Database error", {}
        )
        if root_folder_id:
            await _clear_indexing_flag(session, root_folder_id)
        return 0, 0, root_folder_id, f"Database error: {e}"

    except Exception as e:
        logger.exception(f"Error during local folder indexing: {e}")
        await task_logger.log_task_failure(
            log_entry, f"Error: {e}", "Unexpected error", {}
        )
        if root_folder_id:
            await _clear_indexing_flag(session, root_folder_id)
        return 0, 0, root_folder_id, str(e)


async def _index_batch_files(
    workspace_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    target_file_paths: list[str],
    root_folder_id: int | None,
    on_progress_callback: HeartbeatCallbackType | None = None,
    get_session_maker: Any = None,
    batch_concurrency: int = BATCH_CONCURRENCY,
) -> tuple[int, int, str | None]:
    """Process multiple files in parallel with bounded concurrency.

    Each file gets its own DB session so they can run concurrently.
    Returns (indexed_count, failed_count, error_summary_or_none).
    """
    if get_session_maker is None:
        get_session_maker = _get_session_maker()

    semaphore = asyncio.Semaphore(batch_concurrency)
    indexed = 0
    failed = 0
    errors: list[str] = []
    lock = asyncio.Lock()
    completed = 0

    async def process_one(file_path: str) -> None:
        nonlocal indexed, failed, completed
        async with semaphore:
            try:
                async with get_session_maker()() as file_session:
                    task_logger = TaskLoggingService(file_session, workspace_id)
                    log_entry = await task_logger.log_task_start(
                        task_name="local_folder_indexing",
                        source="local_folder_batch_indexing",
                        message=f"Batch: indexing {Path(file_path).name}",
                        metadata={"file_path": file_path},
                    )
                    ix, _sk, err = await _index_single_file(
                        session=file_session,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        folder_path=folder_path,
                        folder_name=folder_name,
                        target_file_path=file_path,
                        root_folder_id=root_folder_id,
                        task_logger=task_logger,
                        log_entry=log_entry,
                    )
                    async with lock:
                        indexed += ix
                        if err:
                            failed += 1
                            errors.append(f"{Path(file_path).name}: {err}")
                        completed += 1
                        if on_progress_callback and completed % batch_concurrency == 0:
                            await on_progress_callback(completed)
            except Exception as exc:
                logger.exception(f"Batch: error processing {file_path}: {exc}")
                async with lock:
                    failed += 1
                    completed += 1
                    errors.append(f"{Path(file_path).name}: {exc}")

    await asyncio.gather(*[process_one(fp) for fp in target_file_paths])

    if on_progress_callback:
        await on_progress_callback(completed)

    error_summary = None
    if errors:
        error_summary = f"{failed} file(s) failed: " + "; ".join(errors[:5])
        if len(errors) > 5:
            error_summary += f" ... and {len(errors) - 5} more"

    return indexed, failed, error_summary


async def _index_single_file(
    session: AsyncSession,
    workspace_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    target_file_path: str,
    root_folder_id: int | None,
    task_logger,
    log_entry,
) -> tuple[int, int, str | None]:
    """Process a single file (chokidar real-time trigger)."""
    try:
        full_path = Path(target_file_path)
        if not full_path.exists():
            rel = str(full_path.relative_to(folder_path))
            unique_id = f"{folder_name}:{rel}"
            uid_hash = compute_identifier_hash(
                DocumentType.LOCAL_FOLDER_FILE.value, unique_id, workspace_id
            )
            existing = await check_document_by_unique_identifier(session, uid_hash)
            if existing:
                deleted_folder_id = existing.folder_id
                await session.delete(existing)
                await session.flush()
                if deleted_folder_id and root_folder_id:
                    await _cleanup_empty_folder_chain(
                        session, deleted_folder_id, root_folder_id
                    )
                await session.commit()
                return 0, 0, None
            return 0, 0, None

        rel_path = str(full_path.relative_to(folder_path))

        unique_id = f"{folder_name}:{rel_path}"
        uid_hash = compute_identifier_hash(
            DocumentType.LOCAL_FOLDER_FILE.value, unique_id, workspace_id
        )

        raw_hash = await asyncio.to_thread(_compute_raw_file_hash, str(full_path))

        existing = await check_document_by_unique_identifier(session, uid_hash)

        if existing:
            stored_raw_hash = (existing.document_metadata or {}).get("raw_file_hash")
            if stored_raw_hash and stored_raw_hash == raw_hash:
                mtime = full_path.stat().st_mtime
                meta = dict(existing.document_metadata or {})
                meta["mtime"] = mtime
                existing.document_metadata = meta
                if not DocumentStatus.is_state(existing.status, DocumentStatus.READY):
                    existing.status = DocumentStatus.ready()
                await session.commit()
                return 0, 0, None

        etl_credit_service = EtlCreditService(session)
        try:
            estimated_pages, _billable = await _check_credits_or_skip(
                etl_credit_service, user_id, str(full_path)
            )
        except InsufficientCreditsError as e:
            return 0, 1, f"Insufficient credits: {e}"

        try:
            content, content_hash = await _compute_file_content_hash(
                str(full_path), full_path.name, workspace_id
            )
        except Exception as e:
            return 0, 1, f"Could not read file: {e}"

        if not content.strip():
            return 0, 1, None

        if existing:
            if existing.content_hash == content_hash:
                mtime = full_path.stat().st_mtime
                meta = dict(existing.document_metadata or {})
                meta["mtime"] = mtime
                meta["raw_file_hash"] = raw_hash
                existing.document_metadata = meta
                await session.commit()
                return 0, 1, None

            await create_version_snapshot(session, existing)

        mtime = full_path.stat().st_mtime

        connector_doc = _build_connector_doc(
            title=full_path.name,
            content=content,
            relative_path=rel_path,
            folder_name=folder_name,
            workspace_id=workspace_id,
            user_id=user_id,
        )

        if root_folder_id:
            connector_doc.folder_id = await _resolve_folder_for_file(
                session, rel_path, root_folder_id, workspace_id, user_id
            )

        pipeline = IndexingPipelineService(session)
        documents = await pipeline.prepare_for_indexing([connector_doc])

        if not documents:
            return 0, 1, None

        db_doc = documents[0]

        await pipeline.index(db_doc, connector_doc)

        await session.refresh(db_doc)
        doc_meta = dict(db_doc.document_metadata or {})
        doc_meta["mtime"] = mtime
        doc_meta["raw_file_hash"] = raw_hash
        db_doc.document_metadata = doc_meta
        await session.commit()

        indexed = (
            1 if DocumentStatus.is_state(db_doc.status, DocumentStatus.READY) else 0
        )
        failed_msg = None if indexed else "Indexing failed"

        if indexed:
            final_pages = _compute_final_pages(
                etl_credit_service, estimated_pages, len(content)
            )
            await etl_credit_service.charge_credits(user_id, final_pages)
            await task_logger.log_task_success(
                log_entry,
                f"Single file indexed: {rel_path}",
                {"file": rel_path, "pages_processed": final_pages},
            )
        return indexed, 0 if indexed else 1, failed_msg

    except Exception as e:
        logger.exception(f"Error indexing single file {target_file_path}: {e}")
        await session.rollback()
        return 0, 0, str(e)


async def index_uploaded_files(
    session: AsyncSession,
    workspace_id: int,
    user_id: str,
    folder_name: str,
    root_folder_id: int,
    file_mappings: list[dict],
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    use_vision_llm: bool = False,
    processing_mode: str = "basic",
    upload_batch_concurrency: int = UPLOAD_BATCH_CONCURRENCY,
) -> tuple[int, int, str | None]:
    """Index files uploaded from the desktop app via temp paths.

    Each entry in *file_mappings* is ``{temp_path, relative_path, filename}``.
    This function mirrors the folder structure from the provided relative
    paths, then indexes each file exactly like ``_index_single_file`` but
    reads from the temp path.  Temp files are cleaned up after processing.

    Returns ``(indexed_count, failed_count, error_summary_or_none)``.
    """
    from app.etl_pipeline.etl_document import ProcessingMode

    mode = ProcessingMode.coerce(processing_mode)

    task_logger = TaskLoggingService(session, workspace_id)
    log_entry = await task_logger.log_task_start(
        task_name="local_folder_indexing",
        source="uploaded_folder_indexing",
        message=f"Indexing {len(file_mappings)} uploaded file(s) for {folder_name}",
        metadata={"file_count": len(file_mappings), "processing_mode": mode.value},
    )

    try:
        all_relative_paths = [m["relative_path"] for m in file_mappings]
        _folder_mapping, root_folder_id = await _mirror_folder_structure_from_paths(
            session=session,
            relative_paths=all_relative_paths,
            folder_name=folder_name,
            workspace_id=workspace_id,
            user_id=user_id,
            root_folder_id=root_folder_id,
        )
        await session.flush()

        await _set_indexing_flag(session, root_folder_id)

        etl_credit_service = EtlCreditService(session)

        vision_llm_instance = None
        if use_vision_llm:
            from app.services.llm_service import get_vision_llm

            vision_llm_instance = await get_vision_llm(session, workspace_id)

        indexed_count = 0
        failed_count = 0
        errors: list[str] = []

        for i, mapping in enumerate(file_mappings):
            temp_path = mapping["temp_path"]
            relative_path = mapping["relative_path"]
            filename = mapping["filename"]

            try:
                unique_id = f"{folder_name}:{relative_path}"
                uid_hash = compute_identifier_hash(
                    DocumentType.LOCAL_FOLDER_FILE.value,
                    unique_id,
                    workspace_id,
                )

                raw_hash = await asyncio.to_thread(_compute_raw_file_hash, temp_path)

                existing = await check_document_by_unique_identifier(session, uid_hash)

                if existing:
                    stored_raw_hash = (existing.document_metadata or {}).get(
                        "raw_file_hash"
                    )
                    if stored_raw_hash and stored_raw_hash == raw_hash:
                        meta = dict(existing.document_metadata or {})
                        meta["mtime"] = datetime.now(UTC).timestamp()
                        existing.document_metadata = meta
                        if not DocumentStatus.is_state(
                            existing.status, DocumentStatus.READY
                        ):
                            existing.status = DocumentStatus.ready()
                        await session.commit()
                        continue

                try:
                    estimated_pages, _billable_pages = await _check_credits_or_skip(
                        etl_credit_service,
                        user_id,
                        temp_path,
                        page_multiplier=mode.page_multiplier,
                    )
                except InsufficientCreditsError:
                    logger.warning(f"Insufficient credits, skipping: {relative_path}")
                    failed_count += 1
                    continue

                try:
                    content, content_hash = await _compute_file_content_hash(
                        temp_path,
                        filename,
                        workspace_id,
                        vision_llm=vision_llm_instance,
                        processing_mode=mode.value,
                    )
                except Exception as e:
                    logger.warning(f"Could not read {relative_path}: {e}")
                    failed_count += 1
                    errors.append(f"{filename}: {e}")
                    continue

                if not content.strip():
                    failed_count += 1
                    continue

                if existing:
                    if existing.content_hash == content_hash:
                        meta = dict(existing.document_metadata or {})
                        meta["mtime"] = datetime.now(UTC).timestamp()
                        meta["raw_file_hash"] = raw_hash
                        existing.document_metadata = meta
                        if not DocumentStatus.is_state(
                            existing.status, DocumentStatus.READY
                        ):
                            existing.status = DocumentStatus.ready()
                        await session.commit()
                        continue

                    await create_version_snapshot(session, existing)

                connector_doc = _build_connector_doc(
                    title=filename,
                    content=content,
                    relative_path=relative_path,
                    folder_name=folder_name,
                    workspace_id=workspace_id,
                    user_id=user_id,
                )

                connector_doc.folder_id = await _resolve_folder_for_file(
                    session,
                    relative_path,
                    root_folder_id,
                    workspace_id,
                    user_id,
                )

                pipeline = IndexingPipelineService(session)
                documents = await pipeline.prepare_for_indexing([connector_doc])
                if not documents:
                    failed_count += 1
                    continue

                db_doc = documents[0]

                await pipeline.index(db_doc, connector_doc)

                await session.refresh(db_doc)
                doc_meta = dict(db_doc.document_metadata or {})
                doc_meta["mtime"] = datetime.now(UTC).timestamp()
                doc_meta["raw_file_hash"] = raw_hash
                db_doc.document_metadata = doc_meta
                await session.commit()

                if DocumentStatus.is_state(db_doc.status, DocumentStatus.READY):
                    indexed_count += 1
                    final_pages = _compute_final_pages(
                        etl_credit_service, estimated_pages, len(content)
                    )
                    final_billable = final_pages * mode.page_multiplier
                    await etl_credit_service.charge_credits(user_id, final_billable)
                else:
                    failed_count += 1

                if on_heartbeat_callback and (i + 1) % 5 == 0:
                    await on_heartbeat_callback(i + 1)

            except Exception as e:
                logger.exception(f"Error indexing uploaded file {relative_path}: {e}")
                await session.rollback()
                failed_count += 1
                errors.append(f"{filename}: {e}")
            finally:
                with contextlib.suppress(OSError):
                    os.unlink(temp_path)

        error_summary = None
        if errors:
            error_summary = f"{failed_count} file(s) failed: " + "; ".join(errors[:5])
            if len(errors) > 5:
                error_summary += f" ... and {len(errors) - 5} more"

        await task_logger.log_task_success(
            log_entry,
            f"Upload indexing complete: {indexed_count} indexed, {failed_count} failed",
            {"indexed": indexed_count, "failed": failed_count},
        )

        return indexed_count, failed_count, error_summary

    except SQLAlchemyError as e:
        logger.exception(f"Database error during uploaded file indexing: {e}")
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry, f"DB error: {e}", "Database error", {}
        )
        return 0, 0, f"Database error: {e}"

    except Exception as e:
        logger.exception(f"Error during uploaded file indexing: {e}")
        await task_logger.log_task_failure(
            log_entry, f"Error: {e}", "Unexpected error", {}
        )
        return 0, 0, str(e)

    finally:
        await _clear_indexing_flag(session, root_folder_id)
