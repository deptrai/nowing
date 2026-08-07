# BMAD Code Review — Story 14.1: RSS Feed Integration

- **Commit reviewed:** `6b7169380`
- **Diff:** `_bmad-output/implementation-artifacts/code-review/diff-story-14.1.patch`
- **Story file:** `_bmad-output/implementation-artifacts/stories/14-1-rss-feed-integration.md`
- **Reviewer:** BMAD adversarial agent
- **Date:** 2026-08-07

## Verdict

**PASS_WITH_WARNINGS**

The core RSS → document pipeline works for the four hard-coded Vietnamese RSS 2.0 feeds, all new tests pass, and the canonical-entity deduplication path (AD-27) is wired correctly. However, adversarial probing found real gaps in XML/Atom parsing, SSRF/operational safety, error propagation, and PII handling that should be fixed or explicitly accepted before the connector is exposed to arbitrary workspace configs or external feeds.

## Static Analysis

```bash
cd nowing_backend
ruff check alembic/versions/195_add_rss_news_connector_enums.py \
  app/celery_app.py app/db.py \
  app/routes/search_source_connectors_routes.py \
  app/services/news/ app/tasks/celery_tasks/rss_tasks.py \
  app/tasks/celery_tasks/schedule_checker_task.py \
  app/tasks/connector_indexers/ app/utils/periodic_scheduler.py \
  tests/integration/news/ tests/unit/services/news/
```

Result: **All checks passed.**

## Automated Test Results

```bash
pytest tests/unit/services/news/test_rss_fetcher.py -q
# 4 passed, 7 warnings

pytest tests/integration/news/test_news_rss_integration.py \
       tests/integration/news/test_news_dedup.py \
       tests/integration/news/test_news_search.py -q
# 5 passed, 22 warnings
```

Both unit and integration suites pass. Tests cover RSS 2.0 parsing, workspace-level `feed_urls` override, link-level deduplication, canonical cross-portal merge, and unified search surfacing.

## Manual Adversarial Probes

A standalone probe was run against `app/services/news/rss_fetcher.py::fetch_feed` with synthetic feeds. Results:

| Feed type | Expected articles | Returned | Note |
|-----------|------------------|----------|------|
| Atom with default namespace (`http://www.w3.org/2005/Atom`) | 1 | **0** | Standard Atom feeds are silently dropped |
| RSS 1.0 with default namespace (`http://purl.org/rss/1.0/`) | 1 | **0** | RDF/RSS 1.0 feeds are silently dropped |
| RSS 2.0 with nested HTML in title (`<title>Foo <b>bar</b> baz</title>`) | 1 | 1 | Title returned as `'Foo'`, missing nested text `bar` |
| RSS 2.0 with `<content:encoded>` | 1 | 1 | Only `<description>` used; richer `content:encoded` ignored |
| RSS 2.0 with `<guid>` but no `<link>` | 1 | 1 | Link is empty; `<guid>` not used as fallback |
| RSS 2.0 with invalid `<pubDate>` | 1 | 1 | pub_date falls back to `datetime.now(UTC)`, which changes every call |

## Adversarial Findings

### 1. XML namespace handling is missing — Atom/RSS 1.0 feeds return zero articles

**File:** `nowing_backend/app/services/news/rss_fetcher.py`  
**Lines:** 93-109, 112-119

`xml.etree.ElementTree.find` and `findall` use local tag names without accounting for XML namespaces. A standard Atom feed declares `xmlns="http://www.w3.org/2005/Atom"`, so the real tag is `{http://www.w3.org/2005/Atom}entry`, not `entry`. The parser therefore finds no `item`/`entry` elements and returns `[]`.

This contradicts the code comment "Atom-style ... try first item" and breaks real-world feeds that use default namespaces. The same failure applies to RSS 1.0/RDF feeds.

**Recommendation:** Use namespace-aware parsing or strip namespaces before searching. `defusedxml` / `lxml` with namespace registration would be safer, but at minimum register a `{*}localname` glob:

```python
items = channel.findall(".//{*}item") or channel.findall(".//{*}entry")
```

### 2. `feed_urls` are not validated — SSRF and protocol abuse risk

**Files:**
- `nowing_backend/app/utils/validators.py:482-649` — no validation rule for `RSS_FEED`
- `nowing_backend/app/services/news/rss_config.py:15-19` — returns `connector_config["feed_urls"]` unchecked
- `nowing_backend/app/services/news/rss_fetcher.py:70-73` — `httpx.AsyncClient.get(url, follow_redirects=True)`

`validate_connector_config` has no entry for `RSS_FEED`, so any key/value is accepted. A workspace admin can set `feed_urls` to `file:///etc/passwd`, `http://169.254.169.254/`, or internal service endpoints. `httpx` follows redirects, enabling SSRF and internal network probing from the Celery worker.

**Recommendation:** Add an `RSS_FEED` rule in `validate_connector_config` that:
- Requires `feed_urls` to be a non-empty list of strings
- Validates each URL as `http(s)://` with a public/non-private host
- Rejects `file://`, `localhost`, loopback, and RFC 1918 addresses

### 3. No feed throttling, rate limiting, caching, or User-Agent

**File:** `nowing_backend/app/services/news/rss_fetcher.py:18-81`

- `_FEED_TIMEOUT = 10.0` is per feed, with no global cycle cap. If a workspace overrides `feed_urls` with a long list, the task can run for minutes and miss Celery timeouts.
- No `User-Agent` header; many portals block or rate-limit requests without one.
- No HTTP caching/ETag/Last-Modified handling, so every 15-minute poll re-downloads the whole feed, wasting bandwidth and accelerating rate-limit bans.

**Recommendation:** Add a shared `httpx.AsyncClient` with a configured `User-Agent`, an overall `feed_urls` request budget/timeout, and lightweight conditional GET using stored `last_modified`/`etag` values.

### 4. `pubDate` fallback to `datetime.now()` makes repeated polls non-idempotent

**File:** `nowing_backend/app/services/news/rss_fetcher.py:28-39`

When a feed lacks a parseable `pubDate`/`published`/`updated`, `_parse_pub_date` returns `datetime.now(UTC).isoformat()`. Because `source_markdown` includes `**Published:** {article.pub_date}` (`rss_indexer.py:31-34`), the document `content_hash` changes on every poll, even for the same article. This triggers:

- Re-indexing / embedding recomputation every 15 minutes
- Canonical entity version bumps every 15 minutes (`rss_indexer.py:522-544`)

**Recommendation:** Use a deterministic sentinel for unparseable dates, e.g. `datetime.fromtimestamp(0, tz=UTC).isoformat()` or the feed fetch time shared for the whole batch.

### 5. `_first_text` and `_strip_html` lose nested element text and ignore `content:encoded`

**File:** `nowing_backend/app/services/news/rss_fetcher.py:21-25, 42-48, 111-144`

`_first_text` reads `child.text` only, not `child.itertext()`. A title such as `<title>Foo <b>bar</b> baz</title>` returns `'Foo baz'`, dropping `bar`. The same applies to descriptions with inline HTML.

Additionally, `content:encoded` (RSS Content Module) is ignored even when `<description>` is empty or truncated; the richer body is never indexed.

**Recommendation:** Use `''.join(child.itertext())` to collect all text nodes, and fall back to `content:encoded` before stripping HTML.

### 6. Fetch errors are not surfaced when all feeds fail

**File:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:191-212`

`fetch_errors` is populated but the `if not all_articles:` branch returns `0, 0, None` at line 212, before the warning `f"{len(fetch_errors)} feed(s) failed to fetch"` is constructed at line 290-273. If every feed fails, the task reports success with no error/warning.

**Recommendation:** Return the joined `fetch_errors` string when `all_articles` is empty.

### 7. PII is not redacted from news article canonical data

**Files:**
- `nowing_backend/app/canonical/services/canonical_pii.py:44-50` — `news_article` has no domain-specific redaction rules
- `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:504-546` — `upsert_canonical_entity` stores title, description, and search text verbatim

The generic PII redactor only drops keys containing `phone`/`email`. News titles and descriptions frequently contain names, phone numbers, and addresses (e.g. accident reports, real estate listings, interviews). For `news_article`, these are stored unredacted in canonical data, search text, and source snapshots.

**Recommendation:** Add a `news_article` redaction profile or run an AD-25-style PII redactor over `search_text`, `title`, and `description` before canonical persistence.

### 8. `<guid>` is not used as a link fallback

**File:** `nowing_backend/app/services/news/rss_fetcher.py:112-119`

If an item has `<guid>` but no `<link>`, the article is skipped because `link` is empty. Many RSS feeds use `guid` as the canonical permalink.

**Recommendation:** Add `_first_text(item, "guid")` as a link fallback (only when `isPermaLink` is not `false`).

### 9. `update_connector_last_indexed` uses naive local time

**File:** `nowing_backend/app/tasks/connector_indexers/base.py:300-315`

`update_connector_last_indexed` sets `connector.last_indexed_at = datetime.now()` (naive local time). `rss_indexer.py` calls this at lines 183, 206, 269. On a server not in UTC, this pollutes `last_indexed_at` and can misalign the 15-minute schedule.

**Recommendation:** Change to `datetime.now(UTC)` (pre-existing base bug, but exercised by the new RSS code).

### 10. Dedup fingerprint is brittle and can over-merge

**File:** `nowing_backend/app/tasks/connector_indexers/rss_indexer.py:73-83`

`_news_fingerprint` hashes `title.lower()` + first 80 chars of `description.lower()`. Two unrelated follow-up stories with the same headline and similar opening sentence will collide. It also does not normalize Unicode punctuation or whitespace, so near-identical Vietnamese titles can produce different fingerprints.

**Recommendation:** Normalize whitespace, remove punctuation, and consider including a normalized link/domain seed in the fingerprint to reduce false positives.

### 11. No response size / feed item limits

**File:** `nowing_backend/app/services/news/rss_fetcher.py:70-75`

The entire response is loaded into `response.text` and parsed with `ET.fromstring`. A malicious or compromised feed can return a multi-hundred-megabyte XML body, causing worker OOM. There is also no cap on the number of `item`/`entry` elements processed.

**Recommendation:** Stream or cap the response read (`max_bytes`/`max_items`), and truncate the article list to a configurable maximum per feed.

## What Worked Well

- Clean separation of concerns: `rss_fetcher`, `rss_config`, `rss_indexer`, `rss_tasks`.
- Graceful degradation: one bad feed does not abort the whole poll.
- Link-level deduplication within a single poll is correct.
- Canonical entity upsert correctly merges syndicated articles across portals (verified by `test_news_dedup.py`).
- Integration with `IndexingPipelineService` and `UnifiedSearchService` is wired and tested.
- Celery queue registration, periodic scheduler registration, and route trigger are all in place.

## Recommendations Summary (Priority Order)

| Priority | Item |
|----------|------|
| P0 | Validate and restrict `feed_urls` to public `http(s)://` URLs to close SSRF |
| P0 | Add XML namespace handling for Atom/RSS 1.0 feeds |
| P1 | Make unparseable `pubDate` deterministic to avoid re-index churn |
| P1 | Add feed size limits and per-connector request budget |
| P1 | Add `User-Agent` and conditional GET caching |
| P2 | Use `itertext()` and `content:encoded` for richer, lossless parsing |
| P2 | Add `news_article` PII redaction profile |
| P2 | Use `<guid>` as link fallback and surface all-feed failures as warnings |
| P3 | Harden `_news_fingerprint` and use UTC in `update_connector_last_indexed` |

## Conclusion

Story 14.1 is functionally complete for its targeted RSS 2.0 Vietnamese feeds, but the connector as implemented is too permissive and too fragile for arbitrary or real-world feeds. The P0 SSRF and namespace gaps should be addressed before this is considered production-grade. The current state is acceptable for a controlled internal pilot under the existing default feed list.

---
*BMAD review: adversarial parsing, XML/Atom, SSRF, throttling, error handling, duplicate entries, PII, and rate-limit analysis performed. No push executed.*
