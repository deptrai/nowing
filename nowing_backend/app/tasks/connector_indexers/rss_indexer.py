"""RSS news connector indexer."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.canonical.services.canonical_cleanup import (
    delete_canonical_sources_by_record_ids,
    delete_orphaned_canonical_entities,
)
from app.canonical.services.canonical_persist_service import upsert_canonical_entity
from app.db import (
    Chunk,
    Document,
    DocumentStatus,
    DocumentType,
    SearchSourceConnectorType,
)
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
    PlaceholderInfo,
)
from app.services.news.rss_config import get_feeds_for_workspace
from app.services.news.rss_fetcher import _MISSING_PUB_DATE, NewsArticle, fetch_feed
from app.services.task_logging_service import TaskLoggingService

from .base import get_connector_by_id, logger, update_connector_last_indexed

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30

# Articles are pruned when they have not been seen in a feed for this long.
# RSS feeds are rolling windows (typically 24-48h), so anything unseen for a
# month is definitively gone from the source and its indexed copy is stale.
RSS_RETENTION_DAYS = 30


def _format_pub_date(article: NewsArticle) -> str:
    """Human-readable publish date for display text.

    When the feed omits ``pubDate`` the fetcher records a deterministic
    1970-01-01 sentinel in canonical data (anti-churn); render it as
    "Unknown" instead of leaking the epoch sentinel into searchable text.
    """
    if article.pub_date and not article.pub_date.startswith("1970-01-01"):
        return article.pub_date
    return "Unknown"


def _build_source_markdown(article: NewsArticle) -> str:
    """Create clean markdown content for indexing and search."""
    parts = [f"# {article.title}", ""]
    parts.append(f"**Source:** {article.source}")
    if article.category:
        parts.append(f"**Category:** {article.category}")
    parts.append(f"**Published:** {_format_pub_date(article)}")
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


def _normalise_text(value: str) -> str:
    """NFC-normalize and collapse whitespace so the same title written with
    differently composed diacritics or spacing still fingerprints identically."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip().lower()


def _news_fingerprint(article: NewsArticle) -> str:
    """Stable fingerprint for cross-portal deduplication.

    Normalised title plus the first 80 characters of the description is
    enough to catch syndicated articles while still distinguishing genuine
    follow-up stories. When the description is empty or just repeats the
    title, the title alone is the seed so the same headline from two portals
    still merges instead of falsely splitting.
    """
    normalised_title = _normalise_text(article.title)
    description_seed = _normalise_text(article.description)[:80]
    if not description_seed or description_seed == normalised_title:
        combined = normalised_title
    else:
        combined = f"{normalised_title}|{description_seed}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _source_name_for_canonical(article: NewsArticle) -> str:
    """Use the article URL's domain as the canonical source name.

    Channel titles vary per feed section (e.g. "Thời sự" vs "Thế giới" on
    the same portal); the domain keeps cross-section attribution stable.
    """
    try:
        host = urlparse(article.link).hostname or ""
    except ValueError:
        host = ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or article.source


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


def _parse_meta_date(pub_date: str | None) -> datetime | None:
    """Return a parsed UTC datetime from stored metadata pubDate.

    Falls back to ``None`` for the epoch sentinel or unparseable values so the
    caller can use ``Document.created_at`` instead.
    """
    if not pub_date or pub_date.startswith(_MISSING_PUB_DATE.isoformat()):
        return None
    try:
        return datetime.fromisoformat(pub_date)
    except ValueError:
        return None


async def _prune_stale_articles(
    session: AsyncSession,
    *,
    connector_id: int,
    workspace_id: int,
    seen_links: set[str],
) -> int:
    """Delete articles that left the feed's rolling window.

    Articles not seen in the current poll and older than the retention window
    are gone from the source; remove their documents, canonical provenance
    rows and any canonical entities left without sources.
    """
    cutoff = datetime.now(UTC) - timedelta(days=RSS_RETENTION_DAYS)
    link_expr = Document.document_metadata["link"].as_string()
    pub_date_expr = Document.document_metadata["pubDate"].as_string()
    result = await session.execute(
        select(Document.id, link_expr, pub_date_expr, Document.created_at).where(
            Document.workspace_id == workspace_id,
            Document.connector_id == connector_id,
            Document.document_type == DocumentType.NEWS_CONNECTOR,
            ~link_expr.in_(seen_links),
        )
    )
    rows = result.fetchall()
    if not rows:
        return 0

    prunable_ids: list[int] = []
    pruned_links: list[str] = []
    for doc_id, link, pub_date, created_at in rows:
        article_date = _parse_meta_date(pub_date) or created_at
        if article_date and article_date < cutoff:
            prunable_ids.append(doc_id)
            if link:
                pruned_links.append(link)

    if not prunable_ids:
        return 0

    doc_ids = prunable_ids

    # Chunks first, then the document rows (mirrors delete_document_task).
    batch_size = 500
    for start in range(0, len(doc_ids), batch_size):
        batch = doc_ids[start : start + batch_size]
        await session.execute(sa_delete(Chunk).where(Chunk.document_id.in_(batch)))
    await session.execute(sa_delete(Document).where(Document.id.in_(doc_ids)))

    # Remove canonical provenance for the pruned articles, then sweep any
    # entities left without sources.
    await delete_canonical_sources_by_record_ids(session, workspace_id, pruned_links)
    await delete_orphaned_canonical_entities(
        session, workspace_id, entity_types=["news_article"]
    )
    await session.commit()

    logger.info(
        "Pruned %d stale article(s) for RSS connector %s", len(doc_ids), connector_id
    )
    return len(doc_ids)


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
                        "title": doc.title,
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

        # Rolling-window retention: drop articles that left the feed long ago.
        await _prune_stale_articles(
            session,
            connector_id=connector_id,
            workspace_id=workspace_id,
            seen_links=seen_links,
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
