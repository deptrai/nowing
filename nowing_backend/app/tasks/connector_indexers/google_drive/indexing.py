"""Google Drive single-file and user-selected file indexing."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.db import DocumentType
from app.indexing_pipeline.document_hashing import compute_unique_identifier_hash
from app.services.etl_credit_service import EtlCreditService
from app.tasks.connector_indexers.google_drive.document import (
    _build_connector_doc,
)

logger = logging.getLogger(__name__)

SkipFn = Callable[[Any, dict, int], Awaitable[tuple[bool, str | None]]]
GetFileFn = Callable[[Any, str], Awaitable[tuple[dict | None, str | None]]]
DownloadAndIndexFn = Callable[..., Awaitable[tuple[int, int]]]


async def _process_single_file_core(
    drive_client: Any,
    session: Any,
    file: dict,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    *,
    skip_fn: SkipFn,
    extract_fn: Any,
    pipeline_cls: Any,
    mark_failed_fn: Any,
    vision_llm: Any | None = None,
) -> tuple[int, int, int]:
    """Download, extract, and index a single Drive file via the pipeline.

    Returns (indexed, skipped, failed).
    """
    file_name = file.get("name", "Unknown")

    try:
        skip, msg = await skip_fn(session, file, workspace_id)
        if skip:
            if msg and "renamed" in msg.lower():
                return 1, 0, 0
            return 0, 1, 0

        etl_credit_service = EtlCreditService(session)
        estimated_pages = EtlCreditService.estimate_pages_from_metadata(
            file_name, file.get("size")
        )
        await etl_credit_service.check_credits(user_id, estimated_pages)

        markdown, drive_metadata, error = await extract_fn(
            drive_client, file, vision_llm=vision_llm
        )
        if error or not markdown:
            reason = error or "empty content"
            logger.warning(f"ETL failed for {file_name}: {reason}")
            file_id = file.get("id")
            if file_id:
                await mark_failed_fn(
                    session,
                    document_type=DocumentType.GOOGLE_DRIVE_FILE,
                    workspace_id=workspace_id,
                    failures=[(file_id, f"Download/ETL failed: {reason}")],
                )
            return 0, 1, 0

        doc = _build_connector_doc(
            file,
            markdown,
            drive_metadata or {},
            connector_id=connector_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )

        pipeline = pipeline_cls(session)
        documents = await pipeline.prepare_for_indexing([doc])
        if not documents:
            return 0, 1, 0

        doc_map = {compute_unique_identifier_hash(doc): doc}
        for document in documents:
            connector_doc = doc_map.get(document.unique_identifier_hash)
            if not connector_doc:
                continue
            await pipeline.index(document, connector_doc)

        await etl_credit_service.charge_credits(user_id, estimated_pages)
        logger.info(f"Successfully indexed Google Drive file: {file_name}")
        return 1, 0, 0

    except Exception as e:
        logger.error(f"Error processing file {file_name}: {e!s}", exc_info=True)
        return 0, 0, 1


async def _index_selected_files_core(
    drive_client: Any,
    session: Any,
    file_ids: list[tuple[str, str | None]],
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    get_file_fn: GetFileFn,
    skip_fn: SkipFn,
    download_and_index_fn: DownloadAndIndexFn,
    create_placeholders_fn: Any,
    on_heartbeat: Any | None = None,
    extract_fn: Any | None = None,
    vision_llm: Any | None = None,
) -> tuple[int, int, int, list[str]]:
    """Index user-selected files using the parallel pipeline.

    Phase 1 (serial): fetch metadata + skip checks.
    Phase 2+3 (parallel): download, ETL, index via _download_and_index.

    Returns (indexed_count, skipped_count, unsupported_count, errors).
    """
    etl_credit_service = EtlCreditService(session)
    available_micros = await etl_credit_service.get_available_micros(user_id)
    batch_estimated_pages = 0

    files_to_download: list[dict] = []
    errors: list[str] = []
    renamed_count = 0
    skipped = 0
    unsupported_count = 0

    for file_id, file_name in file_ids:
        file, error = await get_file_fn(drive_client, file_id)
        if error or not file:
            display = file_name or file_id
            errors.append(f"File '{display}': {error or 'File not found'}")
            continue

        skip, msg = await skip_fn(session, file, workspace_id)
        if skip:
            if msg and msg.startswith("unsupported:"):
                unsupported_count += 1
            elif msg and "renamed" in msg.lower():
                renamed_count += 1
            else:
                skipped += 1
            continue

        file_pages = EtlCreditService.estimate_pages_from_metadata(
            file.get("name", ""), file.get("size")
        )
        if (
            available_micros is not None
            and EtlCreditService.pages_to_micros(batch_estimated_pages + file_pages)
            > available_micros
        ):
            display = file_name or file_id
            errors.append(f"File '{display}': insufficient credits")
            continue

        batch_estimated_pages += file_pages
        files_to_download.append(file)

    await create_placeholders_fn(
        session,
        files_to_download,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    batch_indexed, _failed = await download_and_index_fn(
        drive_client,
        session,
        files_to_download,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        on_heartbeat=on_heartbeat,
        extract_fn=extract_fn,
        vision_llm=vision_llm,
    )

    if batch_indexed > 0 and files_to_download and batch_estimated_pages > 0:
        pages_to_deduct = max(
            1, batch_estimated_pages * batch_indexed // len(files_to_download)
        )
        await etl_credit_service.charge_credits(user_id, pages_to_deduct)

    return renamed_count + batch_indexed, skipped, unsupported_count, errors
