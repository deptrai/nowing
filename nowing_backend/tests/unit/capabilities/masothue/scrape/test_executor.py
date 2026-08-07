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
    """cost_micros uses MASOTHUE_SCRAPE_MICROS_PER_ITEM default (3000 micros)."""
    # Force the fallback value so any mutation of the default constant is caught.
    monkeypatch.delattr("app.config.config.MASOTHUE_SCRAPE_MICROS_PER_ITEM", raising=False)

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
    assert out.cost_micros == 1 * 3000


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


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_timeout() -> None:
    """A MasothueTimeoutError must return a degraded ScrapeOutput."""

    async def fake_scrape(_: Any) -> None:
        raise MasothueTimeoutError("timeout")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "timeout"


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_access_blocked() -> None:
    """A MasothueAccessBlockedError must return a degraded ScrapeOutput."""

    async def fake_scrape(_: Any) -> None:
        raise MasothueAccessBlockedError("blocked")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "api_error"


@pytest.mark.asyncio
async def test_executor_returns_degraded_for_unexpected_exception() -> None:
    """A generic exception must return a degraded ScrapeOutput with reason api_error."""

    async def fake_scrape(_: Any) -> None:
        raise RuntimeError("boom")

    execute = build_scrape_executor(scrape_fn=fake_scrape)
    out = await execute(ScrapeInput(query="vinamilk", max_items=1, max_pages=1))

    assert out.degraded is True
    assert out.degradation_reason == "api_error"


@pytest.mark.asyncio
async def test_executor_persists_with_context(monkeypatch: Any) -> None:
    """When a CapabilityContext is provided, each item is upserted to the canonical store."""
    from app.capabilities.core.types import CapabilityContext

    calls: list[dict[str, Any]] = []

    async def fake_upsert(session: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.upsert_canonical_entity",
        fake_upsert,
    )
    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.fingerprint",
        lambda item: f"fp-{item.get('tax_code')}",
    )
    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.search_text",
        lambda item: f"text-{item.get('name')}",
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
    assert len(calls) == 1
    assert calls[0]["title"] == "Vinamilk"
    assert calls[0]["source_record_id"] == "0314539064"
    assert calls[0]["workspace_id"] == 42


@pytest.mark.asyncio
async def test_executor_persists_uses_fingerprint_when_tax_code_missing(monkeypatch: Any) -> None:
    """If the company has no tax_code, source_record_id falls back to the fingerprint."""
    from app.capabilities.core.types import CapabilityContext

    calls: list[dict[str, Any]] = []

    async def fake_upsert(session: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.upsert_canonical_entity",
        fake_upsert,
    )
    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.fingerprint",
        lambda item: "fp-no-tax",
    )
    monkeypatch.setattr(
        "app.capabilities.masothue.scrape.executor.search_text",
        lambda item: f"text-{item.get('name')}",
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
    assert len(calls) == 1
    assert calls[0]["title"] == "No Tax Co"
    assert calls[0]["source_record_id"] == "fp-no-tax"