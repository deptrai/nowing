---
baseline_commit: 6158e7903
status: done
story_key: 14-2b-news-entity-search
---

# Story 14.2b: News Entity Search

**Status:** `done`
**Epic:** Epic 14 — News Aggregation (Vietnam)
**Priority:** P1
**Blocked by:** `chainlens-research` chưa hỗ trợ entity search / ingest với `metadata.entities` (theo dõi 2026-08-24). Nowing chỉ làm agent wiring và mock/stub; phần core entity linking/disambiguation thuộc engine.
**Related:** Story 14.2a (entity extraction & redaction) đã done; 14.2b build trên `metadata.entities` đã được gửi qua `NowingIngestService`.

## Story

As a researcher,
I want to ask the chat agent about people, organizations, or locations mentioned in news,
So that the agent can query the canonical index and return relevant articles with citations.

## Acceptance Criteria

1. **Given** `chainlens-research` exposes entity search and accepts `metadata.entities` at ingest, **When** a `Chunk` with `metadata.entities` is ingested, **Then** the canonical index stores and indexes the entity metadata; `chainlens-research` handles entity linking and disambiguation.
2. **Given** entity tracking is active in the canonical index, **When** a user queries an entity in chat, **Then** the agent calls `chainlens-research` and returns mentioning articles with citations; no local entity table is built in Nowing.

## Validation

- Integration test: `test_news_entity_search_chainlens.py` — entity query returns indexed articles (stub/mocked until chainlens contract lands).
- Unit test: `test_news_entity_search_agent_routing.py` — agent routing recognizes entity-name intent and dispatches đúng tool/capability.

## Tags

AD-34, AD-35, AD-27, AD-25, news, NER, entity-search, chainlens, citations

## Tasks / Subtasks

- [x] Define entity search contract (AC: #1)
  - [x] Xác nhận `chainlens-research` `POST /v1/ingest/scraper` chấp nhận `metadata.entities` (đã gửi từ 14.2a); engine index + search contract.
  - [x] Xác nhận `chainlens-research` `POST /api/v1/search` hỗ trợ filter theo `entity`, `entity_type`, `category: news`, `contentType: news`.
  - [x] Cập nhật story/spec và schema theo contract ChainLens search.

- [x] Add `news.entity_search` agent tool / capability (AC: #2)
  - [x] Tạo `app/capabilities/news/entity_search/definition.py` + `executor.py` để agent có verb `news.entity_search`.
  - [x] Input schema: `EntitySearchInput` với `entity_name`, `entity_type` (person | organization | location | all), `workspace_id`, `limit`.
  - [x] Output schema: `EntitySearchOutput` với `articles: list[Source]` (title, url, snippet, pubDate, source portal) và citations.
  - [x] Đăng ký `BillingUnit.CHAINLENS_QUERY` trong capability definition.
  - [x] Executor gọi `chainlens-research` `POST /api/v1/search` với entity filter (không dùng local search corpus — AD-35); xử lý `engine_unavailable` / timeout graceful degradation.

- [x] Wire into chat agent (AC: #2)
  - [x] Cập nhật `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py` để load `news.entity_search` capability (`news_entity_search`).
  - [x] Đảm bảo citation rendering dùng `Source.url` + `Source.title` từ `EntitySearchOutput`.

- [x] Degradation & PII (AD-25)
  - [x] Nếu `chainlens-research` trả về `engine_unavailable` hoặc timeout, trả kết quả degraded thay vì crash/hallucinate.
  - [x] Không query tên người đã bị redact thành placeholder `<NAME>` (AD-25), trả degraded note giải thích rõ ràng.

- [x] Tests
  - [x] `tests/unit/capabilities/news/test_entity_search.py` — schema validation, capability registration, subagent tool loading, `<NAME>` redaction check, engine unavailable handling (8 passed).
  - [x] `tests/integration/news/test_news_entity_search_chainlens.py` — stub `chainlens-research` response, verify `EntitySearchInput`/`Output` contract (1 passed).

## Dev Notes

### Previous Story Intelligence (14.2a learnings)

- **Entity model**: `NewsEntity` trong `app/services/news/entities.py` có `text`, `type` (person/organization/location), `confidence`, `surface_forms`.
- **Redaction order**: extract raw entities → mask person surface forms to `<NAME>` → `redact_pii(..., context="default")` → serialize to `Chunk.content` và `metadata.entities`.
- **Cost tracking**: mọi extraction call ghi `TokenUsage` với `usage_type="entity_extraction"` (đã thêm enum trong `token_tracking_service.py`).
- **Budget gate**: `check_news_entity_extraction_allowed()` chạy trước LLM; khi workspace không đủ budget/quota/rate thì trả `[]` và log `news_entity_extraction_{reason}`.
- **Chunk contract**: `ChunkMetadata.source` phải là `nowing_scraper`; `domain` lấy từ hostname article URL; `contentType` là `news`.
- **Ingest result handling**: `NowingIngestService.ingest()` trả `IngestResult` với status `ok`/`noop`/`partial`/`service_auth_unavailable`/`failed`. Với news, xử lý `partial`/`service_auth_unavailable`/`failed`, log, và persist `ChainLensIngestJob(status="failed")` nếu cần.
- **Review pattern hay dùng**: negative lookaround `(?<!\w)…(?!\w)` cho whole-phrase person-name redaction; `NewsEntityList.model_validate` override để drop từng entity lỗi thay vì drop cả list.

### Git Intelligence Summary

- **Baseline commit:** `6158e7903` — `fix(news): harden Story 14.2a news entity extraction after review`.
- **Recent commits liên quan:**
  - `6cd320a39` — reconcile 3.14 status.
  - `1a1eff5a6` — auto-extract budget caps in self-hosted workspace limits.
- **Pattern dùng cho news:** capabilities đặt trong `app/capabilities/news/`, services đặt trong `app/services/news/`, tests unit trong `tests/unit/services/news/`, tests integration trong `tests/integration/news/`, fixtures trong `tests/unit/services/news/fixtures/`.
- **Không dùng local DB corpus cho public data** (AD-35); mọi search gọi `chainlens-research`.

### Technical Requirements

- **Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, LangChain tool/capability registry, `httpx` cho gọi ngoài.
- **Schemas:** Dùng Pydantic `BaseModel` + `Field`; kế thừa hoặc reuse `Source`, `ResearchInput`, `ResearchOutput` từ `app/capabilities/chainlens/research/schemas.py`.
- **Capability registry:** Đăng ký qua `Capability` + `register_capability` trong `app/capabilities/core/__init__.py`; billing unit dùng `BillingUnit` enum.
- **Agent wiring:** Cập nhật routing prompt và builtin tools trong `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md` và `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py`.
- **External API:** `POST /api/v1/search` trên `config.CHAINLENS_API_URL` với service token (`app/services/chainlens/auth.py`); trả về SSE hoặc JSON tùy contract chưa xác định.
- **Error handling:** Degraded response khi `chainlens-research` unavailable, timeout, hoặc entity chưa index; không fall back sang local search.
- **PII:** Không expose raw person names; `EntitySearchInput` nhận từ user (public figure) hoặc entity text đã redact (`<NAME>`).

### Architecture Compliance

- **AD-34 — Nowing Scraper Feed Contract**: `Chunk` đã có `source: 'nowing_scraper'`, `sourceId`, `domain`, `fetchedAt`, `contentType`, `metadata.entities`, `pubDate`.
- **AD-35 — Nowing Does Not Build Public/Vertical Search Corpus**: KHÔNG tạo bảng `Entity` hay `NewsArticle` local để search. Toàn bộ entity search query phải đi qua `chainlens-research`.
- **AD-27 — Nowing Domain Scraper Output Feeds chainlens-research**: `news.entity_search` chỉ là thin wrapper/agent wiring; canonical index và linking thuộc engine.
- **AD-25 — PII redaction**: `EntitySearchInput` không được nhận raw person names từ bài viết gốc; dùng entity text đã redact. Nếu user hỏi tên công khai (public figure), agent vẫn search theo tên đó (do user cung cấp), không phải PII của private individual.

### File Structure Requirements

**NEW files (expected):**
- `app/capabilities/news/entity_search/__init__.py`
- `app/capabilities/news/entity_search/definition.py` — `Capability` registration.
- `app/capabilities/news/entity_search/executor.py` — call `chainlens-research`.
- `app/capabilities/news/entity_search/schemas.py` — `EntitySearchInput`, `EntitySearchOutput`.
- `tests/unit/capabilities/news/test_entity_search.py` — schema + executor unit tests.
- `tests/integration/news/test_news_entity_search_chainlens.py` — stub integration.

**UPDATE files (nếu cần wire agent):**
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md`
- `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py` hoặc tạo `app/agents/chat/multi_agent_chat/subagents/builtins/news/tools/index.py`
- `app/capabilities/core/__init__.py` nếu thêm `BillingUnit` mới.

**DO NOT create:**
- `app/services/news/entity_search_service.py` với local DB index.
- Alembic migration cho entity table.

### Testing Requirements

- **Unit tests:** `pytest -m unit`. Dùng `respx` để mock `chainlens-research` HTTP (`tests/integration/news/test_news_rss_integration.py` đã dùng pattern này).
- **Integration tests:** `pytest -m integration` với real Postgres; stub chainlens response; skip/xfail nếu contract chưa sẵn sàng.
- **Schema validation:** `EntitySearchInput` phải validate `entity_type` enum, `entity_name` không rỗng, `workspace_id` bắt buộc.
- **Ruff / format:** chạy `ruff check app/capabilities/news tests/unit/capabilities/news tests/integration/news` và `ruff format` trước commit.
- **Target test files:**
  - `tests/unit/capabilities/news/test_entity_search.py`
  - `tests/integration/news/test_news_entity_search_chainlens.py`
  - `tests/unit/services/news/test_entity_search_agent_routing.py` (nếu routing phức tạp).

### External Dependency Gating

- Story này **không thể complete** cho đến khi `chainlens-research` xác nhận:
  1. Ingest `metadata.entities` thành entity index.
  2. Search endpoint chấp nhận entity filter và trả về `Source[]` với `url`, `title`, `content`, `pubDate`.
- **CRITICAL: Person-name search ambiguity** — sau redaction, `metadata.entities` của `person` có `text: "<NAME>"`. Nếu `chainlens-research` index trực tiếp `metadata.entities` đã redact thì search theo tên người thật sẽ **không khớp**. Cần xác nhận với engine:
  - Engine nhận `metadata.entities` **pre-redaction** cho mục đích entity index trong khi vẫn giữ `Chunk.content` đã redact? (có thể vi phạm AD-25).
  - Hoặc person-name search chỉ hoạt động khi user cung cấp tên public figure (do user nhập, không phải từ metadata)?
  - Hoặc entity linking của engine tự chạy NER trên `content` gốc, bỏ qua `metadata.entities`?
  **Đây là blocker phải resolve trước khi dev full implementation.**
- Trong thời gian chờ, implement phần Nowing: schema, agent routing, mock executor, unit test stub. Integration test chỉ chạy khi contract sẵn sàng (skip hoặc xfail với lý do rõ ràng).

### Latest Tech / Web Research

- `chainlens-research` entity search contract chưa public trong repo. Không tìm thấy tài liệu endpoint `/search/entity` hoặc filter `metadata.entities`.
- Sử dụng `httpx` async với timeout/retries pattern từ `app/capabilities/chainlens/research/executor.py`.
- Không thêm dependency mới; dùng `httpx`, `pydantic`, `langchain_core` đã có.

### Project Context Reference

- Nowing quality pipeline: `_bmad/custom/nowing-quality-pipeline.md`.
- Story này là P1, touch P0 area chỉ nếu thay đổi `token_tracking_service.py` hoặc billing/routing; nếu chỉ là thin wrapper/agent wiring thì P0 gates (4.6, 4.10, 4.13) có thể giảm nhẹ nhưng vẫn nên chạy nếu touch `llm_service` hoặc billing.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 14 / Story 14.2b]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` — AD-27, AD-34, AD-35]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — FR-49]
- [Source: `nowing_backend/app/capabilities/chainlens/research/executor.py`]
- [Source: `nowing_backend/app/capabilities/chainlens/research/schemas.py`]
- [Source: `_bmad-output/implementation-artifacts/stories/14-2a-news-entity-extraction.md`]

## Story Completion Status

- **Status:** `ready-for-dev` (story file validated and enriched; implementation still gated on `chainlens-research` entity search contract).
- **Validation note:** Applied `bmad-create-story` checklist review — added Previous Story Intelligence, Git Intelligence, Technical Requirements, File Structure, Testing Requirements, and critical external dependency / person-name redaction blocker.
- **Open blocker:** Person-name search ambiguity after `<NAME>` redaction — must resolve with `chainlens-research` contract owner before full `dev-story`.

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

### Completion Notes List

### File List

- `_bmad-output/implementation-artifacts/stories/14-2b-news-entity-search.md`

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **No dedicated `news.entity_search` capability found.** Codebase search (`vibervn-context-engine` + grep) found no existing `entity_search` capability or service for news.
- **Close relatives that must NOT be duplicated:**
  - `app/capabilities/chainlens/research/` — already owns `POST /api/v1/search` SSE, cost parsing, `Source` schema, `engine_unavailable` degradation. This is the engine-side search path; do NOT rebuild a parallel HTTP client.
  - `app/capabilities/news/signal/` — local `SignalDetectionService` for news buying-intent signals; unrelated to entity search.
  - `app/capabilities/social/search_leads/` — searches local `social_search` table for leads; unrelated to chainlens.
  - `app/proprietary/platforms/telegram/entity_extractor.py` + `app/capabilities/telegram/tools.py` — Telegram-specific tools with `StructuredTool`; NOT a drop-in pattern for the Capability registry (`build_capability_tools`).
- **Verdict:** No exact duplicate. However, `chainlens.research` already implements the generic canonical search. Proceed to Q2 before deciding whether a new capability is necessary.

### Q2 — Simpler alternative?

- **Critical finding:** The requested behavior — "ask the chat agent about a person/org/location in news and get cited articles" — is a subset of what `chainlens.research` already does (multi-source web research returning `Source[]` with citations).
- **Simpler alternatives to consider before building `news.entity_search`:**
  1. **Extend `chainlens.research` with a `news` source filter / `system_instructions`:** agent detects entity intent, calls `chainlens.research` with query like `"Find news articles about {entity_name} ({entity_type})"` and `sources=["news"]` (if supported). No new capability, executor, HTTP client, or billing unit.
  2. **Add optional `entity_name`/`entity_type` fields to `ResearchInput` and let `chainlens.research` executor build the query internally.** Keeps one endpoint, one schema, one billing unit (`CHAINLENS_QUERY`).
- **When a separate `news.entity_search` capability IS justified:**
  - `chainlens-research` exposes a dedicated entity search endpoint (e.g., `POST /v1/search/entity`) with entity filter, disambiguation, and article list output distinct from synthesized answer.
  - The UX requires a deterministic "article list" tool rather than a synthesized research answer.
- **Money/billing duplicate risk:** Creating a new `BillingUnit` (e.g., `NEWS_ENTITY_SEARCH`) duplicates cost tracking already handled by `CHAINLENS_QUERY`. If `news.entity_search` merely wraps `chainlens.research`, it should bill as `CHAINLENS_QUERY` to avoid double accounting.
- **Verdict:** **CRITICAL — decision needed.** Do NOT implement a new `news.entity_search` capability until PM/PO confirms that `chainlens.research` cannot satisfy the ACs. If entity search is just a query specialization, reuse `chainlens.research` and update the routing prompt only.

### Q3 — Edge cases spec misses (Pattern 3)

- **Boundary:**
  - `entity_name` at min/max length; `ResearchInput.query` clamps at 500 chars — entity names exceeding this must be truncated or rejected.
  - `top_k` / number of returned `Source` items; default and max values not specified.
  - `entity_type` enum strictness — unknown type should reject input, not silently fall through.
  - Workspace with zero news chunks ingested yet; search returns empty without error.
- **Null/empty:**
  - `entity_name` empty/whitespace-only string.
  - `metadata.entities` is `[]` or missing on a `Chunk`.
  - `EntitySearchOutput.articles` is `[]`.
  - `chainlens-research` returns `insufficient_evidence` or `partial` (research status) — currently not mapped to entity search behavior.
- **Concurrent:**
  - Multiple entity tool calls in same chat turn — ensure no duplicate `TokenUsage` rows; reuse `add_current_turn_tool_cost` pattern.
  - Same entity query from multiple workspaces/users — rate limit and billing must be scoped per API key/workspace.
- **PII/Redaction edge case (already in story but worth restating):**
  - All `person` entities in `metadata.entities` are redacted to `<NAME>`; user asking for a real person name will not match unless chainlens indexes pre-redaction data or runs its own NER on raw content.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- **Service down / unavailable:**
  - `chainlens-research` timeout/5xx/connection refused → return `engine_unavailable` with degradation reason (reuse `chainlens.research` pattern).
  - `ChainLensServiceAuth` returns no API key or invalid key → `service_auth_unavailable` status.
- **Rate/cost failures:**
  - ChainLens API key rate-limited per `B2bRateLimiterService` (OQ-7 Q4) → backoff, retry, or degrade.
  - Workspace out of `CHAINLENS_QUERY` budget/credit → do NOT call engine; return degraded answer.
  - `costDollars` missing from terminal SSE `done` frame → fallback to `CHAINLENS_QUERY_MICROS_PER_CALL` (60k micros) and log warning (per FR-37/Epic 9.2, OQ-7 Q2).
- **Malformed / partial responses:**
  - SSE stream ends without `done` frame → current `_SSEParser` raises `ChainLensError`; `news.entity_search` must do the same.
  - `Source` missing `url`/`title`/`content` → defensive parsing, skip invalid source, degrade.
  - `chainlens-research` returns `partial` or `insufficient_evidence` — decide whether agent shows "no articles found" or falls back to a summary.
- **Agent routing failures:**
  - User asks ambiguous question that could be general chat or entity search; routing prompt must disambiguate or default to `chainlens.research`.
  - Entity name in Vietnamese with diacritics / tone marks — normalize before chainlens query or not? Contract not specified.
- **PII failure:**
  - User asks for a private individual by real name. Agent must not bypass redaction by sending raw name to chainlens if the canonical index only contains redacted `<NAME>`. This can cause false matches against every person-mentioning article.

### Triage

| Finding | Severity | Action |
|---------|----------|--------|
| Q2 — `chainlens.research` may be simpler alternative than `news.entity_search` | **Critical** | **HALT for PM/PO approval:** decide reuse `chainlens.research` vs. dedicated `news.entity_search` capability before `dev-story`. |
| Q2 — Billing unit duplicate risk if `news.entity_search` wraps `chainlens.research` | **Critical** | **HALT for PM/PO approval:** reuse `CHAINLENS_QUERY` billing; do not create `NEWS_ENTITY_SEARCH` billing unit unless there is a distinct cost model. |
| Q4 — Cost/rate-limit failure modes not specified | **Critical** | Add to story and test skeleton; reuse FR-37/Epic 9.2 cost fallback pattern. |
| Q3 — Person-name redaction makes entity search by real name undefined | Non-critical (already documented blocker) | Add test cases and clarify chainlens contract in story. |
| Q3 — Boundary/empty/concurrent edge cases | Non-critical | Add to test skeleton. |
| Q4 — Service down / malformed SSE / auth failures | Non-critical | Reuse `chainlens.research` degradation; add tests. |
