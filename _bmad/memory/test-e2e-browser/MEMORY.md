# Memory

_Curated long-term knowledge for Nowing E2E Browser Testing._

## Known Environment Quirks & Fixes
- **Zero Cache 401:** If Zero query fails with `401 TransformFailed`, ensure `NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848` and `POSTGRES_PORT=5434` are properly aligned.
- **Local Ports:** Postgres runs on `5434` and Redis on `6380` to avoid conflicts with host instances.

## Flaky Selectors & DOM Patterns
- **Header Auth Controls:** The `Sign In` link in the main navigation uses `hidden md:block`. When testing with browser MCP tools, always ensure viewport is set to desktop size (e.g. 1440x900 via `browser_resize`) or click the `Get Started` hero link if testing on small viewports.
- **Chat Prompt & Turn Trace:** Chat prompt input is accessible via `getByRole('textbox')`. Tool trace details and execution steps expand via `getByRole('button', { name: 'Reviewed' })` or `getByRole('button', { name: 'Open agent action log' })`. Modals can be safely dismissed with `keyboard.press('Escape')`.
- **1-Click Reverse-ICP (Story 21.10):**
  - Trigger button on `/dashboard/{workspace_id}/leads`: `button:has-text('1-Click Reverse-ICP')`.
  - Modal: `div.fixed.inset-0.z-50`, URL input `#target-url-input`, sample chips inside the modal, analyze button `button:has-text('Phân tích ICP')`.
  - Result view shows buyer personas, suggested queries, negative keywords, and chat starter prompts.
  - Action buttons: `button:has-text('Áp dụng vào Bộ lọc')`, `button:has-text('Tạo Tab Bảng Mới')`, and per-prompt `button:has-text('Mở Chat')`.
  - Filter apply maps LLM platform names (`batdongsan.com.vn`, `topcv.vn`, etc.) to canonical `<select>` values; other platforms fall back to `all`.
  - Chat starter navigates to `/dashboard/{workspace_id}/new-chat?q=<encoded prompt>`; the new-chat page currently ignores the `q` param (placeholder integration).
- **Smart Whitelist & DNC Compliance Engine (Story 21.14):**
  - Trigger button on `/dashboard/{workspace_id}/leads`: `button:has-text('Do-Not-Call (DNC)')`.
  - Modal: `h2:has-text('Do-Not-Call (DNC) & Compliance Registry')`.
  - 3 Tabs: `button:has-text('Blacklist Registry')`, `button:has-text('Add Single Record')`, `button:has-text('Bulk CSV Import')`.
  - Add Single: Select type (`phone`, `domain`, `email`, `tax_id`), input `input[placeholder='0908123456']`, submit `button:has-text('Add to DNC Blacklist')`.
  - Bulk CSV: drag-drop input `.csv`, `button:has-text('Upload & Process DNC CSV')`.
  - In-stream Lead Suppression: Lead cards with blocked contacts render badge `🚫 DNC Blocked` and disable/suppress `ZaloOutreachButton`.
  - PII Hard Purge (Decree 13 PDPD / GDPR): `DELETE /api/v1/leads/{id}/pii` hard purges phone/email/contacts and appends Keyed HMAC to DNC set with `value: null`.
- **Suggested Action Pills (Story 21.11):** Suggested execution pills mount directly below assistant messages via container `[data-testid='suggested-action-pills']` and buttons `button[data-action-type]`. Supports 1-click prompt dispatch and keyboard shortcuts `Alt+Digit1`, `Alt+Digit2`, `Alt+Digit3` when composer input is unfocused. Emits window custom event `nowing:action-dispatched` triggering `.cell-pulse` highlight.
- **Phone Copy Pills & PII Masking (Story 21.3):** Lead phone numbers render inside `button[aria-label^='Copy phone number']`. Non-privileged views strictly display masked format (`0908***456`). Clicking copies normalized digits and temporarily updates state to `(Đã copy)` with a 1500ms reset timer.
- **Nowing Split-View Canvas & Dynamic Multi-Mode Hub (Story 21.16):**
  - Main container: `main[data-testid='nowing-split-canvas']` with Sọc Caro grid texture headers (`.soc-caro-grid`) and Emerald Green brand tokens.
  - Left Panel: `section[data-testid='nowing-chat-copilot']`, width 340px, full Assistant-UI runtime. Dynamic `💡 SUGGESTED NEXT ACTIONS` renders 1-click prompt action buttons above the composer. Table outputs render as `TableArtifactCard` `[ ▦ ] Bảng dữ liệu Khách hàng & Leads (● Đang xem >)`, which pings and highlights matching matrix rows. Query parameter `?q=...` automatically fills and executes initial prompts.
  - Collapse / Expand: Collapse trigger `button[title='Thu gọn Co-pilot']`, Expand trigger `button[title='Mở rộng AI Co-pilot']` (renders vertical rail `[writing-mode:vertical-rl]`).
  - Resizer Divider: `div[role='slider'][data-testid='split-canvas-resizer']` supporting drag, keyboard arrow keys `ArrowLeft`/`ArrowRight`, and double-click reset to 340px.
  - Right Panel Hub: 4 contextual modes:
    - `Leads Matrix`: `div[data-testid='nowing-lead-matrix']` with fluid auto-fit columns, fit score badges, phone copy pills, and 1-click Zalo outreach. Fullscreen toggle `button:has-text('Toàn màn hình')`.
    - `Research Studio`: Executive summary, RAG citations, real `.md` blob export (`button:has-text('Xuất .MD')`), and print PDF (`button:has-text('Tải PDF')`).
    - `Automation Flow`: Connected to `automationsApiService.createAutomation()` to save cron triggers.
    - `Scraper Health`: Connected to `scraperPlatformAccountsApiService.list()` and `capture()`.
  - Floating Bulk Action Bar: `aside[data-testid='floating-bulk-action-bar']` slides in from bottom at `z-[60]` when $\ge 2$ checkboxes selected.
  - Flyout Detail Drawer: `aside[data-testid='lead-detail-flyout-drawer']` (480px) opens on row click with Fit Score bars, 1-click Zalo outreach, Click-to-call link (`tel:`), and invalid phone report trigger.
- **Telegram MTProto Userbot Client & Monitored Channels (Epic 22):**
  - Page: `/admin/scraper-accounts` (requires `User.is_superuser=True`).
  - Tabs: `All Accounts`, `Telegram`, `Channels`.
  - Telegram Tab: `Telegram MTProto Accounts` table displays accounts with live `Token Quota` (`rpm`), `Proxy` (`socks5h://`), status badges (`Active`, `Rate-Limited`, `Cooldown` with countdown timer).
  - Add Account Modal: `button:has-text('Add Telegram Account')` or `button:has-text('Connect Telegram')` opens multi-step modal with `Phone Number`, `Telegram API ID`, `API Hash`, `Proxy (Optional)`. Sends auth code via Redis `telegram:auth_flow:{phone}` and validates 2FA cloud passwords into encrypted `StringSession` records.
  - Channels Tab: `Monitored Telegram Channels` table displays channels (`@bds_hanoi_chinhchu`, etc.), message counts, and realtime ingestion stream toggles (`button[data-testid='channel-stream-toggle']`) that immediately switch state between `OFF` (Idle) and `ON` (⚡ Live).

  - Credits Badge: Top-right header dynamically tracks real user credits (`🌸 500 Credits` for `$5.00` balance).
- **Enterprise Company Graph Drawer (Story 21.3 / 21.4):** Triggered by `button[name='Xem Company Graph']`. Displays company registration data (MST, representative, capital), decision-makers list with masked contacts, and recruitment signals.

- **CRM Integration & Write-Back (Story 21.5):**
  - REST Endpoints: `POST /api/v1/workspaces/{id}/crm/{provider}/connect` generates PKCE `auth_url`. Callback `/api/v1/auth/crm/{provider}/callback` verifies `state`, exchanges token, encrypts credentials into `CrmConnection`.
  - Phase 1 Dedup: `POST /api/v1/workspaces/{id}/crm/connections/{connection_id}/dedup` matches domain & contact email without false positives.
  - Phase 2 Write-back: `POST /api/v1/workspaces/{id}/crm/connections/{connection_id}/sync` maps fields, writes `CrmSyncLog`, and appends redacted `Memory` context.
  - Pagination: `GET /api/v1/workspaces/{id}/crm/connections/{connection_id}/sync-logs?limit=N&offset=N`.

- **Unified Multi-Source Lead Generation Orchestrator (Story 21.15):**
  - Natural language lead search triggers `multi_source_lead_gen` tool dispatch with parallel scraping across 5 adapters (Batdongsan, Chotot, JobMarket, Enterprise, Social).
  - SSE streaming turn renders interactive tool call accordion (`Plan tasks`, `Google Maps`, `BATDONGSAN`, `CHOTOT`) with live step status.
  - Markdown output displays sanitized tabular columns (`Tên / Tiêu đề`, `Doanh nghiệp / Người liên hệ`, `Số điện thoại`, `Độ tin cậy`, `Nguồn`).
  - Zero-cache automatically synchronizes new leads to the Live Lead Matrix (`/dashboard/{workspace_id}/leads`).

## High-Risk User Journeys
- Unified Multi-Source Lead Generation Orchestrator (Story 21.15): Query decomposition across 5 sources, HMAC PII deduplication, anti-loop retry, fail-soft fallback, and live table streaming.
- Vietnam Phone & Contact Waterfall Engine (Story 21.3): 3-tier waterfall phone extraction, PII AES-256 encryption at rest, 1.5 credit billing event, and 24h SLA auto-refund reporting.
- CRM Integration, OAuth & Write-Back (Story 21.5): Multi-tenant PKCE state matching, RLS client isolation with `NULLIF`, timezone-aware UTC conflict resolution, and FastMCP tool rendering.
- Compliance & DNC Blacklist Engine (Story 21.14): In-stream contact suppression, Zero credit billing invariant, Right-to-be-Forgotten hard purge with zero-knowledge HMAC hashing.
- Chat turns with SSE streaming, tool invocation widgets, and contextual suggested action pills (`data-suggested-actions`).
- Connector authentication and indexing pipelines.
- Workspace creation and Zero-cache state synchronization.
- **Lead Clipper Extension & Multi-Tab Isolation (Story 24.4):**
  - Content scripts communicate strictly via `chrome.runtime.sendMessage` to background service worker (`INV-24.5`).
  - Backend deduplication route: `POST /api/v1/workspaces/{id}/leads/clip` returns `is_duplicate: true` on collision.
  - Multi-tab Playwright test: `tests/leads/lead-clipper-multitab.spec.ts` verifies token isolation in `chrome.storage`, DOM extractors, offline queue resilience, and Zero-sync ingestion.


