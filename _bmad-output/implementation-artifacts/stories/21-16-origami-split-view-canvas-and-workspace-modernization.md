---
baseline_commit: 591bc6a16
---

# Story 21.16: Origami Split-View Canvas & Workspace Modernization

Status: done

<!-- Note: Governed by epics.md (FR-86, AD-31, UX-Contract-Lead-Panel) & DESIGN.md, EXPERIENCE.md -->

## Story

As a sales rep or market researcher working in a workspace,
I want an interactive 2-panel split canvas (a 420px Chat Co-pilot on the left and a Resizable Data Matrix on the right) with Mint Green theme, Sọc Caro grid paper styling, and bi-directional context sync,
So that I can naturally chat with AI to command scrapers while inspecting, filtering, sorting, and taking 1-click outreach actions on hundreds of real-time leads without losing screen context.

## Acceptance Criteria

1. **Given** navigation to `/dashboard/[workspace_id]/leads`, **When** the page loads, **Then** it renders a Split-View Canvas composed of:
   - **Left Panel (Chat Co-pilot):** Default width 420px (min 360px, max 650px) with interactive prompt box, Suggested Action Pills (`data-testid='suggested-action-pills'`), and 3-Mode Switcher (`🎯 Leads`, `🧠 Research`, `⚡ Scrapers`).
   - **Center Resizer:** Draggable vertical divider (`cursor: col-resize`, `hover:bg-emerald-400`, `role='slider'`) allowing fluid panel resizing, with a double-click reset to 50/50 (420px) and a 1-click collapse button.
   - **Right Panel (Live Data Matrix):** Resizable table with columns (Checkbox, Lead / Company, Source Badge, Decoded Phone, Fit Score, Actions: Zalo / Phone, Custom Fields), Table Virtualization, and Fullscreen Toggle.
2. **Given** the visual design tokens from `DESIGN.md`, **When** rendered, **Then** the canvas applies:
   - Primary Brand: Emerald & Mint Green (`#10B981`, `#059669`, subtle background `#ECFDF5`, border `#A7F3D0`).
   - Workbench Texture: Sọc Caro Grid Paper background (`20px x 20px` pattern `#F1F5F9`) in toolbar headers and empty state hero.
   - Typography Trio: `Instrument Serif` (Display headlines), `Plus Jakarta Sans` (Body & UI text), `JetBrains Mono` (Scores, Prices, Phone numbers).
3. **Given** new incoming leads from background scrapers, **When** pushed via Zero-cache (`zero.nowing.net`), **Then** rows stream into the active table in real-time ($< 100$ms) with a soft Mint Green shimmer animation (`.cell-pulse`) without layout shifts or page reloads.
4. **Given** bi-directional context synchronization:
   - **Table $\rightarrow$ Chat:** Clicking a lead row displays an active context badge in the chat composer (`[Đang chọn: Nguyễn Văn Hùng - Bán nhà Thủ Đức 8.5 Tỷ]`), automatically injecting the lead's metadata into subsequent AI prompts.
   - **Chat $\rightarrow$ Table:** When the AI filters, sorts, or adds leads, the table highlights the matching rows immediately.
5. **Given** multiple lead selection ($\ge 2$ checkboxes ticked in the table), **When** active, **Then** a Floating Bulk Action Bar slides up at the bottom: `[ Đã chọn N leads | 📱 Mở khóa SĐT | 🚀 Xuất Lark Base | 💬 Gửi Zalo hàng loạt | ✕ Bỏ chọn ]`.
6. **Given** clicking any lead row, **When** triggered, **Then** a Flyout Detail Drawer (width 480px) slides out from the right displaying: full listing text, parsed entities, fit score breakdown, and 1-click Zalo Deep-link (`zalo.me/{phone}`).
7. **Given** viewport width $< 1280$px, **When** rendered, **Then** the workspace sidebar auto-collapses to a 64px Icon Rail, preserving a minimum 750px width for the Data Matrix.

## Tasks / Subtasks

- [x] Task 1: Split-View Layout & Resizer Engine (AC: 1, 7)
  - [x] 1.1 Xây dựng `OrigamiSplitCanvas.tsx` tại `nowing_web/components/leads/OrigamiSplitCanvas.tsx` sử dụng custom drag hook & CSS clamp bounds.
  - [x] 1.2 Tích hợp nút Fullscreen Toggle mở rộng Data Matrix 100% width và nút thu gọn Left Chat Panel.
  - [x] 1.3 Xây dựng cơ chế Auto-Collapse Sidebar khi viewport $< 1280$px.
- [x] Task 2: Chat Co-pilot Panel & Mode Switcher (AC: 1, 2, 4)
  - [x] 2.1 Xây dựng `OrigamiChatCopilot.tsx` tại `nowing_web/components/leads/OrigamiChatCopilot.tsx` với header Sọc Caro Grid Paper.
  - [x] 2.2 Tích hợp 3-Mode Switcher (`🎯 Leads | 🧠 Research | ⚡ Scrapers`) lưu state trong Jotai atoms (`canvasModeAtom`).
  - [x] 2.3 Tích hợp `SuggestedActionPills` và Context Badge (`ActiveLeadContextBadge`) khi người dùng click chọn hàng trong bảng.
  - [x] 2.4 Hỗ trợ phím tắt `⌘K` (Tìm kiếm nhanh), `Enter` gửi, `Shift+Enter` xuống dòng.
- [x] Task 3: Live Data Matrix & Zero-Cache Reactive Grid (AC: 1, 2, 3, 5, 6)
  - [x] 3.1 Xây dựng `OrigamiLeadMatrix.tsx` tại `nowing_web/components/leads/OrigamiLeadMatrix.tsx` với responsive virtualized scroll container.
  - [x] 3.2 Tích hợp CSS animation `.cell-pulse` shimmer xanh mint khi có rows mới từ Zero-cache.
  - [x] 3.3 Tích hợp `MultiTableTabs` và `SendExportDropdown` trên thanh công cụ của Matrix.
  - [x] 3.4 Xây dựng `FloatingBulkActionBar.tsx` nổi ở đáy bảng khi tick chọn $\ge 2$ leads.
  - [x] 3.5 Xây dựng `LeadDetailFlyoutDrawer.tsx` trượt từ cạnh phải khi nhấp vào hàng lead.
- [x] Task 4: Page Integration & Design Tokens (AC: 1, 2)
  - [x] 4.1 Cập nhật `nowing_web/app/dashboard/[workspace_id]/leads/page.tsx` render `OrigamiSplitCanvas`.
  - [x] 4.2 Định nghĩa CSS Tokens cho Sọc Caro Grid Paper (`.soc-caro-grid`) và Mint Green variables trong `globals.css`.
- [x] Task 5: Testing & Quality Gates (AC: 1-7)
  - [x] 5.1 Typecheck & Biome check: `pnpm tsc --noEmit` & `pnpm exec biome check` (0 errors).
  - [x] 5.2 Playwright E2E test: `nowing_web/tests/leads/split-canvas.spec.ts` (Kiểm thử kéo resizer, chuyển 3-Mode, tick checkbox hiện floating bar, mở detail drawer).

### Review Findings (AI Adversarial Review - Resolved)
- [x] [Review][Patch] Fix Resizer Drag Offset Coordinate calculation via `containerRef.current.getBoundingClientRect().left` [`OrigamiSplitCanvas.tsx`]
- [x] [Review][Patch] Fix Table Select All logic `isAllSelected` with `leads.every` [`OrigamiLeadMatrix.tsx`]
- [x] [Review][Patch] Reset cross-workspace selection and context atoms on unmount/workspaceId switch [`OrigamiSplitCanvas.tsx`]
- [x] [Review][Patch] Increase `FloatingBulkActionBar` z-index to `z-[60]` for Fullscreen mode visibility [`FloatingBulkActionBar.tsx`]
- [x] [Review][Patch] Fix unmounted `setTimeout` memory leak with `timerRef` in `OrigamiChatCopilot.tsx`
- [x] [Review][Patch] Fix prompt string template formatting to avoid dangling hyphens [`OrigamiChatCopilot.tsx`]
- [x] [Review][Patch] Fix Fit Score null handling ("Chờ chấm") & price fallback [`OrigamiLeadMatrix.tsx`]
- [x] [Review][Patch] Add a11y attributes `role="dialog"`, `aria-modal="true"`, safe `tel:` check [`LeadDetailFlyoutDrawer.tsx`]

## Dev Agent Record

### Implementation Plan
1. Xây dựng State Management qua Jotai Atoms (`leads-canvas.atoms.ts`) quản lý panel width, active mode, selected lead context, multi-select array, và drawer visibility.
2. Xây dựng bộ component Origami Leads Canvas:
   - `OrigamiSplitCanvas.tsx`: Khung điều khiển 2 panel với center resizer divider mượt mà, hỗ trợ bàn phím (`role="slider"`), reset 420px, fullscreen toggle.
   - `OrigamiChatCopilot.tsx`: Left AI Copilot panel với Sọc Caro Grid Paper, 3-Mode Switcher, Suggested Action Pills, context badge.
   - `OrigamiLeadMatrix.tsx`: Right Live Data Matrix với bảng dữ liệu leads, Fit Score badge phân cực, Zalo Outreach, Company Graph trigger.
   - `FloatingBulkActionBar.tsx`: Floating action bar nổi ở đáy khi chọn $\ge 2$ leads.
   - `LeadDetailFlyoutDrawer.tsx`: Flyout drawer 480px hiển thị chi tiết lead, score breakdown, contact, report invalid phone.
3. Thiết lập Design Tokens CSS trong `globals.css` cho `.soc-caro-grid` (Grid paper 20px x 20px) và `.cell-pulse` shimmer.
4. Cập nhật `nowing_web/app/dashboard/[workspace_id]/leads/page.tsx` tích hợp `OrigamiSplitCanvas`.

### Completion Notes
- Tất cả 5 Tasks và 13 Subtasks đã hoàn thành 100%.
- Adversarial Code Review 3 lớp (Blind Hunter, Edge Case Hunter, Acceptance Auditor) đã rà soát và toàn bộ 8 findings đã được vá triệt để.
- 16/16 Unit Tests pass (`nowing_web/components/leads/__tests__/*.test.ts`).
- `pnpm tsc --noEmit` đạt 0 lỗi (Exit code 0).
- `pnpm exec biome check` đạt 0 lỗi, 0 cảnh báo.
- ATDD Checklist hoàn tất tại `_bmad-output/test-artifacts/atdd-checklist-21-16.md`.

## File List
- `nowing_web/components/leads/OrigamiSplitCanvas.tsx` (New)
- `nowing_web/components/leads/OrigamiChatCopilot.tsx` (New)
- `nowing_web/components/leads/OrigamiLeadMatrix.tsx` (New)
- `nowing_web/components/leads/FloatingBulkActionBar.tsx` (New)
- `nowing_web/components/leads/LeadDetailFlyoutDrawer.tsx` (New)
- `nowing_web/atoms/leads/leads-canvas.atoms.ts` (New)
- `nowing_web/components/leads/__tests__/OrigamiSplitCanvas.test.ts` (New)
- `nowing_web/tests/leads/split-canvas.spec.ts` (New)
- `nowing_web/app/dashboard/[workspace_id]/leads/page.tsx` (Modified)
- `nowing_web/app/globals.css` (Modified)
- `_bmad-output/test-artifacts/atdd-checklist-21-16.md` (New)

## Change Log
- 2026-08-16: Hoàn tất triển khai Story 21.16: Origami Split-View Canvas & Workspace Modernization với đầy đủ ATDD test scaffold, component split-view, bi-directional context sync, bulk action bar, flyout drawer, và design tokens.
- 2026-08-16: Áp dụng 8 review patches từ Adversarial Code Review (tọa độ resizer, logic isAllSelected, cleanup tenant state, z-index fullscreen, timer memory leak, a11y, safe tel).

## Dev Notes

- **Zero Layout Shift:** Draggable divider sử dụng GPU-accelerated CSS transform để duy trì 60fps khi kéo thả.
- **Table Virtualization:** Đảm bảo render mượt mà khi bảng có $\ge 1,000$ leads mà không tốn RAM trình duyệt.
- **Bi-directional Sync:** Sử dụng React Context hoặc Jotai Atoms (`selectedLeadContextAtom`, `selectedLeadIdsAtom`) để kết nối tức thì giữa Chat Panel và Data Matrix.

### References
- [Architecture Spine: epic21-architecture-update.md (AD-31)]
- [UX Design: DESIGN.md, EXPERIENCE.md]
- [Mockup: _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/mockups/workspace-lead-intelligence.html]
