"""Unit tests asserting record_scraper_ingest_failure wiring across scrapers (Story 35.3).

Asserts that each wired exception catch point across:
- app.proprietary.platforms.batdongsan.scraper
- app.proprietary.platforms.muaban_bds.scraper
- app.proprietary.platforms.medirus.adapter
- app.proprietary.platforms.medirus.adapter_v2
- app.tasks.celery_tasks.social_medirus_ingest
- app.tasks.lead_scrapers
invokes record_scraper_ingest_failure(platform, reason) with the correct arguments.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.proprietary.platforms.batdongsan.fetch import (
    BatdongsanAccessBlockedError,
    BatdongsanDecodeError,
    BatdongsanRateLimitedError,
)
from app.proprietary.platforms.batdongsan.schemas import BatdongsanScrapeInput
from app.proprietary.platforms.batdongsan.scraper import scrape_batdongsan
from app.proprietary.platforms.medirus.adapter import MedirusSocialAdapter
from app.proprietary.platforms.medirus.adapter_v2 import (
    MedirusSocialAdapterV2,
    TargetUnsupportedError,
)
from app.proprietary.platforms.medirus.mcp_client import MedirusMcpError
from app.proprietary.platforms.muaban_bds.fetch import (
    MuabanBdsDecodeError,
    MuabanBdsRateLimitedError,
)
from app.proprietary.platforms.muaban_bds.schemas import MuabanBdsScrapeInput
from app.proprietary.platforms.muaban_bds.scraper import scrape_muaban_bds
from app.tasks.celery_tasks import social_medirus_ingest
from app.tasks.lead_scrapers import _execute_scraper_job

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# 1. Batdongsan Scraper Catch Points
# ---------------------------------------------------------------------------


class TestBatdongsanMetricWiring:
    @pytest.mark.asyncio
    async def test_decode_error_records_failure(self):
        input_model = BatdongsanScrapeInput(city="HN", max_items=5, max_pages=1)
        mock_fetch = AsyncMock(side_effect=BatdongsanDecodeError("Bad payload"))

        with patch(
            "app.proprietary.platforms.batdongsan.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_batdongsan(input_model, fetch_fn=mock_fetch)

        assert output.degraded
        mock_record.assert_any_call("batdongsan", "decode_error")

    @pytest.mark.asyncio
    async def test_rate_limited_records_failure(self):
        input_model = BatdongsanScrapeInput(city="HN", max_items=5, max_pages=1)
        mock_fetch = AsyncMock(side_effect=BatdongsanRateLimitedError("Rate limited"))

        with patch(
            "app.proprietary.platforms.batdongsan.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_batdongsan(input_model, fetch_fn=mock_fetch)

        assert output.degraded
        mock_record.assert_any_call("batdongsan", "rate_limited")

    @pytest.mark.asyncio
    async def test_api_error_records_failure(self):
        input_model = BatdongsanScrapeInput(city="HN", max_items=5, max_pages=1)
        mock_fetch = AsyncMock(side_effect=BatdongsanAccessBlockedError("IP blocked"))

        with patch(
            "app.proprietary.platforms.batdongsan.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_batdongsan(input_model, fetch_fn=mock_fetch)

        assert output.degraded
        mock_record.assert_any_call("batdongsan", "api_error")

    @pytest.mark.asyncio
    async def test_web_fallback_failed_records_failure(self):
        # City-level query triggers web fallback on empty mobile response
        input_model = BatdongsanScrapeInput(city="HN", max_items=5, max_pages=1)
        mock_fetch = AsyncMock(return_value={"data": [], "m": None})
        mock_web_fetch = AsyncMock(side_effect=RuntimeError("Web fetch failed"))

        with patch(
            "app.proprietary.platforms.batdongsan.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_batdongsan(
                input_model, fetch_fn=mock_fetch, web_fetch_fn=mock_web_fetch
            )

        assert output.degraded
        mock_record.assert_any_call("batdongsan", "web_fallback_failed")

    @pytest.mark.asyncio
    async def test_web_fallback_rate_limited_records_failure(self):
        input_model = BatdongsanScrapeInput(city="HN", max_items=5, max_pages=1)
        mock_fetch = AsyncMock(return_value={"data": [], "m": None})
        mock_web_fetch = AsyncMock(
            side_effect=BatdongsanRateLimitedError("Web rate limited")
        )

        with patch(
            "app.proprietary.platforms.batdongsan.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_batdongsan(
                input_model, fetch_fn=mock_fetch, web_fetch_fn=mock_web_fetch
            )

        assert output.degraded
        mock_record.assert_any_call("batdongsan", "rate_limited")


# ---------------------------------------------------------------------------
# 2. Muaban BĐS Scraper Catch Points
# ---------------------------------------------------------------------------


class _FakeMuabanSession:
    def __init__(self, **kwargs):
        pass

    async def start(self):
        pass

    async def close(self):
        pass


class TestMuabanBdsMetricWiring:
    @pytest.mark.asyncio
    async def test_rate_limited_records_failure(self, monkeypatch):
        monkeypatch.setattr(
            "app.proprietary.platforms.muaban_bds.scraper.AsyncStealthySession",
            _FakeMuabanSession,
        )
        monkeypatch.setattr(
            "app.proprietary.platforms.muaban_bds.scraper.fetch_page",
            AsyncMock(side_effect=MuabanBdsRateLimitedError("429 Too Many Requests")),
        )

        input_model = MuabanBdsScrapeInput(city="ho-chi-minh", max_items=5, max_pages=1)
        with patch(
            "app.proprietary.platforms.muaban_bds.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_muaban_bds(input_model)

        assert output.degraded
        assert output.degradation_reason == "rate_limited"
        mock_record.assert_any_call("muaban_bds", "rate_limited")

    @pytest.mark.asyncio
    async def test_api_error_records_failure(self, monkeypatch):
        monkeypatch.setattr(
            "app.proprietary.platforms.muaban_bds.scraper.AsyncStealthySession",
            _FakeMuabanSession,
        )
        monkeypatch.setattr(
            "app.proprietary.platforms.muaban_bds.scraper.fetch_page",
            AsyncMock(side_effect=MuabanBdsDecodeError("Malformed JSON")),
        )

        input_model = MuabanBdsScrapeInput(city="ho-chi-minh", max_items=5, max_pages=1)
        with patch(
            "app.proprietary.platforms.muaban_bds.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_muaban_bds(input_model)

        assert output.degraded
        assert output.degradation_reason == "api_error"
        mock_record.assert_any_call("muaban_bds", "api_error")

    @pytest.mark.asyncio
    async def test_scraper_error_records_failure(self, monkeypatch):
        # Force top-level exception
        monkeypatch.setattr(
            "app.proprietary.platforms.muaban_bds.scraper.AsyncStealthySession",
            MagicMock(side_effect=RuntimeError("Browser launch crash")),
        )

        input_model = MuabanBdsScrapeInput(city="ho-chi-minh", max_items=5, max_pages=1)
        with patch(
            "app.proprietary.platforms.muaban_bds.scraper.record_scraper_ingest_failure"
        ) as mock_record:
            output = await scrape_muaban_bds(input_model)

        assert output.degraded
        assert output.degradation_reason == "scraper_error"
        mock_record.assert_any_call("muaban_bds", "scraper_error")


# ---------------------------------------------------------------------------
# 3. Medirus Social Adapter (v1) Catch Points
# ---------------------------------------------------------------------------


class TestMedirusAdapterV1MetricWiring:
    @pytest.mark.asyncio
    async def test_timeout_records_failure(self):
        adapter = MedirusSocialAdapter(medirus_path="/opt/medirus")
        adapter._build_mcp_tool_args = AsyncMock(
            return_value=("medirus_facebook_group_posts", {})
        )
        adapter._resolve_mcp_server_params = MagicMock(return_value=MagicMock())
        adapter._call_mcp_tool = AsyncMock(side_effect=TimeoutError("MCP timeout"))

        with patch(
            "app.proprietary.platforms.medirus.adapter.record_scraper_ingest_failure"
        ) as mock_record:
            result = await adapter._execute_medirus_command(
                "medirus_facebook_group_posts", {}
            )

        assert not result["success"]
        mock_record.assert_any_call("medirus", "timeout")

    @pytest.mark.asyncio
    async def test_decode_error_records_failure(self):
        adapter = MedirusSocialAdapter(medirus_path="/opt/medirus")
        adapter._build_mcp_tool_args = AsyncMock(
            return_value=("medirus_facebook_group_posts", {})
        )
        adapter._resolve_mcp_server_params = MagicMock(return_value=MagicMock())
        adapter._call_mcp_tool = AsyncMock(
            side_effect=json.JSONDecodeError("Expecting value", "doc", 0)
        )

        with patch(
            "app.proprietary.platforms.medirus.adapter.record_scraper_ingest_failure"
        ) as mock_record:
            result = await adapter._execute_medirus_command(
                "medirus_facebook_group_posts", {}
            )

        assert not result["success"]
        mock_record.assert_any_call("medirus", "decode_error")

    @pytest.mark.asyncio
    async def test_mcp_error_records_failure(self):
        adapter = MedirusSocialAdapter(medirus_path="/opt/medirus")
        adapter._build_mcp_tool_args = AsyncMock(
            return_value=("medirus_facebook_group_posts", {})
        )
        adapter._resolve_mcp_server_params = MagicMock(return_value=MagicMock())
        adapter._call_mcp_tool = AsyncMock(
            side_effect=MedirusMcpError(code="500", message="Internal error")
        )

        with patch(
            "app.proprietary.platforms.medirus.adapter.record_scraper_ingest_failure"
        ) as mock_record:
            result = await adapter._execute_medirus_command(
                "medirus_facebook_group_posts", {}
            )

        assert not result["success"]
        mock_record.assert_any_call("medirus", "mcp_error")

    @pytest.mark.asyncio
    async def test_unexpected_error_records_failure(self):
        adapter = MedirusSocialAdapter(medirus_path="/opt/medirus")
        adapter._build_mcp_tool_args = AsyncMock(
            return_value=("medirus_facebook_group_posts", {})
        )
        adapter._resolve_mcp_server_params = MagicMock(return_value=MagicMock())
        adapter._call_mcp_tool = AsyncMock(
            side_effect=RuntimeError("Unexpected OS crash")
        )

        with patch(
            "app.proprietary.platforms.medirus.adapter.record_scraper_ingest_failure"
        ) as mock_record:
            result = await adapter._execute_medirus_command(
                "medirus_facebook_group_posts", {}
            )

        assert not result["success"]
        mock_record.assert_any_call("medirus", "unexpected_error")


# ---------------------------------------------------------------------------
# 4. Medirus Social Adapter V2 Catch Points
# ---------------------------------------------------------------------------


class TestMedirusAdapterV2MetricWiring:
    @pytest.mark.asyncio
    async def test_mcp_error_records_failure(self):
        client = AsyncMock()
        client.call_tool.side_effect = MedirusMcpError(
            code="500", message="Primary MCP tool error"
        )
        adapter = MedirusSocialAdapterV2(client=client)

        target = SimpleNamespace(
            id=1,
            platform="facebook_group",
            target_id="group_123",
            target_url="https://facebook.com/groups/group_123",
            account_id=None,
            proxy_url=None,
            workspace_id=1,
        )

        with (
            patch(
                "app.proprietary.platforms.medirus.adapter_v2.record_scraper_ingest_failure"
            ) as mock_record,
            pytest.raises(MedirusMcpError),
        ):
            await adapter.fetch_posts_for_target(target)

        mock_record.assert_any_call("medirus", "mcp_error")

    @pytest.mark.asyncio
    async def test_fallback_mcp_error_records_failure(self):
        client = AsyncMock()
        # Primary call raises tool not found (4001), fallback call raises 500
        client.call_tool.side_effect = [
            MedirusMcpError(code="4001", message="Tool not found"),
            MedirusMcpError(code="500", message="Fallback tool failed"),
        ]
        adapter = MedirusSocialAdapterV2(client=client)

        target = SimpleNamespace(
            id=2,
            platform="facebook_group",
            target_id="group_fallback",
            target_url="https://facebook.com/groups/group_fallback",
            account_id=None,
            proxy_url=None,
            workspace_id=1,
        )

        with (
            patch(
                "app.proprietary.platforms.medirus.adapter_v2.record_scraper_ingest_failure"
            ) as mock_record,
            pytest.raises(MedirusMcpError),
        ):
            await adapter.fetch_posts_for_target(target)

        mock_record.assert_any_call("medirus", "mcp_error")
        mock_record.assert_any_call("medirus", "fallback_mcp_error")


# ---------------------------------------------------------------------------
# 5. Celery Task social_medirus_ingest Catch Points
# ---------------------------------------------------------------------------


class _FakeAdapterCtx:
    def __init__(self, adapter):
        self.adapter = adapter

    async def __aenter__(self):
        return self.adapter

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class _FakeCelerySession:
    def __init__(self, target):
        self.target = target

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def get(self, model, ident):
        return self.target

    async def execute(self, stmt):
        res = MagicMock()
        res.scalars().first.return_value = None
        return res

    async def commit(self):
        pass

    async def rollback(self):
        pass


class TestSocialMedirusIngestMetricWiring:
    @pytest.mark.asyncio
    async def test_target_unsupported_records_failure(self, monkeypatch):
        target = SimpleNamespace(
            id=10,
            workspace_id=1,
            platform="shopee_keyword",
            target_id="shopee_bds",
            target_name="Shopee BDS",
            scrape_interval_minutes=15,
            last_scraped_at=None,
            is_active=True,
            status="active",
            account_id=None,
            proxy_url=None,
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "get_celery_session_maker",
            lambda: lambda: _FakeCelerySession(target),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_acquire_target_lock",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_release_target_lock",
            AsyncMock(),
        )

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        monkeypatch.setattr(
            social_medirus_ingest.aioredis,
            "from_url",
            lambda *a, **kw: mock_client,
        )

        mock_adapter = MagicMock()
        mock_adapter.fetch_posts_for_target = AsyncMock(
            side_effect=TargetUnsupportedError("Platform shopee_keyword unsupported")
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "MedirusSocialAdapterV2",
            lambda: _FakeAdapterCtx(mock_adapter),
        )

        task = MagicMock()
        with patch(
            "app.tasks.celery_tasks.social_medirus_ingest.record_scraper_ingest_failure"
        ) as mock_record:
            res = await social_medirus_ingest._ingest_social_target(task, target.id)

        assert res == 0
        mock_record.assert_any_call("medirus", "target_unsupported")

    @pytest.mark.asyncio
    async def test_mcp_error_records_failure(self, monkeypatch):
        target = SimpleNamespace(
            id=11,
            workspace_id=1,
            platform="facebook_group",
            target_id="fb_group_err",
            target_name="FB Group",
            scrape_interval_minutes=15,
            last_scraped_at=None,
            is_active=True,
            status="active",
            account_id=None,
            proxy_url=None,
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "get_celery_session_maker",
            lambda: lambda: _FakeCelerySession(target),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_acquire_target_lock",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_release_target_lock",
            AsyncMock(),
        )

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        monkeypatch.setattr(
            social_medirus_ingest.aioredis,
            "from_url",
            lambda *a, **kw: mock_client,
        )

        mock_adapter = MagicMock()
        # Code 4029 halts target without retrying
        mock_adapter.fetch_posts_for_target = AsyncMock(
            side_effect=MedirusMcpError(code="4029", message="Permanent halt error")
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "MedirusSocialAdapterV2",
            lambda: _FakeAdapterCtx(mock_adapter),
        )

        task = MagicMock()
        with patch(
            "app.tasks.celery_tasks.social_medirus_ingest.record_scraper_ingest_failure"
        ) as mock_record:
            res = await social_medirus_ingest._ingest_social_target(task, target.id)

        assert res == 0
        # Task must not duplicate mcp_error; adapter already records it
        mock_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_mcp_error_reraise_does_not_record_generic_ingest_failure(
        self, monkeypatch
    ):
        target = SimpleNamespace(
            id=13,
            workspace_id=1,
            platform="facebook_group",
            target_id="fb_group_reraise",
            target_name="FB Reraise",
            scrape_interval_minutes=15,
            last_scraped_at=None,
            is_active=True,
            status="active",
            account_id=None,
            proxy_url=None,
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "get_celery_session_maker",
            lambda: lambda: _FakeCelerySession(target),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_acquire_target_lock",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_release_target_lock",
            AsyncMock(),
        )

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        monkeypatch.setattr(
            social_medirus_ingest.aioredis,
            "from_url",
            lambda *a, **kw: mock_client,
        )

        mock_adapter = MagicMock()
        # An unmapped code with fallback behaviour that re-raises
        err = MedirusMcpError(code="9999", message="Fatal mcp error")
        mock_adapter.fetch_posts_for_target = AsyncMock(side_effect=err)
        monkeypatch.setattr(
            social_medirus_ingest,
            "MedirusSocialAdapterV2",
            lambda: _FakeAdapterCtx(mock_adapter),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "resolve_task_behavior",
            lambda exc: SimpleNamespace(behavior=None),
        )

        task = MagicMock()
        with (
            patch(
                "app.tasks.celery_tasks.social_medirus_ingest.record_scraper_ingest_failure"
            ) as mock_record,
            pytest.raises(MedirusMcpError),
        ):
            await social_medirus_ingest._ingest_social_target(task, target.id)

        mock_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_failure_records_failure(self, monkeypatch):
        target = SimpleNamespace(
            id=12,
            workspace_id=1,
            platform="facebook_group",
            target_id="fb_group_fatal",
            target_name="FB Fatal",
            scrape_interval_minutes=15,
            last_scraped_at=None,
            is_active=True,
            status="active",
            account_id=None,
            proxy_url=None,
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "get_celery_session_maker",
            lambda: lambda: _FakeCelerySession(target),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_acquire_target_lock",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "_release_target_lock",
            AsyncMock(),
        )

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        monkeypatch.setattr(
            social_medirus_ingest.aioredis,
            "from_url",
            lambda *a, **kw: mock_client,
        )

        mock_adapter = MagicMock()
        # Non-MCP error triggers outer except block
        mock_adapter.fetch_posts_for_target = AsyncMock(
            side_effect=RuntimeError("Unrecoverable database corruption")
        )
        monkeypatch.setattr(
            social_medirus_ingest,
            "MedirusSocialAdapterV2",
            lambda: _FakeAdapterCtx(mock_adapter),
        )

        task = MagicMock()
        with (
            patch(
                "app.tasks.celery_tasks.social_medirus_ingest.record_scraper_ingest_failure"
            ) as mock_record,
            pytest.raises(RuntimeError),
        ):
            await social_medirus_ingest._ingest_social_target(task, target.id)

        mock_record.assert_any_call("medirus", "ingest_failure")


# ---------------------------------------------------------------------------
# 6. Lead Scrapers Task Catch Points
# ---------------------------------------------------------------------------


class TestLeadScrapersMetricWiring:
    @pytest.mark.asyncio
    async def test_scraper_task_failure_records_metric(self, monkeypatch):
        mock_circuit = MagicMock()
        mock_circuit.is_available = AsyncMock(return_value=True)
        mock_circuit.record_failure = AsyncMock()
        monkeypatch.setattr(
            "app.tasks.lead_scrapers.PlatformCircuitBreaker",
            lambda: mock_circuit,
        )

        mock_limiter = MagicMock()
        mock_limiter.acquire = AsyncMock(
            return_value=SimpleNamespace(allowed=True, retry_after_ms=0)
        )
        monkeypatch.setattr(
            "app.tasks.lead_scrapers.PlatformRateLimiter",
            lambda: mock_limiter,
        )

        mock_adapter = MagicMock()
        mock_adapter.search_leads = AsyncMock(
            side_effect=RuntimeError("Upstream portal error")
        )

        mock_registry = MagicMock()
        mock_registry.get_adapter.return_value = mock_adapter
        monkeypatch.setattr(
            "app.tasks.lead_scrapers.LeadSourceAdapterRegistry.get_default",
            lambda: mock_registry,
        )

        mock_buffer = MagicMock()
        monkeypatch.setattr(
            "app.tasks.lead_scrapers.LeadStreamBuffer",
            lambda workspace_id: mock_buffer,
        )

        with (
            patch(
                "app.tasks.lead_scrapers.record_scraper_ingest_failure"
            ) as mock_record,
            pytest.raises(RuntimeError),
        ):
            await _execute_scraper_job(
                workspace_id=1,
                platform="batdongsan",
                query="can ho vin",
            )

        mock_record.assert_any_call("batdongsan", "scraper_task_failure")
