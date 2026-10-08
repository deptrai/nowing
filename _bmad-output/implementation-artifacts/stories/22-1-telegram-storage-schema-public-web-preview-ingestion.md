---
story_key: 22-1-telegram-storage-schema-public-web-preview-ingestion
story_id: "22.1"
epic: "22"
status: done
architecture: _bmad-output/planning-artifacts/architecture/architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md
source: _bmad-output/planning-artifacts/epics.md
---

# Story 22.1: Telegram Storage Schema & Public Web Preview Ingestion Engine

> Governed by `architecture-telegram-scraper-2026-08-15` (AD-1 to AD-8).

## Story

As an OSINT analyst, real estate investor, or brand monitor,
I want to store Telegram channel metadata and scrape public channel messages via zero-login web preview (`https://t.me/s/{channel}`),
So that I can monitor public community discussions, capture broadcast leads, and extract contact numbers with zero API credential footprint.

## Acceptance Criteria

1. **Given** a clean or existing database environment, **When** Alembic migration `210_add_telegram_scraper_tables.py` is executed, **Then** tables `telegram_channels`, `telegram_messages`, and `telegram_media` are created with composite unique constraint `(channel_id, message_id)`, `embedding vector(1536)` with HNSW `vector_cosine_ops`, and GIN indexes for full-text search and `raw_entities` JSONB.
2. **Given** a valid public Telegram channel username or URL (e.g. `batdongsan_vietnam` or `https://t.me/s/batdongsan_vietnam`), **When** `TelegramWebPreviewScraper.scrape_channel(channel_username, before=None, after=None)` is called, **Then** the scraper fetches `https://t.me/s/{channel_username}` with a randomized desktop User-Agent, parses message text, views, date, author, and media thumbnails using `selectolax`, and retries with exponential backoff on `429`/`503`.
3. **Given** a public channel page with non-text messages (photos/stickers without caption, edited posts, or album posts with `?single`), **When** `parse_messages()` runs, **Then** it gracefully sets `text=""`, sets `has_media=True`, extracts thumbnail URLs, and does not raise unhandled parsing exceptions.
4. **Given** existing messages in `telegram_messages` for a channel, **When** a subsequent scrape processes the same `(channel_id, message_id)`, **Then** PostgreSQL executes `INSERT ... ON CONFLICT (channel_id, message_id) DO UPDATE` updating `text`, `views`, `forwards`, `replies_count`, `raw_entities`, `intent_tag`, `has_media`, and `updated_at` without duplicating rows or raising unique constraint errors.
5. **Given** message text, **When** `TelegramEntityExtractor` runs, **Then** it extracts Vietnamese phone numbers, BĐS prices, emails, hashtags, locations, and assigns `intent_tag` (`sell`, `buy`, `seeking`, `news`), storing typed entities into `raw_entities` JSONB.
6. **Given** a request to the `telegram.search` capability, **When** `search_telegram_messages(payload)` executes, **Then** it returns `TelegramSearchOutput` with filtered/paginated `TelegramMessageParsed` messages and `billable_units = len(messages)`.

## Architectural Invariants Mapping

- **AD-1** — Tiered Ingestion: Tier 1 public preview via `TelegramWebPreviewScraper` (`t.me/s/`) before MTProto.
- **AD-2** — Storage Schema & Multi-Modal Separation: `telegram_channels`, `telegram_messages`, `telegram_media`.
- **AD-3** — HNSW Vector Indexing & GIN Full-Text Search: `idx_telegram_msg_embedding`, `idx_telegram_msg_text_gin`, `idx_telegram_messages_entities_gin`.
- **AD-4** — Entity & Intent Extraction: `TelegramEntityExtractor` (phone, price, email, hashtag, location).
- **AD-5** — Idempotent Upsert: `ON CONFLICT (channel_id, message_id) DO UPDATE`.
- **AD-6** — Capability Registration: `telegram.search` in `app/capabilities/telegram/search/definition.py`, with MCP catalog entry `nowing_telegram_search_messages` in `app/mcp_tools.py`.

## Review Findings & Fixes Applied (2026-08-15)

- [x] RF-1: Created Alembic migration `210_add_telegram_scraper_tables.py` creating `telegram_channels`, `telegram_messages`, and `telegram_media`.
- [x] RF-2: Created `TelegramChannel` model with `id` (Telegram peer ID / BIGINT primary key), `username`, `title`, `about`, `members_count`, `last_scraped_message_id`, `is_megagroup`, and `is_active`.
- [x] RF-3: Created `TelegramMessage` model with `id` (UUID), `channel_id`, `message_id` (external BIGINT), `date`, `text`, `raw_entities` JSONB, `author_user_id`, `author_username`, `views`, `forwards`, `replies_count`, `grouped_id`, `has_media`, `intent_tag`, `embedding vector(1536)`, and `uq_telegram_channel_message`.
- [x] RF-4: Added HNSW `idx_telegram_msg_embedding`, GIN `idx_telegram_msg_text_gin`, and `idx_telegram_messages_entities_gin`.
- [x] RF-5: Added `TelegramWebPreviewScraper.sanitize_username()` stripping `https://t.me/s/`, `https://t.me/`, `t.me/`, `@` and validating `^[a-zA-Z0-9_]{4,32}$`.
- [x] RF-6: Added safe newline extraction in `_extract_text_with_newlines` preserving `<br>` and `</p>` without raw `html.unescape` vulnerabilities.
- [x] RF-7: Supported optional injected `httpx.AsyncClient` and async context manager in `TelegramWebPreviewScraper` for connection pooling.
- [x] RF-8: Fixed 429/503 backoff logging and tracking `last_err`.
- [x] RF-9: Handled album post message IDs containing `?single` query parameter.
- [x] RF-10: Handled European view counts `1,5K` and non-breaking space `\xa0` in `parse_count`.
- [x] RF-11: Added `(?<!\w)` lookbehind to VN phone regex to prevent matching alphanumeric SKU codes, and expanded price regex for thousand separators (`1.500.000 đ`).
- [x] RF-12: Fixed `TelegramSearchOutput.billable_units` to return `len(self.messages)` (0 units when no results).

## Tasks / Subtasks

- [x] Task 1: Database schema (AC: 1)
  - [x] 1.1 Migration `alembic/versions/210_add_telegram_scraper_tables.py`.
  - [x] 1.2 Models in `nowing_backend/app/proprietary/platforms/telegram/models.py`.
- [x] Task 2: Public web preview scraper (`t.me/s/`) (AC: 2, 3)
  - [x] 2.1 `TelegramWebPreviewScraper` in `app/proprietary/platforms/telegram/preview_scraper.py`.
  - [x] 2.2 Pydantic schemas in `app/proprietary/platforms/telegram/schemas.py`.
  - [x] 2.3 `selectolax` CSS selectors: `.tgme_widget_message_text`, `.tgme_widget_message_views`, `.tgme_widget_message_date`, `.tgme_channel_info`.
- [x] Task 3: Idempotent persistence schema (AC: 4)
  - [x] 3.1 Unique constraint `uq_telegram_channel_message` on `(channel_id, message_id)`.
  - [x] 3.2 `ON CONFLICT (channel_id, message_id) DO UPDATE` semantics modeled in `TelegramMessage`.
- [x] Task 4: Entity extraction & intent classification (AC: 5)
  - [x] 4.1 `TelegramEntityExtractor` in `app/proprietary/platforms/telegram/entity_extractor.py`.
  - [x] 4.2 Extraction of SĐT VN (+84, 03x, 05x, 07x, 08x, 09x), email, BĐS prices (tỷ/triệu/k/USD/tr/m²), hashtags, locations.
  - [x] 4.3 `intent_tag` classification (`sell`, `buy`, `seeking`, `news`).
- [x] Task 5: Capability registration (AC: 6)
  - [x] 5.1 Capability `telegram.search` in `app/capabilities/telegram/search/definition.py`.
  - [x] 5.2 Executor in `app/capabilities/telegram/search/executor.py`.
  - [x] 5.3 Input/output schemas in `app/capabilities/telegram/search/schemas.py`.
  - [x] 5.4 MCP catalog entry `nowing_telegram_search_messages` in `app/mcp_tools.py`.
- [x] Task 6: Tests
  - [x] 6.1 `tests/unit/proprietary/platforms/telegram/test_preview_scraper.py` (parser + fetch fixtures).
  - [x] 6.2 `tests/unit/proprietary/platforms/telegram/test_entity_extractor.py`.
  - [x] 6.3 `tests/unit/proprietary/platforms/telegram/test_client.py` (MTProto client, Story 22.2).
  - [x] 6.4 `tests/unit/capabilities/test_telegram_capabilities.py` (MCP catalog + capability executor).
  - [x] 6.5 `tests/unit/capabilities/telegram/test_agent_tools.py` (agent tools, Story 22.3).

## ATDD Artifacts

- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-22-1-telegram-storage-schema-public-web-preview-ingestion.md`
- **Active unit tests (green):**
  - `nowing_backend/tests/unit/proprietary/platforms/telegram/test_preview_scraper.py::test_parse_messages_non_text_and_album`
  - `nowing_backend/tests/unit/proprietary/platforms/telegram/test_preview_scraper.py::test_scrape_channel_retries_429_503_with_backoff`
- **Red-phase integration scaffolds:**
  - `nowing_backend/tests/integration/db/test_migration_210_telegram_schema.py`
  - `nowing_backend/tests/integration/proprietary/platforms/telegram/test_telegram_persistence_idempotency.py`
  - `nowing_backend/tests/integration/routes/test_telegram_search.py`
- **Red-phase E2E scaffold:**
  - `nowing_web/tests/playground/telegram-search.spec.ts`

## Dev Notes

- **Zero-Login Invariant:** Web preview `https://t.me/s/{channel}` does not require Telegram API credentials (`api_id`/`api_hash`), giving zero ban risk for public scans.
- **Dependencies:** `selectolax>=0.3.21`, `httpx>=0.27.0`, `pgvector>=0.3.0`.
- **Cross-story boundary:** Agent-facing chat tools (`telegram_search_channel`, `telegram_fetch_recent_posts`) and the DB query implementation in `query_telegram_messages()` belong to **Story 22.3** (`app/capabilities/telegram/tools.py`). Story 22.1 owns the capability executor, MCP catalog registration, and public preview scraper.
- **Model/migration drift note:** Migration 210 defines `telegram_channels.id` with `autoincrement=True` and a separate nullable `peer_id` column, whereas `models.py` treats `id` as the Telegram peer ID and does not map `peer_id`. A future story should reconcile this if the channel persistence path becomes active.

## References

- [Architecture Spine: architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md]
- [Epic 22: _bmad-output/planning-artifacts/epics.md]
