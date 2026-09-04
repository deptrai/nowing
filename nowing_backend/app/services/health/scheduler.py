"""Scheduler for executing category probes concurrently with concurrency throttling."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.services.health.alert_engine import AdminHealthAlertEngine
from app.services.health.probe_base import HealthProbe, HealthResult
from app.services.health.registry import HealthProbeRegistry
from app.services.health.result_store import HealthResultStore

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Max concurrent probes across a batch
CONCURRENCY_LIMIT = 20

# Per-probe timeout to prevent hung connections from holding a semaphore slot
PROBE_TIMEOUT_SECONDS = 60


class HealthProbeScheduler:
    """Orchestrates periodic and on-demand probe execution with bounded concurrency."""

    @classmethod
    async def run_category(
        cls,
        category: str,
        session: AsyncSession | None = None,
    ) -> list[HealthResult]:
        """Run all probes for a category, bounded by semaphore."""
        await HealthProbeRegistry.ensure_initialized()
        probes = HealthProbeRegistry.get_probes(category=category if category != "all" else None)
        if not probes:
            logger.info("No probes registered for category '%s'", category)
            return []

        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

        async def _run_single_probe(probe: HealthProbe) -> HealthResult:
            async with semaphore:
                try:
                    result = await asyncio.wait_for(probe.probe(), timeout=PROBE_TIMEOUT_SECONDS)
                    result.interval_seconds = probe.interval_seconds
                    result.next_probe_at = result.probed_at + timedelta(seconds=probe.interval_seconds)
                    return result
                except asyncio.TimeoutError:
                    logger.error("Probe timeout for %s after %ss", probe.service_id, PROBE_TIMEOUT_SECONDS)
                    return HealthResult(
                        service_id=probe.service_id,
                        service_name=probe.service_name,
                        category=probe.category,
                        display_group=probe.display_group,
                        status="unavailable",
                        latency_ms=0,
                        last_error=f"Probe timed out after {PROBE_TIMEOUT_SECONDS}s",
                        suggested_action="Investigate probe logs and verify connection credentials",
                        error_rate_15m=100.0,
                        success_rate_15m=0.0,
                        metadata={},
                        probed_at=datetime.now(UTC),
                        interval_seconds=probe.interval_seconds,
                        next_probe_at=datetime.now(UTC) + timedelta(seconds=probe.interval_seconds),
                    )
                except Exception as exc:
                    logger.error("Unhandled error probing %s: %s", probe.service_id, exc)

                    safe_err = f"Probe execution error: {type(exc).__name__}"
                    return HealthResult(
                        service_id=probe.service_id,
                        service_name=probe.service_name,
                        category=probe.category,
                        display_group=probe.display_group,
                        status="unavailable",
                        latency_ms=0,
                        last_error=safe_err,
                        suggested_action="Investigate probe logs and verify connection credentials",
                        error_rate_15m=100.0,
                        success_rate_15m=0.0,
                        metadata={},
                        probed_at=datetime.now(UTC),
                        interval_seconds=probe.interval_seconds,
                        next_probe_at=datetime.now(UTC) + timedelta(seconds=probe.interval_seconds),
                    )

        # Run probes with semaphore throttling
        results = await asyncio.gather(*[_run_single_probe(p) for p in probes])

        # Persist and evaluate alerts
        if session is not None:
            await cls._persist_and_alert(session, results)
        else:
            async with async_session_maker() as new_session:
                await cls._persist_and_alert(new_session, results)

        return results

    @classmethod
    async def run_single(
        cls,
        service_id: str,
        session: AsyncSession | None = None,
    ) -> HealthResult | None:
        """Run a single probe on-demand by service ID."""
        probe = HealthProbeRegistry.get_probe(service_id)
        if not probe:
            logger.warning("Probe not found for service_id '%s'", service_id)
            return None

        try:
            result = await asyncio.wait_for(probe.probe(), timeout=PROBE_TIMEOUT_SECONDS)
            result.interval_seconds = probe.interval_seconds
            result.next_probe_at = result.probed_at + timedelta(seconds=probe.interval_seconds)
        except asyncio.TimeoutError:
            logger.error("Probe timeout for %s after %ss", service_id, PROBE_TIMEOUT_SECONDS)
            result = HealthResult(
                service_id=probe.service_id,
                service_name=probe.service_name,
                category=probe.category,
                display_group=probe.display_group,
                status="unavailable",
                latency_ms=0,
                last_error=f"Probe timed out after {PROBE_TIMEOUT_SECONDS}s",
                suggested_action="Investigate probe logs and verify connection credentials",
                error_rate_15m=100.0,
                success_rate_15m=0.0,
                metadata={},
                probed_at=datetime.now(UTC),
                interval_seconds=probe.interval_seconds,
                next_probe_at=datetime.now(UTC) + timedelta(seconds=probe.interval_seconds),
            )
        except Exception as exc:
            logger.error("Probe error for %s: %s", service_id, exc)

            safe_err = f"Probe execution error: {type(exc).__name__}"
            result = HealthResult(
                service_id=probe.service_id,
                service_name=probe.service_name,
                category=probe.category,
                display_group=probe.display_group,
                status="unavailable",
                latency_ms=0,
                last_error=safe_err,
                suggested_action="Investigate probe logs and verify connection credentials",
                error_rate_15m=100.0,
                success_rate_15m=0.0,
                metadata={},
                probed_at=datetime.now(UTC),
                interval_seconds=probe.interval_seconds,
                next_probe_at=datetime.now(UTC) + timedelta(seconds=probe.interval_seconds),
            )

        if session is not None:
            await cls._persist_and_alert(session, [result])
        else:
            async with async_session_maker() as new_session:
                await cls._persist_and_alert(new_session, [result])

        return result

    @classmethod
    async def _persist_and_alert(
        cls,
        session: AsyncSession,
        results: list[HealthResult],
    ) -> None:
        """Persist probe results and evaluate alert engine rules.

        Failures for individual results are isolated: the batch continues so one
        misbehaving probe does not abort the entire scheduler run.
        """
        for res in results:
            try:
                await HealthResultStore.save_result(session, res)
                await AdminHealthAlertEngine.evaluate_result(session, res)
            except Exception as exc:
                logger.error("Failed to store/alert result for %s: %s", res.service_id, exc)
                try:
                    await session.rollback()
                except Exception as rb_exc:
                    logger.warning("Rollback error on %s: %s", res.service_id, rb_exc)
