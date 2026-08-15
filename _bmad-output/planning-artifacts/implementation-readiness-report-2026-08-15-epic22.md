---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
date: "2026-08-15"
project: "Nowing"
feature: "Epic 22: Telegram Scraper & Channel Ingestion Engine"
readiness_verdict: "READY"
---

# Implementation Readiness Assessment Report

**Date:** 2026-08-15  
**Project:** Nowing  
**Feature Focus:** Epic 22 — Telegram Scraper & Channel Ingestion Engine  
**Assessor:** BMAD Implementation Readiness Specialist  

---

## 1. Document Discovery & Inventory

| Document Type | File Path | Status |
| :--- | :--- | :---: |
| **Requirements / Research** | [`_bmad-output/planning-artifacts/research/technical-telegram-scraper-integration-research-2026-08-15.md`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/technical-telegram-scraper-integration-research-2026-08-15.md) | ✅ Complete |
| **Architecture Specification** | [`_bmad-output/planning-artifacts/architecture/architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-telegram-scraper-2026-08-15/ARCHITECTURE-SPINE.md) | ✅ Final (AD-1 to AD-8) |
| **Epics & User Stories** | [`_bmad-output/planning-artifacts/epics.md`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md) (Epic 22: Stories 22.1, 22.2, 22.3) | ✅ Ready-for-dev |
| **UX Design Contract** | [`_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-telegram-scraper-engine.md`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-telegram-scraper-engine.md) | ✅ Complete (U1 to U7) |
| **Sprint Tracking** | [`_bmad-output/implementation-artifacts/sprint-status.yaml`](file:///Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml) | ✅ Aligned |

---

## 2. Requirements & Traceability Analysis

### Functional Requirements Extracted:
* **FR-70 (Web Preview Scraper):** Cào tin nhắn các kênh Telegram công khai qua HTTP `https://t.me/s/{channel}` bằng `httpx` + `selectolax` (Stateless, Zero-risk, không tốn session slot).
* **FR-71 (MTProto Client Ingestion):** Kết nối qua `telethon` để cào các kênh/nhóm riêng tư, luồng bình luận (discussion replies), tin nhắn forward và metadata thành viên.
* **FR-72 (Platform Account & Session Onboarding):** Quản lý tài khoản Telegram trong `scraper_platform_accounts`, hỗ trợ xác thực SMS OTP / Telegram App Code & 2FA Cloud Password, mã hóa `StringSession` bằng AES-256 đối xứng.
* **FR-73 (Rate Limiter & FloodWait Cooldown):** Tích hợp `ScraperPlatformAccountRotator`, tự động sleep và cách ly tài khoản khi gặp `FloodWaitError(seconds=N)`.
* **FR-74 (Async S3 Media Streaming):** Celery task tải ảnh/video/tài liệu dạng stream trực tiếp lên S3/MinIO qua `aiobotocore` (single `put_object` < 5MB, multipart $\ge$ 5MB).
* **FR-75 (Telegram Entity Extraction):** Tự động bóc tách Số điện thoại Việt Nam, Email, Giá tiền BĐS, Địa điểm, Hashtags vào trường `raw_entities` JSONB.
* **FR-76 (Realtime Event Stream Daemon):** Daemon chạy nền lắng nghe sự kiện `events.NewMessage` với Redis leader election, đẩy payload vào Redis Stream `stream:telegram:raw_events`.
* **FR-77 (Alert Engine & Saved Searches Trigger):** Tự động kích hoạt thông báo tức thời khi bài đăng Telegram mới khớp với bộ lọc/từ khóa của Saved Search.
* **FR-78 (Nowing AI Agent Tools):** Đóng gói tool `telegram_search_channel` và `telegram_fetch_recent_posts` cho Nowing Chat/Research Agent.
* **FR-79 (PostgreSQL Storage & Zero Cache Sync):** Lưu trữ bảng `telegram_channels`, `telegram_messages`, `telegram_media` với ràng buộc UPSERT `(channel_id, message_id)` và đồng bộ realtime lên giao diện qua Zero Cache.

---

## 3. Epic Coverage Validation Matrix

| FR ID | Mô tả Yêu cầu | Story Đảm nhiệm | Trạng thái Bao phủ |
| :--- | :--- | :--- | :---: |
| **FR-70** | Telegram Web Preview Scraper | **Story 22.1** | ✅ 100% Covered |
| **FR-71** | Telegram MTProto Client Ingestion | **Story 22.2** | ✅ 100% Covered |
| **FR-72** | Platform Accounts & Encrypted Session Onboarding | **Story 22.2** | ✅ 100% Covered |
| **FR-73** | Rate Limiter & FloodWait Cooldown State Machine | **Story 22.2** | ✅ 100% Covered |
| **FR-74** | Async S3 Media Streaming | **Story 22.3** | ✅ 100% Covered |
| **FR-75** | Telegram Entity Extraction (Phone / Price / Email) | **Story 22.3** | ✅ 100% Covered |
| **FR-76** | Realtime Stream Daemon (`stream:telegram:raw_events`) | **Story 22.3** | ✅ 100% Covered |
| **FR-77** | Alert Engine & Saved Searches Trigger | **Story 22.3** | ✅ 100% Covered |
| **FR-78** | Nowing AI Agent Tools (`telegram_search_channel`) | **Story 22.3** | ✅ 100% Covered |
| **FR-79** | PostgreSQL Schema (`pgvector` + GIN) & Zero Cache | **Story 22.1** | ✅ 100% Covered |

* **Tỷ lệ bao phủ FR:** **10/10 (100%)**
* **Số lượng Story mồ côi (Unmapped requirements):** **0**

---

## 4. UX & Architecture Alignment Assessment

### UX Alignment:
- **UX Contract Status:** ✅ Đầy đủ tại `ux-contract-telegram-scraper-engine.md`.
- **Giao diện quản trị:**
  * Multi-step Modal xác thực Telegram (SĐT $\rightarrow$ OTP $\rightarrow$ 2FA Password).
  * Account Health Table với Badge `Active`, `Rate-Limited`, `Cooldown` kèm Countdown Timer đồng bộ qua Zero Cache.
  * Monitored Channel Table với toggle `Web Preview` vs `MTProto Deep` và `Realtime Stream`.
- **AI Chat Widget:**
  * Widget Card trong khung chat hiển thị bài đăng Telegram có Pill Copy SĐT nhanh, Highlight Giá BĐS và Thumbnail Lightbox S3.

### Architecture Alignment (Invariants Compliance):
- **AD-1 (Hybrid Ingestion):** Tách bạch Web Preview (Fast-path) và MTProto (Deep-path).
- **AD-2 (Stateless Session):** `StringSession` mã hóa AES-256, 0 SQLite session files trên disk.
- **AD-3 (Redis Mutex Lock):** Khóa `telegram:session:lock:{account_id}` (TTL 120s) chống xung đột đa worker.
- **AD-4 (FloodWait State Machine):** Cooldown `banned_until = now + seconds + jitter`, xoay account ngay lập tức.
- **AD-5 (S3 Media Stream):** Stream 128KB chunks trực tiếp lên S3/MinIO.
- **AD-6 (Idempotent UPSERT):** Composite unique key `(channel_id, message_id)`.
- **AD-7 (Proxy Binding):** SOCKS5 `socks5h://` định tuyến DNS từ xa chống rò rỉ IP.
- **AD-8 (Redis Stream Buffer):** Tách Ingestion Edge khỏi Celery enrichment worker.

---

## 5. Epic Quality & Dependency Review

1. **User-Value Orientation:** Cả 3 stories đều hướng trực tiếp đến giá trị người dùng (User & Admin outcomes), không có technical-only milestone epics.
2. **Story Independence & Flow:**
   * Story 22.1 (Storage Schema & Web Preview Ingestion) chạy độc lập $100\%$.
   * Story 22.2 (MTProto Client & Session Pool) chỉ phụ thuộc vào Schema DB 22.1.
   * Story 22.3 (Enrichment, Realtime Alert & Agent Tools) sử dụng dữ liệu từ 22.1 và 22.2.
   * **Forward Dependencies:** **0% (Không có phụ thuộc ngược).**
3. **Acceptance Criteria Rigor:** Đầy đủ cấu trúc **Given / When / Then**, bao gồm các điều kiện biên:
   * Caption-less media (ảnh không text) fallback `text=""`, `raw_entities=[]`.
   * S3 multipart upload 5MB part buffer threshold.
   * Stateless OTP caching trong Redis (`telegram:auth_flow:{phone}`, TTL 300s).
   * HNSW vector index trên `telegram_messages.embedding`.

---

## 6. Summary and Recommendations

### 🏁 Overall Readiness Status: **`READY FOR IMPLEMENTATION` (🟢 SẴN SÀNG TRIỂN KHAI)**

### 📝 Action Items trước khi bắt đầu Code:
1. Thêm dependencies vào `nowing_backend/pyproject.toml`:
   ```toml
   telethon = "1.36.0"
   selectolax = ">=0.3.21"
   python-socks = { extras = ["asyncio"], version = ">=2.4.0" }
   aiobotocore = ">=2.13.0"
   ```
2. Chạy `uv sync` hoặc `poetry lock` để cài đặt thư viện.
3. Triển khai tuần tự theo 3 Stories:
   - **Step 1:** Story 22.1 (Alembic DDL Migration + `TelegramWebPreviewScraper` + Upsert).
   - **Step 2:** Story 22.2 (`TelethonScraperClient` + Redis Mutex Lock + Account Rotator + Admin OTP Endpoints).
   - **Step 3:** Story 22.3 (`TelegramEntityExtractor` + S3 Media Uploader + Stream Daemon + Agent Tools & Admin UI).
