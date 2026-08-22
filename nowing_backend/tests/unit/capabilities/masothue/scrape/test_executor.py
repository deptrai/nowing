"""Unit tests for masothue.scrape executor."""

from __future__ import annotations

from typing import Any

import pytest

from app.capabilities.masothue.scrape.executor import build_scrape_executor
from app.capabilities.masothue.scrape.schemas import ScrapeInput, ScrapeOutput
from app.proprietary.platforms.masothue import (
    MasothueAccessBlockedError,
    MasothueDecodeError,
    MasothueRateLimitedError,
    MasothueTimeoutError,
)

pytestmark = pytest.mark.unit


def _company_data(tax_code: str, name: str) -> dict[str, Any]:
    return {
        "tax_code": tax_code,
        "name": name,
        "address": "10 Đường 3/2",
        "main_industry": "Sản xuất sữa",
    }


@pytest.mark.asyncio
async def test_executor_returns_output_and_cost(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "app.config.config.MASOTHUE_SCRAPE_MICROS_PER_ITEM", 3000, raising=False
    )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [
                _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn"),
                _company_data("0314539065", "Công ty Cổ phần Sữa Việt Nam"),
            ],
            "degraded": False,
        }

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=2, max_pages=1))

    assert isinstance(out, ScrapeOutput)
    assert out.degraded is False
    assert out.total_items == 2
    assert out.billable_units == 2
    assert out.cost_micros == 2 * 3000


@pytest.mark.asyncio
async def test_executor_returns_zero_cost_when_degraded(monkeypatch: Any) -> None:
    """A degraded run reports cost_micros=0 even when items were returned."""
    monkeypatch.setattr(
        "app.config.config.MASOTHUE_SCRAPE_MICROS_PER_ITEM", 3000, raising=False
    )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [
                {"tax_code": "0314539064", "name": "Công ty TNHH Vinamilk Tân Sơn"},
            ],
            "degraded": True,
            "degradation_reason": "rate_limited",
        }

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.total_items == 1
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_cost_uses_default_rate(monkeypatch: Any) -> None:
    """When MASOTHUE_SCRAPE_MICROS_PER_ITEM is not configured, default 3000 is used."""
    import app.capabilities.masothue.scrape.executor as executor_mod

    if hasattr(executor_mod.config, "MASOTHUE_SCRAPE_MICROS_PER_ITEM"):
        monkeypatch.delattr(
            executor_mod.config, "MASOTHUE_SCRAPE_MICROS_PER_ITEM", raising=False
        )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [
                _company_data("0314539064", "Công ty TNHH Vinamilk Tân Sơn"),
            ],
            "degraded": False,
        }

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is False
    assert out.total_items == 1
    assert out.cost_micros == 3000


@pytest.mark.asyncio
async def test_executor_unwraps_none_result(monkeypatch: Any) -> None:
    """When the scrape actor returns None, the executor returns an empty degraded result."""
    monkeypatch.setattr(
        "app.config.config.MASOTHUE_SCRAPE_MICROS_PER_ITEM", 3000, raising=False
    )

    async def fake_scrape(_: Any) -> None:
        return None

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.total_items == 0
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_rate_limit() -> None:
    """A MasothueRateLimitedError must return a degraded ScrapeOutput."""

    async def fake_scrape(_: Any) -> None:
        raise MasothueRateLimitedError("429")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "rate_limited"
    assert out.total_items == 0
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_decode_error() -> None:
    """A MasothueDecodeError must return a degraded ScrapeOutput."""

    async def fake_scrape(_: Any) -> None:
        raise MasothueDecodeError("bad html")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "decode_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_timeout() -> None:
    """A MasothueTimeoutError must return a degraded ScrapeOutput."""

    async def fake_scrape(_: Any) -> None:
        raise MasothueTimeoutError("timeout")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "timeout"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_access_blocked() -> None:
    """A MasothueAccessBlockedError must return a degraded ScrapeOutput."""

    async def fake_scrape(_: Any) -> None:
        raise MasothueAccessBlockedError("blocked")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "api_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_unexpected_exception() -> None:
    """A generic exception must return a degraded ScrapeOutput with reason api_error."""

    async def fake_scrape(_: Any) -> None:
        raise RuntimeError("boom")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "api_error"
    assert out.cost_micros == 0


@pytest.mark.asyncio
async def test_executor_persists_with_context(monkeypatch: Any) -> None:
    """When a CapabilityContext is provided, each item is upserted to the canonical store."""
    from app.capabilities.core.types import CapabilityContext

    ingest_calls: list[list[Any]] = []

    async def fake_ingest(*args: Any, **kwargs: Any) -> None:
        ingest_calls.append([args, kwargs])

    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.NowingIngestService.ingest",
        fake_ingest,
    )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [
                _company_data("0314539064", "Vinamilk"),
            ],
            "degraded": False,
        }

    class FakeSession:
        pass

    ctx = CapabilityContext(session=FakeSession(), workspace_id=42)
    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(
        ScrapeInput(query="vinamilk", max_items=1, max_pages=1),
        ctx=ctx,
    )

    assert out.degraded is False
    assert out.total_items == 1
    assert len(ingest_calls) == 1
    _args, kwargs = ingest_calls[0]
    assert kwargs["scraper_id"] == "masothue"
    assert kwargs["workspace_id"] == 42


@pytest.mark.asyncio
async def test_executor_persists_uses_fingerprint_when_tax_code_missing(
    monkeypatch: Any,
) -> None:
    """If the company has no tax_code, source_record_id falls back to the fingerprint."""
    from app.capabilities.core.types import CapabilityContext

    ingest_calls: list[list[Any]] = []

    async def fake_ingest(*args: Any, **kwargs: Any) -> None:
        ingest_calls.append([args, kwargs])

    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.NowingIngestService.ingest",
        fake_ingest,
    )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [
                {"name": "No Tax Co"},
            ],
            "degraded": False,
        }

    class FakeSession:
        pass

    ctx = CapabilityContext(session=FakeSession(), workspace_id=7)
    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(
        ScrapeInput(query="vinamilk", max_items=1, max_pages=1),
        ctx=ctx,
    )

    assert out.degraded is False
    assert len(ingest_calls) == 1
    _args, kwargs = ingest_calls[0]
    assert kwargs["scraper_id"] == "masothue"


@pytest.mark.asyncio
async def test_executor_unwraps_masothue_scrape_output() -> None:
    """The executor can also accept a MasothueScrapeOutput object from the actor."""
    from app.proprietary.platforms.masothue.schemas import (
        MasothueCompany,
        MasothueScrapeOutput,
    )

    async def fake_scrape(_: Any) -> MasothueScrapeOutput:
        return MasothueScrapeOutput(
            items=[MasothueCompany(name="Vinamilk", tax_code="0314539064")],
        )

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is False
    assert out.total_items == 1
    assert out.items[0].name == "Vinamilk"


@pytest.mark.asyncio
async def test_executor_uses_exclude_unset() -> None:
    """Only the fields the caller explicitly set are forwarded to MasothueSearchInput."""
    captured: dict[str, Any] = {}
    from app.proprietary.platforms.masothue.schemas import MasothueSearchInput

    original_init = MasothueSearchInput.__init__

    def tracking_init(self: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        original_init(self, **kwargs)

    async def fake_scrape(actor_input: MasothueSearchInput) -> dict[str, Any]:
        return {"items": []}

    execute = build_scrape_executor(scrape_fn=fake_scrape)

    from unittest.mock import patch

    with patch.object(MasothueSearchInput, "__init__", tracking_init):
        await execute(ScrapeInput(query="vinamilk"))

    assert "query" in captured
    assert captured["query"] == "vinamilk"
    # If exclude_unset was False, all default fields would also be present.
    assert "max_items" not in captured


@pytest.mark.asyncio
async def test_executor_default_degraded_is_false_when_result_omits_key() -> None:
    """result.get('degraded', False) must default to False, not True."""

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [_company_data("0314539064", "Vinamilk")],
        }

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is False
    assert out.total_items == 1


@pytest.mark.asyncio
async def test_executor_swallows_upsert_exception(monkeypatch: Any) -> None:
    """An exception during canonical upsert must be logged and swallowed."""
    from app.capabilities.core.types import CapabilityContext

    async def fake_ingest(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("ingest boom")

    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.NowingIngestService.ingest",
        fake_ingest,
    )

    async def fake_scrape(_: Any) -> dict[str, Any]:
        return {
            "items": [_company_data("0314539064", "Vinamilk")],
            "degraded": False,
        }

    class FakeSession:
        pass

    ctx = CapabilityContext(session=FakeSession(), workspace_id=42)
    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(
        ScrapeInput(query="vinamilk", max_items=1, max_pages=1),
        ctx=ctx,
    )

    assert out.degraded is False
    assert out.total_items == 1


@pytest.mark.asyncio
async def test_unwrap_result_none() -> None:
    """_unwrap_result(None) returns an empty, degraded dict with total_items=0."""
    from app.capabilities.masothue.scrape.executor import _unwrap_result

    result = _unwrap_result(None)
    assert result["items"] == []
    assert result["total_items"] == 0
    assert result["degraded"] is True
    assert result["degradation_reason"] == "unknown"
