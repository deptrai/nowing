# Epic 40 Context: Unified Scraper Gateway & Trinity Pipeline Optimization

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Chuyển đổi Nowing thành tầng điều phối và gateway cào dữ liệu duy nhất thông qua XActions (`:3001`), đóng gói các endpoint Scraper Playground thành thin proxy có kiểm soát billing, giải phóng 22 scraper cũ trong Nowing để giảm tải bảo trì và thu gọn Docker image; đồng thời cắm tầng quyết định Jev (Epic 39) vào luồng stream ingest để tự động dedup và lọc PII, và gia cố bảo vệ timeout cho kết nối với ChainLens.

## Stories

- Story 40.1: XActions Gateway Client & Streamable-HTTP Cutover
- Story 40.2: Scraper Playground Thin Proxy & Workspace Billing Gate
- Story 40.3: Decommission 22 Internal Platform Crawlers & Docker Slimming
- Story 40.4: Jev Stream Dedup & PII Guardrail Pipeline
- Story 40.5: ChainLens S2S Circuit Breaker & Timeout Hardening

## Requirements & Constraints

- **XActions Gateway Client (FR-40.1):** `adapter_v2.py` làm client chính thức gọi `x_scrape` qua `XActionsMcpClient` Streamable-HTTP (`:3001/mcp`) với Circuit Breaker 4.0s fail-fast; preview ≤30 records, bulk vào Redis Stream `stream:social:raw_posts`.
- **Playground Thin Proxy (FR-40.2):** Route `/api/v1/scrapers/{platform}/{verb}` check credit, forward sang XActions, trả kết quả chuẩn; UI `nowing_web` 100% không đổi.
- **Decommission Crawlers (FR-40.3):** Xóa code cào/bypass/headless browser trong `app/proprietary/platforms/`; giữ lại `models.py`, `schemas.py`, `parsers.py`; gỡ dependencies nặng (`playwright`, `selenium`) → Docker giảm ≥400MB.
- **Jev Stream Dedup (FR-40.4):** `social_stream_worker.py` gọi `DecisionService.decide(entity_match)` (≥1.5 merge, 0.5–1.5 curate, <0.5 new) và `decide(content_filter)` lọc PII/prompt injection trước khi DB commit.
- **ChainLens Resilience (FR-40.5):** Hard deadline 5.0s cho `POST /v1/private-data/search`; outbound deep research fallback sang local knowledge nếu SSE fail/timeout.

## Technical Decisions

- **Adapter & Contracts:** Nowing dùng `app/proprietary/platforms/xactions/adapter_v2.py` + `mcp_client.py` + `action_matrix.py` (dynamic discovery qua `x_actions_list`). Payload chuẩn: `{platform, action, args, context{targetId, workspaceId}}`.
- **Circuit Breaker:** 3 lỗi liên tiếp hoặc timeout >4.0s mở circuit 60s; trả `PlatformError(XACT_4001, scraper_temporarily_unavailable)`.
- **Billing Gate:** Playground route phải soft-lock credits qua `wallet_credit.check_balance`, forward sang XActions, debit wallet và ghi `BillingEvent` khi thành công; refund nếu XActions trả lỗi anti-bot/session.
- **Decommission:** Giữ nguyên `NormalizedLead`, `SocialPostEvent`, phone extractor và các parser chuẩn hóa dữ liệu; xóa `fetch.py`, `crawler.py`, `client.py` cào thô.
- **Jev Integration:** Worker dùng `DecisionService` (đã implement Epic 39); score ≥1.5 auto-merge, 0.5–1.5 `needs_curation`, <0.5 distinct. Content filter là Noul battery (relevance, injection, PII).
- **ChainLens Boundary:** Nowing cung cấp `POST /v1/private-data/search` với `ChainLensServiceAuth`; Nowing gọi ChainLens `/api/v1/search` với timeout SSE 900s/connection 10s.

## Cross-Story Dependencies

- 40.1 làm nền tảng cho 40.2 (Playground proxy cần gateway client) và 40.3 (xóa crawler sau khi cutover ổn định).
- 40.4 phụ thuộc 40.1 (stream data) và Epic 39 (DecisionService đã sẵn sàng).
- 40.5 độc lập với các story trước nhưng nằm trong cùng phạm vi hardening Trinity ecosystem.
