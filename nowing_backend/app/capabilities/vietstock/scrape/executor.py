"""``vietstock.scrape`` executor: verb input → scraper → typed output."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.capabilities.core import Executor
from app.capabilities.core.progress import emit_progress
from app.capabilities.core.types import CapabilityContext
from app.config import config
from app.proprietary.platforms.vietstock import (
    VietstockAccessBlockedError,
    VietstockAuthRefreshError,
    VietstockDecodeError,
    VietstockRateLimitedError,
    VietstockScrapeOutput,
    scrape_vietstock,
)
from app.proprietary.platforms.vietstock.schemas import VietstockScrapeInput
from app.services.chainlens.ingest import NowingIngestService
from app.services.scraper_chunks.serializer import to_chunks

from .schemas import ScrapeInput, ScrapeOutput

logger = logging.getLogger(__name__)

ScrapeFn = Callable[..., Awaitable[VietstockScrapeOutput]]


def _statement_records(financials: Any, fetched_at: str) -> list[dict[str, Any]]:
    """Turn typed financial statements into canonical per-period records."""
    records: list[dict[str, Any]] = []
    if financials is None:
        return records

    statements = {
        "balance_sheet": financials.balance_sheet,
        "income_statement": financials.income_statement,
        "cash_flow": financials.cash_flow,
    }
    for statement_type, report in statements.items():
        for idx, period in enumerate(report.periods or []):
            items: list[dict[str, Any]] = []
            for line in report.items or []:
                values = line.values or []
                if idx < len(values):
                    items.append(
                        {
                            "code": line.code,
                            "name": line.name,
                            "value": values[idx],
                        }
                    )
            records.append(
                {
                    "symbol": financials.symbol,
                    "statement_type": statement_type,
                    "period": period,
                    "unit": report.unit,
                    "items": items,
                    "conflict_flags": False,
                    "source_count": 1,
                }
            )
    return records


def _build_vietstock_chunks(
    result: VietstockScrapeOutput,
    fetched_at: str,
) -> list[Any]:
    """Convert a Vietstock scrape result into ChainLens ``Chunk[]``.

    Failures for individual records are swallowed so that one bad record does
    not block the rest of the batch.
    """
    chunks: list[Any] = []

    if result.quote is not None:
        try:
            chunks.extend(
                to_chunks(
                    domain="vietstock",
                    data=result.quote.model_dump(),
                    fetched_at=fetched_at,
                    content_type="text/markdown",
                    category="quote",
                )
            )
        except Exception:
            logger.exception("vietstock quote chunk serialization failed")

    if result.financials is not None:
        for record in _statement_records(result.financials, fetched_at):
            try:
                chunks.extend(
                    to_chunks(
                        domain="vietstock",
                        data=record,
                        fetched_at=fetched_at,
                        content_type="financial_statement",
                        category="financial_statement",
                    )
                )
            except Exception:
                logger.exception(
                    "vietstock financial chunk serialization failed",
                    extra={"symbol": record.get("symbol"), "period": record.get("period")},
                )

    return chunks


async def _ingest_vietstock_output(
    output: ScrapeOutput,
    result: VietstockScrapeOutput,
    ctx: CapabilityContext,
) -> None:
    """Ingest quote and financial statement chunks to chainlens-research."""
    fetched_at = datetime.now(UTC).isoformat()
    chunks = _build_vietstock_chunks(result, fetched_at)
    if not chunks:
        output.ingest_status = "noop"
        return

    try:
        ingest_result = await NowingIngestService().ingest(
            scraper_id="vietstock.scrape",
            chunks=chunks,
            workspace_id=ctx.workspace_id,
            session=ctx.session,
            correlation_id=ctx.run_id,
        )
        output.ingest_job_id = (
            ingest_result.ingest_job_id or ingest_result.parent_ingest_job_id
        )
        output.ingest_status = ingest_result.status
    except Exception:
        logger.exception("vietstock.scrape chainlens ingest failed")
        output.ingest_status = "failed"


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape = scrape_fn or scrape_vietstock

    async def execute(
        payload: ScrapeInput,
        ctx: CapabilityContext | None = None,
    ) -> ScrapeOutput:
        actor_input = VietstockScrapeInput(
            **payload.model_dump(exclude_unset=True)
        )

        emit_progress(
            "starting",
            f"Resolving Vietstock data for {payload.symbol}",
            total=1,
            unit="query",
        )
        try:
            raw = await scrape(actor_input)
        except VietstockRateLimitedError:
            logger.exception("vietstock.scrape rate limited")
            return ScrapeOutput(
                cost_micros=0,
                degraded=True,
                degradation_reason="rate_limited",
                total_items=0,
            )
        except VietstockDecodeError:
            logger.exception("vietstock.scrape decode error")
            return ScrapeOutput(
                cost_micros=0,
                degraded=True,
                degradation_reason="decode_error",
                total_items=0,
            )
        except VietstockAuthRefreshError:
            logger.exception("vietstock.scrape auth refresh failed")
            return ScrapeOutput(
                cost_micros=0,
                degraded=True,
                degradation_reason="auth_refresh_failed",
                total_items=0,
            )
        except (VietstockAccessBlockedError, Exception) as exc:
            logger.exception("vietstock.scrape actor failed: %s", exc)
            return ScrapeOutput(
                cost_micros=0,
                degraded=True,
                degradation_reason="api_error",
                total_items=0,
            )

        billable = int(raw.billable_units or 0)
        degraded = bool(raw.degraded)
        cost = (
            0
            if degraded
            else billable
            * getattr(config, "VIETSTOCK_DATA_MICROS_PER_ITEM", 5000)
        )

        output = ScrapeOutput(
            quote=raw.quote,
            financials=raw.financials,
            cost_micros=cost,
            degraded=degraded,
            degradation_reason=raw.degradation_reason,
            total_items=billable,
        )

        if not degraded and ctx is not None:
            await _ingest_vietstock_output(output, raw, ctx)

        emit_progress(
            "done",
            f"Vietstock scrape for {payload.symbol.upper()} complete",
            current=1 if not degraded else 0,
            total=1,
            unit="query",
        )

        return output

    return execute
