---
baseline_commit: d3c10413812e5a801a22c2ec05043fe0dd24e7ef
status: in-progress
story_key: 14-2a-news-entity-extraction
---

# Story 14.2a: News Entity Extraction

**Status:** `in-progress`
**Epic:** Epic 14 — News Aggregation (Vietnam)
**Priority:** P1
**Blocked by:** None. This is the Nowing-only portion of the original Story 14.2.
**Related:** Story 14.2b (entity search) is gated on the `chainlens-research` entity contract and remains in `backlog`.

## Story

As a researcher,
I want named entities (people, organizations, locations) extracted from news articles and attached to `Chunk` metadata before the article is sent to `chainlens-research`,
So that `chainlens-research` can index those entities later without needing a re-ingest.

## Acceptance Criteria

1. **Given** a news article is parsed, **When** entity extraction runs, **Then** named entities (people, organizations, locations) are extracted with confidence scores.
2. **Given** extracted entities, **When** the article is normalized to a `Chunk`, **Then** `metadata.entities` contains the entity mentions, types, and redacted surface forms; the article is still sent to `chainlens-research` via `NowingIngestService`.
3. **Given** the entity extraction model returns an empty entity list or malformed JSON, **When** entity enrichment runs, **Then** it falls back to `metadata.entities = []` and the article is still indexed.
4. **Given** the workspace cannot pay for entity extraction (insufficient wallet / `QuotaInsufficientError`, news-entity-extraction budget exceeded, or rate-limited), **When** extraction is requested, **Then** no LLM call is made, extraction degrades to `metadata.entities = []`, logs `news_entity_extraction_{reason}`, and the article is still indexed.
5. **Given** `NowingIngestService` fails to ingest a news `Chunk[]` to `chainlens-research` (5xx, auth unavailable, timeout, max retries), **When** the failure occurs, **Then** it logs `chainlens_news_ingest_failed`, emits a metric, persists a `ChainLensIngestJob` with status `failed`, continues processing the rest of the batch, and does **not** fall back to a local `Document`/`Chunk` index (AD-35).

## Validation

- Unit test: `test_news_entity_extraction.py` — entity accuracy ≥ 0.85, fallback, confidence threshold, deduplication
- Unit test: `test_news_entity_redaction.py` — person surface forms masked to `<NAME>` in `Chunk.content` and `metadata.entities`; foreign person names masked; composite org names with person substrings masked
- Unit test: `test_news_entity_extract_budget.py` — gate blocks when disabled, budget exceeded, rate-limited, wallet insufficient
- Unit test fixture: `tests/unit/services/news/fixtures/entity_extraction_golden.json` — 10 golden Vietnamese snippets (mix VnExpress/Tuổi Trẻ/Dân Trí/Vietnamnet) with labeled entities
- Integration test: `test_news_entity_chunk_metadata.py` — `NowingIngestService.ingest()` called with `metadata.entities` and correct AD-34 fields
- Integration test (existing, updated): `test_news_rss_integration.py` — `ChainLensIngestJob` created / `NowingIngestService.ingest()` called, not local `Document` count
- Integration test (existing, updated): `test_news_dedup.py` — idempotent `sourceId` / chainlens noop instead of local canonical merge

## Tags

AD-34, AD-35, AD-25, AD-27, news, NER, entity-extraction, chainlens, rss, PII-redaction

## Tasks / Subtasks

- [x] Define entity extraction contract (AC: #1, #2)
  - [x] Add `app/services/news/entities.py` with `NewsEntity` Pydantic model: `text`, `type` (`person`, `organization`, `location`), `confidence` (0.0–1.0), `surface_forms`.
  - [x] Add `NewsEntityList` Pydantic model for structured output.
  - [x] Add `NewsEntityExtractor` with async `extract(article_text: str, workspace_id: int, session: AsyncSession) -> list[NewsEntity]`.
  - [x] **Entity quality gates**: confidence threshold `≥ 0.6`; deduplicate by `(type, normalized_text)` keeping highest confidence; drop unknown `type` values and log `news_entity_unknown_type_dropped`.
- [x] Implement extraction backend (AC: #1, #3, #4)
  - [x] Use `app.services.llm_service.get_vision_llm(session, workspace_id)` (quota-enforced, bills workspace owner) or `get_agent_llm` if vision quota is not configured; do **not** rely on `QuotaCheckedVisionLLM.with_structured_output` because `with_structured_output` is forwarded to the inner model and bypasses quota gating. Use `ainvoke` with a JSON-output parser or wrap the structured model call so the quota check still runs.
  - [x] Use `langchain_core.messages.HumanMessage` + `with_structured_output(NewsEntityList)` on the **unwrapped** base model only if the workspace is not premium; otherwise call `ainvoke` through the quota wrapper and parse the JSON result.
  - [x] **Prompt template** (Vietnamese): extract people, organizations, locations; return `text`, `type`, `confidence`, `surface_forms`.
  - [x] Add malformed/empty JSON fallback returning `[]` and log `news_entity_extraction_fallback` counter.
  - [x] Add `QuotaInsufficientError` catch (AC-4): log `news_entity_extraction_quota_exhausted`, set `metadata.entities = []`, continue indexing.
  - [x] Add LLM timeout/rate-limit/terminal provider degradation: catch `TimeoutError`, `RateLimitError`, and provider terminal errors; log `news_entity_extraction_degraded`; continue with empty entities.
  - [x] Cache results per article in Redis (TTL 1h) using key `news_entity:{workspace_id}:{sha256(article.link).hexdigest()}`. Use `SET NX`/`news_entity:lock:{...}` to avoid duplicate concurrent LLM calls.
  - [x] **Cost tracking**: every extraction call writes `TokenUsage` with `usage_type=UsageType.ENTITY_EXTRACTION` (add `ENTITY_EXTRACTION = "entity_extraction"` to `UsageType` enum in `token_tracking_service.py`); do not bypass wallet.
  - [x] **Cost-control gate**: before calling the LLM, run `check_news_entity_extraction_allowed(session, workspace)`. If disabled or over budget/rate, log reason and return `[]`.
- [x] PII redaction guard for person names (AD-25) (AC: #1, #2)
  - [x] **Redaction order**: extract entities FIRST, then mask:
    1. Run extraction on raw article text → `list[NewsEntity]` with raw `surface_forms`.
    2. For every `person` entity, replace all raw `surface_forms` in the article text with `<NAME>` (case-insensitive, whole word).
    3. Run `redact_pii(..., context="default")` on the masked content to catch remaining phone/email/person patterns → `Chunk.content`.
    4. For `metadata.entities`:
       - `person`: store `text="<NAME>"`, `surface_forms=["<NAME>"]`, keep `type`/`confidence`.
       - `organization`/`location`: keep text, but apply person-name replacement to any `surface_form` that contains a person substring.
  - [x] Ensure raw person names never appear in `Chunk.content`, `metadata.entities`, `Memory`, logs, or UI.
  - [x] If redaction fails, raise `ChunkValidationError` so the article is not indexed with unredacted PII.
- [x] Add cost-control gate (reuses `memory/extract_budget.py` pattern)
  - [x] Create `app/services/news/extract_budget.py` with `check_news_entity_extraction_allowed()` and `record_news_entity_extraction()`.
  - [x] Add config keys `NEWS_ENTITY_EXTRACTION_*` to `app/config/__init__.py`.
  - [x] Extend `ResolvedWorkspaceLimits` and `workspace_limits` table with `news_entity_extraction_*` fields (alembic migration).
  - [x] Update `app/services/workspace_limits.py` and `app/schemas/workspace.py` to expose the new fields.
  - [x] Gate is evaluated before any LLM call; on block, return `[]` and log `news_entity_extraction_{reason}`.
- [x] Refactor news indexing to `NowingIngestService` (AC: #2, #5)
  - [x] Replace `IndexingPipelineService.index_batch()` in `app/tasks/connector_indexers/rss_indexer.py` with `NowingIngestService().ingest(scraper_id="news.rss", chunks=..., workspace_id=..., session=...)`. Pass the active `session` so `ChainLensIngestJob` is persisted.
  - [x] Remove local `Document`/`Chunk`/`CanonicalEntity` persistence for news (replaces 14.1 local-indexing path; AD-35). Keep placeholder/connector metadata only if required by the UI, not an indexed corpus.
  - [x] Keep deduplication by `sourceId` (article link hash) so chainlens-research receives idempotent chunks.
  - [x] Add `NowingIngestService` failure handling (AC-5): inspect `IngestResult.status` in `failed`/`service_auth_unavailable`/`partial`; log `chainlens_news_ingest_failed`, emit `record_chainlens_ingest_failed`, persist `ChainLensIngestJob(status="failed")`, continue processing the rest of the batch, and do **not** create local `Document`/`Chunk` fallback.
- [x] Update chunk/ingest schema (AC: #2)
  - [x] Add `entities: list[dict[str, Any]] | None = None`, `pubDate: str | None = None`, `source: str | None = None` to `ChunkMetadata` in `app/services/scraper_chunks/schemas.py` (or rely on `extra="allow"` but be explicit for documentation).
  - [x] Set `contentType: "news"` and correct `domain` (`vnexpress.net`, `tuoitre.vn`, etc.) in the news chunk payload. Update `scraper_chunks/serializer.py` so `to_chunks(domain="news", ...)` defaults `content_type` to `"news"` when `domain` is a news domain.
  - [x] Ensure `scraper_chunks/serializer.py` `_required_fields("news")` accepts `title` only; `description` is optional.
- [x] Tests
  - [x] Unit: `tests/unit/services/news/test_entity_extractor.py` — extraction accuracy, confidence, fallback, malformed/empty JSON, timeout/rate-limit, unknown type, Redis lock/cache, long article, token usage.
  - [x] Unit: `tests/unit/services/news/test_entity_extract_budget.py` — disabled, budget exceeded, rate-limited, wallet insufficient, boundary cases, config fallback.
  - [x] Unit: `tests/unit/services/news/test_entity_redaction.py` — person surface forms masked to `<NAME>`, foreign names, composite org/location with person substrings, redaction failure.
  - [x] Unit: `tests/unit/services/news/fixtures/entity_extraction_golden.json` — 10 golden Vietnamese snippets (mix VnExpress/Tuổi Trẻ/Dân Trí/Vietnamnet) with labeled entities.
  - [x] Integration: `tests/integration/news/test_news_entity_chunk_metadata.py` — `NowingIngestService.ingest()` called with `metadata.entities` and correct AD-34 fields; `ChainLensIngestJob` persisted.
  - [x] Integration: `tests/integration/news/test_news_entity_extract_budget.py` — gate respects `workspace_limits.news_entity_extraction_*`, writes `TokenUsage` with `usage_type="entity_extraction"`, handles budget/rate/wallet.
  - [x] Update `tests/integration/news/test_news_rss_integration.py` — assert `ChainLensIngestJob` created / `NowingIngestService.ingest()` called, not `Document` count.
  - [x] Update `tests/integration/news/test_news_dedup.py` — assert idempotent `sourceId` / chainlens noop instead of local canonical merge.

### Review Findings

- [x] [Review][Patch] Mask article.title with mask_person_entities_in_text before serialization to prevent PII leakage [nowing_backend/app/tasks/connector_indexers/rss_indexer.py:161]
- [x] [Review][Patch] Fix case-sensitive check preventing IGNORECASE regex redaction in redact_entities_metadata and mask_person_entities_in_text [nowing_backend/app/services/news/entity_extractor.py:167]
- [x] [Review][Patch] Accept article_link in NewsEntityExtractor.extract and key Redis cache by article.link hash [nowing_backend/app/services/news/entity_extractor.py:263]
- [x] [Review][Patch] Resolve workspace owner user_id in extract_budget when user_id is None to ensure TokenUsage persistence and wallet check [nowing_backend/app/services/news/extract_budget.py:300]
- [x] [Review][Patch] Block extraction gate immediately when budget_cap or rate_max is configured as 0 [nowing_backend/app/services/news/extract_budget.py:250]
- [x] [Review][Patch] Improve _clean_json_snippet with markdown fence regex and support array JSON responses [nowing_backend/app/services/news/entity_extractor.py:127]
- [x] [Review][Patch] Handle list content blocks in LLM response and safe integer parsing for total_tokens [nowing_backend/app/services/news/entity_extractor.py:359]
- [x] [Review][Patch] Discard entity text < 2 chars and single Vietnamese pronouns to prevent accidental text destruction [nowing_backend/app/services/news/entities.py:19]
- [x] [Review][Patch] Safeguard clear_entity_cache with scan_iter and testing environment guard [nowing_backend/app/services/news/entity_extractor.py:466]
- [x] [Review][Patch] Map news_entity_extraction_* fields in workspaces_routes.py GET and PUT endpoints [nowing_backend/app/routes/workspaces_routes.py:447]
- [x] [Review][Patch] Remove dead code from Story 14.1 in rss_indexer.py and add golden dataset accuracy test [nowing_backend/app/tasks/connector_indexers/rss_indexer.py:226]
- [x] [Review][Defer] Pre-reserve atomic rate limiter bucket before LLM call [nowing_backend/app/services/news/extract_budget.py:270] — deferred, pre-existing soft limit pattern

### Review Findings — 2026-08-24 (groups A+B, full review)

#### Decision needed
- [ ] [Review][Decision] Reconcile cost tracking for news entity extraction with `QuotaCheckedVisionLLM` and `TokenUsage` — For premium workspaces `QuotaCheckedVisionLLM.ainvoke` already records a `vision_extraction` `TokenUsage` row inside `billable_call`; `entity_extractor.extract` then writes a second `entity_extraction` row with a hand-rolled `cost_micros = total_tokens * 0.5`. For free/BYOK workspaces the unwrapped `SanitizedChatLiteLLM` call is not inside `scoped_turn`, so actual prompt/completion tokens and cost are not captured. The budget gate only sums `entity_extraction` rows, so the real premium spend is invisible. Options: (A) make `get_vision_llm`/`QuotaCheckedVisionLLM` accept `usage_type="entity_extraction"` so one call records the correct row with real cost and the gate sees it; (B) route the extraction through a dedicated `billable_call`/`scoped_turn` and remove the manual `record_token_usage` call; (C) keep the manual row but derive actual cost from `usage_metadata` and avoid double-recording for premium. This affects AC4 and the "do not hand-roll token counting" AD. [nowing_backend/app/services/news/entity_extractor.py:476-492, nowing_backend/app/services/news/extract_budget.py:340-358, nowing_backend/app/services/quota_checked_vision_llm.py:63-91]

#### Patch
- [ ] [Review][Patch] Rate/budget gate is not pre-reserved atomically; concurrent RSS workers can exceed caps [nowing_backend/app/services/news/extract_budget.py:181-317, nowing_backend/app/services/news/entity_extractor.py:486-492]
- [ ] [Review][Patch] Chunk `source` and `domain` contract violations: `to_chunks` receives `article.source` (which may be the RSS channel title) as `domain`, so `_is_news_domain` can fail and content falls through to the listing layout; `ChunkMetadata.source` is set to the portal name instead of the AD-34 constant `nowing_scraper` [nowing_backend/app/tasks/connector_indexers/rss_indexer.py:184-190, nowing_backend/app/services/scraper_chunks/serializer.py:533-538, nowing_backend/app/services/scraper_chunks/schemas.py:26, nowing_backend/app/services/scraper_chunks/serializer.py:211-238]
- [ ] [Review][Patch] RSS indexer ignores `partial` and `service_auth_unavailable` `IngestResult` statuses and reports the whole batch as skipped; does not emit `record_chainlens_ingest_failed` or persist `ChainLensIngestJob(status="failed")` for these cases [nowing_backend/app/tasks/connector_indexers/rss_indexer.py:211-222]
- [ ] [Review][Patch] Person-name redaction uses ASCII `\b` word boundaries and a non-boundary fallback that can mangle unrelated text, and `redact_pii(context="default")` only catches Vietnamese surnames so foreign person names missed by the LLM can leak into chunks [nowing_backend/app/services/news/entity_extractor.py:165-178, nowing_backend/app/services/pii/redact.py:45-67]
- [ ] [Review][Patch] Raw article title and description are placed in the NER prompt before PII redaction, sending unredacted person names/phones/emails to the LLM provider; also `raw_text` becomes the literal string "None" when `article.title` is None [nowing_backend/app/services/news/entity_extractor.py:327-345, nowing_backend/app/tasks/connector_indexers/rss_indexer.py:140-144]
- [ ] [Review][Patch] `NewsEntityList.model_validate` discards the entire entity list if one entity fails the `text` validator, rather than dropping only the malformed entity and keeping the valid ones [nowing_backend/app/services/news/entity_extractor.py:400-424, nowing_backend/app/services/news/entities.py:24-44]
- [ ] [Review][Patch] `_clean_json_snippet` uses `rfind` with naive start/end indices and can capture invalid JSON when the response contains trailing prose or nested braces [nowing_backend/app/services/news/entity_extractor.py:124-142]
- [ ] [Review][Patch] `user_id` is passed as a `str` from `rss_indexer` through the extraction gate into `record_token_usage`, which expects a `UUID`; `TokenUsage.user_id` is `UUID(as_uuid=True)` and can fail the insert [nowing_backend/app/tasks/connector_indexers/rss_indexer.py:306, nowing_backend/app/services/news/extract_budget.py:340-358, nowing_backend/app/services/token_tracking_service.py:569-590]
- [ ] [Review][Patch] `record_token_usage` is called after the rate counter is incremented, so if token recording fails the rate counter is inflated without any cost being tracked [nowing_backend/app/services/news/extract_budget.py:346-364]
- [ ] [Review][Patch] Dead Story 14.1 functions `_build_connector_doc`, `_build_source_markdown`, `_news_fingerprint`, and `_prune_stale_articles` remain in `rss_indexer.py` but are no longer called [nowing_backend/app/tasks/connector_indexers/rss_indexer.py:57-125,242-279]
- [ ] [Review][Patch] `WorkspaceLimitUpdate` allows negative news caps, which causes `ResolvedWorkspaceLimits.__post_init__` to raise and the PUT endpoint to return 500 [nowing_backend/app/schemas/workspace.py:121-129, nowing_backend/app/routes/workspaces_routes.py:511-522]
- [ ] [Review][Patch] `MAX_CONTEXT_CHARS` truncates at a hard 32,000-character boundary with no token counting or word-boundary preservation, so long articles can be cut mid-word and the per-article token/cost bound is not enforced [nowing_backend/app/services/news/entity_extractor.py:39,282-283]

#### Deferred
- [x] [Review][Defer] `NowingIngestService` can fail to persist `ChainLensIngestJob` after a successful `IngestResult` because the persistence block is best-effort and can raise; this is pre-existing `NowingIngestService` reliability debt, not introduced by Story 14.2a — revisit when chainlens ingest durability is hardened. [nowing_backend/app/services/chainlens/ingest.py:479-503]

## Dev Notes

### Current state from Story 14.1

- `app/services/news/rss_fetcher.py` parses RSS/Atom into `NewsArticle` (`title`, `link`, `description`, `pub_date`, `category`, `source`).
- `app/tasks/connector_indexers/rss_indexer.py` currently calls `IndexingPipelineService.index_batch()` → persists `Document`/`Chunk` in local Postgres and upserts `CanonicalEntity`.
- This local-news-index path violates AD-35 (Nowing does not build a public/vertical search corpus). This story must replace it with `NowingIngestService` → `chainlens-research`.
- `app/canonical/services/unified_search_service.py` is local-only; news search will be delegated to `chainlens-research`.
- Tests in `tests/integration/news/` currently assert local `Document`/`Chunk` rows; they must be updated to assert the `NowingIngestService` contract.

### Architecture compliance

- **AD-34 — Nowing Scraper Feed Contract**: canonical `Chunk[]` must have `source: 'nowing_scraper'`, `sourceId`, `domain` (actual portal domain, e.g. `vnexpress.net`), `fetchedAt`, `contentType: 'news'`, plus optional `metadata.entities`, `pubDate`, `source`.
- **AD-35 — Nowing Does Not Build Public/Vertical Search Corpus**: news search goes through `chainlens-research` only; no local `Document`/`Chunk` corpus for news.
- **AD-25 — Unified PII Redaction Pipeline**: redact person names via `app/services/pii/redact.py` before storage; do not create a separate news redaction module.
- **AD-27 — Nowing Scraper Output Feeds chainlens-research**: entity linking/disambiguation happens in chainlens-research; Nowing sends surface-level entities only.

### Content type, domain, and metadata contract

- `ChunkMetadata` (`app/services/scraper_chunks/schemas.py`) uses `extra="allow"`, so `entities`, `pubDate`, and `source` can be added without breaking existing consumers.
- Add explicit fields to `ChunkMetadata` for documentation and IDE support.
- `scraper_chunks/serializer.py` already has `_NEWS_DOMAINS = {"news", "news_article"}` and `_is_news_domain()`. Extend `_build_content` and `_metadata_from_data` to:
  - set `contentType` to `"news"` for news domains,
  - pass `pubDate` and `source` (portal name) into metadata,
  - accept `entities` from the raw record and place it in `metadata.entities`.
- `to_chunks` for news must be called with `domain` equal to the actual portal domain (`vnexpress.net`, `tuoitre.vn`, etc.), not the literal string `"news"`. The serializer should canonical-map or accept any news domain.

### PII redaction order

1. Extract entities from raw text → `list[NewsEntity]` with raw `text` and `surface_forms`.
2. Build redacted article content:
   - For every `person` entity, replace **all raw `surface_forms`** (case-insensitive, whole word where possible) in the original article text with `<NAME>`.
   - Then run `redact_pii(redacted_text, context="default")` to catch any remaining phone/email/person patterns missed by the LLM.
3. Build redacted `metadata.entities`:
   - `person`: `text = "<NAME>"`, `surface_forms = ["<NAME>"]` (do not store raw name). Keep `type` and `confidence`.
   - `organization` / `location`: keep the canonical `text` and `surface_forms`, but apply the same person-name replacement to any `surface_form` that contains a person substring (e.g. `Công ty Nguyễn Văn A` → `Công ty <NAME>`).
4. If redaction fails, raise `ChunkValidationError` and skip the article.

*ponytail:* Person-name masking depends on the NER LLM correctly classifying person entities. Foreign person names missed by the LLM will not be caught by `redact_pii` default context. If leakage is observed in production, add a second regex pass or a `news` context to `redact_pii`.

### Quota, cost, and `TokenUsage`

- `get_vision_llm` returns `QuotaCheckedVisionLLM` for premium global configs; otherwise returns the unwrapped `SanitizedChatLiteLLM`.
- Do **not** call `.with_structured_output` on a `QuotaCheckedVisionLLM` instance and then `.ainvoke` the resulting model, because the structured-output model is not wrapped and the quota check is bypassed.
- Prefer: get the base model, apply `with_structured_output` if needed, then route the call through `billable_call` / `QuotaCheckedVisionLLM.ainvoke`, or parse JSON from a plain `ainvoke`.
- Add `ENTITY_EXTRACTION = "entity_extraction"` to `UsageType` in `token_tracking_service.py`.
- Record `TokenUsage` with the actual provider-reported tokens/cost via the same LiteLLM callback path used for chat; do not hand-roll token counting.

### Cost-control gate

News RSS indexing is a background Celery task and can run every 15 minutes per workspace. To prevent unbounded LLM spend (especially for free/BYOK workspaces), reuse the budget/rate pattern from `app/services/memory/extract_budget.py`:

- Create `app/services/news/extract_budget.py` (or refactor `memory/extract_budget.py` into a generic `UsageBudgetGate` if a third usage type appears).
- Config keys (default `0` = disabled/off):
  - `NEWS_ENTITY_EXTRACTION_ENABLED` — global kill-switch.
  - `NEWS_ENTITY_EXTRACTION_MIN_RESERVE_MICROS` — wallet floor for premium workspaces.
  - `NEWS_ENTITY_EXTRACTION_BUDGET_MICROS` — rolling spend cap.
  - `NEWS_ENTITY_EXTRACTION_BUDGET_WINDOW` (`day`/`week`/`month`).
  - `NEWS_ENTITY_EXTRACTION_RATE_MAX` — max extractions per window.
  - `NEWS_ENTITY_EXTRACTION_RATE_WINDOW_SECONDS`.
- Per-workspace overrides: extend `ResolvedWorkspaceLimits` and `workspace_limits` table with `news_entity_extraction_item_cap`, `news_entity_extraction_spend_cap_micros`, `news_entity_extraction_wallet_pre_check` (alembic migration `NNN_add_news_entity_extraction_limits`).
- Gate checks (run **before** any LLM call):
  1. If `NEWS_ENTITY_EXTRACTION_ENABLED` is false → `allowed=False, reason="disabled"`, set `metadata.entities = []`.
  2. Workspace budget/rate exceeded → `allowed=False, reason="budget_exceeded"` / `"rate_limited"`, set `metadata.entities = []`, log `news_entity_extraction_{reason}`.
  3. Wallet pre-check fails for premium workspace → `allowed=False, reason="insufficient_wallet"`, set `metadata.entities = []`.
- After a successful extraction, call `record_token_usage(..., usage_type="entity_extraction")` and increment the rate counter.

### Redis cache

- Key: `news_entity:{workspace_id}:{sha256(article.link).hexdigest()}`.
- Lock key: `news_entity:lock:{workspace_id}:{hash}` with short TTL to prevent duplicate concurrent LLM calls.
- If Redis is unavailable, fall back to calling the LLM directly (no cache) rather than failing the article.
- Cache by article link only; if the title changes, treat it as a new article on the next poll.

### Edge cases and failure modes

- **Long article:** Truncate to the first `MAX_CONTEXT_TOKENS` with a `ponytail:` note, or chunk the article, extract per chunk, and merge/deduplicate entities. Decide and document in a `ponytail:` comment.
- **All entities below confidence threshold:** Return `[]`.
- **Empty/whitespace description:** Still extract from `title`; `to_chunks` `_required_fields("news")` must accept `title` alone.
- **Unknown `type` from LLM:** Drop and log `news_entity_unknown_type_dropped`.
- **LLM timeout/rate-limit/terminal error:** Catch `TimeoutError`, `RateLimitError`, and provider terminal errors; log `news_entity_extraction_degraded`; continue with `metadata.entities = []`.
- **Redis down:** Call LLM directly, no cache.
- **PII redactor failure:** Raise `ChunkValidationError` so the article is skipped.
- **Concurrent double-poll / duplicate article:** `NowingIngestService` returns `409` noop; entity extraction must not run twice because the RSS link is already in the cache or the ingest is idempotent.

### File structure and conventions

- New code:
  - `app/services/news/entities.py` — `NewsEntity`, `NewsEntityList` models.
  - `app/services/news/entity_extractor.py` — `NewsEntityExtractor`, redaction, cache, gate integration.
  - `app/services/news/extract_budget.py` — cost/rate/wallet gate (pattern from `memory/extract_budget.py`).
- Modify:
  - `app/tasks/connector_indexers/rss_indexer.py` — use `NowingIngestService`.
  - `app/services/scraper_chunks/schemas.py` — `ChunkMetadata` fields.
  - `app/services/scraper_chunks/serializer.py` — `contentType`, `domain`, `pubDate`, `source`, `entities`.
  - `app/services/token_tracking_service.py` — `UsageType.ENTITY_EXTRACTION`.
  - `app/services/workspace_limits.py` and `app/schemas/workspace.py` — add `news_entity_extraction_*` limit fields.
  - `app/db.py` — add columns to `workspace_limits` table.
- Reuse: `app/services/llm_service.py`, `app/services/pii/redact.py`, `app/services/chainlens/ingest.py`, `app/services/memory/extract_budget.py` (pattern), `app/observability/metrics.py`.
- Alembic migration: add `news_entity_extraction_item_cap`, `news_entity_extraction_spend_cap_micros`, `news_entity_extraction_wallet_pre_check` to `workspace_limits`.
- No DB migration for `Chunk` table (chunks live in `chainlens-research` via `NowingIngestService`).

### Library / framework requirements

- `pydantic` for `NewsEntity` and `NewsEntityList`.
- `langchain_core.messages.HumanMessage` + `with_structured_output` (or manual JSON parse wrapped in `QuotaCheckedVisionLLM.ainvoke` or `billable_call`).
- `redis.asyncio` for per-article extraction cache.
- Existing token tracker (`app.services.token_tracking_service.UsageType`) or `QuotaCheckedVisionLLM` for cost attribution.

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
  - **14.1 indexed news locally, which now violates AD-35. This story must replace this path.**

### Latest technical specifics

- `ChunkMetadata` (`app/services/scraper_chunks/schemas.py`) uses `extra="allow"`, so `entities`, `pubDate`, and `source` can be added without breaking existing consumers.
- `NowingIngestService` (`app/services/chainlens/ingest.py`) supports 1000-chunk pagination, `409` noop, `5xx` retry, and parent/child `ingestJobId` tracking. Pass `session` to persist `ChainLensIngestJob`.
- `app/services/pii/redact.py` supports `default`, `job_data`, `lead_enrichment`. Add `news` context only if the rule set must diverge; otherwise `default` is sufficient.
- `scraper_chunks/serializer.py` already has `_NEWS_DOMAINS` and news-domain handling, but does not set `contentType="news"` or pass `pubDate`/`source`/`entities` into `ChunkMetadata`.
- `UsageType` in `token_tracking_service.py` does not yet include `entity_extraction`; add it as an enum member.
- `app/services/memory/extract_budget.py` provides a proven budget/rate/wallet gate pattern that should be adapted for news entity extraction (`app/services/news/extract_budget.py`) to avoid unbounded background LLM spend.

### Phase B contract (deferred to Story 14.2b)

- `chainlens-research` `POST /v1/ingest/scraper` stores `Chunk[]` but does not parse or index `metadata.entities` for search.
- `chainlens-research` `POST /api/v1/search` is an SSE research endpoint; `numEntities` is a `wide_research` output parameter, not an entity search filter.
- Therefore the **chat entity query** ACs are not in scope for 14.2a. They live in 14.2b, which stays in `backlog` until the chainlens contract lands.

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

- Validation run: applied `bmad-create-story` checklist on original 14.2; split into 14.2a (Nowing-only) and 14.2b (chainlens-gated) via `bmad-correct-course`.

### Completion Notes List

- Split from original Story 14.2.
- Fully implemented and verified:
  - `NewsEntity` & `NewsEntityList` Pydantic models with quality gating (`confidence >= 0.6`, dropping unknown types with `news_entity_unknown_type_dropped` log) in `app/services/news/entities.py`.
  - `NewsEntityExtractor` in `app/services/news/entity_extractor.py` with Redis caching (1h TTL), Redis lock to avoid duplicate LLM calls, context window truncation (32,000 chars), and LLM degradation fallback.
  - PII Redaction Pipeline in `app/services/news/entity_extractor.py` (`mask_person_entities_in_text` + `redact_entities_metadata`) masking person surface forms with `<NAME>` and running `redact_pii` before chunk serialization.
  - Cost-Control Gate & Usage Tracking in `app/services/news/extract_budget.py` with Redis Lua atomic rate limiting, budget cap check, wallet pre-check, and fallback.
  - `UsageType.ENTITY_EXTRACTION` registered in `app/services/token_tracking_service.py`.
  - Database schema & Alembic migration `230_add_news_entity_extraction_limits.py` adding `news_entity_extraction_item_cap`, `news_entity_extraction_spend_cap_micros`, and `news_entity_extraction_wallet_pre_check` to `WorkspaceLimit`.
  - Updated `ResolvedWorkspaceLimits`, `WorkspaceLimitService`, and workspace schemas.
  - Updated chunk schemas (`ChunkMetadata`) and serializer (`to_chunks` with `contentType="news"` and `entities`/`pubDate`/`source` in metadata).
  - Refactored `rss_indexer.py` to use `NowingIngestService().ingest(scraper_id="news.rss", ...)` for ChainLens ingest adhering to AD-34 & AD-35.
- All tests passing (104/104):
  - Unit tests: 99 passed (`test_entity_extractor.py`, `test_entity_extract_budget.py`, `test_entity_redaction.py`, `test_rss_fetcher.py`, `test_rss_indexer_units.py`).
  - Integration tests: 5 passed (`test_news_entity_chunk_metadata.py`, `test_news_entity_extract_budget.py`, `test_news_rss_integration.py`).
  - Linting & formatting: 100% clean (`ruff check` & `ruff format`).

### File List

- Created:
  - `nowing_backend/app/services/news/entities.py`
  - `nowing_backend/app/services/news/entity_extractor.py`
  - `nowing_backend/app/services/news/extract_budget.py`
  - `nowing_backend/alembic/versions/230_add_news_entity_extraction_limits.py`
  - `nowing_backend/tests/unit/services/news/test_entity_extractor.py`
  - `nowing_backend/tests/unit/services/news/test_entity_extract_budget.py`
  - `nowing_backend/tests/unit/services/news/test_entity_redaction.py`
  - `nowing_backend/tests/unit/services/news/fixtures/entity_extraction_golden.json`
  - `nowing_backend/tests/integration/news/test_news_entity_chunk_metadata.py`
  - `nowing_backend/tests/integration/news/test_news_entity_extract_budget.py`
- Modified:
  - `nowing_backend/app/config/__init__.py`
  - `nowing_backend/app/db.py`
  - `nowing_backend/app/services/scraper_chunks/schemas.py`
  - `nowing_backend/app/services/scraper_chunks/serializer.py`
  - `nowing_backend/app/services/token_tracking_service.py`
  - `nowing_backend/app/services/workspace_limits.py`
  - `nowing_backend/app/schemas/workspace.py`
  - `nowing_backend/app/tasks/connector_indexers/rss_indexer.py`
  - `nowing_backend/tests/unit/services/news/test_rss_indexer_units.py`
  - `nowing_backend/tests/integration/news/conftest.py`
  - `nowing_backend/tests/integration/news/test_news_rss_integration.py`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
  - `_bmad-output/implementation-artifacts/stories/14-2a-news-entity-extraction.md`

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **No exact duplicate for news NER found.** There is no existing `app/services/news/entity_extractor.py` or news-specific NER in `nowing_backend`.
- **Similar helper patterns exist and should be reused / referenced:**
  - `app/services/memory/pipeline.py:invoke_extraction_llm` — LLM call with timeout and error taxonomy.
  - `app/services/memory/extraction.py` — uses `scoped_turn()` + `record_token_usage()` for extraction cost tracking.
  - `app/proprietary/platforms/telegram/entity_extractor.py` — regex-based extraction of Vietnamese locations, phones, prices, emails. The `_VN_LOCATIONS` list could be reused to validate/ground `location` entities extracted by the LLM.
  - `app/services/lead_extraction_service.py` and `app/routes/extract_entities_routes.py` — hermetic extraction of phones/tax codes/company names, **not** suitable for news NER.

**Verdict:** Proceed, but design the `NewsEntityExtractor` to reuse the `scoped_turn()` + `record_token_usage()` pattern from memory extraction and consider importing `_VN_LOCATIONS` for location validation.

### Q2 — Simpler alternative?

- **Partial helper:** `TelegramEntityExtractor.extract_entities` already extracts locations via regex for Vietnamese provinces/districts. It does **not** extract people or organizations.
- **No full alternative to an LLM-based NER for people/organizations.** The AC explicitly requires person and organization entities, which regex cannot reliably produce.

**Verdict:** Proceed. Reuse the location regex only as a validator or fallback; do not replace the LLM NER.

### Q3 — Edge cases the spec misses (Pattern 3)

- [ ] **Boundary — confidence threshold:** `confidence == 0.6` must be included (`>=`), `0.599` dropped, `0.601` included.
- [ ] **Boundary — empty/malformed `surface_forms`:** LLM returns `surface_forms: []` or `null`; normalize to `[]`.
- [ ] **Boundary — `description` empty/whitespace-only:** extraction should still run on `title`.
- [ ] **Boundary — title-only or title missing:** `_required_fields("news")` accepts title; if title missing, `ChunkValidationError` skips article.
- [ ] **Boundary — article text beyond model context:** no `MAX_CONTEXT_TOKENS` specified; need truncation/chunking strategy.
- [ ] **Null/empty — `metadata.entities` missing or `null` in `Chunk`:** should be normalized to `[]`.
- [ ] **Null/empty — `pubDate` or `source` missing:** `_metadata_from_data` must handle `None`.
- [ ] **Null/empty — `link` missing or malformed:** no stable `sourceId`; article should be skipped before extraction.
- [ ] **Concurrent — same article from two feeds in one poll:** `sourceId` deduplication in `rss_indexer` should prevent double extraction.
- [ ] **Concurrent — two workers process the same new article:** Redis lock `news_entity:lock:{workspace}:{hash}` must be used.
- [ ] **Idempotency — lock holder crashes before updating cache:** lock TTL must be short enough to recover but not so short that a slow extraction gets interrupted.
- [ ] **Type validation — LLM returns entity type `product` or other unknown value:** drop and log `news_entity_unknown_type_dropped`.
- [ ] **Composite entity — organization name contains a person name (e.g., `Công ty TNHH Nguyễn Văn A`):** redaction order must redact the inner person surface form.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **LLM provider returns non-JSON output:** fallback to `metadata.entities = []`.
- [ ] **LLM provider returns JSON with missing fields:** e.g. `confidence` or `surface_forms` missing; parse defensively.
- [ ] **LLM `get_vision_llm` returns `None`:** no vision model configured; should skip extraction and continue indexing.
- [ ] **`get_agent_llm` fallback is not quota-gated for free/BYOK workspaces:** `get_agent_llm` returns an unwrapped model; the spec does not say how to bill/track cost for that path. **Money gap — needs PM/PO clarification.**
- [ ] **`redact_pii` cannot reliably redact non-Vietnamese person names (e.g., `Joe Biden`, `Elon Musk`):** `_NAME_PATTERN` only matches a fixed list of Vietnamese surnames. AC claims "raw person names never appear" but the current redactor will leak non-Vietnamese names. **Security gap — needs PM/PO clarification.**
- [ ] **`redact_pii` itself raises:** catch and raise `ChunkValidationError`, skip article.
- [ ] **`NowingIngestService.ingest` returns `partial`:** some batches ingested, some failed; behavior not specified.
- [ ] **`ChainLensIngestJob` persistence fails after `IngestResult` success:** article is already in chainlens but job row not persisted; need idempotent re-run.
- [ ] **`record_token_usage` fails (DB error):** extraction already happened; must not fail the article, just log.
- [ ] **Redis down:** fall back to calling LLM directly (no cache), but this may double cost under concurrent load.
- [ ] **`to_chunks` raises `ChunkValidationError`:** catch in `_persist_canonical_articles`, log, continue batch.

### Triage

- **Critical — Security gap (Q4):** RESOLVED. `redact_pii` default context cannot reliably catch non-Vietnamese person names.
  - **Chosen solution (B + targeted masking):** Use LLM-extracted `person` entities to replace all raw `surface_forms` with `<NAME>` in the article text and in `metadata.entities`. Then run `redact_pii(..., context="default")` as a second pass for phone/email/remaining Vietnamese name patterns. Organization and location surface forms that contain a person substring are also masked.
  - Added `ponytail` note: if leakage persists, add a second regex pass or a `news` context to `redact_pii`.
- **Critical — Money gap (Q4):** RESOLVED. Entity extraction for free/BYOK workspaces can run every RSS poll.
  - **Chosen solution (reuse `memory/extract_budget.py`):** Add `app/services/news/extract_budget.py` with config keys `NEWS_ENTITY_EXTRACTION_*`, per-workspace limits, wallet pre-check, budget cap, and rate cap. The gate runs before any LLM call. If disabled/budget/rate/wallet blocks, return `[]` and log `news_entity_extraction_{reason}`.
  - Extend `ResolvedWorkspaceLimits`, `workspace_limits` table, and `app.config` to support `news_entity_extraction_item_cap`, `news_entity_extraction_spend_cap_micros`, `news_entity_extraction_wallet_pre_check`.
- **P0 surfaces touched:** `token_tracking_service.py`, `llm_service.py`, `chainlens/ingest.py`, `rss_indexer.py`, `workspace_limits.py`, `db.py` → must pass `bmad-nowing-integration-test`, `bmad-nowing-mutation-gate`, and `bmad-nowing-human-review-gate`.

**Recommendation:** Critical gaps resolved. Update story ACs and tasks to reflect the chosen PII masking and cost-control gate. Proceed to `bmad-nowing-test-first-atdd`.

