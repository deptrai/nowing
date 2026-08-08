# Story 14.1: RSS Feed Integration

**Status:** done
**Epic:** Epic 14 — News Aggregation (Vietnam)
**Priority:** P0

## Story

As a user,
I want news from major Vietnamese portals available in my workspace,
So that I can search and reference news articles alongside my research documents.

## Acceptance Criteria

- **Given** RSS feeds are configured, **When** the system polls (every 15 min), **Then** new articles from VnExpress, Tuổi Trẻ, Dân Trí, Vietnamnet are fetched and stored.
- **Given** articles are fetched, **When** stored, **Then** each article has: title, link, description, pubDate, category, source.
- **Given** articles are stored, **When** a user searches, **Then** news articles appear in unified search results.
- **Given** duplicate articles (syndicated across portals), **When** detected, **Then** they are deduplicated via canonical entity convention (AD-27).

## Validation

- Integration test: `test_news_rss_integration.py` — all 4 portals polled.
- Unit test: `test_news_dedup.py` — syndicated articles deduplicated.
- Search test: `test_news_search.py` — articles appear in search results.
- Playwright MCP smoke: dashboard loads after changes.

## Tags

AD-27, AD-2, RSS, news, VnExpress, TuoiTre, DanTri, Vietnamnet
