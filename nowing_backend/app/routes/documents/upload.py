"""Document upload and folder indexing endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import (
    Document,
    DocumentStatus,
    DocumentType,
    Folder,
    Permission,
    get_async_session,
)
from app.etl_pipeline.etl_document import ProcessingMode
from app.file_storage.service import store_document_file
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.routes.documents._shared import (
    MAX_FILE_SIZE_BYTES,
    FolderMtimeCheckRequest,
)
from app.schemas import DocumentsCreate
from app.services.folder_service import MAX_FOLDER_DEPTH
from app.services.task_dispatcher import TaskDispatcher, get_task_dispatcher
from app.services.workspace_limits import workspace_limit_service
from app.tasks.celery_tasks.document_tasks import (
    index_uploaded_folder_files_task,
)
from app.tasks.document_processors.base import (
    check_document_by_unique_identifier,
    get_current_timestamp,
)
from app.users import get_auth_context
from app.utils.document_converters import generate_unique_identifier_hash
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/documents")
async def create_documents(
    request: DocumentsCreate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """
    Create new documents.
    Requires DOCUMENTS_CREATE permission.
    """
    try:
        # Check permission
        await check_permission(
            session,
            auth,
            request.workspace_id,
            Permission.DOCUMENTS_CREATE.value,
            "You don't have permission to create documents in this workspace",
        )

        # Enforce workspace document limit (best-effort for EXTENSION; Celery
        # creates the actual Document rows asynchronously).
        await workspace_limit_service.check_document_limit(
            session, request.workspace_id, additional=len(request.content)
        )

        if request.document_type == DocumentType.EXTENSION:
            from app.tasks.celery_tasks.document_tasks import (
                process_extension_document_task,
            )

            for individual_document in request.content:
                # Convert document to dict for Celery serialization
                document_dict = {
                    "metadata": {
                        "VisitedWebPageTitle": individual_document.metadata.VisitedWebPageTitle,
                        "VisitedWebPageURL": individual_document.metadata.VisitedWebPageURL,
                        "BrowsingSessionId": individual_document.metadata.BrowsingSessionId,
                        "VisitedWebPageDateWithTimeInISOString": individual_document.metadata.VisitedWebPageDateWithTimeInISOString,
                        "VisitedWebPageVisitDurationInMilliseconds": individual_document.metadata.VisitedWebPageVisitDurationInMilliseconds,
                        "VisitedWebPageReffererURL": individual_document.metadata.VisitedWebPageReffererURL,
                    },
                    "pageContent": individual_document.pageContent,
                }
                process_extension_document_task.delay(
                    document_dict, request.workspace_id, str(user.id)
                )
        else:
            raise HTTPException(status_code=400, detail="Invalid document type")

        await session.commit()
        return {
            "message": "Documents queued for background processing",
            "status": "queued",
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to process documents: {e!s}"
        ) from e


@router.post("/documents/fileupload")
async def create_documents_file_upload(
    files: list[UploadFile],
    workspace_id: int = Form(...),
    use_vision_llm: bool = Form(False),
    processing_mode: str = Form("basic"),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
    dispatcher: TaskDispatcher = Depends(get_task_dispatcher),
):
    user = auth.user
    """
    Upload files as documents with real-time status tracking.

    Implements 2-phase document status updates for real-time UI feedback:
    - Phase 1: Create all documents with 'pending' status (visible in UI immediately via Zero)
    - Phase 2: Celery processes each file: pending → processing → ready/failed

    Requires DOCUMENTS_CREATE permission.
    """
    import os

    from app.etl_pipeline.etl_document import ProcessingMode

    validated_mode = ProcessingMode.coerce(processing_mode)

    try:
        await check_permission(
            session,
            auth,
            workspace_id,
            Permission.DOCUMENTS_CREATE.value,
            "You don't have permission to create documents in this workspace",
        )

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        for file in files:
            file_size = file.size or 0
            if file_size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{file.filename}' ({file_size / (1024 * 1024):.1f} MB) "
                    f"exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per-file limit.",
                )

        # ===== Read all files concurrently to avoid blocking the event loop =====
        async def _read_and_save(file: UploadFile) -> tuple[str, str, int, str | None]:
            """Read upload content and write to temp file off the event loop."""
            content = await file.read()
            file_size = len(content)
            filename = file.filename or "unknown"
            content_type = file.content_type

            if file_size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{filename}' ({file_size / (1024 * 1024):.1f} MB) "
                    f"exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per-file limit.",
                )

            def _write_temp() -> str:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(filename)[1]
                ) as tmp:
                    tmp.write(content)
                    return tmp.name

            temp_path = await asyncio.to_thread(_write_temp)
            return temp_path, filename, file_size, content_type

        saved_files = await asyncio.gather(*(_read_and_save(f) for f in files))

        # ===== PHASE 1: Create pending documents for all files =====
        created_documents: list[Document] = []
        new_documents: list[Document] = []
        # (document, temp_path, filename, content_type)
        files_to_process: list[tuple[Document, str, str, str | None]] = []
        skipped_duplicates = 0
        duplicate_document_ids: list[int] = []
        new_document_count = 0

        for temp_path, filename, file_size, content_type in saved_files:
            try:
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.FILE, filename, workspace_id
                )

                existing = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )
                if existing:
                    if DocumentStatus.is_state(existing.status, DocumentStatus.READY):
                        os.unlink(temp_path)
                        skipped_duplicates += 1
                        duplicate_document_ids.append(existing.id)
                        continue

                    existing.status = DocumentStatus.pending()
                    existing.content = "Processing..."
                    existing.document_metadata = {
                        **(existing.document_metadata or {}),
                        "file_size": file_size,
                        "upload_time": datetime.now().isoformat(),
                    }
                    existing.updated_at = get_current_timestamp()
                    created_documents.append(existing)
                    files_to_process.append(
                        (existing, temp_path, filename, content_type)
                    )
                    continue

                document = Document(
                    workspace_id=workspace_id,
                    title=filename if filename != "unknown" else "Uploaded File",
                    document_type=DocumentType.FILE,
                    document_metadata={
                        "FILE_NAME": filename,
                        "file_size": file_size,
                        "upload_time": datetime.now().isoformat(),
                    },
                    content="Processing...",
                    content_hash=unique_identifier_hash,
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=None,
                    status=DocumentStatus.pending(),
                    updated_at=get_current_timestamp(),
                    created_by_id=str(user.id),
                )
                # Do not add to session until after the limit check; otherwise
                # AsyncSession autoflush would make count_documents see these
                # pending rows and double-count them with `additional`.
                new_document_count += 1
                created_documents.append(document)
                new_documents.append(document)
                files_to_process.append((document, temp_path, filename, content_type))

            except HTTPException:
                raise
            except (ValueError, TypeError, OSError, SQLAlchemyError) as e:
                os.unlink(temp_path)
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to process file {filename}: {e!s}",
                ) from e

        # Enforce workspace document limit before inserting pending rows.
        if new_document_count:
            await workspace_limit_service.check_document_limit(
                session, workspace_id, additional=new_document_count
            )

        # Now add the new document rows; they were held back from the session
        # until the limit check completed.
        session.add_all(new_documents)

        if created_documents:
            await session.commit()
            for doc in created_documents:
                await session.refresh(doc)

        # ===== PHASE 1.5: Persist the original uploads to durable storage =====
        # Best-effort: a storage failure must not block parsing or the response.
        for document, temp_path, filename, content_type in files_to_process:
            try:
                original_bytes = await asyncio.to_thread(
                    lambda p=temp_path: Path(p).read_bytes()
                )
                await store_document_file(
                    session,
                    document_id=document.id,
                    workspace_id=workspace_id,
                    data=original_bytes,
                    filename=filename,
                    mime_type=content_type,
                    created_by_id=str(user.id),
                )
            except (OSError, SQLAlchemyError, TypeError, ValueError) as storage_error:
                logger.warning(
                    "Failed to store original upload for document %s: %s",
                    document.id,
                    storage_error,
                )
        await session.commit()

        # ===== PHASE 2: Dispatch tasks for each file =====
        for document, temp_path, filename, _content_type in files_to_process:
            await dispatcher.dispatch_file_processing(
                document_id=document.id,
                temp_path=temp_path,
                filename=filename,
                workspace_id=workspace_id,
                user_id=str(user.id),
                use_vision_llm=use_vision_llm,
                processing_mode=validated_mode.value,
            )

        return {
            "message": "Files uploaded for processing",
            "document_ids": [doc.id for doc in created_documents],
            "duplicate_document_ids": duplicate_document_ids,
            "total_files": len(files),
            "pending_files": len(files_to_process),
            "skipped_duplicates": skipped_duplicates,
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to upload files: {e!s}"
        ) from e


@router.post("/documents/folder-mtime-check")
async def folder_mtime_check(
    request: FolderMtimeCheckRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Pre-upload optimization: check which files need uploading based on mtime.

    Returns the subset of relative paths where the file is new or has a
    different mtime, so the client can skip reading/uploading unchanged files.
    """

    await check_permission(
        session,
        auth,
        request.workspace_id,
        Permission.DOCUMENTS_CREATE.value,
        "You don't have permission to create documents in this workspace",
    )

    uid_hashes = {}
    for f in request.files:
        uid = f"{request.folder_name}:{f.relative_path}"
        uid_hash = compute_identifier_hash(
            DocumentType.LOCAL_FOLDER_FILE.value, uid, request.workspace_id
        )
        uid_hashes[uid_hash] = f

    existing_docs = (
        (
            await session.execute(
                select(Document).where(
                    Document.unique_identifier_hash.in_(list(uid_hashes.keys())),
                    Document.document_type == DocumentType.LOCAL_FOLDER_FILE,
                    Document.archived_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    existing_by_hash = {doc.unique_identifier_hash: doc for doc in existing_docs}

    mtime_tolerance = 1.0
    files_to_upload: list[str] = []

    for uid_hash, file_info in uid_hashes.items():
        doc = existing_by_hash.get(uid_hash)
        if doc is None:
            files_to_upload.append(file_info.relative_path)
            continue

        stored_mtime = (doc.document_metadata or {}).get("mtime")
        if stored_mtime is None:
            files_to_upload.append(file_info.relative_path)
            continue

        if abs(file_info.mtime - stored_mtime) >= mtime_tolerance:
            files_to_upload.append(file_info.relative_path)

    return {"files_to_upload": files_to_upload}


@router.post("/documents/folder-upload")
async def folder_upload(
    files: list[UploadFile],
    folder_name: str = Form(...),
    workspace_id: int = Form(...),
    relative_paths: str = Form(...),
    root_folder_id: int | None = Form(None),
    use_vision_llm: bool = Form(False),
    processing_mode: str = Form("basic"),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    """Upload files from the desktop app for folder indexing.

    Files are written to temp storage and dispatched to a Celery task.
    Works for all deployment modes (no is_self_hosted guard).
    """
    import tempfile


    validated_mode = ProcessingMode.coerce(processing_mode)

    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.DOCUMENTS_CREATE.value,
        "You don't have permission to create documents in this workspace",
    )

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        rel_paths: list[str] = json.loads(relative_paths)
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid relative_paths JSON: {e}"
        ) from e

    if len(rel_paths) != len(files):
        raise HTTPException(
            status_code=400,
            detail=f"Mismatch: {len(files)} files but {len(rel_paths)} relative_paths",
        )

    for file in files:
        file_size = file.size or 0
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' ({file_size / (1024 * 1024):.1f} MB) "
                f"exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB per-file limit.",
            )


    max_subfolder_depth = max((p.count("/") for p in rel_paths if "/" in p), default=0)
    if 1 + max_subfolder_depth > MAX_FOLDER_DEPTH:
        raise HTTPException(
            status_code=400,
            detail=f"Folder structure too deep: {1 + max_subfolder_depth} levels "
            f"exceeds the maximum of {MAX_FOLDER_DEPTH}.",
        )

    if root_folder_id:
        root_folder = await session.get(Folder, root_folder_id)
        if not root_folder or root_folder.workspace_id != workspace_id:
            raise HTTPException(
                status_code=404, detail="Root folder not found in this workspace"
            )

    if not root_folder_id:
        watched_metadata = {
            "watched": True,
            "folder_path": folder_name,
            "processing_mode": validated_mode.value,
        }
        existing_root = (
            await session.execute(
                select(Folder).where(
                    Folder.name == folder_name,
                    Folder.parent_id.is_(None),
                    Folder.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()

        if existing_root:
            root_folder_id = existing_root.id
            existing_root.folder_metadata = watched_metadata
        else:
            root_folder = Folder(
                name=folder_name,
                workspace_id=workspace_id,
                created_by_id=str(user.id),
                position="a0",
                folder_metadata=watched_metadata,
            )
            session.add(root_folder)
            await session.flush()
            root_folder_id = root_folder.id

        await session.commit()

    async def _read_and_save(file: UploadFile, idx: int) -> dict:
        content = await file.read()
        raw_name = file.filename or rel_paths[idx]
        filename = raw_name.split("/")[-1]

        def _write_temp() -> str:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(filename)[1]
            ) as tmp:
                tmp.write(content)
                return tmp.name

        temp_path = await asyncio.to_thread(_write_temp)
        return {
            "temp_path": temp_path,
            "relative_path": rel_paths[idx],
            "filename": filename,
        }

    file_mappings = await asyncio.gather(
        *(_read_and_save(f, i) for i, f in enumerate(files))
    )


    index_uploaded_folder_files_task.delay(
        workspace_id=workspace_id,
        user_id=str(user.id),
        folder_name=folder_name,
        root_folder_id=root_folder_id,
        use_vision_llm=use_vision_llm,
        file_mappings=list(file_mappings),
        processing_mode=validated_mode.value,
    )

    return {
        "message": f"Folder upload started for {len(files)} file(s)",
        "status": "processing",
        "root_folder_id": root_folder_id,
        "file_count": len(files),
    }


