story_key: 22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui
status: done
baseline_commit: d1877927ca8681283e1858a7da054b1f413a9686
epic: 22
story: 3
---

# Story 22.3: Telegram Data Enrichment, Realtime Alert Trigger, AI Agent Tools & Scraper UI

Status: done


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
**When** the streaming download Celery task runs,
**Then** the media stream is piped directly into S3/MinIO using `aiobotocore` without buffering full files to worker disk (AD-4), and `telegram_media` records are created with storage URLs.

### AC-3 — Real-Time Alert Rule Triggering & Redis Stream
**Given** an active `AlertRule` (saved search) matching keywords or entities,
**When** a new message arrives on a monitored channel via `TelegramStreamDaemon`,
**Then** the message event is published to Redis Stream `stream:telegram:raw_events` and immediately evaluated against `AlertRule` criteria to dispatch in-app/Telegram notifications.

### AC-4 — AI Agent Chat Tools & LeadSourceAdapter
**Given** an AI Agent session in Nowing chat,
**When** the user asks to search Telegram channels or query recent posts,
**Then** `telegram_search_channel` and `telegram_fetch_recent_posts` tools execute queries over `telegram_messages` and format results with phone/price badges; and `TelegramLeadAdapter` satisfies `LeadSourceAdapter` ABC (AD-44).

### AC-5 — Admin Scraper UI Telegram Tab & Cooldown Timer
**Given** a superuser managing scraper accounts in `/admin/scraper-accounts/`,
**When** navigating to the Telegram tab,
**Then** accounts display status pills (Active 🟢, Rate-Limited 🟡, Cooldown 🔴 with live countdown timer), multi-step OTP/2FA onboarding modal is available, and monitored channels have realtime stream toggle switches.

---

## Tasks / Subtasks

- [x] **Task 1: Telegram Entity Extractor (`nowing_backend/app/proprietary/platforms/telegram/entity_extractor.py`)**
  - [x] Implement regex-based and NLP extraction for Vietnamese phone numbers, price patterns (tỷ, triệu, k), emails, and location keywords.
  - [x] Normalize entities into structured JSONB schema in `telegram_messages.raw_entities`.

- [x] **Task 2: S3 Media Streaming Offloader (`nowing_backend/app/tasks/telegram_media_tasks.py`)**
  - [x] Implement `download_telegram_media_task` using `aiobotocore`.
  - [x] Direct streaming upload without writing full files to disk.
  - [x] Record media metadata in `telegram_media` table.

- [x] **Task 3: Realtime Stream Daemon & Alert Evaluation (`nowing_backend/app/alerts/engine/telegram_listener.py`)**
  - [x] Implement leader election with Redis `SET telegram:daemon:leader val NX EX 30`.
  - [x] Hook incoming messages into `app.alerts.engine.notify.evaluate_alert_rules()`.

- [x] **Task 4: AI Agent Tools & LeadSourceAdapter (`nowing_backend/app/capabilities/telegram/`)**
  - [x] Implement agent tools: `telegram_search_channel`, `telegram_fetch_recent_posts`.
  - [x] Implement `TelegramLeadAdapter` registered in `LeadGenOrchestrator`.

- [x] **Task 5: Frontend Admin UI (`nowing_web/app/admin/scraper-accounts/`)**
  - [x] Add Telegram account management tab with status pills and live cooldown timer.
  - [x] Create Telegram OTP/2FA Onboarding Modal dialog.
  - [x] Channel subscription and realtime stream toggle switch.

- [x] **Task 6: Automated Testing & Verification**
  - [x] Unit tests for `TelegramEntityExtractor` covering Vietnamese edge cases.
  - [x] Unit tests for `TelegramLeadAdapter`.
  - [x] Integration tests for AlertRule matching on Telegram messages.

### Review Findings

- [x] [Review][Patch] Implement periodic heartbeat renewal loop and release Lua script for Redis leader election [app/proprietary/platforms/telegram/stream_daemon.py:30]
- [x] [Review][Patch] Wrap aiobotocore S3 client in async context manager and add abort_multipart_upload on error [app/tasks/telegram_media_tasks.py:20]
- [x] [Review][Patch] Escape MarkdownV2 special characters in Telegram alert notification dispatch [app/alerts/engine/notify.py:101]
- [x] [Review][Patch] Align TelegramLeadAdapter search_leads return type and remove AsyncMock prod import [app/lead_intelligence/adapters/telegram.py:38]
- [x] [Review][Patch] Fix compound pricing with 'k' / single-digit billion decimal and thousands dot formatting [app/proprietary/platforms/telegram/entity_extractor.py:245]
- [x] [Review][Patch] Guard string/list raw_entities and register tools properly in agent access layer [app/capabilities/telegram/tools.py:53]
- [x] [Review][Patch] Fix cooldown timer auto-transition when reaching 0s and validate 2FA password in modal [app/admin/scraper-accounts/page.tsx:336]
- [x] [Review][Patch] Add 'telegram', 'tele', 'tg' keywords to LeadSourceAdapterRegistry intent routing [app/lead_intelligence/adapters/registry.py:190]
- [x] [Review][Defer] Configure timeout and SSL options for smtplib.SMTP in alert notifications [app/alerts/engine/notify.py:122] — deferred, pre-existing
- [x] [Review][Defer] Connect full TanStack Query API endpoints for Telegram Userbot / Channel list when scraper DB endpoints are finalized [app/admin/scraper-accounts/page.tsx:227] — deferred, future epic



---

## Dev Agent Guardrails & Architectural Invariants

- **AD-4 (Streaming Media Upload):** Không đệm toàn bộ media file trên đĩa worker; bắt buộc stream trực tiếp vào S3/MinIO.
- **AD-5 (Leader Election):** Chỉ duy nhất 1 Stream Daemon instance được active thông qua Redis key `telegram:daemon:leader`.
- **AD-6 (Zero-Cache Sync):** Mọi thay đổi kênh hoặc message mới phải sync WAL tức thì lên Zero-cache.

---

## ATDD Artifacts

- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-22-3-telegram-data-enrichment-realtime-alerts-and-scraper-ui.md`
- **Unit & API Tests:**
  - `nowing_backend/tests/unit/platforms/telegram/test_entity_extractor.py` (8 tests)
  - `nowing_backend/tests/unit/platforms/telegram/test_lead_adapter.py` (5 tests)
  - `nowing_backend/tests/unit/tasks/test_telegram_media_tasks.py` (3 tests)
  - `nowing_backend/tests/unit/alerts/test_telegram_listener.py` (4 tests)
  - `nowing_backend/tests/unit/capabilities/telegram/test_agent_tools.py` (3 tests)
- **E2E Tests:** `nowing_web/tests/admin/telegram-scraper-accounts.spec.ts` (4 tests)

---

## Verification Commands

```bash
# 1. Run Entity Extractor & Adapter Unit Tests
cd nowing_backend
uv run pytest tests/unit/platforms/telegram/test_entity_extractor.py tests/unit/platforms/telegram/test_lead_adapter.py tests/unit/tasks/test_telegram_media_tasks.py tests/unit/alerts/test_telegram_listener.py tests/unit/capabilities/telegram/test_agent_tools.py -q

# 2. Frontend Typecheck & Biome
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check tests/admin/telegram-scraper-accounts.spec.ts
```

