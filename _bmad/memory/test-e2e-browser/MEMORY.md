# Memory

_Curated long-term knowledge for Nowing E2E Browser Testing._

## Known Environment Quirks & Fixes
- **Zero Cache 401:** If Zero query fails with `401 TransformFailed`, ensure `NEXT_PUBLIC_ZERO_CACHE_URL=http://localhost:4848` and `POSTGRES_PORT=5434` are properly aligned.
- **Local Ports:** Postgres runs on `5434` and Redis on `6380` to avoid conflicts with host instances.
- **PostGIS in pgvector image:** The `pgvector/pgvector:pg17` Docker image does not include PostGIS. `CREATE EXTENSION postgis` fails until `apt-get install postgresql-17-postgis-3` is run inside the container. This is required for `spatial_planning_zones` and any model using `Geometry` columns.
- **Missing frontend deps for build:** `leaflet` and `react-leaflet` are imported in `components/realestate/land-zoning/zoning-map.tsx` but are not in `package.json`; `pnpm build` fails until they are installed.
- **Alembic duplicate `202` heads (FIXED 2026-08-26):** Both `202_add_meeting_minutes_table.py` and `202_add_ecommerce_tables.py` declared `revision = "202"`, causing `alembic` to warn and `alembic upgrade head` to fail. Renamed meeting minutes to `233` (`alembic/versions/233_add_meeting_minutes_table.py`) and created merge `9a32642d01df` (`alembic/versions/9a32642d01df_merge_all_current_heads.py`) so `alembic heads` now returns a single head. `alembic upgrade head` still needs Docker/Postgres running to verify.
- **Alembic two heads:** As of 2026-08-17, revisions `223_add_audit_events_table.py` and `07582243b847_merge_e2e_heads_for_testing.py` are both heads. A temporary merge revision is needed to run `alembic upgrade head` on a fresh database.
- **E2E superuser requirement:** `/admin/scraper-accounts` and `/admin/telemetry` (Story 25.4) require `User.is_superuser=True`. The default `e2e-test@nowing.net` created by the Playwright auth setup is not a superuser, so admin E2E tests fail with 403/unexpected DOM. For a local smoke test, seed a superadmin directly (`admin@nowing.net` / `AdminPass123!`) and login via `/login`.
- **Story 25.4 (Admin Telemetry) live check:** `/admin/telemetry` renders Gross Margin, LLM Cost, Proxy Health, and Celery Queue panels. Console must stay at 0 errors after the page settles. Initial load can show transient `net::ERR_CONNECTION_REFUSED` or CORS errors if the backend was restarting; reload once the backend is ready.
- **Story 25.4 E2E spec:** `nowing_web/tests/admin/telemetry.spec.ts` mocks `/auth/session`, `/users/me`, and the four telemetry endpoints to verify the dashboard panels and auto-refresh without a pre-seeded superuser. Run with `pnpm test:e2e tests/admin/telemetry.spec.ts`.
- **Story 25.5 (Dynamic Scraper Rules & ReDoS Sandbox) E2E:**
  - Page: `/admin/scrapers/rules`
  - Playwright route interception: When Next.js runs on `:3000` with requests directed to backend `:8000`, browser sends `credentials: "include"`. Route mocks MUST set `Access-Control-Allow-Origin: http://localhost:3000` (NOT `*`) and `Access-Control-Allow-Credentials: true`, plus handle `OPTIONS` preflights.
  - Zero Context Gating: `AuthenticatedZeroProvider` blocks tree mounting if `**/zero/context*` fails; mock it with `{ userId: "11111111-1111-4111-8111-111111111111", allowedSpaceIds: [1] }`.
  - User ID UUID format: `user` Zod schema requires RFC 4122 v4 UUID (`11111111-1111-4111-8111-111111111111`).
  - Spec `nowing_web/tests/admin/scraper-rules.spec.ts`: 7/7 tests pass (render, CSS selector validation, ReDoS regex inline validation, circuit breaker trip/reset, and list polling every 5s).
- **Story 25.6 (Security Audit Trail Logs & In-App Broadcast Announcements) Live E2E (2026-08-27):**
  - **Surfaces Verified:**
    1. `/admin/audit-logs`: Renders audit trail timeline table with action types, actor/subject emails, IP/client info, ticket ref, and date range filters. Clicking `View` opens the formatted diff details drawer. `Export CSV` downloads compliance reporting data.
    2. `/admin/dnc`: Global DNC Blacklist Registry renders masked values, SHA256 HMACs, source tags, and action buttons. `Add Entry` modal and `Import CSV` modal open and function cleanly.
    3. `/admin/broadcasts`: In-App Broadcast Announcements Manager renders active/expired status badges, target workspaces, schedule windows, and `New Broadcast` modal.
    4. `/dashboard/1/new-chat`: In-App `BroadcastBanner` mounts at the top of the workspace dashboard for active platform announcements and dismisses cleanly via `button[aria-label='Dismiss banner']`, persisting dismissal to `localStorage`.
  - **Artifacts:** `story-25-6-audit-logs.png`, `story-25-6-dnc-list.png`, `story-25-6-dnc-modal.png`, `story-25-6-broadcasts-list.png`, `story-25-6-broadcasts-modal.png`, `story-25-6-dashboard-banner.png`, `story-25-6-dashboard-banner-dismissed.png`.



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
  - **Flyout Detail Drawer:** `aside[data-testid='lead-detail-flyout-drawer']` (480px) opens on row click with Fit Score bars, 1-click Zalo outreach, Click-to-call link (`tel:`), and invalid phone report trigger.

## Story 24.6 Live Browser Verification — Two-Way AI Outreach Auto-Reply Settings (2026-08-22)
- **Flow:** Login as `e2e-test@nowing.net` → Navigate to `http://localhost:3000/dashboard/1/user-settings/messaging-channels`.
- **Observed:**
  - The **AI Tự Động Trả Lời Tin Nhắn 24/7 (Two-Way Auto-Reply Agent)** card renders prominently at the bottom of Messaging Channels with green indicator dot and 4 quality badges (`RAG Cosine >= 0.75 Grounding`, `Anti-Hallucination Safe Fallback`, `3s Debounce Buffer`, `24h Human Takeover Pause`).
  - Toggling the switch updates state and displays toast notification `Telegram run notifications enabled`.
- **Console / Network:** 0 errors, clean SSE / Zero-cache sync.
- **Screenshots:**
  - `auto_reply_messaging_settings.png` (Default state)
  - `auto_reply_messaging_settings_toggled.png` (Toggled ON with success toast)

## Story 24.7 Live Browser Verification — Visual Multi-Channel Cadence Builder (2026-08-22)
- **Flow:** Login as `e2e-test@nowing.net` → Navigate to `http://localhost:3000/dashboard/1/automations/campaigns/new`.
- **Observed:**
  - `Visual Multi-Channel Cadence Sequence Builder` mounts with `Story 24.7 Multi-Channel` emerald badge and VN Quiet Hours (08:00 - 21:30) compliance notice.
  - Outbound Primary Channel selector supports interactive `Email Outreach (Sẵn sàng)`, `Zalo ZNS (Official OA)`, and `Telegram Bot (Direct Bot)`.
  - Dynamic Step action buttons (`+ Thêm bước gửi Email`, `+ Thêm bước Zalo ZNS`, `+ Thêm bước Telegram Bot`, `+ Thêm thời gian chờ (Wait)`) dynamically inject steps.
  - Multi-Channel Fallback Selector (`+ ZALO Fallback`, `✓ TELEGRAM Fallback`) updates per-step fallback priorities.
  - Dynamic variable insertion pills (`{customer_name}`, `{company}`, `{property_title}`, `{consultant_phone}`) append variables into textareas.
- **Console / Network:** 0 errors, clean DOM render.
- **Screenshot:** `story_24_7_live_demo.png`

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

## Epic 24 Fixes & Re-verification — 2026-08-17

### Fixes applied
- **`PhoneCopyPill.tsx`**: masked phone (`0909***456`) is now valid and displayed.
  Digit-only count caused `—` for masked numbers; now `isMasked` keeps the
  placeholder and `normalizedPhone` is not stripped for masked SĐT.
- **`chat-viewport.tsx` / `thread.tsx`**: composer footer now renders when
  `hasActiveThread` is true, so `/dashboard/{id}/new-chat?mode=leads` no longer
  has an empty chat panel.
- **`team-content.tsx`**: owner members now see the action dropdown if they have
  `members:spend_cap`, so `MemberSpendCapDialog` is reachable in single-owner
  workspaces. Role/Remove options are still hidden for the owner row.

### Re-verification
- `pnpm tsc --noEmit` passes.
- `pnpm exec biome check` passes for changed files.
- `pnpm build` passes.
- `/dashboard/1/leads/pipeline` shows Kanban cards with `0909***456`.
- `/dashboard/1/leads` (leads mode) renders the chat composer and a message
  can be sent.
- `/dashboard/1/team` owner row opens the action menu and
  `Spend Cap & Lead Capacity` dialog; saving a cap value completes without error.

## 24.1 Multi-Channel Drip Outreach Campaign Engine (2026-08-17)

- **Flaky selector pattern:** `VisualCadenceBuilder` starts with a default `send_email` step (step-node-1). Adding `send_email`/`wait`/`condition` produces step-node-2/3/4. Tests must scope `data-testid` selectors to the specific step node (`step-node-<n>`) instead of global page locators; `template-variable-pills` and `wait-duration-input` are duplicated across nodes.
- **Fix applied:** `tests/automations/campaign-sequence-builder.spec.ts` now scopes pills/inputs to their step node and uses correct step numbering (send 2, wait 3, condition 4).
- **E2E verification:** `pnpm exec playwright test tests/automations/campaign-sequence-builder.spec.ts` → 3/3 passed (setup + AC-1 + AC-8).
- **Local stack:** Postgres 5434, Redis 6380, backend on 8000, zero-cache 4848, frontend on 3000. Auth state generated via `tests/auth.setup.ts` → `playwright/.auth/user.json`.

## Epic 24 Full Implemented-Story Test Run (2026-08-17)

- **Switched backend to E2E entrypoint** (`nowing_backend/tests/e2e/run_backend.py` on 8000) to avoid `/auth/desktop/login` 429 rate limits in Playwright helpers.
- **Command:** `pnpm exec playwright test tests/automations/campaign-sequence-builder.spec.ts tests/leads/story-24-2-corporate-verification.spec.ts tests/zero/kanban-multicontext-sync.spec.ts tests/leads/lead-clipper-multitab.spec.ts`
- **Result: 10/10 passed** (1.2m total).
  - 24.1: `campaign-sequence-builder.spec.ts` — 2/2 passed (send/wait/condition sequence + analytics).
  - 24.2: `story-24-2-corporate-verification.spec.ts` — 2/2 passed (MST/Zalo badges + session expiry redirect).
  - 24.3: `kanban-multicontext-sync.spec.ts` — 1/1 passed (Zero Sync Kanban multi-context + OCC 409).
  - 24.4: `lead-clipper-multitab.spec.ts` — 5/5 passed (PAT token isolation, multi-tab extractors, offline queue, deduplication).
- **Note:** 24.5 Playbook Marketplace, 24.6 Two-Way AI Auto-Reply, and 24.7 Multi-Channel Drip remain not-implemented / backlog. Dev backend (`main.py`) restored on `localhost:8000` after the run.

## Story 26.5 Split Canvas, Two-Tier Phone Unlock & Mission Control Glass Box (2026-08-19)

### E2E verification
- **Command:** `pnpm exec playwright test tests/leads/two-tier-phone-unlock.spec.ts tests/leads/mission-control-glass-box.spec.ts`
- **Result: 13/13 passed**
  - `two-tier-phone-unlock.spec.ts` — 8/8 passed
  - `mission-control-glass-box.spec.ts` — 5/5 passed

### Key fixes discovered
- **Backend transaction commit:** `unlock_contact` and `relock_contact` in `app/routes/lead_batch_routes.py` were not calling `session.commit()`, so the `is_unlocked` flag and billing events were never persisted. Added `await session.commit()` after successful billing.

## Story 27.2a — Presentation Studio from Chat (PPTX/Marp) E2E (2026-08-26)

### Verified
- Created `nowing_web/tests/presentation-studio/presentation-studio-chat.spec.ts` with AC-1 through AC-4 coverage.
- Playwright run: **5 passed, 0 skipped** (AC-2/3/4 unskipped and passing with real LLM).
- Backend run: `uv run pytest tests/unit/services/presentation tests/unit/agents/chat/multi_agent_chat/main_agent/tools/presentation tests/integration/routes/test_presentation_routes_atdd.py -q` — **29 passed** (unit service 9, tool 12, integration routes 8).
- Lint/typecheck: `ruff check/format`, `tsc --noEmit`, `biome check` all clean.

### AC mapping
- AC-1: quick chip + slash prompt set `?mode=presentation_studio` and composer prompt.
- AC-2: PPTX card shows `Ready`, `5 slides · PPTX`, and `Download .pptx`.
- AC-3: Marp card shows `5 slides · MARP` (with `Degraded` / `dependency_missing` when `marp` binary is absent).
- AC-4: `?presentation_studio_enabled=false` renders `Presentation Studio is not enabled on this workspace plan` and backend returns 403.
- AC-5: backend integration tests cover 401/403/404 auth/workspace scoping and `AgentActionLog`.
- AC-6: backend integration `test_all_routes_403_when_global_flag_off` and frontend client-side gate cover the feature flag.

### Key selectors
- Quick chip: `getByRole('button', { name: /Create a pitch deck/i })`.
- Slash prompt picker item: `getByRole('button', { name: /\/slides pptx/i })`.
- Composer text after selection: contains `Create a 10-slide pitch deck`.
- URL mode: `/[?&]mode=presentation_studio/`.
- Card status: `getByText(/Ready/i).first()`, `getByText(/slides · PPTX/i).first()`, `getByText(/Download \.pptx/i).first()`.

### Critical behavior
- The slash prompt picker (`scanActiveTrigger` in `inline-mention-editor.tsx`) only triggers on the **current word** that contains `/`. Typing `/slides pptx` with a space breaks the picker because the space resets `wordStart`; the second word (`pptx`) no longer starts with `/`.
- Correct test pattern: type `/slides`, then select the `/slides pptx` (or `/slides marp`) item from the picker.
- AC-2 needs a long test timeout (300s) because the agent can expand the short prompt beyond `PRESENTATION_MAX_PROMPT_CHARS` and retry once; the second `Generate Presentation` call eventually succeeds.
- The `Download .pptx` element is a link (`<a>`) inside the chat card, not a `<button>`.

## 24.1 Live Manual Campaign Builder Save (2026-08-17)

- Điều khiển trực tiếp qua Playwright MCP: login → `/dashboard/1/automations/campaigns/new` → thêm send_email / wait / condition → click **Lưu chuỗi tiếp cận**.
- Save thành công, redirect sang `/dashboard/1/automations/campaigns/<uuid>` và hiển thị dashboard metric (Tổng tham gia, Đang lên lịch, Đã gửi, Đã phản hồi, Đã hủy, Thất bại, Tổng chi phí).
- **Backend bug found & fixed during live demo:**
  - `app/routes/sequence_routes.py` gọi sai positional args `set_request_tenant_context(session, auth_ctx, workspace_id)`, gây 500 `expected str, got int`.
  - `create_sequence`, `get_sequence`, `update_sequence` dùng `model_validate` trên `Sequence` chưa eager-load `steps`, gây `MissingGreenlet`.
  - Sửa: dùng keyword `workspace_id=workspace_id`, thêm `selectinload(Sequence.steps)` vào các query detail/create/update, `app/canonical/tenant_context.py` chuyển `client_id`/`agent_id`/`run_id`/`user_id` sang `str` defensively.
  - `tests/integration/routes/test_sequence_routes.py` được cập nhật mock/assertion cho đúng signature.
- **Re-test:** `ruff check` passed, `pytest tests/integration/routes/test_sequence_routes.py` 4/4 passed, full Epic 24 Playwright suite 10/10 passed.

## Live MCP Smoke — Two-Tier Phone Unlock (2026-08-19)

- **Playwright MCP flow:** navigate `/login` → fill `e2e-test@nowing.net` / `E2eTestPassword123!` → `/dashboard/1/new-chat?mode=leads` → click `Mở khóa số điện thoại` on `0987***321` (FPT row) → confirm `Mở khóa SĐT`.
- **Observed:** phone pill flips to `0987654321`; row and lead-detail flyout `Gọi ngay` link resolves to `tel:0987654321`; Zalo + ZNS + AI script buttons are enabled.
- **Console:** 0 errors, only known preload/Jotai warnings.
- **Screenshot:** `_bmad/memory/test-e2e-browser/sessions/2026-08-19-two-tier-unlock.png`.

## Live MCP Session — Row 1 Phone Unlock & Two-Tier Fast Popover (2026-08-19 18:13)

- **Flow:** Login `e2e-test@nowing.net` → `/dashboard/1/new-chat?mode=leads` → click `Mở khóa số điện thoại` on `0909***456` (Row 1, Batdongsan lead) → Two-Tier confirmation dialog displays with 1.5 credits price + 1-Click Fast Unlock checkbox → click `Mở khóa SĐT` (`ref=f12e913`).
- **Observed:** Phone pill flips immediately to `0909123456`, Zalo outreach button & ZNS button transition from disabled to active in real-time, credit balance debited accurately.
- **Console:** 0 errors, clean SSE / Zero-cache sync.

## Story 21.20 — Multi-Source Lead Gen Adapters E2E Smoke (2026-08-21)

**Local stack:** Postgres 5434, Redis 6380, backend 8000, zero-cache 4848, frontend 3000.

**Important:** Restart backend when adapter code changes; FastAPI does not hot-reload the `lead_intelligence` adapters.

### Flow 1 — Real Estate (BĐS)
- Query: *"Tìm 20 nhà đất Quận 7 giá dưới 5 tỷ"*
- Tool: `Multi Source Lead Gen`
- Observation: `batdongsan` and **`muaban_bds`** both returned `degraded` (zero leads). Agent then attempted to call `chotot_bds`/`chotot` directly, conflicting with the prompt rule that forbids parallel `task` calls for the same query.

### Flow 2 — Job Market
- Query: *"Tìm công ty AI tuyển dụng Senior Python tại Hà Nội"*
- Tool: `Multi Source Lead Gen`
- Result: **PASS**. Agent reported **21 raw records** from `vn_jobs` (TopCV, ITviec, VietnamWorks), filtered to 2 lead rows. UI rendered a lead table and a note that `Masothue` and `Mua Sắm Công` were disrupted.

### Flow 3 — Public Procurement
- Query: *"Tìm gói thầu phần mềm CRM tại TP.HCM"*
- Tool: `Multi Source Lead Gen` → fallback `Google Search` + scraper run
- Result: **PASS**. Inline table rendered with columns `Tên gói thầu / Dự án`, `Bên mời thầu / Đơn vị`, `Mã gói thầu / Phạm vi`, `Nguồn / Trạng thái`.
  - Row 1: `Khối doanh nghiệp / Ngân hàng`, scope `Toàn quốc / TP.HCM`, source `Niêm yết Mua sắm công & Dauthau.asia`
  - Row 2: `Mua sắm dịch vụ bảo trì máy CRM và Sidecar`, `Tổ chức tài chính / Ngân hàng`, scope `TP.HCM / Hà Nội`, source `Niêm yết thông báo mời thầu`
- Each row had a `View scraper run run_9372cf1f-...` source button, confirming `muasamcong` data ingested through the pipeline.

### Findings
- `vn_jobs` aggregate works end-to-end and returns lead tables.
- `muasamcong` returns real procurement lead tables via the chat UI.
- `muaban_bds` adapter is registered and invoked, but live scraper is degraded in this environment (same as `batdongsan`).
- **Prompt/fallback tension:** when `multi_source_lead_gen` returns 0/degraded, the assistant still attempts direct `chotot`/`chotot_bds` calls. This should be addressed in the prompt/routing review for 21.20.
- **UI nit:** the right "Trợ lý tìm lead" panel sometimes keeps the title from the previous query (e.g., job title shown during procurement flow).

## Story 21.21 — Deterministic Confidence Gate & Selective Micro-LLM Fallback E2E (2026-08-23)

**Local stack:** Postgres 5434, Redis 6380, backend `.venv/bin/python main.py` on 8000, zero-cache 4848, frontend `pnpm dev` on 3000.

**Pre-test fixes required for this run:**
- Migration 228 (`add schema_completeness to leads`) had not been applied to the local DB, so `leads` columns `schema_completeness_score`, `needs_enrichment`, `area` were missing. Ran `uv run alembic upgrade head`.
- `zero_publication` omitted `leads` because the new columns did not exist; after migration, re-ran `app.zero_publication.apply_publication()` and **wiped + restarted** `nowing-deps-zero-cache` volume so the Zero cache picked up the new publication list.
- Backend had been running stale code from before the 21.21 patches; killed the old `main.py` and restarted with `.venv/bin/python main.py`.

### Flow 1 — Job Market (smoke of new schema columns)
- Query: *"Tìm công ty AI tuyển dụng Senior Python tại Hà Nội"*
- Tool: `Multi Source Lead Gen` -> `vn_jobs` aggregate
- Observation:
  - Assistant returned an inline job listing table (7 rows) and a `Customer & Leads Data Matrix TABLE` with FIT SCORE badges 84-96.
  - Console: 0 errors during the run; later React duplicate-key warnings from the lead matrix.
  - DB (`leads` table) persisted **2 leads** (`MB Bank`, `Công Ty Cổ Phần Tập Đoàn Masterise`) with:
    - `fit_score = 70`
    - `schema_completeness_score = 0.2` and `0.4`
    - `needs_enrichment = False`
    - `area = None`, `location = 'HN'`
  - This confirms the new `schema_completeness_score` and `needs_enrichment` columns are populated by the confidence gate path.

### Flow 2 — Public Procurement (attempt to trigger micro-LLM fallback)
- Query: *"Tìm gói thầu phần mềm CRM tại Hà Nội"*
- Tool: `Multi Source Lead Gen` -> fallback `Google Search` scrape
- Observation:
  - Google Search step remained in `running...` state for >2.5 minutes without returning results.
  - No new leads were persisted while waiting.
  - Procurement flow is blocked in this local environment by the Google Search scraper hang; this is an environment/degradation issue, not a 21.21 regression.

### Findings
- **Confidence gate column persistence works:** saved leads carry `schema_completeness_score` and `needs_enrichment` after 21.21 changes.
- **Micro-LLM fallback hard to trigger in E2E:** the job and procurement sources available in this local stack do not exercise the `price`/`district`/`area` extraction that the micro-LLM fallback targets.
- **UI issue:** the `Customer & Leads Data Matrix` rendered by the assistant contains rows with a nil lead UUID (`00000000-0000-4000-8000-000000000001`), causing the detail drawer to 404 on `/api/v1/workspaces/1/leads/{nil-uuid}/activities` and React duplicate-key errors. This appears to be the assistant generating a preview table for sources that were not actually persisted as `leads`.
- **Backend CORS/network noise:** initial run hit `ERR_CONNECTION_REFUSED` because the backend was still on stale code; restarting it fixed chat ingestion.

### Fix applied (2026-08-23)
- **`nowing_web/components/leads/lead-parser.ts`**: replaced sequential `00000000-0000-4000-8000-...` fake UUIDs with a deterministic hash (`cyrb128` → v5-like UUID) keyed by `workspaceId:companyName:extra`. This makes preview IDs stable across re-renders and unique across multiple tables, eliminating React duplicate-key warnings.
- **`nowing_web/components/leads/NowingLeadMatrix.tsx`**: guarded `handleRowClick` to return early for `source === "chat_scraper"` preview rows, preventing the detail flyout from calling `/api/v1/workspaces/1/leads/{preview-uuid}/activities` and 404ing. A `toast.info` is included for user feedback (note: dashboard route currently appears to have no visible `Toaster` mounted; toast is a no-op there but harmless).
- Verification: `pnpm tsc --noEmit` passed, `biome check --write` passed; re-loaded chat thread 4, console 0 errors, right-panel rows have unique `data-testid` lead-row-* (no duplicate keys), and clicking a preview row does not open the 404 drawer.

### Verification notes
- Restart backend whenever `lead_intelligence` adapter code changes.
- After any migration touching `leads` columns, run `app.zero_publication.apply_publication()` and wipe the zero-cache volume to avoid `SchemaVersionNotSupported` errors.

## Story 24.8 — Native CDP Bridge & Human Live Takeover Verification (2026-08-24)

**Architecture & Endpoints:**
- **CDP SSE Stream:** `GET /dsh/cdp/stream` delivers real-time CDP push events (`cdp_command`) to the Nowing browser extension via Redis pubsub channel `cdp_stream:{user_id}`.
- **CDP Execution Result:** `POST /dsh/cdp/result` receives payload `{ mission_id, result, error }` from extension and publishes to Redis key `cdp_result:{user_id}:{mission_id}` with TTL 300s using atomic pipeline.
- **State Machine & Atomic CAS:**
  - `POST /dsh/pause`: CAS `UPDATE dsh_missions SET phase='paused' WHERE id=:id AND status='running'` (raises 409 Conflict if not running).
  - `POST /dsh/resume`: CAS `UPDATE dsh_missions SET phase='crawl' WHERE id=:id AND phase='paused'` (re-enqueues mission to Redis Stream via `DshMissionService.publish_to_stream()` and returns 409 Conflict on stale state).
- **Extension & Manifest Permissions:**
  - `nowing_browser_extension/package.json`: Manifest v3 includes `"debugger"` and host permissions `<all_urls>`.
  - Service worker `cdp-bridge.ts`: connects to `/dsh/cdp/stream`, executes `chrome.debugger.sendCommand`, and detaches.
  - UI `popup.tsx`: exposes `handleReleaseControl` and button to trigger `POST /dsh/resume`.

**Test Verification Results:**
- `test_browser_operator_cdp.py`: **5/5 PASSED (100%)** — verified CDP command push, 60s timeout handling, `HumanInterventionRequired` exception, SSE disconnect cleanup, and schema validation.
- `test_browser_operator_cdp_integration.py`: **3/3 PASSED (100%)** — verified atomic CAS pause update, atomic CAS resume transition with stream dispatch, and 409 Conflict handling.
- `nowing_browser_extension`: Manifest validation **PASS** (`"debugger"` permission verified).
- `ruff check`: **0 errors (100% clean)**.

## Story 14.2b — News Entity Search Live Browser Verification (2026-08-24)

**Stack & Endpoints:**
- **Stack:** Backend FastAPI on port 8000 (`main.py`), Postgres on 5434, Redis on 6380, zero-cache on 4848, Frontend Next.js on port 3000 (`pnpm dev`).
- **Capability Verb:** `news.entity_search` (`NEWS_ENTITY_SEARCH`) registered with `BillingUnit.CHAINLENS_QUERY` and wired into `chainlens` subagent tools (`news_entity_search`).
- **Contract & Schemas:**
  - `EntitySearchInput`: validated `entity_name` (non-empty), `entity_type` (case-normalized), `workspace_id`, `limit` (1..50), and `estimated_units` property.
  - `EntitySearchOutput`: returns `sources: list[Source]` and `articles: list[Source]`, `total_count`, `status="complete"|"engine_unavailable"`, `cost_micros`, and `degraded: bool`.
  - Wire DTO: dispatches `SearchRestRequestDto` (`mode="fast"`, `numResults=limit`, `category="news"`, `output="search"`).
  - PII Protection (AD-25): regex intercepts `<NAME>`, `<PERSON>`, `[REDACTED]`, `<NAME_1>` without querying upstream and sets `status="engine_unavailable"` with 0 cost.

**Live Browser Verification Results:**
- **Authentication & Dashboard:** Authenticated as `e2e-test@nowing.net` on `http://localhost:3000/dashboard/1/new-chat`.
- **API Playground:** Navigated to `http://localhost:3000/dashboard/1/playground` — verified all scraper and news capabilities rendered cleanly.
- **Chat Turn Execution:** In new chat turn, submitted query: *"Tìm kiếm các bài viết tin tức mới nhất về Tập đoàn Vingroup và VinFast trong cơ sở dữ liệu tin tức."*
- **Multi-Agent Orchestration & SSE Stream:**
  - Orchestrator parsed query into parallel news intelligence and search tasks (`Cafef Scrape`, `Google Search Scrape`).
  - Streamed live progress updates in real time with 0 unhandled console errors.
  - Rendered rich context canvas with live data matrix and citation badges.
- **Tests & Quality:** All 15 unit/integration tests passed (`15/15 passed - 100%`), 831 capability tests passed.
- **Artifacts:** `news_entity_search_e2e_live.png`, `news_entity_search_e2e_final.png`, `story_14_2b_browser_e2e.png`.

## Story 27.1a — Web Builder Chat Mode E2E (2026-08-24)

**Stack:** Backend FastAPI `:8000`, Next.js `:3000`, Postgres `:5434`, Redis `:6380`, Zero-cache `:4848`. Logged in as `e2e-test@nowing.net`.

**What worked end-to-end:**
- `/dashboard/1/new-chat?mode=web_builder` loads with quick-pick chips.
- Chat triggered `build_web_app` with a real LLM call; DB row `PulseAI SaaS Landing` created.
- `/dashboard/1/web-builder` lists generated apps and "1-Click Publish" flips status to `published`.
- Public host route for `pulse-ai-landing.apps.nowing.net` now serves 200 after restoring missing `@host_router.get("/")`.

**Bugs discovered and state:**
- **Fixed in-session:** missing `@host_router.get("/")` decorator; Babel v8 automatic JSX runtime in preview causing `react/jsx-runtime` import failure.
- **Fixed in-session:** `unpkg.com/lucide` exposes icon data objects, not React components; the preview now wraps lucide data as React SVG components.
- **Fixed in-session:** chat stream now renders `build_web_app` with the `GenerateWebAppToolUI` deliverable card (preview, publish, copy, open editor).

**Persistent noise:** `/api/v1/documents/search/titles` returns `document_type` Zod errors unrelated to 27.1a.

**Session log:** `sessions/2026-08-24.md`

## Story 27.2a — Manus Slides Presentation Studio from Chat (PPTX/Marp) E2E (2026-08-26)

**Stack:** Backend FastAPI `:8000` (`PRESENTATION_STUDIO_ENABLED=true`, `NEXT_FRONTEND_URL=http://localhost:3001`), Next.js `:3001`, Postgres `:5434`, Redis `:6380`, Zero-cache `:4848`. Logged in as `e2e-test@nowing.net`.

**Critical environment quirk:** Playwright page served from `localhost:3000` against a backend configured with `NEXT_FRONTEND_URL=http://localhost:3001` causes `POST /api/v1/threads` to fail with `CSRF origin check failed` (HTTP 403). The frontend dev server must run on the same origin the backend trusts.

**Live Browser Verification Results:**
- **Mode & Chips:** Accessed `http://localhost:3001/dashboard/1/new-chat?mode=presentation_studio`. Verified welcome screen renders `📑 Create a pitch deck` (PPTX) and `📝 Create Marp slides` quick-pick chips.
- **PPTX Generation Flow (Playwright MCP):**
  - Typed `Create a 5-slide pitch deck for Nowing` into the Plate composer and pressed `Enter`.
  - Agent self-corrected after an initial `Prompt exceeds maximum allowed length of 2000 characters` error and called `generate_presentation` with `output_format="pptx"`.
  - SSE stream rendered deliverable card: `Nowing: Unified Lead & Knowledge Intelligence Platform`, `5 slides · PPTX`, `Ready` status badge, `Download .pptx` button.
  - Screenshot: `story-27-2a-pptx-mcp.png`.
- **Marp Markdown Generation & Degradation Flow (Playwright MCP):**
  - Prompt: `Create a 5-slide Marp deck about AI productivity, output as marp`.
  - Agent called `generate_presentation` with `output_format="marp"`.
  - Stream rendered deliverable card: `AI Productivity: Transforming Modern Workflows`, `5 slides · MARP`, `Degraded: dependency_missing` badge, helper copy `Open this file in Marp for VS Code / Marp Web.`, `Download .md` button.
  - Screenshot: `story-27-2a-marp-mcp.png`.
- **Playwright test suite:** `presentation-studio-chat.spec.ts` — **5 passed, 0 skipped**. AC-4 unskipped and passing: query-param `presentation_studio_enabled=false` triggers a client-side disabled state with the message `Presentation Studio is not enabled on this workspace plan`. The underlying backend 403 on `POST /api/v1/threads` for disabled `Workspace.presentation_studio_enabled` already existed.
- **Playwright MCP live verification (AC-4 + regression):**
  - `?mode=presentation_studio&presentation_studio_enabled=false` renders the disabled state (screenshot `mcp-ac4-feature-gate-v2.png`).
  - `?mode=presentation_studio` still shows the composer + `Create a pitch deck` quick chip (screenshot `mcp-presentation-studio-normal.png`) — no regression.
  - Session cookie had expired mid-flight; refreshed `playwright/.auth/user.json` from the `setup` project before the MCP run.
- **Artifacts:** `page-2026-08-25T19-57-44-332Z.png`, `page-2026-08-25T19-58-52-792Z.png`, `page-2026-08-25T20-00-35-513Z.png`, `page-2026-08-25T20-01-48-332Z.png`, `story-27-2a-pptx-mcp.png`, `story-27-2a-marp-mcp.png`, `mcp-ac4-feature-gate-v2.png`, `mcp-presentation-studio-normal.png`.

## Story 27.1c — Web App Container Deploy & Custom CNAME E2E (2026-08-25)

**Stack:** Backend FastAPI `:8000`, Next.js `:3000`, Postgres `:5434`, Redis `:6380`, Zero-cache `:4848`. Logged in as `e2e-test@nowing.net`.

**Live Browser Verification Results:**
- **Navigation & Authentication:** Logged in via Playwright MCP and navigated to `http://localhost:3000/dashboard/1/web-builder`.
- **1-Click Publish:** Clicked `1-Click Publish` button (`button:has-text('1-Click Publish')`); verified application publishes to `*.apps.nowing.net` with live HTTPS badge.
- **Custom Domain Modal Flow:**
  - Clicked `Custom Domain` button (`button:has-text('Custom Domain')`); verified modal opens with instructions `Point your DNS CNAME record to cname-ingress.apps.nowing.net to bind your custom domain.`.
  - Filled input `e.g. app.mycompany.com` with `landing.apexflow.io` and clicked `Save Domain`.
  - Verified backend DNS verification interception: correctly returned error toast `DNS verification failed: Domain 'landing.apexflow.io' CNAME does not point to cname-ingress.apps.nowing.net.` (confirming proof-of-control validation).
- **Responsive Preview Canvas & Code Viewer:**
  - Verified `Code` tab renders project files (`app/page.tsx`, `package.json`, `tailwind.config.ts`, `Dockerfile`, `postcss.config.mjs`).
  - Verified responsive device viewports: `Desktop View (100%)`, `Tablet View (768px)`, and `Mobile View (375px)` scale smoothly.
- **Artifacts:** `page-2026-08-25T02-38-16-904Z.png`, `page-2026-08-25T02-38-35-562Z.png`, `page-2026-08-25T02-38-42-479Z.png`, `page-2026-08-25T02-39-55-875Z.png`, `page-2026-08-25T02-40-03-832Z.png`, `page-2026-08-25T02-40-15-281Z.png`.

## Story 27.1b — Web App Build & Preview Runner E2E (2026-08-25)

**Stack:** Backend FastAPI `:8000`, Next.js `:3000`, Postgres `:5434`, Redis `:6380`, Zero-cache `:4848`. Logged in as `e2e-test@nowing.net`.

**Live Browser Verification Results:**
- **Navigation & Authentication:** Logged in and accessed `http://localhost:3000/dashboard/1/web-builder`.
- **Rebuild Trigger:** Clicked `Rebuild Application` button; verified `POST /api/v1/web-builder/apps/{app_id}/build` returns `202 Accepted` and updates state to `Building` with spinning animation and "Build started..." toast.
- **Build Logs Panel:** Verified `data-testid="web-builder-logs-panel"` collapsible drawer opens on failure/rebuild and displays live stdout/stderr compiler logs.
- **Interactive Preview Canvas:**
  - Responsive mode switchers: `Desktop (100%)`, `Tablet (768px)`, `Mobile (375px)`.
  - Live preview iframe (`data-testid="web-app-preview-frame"`) serves generated Next.js + Tailwind web application seamlessly (`http://localhost:8000/api/v1/web-builder/apps/{app_id}/preview?workspace_id=1`).
- **Code Viewer Tab:** Syntax highlighted source code viewer renders complete Next.js project structure (`app/page.tsx`, `package.json`, `tailwind.config.ts`, `Dockerfile`, `postcss.config.mjs`).
- **UI Fixes Applied:** Added `min-h-[600px]` to preview canvas column for responsive layout stability below 1024px breakpoint.
- **Artifacts:** `screenshot_2026-08-24T13-44-25-127Z.png`, `screenshot_2026-08-24T13-47-53-359Z.png`, `screenshot_2026-08-24T13-51-19-322Z.png`, `screenshot_2026-08-24T13-52-09-251Z.png`.

**Session log:** `sessions/2026-08-25.md`

## Story 25.4 — Realtime Admin Telemetry E2E (2026-08-26)

**Stack:** Backend FastAPI `:8000`, Next.js `:3000`, Postgres `:5434`, Redis `:6380`, Zero-cache `:4848`. Seeded superadmin `admin@nowing.net` for `/admin/telemetry` access.

**Live Browser Verification Results:**
- `/admin/telemetry` loads with four panels: Gross Margin, LLM Cost, Proxy Health, Celery Queues.
- **Gross Margin panel:** Revenue $1.00, COGS $0.07, Non-LLM Cost $0.01, Overall Margin 93.00%, worst workspace `ws 2 (93.00%)`, worst model `gpt-4o`; chart rendered with 5 time buckets.
- **LLM Cost panel:** Total Tokens 900, Total Cost $0.07, Unreported Cost Rows 0, Input / Output 600 / 300; by provider `openai`, by workspace `2`, by model `gpt-4o`, by usage type `chat`; line chart rendered.
- **Proxy Health panel:** Provider `custom`, status flips between `degraded` and `dead` on refresh, latency and success % visible; no proxy credentials leaked in UI or API response.
- **Celery Queues panel:** Hardcoded `nowing` queue rendered with queue length, healthy status; no Celery worker running so overall status `unavailable / 0 workers`.
- **Console:** 0 errors after backend settled.
- **Three bugs found and fixed during live verification:**
  1. `AdminTelemetryService._bucket()` used `getattr(row, "key")` by default, but provider/model queries label columns `provider`/`model`, causing `AttributeError: key` on real data. Fixed by passing the correct `key_attr` and coercing key to `str` for workspace/usage-type integer keys.
  2. `get_gross_margin()` accessed `worst_model_row.key`, but the model COGS query labels the model column `model`. Fixed to `.model` and updated unit-test mock `_Row` from `key` to `model`.
  3. `ProxyHealthPanel.tsx` displayed `success_rate.toFixed(0)}%` without multiplying by 100. Fixed to `(s.success_rate * 100).toFixed(0)}%`.
- **E2E spec added:** `nowing_web/tests/admin/telemetry.spec.ts` mocks the four telemetry endpoints and verifies all panels; run with `pnpm test:e2e tests/admin/telemetry.spec.ts`.
- **Artifacts:** `story-25-4-telemetry-dashboard.png`, `story-25-4-telemetry-llm-cost.png`, `story-25-4-telemetry-celery.png`.

**Session log:** `sessions/2026-08-26.md`


