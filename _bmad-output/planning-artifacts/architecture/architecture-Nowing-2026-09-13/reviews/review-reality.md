# Reality-Check Review: Architecture Spine Nowing ↔ XActions Connection

**Target File:** `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md`  
**Reviewer:** Reality-Check Architecture Reviewer  
**Date:** 2026-09-13  

---

## Verdict

**CONDITIONAL PASS** — 7/7 tuyên bố về hiện trạng codebase và 4/4 công nghệ được xác minh chính xác 100% trên mã nguồn thực tế; tuy nhiên phát hiện 3 xung đột thực thi nghiêm trọng cần được hiệu chỉnh trước khi triển khai (schema mismatch giữa thin event và consumer, fallback_crawl_post thiếu tham số platform, và tên action sai lệch trong PLATFORM_TOOL_MAP).

---

## 1. Kiểm chứng các tuyên bố về Code (Code Claims)

| # | Claim | Trạng thái | Minh chứng Code thực tế |
|---|---|---|---|
| 1.1 | `PLATFORM_TOOL_MAP` gọi `x_scrape` cho target VN nhưng XActions không có tool `x_scrape` | **VERIFIED** | - `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py`: dòng 44–106 định nghĩa 9 target (`tiktok_hashtag`, `chotot_category`, `shopee_keyword`, `topcv_search`, `vietnamworks_search`, `linkedin_company`, `batdongsan_category`, `masothue_lookup`, `b2b_registry_search`) gọi tool `x_scrape`.<br>- `/Users/luisphan/Documents/GitHub/XActions/src/mcp/server.js`: mảng `TOOLS` không có tool nào tên `x_scrape` (chỉ có `x_scrape_space` tại dòng 712; `x_scrape` chỉ xuất hiện trong docstring dòng 1721). Khi gọi sẽ văng `tool_not_found`. |
| 1.2 | `fallback_crawl_post` được định nghĩa nhưng không bao giờ gọi | **VERIFIED** | - `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py`: dòng 126 định nghĩa `fallback_crawl_post`.<br>- Toàn bộ codebase `nowing_backend`: chỉ xuất hiện duy nhất trong file test unit `tests/unit/platforms/test_xactions_adapter_v2.py:44,48`. Hàm `fetch_posts_for_target` (dòng 162) chỉ gọi `UniversalScrapeTargetMapper.map(target)` và re-raise `XActionsMcpError` khi lỗi chứ không gọi fallback.<br>- **Phát hiện thêm:** `fallback_crawl_post` trả về `("x_crawl_post", {"url": target_url})` thiếu tham số bắt buộc `platform`. Nếu gọi vào XActions `server.js:3465`, sẽ lập tức văng `XACT_4001: x_crawl_post requires a platform argument`. |
| 1.3 | `adapter_v2.ingest_raw_post_to_stream` ghi vào `stream:social:raw_posts` (nguồn ghi thứ 2) | **VERIFIED** | - `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py`: dòng 229–243 gọi `redis_client.xadd("stream:social:raw_posts", payload, maxlen=20000)`.<br>- `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py`: dòng 201 lặp các post trả về từ MCP và đẩy vào stream.<br>- Phía XActions: `/Users/luisphan/Documents/GitHub/XActions/src/scrapers/social/facebook/crawler.js:2774` và `/Users/luisphan/Documents/GitHub/XActions/src/utils/redis-stream-publisher.js:85` cũng ghi trực tiếp vào `stream:social:raw_posts`. Hai bên ghi đè/nhân đôi dữ liệu với 2 định dạng schema khác nhau. |
| 1.4 | `x_actions_list` chỉ enumerate 5 social crawler, không có VN | **VERIFIED** | - `/Users/luisphan/Documents/GitHub/XActions/src/scrapers/social/actions-list.js`: dòng 23–29 chỉ import và khởi tạo đúng 5 crawler: `FacebookCrawler`, `ThreadsCrawler`, `RedditCrawler`, `MediumCrawler`, `InstagramCrawler`. Hoàn toàn không có bất kỳ crawler VN hay non-social nào (thậm chí thiếu cả Twitter, Bluesky, Mastodon dù docstring `server.js:2701` có đề cập). |
| 1.5 | 15 crawler VN/non-social không gọi `xAdd` (chỉ social crawler có) | **VERIFIED** | - Trong toàn bộ `/Users/luisphan/Documents/GitHub/XActions/src/scrapers/`, chỉ có `src/scrapers/social/facebook/crawler.js` gọi trực tiếp `xAdd`/`xadd` (dòng 2774, 2787), và các crawler social (`twitter`, `reddit`, `tiktok`, `bluesky`, `medium`, `threads`, `instagram`) import `redis-stream-publisher.js`.<br>- 15 crawler thuộc `realestate/` (`batdongsan`, `chotot`), `recruitment/` (`topcv`, `vietnamworks`, `linkedin`), `ecom/` (`shopee`, `tiktok-shop`), `procurement/` (`masothue`, `b2b-registry-extended`), `vehicles/` (`automotive`), `fnb/` (`merchant`), `healthcare/`, `legal/` (`ip-trademark`), `social/zalo`, `social/youtube` hoàn toàn không import redis publisher và không gọi `xAdd`. |
| 1.6 | Crawler VN extends `AbstractCrawler`; `base-crawler.js` không có stream hook | **VERIFIED** | - `/Users/luisphan/Documents/GitHub/XActions/src/core/base-crawler.js`: lớp `AbstractCrawler` quản lý governor, accountPool, cdpUrl, telemetry, checkpoint, nhưng hoàn toàn không có bất kỳ logic nào về Redis hay stream publish hook.<br>- Các crawler VN (`BatdongsanCrawler`, `TopCvCrawler`, `ShopeeCrawler`, `ChototCrawler`, v.v.) đều `extends AbstractCrawler`. |
| 1.7 | `XActionsMcpClient` dùng `streamablehttp_client` + `X-Consumer-Id`; governor nowing=60 RPM/burst 15 | **VERIFIED** | - `/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/proprietary/platforms/xactions/mcp_client.py`: dòng 23 import `streamablehttp_client`; dòng 65–68 cấu hình header `X-Consumer-Id: nowing` (hoặc cấu hình tương đương).<br>- `/Users/luisphan/Documents/GitHub/XActions/src/core/adaptive-governor.js`: dòng 98–105 khởi tạo quota cứng cho `nowing`: `rpmLimit: 60`, `burstLimit: 15`, `priority: 2`. |

---

## 2. Kiểm chứng Công nghệ (Technology Stack Reality)

| Công nghệ / Symbol | Tình trạng | Kết quả thẩm tra |
|---|---|---|
| **MCP `streamable-http` transport** | **TỒN TẠI & CHÍNH THỨC** | Là transport HTTP streaming chuẩn theo đặc tả mới nhất của MCP. Có sẵn trong thư viện Python `mcp>=1.25.0` tại `mcp.client.streamable_http.streamablehttp_client`. Phía XActions Node.js triển khai qua `startHttpTransport()` tại `server.js:5303`. |
| **`ClientSession.initialize`** | **TỒN TẠI & CHÍNH THỨC** | Xác thực trực tiếp qua runtime Python: `hasattr(ClientSession, 'initialize') == True`. Được gọi trong `XActionsMcpClient.__aenter__`. |
| **Redis Stream `XADD`, `XREADGROUP`, `MAXLEN ~ N`** | **TỒN TẠI & CHÍNH THỨC** | Lệnh Redis Stream tiêu chuẩn từ Redis 5.0+. Đã được hỗ trợ đầy đủ bởi `redis.asyncio` (Python) và `node-redis`/`ioredis` (Node.js). |
| **Celery Beat** | **TỒN TẠI & HOẠT ĐỘNG** | Đã được cấu hình thực tế trong `nowing_backend/app/celery_app.py:348-363` với các task định kỳ `check-social-monitored-targets` (mỗi 1 phút) và `process-social-stream` (mỗi 30 giây). |

---

## 3. Các AD và Rủi ro Cần Hiệu Chỉnh (Gaps & Mismatches)

### 3.1. RỦI RO NGHIÊM TRỌNG: Mâu thuẫn Schema giữa Thin Event và Consumer (AD-3, AD-4)
- **Vấn đề:** AD-4 quy định XActions là SOLE WRITER phát thin event `{id, platform, externalId, category, authorId, crawledAt, storageRef, scraperId}` và Nowing loại bỏ `ingest_raw_post_to_stream`.
- **Thực tế Code:**
  - Consumer hiện tại của Nowing (`app/tasks/social_stream_worker.py`) xác thực qua Pydantic model `SocialPostEvent`:
    - Bắt buộc trường `external_post_id` (`externalId` từ XActions sẽ gây `ValidationError`).
    - Đòi hỏi `content` để trích xuất intent/fit_score (`SocialEntityExtractor.extract_all(event.content)`). Thin event không có `content`.
    - Bắt buộc trường `workspace_id` để tạo bản ghi `Lead` (`leads.workspace_id NOT NULL`) và kích hoạt `AlertRule`. XActions là service crawl độc lập, không hề biết `workspace_id` hay `target_id` của Nowing nếu không được truyền vào và phát ngược lại trong event.
- **Khuyến nghị:**
  - Cần quy định rõ trong AD-3: XActions thin event phải giữ lại trường ngữ cảnh nếu caller truyền vào (`customContext` / `metadata: {workspaceId, targetId}`), hoặc base hook phát event kèm `workspaceId`.
  - Đồng thời, trước khi tắt `ingest_raw_post_to_stream`, `social_stream_worker.py` của Nowing phải được refactor để: chấp nhận alias `externalId` -> `external_post_id`, và cơ chế hydrate `content` từ `storageRef`/artifact store.

### 3.2. LỖI THỰC THI: `fallback_crawl_post` thiếu tham số bắt buộc (AD-6)
- **Vấn đề:** AD-6 dự định kích hoạt `fallback_crawl_post` khi gặp lỗi `tool_not_found`.
- **Thực tế Code:**
  - `UniversalScrapeTargetMapper.fallback_crawl_post(target)` tại `adapter_v2.py:133` chỉ trả về:
    `"x_crawl_post", {"url": target_url}`
  - Trong khi đó, `executeCrawlPostTool` tại `XActions/src/mcp/server.js:3465` kiểm tra nghiêm ngặt:
    `if (!platform || typeof platform !== 'string') throw new PlatformError({ code: 'XACT_4001', message: 'x_crawl_post requires a platform argument' })`
  - Nếu fallback này được kích hoạt, hệ thống sẽ sập ngay lập tức với lỗi `XACT_4001`.
- **Khuyến nghị:** Sửa ngay `fallback_crawl_post` trong `adapter_v2.py` để truyền thêm `platform: target.platform`.

### 3.3. BẤT TƯƠNG THÍCH: Tên Action giữa `PLATFORM_TOOL_MAP` và XActions Descriptors (AD-2, AD-6)
- **Vấn đề:** AD-2 giả định chỉ cần expose `x_scrape` là các target VN sẽ chạy thông suốt.
- **Thực tế Code:**
  - Trong `adapter_v2.py`, Nowing hardcode gọi:
    - `batdongsan_category` -> `action: "posts"`
    - `chotot_category` -> `action: "posts"`
    - `masothue_lookup` -> `action: "lookup"`
  - Nhưng trong XActions descriptors (`src/scrapers/*/descriptor.js`):
    - `batdongsan`: chỉ hỗ trợ `search_listings`, `listing_detail` (không có `posts`).
    - `chotot`: chỉ hỗ trợ `search_listings`, `listing_detail`, `get_phone` (không có `posts`).
    - `masothue`: chỉ hỗ trợ `search`, `search_by_province`, `detail` (không có `lookup`).
- **Hệ quả:** Dù XActions có mở `x_scrape`, cả 3 target trên vẫn sẽ văng lỗi `actionNotAvailable` (`XACT_4001`). Điều này khẳng định AD-6/AD-7 (discovery qua `x_actions_list` thay vì hardcode) là bắt buộc, đồng thời Nowing Phase 0 phải map đúng tên action tương ứng của từng domain.

### 3.4. CHÍNH XÁC HÓA: Scoped Idempotency Constraint (AD-SOC-6)
- **Vấn đề:** Spine ghi `UNIQUE(platform, external_post_id)` ở nowing DB.
- **Thực tế Code:** Trong `nowing_backend/app/models/leads/social.py:89`, ràng buộc là:
  `UniqueConstraint("workspace_id", "platform", "external_post_id", name="uq_social_post")`
  Ràng buộc thực tế được cô lập theo từng `workspace_id`, không phải bảng toàn cục. Điều này củng cố thêm lý do tại sao `workspace_id` là trường bắt buộc phải có trong data pipeline.

---

## 4. Tổng kết

Spine phản ánh rất sâu và chính xác cấu trúc thực tế của 2 repo (đặc biệt là các điểm nghẽn ngầm như 15 crawler thiếu stream, MCP tool bị thiếu, governor quota). Ba điểm mấu chốt cần bổ sung vào tài liệu kiến trúc trước khi code:
1. Xác định rõ cơ chế gắn `workspaceId` / `targetId` vào thin event stream của XActions (hoặc qua `args` -> event context).
2. Quy định lộ trình refactor consumer `social_stream_worker` của Nowing để hydrate data từ thin event trước khi bỏ `ingest_raw_post_to_stream`.
3. Chuẩn hóa mapping action tên miền thực tế (`search_listings`, `search_jobs`, `search`) thay vì gán nhầm `posts`/`lookup`.
