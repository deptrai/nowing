"""Charge the workspace owner per billable success at the capability executor (03c)."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.capabilities.core.types import (
    BillableInput,
    BillableOutput,
    BillingUnit,
    CapabilityContext,
)
from app.config import config
from app.services import wallet_credit
from app.services.platform_scrape_credit_service import PlatformScrapeCreditService
from app.services.token_tracking_service import record_token_usage
from app.services.web_crawl_credit_service import WebCrawlCreditService
from app.utils.captcha import captcha_enabled

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Each platform meter -> the config knob holding its micro-USD per-item rate.
# The rate is looked up live (not cached) so an env retune + restart takes
# effect without a code change, mirroring the crawl biller.
_PLATFORM_RATE_KEYS: dict[BillingUnit, str] = {
    BillingUnit.REDDIT_ITEM: "REDDIT_SCRAPE_MICROS_PER_ITEM",
    BillingUnit.GOOGLE_SEARCH_SERP: "GOOGLE_SEARCH_MICROS_PER_SERP",
    BillingUnit.GOOGLE_MAPS_PLACE: "GOOGLE_MAPS_MICROS_PER_PLACE",
    BillingUnit.GOOGLE_MAPS_REVIEW: "GOOGLE_MAPS_MICROS_PER_REVIEW",
    BillingUnit.AMAZON_PRODUCT: "AMAZON_MICROS_PER_PRODUCT",
    BillingUnit.YOUTUBE_VIDEO: "YOUTUBE_MICROS_PER_VIDEO",
    BillingUnit.YOUTUBE_COMMENT: "YOUTUBE_MICROS_PER_COMMENT",
    BillingUnit.INSTAGRAM_ITEM: "INSTAGRAM_SCRAPE_MICROS_PER_ITEM",
    BillingUnit.INSTAGRAM_COMMENT: "INSTAGRAM_SCRAPE_MICROS_PER_COMMENT",
    BillingUnit.TIKTOK_VIDEO: "TIKTOK_MICROS_PER_VIDEO",
    BillingUnit.TIKTOK_USER: "TIKTOK_MICROS_PER_USER",
    BillingUnit.TIKTOK_COMMENT: "TIKTOK_MICROS_PER_COMMENT",
    BillingUnit.CHAINLENS_QUERY: "CHAINLENS_QUERY_MICROS_PER_CALL",
    BillingUnit.BATDONGSAN_ITEM: "BATDONGSAN_SCRAPE_MICROS_PER_ITEM",
}


def _platform_rate(unit: BillingUnit) -> int:
    """Micro-USD per item for a platform meter, read live from config."""
    return int(getattr(config, _PLATFORM_RATE_KEYS[unit]))


# Display noun for each platform meter, e.g. "$3.50 / 1k places".
_UNIT_NOUNS: dict[BillingUnit, str] = {
    BillingUnit.REDDIT_ITEM: "item",
    BillingUnit.GOOGLE_SEARCH_SERP: "SERP",
    BillingUnit.GOOGLE_MAPS_PLACE: "place",
    BillingUnit.GOOGLE_MAPS_REVIEW: "review",
    BillingUnit.AMAZON_PRODUCT: "product",
    BillingUnit.YOUTUBE_VIDEO: "video",
    BillingUnit.YOUTUBE_COMMENT: "comment",
    BillingUnit.INSTAGRAM_ITEM: "item",
    BillingUnit.INSTAGRAM_COMMENT: "comment",
    BillingUnit.TIKTOK_VIDEO: "video",
    BillingUnit.TIKTOK_USER: "profile",
    BillingUnit.TIKTOK_COMMENT: "comment",
    BillingUnit.CHAINLENS_QUERY: "query",
    BillingUnit.BATDONGSAN_ITEM: "listing",
}


def pricing_meters(unit: BillingUnit | None) -> list[dict]:  # pragma: no mutate
    """The live per-item rates a verb charges, for UI display. Empty = free.

    Mirrors the gate/charge logic exactly: meters whose billing flag is off are
    omitted, so a self-hosted install with billing disabled reads as free.
    """
    if unit is None:
        return []
    if unit is BillingUnit.WEB_CRAWL:
        meters = []
        if WebCrawlCreditService.billing_enabled():
            meters.append(
                {"unit": "page", "micros_per_unit": config.WEB_CRAWL_MICROS_PER_SUCCESS}
            )
        if WebCrawlCreditService.captcha_billing_enabled() and captcha_enabled():
            meters.append(
                {
                    "unit": "captcha solve",
                    "micros_per_unit": config.WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE,
                }
            )
        return meters
    if not config.PLATFORM_SCRAPE_BILLING_ENABLED:
        return []
    meters = [{"unit": _UNIT_NOUNS[unit], "micros_per_unit": _platform_rate(unit)}]
    if unit is BillingUnit.GOOGLE_MAPS_PLACE:
        # Dual-metered: attached reviews bill on their own meter.
        meters.append(
            {
                "unit": _UNIT_NOUNS[BillingUnit.GOOGLE_MAPS_REVIEW],
                "micros_per_unit": _platform_rate(BillingUnit.GOOGLE_MAPS_REVIEW),
            }
        )
    return meters


async def gate_capability(
    payload: BillableInput,
    unit: BillingUnit | None,
    ctx: CapabilityContext,  # pragma: no mutate
) -> None:
    """Pre-flight: block an over-budget owner before the executor runs (03c).

    Raises ``InsufficientCreditsError`` when the wallet can't cover the input's
    worst-case ``estimated_units``. ``None`` unit = free = no gate.
    """
    if unit is None:
        return
    if unit is BillingUnit.WEB_CRAWL:
        await _gate_web_crawl(ctx, payload.estimated_units)
        return
    await _gate_platform(payload, unit, ctx)


async def _gate_web_crawl(ctx: CapabilityContext, estimated_successes: int) -> None:
    """Reserve the worst-case cost: crawl successes + worst-case captcha attempts.

    Captcha budget is only reserved when solving is actually enabled — with
    solving off, attempts can never happen, so reserving would wrongly block a
    run for captcha that will never be attempted. Mirrors the indexer path (3d).
    """
    service = WebCrawlCreditService(ctx.session)
    crawl_on = service.billing_enabled()
    captcha_on = service.captcha_billing_enabled() and captcha_enabled()
    if not crawl_on and not captcha_on:
        return
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return

    required_micros = 0
    if crawl_on:
        required_micros += service.successes_to_micros(estimated_successes)
    if captcha_on:
        worst_case_attempts = estimated_successes * config.CAPTCHA_MAX_ATTEMPTS_PER_URL
        required_micros += service.captcha_solves_to_micros(worst_case_attempts)
    await service.check_balance(owner_user_id, required_micros)


async def _gate_platform(
    payload: BillableInput, unit: BillingUnit, ctx: CapabilityContext
) -> None:
    """Reserve the worst-case per-item cost for a platform scraper verb.

    ``google_maps.scrape`` is dual-metered: it can attach reviews per place, so
    its gate also reserves ``estimated_review_units`` at the review rate — same
    two-meters-one-verb shape as crawl + captcha.
    """
    service = PlatformScrapeCreditService(ctx.session)
    if not service.billing_enabled():
        return
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return

    required_micros = service.items_to_micros(
        payload.estimated_units, _platform_rate(unit)
    )
    if unit is BillingUnit.GOOGLE_MAPS_PLACE:
        review_units = getattr(payload, "estimated_review_units", 0)
        required_micros += service.items_to_micros(
            review_units, _platform_rate(BillingUnit.GOOGLE_MAPS_REVIEW)
        )
    await wallet_credit.check_balance(ctx.session, owner_user_id, required_micros)


async def charge_capability(
    output: BillableOutput,
    unit: BillingUnit | None,
    ctx: CapabilityContext,  # pragma: no mutate
) -> int:
    """Bill the workspace owner for this result and return the micros charged.

    For crawl-backed verbs this also bills any captcha *attempts* (Phase 3d) as a
    separate per-attempt unit — the solver charges per attempt even when the crawl
    ultimately failed, so it can't ride the per-success crawl meter. Platform
    verbs bill per item returned; ``google_maps.scrape`` additionally bills its
    attached reviews. ``None`` unit = free = returns 0.

    The returned total lets the doors persist a per-run ``cost_micros``.
    """
    if unit is None:
        return 0
    if unit is BillingUnit.WEB_CRAWL:
        charged = await _charge_web_crawl(ctx, output.billable_units)
        charged += await _charge_captcha(ctx, getattr(output, "captcha_attempts", 0))
        return charged
    if unit is BillingUnit.CHAINLENS_QUERY:
        return await _charge_chainlens(output, ctx)
    return await _charge_platform(output, unit, ctx)


async def _charge_web_crawl(ctx: CapabilityContext, successes: int) -> int:
    if successes <= 0:
        return 0
    service = WebCrawlCreditService(ctx.session)
    if not service.billing_enabled():
        return 0
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return 0
    cost_micros = service.successes_to_micros(successes)
    # Stage the audit row before charge_credits' commit flushes both.
    await record_token_usage(
        ctx.session,
        usage_type="web_crawl",
        workspace_id=ctx.workspace_id,
        user_id=owner_user_id,
        cost_micros=cost_micros,
        call_details={"successes": successes},
    )
    await service.charge_credits(owner_user_id, successes)
    return cost_micros


async def _charge_captcha(ctx: CapabilityContext, attempts: int) -> int:
    if attempts <= 0:
        return 0
    service = WebCrawlCreditService(ctx.session)
    if not service.captcha_billing_enabled():
        return 0
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return 0
    cost_micros = service.captcha_solves_to_micros(attempts)
    # Stage the audit row before charge_captcha's commit flushes both.
    await record_token_usage(
        ctx.session,
        usage_type="web_crawl_captcha",
        workspace_id=ctx.workspace_id,
        user_id=owner_user_id,
        cost_micros=cost_micros,
        call_details={"attempts": attempts},
    )
    await service.charge_captcha(owner_user_id, attempts)
    return cost_micros


async def _charge_chainlens(output: BillableOutput, ctx: CapabilityContext) -> int:
    """Charge a deep-research call using the real cost from the engine.

    Falls back to the configured flat rate when the engine does not emit
    ``costDollars``. Always records a ``TokenUsage`` row so cost analytics
    work even when billing is disabled.
    """
    service = PlatformScrapeCreditService(ctx.session)
    billing_enabled = service.billing_enabled()
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return 0

    # Do not charge for a complete engine failure with no usable content.
    status = getattr(output, "status", None)
    has_content = bool(
        getattr(output, "answer", None) or getattr(output, "sources", None)
    )
    if status == "engine_unavailable" and not has_content:
        return 0

    cost_micros: int | None = getattr(output, "cost_micros", None)
    cost_basis: str | None = getattr(output, "cost_basis", None)
    resolved_mode: str | None = getattr(output, "resolved_mode", None)
    tokens_total: int | None = getattr(output, "tokens_total", None)
    mode_requested: str | None = getattr(output, "mode_requested", None)
    e2e_ms: int | None = getattr(output, "duration_ms", None)
    ttfb_ms: int | None = getattr(output, "first_token_time_ms", None)

    resolved_mode = resolved_mode or mode_requested

    if cost_micros is None:
        rate = _platform_rate(BillingUnit.CHAINLENS_QUERY)
        cost_micros = service.items_to_micros(1, rate)
        cost_basis = "fallback"
        logger.warning(
            "chainlens.research using fallback flat rate "
            "(%d micros) for workspace %s: no costDollars in SSE",
            cost_micros,
            ctx.workspace_id,
        )

    if cost_micros is None or cost_micros < 0:
        return 0

    call_details: dict[str, Any] = {
        "resolved_mode": resolved_mode,
        "mode_requested": mode_requested,
        "cost_basis": cost_basis,
        "tokens_total": tokens_total,
        "e2e_ms": e2e_ms,
        "ttfb_ms": ttfb_ms,
        "cost_dollars": float(Decimal(cost_micros) / Decimal("1000000")),
    }
    if getattr(output, "degraded", False):
        call_details["degradation_reason"] = (
            getattr(output, "degradation_reason", None) or "unknown"
        )
        call_details["final_status"] = getattr(output, "status", None) or "unknown"

    if not billing_enabled:
        await _record_deep_research_token_usage(
            ctx,
            owner_user_id,
            cost_micros,
            call_details,
            resolved_mode=resolved_mode,
            mode_requested=mode_requested,
            e2e_ms=e2e_ms,
            ttfb_ms=ttfb_ms,
        )
        return 0

    await wallet_credit.check_balance(ctx.session, owner_user_id, cost_micros)
    await _record_deep_research_token_usage(
        ctx,
        owner_user_id,
        cost_micros,
        call_details,
        resolved_mode=resolved_mode,
        mode_requested=mode_requested,
        e2e_ms=e2e_ms,
        ttfb_ms=ttfb_ms,
    )
    await wallet_credit.apply_debit(ctx.session, owner_user_id, cost_micros)
    return cost_micros


async def _record_deep_research_token_usage(
    ctx: CapabilityContext,
    owner_user_id: UUID,
    cost_micros: int,
    call_details: dict[str, Any],
    *,
    resolved_mode: str | None = None,
    mode_requested: str | None = None,
    e2e_ms: int | None = None,
    ttfb_ms: int | None = None,
) -> None:
    """Stage the audit row. Fail-open: log and continue if persistence fails."""
    try:
        await record_token_usage(
            ctx.session,
            usage_type="deep_research",
            workspace_id=ctx.workspace_id,
            user_id=owner_user_id,
            cost_micros=cost_micros,
            call_details=call_details,
            resolved_mode=resolved_mode,
            mode_requested=mode_requested,
            e2e_ms=e2e_ms,
            ttfb_ms=ttfb_ms,
        )
    except Exception:
        logger.exception("Failed to record deep_research token usage; continuing")


async def _charge_platform(
    output: BillableOutput, unit: BillingUnit, ctx: CapabilityContext
) -> int:
    """Charge a platform verb per item; dual-meter ``google_maps.scrape`` reviews."""
    service = PlatformScrapeCreditService(ctx.session)
    if not service.billing_enabled():
        return 0
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return 0

    charged = await _charge_platform_meter(
        service, ctx, owner_user_id, unit, output.billable_units, output
    )
    if unit is BillingUnit.GOOGLE_MAPS_PLACE:
        reviews = getattr(output, "attached_review_count", 0)
        charged += await _charge_platform_meter(
            service, ctx, owner_user_id, BillingUnit.GOOGLE_MAPS_REVIEW, reviews, output
        )
    return charged


async def _charge_platform_meter(
    service: PlatformScrapeCreditService,
    ctx: CapabilityContext,
    owner_user_id: UUID,
    unit: BillingUnit,
    items: int,
    output: BillableOutput,
) -> int:
    if items <= 0:
        return 0
    rate = _platform_rate(unit)
    cost_micros = service.items_to_micros(items, rate)
    # Stage the audit row before charge's commit flushes both.
    call_details: dict[str, Any] = {"items": items}
    if getattr(output, "degraded", False):
        call_details["degradation_reason"] = (
            getattr(output, "degradation_reason", None) or "unknown"
        )
        call_details["final_status"] = getattr(output, "status", None) or "unknown"
    await record_token_usage(
        ctx.session,
        usage_type=unit.value,
        workspace_id=ctx.workspace_id,
        user_id=owner_user_id,
        cost_micros=cost_micros,
        call_details=call_details,
    )
    await service.charge(owner_user_id, items, rate)
    return cost_micros


async def _resolve_workspace_owner(
    session: AsyncSession, workspace_id: int
) -> UUID | None:  # pragma: no mutate
    """The ``user_id`` that owns ``workspace_id`` (the crawl payer, not the caller)."""
    from app.db import Workspace

    result = await session.execute(
        select(Workspace.user_id).where(Workspace.id == workspace_id)
    )
    return result.scalar_one_or_none()
