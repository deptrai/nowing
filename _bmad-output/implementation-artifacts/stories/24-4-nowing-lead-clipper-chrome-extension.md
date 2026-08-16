---
story_key: "24-4"
epic: "epic-24"
story: "24.4"
title: "Nowing Lead Clipper — Chrome Extension for 1-Click Lead Capturing"
status: "done"
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

### Review Findings
- [x] [Review][Patch] Concurrency Race & IntegrityError Rollback on Duplicate Clipper Ingest [nowing_backend/app/routes/lead_clipper_routes.py:179]
- [x] [Review][Patch] Vietnamese Phone Normalization Leading-Zero Over-Prepend Bug (+8409...) [nowing_backend/app/routes/lead_clipper_routes.py:37]
- [x] [Review][Patch] Multi-Tenant client_id and Domain Propagation in Lead & VerifiedContact [nowing_backend/app/routes/lead_clipper_routes.py:199]
- [x] [Review][Patch] URL Canonicalization Ad Tracking Parameter Scrubbing & Scheme Sanitization [nowing_backend/app/routes/lead_clipper_routes.py:48]
- [x] [Review][Patch] Lead Context Payload Preservation (price/content to VerifiedContact.title) [nowing_backend/app/routes/lead_clipper_routes.py:213]

---

## Verification Commands

```bash
# Backend endpoint tests
cd nowing_backend
uv run ruff check app/routes/lead_clipper_routes.py tests/unit/routes/test_lead_clipper.py
uv run pytest tests/unit/routes/test_lead_clipper.py -q
uv run pytest tests/integration/routes/test_lead_clipper_ingest.py -q

# Extension build & test
cd ../nowing_web
pnpm tsc --noEmit
```
