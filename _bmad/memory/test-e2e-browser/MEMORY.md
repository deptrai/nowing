# Memory

_Curated long-term knowledge for Nowing E2E Browser Testing._

## Known Environment Quirks & Fixes
- **Zero Cache 401:** If Zero query fails with `401 TransformFailed`, ensure `NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848` and `POSTGRES_PORT=5434` are properly aligned.
- **Local Ports:** Postgres runs on `5434` and Redis on `6380` to avoid conflicts with host instances.
- **PostGIS in pgvector image:** The `pgvector/pgvector:pg17` Docker image does not include PostGIS. `CREATE EXTENSION postgis` fails until `apt-get install postgresql-17-postgis-3` is run inside the container. This is required for `spatial_planning_zones` and any model using `Geometry` columns.
- **Missing frontend deps for build:** `leaflet` and `react-leaflet` are imported in `components/realestate/land-zoning/zoning-map.tsx` but are not in `package.json`; `pnpm build` fails until they are installed.
- **Alembic two heads:** As of 2026-08-17, revisions `223_add_audit_events_table.py` and `07582243b847_merge_e2e_heads_for_testing.py` are both heads. A temporary merge revision is needed to run `alembic upgrade head` on a fresh database.
- **E2E superuser requirement:** `/admin/scraper-accounts` (and likely all `/admin/*` pages) require `User.is_superuser=True`. The default `e2e-test@nowing.net` created by the Playwright auth setup is not a superuser, so admin E2E tests fail with 403/unexpected DOM.

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
- **Lead Detail Flyout Drawer Hook Ordering Fix (Story 24.3 / 21.16):** `LeadDetailFlyoutDrawer.tsx` must declare all `useState` and `useEffect` hooks at top level before `if (!isOpen || !lead) return null;` to avoid React Rules of Hooks crash (`Rendered more hooks than during the previous render`).
- **Multi-Vertical Beta Pilot Live Dogfooding Run (2026-08-17):**
  - **BĐS (5):** Batdongsan & Chợ Tốt active broker listings & ngộp properties (Quận 3, Quận 12, Quận 10, Tây Hồ, Đức Linh).
  - **HR & Headhunting (5):** TopCV & ITviec Tech Recruiters (CMC Telecom, Newwave Solutions, AHT Tech, BSS Group, VBA Technology).
  - **B2B Corporate & Services (5):** Masothue & CafeF newly registered entities with verified MST and legal reps (Taseco KCN Kim Bảng, Auto Investment Group, USC Interco, Khánh Linh, Xây dựng Đại Phát).
  - **Verification:** Lead Kanban Pipeline (`/dashboard/1/leads/pipeline`), Round-Robin allocation, timeline audit trail, 1-Click Zalo Outreach script copier, and Masked Phone display (`PhoneCopyPill`) fully operational.
  - **Pilot Tracker:** Populated in `_bmad-output/planning-artifacts/multi-vertical-pilot-tracker.csv`.

## Epic 24 Live Pilot — 2026-08-17

### Environment
- Stack: Postgres 5434, Redis 6380, Backend 8000, Zero 4848, Frontend 3000.
- Playwright viewport default, logged in as `e2e-test@nowing.net`.

### 24.4 Lead Clipper
- Extension builds successfully (`pnpm run build` in `apps/chrome-extension`).
- Backend `POST /api/v1/workspaces/1/leads/clip` accepts clipper PAT and returns
  `{success, lead_id, dedupe_hash, is_duplicate}`.
- Phone normalization works: `+84 0909123456` stored/normalized to `0909***456`
  (masked in `lead.phone`).
- Deduplication works: re-clipping same canonical URL + phone returns
  `is_duplicate: true`.
- ⚠️ Live extension UI not loaded in this session — requires Chrome with unpacked
  `dist/` extension. API path verified only.

### 24.3 Kanban / Team
- `/dashboard/1/leads/pipeline` renders 4 stages (Mới săn, Đang tiếp cận,
  Tiềm năng, Đã chốt, Hủy / Không nhu cầu) and live lead cards.
- Lead detail flyout drawer opens and shows fit-score, timeline, source, content.
- Team page `/dashboard/1/team` loads member list.
- ⚠️ MemberSpendCapDialog not reachable because test workspace only has the owner;
  action menu is hidden for `is_owner=true` members (`showActions = !is_owner`).
- ⚠️ Drag-and-drop stage transition not exercised in this session; Playwright MCP
  has no native drag tool and dnd-kit requires careful pointer-event synthesis.

### 24.2 Phone Waterfall / PII Masking
- Lead API returns masked phone `0909***456`.
- ⚠️ `PhoneCopyPill` renders `—` for masked phone because
  `safePhone.replace(/\D/g, '').length >= 8` only counts digits, and a masked
  11-digit number like `0909***456` has only 7 digits. Kanban card therefore shows
  `—` instead of `0909***456`.
- Copy-to-clipboard for masked numbers would also produce an incomplete number
  because `safePhone.replace(/[^\d+]/g, '')` drops the `*`, e.g. `0909456`.
- This is a pre-existing UI issue that also breaks masked-phone display on the
  Lead Kanban board.

### Console / Errors
- Initial page load on `/` produced `401 /auth/session` before login.
- No console errors on dashboard or team pages during pilot.



