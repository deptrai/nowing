"""Red-phase unit tests for Redis Stream Transit Buffer and Dual-Trigger Flush Window (Story 23.1 / AC-2).

Governed by:
- AC-2: Redis Stream Transit Buffer & Dual-Trigger Flush Window
- INV-23.2: Bounded Redis Streams (MAXLEN ~ 10000)
- Architecture Spine: architecture-epic23-lead-infrastructure.md
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

# Target module to be implemented in Story 23.1:
# from app.lead_intelligence.services.lead_stream_service import (
#     LeadStreamBuffer,
#     LeadRecordPayload,
#     FLUSH_BATCH_SIZE,
#     FLUSH_TIME_WINDOW_SECONDS,
#     REDIS_STREAM_MAXLEN,
# )

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. LeadStreamBuffer Dual-Trigger Flush Logic (AC-2)
# ---------------------------------------------------------------------------
class TestLeadStreamBufferDualTrigger:
    """Validate that LeadStreamBuffer flushes on either 5+ items OR 3.0s timeout."""

    @pytest.mark.asyncio
    async def test_buffer_flushes_immediately_when_five_leads_accumulate(self) -> None:
        """AC-2 Trigger 1: Accumulating 5 leads triggers immediate flush to Redis Stream."""
        from app.lead_intelligence.services.lead_stream_service import (
            LeadStreamBuffer,
        )

        mock_redis = AsyncMock()
        buffer = LeadStreamBuffer(workspace_id=42, redis_client=mock_redis)

        # Add 4 leads -> should not flush yet
        for i in range(4):
            flushed = await buffer.add_lead(
                {
                    "source": "batdongsan",
                    "client_id": f"bds_{i}",
                    "value_hmac": f"hmac_{i}",
                    "company_name": f"BDS Company {i}",
                    "fit_score": 0.85,
                }
            )
            assert flushed is False
            assert buffer.get_buffered_count() == i + 1

        mock_redis.xadd.assert_not_called()

        # Add 5th lead -> triggers batch size flush
        flushed_on_5th = await buffer.add_lead(
            {
                "source": "batdongsan",
                "client_id": "bds_4",
                "value_hmac": "hmac_4",
                "company_name": "BDS Company 4",
                "fit_score": 0.90,
            }
        )
        assert flushed_on_5th is True
        assert buffer.get_buffered_count() == 0
        assert mock_redis.xadd.call_count == 5

    @pytest.mark.asyncio
    async def test_buffer_flushes_on_time_window_trigger(self) -> None:
        """AC-2 Trigger 2: When 3.0 seconds elapse with >= 1 lead, flush is triggered."""
        from app.lead_intelligence.services.lead_stream_service import (
            LeadStreamBuffer,
        )

        mock_redis = AsyncMock()
        buffer = LeadStreamBuffer(
            workspace_id=42,
            redis_client=mock_redis,
            flush_time_seconds=3.0,
        )

        # Add 2 leads (below batch size of 5)
        await buffer.add_lead(
            {
                "source": "chotot",
                "client_id": "ct_1",
                "value_hmac": "hmac_ct1",
            }
        )
        await buffer.add_lead(
            {
                "source": "chotot",
                "client_id": "ct_2",
                "value_hmac": "hmac_ct2",
            }
        )
        assert buffer.get_buffered_count() == 2

        # Check before timeout -> should not flush
        should_flush_early = buffer.should_flush_by_timeout(current_time=time.time())
        assert should_flush_early is False

        # Simulate 3.1 seconds later
        future_time = time.time() + 3.1
        should_flush_timeout = buffer.should_flush_by_timeout(current_time=future_time)
        assert should_flush_timeout is True

        # Perform timed flush
        flushed_count = await buffer.flush_if_due(current_time=future_time)
        assert flushed_count == 2
        assert buffer.get_buffered_count() == 0
        assert mock_redis.xadd.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_buffer_does_not_flush_on_timeout(self) -> None:
        """AC-2: Empty buffer does not perform XADD even if time window elapses."""
        from app.lead_intelligence.services.lead_stream_service import (
            LeadStreamBuffer,
        )

        mock_redis = AsyncMock()
        buffer = LeadStreamBuffer(workspace_id=42, redis_client=mock_redis)

        future_time = time.time() + 10.0
        assert buffer.should_flush_by_timeout(current_time=future_time) is False

        flushed_count = await buffer.flush_if_due(current_time=future_time)
        assert flushed_count == 0
        mock_redis.xadd.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Redis Stream Bounded Size & Trimming (INV-23.2)
# ---------------------------------------------------------------------------
class TestRedisStreamBoundedTrimming:
    """Validate INV-23.2: Every XADD strictly enforces MAXLEN ~ 10000."""

    @pytest.mark.asyncio
    async def test_xadd_enforces_approximate_maxlen_10000(self) -> None:
        """INV-23.2: xadd call must specify maxlen=10000 with approximate=True."""
        from app.lead_intelligence.services.lead_stream_service import (
            LeadStreamBuffer,
        )

        mock_redis = AsyncMock()
        buffer = LeadStreamBuffer(workspace_id=101, redis_client=mock_redis)

        lead_payload = {
            "source": "topcv",
            "client_id": "topcv_99",
            "value_hmac": "hmac_topcv_99",
            "company_name": "Tech Corp Vietnam",
        }

        await buffer.add_lead(lead_payload)
        await buffer.flush()

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args

        # Expected stream key: workspace:101:leads_stream
        assert call_args[0][0] == "workspace:101:leads_stream"
        assert call_args[1].get("maxlen") == 10000 or call_args[0][2] == 10000
        assert (
            call_args[1].get("approximate") is True
            or call_args[1].get("approx") is True
        )


# ---------------------------------------------------------------------------
# 3. Idempotent PostgreSQL Upsert Contract (AC-2)
# ---------------------------------------------------------------------------
class TestLeadStreamIdempotentUpsert:
    """Validate that flushed stream records generate idempotent SQL upserts."""

    @pytest.mark.asyncio
    async def test_upsert_query_contains_on_conflict_clause(self) -> None:
        """Flushed stream batch upsert must use ON CONFLICT (workspace_id, value_hmac) DO UPDATE."""
        from app.lead_intelligence.services.lead_stream_service import (
            build_lead_upsert_stmt,
        )

        leads = [
            {
                "workspace_id": 42,
                "client_id": "bds_100",
                "source": "batdongsan",
                "value_hmac": "hmac_unique_100",
                "company_name": "Novaland Group",
                "fit_score": 0.92,
            }
        ]

        sql_stmt = build_lead_upsert_stmt(leads)
        compiled_sql = str(sql_stmt).lower()

        assert "insert into leads" in compiled_sql
        assert "on conflict" in compiled_sql
        assert "workspace_id" in compiled_sql
        assert "value_hmac" in compiled_sql
        assert "do update" in compiled_sql
