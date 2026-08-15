# Story 22.1: Telegram Storage Schema & Public Web Preview Ingestion Engine

Status: completed

<!-- Governed by architecture-telegram-scraper-2026-08-15 (AD-1 to AD-8) -->

## Story

As an OSINT analyst, real estate investor, or brand monitor,
I want to ingest public Telegram channel messages via web previews (`https://t.me/s/{channel}`) without requiring an authenticated Telegram account,
So that I can monitor public community discussions, capture broadcast leads, and extract contact numbers with zero API credential footprint.

## Acceptance Criteria

1. **Given** a target public Telegram channel username (e.g. `batdongsanhanoi`, `diaocsaigon`), **When** `TelegramWebPreviewScraper` executes, **Then** it fetches HTML from `https://t.me/s/{channel_username}` using `selectolax` parsing with randomized user-agents and exponential backoff retry.
2. **Given** parsed web preview HTML, **When** messages are processed, **Then** records are saved into `telegram_channels` and `telegram_messages` with unique constraint `(channel_id, message_id)`.
3. **Given** message text, **When** `TelegramEntityExtractor` runs, **Then** it extracts phone numbers, prices, email addresses, and hashtags, storing them into `raw_entities JSONB` and assigning `intent_tag: 'sell'`, `'buy'`, `'seeking'`, or `'news'`.
4. **Given** message records with text, **When** vector embeddings are computed, **Then** vectors (`vector(1536)`) are stored with an HNSW cosine index for semantic message search.
5. **Given** an AI Agent session, **When** invoking `telegram_search_messages(channel_username, keyword, intent)`, **Then** matched messages with extracted contacts and timestamps are returned.

## Architectural Invariants Mapping

- **AD-1**: Tiered Ingestion Architecture (Tier 1: Zero-Login Web Preview `/s/` Ingress)
- **AD-2**: Storage Schema & Multi-Modal Separation (`telegram_channels`, `telegram_messages`, `telegram_media`)
- **AD-3**: HNSW Vector Indexing & GIN Full-Text Search
- **AD-4**: Entity & Intent Extraction Pipeline (SĐT VN, Price, Email)
- **AD-5**: Idempotent Upsert with Unique `(channel_id, message_id)`
- **AD-6**: AI Agent Tool Registration (`nowing_telegram_search_messages`)

## Tasks / Subtasks

- [x] Task 1: Database Models & Vector Storage (AC: 2, 4)
  - [x] 1.1 Tạo model `TelegramChannel` trong `nowing_backend/app/proprietary/platforms/telegram/models.py` (`id`, `username`, `title`, `description`/`about`, `subscribers_count`/`members_count`, `is_megagroup`, `is_public`/`is_active`, `created_at`, `updated_at`).
  - [x] 1.2 Tạo model `TelegramMessage` (`id`, `channel_id`, `message_id`, `author_username`/`author_name`, `text`, `published_at`/`date`, `views`, `forwards`, `replies_count`, `raw_entities JSONB`, `intent_tag`, `embedding vector(1536)`, `created_at`, `updated_at`, `CONSTRAINT uq_telegram_channel_message UNIQUE (channel_id, message_id)`).
  - [x] 1.3 Tạo model `TelegramMedia` (`id`, `message_id`, `media_type`, `file_id`, `file_name`, `mime_type`, `size_bytes`, `storage_url`, `upload_status`, `created_at`).
  - [x] 1.4 Thiết lập HNSW index `idx_telegram_msg_embedding` và GIN index `idx_telegram_msg_text_gin` / `idx_telegram_messages_entities_gin`.
- [x] Task 2: Public Web Preview Scraper (`t.me/s/`) (AC: 1, 2)
  - [x] 2.1 Xây dựng `TelegramWebPreviewScraper` tại `nowing_backend/app/proprietary/platforms/telegram/preview_scraper.py` (hỗ trợ async fetch, retry, rate limit handling).
  - [x] 2.2 Dùng `selectolax` bóc tách class `.tgme_widget_message_text`, `.tgme_widget_message_views`, `.tgme_widget_message_date`, `.tgme_channel_info`.
- [x] Task 3: Entity Extractor & Intent Classifier (AC: 3)
  - [x] 3.1 Xây dựng `TelegramEntityExtractor` tại `nowing_backend/app/proprietary/platforms/telegram/entity_extractor.py`.
  - [x] 3.2 Bóc tách SĐT tiếng Việt (+84, 09x, 08x, 07x, 03x, 05x), Email, Giá BĐS/mua bán (tỷ, triệu, k, USD, tr/m2), Hashtags.
  - [x] 3.3 Phân loại `intent_tag` (`sell`, `buy`, `seeking`, `news`).
- [x] Task 4: AI Agent Capability & Tools (AC: 5)
  - [x] 4.1 Đăng ký Capability `telegram.search` trong `nowing_backend/app/capabilities/telegram/`.
  - [x] 4.2 Định nghĩa Agent Tool `nowing_telegram_search_messages` và đăng ký vào `nowing_backend/app/mcp_tools.py`.
- [x] Task 5: Unit & Integration Tests (AC: 1-5)
  - [x] 5.1 `tests/unit/proprietary/platforms/telegram/test_preview_scraper.py` (Parser test với HTML preview fixture).
  - [x] 5.2 `tests/unit/proprietary/platforms/telegram/test_entity_extractor.py`.
  - [x] 5.3 `tests/unit/capabilities/test_telegram_capabilities.py`.

## Dev Notes

- **Zero-Login Invariant:** Web preview `https://t.me/s/{channel}` không yêu cầu Telegram API credentials (`api_id`/`api_hash`), giúp hệ thống hoạt động hoàn toàn độc lập với zero ban risk.
- **Dependencies:** `selectolax>=0.3.21`, `httpx>=0.27.0`, `pgvector>=0.3.0`.

### References
- [Architecture Spine: architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md]

