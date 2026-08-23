"""RSS news connector indexer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    ChainLensIngestJob,
    SearchSourceConnectorType,
)
from app.services.chainlens.ingest import NowingIngestService
from app.services.news.entity_extractor import (
    NewsEntityExtractor,
    mask_person_entities_in_text,
    redact_entities_metadata,
)
from app.services.news.rss_config import get_feeds_for_workspace
from app.services.news.rss_fetcher import NewsArticle, fetch_feed
from app.services.scraper_chunks.schemas import ChunkValidationError
from app.services.scraper_chunks.serializer import to_chunks
from app.services.task_logging_service import TaskLoggingService

from .base import get_connector_by_id, logger, update_connector_last_indexed

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30


def _domain_from_url(url: str | None) -> str:
    """Extract the canonical second-level domain from an article URL."""
    if not url:
        return "news"
    host = (urlparse(url).hostname or "news").lower().removeprefix("www.")
    return host or "news"


async def _persist_canonical_articles(
    session: AsyncSession,
    workspace_id: int,
    articles: list[NewsArticle],
    connector_id: int,
    user_id: str | None = None,
) -> tuple[int, int]:
    """Send RSS articles to chainlens-research via NowingIngestService with extracted entities."""
    fetched_at = datetime.now(UTC).isoformat()
    extractor = NewsEntityExtractor()
    chunks: list[Any] = []

    for article in articles:
        raw_text = (
            f"{article.title}\n\n{article.description}".strip()
            if article.description
            else article.title
        )
        try:
            entities = await extractor.extract(
                raw_text,
                workspace_id=workspace_id,
                session=session,
                user_id=user_id,
                article_link=article.link,
            )
        except Exception:
            logger.warning(
                "News entity extraction failed for article %s, degrading to empty",
                article.link,
                exc_info=True,
            )
            entities = []

        try:
            redacted_title = mask_person_entities_in_text(article.title or "", entities)
            redacted_desc = mask_person_entities_in_text(
                article.description or "", entities
            )
            redacted_metadata_entities = redact_entities_metadata(entities)
        except ChunkValidationError:
            logger.warning(
                "PII redaction failed for news article %s, skipping", article.link
            )
            continue
        except Exception:
            logger.exception(
                "Unexpected error during news redaction for %s", article.link
            )
            continue

        data = {
            "title": redacted_title,
            "link": article.link,
            "description": redacted_desc,
            "pubDate": article.pub_date,
            "category": article.category,
            "source": article.source,
            "entities": redacted_metadata_entities,
        }
        try:
            article_domain = _domain_from_url(article.link)
            chunks.extend(
                to_chunks(
                    domain="news",
                    metadata_domain=article_domain,
                    data=data,
                    fetched_at=fetched_at,
                    content_type="text/markdown",
                    category="news_article",
                )
            )
        except Exception:
            logger.exception("RSS article chunk serialization failed: %s", article.link)

    if not chunks:
        return 0, len(articles)

    try:
        ingest_service = NowingIngestService()
        result = await ingest_service.ingest(
            scraper_id="news.rss",
            chunks=chunks,
            workspace_id=workspace_id,
            session=session,
        )
        status_val = getattr(result, "status", "failed") if result else "failed"

        if status_val in ("ok", "noop"):
            return len(articles), 0

        if status_val == "partial":
            ingested = len(getattr(result, "ingested_source_ids", []) or [])
            noop = len(getattr(result, "noop_source_ids", []) or [])
            logger.warning(
                "chainlens_news_ingest_partial workspace_id=%s ingested=%s noop=%s",
                workspace_id,
                ingested,
                noop,
            )
            return len(articles), 0

        if status_val == "service_auth_unavailable":
            logger.warning(
                "chainlens_news_ingest_failed workspace_id=%s status=service_auth_unavailable error=%s",
                workspace_id,
                getattr(result, "error", None),
            )
            try:
                job = ChainLensIngestJob(
                    workspace_id=workspace_id,
                    scraper_id="news.rss",
                    status="failed",
                    error=getattr(result, "error", None),
                )
                session.add(job)
                await session.commit()
            except Exception:
                logger.warning(
                    "chainlens_ingest_job_persistence_failed workspace_id=%s",
                    workspace_id,
                    exc_info=True,
                )
            return 0, len(articles)

        job_id = getattr(result, "ingest_job_id", None)
        logger.warning(
            "chainlens_news_ingest_failed workspace_id=%s ingest_job_id=%s status=%s",
            workspace_id,
            job_id,
            status_val,
        )
        return 0, len(articles)
    except Exception:
        logger.exception("RSS chainlens ingest failed")
        return 0, len(articles)


async def index_rss_feeds(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    feed_urls: list[str] | None = None,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """Fetch configured RSS feeds and index the articles.

    Args:
        session: Database session.
        connector_id: RSS connector ID.
        workspace_id: Target workspace.
        user_id: User ID as a string.
        feed_urls: Optional explicit feed list; falls back to connector config.
        update_last_indexed: Whether to refresh last_indexed_at.
        on_heartbeat_callback: Optional progress callback.

    Returns:
        (indexed, skipped, warning_or_error)
    """
    task_logger = TaskLoggingService(session, workspace_id)
    log_entry = await task_logger.log_task_start(
        task_name="rss_feeds_indexing",
        source="connector_indexing_task",
        message=f"Starting RSS feed indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "feed_urls": feed_urls,
        },
    )

    try:
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.RSS_FEED
        )
        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, 0, f"Connector with ID {connector_id} not found"

        feed_urls = feed_urls or get_feeds_for_workspace(connector.config)
        if not feed_urls:
            logger.info("No feed URLs configured for RSS connector %s", connector_id)
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await task_logger.log_task_success(
                log_entry,
                "No RSS feed URLs configured; nothing to index",
                {"documents_indexed": 0},
            )
            return 0, 0, None

        all_articles: list[NewsArticle] = []
        fetch_errors: list[str] = []

        for url in feed_urls:
            try:
                articles = await fetch_feed(url)
                all_articles.extend(articles)
            except Exception as exc:
                logger.warning("Failed to fetch feed %s: %s", url, exc, exc_info=True)
                fetch_errors.append(f"{url}: {exc}")

        if not all_articles:
            if fetch_errors:
                # Every feed failed: report it as a failure, not a success
                # with "no articles found" (the errors were previously dropped).
                warning = f"{len(fetch_errors)} feed(s) failed to fetch"
                logger.warning(
                    "All RSS feeds failed for connector %s: %s",
                    connector_id,
                    "; ".join(fetch_errors),
                )
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )
                await task_logger.log_task_failure(
                    log_entry,
                    f"All RSS feeds failed for connector {connector_id}",
                    warning,
                    {"error_type": "AllFeedsFailed", "fetch_errors": fetch_errors},
                )
                return 0, 0, warning
            logger.info(
                "No articles returned from RSS feeds for connector %s", connector_id
            )
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await task_logger.log_task_success(
                log_entry,
                "No articles found in RSS feeds",
                {"documents_indexed": 0},
            )
            return 0, 0, None

        # Deduplicate by article link within this poll so the same link from
        # different feeds does not create duplicate documents.
        seen_links: set[str] = set()
        unique_articles: list[NewsArticle] = []
        for article in all_articles:
            if not article.link or not article.title:
                logger.warning(
                    "Skipping RSS article without link/title: title=%r link=%r",
                    article.title,
                    article.link,
                )
                continue
            if article.link in seen_links:
                continue
            seen_links.add(article.link)
            unique_articles.append(article)
            if on_heartbeat_callback and len(seen_links) % 50 == 0:
                await on_heartbeat_callback(len(seen_links))

        # Send to ChainLens via NowingIngestService (AD-34 / AD-35).
        indexed, _skipped_count = await _persist_canonical_articles(
            session,
            workspace_id=workspace_id,
            articles=unique_articles,
            connector_id=connector_id,
            user_id=user_id,
        )

        await update_connector_last_indexed(session, connector, update_last_indexed)

        warning = None
        if fetch_errors:
            warning = f"{len(fetch_errors)} feed(s) failed to fetch"

        await task_logger.log_task_success(
            log_entry,
            f"Completed RSS indexing for connector {connector_id}",
            {
                "documents_indexed": indexed,
                "documents_skipped": len(unique_articles) - indexed,
                "feed_count": len(feed_urls),
                "fetch_errors": len(fetch_errors),
            },
        )

        await session.commit()

        if on_heartbeat_callback:
            await on_heartbeat_callback(indexed)

        return indexed, len(unique_articles) - indexed, warning

    except Exception as exc:
        logger.error("Failed to index RSS feeds: %s", exc, exc_info=True)
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index RSS feeds for connector {connector_id}",
            str(exc),
            {"error_type": type(exc).__name__},
        )
        return 0, 0, f"Failed to index RSS feeds: {exc}"
