"""Celery task for importing ChainLens Webset leads (Story 41.1)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.celery_app import celery_app
from app.services.websets_import import WebsetsImportService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.webset_import.import_webset_leads",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def import_webset_leads(self: Any, webset_id: str) -> dict[str, Any]:
    """Celery worker task that drains and ingests leads from an idle Webset."""
    logger.info("Executing import_webset_leads task for webset_id=%s", webset_id)
    service = WebsetsImportService()
    try:
        return asyncio.run(service.import_webset(webset_id))
    except Exception as exc:
        logger.exception(
            "import_webset_leads failed for webset_id=%s, retrying: %s",
            webset_id,
            exc,
        )
        raise self.retry(exc=exc, countdown=10 * (2**self.request.retries)) from exc
