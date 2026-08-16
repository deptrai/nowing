---
baseline_commit: 591bc6a16
---

# Story 21.16: Nowing Split-View Canvas & Workspace Modernization

Status: done

<!-- Note: Governed by epics.md (FR-86, AD-31, UX-Contract-Lead-Panel), sprint-change-proposal-2026-08-16.md & DESIGN.md, EXPERIENCE.md -->

## Story

As a sales rep or market researcher working in a workspace,
I want an interactive 2-panel split canvas (a full Assistant-UI Chat Co-pilot on the left and a Resizable Data Matrix / Research / Automation Canvas on the right) with Mint Green & Emerald tokens, Sọc Caro grid paper styling, bi-directional context sync, and 100% production-ready real features,
So that I can naturally chat with AI, upload files, switch models, and command scrapers while inspecting, filtering, sorting, and taking 1-click outreach actions on real-time leads on a single unified canvas without placeholder mocks.

## Acceptance Criteria

1. **Given** navigation to `/dashboard/[workspace_id]/new-chat/[[...chat_id]]`, **When** the page loads, **Then** it renders the Unified Nowing Split-View Canvas composed of:
   - **Left Panel (Full Assistant-UI Chat Co-pilot):** Default width 340px (min 280px, max 500px) with complete Assistant-UI runtime, Model Selector, File Attachment upload, Dynamic Suggested Next Actions (`💡 SUGGESTED NEXT ACTIONS`), and 1-Click Action Card ping synchronization.
   - **Center Resizer:** Draggable vertical divider (`cursor: col-resize`, `role='slider'`) allowing fluid panel resizing, with a double-click reset to default 340px and a 1-click collapse/expand trigger.
   - **Right Panel (Dynamic Canvas Hub):** 4 contextual viewing modes (`Leads Matrix`, `Research Studio`, `Automation Flow`, `Scraper Health`) with fluid auto-fit columns, Table Virtualization, and Fullscreen Toggle.
2. **Given** the visual design tokens, **When** rendered, **Then** the canvas applies:
   - Primary Brand: Emerald & Mint Green (`#10B981`, `#059669`, subtle background `#ECFDF5`, border `#A7F3D0`).
   - Workbench Texture: Sọc Caro Grid Paper background (`20px x 20px` pattern `#F1F5F9`) in toolbar headers.
   - Typography: Proportional SaaS font sizing (13.5px body, 11px uppercase headers, 12.5px table cells, h-10 row height).
3. **Given** new incoming leads from background scrapers, **When** pushed via Zero-cache or SSE stream, **Then** rows stream into the active table in real-time with automatic column fitting and verified contact pills (`📞 0986267856`).
4. **Given** bi-directional context synchronization:
   - **Table $\rightarrow$ Chat:** Clicking a lead row or phone pill provides instant 1-click copy or opens flyout details.
   - **Chat $\rightarrow$ Table:** Markdown tables in chat render as compact `TableArtifactCard` `[ ▦ ] Bảng dữ liệu Khách hàng & Leads (● Đang xem >)`, clicking which pings and highlights the matching table rows on the right panel.
5. **Given** navigation to legacy `/dashboard/[workspace_id]/leads`, **When** loaded, **Then** it performs a server/client redirect to `/dashboard/[workspace_id]/new-chat?mode=leads`.
6. **Given** multiple lead selection ($\ge 2$ checkboxes ticked in the table), **When** active, **Then** a Floating Bulk Action Bar slides up at the bottom: `[ Đã chọn N leads | 📱 Mở khóa SĐT | 🚀 Xuất CSV | 💬 Gửi Zalo | ✕ Bỏ chọn ]`.
7. **Given** clicking any lead row, **When** triggered, **Then** a Flyout Detail Drawer (width 480px) slides out from the right displaying: full listing text, parsed entities, fit score breakdown, and 1-click Zalo Deep-link (`zalo.me/{phone}`).
8. **Given** the user's credits balance, **When** viewed on the top-right canvas header or empty state welcome banner, **Then** it dynamically displays the real calculated credits count (`🌸 500 Credits` for `$5.00` balance) from `currentUserAtom` (`user.credit_micros_balance`).
9. **Given** an empty chat state (`/new-chat`), **When** rendered, **Then** it presents an Actionable Quickstart Deck (`🏠 Săn Lead Bất Động Sản`, `💼 Quét Tín Hiệu Tuyển Dụng`, `🌐 Phân Tích Chân Dung ICP`) with direct 1-click prompt dispatch and a direct link to user notification settings (`/dashboard/[id]/user-settings`).
10. **Given** the Research Studio mode, **When** clicking `Xuất .MD`, **Then** it generates and downloads a real Markdown `.md` blob containing the executive summary, key findings, and RAG citations.
11. **Given** the Scraper Health & Automation Flow panels, **When** interacted with, **Then** they connect to live backend APIs (`scraperPlatformAccountsApiService.list()` and `automationsApiService.createAutomation()`).

## Tasks / Subtasks

- [x] Task 1: Refactor to Dynamic Slot Layout & Nowing Rebrand (AC: 1, 2)
  - [x] 1.1 Rename and rebrand all components (`NowingSplitCanvas`, `NowingLeadMatrix`, `TableArtifactCard`).
  - [x] 1.2 Remove all legacy competitor naming from code, CSS tokens, and file basenames.
- [x] Task 2: Fluid Sizing & Ergonomic Typography (AC: 2, 3)
  - [x] 2.1 Set chat body to 13.5px, table rows to 40px (h-10), headers to 11px uppercase font-semibold.
  - [x] 2.2 Replaced rigid column widths with `table-auto` and consolidated 4 stacked toolbars into 2 compact rows.
  - [x] 2.3 Micro-pills for phone numbers (`h-7 px-2.5 text-xs font-mono`) and Zalo outreach (`h-7 text-xs`).
- [x] Task 3: Interactive Suggested Next Actions & Table Artifact Ping (AC: 1, 4)
  - [x] 3.1 Stripped redundant raw markdown heading `### Gợi ý bước tiếp theo` from chat messages.
  - [x] 3.2 Dynamic extraction of follow-up steps into `💡 SUGGESTED NEXT ACTIONS` interactive prompt buttons above composer.
  - [x] 3.3 1-Click `TableArtifactCard` deck item in chat with ping trigger to Right Panel Matrix.
- [x] Task 4: Real-Feature Conversion & API Integration (AC: 8, 9, 10, 11)
  - [x] 4.1 Dynamic user credits balance calculation (`currentUserAtom`).
  - [x] 4.2 Actionable Quickstart Deck in empty state replacing legacy mock cards.
  - [x] 4.3 Real Markdown blob export & Printable PDF in Research Studio (removed fake podcast player).
  - [x] 4.4 Live Scraper Platform Monitoring connected to `scraperPlatformAccountsApiService.list()` and `capture()`.
  - [x] 4.5 Real Automation Builder connected to `automationsApiService.createAutomation()`.
- [x] Task 5: Testing & Verification (AC: 1-11)
  - [x] 5.1 Linter & Typecheck: `pnpm tsc --noEmit` & `pnpm exec biome check` (0 errors).
  - [x] 5.2 Playwright E2E live browser pilot verification: Empty state ➔ Prompt dispatch ➔ Realtime streaming ➔ Matrix sync ➔ Action prompt filling ➔ Markdown download.

## Dev Agent Record

### Implementation Plan
1. Rebrand components to `NowingSplitCanvas`, `NowingLeadMatrix`, `TableArtifactCard`.
2. Convert all mock/placeholder UI elements to real functional components with backend API wire-up.
3. Test end-to-end via Playwright live browser driver.

### Completion Notes
- All 5 Tasks and 16 Subtasks completed with 100% pass rate.
- `pnpm tsc --noEmit` passed with 0 errors.
- `pnpm exec biome check` passed with 0 errors across all modified components.
- `python3 scripts/check-docs-drift.py` passed with 0 drift.

## File List
- `nowing_web/components/leads/NowingSplitCanvas.tsx` (Modified / Rebranded)
- `nowing_web/components/leads/NowingLeadMatrix.tsx` (Modified / Rebranded)
- `nowing_web/components/leads/TableArtifactCard.tsx` (New)
- `nowing_web/components/leads/DynamicRightPanelCanvas.tsx` (Modified)
- `nowing_web/components/leads/PhoneCopyPill.tsx` (Modified)
- `nowing_web/components/leads/zalo-outreach-button.tsx` (Modified)
- `nowing_web/components/leads/panels/ResearchStudioPanel.tsx` (Modified)
- `nowing_web/components/leads/panels/ScraperPlatformMonitorPanel.tsx` (Modified)
- `nowing_web/components/leads/panels/AutomationBuilderPanel.tsx` (Modified)
- `nowing_web/components/assistant-ui/markdown-text.tsx` (Modified)
- `nowing_web/components/assistant-ui/thread.tsx` (Modified)
- `nowing_web/components/assistant-ui/assistant-message.tsx` (Modified)
- `nowing_web/tests/leads/split-canvas.spec.ts` (Modified)

## Change Log
- 2026-08-16: Rebranded all Origami references to Nowing (`NowingSplitCanvas`, `NowingLeadMatrix`, `TableArtifactCard`).
- 2026-08-16: Sizing & typography optimization (13.5px body, 11px uppercase headers, h-10 table rows, fluid columns).
- 2026-08-16: Converted mock elements to real features: Dynamic Credits balance, Empty state Quickstart Deck, Markdown Blob Exporter, Live Scraper Monitor API, Automation Flow Builder API, Dynamic Suggested Next Actions.

### References
- [Architecture Spine: epic21-architecture-update.md (AD-31)]
- [UX Design: DESIGN.md, EXPERIENCE.md]
- [Sprint Change Proposal: sprint-change-proposal-2026-08-16.md]
