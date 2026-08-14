---
baseline_commit: 22121a1b8
---

# Story 14.1: RSS Feed Integration

**Status:** in-progress
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

## Tasks / Subtasks

- [x] RSS connector plumbing
  - [x] `RSS_FEED` connector enum + migration `195_add_rss_news_connector_enums.py`
  - [x] `SearchSourceConnectorRoutes` + trigger route for RSS feeds
  - [x] Periodic scheduler + Celery registration (`index_rss_feeds`)
- [x] RSS fetching and parsing
  - [x] `app/services/news/rss_fetcher.py` — parse RSS 2.0 items (title, link, description, pubDate, category, source)
  - [x] `app/services/news/rss_config.py` — workspace `feed_urls` override + default 4 portals
  - [x] Namespace-aware parsing (`{*}` glob) for Atom / RSS 1.0 feeds
  - [x] Deterministic `_MISSING_PUB_DATE` sentinel (no re-index churn)
  - [x] Tuổi Trẻ naive `M/d/yyyy h:mm:ss AM/PM` pubDate fallback (UTC+7)
  - [x] Default feed list verified live against all 4 portals (2026-08-13); Vietnamnet `thoi-su.rss` (feeds tổng mới nhất)
- [x] Indexing + dedup (AD-27)
  - [x] `app/tasks/connector_indexers/rss_indexer.py` — document + canonical entity upsert
  - [x] Link-level dedup + `_news_fingerprint` + cross-portal canonical merge
  - [x] Degraded feeds degrade gracefully; `fetch_errors` surfaced
- [x] Security hardening (P0 code review)
  - [x] `validate_rss_feed_url` SSRF guard (http(s) only, public IP, no localhost/private)
  - [x] `validate_connector_config` `RSS_FEED` rule for `feed_urls`
  - [x] Redirect validation via `event_hooks` in `fetch_feed`
- [x] Tests
  - [x] Unit: `test_rss_fetcher.py` (8 tests incl. Atom namespace, private-IP reject, epoch pubDate, Tuổi Trẻ naive pubDate)
  - [x] Unit: `test_validators.py` RSS URL + connector config SSRF tests (2 added)
  - [x] Integration: `test_news_rss_integration.py`, `test_news_dedup.py`, `test_news_search.py` (5 tests)

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

- Review commit `6b7169380`; P0 fixes commit `6faee7e07`.
- SSRF: `httpx.AsyncClient` redirects re-validated via `event_hooks={"request": [_validate_rss_request]}` because initial URL validation alone is bypassed by `follow_redirects=True`.
- ElementTree namespace: `{*}item` glob matches any namespace (default or prefixed) — required for Atom (`http://www.w3.org/2005/Atom`) and RDF/RSS 1.0 (`http://purl.org/rss/1.0/`).

### Completion Notes List

- Story 14.1 implemented end-to-end (commit `6b7169380`) and hardened per adversarial review (commit `6faee7e07`, verdict PASS_WITH_WARNINGS).
- P0 findings closed: `validate_rss_feed_url` (http(s) only, public IP, no localhost/loopback/private/.local) + `RSS_FEED` rule in `validate_connector_config` + redirect re-validation; namespace-aware `{*}` parsing for Atom/RSS 1.0.
- P1 findings closed: deterministic `_MISSING_PUB_DATE` epoch sentinel stops 15-min re-index churn.
- P2+ findings accepted for pilot: `itertext()`/`content:encoded`, `<guid>` link fallback, `news_article` PII profile, `_news_fingerprint` normalization, feed size caps — tracked in code review file; default feed list is controlled (4 portals), so SSRF exposure is the only blocking risk and is now closed.
- This session: added 2 unit tests protecting the P0 SSRF guard (`test_validate_rss_feed_url`, `test_validate_connector_config_rss_feed_valid/invalid`); verified 8 news unit + 5 news integration tests green; ruff clean.
- Live API test (2026-08-13) found and fixed 2 real-world issues: Tuổi Trẻ pubDate format `M/d/yyyy h:mm:ss AM/PM` with U+202F narrow no-break space fell back to epoch → added `_VN_TZ` (UTC+7) fallback parser; Vietnamnet `tin-moi-nhat.rss`/`tin-tuc.rss` dead (404) or stale archive (2010–2022) → switched default to `vietnamnet.vn/rss/thoi-su.rss` (live, newest 2026-08-13). All 4 portals now fetch live (48–1000 items each).

### File List

- Added: `nowing_backend/alembic/versions/195_add_rss_news_connector_enums.py`
- Added: `nowing_backend/app/services/news/__init__.py`
- Added: `nowing_backend/app/services/news/rss_config.py`
- Added: `nowing_backend/app/services/news/rss_fetcher.py`
- Added: `nowing_backend/app/tasks/connector_indexers/rss_indexer.py`
- Added: `nowing_backend/app/tasks/celery_tasks/rss_tasks.py`
- Added: `nowing_backend/tests/unit/services/news/__init__.py`
- Added: `nowing_backend/tests/unit/services/news/test_rss_fetcher.py`
- Added: `nowing_backend/tests/integration/news/__init__.py`
- Added: `nowing_backend/tests/integration/news/conftest.py`
- Added: `nowing_backend/tests/integration/news/test_news_dedup.py`
- Added: `nowing_backend/tests/integration/news/test_news_rss_integration.py`
- Added: `nowing_backend/tests/integration/news/test_news_search.py`
- Updated: `nowing_backend/app/db.py` (RSS_FEED enum)
- Updated: `nowing_backend/app/celery_app.py` (task registration)
- Updated: `nowing_backend/app/utils/validators.py` (validate_rss_feed_url + RSS_FEED rule)
- Updated: `nowing_backend/app/routes/search_source_connectors_routes.py` (RSS trigger route)
- Updated: `nowing_backend/app/utils/periodic_scheduler.py` (RSS_FEED schedule)
- Updated: `nowing_backend/app/tasks/celery_tasks/schedule_checker_task.py` (RSS dispatch)
- Updated: `nowing_backend/tests/unit/utils/test_validators.py` (SSRF tests)
- Updated: `nowing_backend/tests/unit/services/news/test_rss_fetcher.py` (Tuổi Trẻ pubDate test)

### Change Log

- 2026-08-06: Implemented RSS connector end-to-end (fetch/parse/config/indexer/tasks) + tests; commit `6b7169380`.
- 2026-08-07: BMAD adversarial code review → PASS_WITH_WARNINGS (2 P0: SSRF, XML namespaces; P1: pubDate churn).
- 2026-08-07: Applied P0 fixes: `validate_rss_feed_url` + connector-config rule + redirect hooks + `{*}` namespace glob + epoch pubDate sentinel; commit `6faee7e07`.
- 2026-08-13: Verified suites green; added SSRF unit tests for validator; updated story file + sprint status → `review`.
- 2026-08-13: Live API test — fixed Tuổi Trẻ naive pubDate parsing (U+202F + `%m/%d/%Y %I:%M:%S %p`, UTC+7) and replaced dead Vietnamnet default feed (`tin-moi-nhat.rss` 404 / `tin-tuc.rss` archive) with live `thoi-su.rss`. 13 news tests green; all 4 portals fetch live.

## Status

review

### Review Findings

- [x] [Review][Resolved] Feed pruning policy — inline pruning in `index_rss_feeds` after `_persist_canonical_articles`: `RSS_RETENTION_DAYS=30`, hard delete of docs not seen in the current poll and older than the window (created_at proxy), plus canonical provenance + orphaned-entity sweep (`app/canonical/services/canonical_cleanup.py`); runs only on successful polls [rss_indexer.py:186]
- [x] [Review][Patch] SSRF DNS-name bypass (high) — validate_rss_feed_url only checks literal hostname string; nip.io/sslip.io/localtest.me resolve to internal/loopback IPs and are accepted; resolve via getaddrinfo at fetch time and require every address to be is_global [app/utils/validators.py:460]
- [x] [Review][Patch] Atom/RSS-1.0 ISO 8601 pubDates fall back to epoch sentinel (medium) — parsedate_to_datetime rejects ISO; add fromisoformat (Z→+00:00) before RFC822; add dc:date to tag list [rss_fetcher.py:43, :163]
- [x] [Review][Patch] Atom entry with first <link rel="self"> collapses the whole feed into one document (medium) — prefer rel="alternate"; skip links whose href equals the feed URL [rss_fetcher.py:149]
- [x] [Review][Patch] All feeds failing is logged as SUCCESS — fetch_feed always returns [], fetch_errors is dropped when all_articles is empty; surface warning/log_task_failure instead [rss_indexer.py:202, rss_fetcher.py:86]
- [x] [Review][Patch] No response-size cap + XML entity expansion (medium) — stream with byte cap (~20MB); reject <!DOCTYPE/<!ENTITY before parsing [rss_fetcher.py:99, :122]
- [x] [Review][Patch] _VN_TZ applied to every feed matching the US format (medium) — scope +7h to known Vietnamese domains; naive RFC822 currently stamped UTC [rss_fetcher.py:44, :53]
- [x] [Review][Patch] Fingerprint normalization (medium) — NFC normalize + collapse whitespace so the same article with different diacritic composition/spacing merges; when description==title use title-only seed to avoid false merges [rss_indexer.py:73]
- [x] [Review][Patch] Inline markup in <title> → "Untitled"; child tails lost in description; Atom <category term="..."> ignored (medium) — use itertext(); handle category term attribute [rss_fetcher.py:60, :148, :168]
- [x] [Review][Patch] No task time limit (medium) — add soft_time_limit/time_limit to index_rss_feeds_task; total-feed timeout [rss_tasks.py:12]
- [x] [Review][Patch] response.text ignores XML prolog encoding (low) — parse response.content bytes so ElementTree honors the prolog (UTF-16 feeds currently dropped) [rss_fetcher.py:106, :122]
- [x] [Review][Patch] _source_name_for_canonical returns channel title, not domain (low) — derive from feed URL host for stable cross-section attribution [rss_indexer.py:86]
- [x] [Review][Patch] HEARTBEAT_INTERVAL_SECONDS never used (low) — emit heartbeats during the article loop or drop the constant [rss_indexer.py:24, :286]
- [x] [Review][Patch] Partial/malformed US-format dates → epoch (low) — multi-attempt parse: drop seconds, tolerate missing meridiem, try %d/%m/%Y, 2-digit year [rss_fetcher.py:51]
- [x] [Review][Patch] Placeholder metadata lacks title; mark_connector_documents_failed never called (low) — include title; mark failed on except path [rss_indexer.py:246]
- [x] [Review][Patch] Default httpx User-Agent likely blocked by portals (low) — set browser-like UA; treat 403/429 distinctly [rss_fetcher.py:99]
- [x] [Review][Patch] Duplicate feed_urls cause double fetch (low) — dedup in validation or at fetch time [rss_config.py:15]
- [x] [Review][Patch] BASE_NAME_FOR_TYPE missing RSS_FEED entry (low) — falls back to generic "Rss Feed" naming [app/utils/connector_naming.py:18]
- [x] [Review][Patch] No test asserts DEFAULT_VIETNAMESE_FEEDS (low) — integration tests monkeypatch fetch_feed; add test asserting the 4 default URLs [rss_config.py:7]
- [x] [Review][Resolved] Canonical churn: `upsert_canonical_entity` skips version bump / merge history / embedding backfill when content unchanged and source did not move; still refreshes `last_seen_at`/`source_count` [canonical_persist_service.py:271]
- [x] [Review][Resolved] Epoch sentinel 1970-01-01 — kept in canonical data/metadata (anti-churn); RSS source markdown renders "Unknown" via `_format_pub_date` instead [rss_indexer.py:96]
- [x] [Review][Resolved] Connector deletion orphans canonical entities — delete route collects document links during batch deletion, then removes canonical sources by record_ids + sweeps orphaned `news_article` entities [search_source_connectors_routes.py:731]

### Re-review findings (2026-08-14) — all fixed

- [x] [Review][Resolved] `_extract_link` skips relative URLs and `<guid isPermaLink="true">` fallback (high) — added `_resolve_article_url` using `urljoin`; resolves relative `<link>` and Atom `href`, rejects fragment-only links; uses `<guid isPermaLink="true">` as fallback [rss_fetcher.py:130]
- [x] [Review][Resolved] No per-feed item-count cap (high) — added `_FEED_MAX_ITEMS = 1000`; `fetch_feed` truncates and logs when a feed exceeds the cap [rss_fetcher.py:27]
- [x] [Review][Resolved] No retry on 429 / 5xx (medium) — added `_FEED_RETRY_ATTEMPTS = 3` and exponential backoff in `fetch_feed`; 429 and 5xx are retried, 4xx fails fast [rss_fetcher.py:253]
- [x] [Review][Resolved] `socket.getaddrinfo` has no timeout (medium) — wrapped DNS resolution in `asyncio.wait_for` with `_FEED_TIMEOUT` [rss_fetcher.py:194]
- [x] [Review][Resolved] Pruning uses `Document.created_at` instead of article `pubDate` (medium) — `_prune_stale_articles` now parses `pubDate` from `document_metadata` and falls back to `created_at`; updated integration test to age `pubDate` metadata [rss_indexer.py:199]
- [x] [Review][Resolved] `fetch_feed` does not log a warning on HTTP 200 with empty body (low) — empty body now logs a warning and returns `[]` [rss_fetcher.py:238]
- [x] [Review][Resolved] Missing Playwright MCP smoke test (low) — added `tests/smoke/rss-dashboard.spec.ts` verifying the connectors page renders and the RSS card is visible [validation section]
- [x] [E2E] Playwright `rss-dashboard.spec.ts` passed locally after adding `RSS_FEED` to the web connector catalog (enum, zod schema, display definitions, icon)

### BMAD code review round 2 (2026-08-14)

- [x] [Review][Resolved] ElementTree expands internal entities — `<!DOCTYPE/<!ENTITY` scan only covered first 4 KB; full-body scan prevents billion-laughs DoS [rss_fetcher.py:344]
- [x] [Review][Resolved] `index_rss_feeds` missing final `session.commit()` — `upsert_canonical_entity` and `update_connector_last_indexed` do not commit internally; added final commit after indexing success [rss_indexer.py:449]
- [x] [Review][Resolved] `update_connector_last_indexed` uses naive local time — changed to `datetime.now(UTC)` [base.py:314]
- [x] [Review][Resolved] Articles with empty link/title silently skipped — added warning log so operators can detect malformed feeds [rss_indexer.py:370]
- [x] [Review][Resolved] `_prune_stale_articles` redundant `None` guard — removed unreachable second fallback after `_parse_meta_date(pub_date) or created_at` [rss_indexer.py:230]

**Deferred / dismissed (noise or pre-existing):**
- [ ] [Review][Defer] Sequential feed fetching — Celery task `time_limit` already bounds total runtime; concurrency is a future optimization [rss_indexer.py:327]
- [ ] [Review][Defer] Memory accumulation across many feeds — per-feed cap + Celery limits mitigate; streaming batching is future work [rss_indexer.py:324]
- [ ] [Review][Defer] Fingerprint collision with short descriptions — current 80-char seed is an intentional design trade-off; revisit if false-merge evidence appears [rss_indexer.py:121]
- [ ] [Review][Defer] IPv6 SSRF test coverage — logic uses `ipaddress.ip_address(...).is_global`; only unit tests were missing; IPv6 loopback test added [test_rss_fetcher.py]
- [ ] [Review][Defer] Date parsing misses RFC 2822 numeric timezones — current parser covers default feeds; `dateutil` fallback is future enhancement [rss_fetcher.py]
- [ ] [Review][Defer] Redirect `max_redirects`, per-connector feed count limit, configurable User-Agent, XML encoding fallback — non-blocking robustness items [rss_fetcher.py]
- [ ] [Review][Dismiss] DOCTYPE check was already case-insensitive via `.lower()` — finding was based on stale code reading [rss_fetcher.py:345]
