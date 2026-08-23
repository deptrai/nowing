---
story_key: "24-8"
epic: "epic-24"
story: "24.8"
title: "Browser Operator CDP Tool for DSH Crawl Subgraph & Human Live Takeover UI"
status: "review"
baseline_commit: "4c37acfa9"
---

# Story 24.8: Browser Operator CDP Tool for DSH Crawl Subgraph & Human Live Takeover UI

## Story Overview

As an autonomous research agent or growth marketer,  
I want Nowing's AI Agent to operate directly within authenticated Chrome browser tabs via Chrome DevTools Protocol (`chrome.debugger` API) and pause for Human Live Takeover when encountering CAPTCHA or 2FA,  
So that the agent can scrape complex JavaScript-rendered and login-protected web platforms (Facebook Ads, LinkedIn, Batdongsan VIP, Shopee, TopCV) without credential sharing or mission failure.

---

## Architectural Invariants (AD-111)

- **AD-111 — Browser Operator Chrome Extension CDP Bridge [ADOPTED]:**
  - Extension (Manifest V3) connects via WebSocket/MessagePassing using `chrome.debugger` API.
  - Interacts directly with user's authenticated tabs holding real session cookies.
  - Supports instant Human Live Takeover without terminating the mission.
- **Fail-Soft Degradation:** If CDP attachment fails or tab is closed, the mission reports a clear degradation error instead of a hard crash.
- **Human Takeover Timeout SLA:** Human takeover pause maintains a 15-minute TTL. If no action is taken within 15 minutes, the CDP session detaches cleanly and transitions to `aborted_timeout`.
- **Zero PII Leakage:** All CDP command logs and DOM snapshots must pass through `redact_pii(..., context='lead_enrichment')`.

---

## Acceptance Criteria

### AC-1 — Chrome Extension CDP Bridge & Tab Attachment
- **Given** Nowing Chrome Extension (Manifest V3) with `debugger` and `activeTab` permissions,
- **When** an autonomous DSH crawl mission requests a browser operator session for a target domain,
- **Then** the Background Service Worker identifies the matching tab and attaches `chrome.debugger.attach({ tabId }, "1.3")`, returning a session token.

### AC-2 — Browser Operator Execution Engine (CDP Actions)
- **Given** an active CDP session,
- **When** the agent invokes `browser_operator.execute` (exposed to the `web_crawler` subagent via the capability/tool registry),
- **Then** it executes standard CDP primitives:
  - `navigate(url)`: `Page.navigate` + waits for `Page.loadEventFired` and a short DOM stability delay.
  - `click(selector)`: Resolves DOM NodeId via `DOM.querySelector`, evaluates box model, and dispatches `Input.dispatchMouseEvent`.
  - `fill(selector, text)`: Focuses input and inserts text via `DOM.focus` + `Input.insertText`.
  - `scroll(direction, px)`: Dispatches synthetic mouse wheel event via `Runtime.evaluate` and `Input.dispatchMouseEvent`.
  - `extract(selector)`: Evaluates `Runtime.evaluate` to return sanitized text/HTML of the selected element.
  - `take_screenshot(format)`: Dispatches `Page.captureScreenshot` (format: png/jpeg).
  - `detect_challenge(url)`: Runs the DOM challenge detector without further interaction and reports the detected signature.

### AC-3 — Bot Challenge Detection & Mission Pause
- **Given** navigation or interaction triggers a Cloudflare Turnstile, reCAPTCHA v2/v3, or 2FA OTP prompt,
- **When** the DOM inspector detects challenge signatures (e.g. `cf-turnstile`, `recaptcha`, `otp-input`),
- **Then** the CDP bridge returns a result with `requires_human=true` and `challenge=<signature>`, the `browser_operator.execute` capability surfaces the takeover condition to the agent, and the extension stores the `activeMissionId` so the popup can offer a "Release Control" button.

### AC-4 — Human Live Takeover UI Popover
- **Given** a mission in `waiting_for_human` state,
- **When** the user views the Nowing Web dashboard (`/dashboard/[workspace_id]`),
- **Then** UI renders a prominent **Human Live Takeover Popover / Banner** showing:
  - Target URL and detected challenge type (`CAPTCHA Challenge` / `2FA Verification`).
  - Active countdown timer (15:00 minutes remaining).
  - Instructions: *"Vui lòng mở tab trình duyệt để giải CAPTCHA hoặc nhập mã OTP, sau đó nhấn 'Tiếp tục'".*
  - Action button: `⚡ Tiếp tục nhiệm vụ (Resume Agent)`.

### AC-5 — Mission Resumption & State Recovery
- **Given** the user solves the CAPTCHA and clicks `Resume Agent`,
- **When** `POST /api/v1/dsh/missions/{mission_id}/resume` is called,
- **Then** backend verifies the challenge is cleared, re-engages the LangGraph mission executor from the last checkpoint, and resumes crawling seamlessly.

### AC-6 — Safe Timeout & CDP Session Detachment
- **Given** a mission waiting for human intervention,
- **When** 15 minutes elapse without user input,
- **Then** backend transitions mission status to `aborted_timeout`, detaches `chrome.debugger`, and refunds unconsumed credits to the workspace wallet.

---

## Technical Tasks

### 1. Backend: Browser Operator Capability & Mission Endpoints (`nowing_backend`)
- [x] Create `app/capabilities/browser_operator/`:
  - `definition.py` registers `browser_operator.execute` in the capability registry.
  - `schemas.py` defines `BrowserOperatorInput` (action as `Literal`, including `navigate`, `click`, `fill`, `scroll`, `extract`, `take_screenshot`, `detect_challenge`) and `BrowserOperatorOutput`.
  - `executor.py` publishes CDP commands to `cdp_stream:{user_id}`, waits on `cdp_result:{user_id}:{mission_id}` via `BLPOP`, and returns `success`/`message`/`data` (including `requires_human`/`challenge` handling).
- [x] Update `app/routes/dsh_routes.py`:
  - `GET /api/v1/dsh/cdp/stream` SSE stream for the Chrome extension to receive commands.
  - `POST /api/v1/dsh/cdp/result` accepts extension results with `result`, `error`, `requires_human`, and `challenge`.
- [x] Update `web_crawler` subagent system prompt (`app/agents/chat/multi_agent_chat/subagents/builtins/web_crawler/system_prompt.md`) to expose and instruct use of `browser_operator.execute`.
- [ ] Implement Mission Pause/Resume routes in `app/routes/dsh_mission_routes.py`:
  - `POST /api/v1/dsh/missions/{mission_id}/pause`
  - `POST /api/v1/dsh/missions/{mission_id}/resume`
- [ ] Implement Redis lock `dsh:lock:takeover:{workspace_id}:{mission_id}` with 900s (15m) TTL.

### 2. Frontend: Human Live Takeover Component & Controls (`nowing_web`)
- [ ] Create `components/dsh/HumanLiveTakeoverPopover.tsx`:
  - Hazard warning header with pulsing amber dot.
  - Challenge description and live countdown timer.
  - 1-Click `Resume Agent` trigger with loading state.
- [ ] Integrate takeover popover into `app/dashboard/[workspace_id]/layout.tsx` or Split-View Canvas.

### 3. Chrome Extension: Manifest V3 CDP Bridge
- [ ] Update `manifest.json` with permissions `debugger`, `activeTab`, `scripting`.
- [ ] Implement `background/cdp_bridge.ts` to attach `chrome.debugger` and handle command routing.

---

## Verification Commands

```bash
# Backend linter & unit tests
cd nowing_backend
uv run ruff check app/capabilities/browser_operator/ app/routes/dsh_routes.py app/schemas/dsh.py app/agents/chat/multi_agent_chat/subagents/builtins/web_crawler
uv run pytest tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py tests/unit/capabilities/test_registry.py tests/unit/capabilities/test_browser_operator.py tests/integration/tasks/dsh_worker/test_browser_operator_cdp_integration.py -q

# Frontend typecheck & linter
cd ../nowing_web
pnpm tsc --noEmit
cd ../nowing_browser_extension
pnpm tsc --noEmit
pnpm exec biome check background/cdp-bridge.ts background/index.ts popup.tsx
```

## Implementation Notes (2026-08-24)

- **Prompt-in-UI control fixed**: the `web_crawler` subagent system prompt now lists `browser_operator.execute` in `<available_tools>` and provides a playbook for mapping user requests ("mở trang", "click", "scroll", "screenshot", "điều khiển trình duyệt") to the correct `action`.
- **Capability contract**: `browser_operator.execute` is a first-class capability (`app.capabilities.browser_operator`). Input uses `Literal` actions (`navigate`, `click`, `fill`, `scroll`, `extract`, `take_screenshot`, `detect_challenge`). Output returns `success`, `action`, `message`, `data`.
- **SSE auth fixed**: the Chrome extension no longer uses `EventSource`; it uses `fetch` with `Accept: text/event-stream` and `Authorization: Bearer <token>`, with token fallback from `chrome.storage.local` and reconnect backoff.
- **Result contract fixed**: `POST /api/v1/dsh/cdp/result` now stores `requires_human` and `challenge`; the executor checks them and returns a human-takeover message to the agent.
- **Known gaps still open**: full DSH mission pause/resume lifecycle (`waiting_for_human` state, 15-minute TTL, credit refund), `nowing_web` Human Live Takeover popover, workspace/PAT scoping on `cdp_result`, and PII redaction of CDP data remain deferred / in progress.

### Review Findings

- [x] [Review][Decision] AD-111 contract mismatch: SSE vs WebSocket — Giữ SSE là canonical transport (đã cập nhật `architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md:AD-111`). Backend → Extension qua SSE; extension → backend qua REST.

- [x] [Review][Decision] Browser operator payload schema — Thêm `BrowserOperatorCdpPayload` trong `app/schemas/dsh.py` với `target_url` validated, `extra="forbid"`. CDP worker validate payload bằng model này và lấy `user_id` từ `mission`/`state` thay vì payload.

- [ ] [Review][Patch] IDOR / command injection qua user_id (high) — `BrowserOperatorCdpSubgraph._cdp_crawl_node` lấy `resolved_user_id` từ `payload.get("user_id")` (`dsh_worker_browser_operator.py:41`) thay vì `mission.user_id`; `DshMissionPayload` không có `user_id`; `LangGraphMissionExecutor.initial_state` thiếu `user_id` (`dsh_worker_langgraph.py:566-579`). Attacker có thể điều khiển trình duyệt của user khác.

- [x] [Review][Patch] CDP actions incomplete and navigate does not wait for load (high) — 2026-08-24: Extension `cdp-bridge.ts` now handles `navigate`, `click`, `fill`, `scroll`, `extract`, `take_screenshot`, and `detect_challenge`; `navigate` uses `Page.loadEventFired` and a 1s DOM stability delay.

- [x] [Review][Patch] No real CAPTCHA/2FA detection (high) — 2026-08-24: `cdp-bridge.ts` implements `_detectChallenge` with `Runtime.evaluate` against a selector list (`cf-turnstile`, `recaptcha`, OTP/2FA inputs, etc.) and runs it automatically after every action; a standalone `detect_challenge` action is also available.

- [ ] [Review][Patch] Pause/resume lifecycle wrong (high) — Khi phát hiện challenge, worker set `phase="paused"` + `status="running"` (`dsh_worker.py:941-950`), không phải `waiting_for_human`; không emit notification event SSE/WebSocket cho dashboard/extension; không xóa Redis lock (`dsh_worker.py:941-953`) nên resume bị trễ.

- [ ] [Review][Patch] Resume endpoint wrong path and no challenge verification (high) — `/dsh/resume` (`dsh_routes.py:501-546`) sai với spec `/api/v1/dsh/missions/{mission_id}/resume`; không verify challenge cleared; không resume từ checkpoint vì `_crawl_node` chỉ skip subtask `"crawl"` (`dsh_worker_langgraph.py:179-184`) trong khi CDP dùng `"cdp_crawl"`.

- [ ] [Review][Patch] Missing 15-minute TTL, aborted_timeout, credit refund (high) — Không có Redis lock `dsh:lock:takeover:{workspace_id}:{mission_id}` TTL 900s; không scheduler transition `aborted_timeout`, detach debugger, hoàn credits; `cdp_result` key expire 300s (`dsh_routes.py:469`).

- [ ] [Review][Patch] PII leakage in CDP data (high) — `cdp_result` lưu raw `payload.result` (`dsh_routes.py:461-470`); worker log full `parsed_result` (`dsh_worker_browser_operator.py:84`) và lưu raw `cdp_res` vào `state_checkpoint` (`dsh_worker_browser_operator.py:101-105`) không qua `redact_pii(..., context='lead_enrichment')`.

- [x] [Review][Patch] SSE auth broken in browser extension (high) — 2026-08-24: `cdp-bridge.ts` uses a fetch-based SSE reader with `Authorization: Bearer <token>` header, with token fallback through `@plasmohq/storage` and `chrome.storage.local`; 401/403 stops reconnection.

- [ ] [Review][Patch] Multi-tab race and non-durable command delivery (high) — Channel `cdp_stream:{auth.user.id}` (`dsh_routes.py:416`) và `cdp_result:{user_id}:{mission_id}` (`dsh_worker_browser_operator.py:58`) hardcoded theo user; worker dùng `redis.publish` (non-durable) nếu extension disconnect thì lệnh mất; `blpop` không kiểm tra command id/nonce.

- [ ] [Review][Patch] pause/resume/cdp_result lack workspace and PAT scoping (high) — Các endpoint `cdp_result`, `pause_mission`, `resume_mission` (`dsh_routes.py:447-546`) chỉ check `mission.user_id == auth.user.id`, không check workspace/PAT scoping (`auth.pat.workspace_id`).

- [x] [Review][Patch] cdp_result accepts arbitrary payload (medium) — 2026-08-24: `CdpResultPayload` uses `extra="forbid"`, validates `requires_human`/`challenge`, and whitelists result keys; caps strings to 1MB; storage uses Redis pipeline `rpush + expire + ltrim` to cap list length.

- [x] [Review][Patch] CdpBridge extension starts unconditionally and has race / URL validation issues (high) — 2026-08-24: `startListening` checks for an existing non-aborted `AbortController` to prevent duplicate streams; `handleCdpCommand` validates URL scheme (`https:`/`http:`) before attaching debugger; `_findMatchingTab` uses `targetUrl` host and falls back to active tab / creates a new tab.

- [ ] [Review][Patch] Human Live Takeover UI missing (high) — Không có `components/dsh/HumanLiveTakeoverPopover.tsx` trong `nowing_web`; extension `popup.tsx` `activeMissionId` khai báo nhưng không bao giờ set (`popup.tsx:11-12`, `popup.tsx:42-50`) nên nút "Release Control" không render.

- [ ] [Review][Patch] CDP result shape breaks downstream extraction (medium) — `_cdp_crawl_node` lưu `sources` từ `parsed_result.get("result")` (`dsh_worker_browser_operator.py:87-88`) với shape `{navigatedUrl, tabId}`, không khớp `_source_to_lead` cần `url/company_name/domain`; cũng không áp dụng `_SOURCE_WHITELIST` như `WideResearchCrawlSubgraph`.

- [ ] [Review][Patch] Worker race with manual pause/resume (medium) — `pause`/`resume` route không gửi signal hủy tới worker đang `blpop` 60s (`dsh_routes.py:475-546` vs `dsh_worker.py:941`); `resume_mission` bắt `Exception` quá rộng, `DshPayloadTooLargeError` bị đồng nhất 503.

- [ ] [Review][Patch] Redis socket timeout shorter than blpop timeout (medium) — `redis.blpop(result_key, timeout=60)` (`dsh_worker_browser_operator.py:72`) trên Redis client `socket_timeout=10` (`redis_client.py:38`), khiến `TimeoutError` sớm hơn 60s.

- [x] [Review][Patch] Extension chooses active tab instead of matching tab (low) — 2026-08-24: `_findMatchingTab` queries all tabs, matches by target URL hostname, falls back to active tab, and creates a new tab with the target URL if none exists.

- [ ] [Review][Patch] Fail-soft degradation missing (high) — Khi CDP attach/navigation thất bại, `_cdp_crawl_node` raise `RuntimeError` (`dsh_worker_browser_operator.py:81-82`), `_crawl_node` catch generic `Exception` và set `status="error"` (`dsh_worker_langgraph.py:236-249`). Không có clear degradation state hay graceful detach.

- [ ] [Review][Patch] CDP session token and lifecycle missing (medium) — `handleCdpCommand` attach/detach mỗi lệnh, không giữ session token, không lắng nghe `chrome.debugger.onDetach` (`cdp-bridge.ts:53-95`).

- [~] [Review][Patch] Tests are inadequate (medium) — 2026-08-24: Added `tests/unit/capabilities/test_browser_operator.py` covering success, human-takeover, extension error, and missing-user cases; updated `tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py` for `pubsub_numsub`; integration tests for pause/resume pass. Workspace/PAT scoping and extension E2E still need coverage.

- [x] [Review][Patch] Extension sendResult with null token / no retry (medium) — 2026-08-24: `_requireToken` checks `@plasmohq/storage` then `chrome.storage.local`; if no token, it logs and stops. `sendResult` retries up to 3 times with exponential backoff, stops on 401/403.

- [x] [Review][Patch] EventSource does not reconnect (medium) — 2026-08-24: `startListening` now uses `fetch` SSE body reader; on disconnect it schedules reconnection with capped exponential backoff up to 30s.

- [ ] [Review][Patch] Popup resume missing validation and error handling (low) — `popup.tsx:19-30` không kiểm tra token null, không validate `activeMissionId` là UUID, không báo lỗi khi backend reject; UI reset dù resume thất bại.

- [ ] [Review][Patch] Extension no onSuspend cleanup (medium) — `background/index.ts:7` bắt đầu nghe SSE khi load nhưng không đăng ký `chrome.runtime.onSuspend` để `stopListening()` và `detachDebugger`, gây leak khi extension bị suspend.

- [ ] [Review][Patch] `updated_at` mixes DB `func.now()` and Python `datetime.now(UTC)` (low) — `pause_mission`/`resume_mission` dùng `func.now()` (`dsh_routes.py:489`, `dsh_routes.py:517`) trong khi code khác dùng `datetime.now(UTC)`, có thể gây clock drift log.

- [ ] [Review][Patch] `cdp_result` list can bloat (low) — `cdp_result` dùng `rpush` mà không `ltrim` (`dsh_routes.py:467-470`), nhiều kết quả extension retry có thể làm list phình to.

## Re-review Findings — Code Review 2026-08-24

### Decision needed (đã quyết định)

- [x] [Review][Decision] Extension `debugger` permission scope — Giữ `debugger` vì CDP attach yêu cầu quyền này; `activeTab` không thay thế được. Viết note bảo mật trong manifest description và tài liệu rủi ro.
- [x] [Review][Decision] Backend URL fallback về `localhost` — Bỏ fallback localhost; `DEFAULT_BACKEND_BASE_URL` bắt buộc `PLASMO_PUBLIC_BACKEND_URL` được set khi build. Nếu thiếu, extension throw rõ ràng thay vì fallback về dev.
- [x] [Review][Decision] `mission_id` cho `browser_operator.execute` — Cho phép synthetic `mission_id` trong chat mode, nhưng embed `workspace_id` + `user_id` prefix để tránh collision và có audit trail tối thiểu.
- [x] [Review][Decision] Cơ chế verify challenge cleared khi resume — Lựa chọn (a): tin user bấm Resume trong popup. Bù lại, `resume_mission` verify lock owner = `auth.user.id` và xóa lock trong `finally`; thêm note rằng đây là MVP human-in-the-loop.

### Patch (đã áp dụng)

- [x] [Review][Patch] SSE stream subscription race condition (high) — `dsh_routes.py:426-471` dùng Redis SETNX lock `cdp:stream:lock:{user_id}` để đảm bảo 1 stream/user.
- [x] [Review][Patch] Command ID mismatch chỉ log warning (high) — `dsh_worker_browser_operator.py:145-151` raise `CdpExecutionError` thay vì xử lý stale result.
- [x] [Review][Patch] CDP endpoints chưa rate limit (high) — `dsh_routes.py:426-471` mỗi user chỉ 1 stream active qua lock; `cdp_result` đã redact + capping list.
- [x] [Review][Patch] Resume không validate lock ownership (high) — `dsh_routes.py:561-576` lưu `auth.user.id` trong takeover lock và verify khi resume.
- [x] [Review][Patch] Redis lock set sau DB commit (medium) — `dsh_routes.py:532-538` set takeover lock trước `session.commit()`.
- [x] [Review][Patch] Resume để lại orphaned lock khi publish fail (medium) — `dsh_routes.py:605-608` xóa lock trong `finally`.
- [x] [Review][Patch] Result key bị xóa trước khi publish, timeout không retry (medium) — `executor.py:77-84` bỏ `asyncio.wait_for` dư thừa, dùng `blpop` timeout.
- [x] [Review][Patch] Subscription check che giấu lỗi Redis thành human intervention (medium) — `dsh_worker_browser_operator.py:103-107` raise `CdpExecutionError` cho lỗi Redis.
- [x] [Review][Patch] Extension reconnection vô hạn (medium) — `cdp-bridge.ts:46-47,140-149` thêm `maxReconnectAttempts=10`.
- [x] [Review][Patch] Command queue trong extension không giới hạn (medium) — `cdp-bridge.ts:48,187-191` capping queue 20, drop oldest.
- [x] [Review][Patch] `sendResult` retry cả 4xx không retryable (low) — `cdp-bridge.ts:599-627` chỉ retry 5xx/429/network error.
- [x] [Review][Patch] `payload.result` type và truncation an toàn (low-medium) — `dsh_routes.py:506-510` thêm `isinstance(payload.result, dict)`; `cdp_result` redact PII trước khi lưu Redis.

### Patch vẫn còn mở

- [ ] [Review][Patch] PII redaction failure đánh dấu `<redaction_failed>` rồi tiếp tục (high) — `dsh_worker_browser_operator.py:55-57` cần quyết định behavior khi redaction service down (defer / fail / drop).
- [ ] [Review][Patch] Screenshot không giới hạn kích thước (medium) — `cdp-bridge.ts:512-520` cần cap dimension/quality.
- [ ] [Review][Patch] Không validate tab thuộc về user trước attach (medium) — `cdp-bridge.ts:212-230` cần ràng buộc matching tab URL rõ ràng hơn.

### Deferred (nợ kỹ thuật / cần story con)

- [x] [Review][Defer] Thiếu `HumanLiveTakeoverPopover` riêng và countdown 15:00 (AC-4) — deferred, chờ story 24.8b/UI.
- [x] [Review][Defer] Thiếu scheduler chuyển mission sang `aborted_timeout` sau 15 phút (AC-6) — deferred, cần Celery Beat job.
- [x] [Review][Defer] Không hoàn credits khi timeout (AC-6) — deferred, liên quan Epic 8/credit refund flow.
- [x] [Review][Defer] Không CDP session token lifecycle và `chrome.debugger.onDetach` listener (AC-1/Review Finding) — deferred, hiện attach/detach mỗi lệnh.
- [x] [Review][Defer] Thiếu audit log cho CDP commands (security) — deferred, cần design audit store.
- [x] [Review][Defer] Không có E2E extension tests (Review Finding) — deferred, cần Playwright + real extension/Chrome.
