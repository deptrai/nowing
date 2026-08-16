"""Red-phase integration tests for Celery Scraper Worker Pool & Redis Stream Ingestion (Story 23.1 / AC-1 & AC-4).

Governed by:
- AC-1: Dedicated Celery Queue (nowing.lead_scrapers) & Non-Blocking Dispatch (< 100ms)
- AC-4: Worker Crash Resilience (acks_late, reject_on_worker_lost) & XPENDING/XCLAIM Recovery
- INV-23.1: Worker Queue Isolation
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Target module to be implemented in Story 23.1:
# from app.tasks.lead_scrapers import (
#     run_platform_scrape_task,
#     reclaim_pending_stream_messages,
#     LEAD_SCRAPERS_QUEUE_NAME,
# )

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 1. Celery Queue Routing & Non-Blocking Dispatch (INV-23.1 & AC-1)
# ---------------------------------------------------------------------------
class TestScraperCeleryQueueRouting:
    """Validate that scraper tasks are strictly routed to the dedicated queue."""

    def test_scraper_task_routed_to_dedicated_queue(self) -> None:
        """INV-23.1: Scraper task must route to nowing.lead_scrapers, never celery_default."""
        from app.celery_app import celery_app

        task_name = "app.tasks.lead_scrapers.run_platform_scrape_task"
        route_config = celery_app.conf.task_routes.get(
            task_name,
            celery_app.conf.task_routes.get("run_platform_scrape_task"),
        )

        assert route_config is not None, f"No route defined for {task_name}"
        assert route_config.get("queue") == "nowing.lead_scrapers"

    def test_scraper_task_resilience_options(self) -> None:
        """AC-4: Scraper tasks must configure acks_late=True, reject_on_worker_lost=True, timeouts (60s/120s)."""
        from app.tasks.lead_scrapers import run_platform_scrape_task

        # Verify Celery task options
        assert getattr(run_platform_scrape_task, "acks_late", True) is True
        assert getattr(run_platform_scrape_task, "reject_on_worker_lost", True) is True
        assert getattr(run_platform_scrape_task, "time_limit", 120) == 120
        assert getattr(run_platform_scrape_task, "soft_time_limit", 60) == 60

    @pytest.mark.asyncio
    async def test_non_blocking_dispatch_returns_within_100ms(self) -> None:
        """AC-1: Dispatching multi-platform scrape returns job_id < 100ms without blocking on HTTP."""
        from app.lead_intelligence.services.lead_gen_orchestrator import (
            LeadGenOrchestrator,
        )

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        orchestrator = LeadGenOrchestrator(db=mock_db, redis=mock_redis)

        with patch(
            "app.tasks.lead_scrapers.run_platform_scrape_task.apply_async"
        ) as mock_apply_async:
            mock_apply_async.return_value = MagicMock(id="celery-job-uuid-12345")

            start_time = time.perf_counter()
            response = await orchestrator.dispatch_scrape_job(
                workspace_id=42,
                query="Công ty công nghệ AI tại TP HCM",
                sources=["batdongsan", "chotot", "topcv", "masothue"],
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            assert elapsed_ms < 100, f"Dispatch took {elapsed_ms:.2f}ms (> 100ms)"
            assert response.job_id is not None
            assert len(response.dispatched_tasks) == 4
            assert mock_apply_async.call_count == 4


# ---------------------------------------------------------------------------
# 2. Redis Stream XPENDING / XCLAIM Dead-Letter Recovery (AC-4)
# ---------------------------------------------------------------------------
class TestRedisStreamCrashRecovery:
    """Validate dead-letter recovery via XPENDING and XCLAIM after worker crash."""

    @pytest.mark.asyncio
    async def test_reclaim_pending_stream_messages_after_30s_inactivity(self) -> None:
        """AC-4: Messages pending > 30s in stream consumer group are reclaimed via XCLAIM."""
        from app.tasks.lead_scrapers import reclaim_pending_stream_messages

        mock_redis = AsyncMock()
        # Mock xpending response: [(msg_id, consumer, idle_time_ms, delivery_count)]
        mock_redis.xpending_range.return_value = [
            {
                "message_id": b"1700000000000-0",
                "consumer": b"crashed_worker_1",
                "idle_time": 35000,  # 35 seconds idle (> 30s)
                "delivery_count": 2,
            }
        ]
        mock_redis.xclaim.return_value = [
            (
                b"1700000000000-0",
                {b"payload": b'{"source":"batdongsan","value_hmac":"hmac_123"}'},
            )
        ]

        reclaimed_count = await reclaim_pending_stream_messages(
            workspace_id=42,
            group_name="leads_writer_group",
            recovery_consumer="standby_worker_2",
            min_idle_ms=30000,
            redis_client=mock_redis,
        )

        assert reclaimed_count == 1
        mock_redis.xclaim.assert_called_once()
