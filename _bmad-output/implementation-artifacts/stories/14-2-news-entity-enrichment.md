---
baseline_commit: d3c10413812e5a801a22c2ec05043fe0dd24e7ef
status: ready-for-dev
---

# Story 14.2: News Entity Enrichment

**Status:** ready-for-dev
**Epic:** Epic 14 — News Aggregation (Vietnam)
**Priority:** P1

## Story

As a researcher,
I want key entities (people, organizations, locations) attached to news chunks before they are indexed,
So that I can track mentions and trends via `chainlens-research` entity search.

## Acceptance Criteria

1. **Given** a news article is parsed, **When** entity extraction runs, **Then** named entities (people, organizations, locations) are extracted with confidence scores.
2. **Given** extracted entities, **When** the article is normalized to a `Chunk`, **Then** `metadata.entities` contains the entity mentions, types, and surface forms.
3. **Given** a `Chunk` with `metadata.entities`, **When** it is ingested into `chainlens-research`, **Then** the canonical index stores and indexes the entity metadata; `chainlens-research` handles entity linking and disambiguation.
4. **Given** entity tracking is active, **When** a user queries an entity in chat, **Then** the agent calls `chainlens-research` and returns mentioning articles with citations; no local entity table is built in Nowing.
5. **Given** entity extraction model returns empty entity list or malformed JSON, **When** entity enrichment runs, **Then** it falls back to `metadata.entities = []` and the article is still indexed.
6. **Given** the workspace has insufficient premium credit for entity extraction, **When** `QuotaInsufficientError` is raised, **Then** extraction degrades to `metadata.entities = []`, logs `news_entity_extraction_quota_exhausted`, and the article is still indexed.
7. **Given** `NowingIngestService` fails to ingest a news `Chunk[]` to `chainlens-research` (5xx, auth unavailable, timeout, max retries), **When** the failure occurs, **Then** it logs `chainlens_news_ingest_failed`, emits a metric, persists a `ChainLensIngestJob` with status `failed`, continues processing the rest of the batch, and does **not** fall back to a local `Document`/`Chunk` index (AD-35).

## Validation

- Unit test: `test_news_entity_extraction.py` — entity accuracy ≥ 0.85
- Integration test: `test_news_entity_chunk_metadata.py` — entities attached to chunk metadata
- Integration test: `test_news_entity_search_chainlens.py` — entity query returns indexed articles

## Tags

AD-34, AD-35, AD-25, news, NER, entity-extraction, chainlens, rss, PII-redaction

## Tasks / Subtasks

- [ ] Define entity extraction contract (AC: #1, #2)
  - [ ] Add `app/services/news/entities.py` with `NewsEntity` Pydantic model: `text`, `type` (`person`, `organization`, `location`), `confidence` (0.0–1.0), `surface_forms`.
  - [ ] Add `NewsEntityList` Pydantic model for structured output.
  - [ ] Add `NewsEntityExtractor` with async `extract(article_text: str, workspace_id: int, session: AsyncSession) -> list[NewsEntity]`.
  - [ ] **Entity quality gates**: confidence threshold `≥ 0.6`; deduplicate by `(type, normalized_text)` keeping highest confidence.
- [ ] Implement extraction backend (AC: #1, #5)
  - [ ] Use `app.services.llm_service.get_vision_llm(session, workspace_id)` (quota-enforced, bills workspace owner) or `get_agent_llm` if vision quota is not configured; wrap with `QuotaCheckedVisionLLM` where available.
  - [ ] Use `langchain_core.messages.HumanMessage` + `with_structured_output(NewsEntityList)` or manual JSON-parse if quota wrapper cannot use `with_structured_output`.
  - [ ] **Prompt template** (Vietnamese): extract people, organizations, locations; return `text`, `type`, `confidence`, `surface_forms`.
  - [ ] Add malformed/empty JSON fallback returning `[]` and log `news_entity_extraction_fallback` counter.
  - [ ] Add `QuotaInsufficientError` catch (AC-6): log `news_entity_extraction_quota_exhausted`, set `metadata.entities = []`, continue indexing.
  - [ ] Add LLM timeout/rate-limit degradation: log `news_entity_extraction_degraded`, continue with empty entities.
  - [ ] Cache results per article in Redis (TTL 1h) using key `news_entity:{workspace_id}:{sha256(article.link).hexdigest()}`.
  - [ ] **Cost tracking**: every extraction call writes `TokenUsage` with `usage_type="entity_extraction"` or uses the existing token tracker; do not bypass wallet.
- [ ] PII redaction guard for person names (AD-25) (AC: #1)
  - [ ] **Redaction order**: extract entities FIRST, then redact:
    1. Run extraction on raw article text.
    2. Redact article content with `redact_pii(article_text, context="default")` → `Chunk.content`.
    3. Redact each `person` surface form with `redact_pii(surface_form, context="default")` → masked `<NAME>`.
    4. Store redacted surface forms in `metadata.entities`; keep `type`, `confidence`, `surface_forms`.
  - [ ] Ensure raw person names never appear in `Chunk.content`, `metadata.entities`, `Memory`, logs, or UI.
  - [ ] If a `news` context is needed to avoid over-redacting organizations/locations, add it to `app/services/pii/redact.py` as a thin alias of `default`.
- [ ] Refactor news indexing to `NowingIngestService` (AC: #2, #3)
  - [ ] Replace `IndexingPipelineService.index_batch()` in `app/tasks/connector_indexers/rss_indexer.py` with `NowingIngestService().ingest(scraper_id="news.rss", chunks=..., workspace_id=..., session=...)`.
  - [ ] Build `Chunk[]` for each article. **Two implementation options (pick one)**:
    - **Option A (preferred)**: extend `app/services/scraper_chunks/serializer.py` for `news` domain:
      - Add `_NEWS_DOMAINS = {"news"}` and `_is_news_domain()`.
      - `_required_fields("news")` = `["title", "description"]`.
      - `_build_content("news", data)` formats `Title`, `Description`, `Source`, `Category`, `PubDate`, `Link` and redacts text.
      - `_identity_fields("news", data)` uses `link` (stable article URL) and `pubDate`.
      - `_metadata_from_data` for news sets `contentType="news"`, `url=link`, `title`, `category`, `pubDate`, and `entities` (passed through `data["entities"]`).
      - Call `to_chunks(domain="news", data=article_dict, fetched_at=..., content_type="news", category=article.category)`.
    - **Option B (fallback)**: build `Chunk` manually in `rss_indexer.py`:
      - Use `app.indexing_pipeline.chunking.chunk_markdown` or `app.services.scraper_chunks.serializer._split_tokens` (if exported) to split oversize content.
      - Construct `Chunk(content=piece, metadata=ChunkMetadata(source="nowing_scraper", sourceId=..., domain="news", fetchedAt=..., contentType="news", title=..., url=..., category=..., pubDate=..., entities=[...]))`.
  - [ ] Ensure AD-34 metadata: `source: 'nowing_scraper'`, `sourceId` stable URL hash, `domain: 'news'`, `fetchedAt` ISO-8601, `contentType: 'news'`, `entities` list.
  - [ ] Remove local `Document`/`Chunk`/`CanonicalEntity` persistence for news (replaces 14.1 local-indexing path; AD-35).
  - [ ] Keep deduplication by `sourceId` (article link hash) so chainlens-research receives idempotent chunks.
  - [ ] Store `ingestJobId` from `NowingIngestService` in `ChainLensIngestJob` for monitoring (service already does this when `session` is passed).
  - [ ] Add `NowingIngestService` failure handling (AC-7): if status is `failed`/`service_auth_unavailable`/`partial`, log `chainlens_news_ingest_failed`, emit metric, continue processing the rest of the batch, and do **not** create local `Document`/`Chunk` fallback.
- [ ] Update chunk/ingest schema (AC: #2)
  - [ ] Add `entities: list[dict[str, Any]] | None = None` field to `ChunkMetadata` in `app/services/scraper_chunks/schemas.py` (or rely on `extra="allow"` but be explicit for documentation).
  - [ ] Add `pubDate` and `source` optional fields to `ChunkMetadata` if not already present.
- [ ] ChainLens entity search contract (AC: #3, #4)
  - [ ] Verify ChainLens `POST /api/v1/search` (or equivalent) supports entity filters.
  - [ ] If contract not ready, stub in integration tests and file follow-up story `14-3` for entity search UI/agent wiring.
  - [ ] Document the expected request/response shape in `tests/integration/news/test_news_entity_search_chainlens.py`.
- [ ] Tests
  - [ ] Unit: `tests/unit/services/news/test_entity_extractor.py` — mock LLM, assert `person`/`organization`/`location`, fallback, PII redaction, confidence threshold, deduplication.
  - [ ] Unit: `tests/unit/services/news/fixtures/entity_extraction_golden.json` — 10 golden Vietnamese snippets (mix VnExpress/Tuổi Trẻ/Dân Trí/Vietnamnet) with labeled entities.
  - [ ] Integration: `tests/integration/news/test_news_entity_chunk_metadata.py` — run `index_rss_feeds` and assert `NowingIngestService.ingest()` called with `metadata.entities` and correct AD-34 fields.
  - [ ] Integration: `tests/integration/news/test_news_entity_search_chainlens.py` — mock chainlens ingest and search endpoints; assert entity query returns articles.
- [ ] Update 14.1 tests after refactor
  - [ ] `tests/integration/news/test_news_rss_integration.py` — assert `ChainLensIngestJob` created / `NowingIngestService.ingest()` called, not `Document` count.
  - [ ] `tests/integration/news/test_news_search.py` — replace local `UnifiedSearchService` query with stubbed chainlens search (or delete if now chainlens-owned).
  - [ ] `tests/integration/news/test_news_dedup.py` — assert idempotent `sourceId` / chainlens noop instead of local canonical merge.
  - [ ] `tests/unit/services/news/test_rss_fetcher.py` — unchanged (parsing only).

## Dev Notes

### Current state from Story 14.1

- `app/services/news/rss_fetcher.py` parses RSS/Atom into `NewsArticle` (`title`, `link`, `description`, `pub_date`, `category`, `source`).
- `app/tasks/connector_indexers/rss_indexer.py` currently calls `IndexingPipelineService.index_batch()` → persists `Document`/`Chunk` in local Postgres and upserts `CanonicalEntity`.
- This local-news-index path violates AD-35 (Nowing does not build a public/vertical search corpus). Story 14.2 must replace it with `NowingIngestService` → `chainlens-research`.
- `app/canonical/services/unified_search_service.py` is local-only; news search will be delegated to `chainlens-research`.
- Tests in `tests/integration/news/` currently assert local `Document`/`Chunk` rows; they must be updated to assert the `NowingIngestService` contract.

### Architecture compliance

- **AD-34 — Nowing Scraper Feed Contract**: canonical `Chunk[]` must have `source: 'nowing_scraper'`, `sourceId`, `domain: 'news'`, `fetchedAt`, `contentType: 'news'`, plus optional `metadata.entities`.
- **AD-35 — Nowing Does Not Build Public/Vertical Search Corpus**: news search goes through `chainlens-research` only; no local `Document`/`Chunk` corpus for news.
- **AD-25 — Unified PII Redaction Pipeline**: redact person names via `app/services/pii/redact.py` before storage; do not create a separate news redaction module.
- **AD-27 — Nowing Domain Scraper Output Feeds chainlens-research**: entity linking/disambiguation happens in `chainlens-research`; Nowing sends surface-level entities only.

### File structure & conventions

- New code: `app/services/news/entities.py`, `app/services/news/entity_extractor.py`.
- Modify: `app/tasks/connector_indexers/rss_indexer.py`, `app/services/scraper_chunks/schemas.py` (explicit `entities`), optionally `app/services/scraper_chunks/serializer.py` for news domain.
- Reuse: `app/services/llm_service.py`, `app/services/pii/redact.py`, `app/services/chainlens/ingest.py`.
- No DB migration for `Chunk` table if using `NowingIngestService` (chunks live in chainlens-research).

### Library / framework requirements

- `pydantic` for `NewsEntity` and `NewsEntityList`.
- `langchain_core.messages.HumanMessage` + `with_structured_output` (or manual JSON parse wrapped in `QuotaCheckedVisionLLM.ainvoke`).
- `redis.asyncio` for per-article extraction cache.
- Existing token tracker (`app.services.token_tracking_service`) or `QuotaCheckedVisionLLM` for cost attribution.

### Testing standards

- Unit tests must mock the LLM; no live provider calls.
- Accuracy ≥ 0.85 against 10 hand-labeled golden Vietnamese snippets.
- Integration tests require PostgreSQL + Redis; mark with `@pytest.mark.integration`.
- Mock `chainlens-research` with `respx` or `httpx` transport; do not require a live ChainLens instance.

### Previous story intelligence (Story 14.1)

- Story 14.1 file: `stories/14-1-rss-feed-integration.md`.
- Relevant learnings:
  - `rss_fetcher.py` returns `NewsArticle` with `title`, `link`, `description`, `pub_date`, `category`, `source`.
  - RSS feeds are polled every 15 min via Celery task `index_rss_feeds`.
  - SSRF guard `validate_rss_feed_url` in `app/utils/validators.py` — reuse if any new feed fetch logic is added.
  - **14.1 indexed news locally, which now violates AD-35. 14.2 must replace this path.**

### Latest technical specifics

- `ChunkMetadata` (`app/services/scraper_chunks/schemas.py`) uses `extra="allow"`, so `entities`, `pubDate`, and `source` can be added without breaking existing consumers.
- `NowingIngestService` (`app/services/chainlens/ingest.py`) supports 1000-chunk pagination, `409` noop, `5xx` retry, and parent/child `ingestJobId` tracking. Pass `session` to persist `ChainLensIngestJob`.
- `app/services/pii/redact.py` supports `default`, `job_data`, `lead_enrichment`. Add `news` context only if the rule set must diverge; otherwise `default` is sufficient.
- `scraper_chunks/serializer.py` currently has no `news` domain; it defaults to listing-style fields (`title`, `city`, `district`, `price`) which will fail. Either extend `to_chunks` for `news` or build `Chunk[]` manually.

### References

- Source: `_bmad-output/planning-artifacts/epics.md` lines 2059–2101 (Epic 14, Story 14.2)
- Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` AD-25, AD-27, AD-34, AD-35
- Source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-07-25-chainlens-engine-boundary.md` (Nowing = product, ChainLens = engine; no local public corpus)
- Source: `nowing_backend/app/tasks/connector_indexers/rss_indexer.py`
- Source: `nowing_backend/app/services/scraper_chunks/schemas.py` and `serializer.py`
- Source: `nowing_backend/app/services/chainlens/ingest.py`
- Source: `nowing_backend/app/services/pii/redact.py`
- Source: `nowing_backend/_bmad-output/implementation-artifacts/stories/14-1-rss-feed-integration.md`

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

- Validation run: applied `bmad-create-story` checklist (8 critical, 6 enhancement, 4 optimization findings).

### Completion Notes List

- Created story 14.2 from Epic 14 backlog.
- After validation: removed local-indexing Option B; mandated `NowingIngestService` path per AD-34/AD-35.
- Added explicit AD-34 metadata, `scraper_chunks/serializer.py` news-domain extension, PII redaction order, model/prompt guidance, cost tracking, Redis cache key, golden test data, and ChainLens search contract verification.

### File List

- New: `_bmad-output/implementation-artifacts/stories/14-2-news-entity-enrichment.md`
- To be created/modified by dev:
  - `nowing_backend/app/services/news/entities.py`
  - `nowing_backend/app/services/news/entity_extractor.py`
  - `nowing_backend/app/tasks/connector_indexers/rss_indexer.py`
  - `nowing_backend/app/services/scraper_chunks/schemas.py`
  - `nowing_backend/app/services/scraper_chunks/serializer.py` (if extending `to_chunks`)
  - `nowing_backend/tests/unit/services/news/test_entity_extractor.py`
  - `nowing_backend/tests/unit/services/news/fixtures/entity_extraction_golden.json`
  - `nowing_backend/tests/integration/news/test_news_entity_chunk_metadata.py`
  - `nowing_backend/tests/integration/news/test_news_entity_search_chainlens.py`
  - `nowing_backend/tests/integration/news/test_news_rss_integration.py` (update)
  - `nowing_backend/tests/integration/news/test_news_search.py` (update or remove)
  - `nowing_backend/tests/integration/news/test_news_dedup.py` (update)

## Open Questions for Product/Architecture

1. **ChainLens entity search contract**: What is the exact endpoint and request/response shape for querying articles by entity? If not ready, should we defer `test_news_entity_search_chainlens.py` to story 14.3?
2. **Entity extraction model**: Should we use the workspace's `vision_model_id` (quota-enforced) or a dedicated cheap global model for NER? If a dedicated model, which one and how is it configured?
3. **PII context for news**: Is `context="default"` sufficient, or do we need a `news` context that avoids over-redacting organization/location names?
4. **Person-name storage in chainlens**: Should `metadata.entities` store person surface forms as `<NAME>` only, or also a hashed/anonymized entity ID for linking while preserving privacy?

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **No dedicated news NER found.** Codebase search (`vibervn-context-engine` + grep) found no existing service that extracts people/organizations/locations from Vietnamese news text.
- **Related but not reusable patterns found:**
  - `app/proprietary/platforms/telegram/entity_extractor.py` (`TelegramEntityExtractor`) extracts phones, emails, prices, hashtags, and intent from Telegram messages — not NER. **Do not reuse for news.**
  - `app/services/pii/redact.py` contains a regex `_NAME_PATTERN` for Vietnamese person names used for redaction. It can be a rule-based *person-name detection* fallback, but it does not extract organizations or locations and is not suitable as the primary NER engine.
  - `app/services/memory/extraction.py` and `app/services/memory/pipeline.py` show the established pattern for structured LLM extraction (`MemoryExtractionResult`, `ExtractedFact`, `invoke_extraction_llm`, `parse_llm_output`). This is a good **pattern reference** for implementing `NewsEntityExtractor`, but not a drop-in reuse.
- **Verdict:** No duplicate logic. Proceed to Q2.

### Q2 — Simpler alternative?

- **No simpler off-the-shelf alternative exists** for Vietnamese news NER with person/organization/location + confidence + surface forms.
- **Reusable building blocks (must be reused, not rebuilt):**
  - `app.services.llm_service.get_agent_llm` / `get_vision_llm` for the LLM instance.
  - `app.services.quota_checked_vision_llm.QuotaCheckedVisionLLM` for quota/cost enforcement (Pattern 4 surface).
  - `app.services.token_tracking_service` for `TokenUsage` rows.
  - `app.services.pii.redact.redact_pii` for person-name masking.
  - `app.services.scraper_chunks.serializer.to_chunks` (after extending for `news` domain) or manual `Chunk` construction.
  - `app.services.chainlens.ingest.NowingIngestService` for sending chunks.
- **Verdict:** No simpler alternative that avoids new code. Proceed to Q3, but ensure all new code reuses the above helpers.

### Q3 — Edge cases the spec misses (Pattern 3)

- [ ] **Boundary — content length:** A long article may exceed the chosen LLM context window. The story does not specify whether to truncate, chunk before extraction, or extract per `Chunk` segment. If extraction is per-article and the article is longer than the model context, it will fail. **Recommendation:** Either truncate to the first N tokens with a `ponytail` note or chunk the article, extract per chunk, and merge/deduplicate entities.
- [ ] **Boundary — confidence threshold:** Story says `≥ 0.6`, but does not specify what happens if *all* entities are below the threshold (empty list — already covered by AC5) or if the LLM returns confidence as `0.0`.
- [ ] **Null/empty:** Article `description` can be empty or whitespace-only. Entity extraction should still run (on title) and return `[]` if no entities. The `to_chunks` `_required_fields` for news must accept `description` as optional or use `title` alone.
- [ ] **Null/empty entities from LLM:** AC5 covers empty/malformed JSON, but not the case where the model returns a valid `NewsEntityList` with `entities: []` (already OK) or with `entities` containing objects with `type = "product"` (unknown type). **Recommendation:** validate and drop unknown types, log `news_entity_unknown_type_dropped`.
- [ ] **Concurrent — idempotency / double-poll:** RSS is polled every 15 min. If the feed is unchanged, `NowingIngestService` returns `409`/noop. Entity extraction should not be repeated for duplicate articles. The Redis cache key must be stable across polls (`link + workspace_id` is good, but should also include `title`? If title changes, re-extract may be needed). **Recommendation:** cache by `sha256(link)` only; if title changes, treat as new article.
- [ ] **Concurrent — race on extraction cache:** Two Celery workers may process the same new article simultaneously. Redis `SET NX` or an in-progress sentinel should prevent duplicate LLM calls. **Recommendation:** add `news_entity:lock:{workspace_id}:{hash}` with short TTL.
- [ ] **Duplicate masked names after redaction:** Multiple distinct person names both masked as `<NAME>` will become indistinguishable in `metadata.entities`. The story says redact surface forms, but does not say how chainlens should disambiguate two different `<NAME>` mentions. **Add to open questions / design with privacy lead.**

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **LLM provider failure / timeout / rate limit:** Story mentions "degraded" log and empty entities, but does not specify *which* exceptions to catch. The implementation must catch `TimeoutError`, `RateLimitError`, and terminal errors from the model provider, not a generic `Exception` that could hide bugs.
- [x] **Quota/credit exhaustion (Pattern 4 — CRITICAL):** `QuotaCheckedVisionLLM.ainvoke` raises `QuotaInsufficientError` if the workspace has no premium credit. **Resolved: degrade gracefully** — catch `QuotaInsufficientError`, log `news_entity_extraction_quota_exhausted`, set `metadata.entities = []`, and continue indexing the article (AC-6).
- [x] **ChainLens service unavailable / 5xx / auth failure (Pattern 2):** `NowingIngestService` returns statuses `service_auth_unavailable`, `partial`, `failed`. **Resolved: continue without local fallback** — log `chainlens_news_ingest_failed`, emit metric, persist `ChainLensIngestJob(status="failed")`, continue processing the rest of the batch. No local `Document`/`Chunk` fallback (AD-35). Re-ingest will be idempotent on next poll (AC-7).
- [ ] **Redis down / unreachable:** If the Redis cache is unavailable, the system should fall back to calling the LLM directly (no cache) rather than fail the article. The story does not state this.
- [ ] **PII redactor failure:** `redact_pii` may throw. Story says "ensure raw person names never appear", but does not say what to do if the redactor itself fails. **Recommendation:** catch and raise `ChunkValidationError` (mirrors `scraper_chunks/serializer.py` behavior) so the article is not indexed with unredacted PII.
- [ ] **Cost tracking miscalibration (Pattern 4):** Entity extraction uses `TokenUsage` with `usage_type="entity_extraction"`. If the model provider returns an estimated cost and the tokenizer count differs from the actual provider bill, the workspace may be under/over-charged. **Recommendation:** use the same `token_tracker` callback path as chat (litellm callback) so actual provider costs are recorded; do not hand-roll token counting.
- [ ] **`to_chunks` news-domain validation error:** If the `news` domain is not properly registered in `scraper_chunks/serializer.py`, `ChunkValidationError` will be raised and the whole batch fails. The story should include a fallback or explicit validation.

### Triage

- **Critical findings — RESOLVED (2026-08-19):**
  1. **Quota/credit exhaustion:** Degrade gracefully — `metadata.entities = []`, article still indexed (AC-6).
  2. **ChainLens `NowingIngestService` failure:** Continue batch, no local fallback, persist `ChainLensIngestJob` failed row, idempotent re-ingest on next poll (AC-7).
- **Non-critical findings:** All remaining Q3 edge cases and Q4 failure modes (LLM timeout/rate-limit, Redis down, PII redactor failure, cost tracking, `to_chunks` validation) should be added to the test skeleton in `bmad-nowing-test-first-atdd`.

**Recommendation:** Critical findings resolved per best practices. Proceed to 4.4 `bmad-nowing-test-first-atdd`.
