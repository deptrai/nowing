---
baseline_commit: NO_VCS
---

# Story 21.10: 1-Click Reverse-ICP from Website / Project URL

Status: in-progress

<!-- Note: Governed by FR-80, AD-31, AD-37, AD-8 and Epic 21 Lead Gen Architecture -->

## Story

As a business owner, sales representative, or real estate broker,
I want to paste my company website domain or a real estate project landing page URL and have Nowing automatically extract metadata and generate the Ideal Customer Profile (ICP), search queries, negative keywords, filter presets, and multi-table tabs,
So that I can launch targeted lead discovery in under 10 seconds without manual prompt writing or complex filter configuration.

## Acceptance Criteria

1. **Given** a raw URL input (e.g. `vinhomes.vn`, `https://topcv.vn/?utm_source=ad`, `haravan.com/`), **When** `FastCrawler.fetch_and_parse(url)` is invoked, **Then** it normalizes the URL (auto-prepends `https://` if missing, strips tracking query parameters `utm_*`, `fbclid`, `ref`), resolves DNS asynchronously via `asyncio.get_event_loop().getaddrinfo`, and validates that all resolved IPs do not belong to private/reserved RFC 1918 subnets (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`, `localhost`, `0.0.0.0`).
2. **Given** an HTTP redirect hop (301/302/307), **When** following redirects (max 3 hops), **Then** `FastCrawler` inspects each target `Location` header before dispatching the next request, rejecting any hop that targets internal/private IPs with an immediate `SSRFProtectionError`.
3. **Given** valid fetched HTML content, **When** parsed by `selectolax.parser.HTMLParser`, **Then** the crawler extracts within 1.0 second:
   - OpenGraph tags (`og:title`, `og:description`, `og:image`, `og:site_name`, `og:type`)
   - Schema.org JSON-LD scripts (`<script type="application/ld+json">`) with recursive `@graph` flattening for `RealEstateListing`, `Product`, `Organization`, `LocalBusiness`, `Service`
   - `<title>`, `<meta name="description">`, `<meta name="keywords">`
   - Headings `<h1>`, `<h2>`, `<h3>` (first 5 headings)
   - Clean body text (stripped of `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>`, `<noscript>`, bounded to a maximum token budget of 2,000 characters).
4. **Given** extracted metadata, **When** processed by `ReverseIcpService.analyze_url(url, custom_instructions)` via LiteLLM / auto-model with temperature $0.2$, **Then** it checks Redis cache first (`icp:cache:{url_hash}`, TTL 3600s), and on cache-miss generates a validated `ReverseIcpResponse` containing:
   - `company_name` & `domain`
   - `value_proposition` (concise 1-2 sentence core value)
   - `industry` (primary vertical classification)
   - 3 `target_buyer_personas` (`title`, `industry`, `company_size`, `pain_points: list[str]`, `buying_triggers: list[str]`)
   - 5 `suggested_search_queries` (optimized for Nowing search & multi-platform scrapers)
   - `negative_keywords` (exclusion keywords to filter junk leads)
   - `filter_presets` (`platforms`, `intent` tag `[BÁN]`/`[MUA]`/`[TUYỂN DỤNG]`/`[ĐẤU THẦU]`, `target_industries`, `locations`, `company_size_range`)
   - 3 `chat_starter_prompts` (1-click ready discovery prompts for the chat co-pilot)
   - `raw_metadata` (summary of OG tags, Schema types found, crawl latency ms)
5. **Given** an authenticated workspace request, **When** calling `POST /api/v1/workspaces/{workspace_id}/leads/reverse-icp`, **Then** the endpoint:
   - Verifies RBAC permission `check_permission(auth, Permission.WORKSPACE_READ)`
   - Enforces a rate limit of 10 requests / minute per workspace
   - Records credit deduction and audit logging with `usage_type="reverse_icp"` via `billable_call`
   - Returns `200 OK` with `ReverseIcpResponse` in $\le 2.5$s total end-to-end latency.
6. **Given** an AI Agent session in chat, **When** the user provides a link or says "Phân tích ICP cho website này", **Then** the agent calls tool `leads_reverse_icp(url, custom_instructions)`, formatting the result into structured persona cards with clickable Suggested Action Pills (`[ 🎯 Tìm 50 Leads Persona 1 ]`, `[ 🔍 Quét Nhóm Facebook ]`).
7. **Given** the Lead Intelligence Panel in `nowing_web`, **When** the user clicks "⚡ 1-Click Reverse-ICP", **Then** an interactive `ReverseIcpModal` opens with sample domain chips (`vinhomes.vn`, `topcv.vn`, `haravan.com`), live step animation (<3s), rendered Persona cards, and action buttons:
   - **"Áp dụng vào Bộ lọc (Apply Filters)"**: Dispatches `filter_presets` into active table filters without page reload.
   - **"Tạo Tab Bảng Mới (Create Tab from ICP)"**: Creates a new tab in `MultiTableTabs` with name and pre-configured queries.
   - **"Mở Chat Săn Lead (Start Discovery)"**: Navigates to `/new-chat` with pre-filled prompt.

## Tasks / Subtasks

- [ ] Task 1: URL Normalization & Multi-Layer Anti-SSRF Crawler (AC: 1, 2)
  - [ ] 1.1 Tạo module `nowing_backend/app/proprietary/platforms/crawler/fast_crawler.py`.
  - [ ] 1.2 Triển khai hàm `normalize_target_url(raw_url: str) -> str` (bù `https://`, gỡ `utm_*`, `fbclid`, `ref`, trailing slashes).
  - [ ] 1.3 Triển khai hàm `async def validate_safe_ip(hostname: str) -> bool` sử dụng `asyncio.get_event_loop().getaddrinfo` và kiểm tra tất cả các IP trả về với `ipaddress.ip_network` (chặn `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`, `localhost`, `0.0.0.0`).
  - [ ] 1.4 Sử dụng `httpx.AsyncClient(follow_redirects=False)` và viết loop duyệt redirect thủ công (tối đa 3 hops) để kiểm tra SSRF trên từng URL chuyển hướng.
  - [ ] 1.5 Thiết lập browser spoofing User-Agent và timeout kết nối: `connect=1.5s`, `read=2.0s`.
- [ ] Task 2: Schema.org `@graph` Parser & HTML Content Extractor (AC: 3)
  - [ ] 2.1 Sử dụng `selectolax.parser.HTMLParser` bóc tách nhanh OpenGraph tags, `<title>`, meta description, meta keywords.
  - [ ] 2.2 Viết helper `extract_json_ld_metadata(tree: HTMLParser) -> list[dict]` xử lý cả dạng đơn lẻ lẫn lồng trong `@graph` cho các schema: `RealEstateListing`, `Product`, `Organization`, `LocalBusiness`, `Service`.
  - [ ] 2.3 Bóc tách thẻ tiêu đề `<h1>`, `<h2>`, `<h3>` (lấy tối đa 5 thẻ đầu).
  - [ ] 2.4 Lọc bỏ các thẻ rác (`<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>`, `<noscript>`) và cắt lấy tối đa 2,000 ký tự văn bản sạch trong `<main>` hoặc `<body>`.
- [ ] Task 3: Pydantic Schemas for Reverse-ICP (AC: 4)
  - [ ] 3.1 Cập nhật `nowing_backend/app/lead_intelligence/schemas.py` với các schema:
    - `BuyerPersona` (`title: str`, `industry: str`, `company_size: str`, `pain_points: list[str]`, `buying_triggers: list[str]`)
    - `FilterPresets` (`platforms: list[str]`, `intent: str`, `target_industries: list[str]`, `locations: list[str]`, `company_size_range: str | None = None`)
    - `ReverseIcpRequest` (`url: str`, `custom_instructions: str | None = None`)
    - `ReverseIcpResponse` (`company_name: str`, `domain: str`, `value_proposition: str`, `industry: str`, `target_buyer_personas: list[BuyerPersona]`, `suggested_search_queries: list[str]`, `negative_keywords: list[str]`, `filter_presets: FilterPresets`, `chat_starter_prompts: list[str]`, `raw_metadata: dict[str, Any] = Field(default_factory=dict)`)
- [ ] Task 4: Reverse-ICP AI Service with Caching & Fallback JSON Parser (AC: 4)
  - [ ] 4.1 Tạo service `nowing_backend/app/lead_intelligence/reverse_icp.py` chứa class `ReverseIcpService`.
  - [ ] 4.2 Tích hợp Redis cache: Tra cứu `icp:cache:{url_sha256}` (TTL 1 giờ) trước khi cào lại hoặc gọi LLM.
  - [ ] 4.3 Xây dựng prompt system và prompt template đưa dữ liệu đã trích xuất (OG, JSON-LD, Headings, Text) yêu cầu output JSON nghiêm ngặt.
  - [ ] 4.4 Gọi LLM qua `litellm.acompletion` (hoặc `LLMRouterService` model `auto`) với `temperature=0.2`, `max_tokens=1500`.
  - [ ] 4.5 Bổ sung parser bảo vệ lỗi JSON (lọc markdown block ```json ... ```, `re.search(r'\{.*\}', text, re.DOTALL)` và sanitize chuỗi dở dang).
- [ ] Task 5: REST API Route, RBAC, Rate Limiting & Billing Audit (AC: 5)
  - [ ] 5.1 Thêm endpoint `POST /api/v1/workspaces/{workspace_id}/leads/reverse-icp` vào `nowing_backend/app/routes/leads_routes.py`.
  - [ ] 5.2 Xác thực RBAC: `check_permission(auth, Permission.WORKSPACE_READ)`.
  - [ ] 5.3 Bổ sung Rate Limiting: Tối đa 10 requests / phút trên mỗi workspace (trả về 429 nếu vượt quá).
  - [ ] 5.4 Tích hợp `billable_call(..., usage_type="reverse_icp")` để ghi nhận token consumption vào bảng `TokenUsage` và trừ credit tương ứng.
  - [ ] 5.5 Xử lý HTTP status codes: `400` cho URL không hợp lệ / dính SSRF, `504` cho kết nối crawl timeout.
- [ ] Task 6: AI Agent Capability & Chat Tool (AC: 6)
  - [ ] 6.1 Tạo `nowing_backend/app/capabilities/leads/reverse_icp_tool.py` đăng ký capability và tool `leads_reverse_icp`.
  - [ ] 6.2 Khai báo tool vào danh mục chat agent tools trong `app/capabilities/core/access/agent.py`.
  - [ ] 6.3 Tích hợp Suggested Action Pills vào phản hồi chat turn (Story 21.11).
- [ ] Task 7: Frontend Reverse-ICP Modal & Multi-Table Integration (AC: 7)
  - [ ] 7.1 Tạo TypeScript contracts trong `nowing_web/contracts/types/leads.types.ts` (`ReverseIcpRequest`, `ReverseIcpResponse`, `BuyerPersona`, `FilterPresets`).
  - [ ] 7.2 Thêm hàm gọi API `analyzeReverseIcp` vào `nowing_web/lib/apis/leads-api.service.ts`.
  - [ ] 7.3 Xây dựng component `nowing_web/components/leads/ReverseIcpModal.tsx` gồm URL input, domain chips, loading progress animation 3 bước, 3 Persona cards, và Negative Keywords pills.
  - [ ] 7.4 Tích hợp nút "⚡ 1-Click Reverse-ICP" vào header của `nowing_web/components/leads/LeadsContent.tsx`.
  - [ ] 7.5 Kết nối nút "Áp dụng vào Bộ lọc (Apply Filters)" để cập nhật bộ lọc Multi-Table mà không reload trang.
  - [ ] 7.6 Bổ sung nút "Tạo Tab Bảng Mới (Create Tab from ICP)" tạo mới `WorkspaceTable` tab trực tiếp từ kết quả ICP.
- [ ] Task 8: Unit & Integration Tests (AC: 1-7)
  - [ ] 8.1 `tests/unit/lead_intelligence/test_fast_crawler.py` (Test URL normalizer, DNS SSRF blocker, redirect SSRF blocker, OpenGraph parser, Schema JSON-LD `@graph` flattening, clean text truncation).
  - [ ] 8.2 `tests/unit/lead_intelligence/test_reverse_icp_service.py` (Test Redis cache hit/miss, prompt formatting, LLM response JSON repair, schema validation).
  - [ ] 8.3 `tests/integration/routes/test_reverse_icp_route.py` (Test endpoint RBAC auth, rate limiting 429, billing audit record creation, mock end-to-end).
  - [ ] 8.4 `nowing_web/components/leads/__tests__/ReverseIcpModal.test.tsx` (Test modal open/close, sample domain chip click, form submit, loading state, persona tab switching, apply filters callback).

## Dev Notes

- **Architecture Invariants:** Tuân thủ triệt để FR-80, AD-31 (Multi-source Lead Discovery), AD-37 (Signal & Search Integration), AD-8 (Billing & Token Tracking).
- **SSRF & DNS Rebinding Security Invariant:**
  - Tuyệt đối không cho phép cào các IP nội bộ, loopback hoặc subnet đám mây (`169.254.169.254`).
  - Phân giải DNS và kiểm tra từng IP trước khi kết nối.
  - Bắt buộc kiểm tra lại IP của từng hop khi gặp mã 301/302 Redirect.
- **Latency & Token Budget:**
  - Fast crawl: $<1.0$s
  - selectolax HTML parse: $<100$ms
  - LiteLLM completion: $<1.5$s
  - Tổng độ trễ toàn trình $\le 2.5$s.
  - Dung lượng text gửi tới LLM tối đa 2,000 ký tự (~500 tokens).
- **Billing & Token Usage Audit:** Khai báo `usage_type="reverse_icp"` để hạch toán minh bạch vào `TokenUsage` qua `billable_call`.
- **Dependencies:** `selectolax>=0.3.21`, `httpx>=0.28.1`, `dnspython>=2.6.1`, `litellm>=1.40.0`, `pydantic>=2.0`.

### Read Files Being Modified

1. **`nowing_backend/app/routes/leads_routes.py`**
   - *Current state:* Cung cấp các endpoint `GET /api/v1/workspaces/{workspace_id}/leads`, `PATCH /leads/{lead_id}/status`, `GET /leads/{lead_id}/company-graph`.
   - *What this story changes:* Thêm endpoint `POST /api/v1/workspaces/{workspace_id}/leads/reverse-icp` có xác thực quyền, rate limiting và `billable_call`.
   - *What must be preserved:* Toàn bộ RBAC auth, permission checks, rate limits, và logic truy vấn Leads hiện tại.

2. **`nowing_backend/app/lead_intelligence/schemas.py`**
   - *Current state:* Khai báo schemas `LeadRead`, `LeadStatusUpdate`, `CompanyGraphRead`, `DecisionMakerRead`.
   - *What this story changes:* Thêm schemas `BuyerPersona`, `FilterPresets`, `ReverseIcpRequest`, `ReverseIcpResponse`.
   - *What must be preserved:* Các schema hiện có và validator finite number trên scores.

3. **`nowing_web/components/leads/LeadsContent.tsx` & `multi-table-tabs.tsx`**
   - *Current state:* Hiển thị header, bộ lọc đa nguồn, bảng Lead, và Company Graph Drawer.
   - *What this story changes:* Thêm nút "⚡ 1-Click Reverse-ICP", state điều khiển `ReverseIcpModal`, và callback áp dụng `filter_presets` / tạo Tab bảng mới.
   - *What must be preserved:* Toàn bộ filter hiện có (`sourceFilter`, `statusFilter`, `searchQuery`), Zero-cache bindings, và clipboard copy.

### Project Structure Notes

- New backend service: `nowing_backend/app/lead_intelligence/reverse_icp.py`
- New crawler utility: `nowing_backend/app/proprietary/platforms/crawler/fast_crawler.py`
- New agent tool: `nowing_backend/app/capabilities/leads/reverse_icp_tool.py`
- New frontend component: `nowing_web/components/leads/ReverseIcpModal.tsx`
- Modified backend files: `nowing_backend/app/lead_intelligence/schemas.py`, `nowing_backend/app/routes/leads_routes.py`, `nowing_backend/app/capabilities/core/access/agent.py`
- Modified frontend files: `nowing_web/components/leads/LeadsContent.tsx`, `nowing_web/contracts/types/leads.types.ts`, `nowing_web/lib/apis/leads-api.service.ts`

### References

- [Epics: _bmad-output/planning-artifacts/epics.md#Story-21.10]
- [Architecture Spine: _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md#AD-31]
- [Lead Intelligence Architecture: _bmad-output/planning-artifacts/architecture/epic21-architecture-update.md]
- [UX Contract: _bmad-output/planning-artifacts/ux-designs/ux-contract-scrapers-expansion-and-lead-intelligence.md]

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash

### Debug Log References

None (Story context created directly from specifications).

### Completion Notes List

- Created comprehensive story specification for Story 21.10 (1-Click Reverse-ICP).
- Defined FastCrawler with selectolax, URL normalizer, and strict multi-layer SSRF + redirect protection.
- Defined Schema.org JSON-LD @graph flattener and hero text token budgeting.
- Defined ReverseIcpService with Redis caching, LiteLLM auto-model resolution, and robust JSON fallback parsing.
- Outlined REST API endpoint with RBAC, rate limiting, and billable_call credit audit.
- Defined frontend ReverseIcpModal with live loading animation, persona cards, filter auto-population, and New Table Tab creation.
- Defined unit, integration, and UI test scaffolding.

### File List

- `nowing_backend/app/proprietary/platforms/crawler/fast_crawler.py` [NEW]
- `nowing_backend/app/lead_intelligence/reverse_icp.py` [NEW]
- `nowing_backend/app/capabilities/leads/reverse_icp_tool.py` [NEW]
- `nowing_backend/app/lead_intelligence/schemas.py` [UPDATE]
- `nowing_backend/app/routes/leads_routes.py` [UPDATE]
- `nowing_backend/app/capabilities/core/access/agent.py` [UPDATE]
- `nowing_web/components/leads/ReverseIcpModal.tsx` [NEW]
- `nowing_web/contracts/types/leads.types.ts` [UPDATE]
- `nowing_web/lib/apis/leads-api.service.ts` [UPDATE]
- `nowing_web/components/leads/LeadsContent.tsx` [UPDATE]
- `nowing_backend/tests/unit/lead_intelligence/test_fast_crawler.py` [NEW]
- `nowing_backend/tests/unit/lead_intelligence/test_reverse_icp_service.py` [NEW]
- `nowing_backend/tests/integration/routes/test_reverse_icp_route.py` [NEW]
- `nowing_web/components/leads/__tests__/ReverseIcpModal.test.tsx` [NEW]
