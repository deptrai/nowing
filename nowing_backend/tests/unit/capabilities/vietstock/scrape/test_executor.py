"""Vietstock capability executor tests — cost, ingest, degradation."""

from __future__ import annotations

import pytest

from app.capabilities.vietstock.scrape.executor import build_scrape_executor
from app.capabilities.vietstock.scrape.schemas import ScrapeInput
from app.proprietary.platforms.vietstock.schemas import (
    VietstockQuote,
    VietstockScrapeOutput,
)

pytestmark = pytest.mark.unit


async def _fake_scrape(*args, **kwargs) -> VietstockScrapeOutput:
    return VietstockScrapeOutput(
        quote=VietstockQuote(
            symbol="VNM",
            current_price=75000.0,
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
    monkeypatch.setattr("app.config.VIETSTOCK_DATA_MICROS_PER_ITEM", 7500)
    out = await exec(ScrapeInput(symbol="VNM"))
    assert out.cost_micros == 7500


async def test_executor_degraded_run_is_free(exec, monkeypatch) -> None:
    """Arithmetic: degraded run should have cost_micros = 0."""
    monkeypatch.setattr("app.config.VIETSTOCK_DATA_MICROS_PER_ITEM", 7500)
    executor = build_scrape_executor(scrape_fn=_fake_scrape_degraded)
    out = await executor(ScrapeInput(symbol="VNM"))
    assert out.degraded
    assert out.cost_micros == 0


async def test_executor_ingests_to_chainlens(exec) -> None:
    """Over-Mocking: should call NowingIngestService and return ingestJobId."""
    # TODO: mock NowingIngestService.ingest
    raise NotImplementedError("red phase — implement ingest mock")


async def test_executor_ingest_failure_degrades() -> None:
    """Over-Mocking: chainlens down should mark ingest_status failed."""
    # TODO: mock NowingIngestService raising
    raise NotImplementedError("red phase — implement chainlens failure mock")
