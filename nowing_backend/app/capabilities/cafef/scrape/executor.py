"""``cafef.scrape`` executor: verb input → scraper → typed output."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.db import DocumentType, Workspace
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.proprietary.platforms.cafef import (
    CafeFAccessBlockedError,
    CafeFDecodeError,
    CafeFRateLimitedError,
    CafeFScrapeOutput,
    scrape_cafef,
)
from app.proprietary.platforms.cafef.schemas import CafeFNewsItem, CafeFScrapeInput

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[..., Awaitable[CafeFScrapeOutput]]


def _news_markdown(item: CafeFNewsItem) -> str:
    """Create clean markdown content for indexing and search."""
    parts = [f"# {item.title}", ""]
    if item.symbol:
        parts.append(f"**Symbol:** {item.symbol}")
    parts.append(f"**Source:** {item.source or 'cafef'}")
    if item.published_at:
        parts.append(f"**Published:** {item.published_at}")
    parts.append("")
    if item.summary:
        parts.append(item.summary)
        parts.append("")
    if item.url:
        parts.append(f"**URL:** {item.url}")
    return "\n".join(parts)


async def _index_cafef_news(
    ctx: CapabilityContext,
    symbol: str,
    news: list[CafeFNewsItem],
) -> None:
    """Persist news articles as NEWS_CONNECTOR documents so they appear in search.

    Failures are logged but do not degrade the main scrape response: the
    downstream consumer already received the article list.
    """
    if not news:
        return

    workspace = await ctx.session.get(Workspace, ctx.workspace_id)
    owner_id = workspace.user_id if workspace is not None else None
    created_by = str(owner_id) if owner_id is not None else None

    pipeline = IndexingPipelineService(ctx.session)
    connector_docs: list[ConnectorDocument] = []
    for item in news:
        unique_id = item.url
        if not unique_id:
            digest = hashlib.md5(f"{symbol}:{item.title}".encode()).hexdigest()
            unique_id = f"cafef:{symbol}:{digest}"
        connector_docs.append(
            ConnectorDocument(
                title=item.title,
                source_markdown=_news_markdown(item),
                unique_id=unique_id,
                document_type=DocumentType.NEWS_CONNECTOR,
                workspace_id=ctx.workspace_id,
                connector_id=None,
                created_by_id=created_by,
                metadata={
                    "symbol": symbol,
                    "source": item.source or "cafef",
                    "published_at": item.published_at,
                    "url": item.url,
                },
            )
        )

    try:
        await pipeline.index_batch(connector_docs)
    except Exception:
        logger.exception("cafef news indexing failed")


def _unwrap_result(
    result: CafeFScrapeOutput | dict[str, Any] | None,
) -> dict[str, Any]:
    if result is None:
        return {
            "quote": None,
            "financials": None,
            "news": [],
            "degraded": True,
            "degradation_reason": "unknown",
            "billable_units": 0,
        }
    if isinstance(result, CafeFScrapeOutput):
        return {
            "quote": result.quote,
            "financials": result.financials,
            "news": result.news,
            "degraded": result.degraded,
            "degradation_reason": result.degradation_reason,
            "billable_units": result.billable_units,
        }
    return result


def build_scrape_executor(
    scrape_fn: ScrapeFn | None = None,
    index_news: bool = True,
) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape = scrape_fn or scrape_cafef

    async def execute(
        payload: ScrapeInput,
        ctx: CapabilityContext | None = None,
    ) -> ScrapeOutput:
        actor_input = CafeFScrapeInput(**payload.model_dump(exclude_unset=True))

        emit_progress(
            "starting",
            f"Resolving CafeF data for {payload.symbol}",
            total=1,
            unit="query",
        )
        try:
            raw = await scrape(actor_input)
        except CafeFRateLimitedError:
            logger.exception("cafef.scrape rate limited")
            return ScrapeOutput(
                cost_micros=0,
                degraded=True,
                degradation_reason="rate_limited",
                total_items=0,
            )
        except CafeFDecodeError:
            logger.exception("cafef.scrape decode error")
            return ScrapeOutput(
                cost_micros=0,
                degraded=True,
                degradation_reason="decode_error",
                total_items=0,
            )
        except (CafeFAccessBlockedError, Exception) as exc:
            logger.exception("cafef.scrape actor failed: %s", exc)
            return ScrapeOutput(
                cost_micros=0,
                degraded=True,
                degradation_reason="api_error",
                total_items=0,
            )

        result = _unwrap_result(raw)
        billable = int(result.get("billable_units", 0) or 0)
        degraded = bool(result.get("degraded", False))
        cost = (
            0
            if degraded
            else billable * getattr(config, "CAFEF_DATA_MICROS_PER_ITEM", 5000)
        )

        symbol = payload.symbol.upper()
        quote = result.get("quote")
        financials = result.get("financials")
        news = result.get("news") or []

        if index_news and payload.include_news and ctx is not None and news:
            await _index_cafef_news(ctx, symbol, news)

        emit_progress(
            "done",
            f"CafeF scrape for {symbol} complete",
            current=1 if not degraded else 0,
            total=1,
            unit="query",
        )

        return ScrapeOutput(
            quote=quote,
            financials=financials,
            news=news,
            cost_micros=cost,
            degraded=degraded,
            degradation_reason=result.get("degradation_reason"),
            total_items=billable,
        )

    return execute
