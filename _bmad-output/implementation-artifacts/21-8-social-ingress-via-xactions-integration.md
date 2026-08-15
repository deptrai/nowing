# Story 21.8: Social Ingress via XActions Integration (Facebook Groups & Twitter/X Feed)

Status: ready-for-dev

<!-- Note: Governed by architecture-xactions-social-integration-2026-08-15 (AD-SOC-1 to AD-SOC-7) -->

## Story

As a B2B sales development representative or real estate investor,
I want to ingest targeted Facebook Group posts and Twitter keyword searches via XActions integration (`/Users/luisphan/Documents/GitHub/XActions`),
So that I can capture real-time social conversations and extract contact numbers without building scrapers from scratch.

## Acceptance Criteria

1. **Given** target Facebook groups or Twitter search keywords, **When** `XActionsSocialAdapter` calls `x_facebook_group_posts` or `x_search_tweets`, **Then** raw social posts are fetched via XActions stealth session pool with sticky 1-to-1 residential proxy IP binding per account.
2. **Given** raw post data, **When** ingested into PostgreSQL, **Then** records are saved into `social_monitored_targets` and `social_posts` with unique constraint `(platform, external_post_id)` and event payload is pushed to Redis Stream `stream:social:raw_posts`.
3. **Given** post content, **When** `SocialEntityExtractor` processes the text, **Then** it runs a 3-step pipeline (pre-normalization of letter-substitutions `o/O->0`, punctuation stripping, Vietnamese regex pattern matching) protected by a 50ms timeout against ReDoS, extracting phone numbers (formats `0912...`, `o9.xx...`, `+84...`), prices, emails, and locations into `raw_entities JSONB`, and assigning `intent_tag: 'sell'`, `'buy'`, `'hiring'`, or `'seeking'`.
4. **Given** new ingested posts, **When** matching active `AlertRule` saved searches, **Then** `AlertEngine` fires instant notifications via Telegram/Email.
5. **Given** an AI Agent session, **When** calling `social_search_posts(platform, intent, keyword, limit)`, **Then** matched posts with extracted contact numbers and intent tags are returned.

## Tasks / Subtasks

- [ ] Task 1: Database Schema & SQLAlchemy Models (AC: 2)
  - [ ] 1.1 Tạo bảng `social_monitored_targets` (`id`, `platform`, `target_id`, `target_name`, `target_url`, `poll_interval_seconds`, `status`, `last_polled_at`).
  - [ ] 1.2 Tạo bảng `social_posts` (`id`, `platform`, `external_post_id`, `target_id`, `author_id`, `author_name`, `content`, `published_at`, `raw_entities JSONB`, `intent_tag`, `fit_score`, `reactions_count`, `comments_count`, `shares_count`, `created_at`, `CONSTRAINT uq_social_post UNIQUE (platform, external_post_id)`).
  - [ ] 1.3 Tạo Alembic migration và indexes (`idx_social_posts_intent`, `idx_social_posts_published`, `idx_social_posts_gin_entities`).
- [ ] Task 2: XActions Adapter & Stealth Proxy Ingress (AC: 1, 2)
  - [ ] 2.1 Xây dựng `XActionsSocialAdapter` tại `nowing_backend/app/proprietary/platforms/xactions/adapter.py` giao tiếp với local XActions MCP / Subprocess.
  - [ ] 2.2 Đảm bảo cấu hình proxy cố định (Sticky residential proxy) gắn chặt 1-to-1 với từng account/target.
  - [ ] 2.3 Đẩy raw post event vào Redis Stream `stream:social:raw_posts`.
- [ ] Task 3: 3-Step Vietnamese Phone & Entity Extraction Pipeline (AC: 3)
  - [ ] 3.1 Xây dựng `SocialEntityExtractor` tại `nowing_backend/app/proprietary/platforms/xactions/phone_extractor.py`.
  - [ ] 3.2 Viết pre-normalization chuyển chữ cái sang số (`o/O->0`, `l/I->1`, `không/chín->0/9`) và gỡ dấu cách/chấm đệm.
  - [ ] 3.3 Khai báo regex nhận diện đầu số di động VN hợp lệ (`03`, `05`, `07`, `08`, `09`, `+84`), bọc trong `asyncio.wait_for(..., timeout=0.05)` chống ReDoS.
  - [ ] 3.4 Phân loại `intent_tag` (`sell`, `buy`, `hiring`, `seeking`) dựa trên keywords từ vựng thương mại.
- [ ] Task 4: Celery Stream Consumer & Alert Trigger (AC: 2, 4)
  - [ ] 4.1 Xây dựng `social_stream_worker.py` tại `nowing_backend/app/tasks/` đọc Redis Stream theo consumer group `social_processors`.
  - [ ] 4.2 Bóc tách entity, chấm điểm Fit Score và thực hiện idempotent UPSERT vào `social_posts`.
  - [ ] 4.3 Kích hoạt `AlertEngine.evaluate_new_social_post()` gửi thông báo tức thời cho người dùng.
- [ ] Task 5: AI Agent Capability & Tools (AC: 5)
  - [ ] 5.1 Đăng ký Capability `social.search_leads` trong `app/capabilities/social/search_leads/`.
  - [ ] 5.2 Định nghĩa Agent Tool `social_search_posts` trả về danh sách lead kèm SĐT và Intent.
- [ ] Task 6: Unit & Integration Tests (AC: 1-5)
  - [ ] 6.1 `tests/unit/platforms/test_obfuscated_phone_regex.py` (10+ biến thể SĐT viết lách).
  - [ ] 6.2 `tests/unit/platforms/test_phone_regex_redos_safety.py` (Assert timeout $\le 50$ms trên chuỗi bệnh lý).
  - [ ] 6.3 `tests/integration/platforms/test_social_redis_stream.py` (Redis Stream $\rightarrow$ DB persistence).

## Dev Notes

- **Architecture Invariants:** Tuân thủ triệt để AD-SOC-1 đến AD-SOC-7 trong `architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md`.
- **Local XActions Path:** Giao tiếp với `/Users/luisphan/Documents/GitHub/XActions` qua MCP tools hoặc CLI.
- **PII Compliance:** Số điện thoại trích xuất được gán nhãn thương mại công khai trong Lead CRM theo chính sách bảo vệ dữ liệu.
- **Dependencies:** `phonenumbers>=8.13.0`, `redis>=5.2.1`.

### References
- [Architecture Spine: architecture-xactions-social-integration-2026-08-15/ARCHITECTURE-SPINE.md]
- [UX Contract: ux-contract-scrapers-expansion-and-lead-intelligence.md#U3]
