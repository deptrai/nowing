"""Celery worker task for batch lead exports (Story 21.13, AC-5)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.lark_base import LarkBaseConnector
from app.db import ExportJob, Lead, get_async_session_context
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)


async def _async_lead_export(
    export_job_id: str,
    workspace_id: int,
    export_type: str,
    lead_ids: list[str],
    mask_pii: bool,
    target_config: dict[str, Any],
) -> dict[str, Any]:
    """Execute lead export asynchronously in chunks of 500 rows."""
    sync_id = f"nowing-export-{export_job_id}"
    export_service = ExportService()

    async with get_async_session_context() as session:
        job = await session.get(ExportJob, UUID(export_job_id))
        if not job:
            logger.error("Export job %s not found", export_job_id)
            return {"status": "error", "error": "Job not found"}

        # Fetch leads
        stmt = (
            select(Lead)
            .where(
                Lead.workspace_id == workspace_id,
                Lead.id.in_([UUID(lid) for lid in lead_ids]),
            )
            .options(selectinload(Lead.verified_contacts))
        )
        result = await session.execute(stmt)
        leads = result.scalars().all()

        job.total_rows = len(leads)
        job.status = "processing"
        await session.commit()

        target_url = None

        try:
            if export_type == "lark_base":
                app_token = target_config.get("app_token", "")
                table_id = target_config.get("table_id", "")
                access_token = target_config.get("access_token", "")

                records = export_service.prepare_lark_records(leads, mask_pii=mask_pii)
                connector = LarkBaseConnector(tenant_access_token=access_token)
                res = await connector.batch_create_records(
                    app_token=app_token,
                    table_id=table_id,
                    records=records,
                    sync_id=sync_id,
                    chunk_size=500,
                )
                target_url = res.get("app_url")
                job.processed_rows = res.get("created_count", len(leads))

            elif export_type == "google_sheets":
                spreadsheet_id = target_config.get("spreadsheet_id", "")
                sheet_range = target_config.get("sheet_range", "Sheet1!A1")
                access_token = target_config.get("access_token", "")

                rows = export_service.prepare_google_sheets_rows(
                    leads, mask_pii=mask_pii
                )
                connector = GoogleSheetsConnector(access_token=access_token)
                res = await connector.append_rows(
                    spreadsheet_id=spreadsheet_id,
                    sheet_range=sheet_range,
                    values=rows,
                    sync_id=sync_id,
                    chunk_size=500,
                )
                target_url = res.get("spreadsheet_url")
                job.processed_rows = len(leads)

            elif export_type == "share_link":
                target_url = f"/shared/leads/{export_job_id}"
                job.processed_rows = len(leads)

            job.status = "completed"
            job.target_url = target_url
            await session.commit()

            return {
                "status": "completed",
                "export_job_id": export_job_id,
                "target_url": target_url,
                "processed_rows": job.processed_rows,
            }

        except Exception as e:
            logger.exception("Error executing export job %s: %s", export_job_id, e)
            job.status = "failed"
            job.error_message = str(e)
            await session.commit()
            raise


@celery_app.task(name="run_lead_export_task", bind=True, max_retries=3)
def run_lead_export_task(
    self,
    export_job_id: str,
    workspace_id: int,
    export_type: str,
    lead_ids: list[str],
    mask_pii: bool = True,
    target_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Celery task entrypoint."""
    try:
        return asyncio.run(
            _async_lead_export(
                export_job_id=export_job_id,
                workspace_id=workspace_id,
                export_type=export_type,
                lead_ids=lead_ids,
                mask_pii=mask_pii,
                target_config=target_config or {},
            )
        )
    except Exception as exc:
        logger.warning("Retrying export task %s due to %s", export_job_id, exc)
        raise self.retry(exc=exc, countdown=10) from exc
