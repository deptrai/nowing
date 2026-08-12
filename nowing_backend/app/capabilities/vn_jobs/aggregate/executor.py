"""``vn_jobs.aggregate`` executor."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.capabilities.core import Executor
from app.services.chainlens.ingest import NowingIngestService
from app.services.jobs_aggregator import aggregate_jobs
from app.services.scraper_chunks.serializer import to_chunks

from .schemas import VnJobAggregateInput, VnJobAggregateOutput

logger = logging.getLogger(__name__)


def _build_vn_jobs_chunks(items: list[Any], fetched_at: str) -> list[Any]:
    """Convert aggregated job listings into ChainLens ``Chunk[]``.

    Failures for individual listings are swallowed so that one bad record
    does not block the rest of the batch (same behavior as chainlens route).
    """
    chunks: list[Any] = []
    for item in items:
        try:
            chunks.extend(
                to_chunks(
                    domain="vn_jobs",
                    data=item,
                    fetched_at=fetched_at,
                    content_type="text/markdown",
                    category=None,
                )
            )
        except Exception:
            logger.exception("Skipping unserializable job listing")
    return chunks


async def _ingest_vn_jobs_output(
    output: VnJobAggregateOutput,
    workspace_id: int,
    session: Any,
    correlation_id: str | None = None,
) -> None:
    """Ingest aggregated listings to chainlens-research and attach job ids."""
    if not output.items:
        output.ingest_status = "noop"
        return

    fetched_at = datetime.now(UTC).isoformat()
    chunks = _build_vn_jobs_chunks(output.items, fetched_at)
    if not chunks:
        output.ingest_status = "no_chunks"
        return

    result = await NowingIngestService().ingest(
        scraper_id="vn_jobs.aggregate",
        chunks=chunks,
        workspace_id=workspace_id,
        session=session,
        correlation_id=correlation_id,
    )

    output.ingest_job_id = result.ingest_job_id or result.parent_ingest_job_id
    output.ingest_status = result.status
    output.ingested_count = len(result.ingested_source_ids or [])
    output.noop_count = len(result.noop_source_ids or [])


def build_aggregate_executor() -> Executor:
    """Return an executor for the multi-source job aggregator."""

    async def execute(input: VnJobAggregateInput, ctx: Any) -> VnJobAggregateOutput:
        output = await aggregate_jobs(input, ctx)

        # AC-6: ingest the aggregated listings into chainlens-research and
        # expose the resulting job id on the output for REST/MCP/chat callers.
        if output.items:
            session = getattr(ctx, "session", None)
            workspace_id = getattr(ctx, "workspace_id", None)
            correlation_id = getattr(ctx, "run_id", None)
            if session is not None and workspace_id is not None:
                try:
                    await _ingest_vn_jobs_output(
                        output, workspace_id, session, correlation_id
                    )
                except Exception:
                    logger.exception("vn_jobs.aggregate ingest failed")
                    output.ingest_status = "failed"
            else:
                output.ingest_status = "no_session"

        return output

    return execute
