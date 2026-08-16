story_key: 22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui
status: ready-for-dev
baseline_commit: d1877927ca8681283e1858a7da054b1f413a9686
epic: 22
story: 3
---

# Story 22.3: Telegram Data Enrichment, Realtime Alert Trigger, AI Agent Tools & Scraper UI

Status: ready-for-dev

<!-- Note: Governed by FR-74, FR-75, FR-76, AD-1 to AD-8, and Architecture Spine: epics.md (Epic 22) -->

## Story

As a market intelligence user and AI researcher,
I want scraped Telegram messages to have entities extracted, media offloaded to S3, real-time alerts fired for matching posts, AI agent search tools enabled, and account status visible on the dashboard,
So that I receive instant listing leads, query Telegram history via AI chat, and manage scraper channels easily.

---

## Acceptance Criteria

### AC-1 — Vietnamese Entity Extraction (Phone, Price, Email)
**Given** raw Telegram message text containing Vietnamese phone numbers (`0912.345.678`, `+84987654321`), prices (`12.5 tỷ`, `35 triệu/tháng`), or emails,
**When** `TelegramEntityExtractor.extract_entities(text)` runs,
**Then** all detected entities are normalized and stored in `telegram_messages.raw_entities` JSONB, falling back safely to `[]` when message has no text.

### AC-2 — Non-Blocking S3/MinIO Streaming Media Offload
**Given** a Telegram message containing media files (photos, documents),
**When** text ingestion finishes,
**Then** `download_telegram_media_task` streams media < 5MB directly via single `put_object` (or multipart upload with >= 5MB parts for large files) directly to S3/MinIO using `aiobotocore`, updating `telegram_media` with `storage_url` without buffering the full file on worker disk.

### AC-3 — Telegram Realtime Stream Daemon & Alert Engine Integration
**Given** the `TelegramStreamDaemon` running with Redis leader election (`telegram:daemon:leader`),
**When** a new message arrives on a monitored channel via `@client.on(events.NewMessage)`,
**Then** the event is pushed to Redis Stream `stream:telegram:raw_events`, processed by Celery, and evaluated against active `AlertRule` saved searches in `app/alerts/engine/notify.py`.

### AC-4 — AI Agent Chat Tools & Lead Source Adapter
**Given** a user chatting with Nowing AI Assistant or running lead discovery,
**When** the agent calls `telegram_search_channel(channel, query, limit)` or `telegram_fetch_recent_posts(channel, limit)`,
**Then** it queries `telegram_messages` and returns formatted post summaries with author, date, views, and extracted phone numbers.
**And** `TelegramLeadAdapter` implements `LeadSourceAdapter` (AD-44), converting message entities and contacts into standard `Lead` records streamed directly into the Split-View Table Matrix.

### AC-5 — Admin Scraper UI Telegram Tab & Live Cooldown Countdown
**Given** an administrator accessing `/admin/scraper-accounts` on `nowing_web`,
**When** viewing the Telegram tab,
**Then** the UI displays account statuses (`Active`, `Rate-Limited`, `Cooldown` with live countdown timer), token balances, an OTP/2FA onboarding modal, and a channel management table with realtime stream toggles.

---

## Tasks / Subtasks

- [ ] **Task 1: Telegram Entity Extractor (`nowing_backend/app/proprietary/platforms/telegram/entity_extractor.py`)**
  - [ ] Implement regex-based and NLP extraction for Vietnamese phone numbers, price patterns (tỷ, triệu, k), emails, and location keywords.
  - [ ] Normalize entities into structured JSONB schema in `telegram_messages.raw_entities`.

- [ ] **Task 2: S3 Media Streaming Offloader (`nowing_backend/app/tasks/telegram_media_tasks.py`)**
  - [ ] Implement `download_telegram_media_task` using `aiobotocore`.
  - [ ] Direct streaming upload without writing full files to disk.
  - [ ] Record media metadata in `telegram_media` table.

- [ ] **Task 3: Realtime Stream Daemon & Alert Evaluation (`nowing_backend/app/alerts/engine/telegram_listener.py`)**
  - [ ] Implement leader election with Redis `SET telegram:daemon:leader val NX EX 30`.
  - [ ] Hook incoming messages into `app.alerts.engine.notify.evaluate_alert_rules()`.

- [ ] **Task 4: AI Agent Tools & LeadSourceAdapter (`nowing_backend/app/capabilities/telegram/`)**
  - [ ] Implement agent tools: `telegram_search_channel`, `telegram_fetch_recent_posts`.
  - [ ] Implement `TelegramLeadAdapter` registered in `LeadGenOrchestrator`.

- [ ] **Task 5: Frontend Admin UI (`nowing_web/app/admin/scraper-accounts/`)**
  - [ ] Add Telegram account management tab with status pills and live cooldown timer.
  - [ ] Create Telegram OTP/2FA Onboarding Modal dialog.
  - [ ] Channel subscription and realtime stream toggle switch.

- [ ] **Task 6: Automated Testing & Verification**
  - [ ] Unit tests for `TelegramEntityExtractor` covering Vietnamese edge cases.
  - [ ] Unit tests for `TelegramLeadAdapter`.
  - [ ] Integration tests for AlertRule matching on Telegram messages.

---

## Dev Agent Guardrails & Architectural Invariants

- **AD-4 (Streaming Media Upload):** Không đệm toàn bộ media file trên đĩa worker; bắt buộc stream trực tiếp vào S3/MinIO.
- **AD-5 (Leader Election):** Chỉ duy nhất 1 Stream Daemon instance được active thông qua Redis key `telegram:daemon:leader`.
- **AD-6 (Zero-Cache Sync):** Mọi thay đổi kênh hoặc message mới phải sync WAL tức thì lên Zero-cache.

---

## Verification Commands

```bash
# 1. Run Entity Extractor & Adapter Unit Tests
cd nowing_backend
uv run pytest tests/unit/platforms/telegram/test_entity_extractor.py tests/unit/platforms/telegram/test_lead_adapter.py -q

# 2. Frontend Typecheck & Biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check app/admin/scraper-accounts/
```
