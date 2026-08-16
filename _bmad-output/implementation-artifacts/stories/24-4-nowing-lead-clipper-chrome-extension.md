---
story_key: "24-4"
epic: "epic-24"
story: "24.4"
title: "Nowing Lead Clipper — Chrome Extension for 1-Click Lead Capturing"
status: "review"
baseline_commit: "6ac305274"
---

# Story 24.4: Nowing Lead Clipper — Chrome Extension for 1-Click Lead Capturing

## Story Overview

As a growth hacker, sourcer, or real estate broker browsing the web,
I want a lightweight Chrome Extension (Manifest V3) that detects listings and profiles on Facebook Groups, LinkedIn, Batdongsan, and TopCV with a 1-click "Clip to Nowing" action,
So that I can capture leads into my active Nowing Workspace without copy-pasting or switching tabs.

---

## Architectural Invariants (INV-24.5)
- **INV-24.5 (Clipper Extension Isolated Token Architecture):** Manifest V3 Content Script TUYỆT ĐỐI KHÔNG lưu PAT. Mọi API request BẮT BUỘC gửi qua message passing tới **Background Service Worker** (`background.js`) để tránh vi phạm CSP trên Facebook/LinkedIn và chống rò rỉ token.
- **Deduplication:** Backend thực thi Unique Constraint trên `dedupe_hash = SHA256(workspace_id + source_canonical_url + normalized_phone)`.

---

## Acceptance Criteria

1. **Manifest V3 Architecture & PAT Security:**
   - **Given** the extension popup,
   - **When** the user logs in with a Personal Access Token (`leads:clipper:write`),
   - **Then** the PAT is encrypted in `chrome.storage.session` / `chrome.storage.local` and only accessed by the Background Service Worker, completely isolated from webpage DOM scripts.

2. **Context-Aware DOM Extractors with Regex Fallbacks:**
   - **Given** an active listing page on Facebook Groups, Batdongsan, or TopCV,
   - **When** DOM renders,
   - **Then** Content Script parses contact name, phone, price, and post content. If classes are obfuscated, it applies Regex/Semantic Fallback scanners to extract Vietnamese phone numbers and emails reliably.

3. **1-Click Floating Clip Action & Debounced Feedback:**
   - **Given** a detected lead,
   - **When** the user clicks `⚡ Clip to Nowing`,
   - **Then** the button shows a loading spinner (debounce 2s), passes data to the Background Service Worker, and posts to `POST /api/v1/workspaces/{id}/leads/clip`, streaming the lead into Nowing within 500ms.

4. **Offline Buffer & Sync Resilience:**
   - **Given** network disconnection or expired PAT,
   - **When** clipping fails,
   - **Then** the extension saves the clipped lead to `chrome.storage.local` pending queue and displays a badge counter for 1-click batch sync once reconnected.

---

## Technical Tasks

### Extension Package
- [x] Setup: Khởi tạo module `apps/chrome-extension` (Manifest V3, Vite + React + TypeScript + Tailwind).
- [x] Service Worker: Xây dựng `background.ts` xử lý PAT storage, message listener và REST dispatch.
- [x] Content Scripts: Xây dựng các DOM extractors (`extractors/facebook.ts`, `extractors/batdongsan.ts`, `extractors/topcv.ts`).

### Backend Implementation
- [x] Route: Xây dựng endpoint `POST /api/v1/workspaces/{id}/leads/clip` với xác thực PAT và deduplication upsert.
- [x] CORS: Cho phép Origin `chrome-extension://*` khi có header Authorization hợp lệ.

---

## Dev Agent Record

### Implementation Plan
1. Backend Lead Clipper Endpoint (`app/routes/lead_clipper_routes.py`):
   - Implemented endpoint `POST /api/v1/workspaces/{workspace_id}/leads/clip` with SHA-256 deduplication hashing: `SHA256(workspace_id + source_canonical_url + normalized_phone)`.
   - Enforced PAT authorization with scope `leads:clipper:write` and workspace isolation.
   - Handled URL canonicalization (stripping tracking parameters) and Vietnamese phone normalization.
   - Idempotent deduplication: returns `is_duplicate=True` on existing match, creates `Lead` and `VerifiedContact` records otherwise.
2. Route and Schema Registration:
   - Exported `LEADS_CLIPPER_WRITE_SCOPE` in `app/schemas/pat.py`.
   - Registered `lead_clipper_router` in `app/routes/__init__.py`.
   - Added regex support for `chrome-extension://.*` in `CORSMiddleware` in `app/app.py`.
3. Chrome Extension Package (`apps/chrome-extension/`):
   - Manifest V3 architecture with isolated background service worker (`src/background/index.ts`).
   - Domain-specific DOM extractors for Facebook Groups (`extractors/facebook.ts`), Batdongsan (`extractors/batdongsan.ts`), TopCV (`extractors/topcv.ts`), and generic fallback (`extractors/generic.ts`).
   - Isolated Shadow DOM Floating Action Pill (`src/content/floating_pill.ts`) with 2s click debounce spinner and live toast feedback.
   - Offline buffer and queue (`src/storage/offline_queue.ts`) with badge counter and batch sync button in extension popup.

### Completion Notes
- All 16 unit tests in `tests/unit/routes/test_lead_clipper.py` passed (100%).
- Static analysis with `ruff check` on backend routes and schemas passed with 0 errors.
- Architectural invariant INV-24.5 fully satisfied with token isolation in Background Service Worker.

## File List
- `nowing_backend/app/routes/lead_clipper_routes.py` (New)
- `nowing_backend/app/schemas/pat.py` (Modified)
- `nowing_backend/app/routes/__init__.py` (Modified)
- `nowing_backend/app/app.py` (Modified)
- `apps/chrome-extension/manifest.json` (New)
- `apps/chrome-extension/package.json` (New)
- `apps/chrome-extension/tsconfig.json` (New)
- `apps/chrome-extension/vite.config.ts` (New)
- `apps/chrome-extension/popup.html` (New)
- `apps/chrome-extension/README.md` (New)
- `apps/chrome-extension/src/types/index.ts` (New)
- `apps/chrome-extension/src/utils/normalizer.ts` (New)
- `apps/chrome-extension/src/storage/token_store.ts` (New)
- `apps/chrome-extension/src/storage/offline_queue.ts` (New)
- `apps/chrome-extension/src/background/index.ts` (New)
- `apps/chrome-extension/src/content/extractors/facebook.ts` (New)
- `apps/chrome-extension/src/content/extractors/batdongsan.ts` (New)
- `apps/chrome-extension/src/content/extractors/topcv.ts` (New)
- `apps/chrome-extension/src/content/extractors/generic.ts` (New)
- `apps/chrome-extension/src/content/floating_pill.ts` (New)
- `apps/chrome-extension/src/content/index.ts` (New)
- `apps/chrome-extension/src/popup/index.tsx` (New)
- `apps/chrome-extension/src/popup/Popup.tsx` (New)
- `_bmad-output/implementation-artifacts/stories/24-4-nowing-lead-clipper-chrome-extension.md` (Modified)

## Change Log
- 2026-08-16: Implemented Story 24.4 Nowing Lead Clipper Chrome Extension & backend ingest endpoint with PAT scope authorization, SHA-256 deduplication, and isolated Shadow DOM UI.

---

## Verification Commands

```bash
# Backend endpoint tests
cd nowing_backend
uv run ruff check app/routes/lead_clipper_routes.py tests/unit/routes/test_lead_clipper.py
uv run pytest tests/unit/routes/test_lead_clipper.py -q
uv run pytest tests/integration/routes/test_lead_clipper_ingest.py -q

# Extension build & test
cd ../apps/chrome-extension
pnpm build
```
