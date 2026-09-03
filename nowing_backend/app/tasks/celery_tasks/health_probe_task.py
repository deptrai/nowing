"""Celery background tasks for periodic third-party health probes."""

from __future__ import annotations

import logging
from typing import Any

from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)


async def _run_health_probe_for_category(category: str) -> dict[str, Any]:
    """Execute category probes asynchronously using a dedicated celery DB session."""
    from app.services.health.scheduler import HealthProbeScheduler

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        try:
            results = await HealthProbeScheduler.run_category(category, session=session)
            return {
                "category": category,
                "count": len(results),
                "healthy": sum(1 for r in results if r.status == "healthy"),
                "degraded": sum(1 for r in results if r.status == "degraded"),
                "unavailable": sum(1 for r in results if r.status == "unavailable"),
            }
        except Exception as exc:
            logger.error("Error running health probe for category %s: %s", category, exc)
            return {"category": category, "error": str(exc)}


@celery_app.task(name="health_probe_infra")
def health_probe_infra() -> dict[str, Any]:
    """Periodic probe for core infrastructure (30s)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("infra"))


@celery_app.task(name="health_probe_model")
def health_probe_model() -> dict[str, Any]:
    """Periodic probe for LLM / AI models (2m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("model"))


@celery_app.task(name="health_probe_scraper")
def health_probe_scraper() -> dict[str, Any]:
    """Periodic probe for platform scrapers (5m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("scraper"))


@celery_app.task(name="health_probe_connector")
def health_probe_connector() -> dict[str, Any]:
    """Periodic probe for SaaS connectors (15m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("connector"))


@celery_app.task(name="health_probe_proxy")
def health_probe_proxy() -> dict[str, Any]:
    """Periodic probe for proxy / anti-bot egress (5m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("proxy"))


@celery_app.task(name="health_probe_research")
def health_probe_research() -> dict[str, Any]:
    """Periodic probe for ChainLens research engine (5m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("research"))

@celery_app.task(name="health_probe_messaging")
def health_probe_messaging() -> dict[str, Any]:
    """Periodic probe for messaging gateways (5m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("messaging"))


@celery_app.task(name="health_probe_payment")
def health_probe_payment() -> dict[str, Any]:
    """Periodic probe for payment gateways (5m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("payment"))


@celery_app.task(name="health_probe_storage")
def health_probe_storage() -> dict[str, Any]:
    """Periodic probe for object storage (5m)."""
    return run_async_celery_task(lambda: _run_health_probe_for_category("storage"))

