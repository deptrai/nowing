"""Google Drive full folder scan and delta sync scan strategies."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.etl_credit_service import EtlCreditService

logger = logging.getLogger(__name__)

SkipFn = Callable[[Any, dict, int], Awaitable[tuple[bool, str | None]]]
GetFilesFn = Callable[..., Awaitable[tuple[list[dict], str | None, str | None]]]
FetchChangesFn = Callable[..., Awaitable[tuple[list[dict], str | None, str | None]]]
CategorizeFn = Callable[[dict], str]
RemoveDocumentFn = Callable[[Any, str, int], Awaitable[None]]
CreatePlaceholdersFn = Callable[..., Awaitable[None]]
DownloadAndIndexFn = Callable[..., Awaitable[tuple[int, int]]]


def _authenticate_error_message(error: str) -> bool:
    err_lower = error.lower()
    return (
        "401" in error
        or "invalid credentials" in err_lower
        or "authError" in error
    )


async def _index_full_scan_core(
    drive_client: Any,
    session: Any,
    connector: object,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    folder_id: str | None,
    folder_name: str,
    task_logger: Any,
    log_entry: object,
    max_files: int,
    *,
    skip_fn: SkipFn,
    get_files_fn: GetFilesFn,
    create_placeholders_fn: CreatePlaceholdersFn,
    download_and_index_fn: DownloadAndIndexFn,
    include_subfolders: bool = False,
    on_heartbeat_callback: Any | None = None,
    vision_llm: Any | None = None,
) -> tuple[int, int, int]:
    """Full scan indexing of a folder.

    Returns (indexed, skipped, unsupported_count).
    """
    await task_logger.log_task_progress(
        log_entry,
        f"Starting full scan of folder: {folder_name} (include_subfolders={include_subfolders})",
        {
            "stage": "full_scan",
            "folder_id": folder_id,
            "include_subfolders": include_subfolders,
        },
    )

    # ------------------------------------------------------------------
    # Phase 1 (serial): collect files, run skip checks, track renames
    # ------------------------------------------------------------------
    etl_credit_service = EtlCreditService(session)
    available_micros = await etl_credit_service.get_available_micros(user_id)
    batch_estimated_pages = 0
    page_limit_reached = False

    renamed_count = 0
    skipped = 0
    unsupported_count = 0
    files_processed = 0
    files_to_download: list[dict] = []
    folders_to_process = [(folder_id, folder_name)]
    first_error: str | None = None

    while folders_to_process and files_processed < max_files:
        cur_id, cur_name = folders_to_process.pop(0)
        page_token = None

        while files_processed < max_files:
            files, next_token, error = await get_files_fn(
                drive_client,
                cur_id,
                include_subfolders=True,
                page_token=page_token,
            )
            if error:
                logger.error(f"Error listing files in {cur_name}: {error}")
                if first_error is None:
                    first_error = error
                break
            if not files:
                break

            for file in files:
                if files_processed >= max_files:
                    break

                mime = file.get("mimeType", "")
                if mime == "application/vnd.google-apps.folder":
                    if include_subfolders:
                        folders_to_process.append(
                            (file["id"], file.get("name", "Unknown"))
                        )
                    continue

                files_processed += 1

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
                    and EtlCreditService.pages_to_micros(
                        batch_estimated_pages + file_pages
                    )
                    > available_micros
                ):
                    if not page_limit_reached:
                        logger.warning(
                            "Insufficient credits during Google Drive full scan, "
                            "skipping remaining files"
                        )
                        page_limit_reached = True
                    skipped += 1
                    continue

                batch_estimated_pages += file_pages
                files_to_download.append(file)

            page_token = next_token
            if not page_token:
                break

    if not files_processed and first_error:
        if _authenticate_error_message(first_error):
            raise Exception(
                f"Google Drive authentication failed. Please re-authenticate. (Error: {first_error})"
            )
        raise Exception(f"Failed to list Google Drive files: {first_error}")

    # ------------------------------------------------------------------
    # Phase 1.5: create placeholders for instant UI feedback
    # ------------------------------------------------------------------
    await create_placeholders_fn(
        session,
        files_to_download,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    # ------------------------------------------------------------------
    # Phase 2+3 (parallel): download, ETL, index
    # ------------------------------------------------------------------
    batch_indexed, failed = await download_and_index_fn(
        drive_client,
        session,
        files_to_download,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        on_heartbeat=on_heartbeat_callback,
        vision_llm=vision_llm,
    )

    if batch_indexed > 0 and files_to_download and batch_estimated_pages > 0:
        pages_to_deduct = max(
            1, batch_estimated_pages * batch_indexed // len(files_to_download)
        )
        await etl_credit_service.charge_credits(user_id, pages_to_deduct)

    indexed = renamed_count + batch_indexed
    logger.info(
        f"Full scan complete: {indexed} indexed, {skipped} skipped, "
        f"{unsupported_count} unsupported, {failed} failed"
    )
    return indexed, skipped, unsupported_count


async def _index_with_delta_sync_core(
    drive_client: Any,
    session: Any,
    connector: object,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    folder_id: str | None,
    start_page_token: str,
    task_logger: Any,
    log_entry: object,
    max_files: int,
    *,
    skip_fn: SkipFn,
    fetch_changes_fn: FetchChangesFn,
    categorize_fn: CategorizeFn,
    remove_document_fn: RemoveDocumentFn,
    create_placeholders_fn: CreatePlaceholdersFn,
    download_and_index_fn: DownloadAndIndexFn,
    include_subfolders: bool = False,
    on_heartbeat_callback: Any | None = None,
    vision_llm: Any | None = None,
) -> tuple[int, int, int]:
    """Delta sync using change tracking.

    Returns (indexed, skipped, unsupported_count).
    """
    await task_logger.log_task_progress(
        log_entry,
        f"Starting delta sync from token: {start_page_token[:20]}...",
        {"stage": "delta_sync", "start_token": start_page_token},
    )

    changes, _final_token, error = await fetch_changes_fn(
        drive_client, start_page_token, folder_id
    )
    if error:
        if _authenticate_error_message(error):
            raise Exception(
                f"Google Drive authentication failed. Please re-authenticate. (Error: {error})"
            )
        raise Exception(f"Failed to fetch Google Drive changes: {error}")

    if not changes:
        logger.info("No changes detected since last sync")
        return 0, 0, 0

    logger.info(f"Processing {len(changes)} changes")

    # ------------------------------------------------------------------
    # Phase 1 (serial): handle removals, collect files for download
    # ------------------------------------------------------------------
    etl_credit_service = EtlCreditService(session)
    available_micros = await etl_credit_service.get_available_micros(user_id)
    batch_estimated_pages = 0
    page_limit_reached = False

    renamed_count = 0
    skipped = 0
    unsupported_count = 0
    files_to_download: list[dict] = []
    files_processed = 0

    for change in changes:
        if files_processed >= max_files:
            break
        files_processed += 1
        change_type = categorize_fn(change)

        if change_type in ["removed", "trashed"]:
            fid = change.get("fileId")
            if fid:
                await remove_document_fn(session, fid, workspace_id)
            continue

        file = change.get("file")
        if not file:
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
            if not page_limit_reached:
                logger.warning(
                    "Insufficient credits during Google Drive delta sync, "
                    "skipping remaining files"
                )
                page_limit_reached = True
            skipped += 1
            continue

        batch_estimated_pages += file_pages
        files_to_download.append(file)

    # ------------------------------------------------------------------
    # Phase 1.5: create placeholders for instant UI feedback
    # ------------------------------------------------------------------
    await create_placeholders_fn(
        session,
        files_to_download,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    # ------------------------------------------------------------------
    # Phase 2+3 (parallel): download, ETL, index
    # ------------------------------------------------------------------
    batch_indexed, failed = await download_and_index_fn(
        drive_client,
        session,
        files_to_download,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        on_heartbeat=on_heartbeat_callback,
        vision_llm=vision_llm,
    )

    if batch_indexed > 0 and files_to_download and batch_estimated_pages > 0:
        pages_to_deduct = max(
            1, batch_estimated_pages * batch_indexed // len(files_to_download)
        )
        await etl_credit_service.charge_credits(user_id, pages_to_deduct)

    indexed = renamed_count + batch_indexed
    logger.info(
        f"Delta sync complete: {indexed} indexed, {skipped} skipped, "
        f"{unsupported_count} unsupported, {failed} failed"
    )
    return indexed, skipped, unsupported_count
