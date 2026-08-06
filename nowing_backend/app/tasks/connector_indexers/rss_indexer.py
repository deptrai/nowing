"""RSS news connector indexer."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.db import DocumentStatus, DocumentType, SearchSourceConnectorType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
    PlaceholderInfo,
)
from app.services.news.rss_config import get_feeds_for_workspace
from app.services.news.rss_fetcher import NewsArticle, fetch_feed
from app.services.task_logging_service import TaskLoggingService

from .base import get_connector_by_id, logger, update_connector_last_indexed

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30


def _build_source_markdown(article: NewsArticle) -> str:
    """Create clean markdown content for indexing and search."""
    parts = [f"# {article.title}", ""]
    parts.append(f"**Source:** {article.source}")
    if article.category:
        parts.append(f"**Category:** {article.category}")
    parts.append(f"**Published:** {article.pub_date}")
    parts.append("")
    parts.append(article.description)
    parts.append("")
    parts.append(f"**Link:** {article.link}")
    return "\n".join(parts)


def _build_connector_doc(
    article: NewsArticle,
    *,
    connector_id: int,
    workspace_id: int,
    user_id: str,
) -> ConnectorDocument:
    """Map a parsed news article to a ConnectorDocument."""
    metadata = {
        "title": article.title,
        "link": article.link,
        "description": article.description,
        "pubDate": article.pub_date,
        "category": article.category,
        "source": article.source,
        "connector_id": connector_id,
        "document_type": "News Article",
        "connector_type": "RSS Feed",
    }

    return ConnectorDocument(
        title=article.title,
        source_markdown=_build_source_markdown(article),
        unique_id=article.link,
        document_type=DocumentType.NEWS_CONNECTOR,
        workspace_id=workspace_id,
        connector_id=connector_id,
        created_by_id=user_id,
        metadata=metadata,
    )


def _news_fingerprint(article: NewsArticle) -> str:
    """Stable fingerprint for cross-portal deduplication.

    Normalised title plus the first 80 characters of the description is
    enough to catch syndicated articles while still distinguishing genuine
    follow-up stories.
    """
    normalised_title = article.title.strip().lower()
    description_seed = article.description.strip().lower()[:80]
    combined = f"{normalised_title}|{description_seed}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _source_name_for_canonical(article: NewsArticle) -> str:
    """Use the article's source domain as the canonical source name."""
    return article.source


async def _persist_canonical_articles(
    session: AsyncSession,
    workspace_id: int,
    articles: list[NewsArticle],
    connector_id: int,
) -> None:
    """Upsert canonical entities so syndicated articles merge across portals."""
    for article in articles:
        fingerprint = _news_fingerprint(article)
        search_text = f"{article.title} {article.description}"
        if article.category:
            search_text = f"{search_text} {article.category}"

        data = {
            "title": article.title,
            "link": article.link,
            "description": article.description,
            "pubDate": article.pub_date,
            "category": article.category,
            "source": article.source,
        }

        await upsert_canonical_entity(
            session,
            workspace_id=workspace_id,
            entity_type="news_article",
            fingerprint=fingerprint,
            title=article.title,
            data=data,
            search_text=search_text,
            source_name=_source_name_for_canonical(article),
            source_record_id=article.link,
            source_url=article.link,
            source_snapshot=data,
            source_fingerprint=fingerprint,
            confidence_score=0.9,
            actor=f"rss-connector:{connector_id}",
            merge_method="rss_fingerprint",
        )


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
                continue
            if article.link in seen_links:
                continue
            seen_links.add(article.link)
            unique_articles.append(article)

        # Placeholders give instant UI feedback before slow embedding/chunking.
        pipeline = IndexingPipelineService(session)
        connector_docs = [
            _build_connector_doc(
                article,
                connector_id=connector_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            for article in unique_articles
        ]
        await pipeline.create_placeholder_documents(
            [
                PlaceholderInfo(
                    title=doc.title,
                    document_type=doc.document_type,
                    unique_id=doc.unique_id,
                    workspace_id=doc.workspace_id,
                    connector_id=doc.connector_id,
                    created_by_id=doc.created_by_id,
                    metadata={
                        "link": doc.unique_id,
                        "connector_id": connector_id,
                        "connector_type": "RSS Feed",
                    },
                )
                for doc in connector_docs
            ]
        )

        results = await pipeline.index_batch(connector_docs)

        indexed = sum(
            1
            for doc in results
            if DocumentStatus.is_state(doc.status, DocumentStatus.READY)
        )

        # Canonical upsert provides cross-portal deduplication (AD-27).
        await _persist_canonical_articles(
            session, workspace_id, unique_articles, connector_id
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
