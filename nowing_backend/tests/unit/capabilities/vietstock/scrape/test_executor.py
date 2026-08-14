"""Vietstock capability executor tests — cost, ingest, degradation."""

from __future__ import annotations

import types
from typing import Any

import pytest

from app.capabilities.core.types import CapabilityContext
from app.capabilities.vietstock.scrape.executor import build_scrape_executor
from app.capabilities.vietstock.scrape.schemas import ScrapeInput
from app.config import config
from app.proprietary.platforms.vietstock.schemas import (
    VietstockFinancialLineItem,
    VietstockFinancialReport,
    VietstockFinancials,
    VietstockQuote,
    VietstockScrapeOutput,
)

pytestmark = pytest.mark.unit


async def _fake_scrape(*args, **kwargs) -> VietstockScrapeOutput:
    return VietstockScrapeOutput(
        quote=VietstockQuote(
            symbol="VNM",
            current_price=75000.0,
            key_ratios={"pe": 15.2, "pb": 2.1, "roe": 18.5, "roa": 10.2},
        ),
        financials=VietstockFinancials(
            symbol="VNM",
            balance_sheet=VietstockFinancialReport(
                periods=["Q4-2025"],
                items=[
                    VietstockFinancialLineItem(
                        code="270", name="Tổng tài sản", values=[1000]
                    )
                ],
                unit="tỷ VND",
            ),
        ),
        degraded=False,
    )


async def _fake_scrape_degraded(*args, **kwargs) -> VietstockScrapeOutput:
    return VietstockScrapeOutput(
        quote=None,
        degraded=True,
        degradation_reason="AUTH_REFRESH_FAILED",
    )


@pytest.fixture
def exec():
    return build_scrape_executor(scrape_fn=_fake_scrape)


async def test_executor_cost_micros(exec, monkeypatch) -> None:
    """Arithmetic: should compute cost_micros = billable * rate."""
    monkeypatch.setattr(config, "VIETSTOCK_DATA_MICROS_PER_ITEM", 7500)
    out = await exec(ScrapeInput(symbol="VNM"))
    assert out.cost_micros == 7500


async def test_executor_degraded_run_is_free(exec, monkeypatch) -> None:
    """Arithmetic: degraded run should have cost_micros = 0."""
    monkeypatch.setattr(config, "VIETSTOCK_DATA_MICROS_PER_ITEM", 7500)
    executor = build_scrape_executor(scrape_fn=_fake_scrape_degraded)
    out = await executor(ScrapeInput(symbol="VNM"))
    assert out.degraded
    assert out.cost_micros == 0


async def test_executor_cost_micros_invalid_config_defaults(exec, monkeypatch) -> None:
    """Edge: non-integer cost config should fall back to default 5000."""
    monkeypatch.setattr(config, "VIETSTOCK_DATA_MICROS_PER_ITEM", "not-an-int")
    out = await exec(ScrapeInput(symbol="VNM"))
    assert out.cost_micros == 5000


async def test_executor_ingests_to_chainlens(exec, monkeypatch) -> None:
    """Over-Mocking: should call NowingIngestService and return ingestJobId."""

    class FakeNowingIngestService:
        calls: list[dict[str, Any]] = []

        async def ingest(self, **kwargs) -> Any:
            self.__class__.calls.append(kwargs)
            return types.SimpleNamespace(
                ingest_job_id="job-123",
                parent_ingest_job_id=None,
                status="ok",
            )

    FakeNowingIngestService.calls.clear()
    monkeypatch.setattr(
        "app.capabilities.vietstock.scrape.executor.NowingIngestService",
        FakeNowingIngestService,
    )

    ctx = CapabilityContext(
        session=types.SimpleNamespace(),
        workspace_id=1,
        run_id="run-1",
    )
    out = await exec(ScrapeInput(symbol="VNM"), ctx)

    assert out.degraded is False
    assert out.ingest_job_id == "job-123"
    assert out.ingest_status == "ok"
    assert FakeNowingIngestService.calls[0]["scraper_id"] == "vietstock.scrape"
    assert FakeNowingIngestService.calls[0]["workspace_id"] == 1
    assert len(FakeNowingIngestService.calls[0]["chunks"]) > 0


async def test_executor_ingest_failure_degrades(monkeypatch) -> None:
    """Over-Mocking: chainlens down should mark ingest_status failed."""

    class FailingNowingIngestService:
        async def ingest(self, **kwargs) -> Any:
            raise RuntimeError("chainlens down")

    monkeypatch.setattr(
        "app.capabilities.vietstock.scrape.executor.NowingIngestService",
        FailingNowingIngestService,
    )

    ctx = CapabilityContext(
        session=types.SimpleNamespace(),
        workspace_id=1,
        run_id="run-1",
    )
    executor = build_scrape_executor(scrape_fn=_fake_scrape)
    out = await executor(ScrapeInput(symbol="VNM"), ctx)

    assert out.degraded is True
    assert out.degradation_reason.startswith("ingest_failed")
    assert out.ingest_status == "failed"
