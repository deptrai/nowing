---
story_key: "24-8"
epic: "epic-24"
story: "24.8"
title: "Browser Operator CDP Tool for DSH Crawl Subgraph & Human Live Takeover UI"
status: "ready-for-dev"
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
- **When** the agent invokes `dsh_browser_operator` tool,
- **Then** it executes standard CDP primitives:
  - `navigate(url)`: `Page.navigate` + waits for `Page.loadEventFired` or DOM stability.
  - `click(selector)`: Resolves DOM NodeId via `DOM.querySelector`, evaluates box model, and dispatches `Input.dispatchMouseEvent`.
  - `fill(selector, text)`: Focuses input, clears existing text, and dispatches `Input.dispatchKeyEvent`.
  - `scroll(direction, px)`: Dispatches synthetic mouse wheel event via `Input.dispatchMouseEvent`.
  - `extract(selector)`: Evaluates `Runtime.evaluate` to return sanitized text/HTML.
  - `take_screenshot()`: Dispatches `Page.captureScreenshot` (format: png/jpeg).

### AC-3 — Bot Challenge Detection & Mission Pause
- **Given** navigation or interaction triggers a Cloudflare Turnstile, reCAPTCHA v2/v3, or 2FA OTP prompt,
- **When** the DOM inspector detects challenge signatures (e.g. `cf-turnstile`, `recaptcha`, `otp-input`),
- **Then** the agent halts execution, sets mission state to `waiting_for_human`, records a checkpoint, and emits a notification event over SSE/WebSocket.

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

### 1. Backend: Browser Operator Service & Mission Endpoints (`nowing_backend`)
- [ ] Create `app/tasks/dsh_worker_browser_operator.py`:
  - Implement `BrowserOperatorService` with CDP command dispatchers (`navigate`, `click`, `fill`, `scroll`, `extract`, `screenshot`).
  - Implement challenge detector (`is_challenge_detected`).
- [ ] Add Mission Pause/Resume routes in `app/routes/dsh_mission_routes.py`:
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
uv run ruff check app/tasks/dsh_worker_browser_operator.py app/routes/dsh_mission_routes.py tests/unit/tasks/test_browser_operator.py
uv run pytest tests/unit/tasks/test_browser_operator.py -q
uv run pytest tests/integration/routes/test_dsh_mission_takeover.py -q

# Frontend typecheck & linter
cd ../nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/dsh/HumanLiveTakeoverPopover.tsx
```

### Review Findings

- [ ] [Review][Decision] {to be filled during review}
- [ ] [Review][Patch] {to be filled during review}
- [ ] [Review][Defer] {to be filled during review}
