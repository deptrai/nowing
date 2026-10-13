"""Celery background task for periodic synthetic DNS probes (Story 31 / Retro Item 29).

Periodically evaluates all active custom domains in the workspace_apps table,
verifying TXT proof-of-ownership and CNAME ingress target.
Dispatches in-app, Telegram, and AdminHealthAlerts on failure with cooldown deduplication.
"""

from __future__ import annotations

import logging
from typing import Any

from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


async def _run_dns_probe_cycle() -> dict[str, Any]:
    """Execute synthetic DNS probe across all active custom domains asynchronously."""
    from app.services.dns.synthetic_probe_service import SyntheticDnsProbeService

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        service = SyntheticDnsProbeService(session=session)
        summary = await service.probe_all_active_custom_domains()
        logger.info(
            "DNS synthetic probe finished: %d scanned, %d healthy, %d unhealthy, %d alerts dispatched",
            summary["scanned"],
            summary["healthy"],
            summary["unhealthy"],
            summary["alerts_dispatched"],
        )
        return summary


@celery_app.task(
    name="dns_synthetic_probe_periodic",
    bind=True,
    default_retry_delay=120,
    max_retries=2,
)
def dns_synthetic_probe_periodic_task(self) -> dict[str, Any]:
    """Periodic Celery task running the DNS synthetic probe cycle."""
    try:
        return run_async_celery_task(_run_dns_probe_cycle)
    except Exception as exc:
        logger.error("Periodic DNS synthetic probe failed: %s", exc)
        raise self.retry(exc=exc) from exc
