"""Parallel Google Drive download / ETL and batch indexing helpers."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.db import DocumentType
from app.indexing_pipeline.exceptions import safe_exception_message
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.tasks.connector_indexers.base import mark_connector_documents_failed
from app.tasks.connector_indexers.google_drive.constants import (
    HEARTBEAT_INTERVAL_SECONDS,
    HeartbeatCallbackType,
)

logger = logging.getLogger(__name__)

BuildDocFn = Callable[..., Any]


async def _download_files_parallel_core(
    drive_client: Any,
    files: list[dict],
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    extract_fn: Callable[..., Awaitable[tuple[str | None, dict[str, Any] | None, str | None]]],
    build_connector_doc_fn: BuildDocFn,
    max_concurrency: int = 3,
    on_heartbeat: HeartbeatCallbackType | None = None,
    vision_llm: Any | None = None,
    heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
) -> tuple[list[Any], list[tuple[str, str]]]:
    """Download and ETL files in parallel.

    Returns (connector_docs, failed_files), where failed_files is a list of
    (file_id, reason) so callers can mark those placeholders failed.
    """
    results: list[Any] = []
    sem = asyncio.Semaphore(max_concurrency)
    last_heartbeat = time.time()
    completed_count = 0
    hb_lock = asyncio.Lock()

    async def _download_one(file: dict) -> Any | str:
        nonlocal last_heartbeat, completed_count
        async with sem:
            markdown, drive_metadata, error = await extract_fn(
                drive_client, file, vision_llm=vision_llm
            )
            if error or not markdown:
                file_name = file.get("name", "Unknown")
                reason = error or "empty content"
                logger.warning(f"Download/ETL failed for {file_name}: {reason}")
                return f"Download/ETL failed: {reason}"
            doc = build_connector_doc_fn(
                file,
                markdown,
                drive_metadata or {},
                connector_id=connector_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            async with hb_lock:
                completed_count += 1
                if on_heartbeat:
                    now = time.time()
                    if now - last_heartbeat >= heartbeat_interval:
                        await on_heartbeat(completed_count)
                        last_heartbeat = now
            return doc

    tasks = [_download_one(f) for f in files]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    failed_files: list[tuple[str, str]] = []
    for file, outcome in zip(files, outcomes, strict=False):
        if outcome.__class__.__name__ == "ConnectorDocument":
            results.append(outcome)
            continue
        file_id = file.get("id")
        if isinstance(outcome, Exception):
            reason = f"Download/ETL error: {safe_exception_message(outcome)}"
            logger.warning(
                "Download/ETL exception for %s: %s",
                file.get("name", "Unknown"),
                outcome,
                exc_info=outcome,
            )
        elif isinstance(outcome, str):
            reason = outcome
        else:
            reason = "Download or extraction failed"
        if file_id:
            failed_files.append((file_id, reason))

    return results, failed_files


async def _download_and_index_core(
    drive_client: Any,
    session: Any,
    files: list[dict],
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    download_files_parallel_fn: Any,
    on_heartbeat: HeartbeatCallbackType | None = None,
    extract_fn: Any | None = None,
    vision_llm: Any | None = None,
    pipeline_cls: Any = IndexingPipelineService,
) -> tuple[int, int]:
    """Phase 2+3: parallel download then parallel indexing.

    Returns (batch_indexed, total_failed).
    """
    connector_docs, failed_files = await download_files_parallel_fn(
        drive_client,
        files,
        connector_id=connector_id,
        workspace_id=workspace_id,
        user_id=user_id,
        on_heartbeat=on_heartbeat,
        extract_fn=extract_fn,
        vision_llm=vision_llm,
    )

    # Fail the placeholders for files whose download/ETL failed, so they don't
    # stay stuck in 'pending'.
    if failed_files:
        await mark_connector_documents_failed(
            session,
            document_type=DocumentType.GOOGLE_DRIVE_FILE,
            workspace_id=workspace_id,
            failures=failed_files,
        )

    batch_indexed = 0
    batch_failed = 0
    if connector_docs:
        pipeline = pipeline_cls(session)
        _, batch_indexed, batch_failed = await pipeline.index_batch_parallel(
            connector_docs,
            max_concurrency=3,
            on_heartbeat=on_heartbeat,
        )

    return batch_indexed, len(failed_files) + batch_failed
