"""``tiktok.scrape`` executor: verb input → scraper → TikTok video items."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.capabilities.core import Executor
from app.capabilities.core.medirus_proxy import medirus_scrape_or_local
from app.capabilities.core.progress import emit_progress
from app.capabilities.tiktok.scrape.schemas import ScrapeInput, ScrapeOutput
from app.exceptions import ForbiddenError
from app.proprietary.platforms.tiktok import (
    TikTokAccessBlockedError,
    TikTokScrapeInput,
    scrape_tiktok,
)
from app.proprietary.platforms.tiktok.schemas import StartUrl

ScrapeFn = Callable[..., Awaitable[list[dict]]]


def build_scrape_executor(scrape_fn: ScrapeFn | None = None) -> Executor:
    """Bind the executor to a scraper fn (defaults to the proprietary actor)."""
    scrape_fn = scrape_fn or scrape_tiktok

    async def execute(payload: ScrapeInput) -> ScrapeOutput:
        actor_input = TikTokScrapeInput(
            startUrls=[StartUrl(url=str(u)) for u in payload.urls],
            profiles=payload.profiles,
            hashtags=payload.hashtags,
            resultsPerPage=payload.results_per_page,
        )
        emit_progress(
            "starting", "Resolving TikTok targets", total=payload.max_items, unit="item"
        )

        async def _local() -> list[dict]:
            try:
                return await scrape_fn(actor_input, limit=payload.max_items)
            except TikTokAccessBlockedError as exc:
                # Anonymous-only scraper; a hard block can't be retried with creds.
                raise ForbiddenError(
                    f"TikTok refused anonymous access: {exc}",
                    code="TIKTOK_ACCESS_BLOCKED",
                ) from exc

        # Medirus tiktok actions: search(query), hashtag_feed(tag),
        # post_detail/get_post_comments(videoId|url). Route only what it can
        # serve — profiles or multi-target mixes go straight to local.
        medirus_call: tuple[str, dict] | None = None
        if (
            payload.hashtags
            and len(payload.hashtags) == 1
            and not (payload.urls or payload.profiles)
        ):
            medirus_call = (
                "hashtag_feed",
                {"tag": payload.hashtags[0], "limit": payload.max_items},
            )
        elif (
            payload.urls
            and len(payload.urls) == 1
            and not (payload.profiles or payload.hashtags)
        ):
            medirus_call = (
                "post_detail",
                {"url": str(payload.urls[0]), "limit": payload.max_items},
            )
        if medirus_call is None:
            raw = {"items": await _local()}
        else:
            raw = await medirus_scrape_or_local(
                platform="tiktok",
                action=medirus_call[0],
                args=medirus_call[1],
                local_fn=_local,
            )
        items = raw.get("items", []) if isinstance(raw, dict) else raw
        emit_progress(
            "done", f"Scraped {len(items)} item(s)", current=len(items), unit="item"
        )
        return ScrapeOutput(items=items)

    return execute
