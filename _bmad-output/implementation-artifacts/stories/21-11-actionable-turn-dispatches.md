---
baseline_commit: 2fc8cf396635cae2ac73c7d0e38a5353b65e565b
---

# Story 21.11: Actionable Turn Dispatches (Suggested Action Pills)

Status: done

<!-- Note: Governed by epic21-architecture-update.md (AD-31 to AD-49) & ux-contract-lead-intelligence-panel.md -->

## Story

As an active user in the split-view chat interface,
I want AI responses to include contextual 1-click execution chips (Suggested Action Pills),
So that I can advance lead workflows (decode numbers, trigger Zalo drafts, find similar leads, export tables) with zero typing friction.

## Acceptance Criteria

1. **Given** any discovery, research, or scraper chat turn completion, **When** `ChatOrchestrator` emits the final SSE response stream, **Then** it appends a structured SSE event `data-suggested-actions`: JSON array of `{ id: string, label: string, icon: string, action_type: string, prompt_template: string, cost_credits?: number, payload?: Record<string, any> }` (maximum 3 pills).
2. **Given** action pills rendered directly below the assistant chat message bubble, **When** user clicks a pill (e.g. `[ 📱 Giải mã 9 SĐT (13.5 credits) ]`), **Then** the frontend dispatches the linked action immediately into the active chat session without requiring user re-typing.
3. **Given** an action dispatch execution, **When** table rows are updated or inserted via Zero-cache (`zero.nowing.net`), **Then** newly affected cells flash a brief green pulse highlight (`@keyframes pulse-highlight 1s ease-out`).
4. **Given** a lead table state with 0 selected rows vs. $N$ selected rows, **When** the AI suggests actions, **Then** pill labels and payload dynamically reflect the exact selection count and credit projection (e.g. `1.5 credits * N`).
5. **Given** keyboard navigation, **When** user presses `Alt + 1`, `Alt + 2`, or `Alt + 3`, **Then** the corresponding suggested action pill is triggered.

## Tasks / Subtasks

- [x] Task 1: Backend Schemas & SSE Event Emitter (AC: 1, 4)
  - [x] 1.1 Thêm schema `SuggestedAction` và `SuggestedActionList` vào `nowing_backend/app/schemas/new_chat.py`.
  - [x] 1.2 Mở rộng `ChatOrchestrator` tại `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` để sinh và stream SSE event `data-suggested-actions`.
  - [x] 1.3 Cấu hình rule-based & LLM fallback generator cho các action templates phổ biến (`decode_phones`, `zalo_draft`, `find_similar`, `export_csv`, `deep_research`).
- [x] Task 2: Frontend Types & Zod Schemas (AC: 1)
  - [x] 2.1 Cập nhật `nowing_web/contracts/types/chat-messages.types.ts` với `suggestedActionSchema` và `SuggestedAction` interface.
  - [x] 2.2 Đảm bảo type safety khi parse SSE stream chunks trong `nowing_web/lib/chat/stream-pipeline.ts` và `streaming-state.ts`.
- [x] Task 3: UI Components & Keyboard Shortcuts (AC: 2, 5)
  - [x] 3.1 Xây dựng component `nowing_web/components/chat/suggested-action-pills.tsx` với styling Mint Green (`#ECFDF5` border `#A7F3D0` hover `#D1FAE5`).
  - [x] 3.2 Tích hợp component vào `nowing_web/components/assistant-ui/assistant-message.tsx` ngay dưới message content.
  - [x] 3.3 Đăng ký shortcut listener (`Alt + 1..3`) kích hoạt click event trên pill tương ứng.
- [x] Task 4: Action Dispatcher & Zero-cache Cell Pulse Animation (AC: 2, 3)
  - [x] 4.1 Xây dựng hook `useSuggestedActionDispatch` tại `nowing_web/lib/hooks/use-suggested-action-dispatch.ts` gửi prompt hoặc gọi REST endpoint.
  - [x] 4.2 Thêm CSS keyframe animation `pulse-highlight` vào `nowing_web/app/globals.css`:
    ```css
    @keyframes pulse-highlight {
      0% { background-color: rgba(16, 185, 129, 0.25); }
      100% { background-color: transparent; }
    }
    .cell-pulse { animation: pulse-highlight 1.2s ease-out; }
    ```
  - [x] 4.3 Gắn trigger class `.cell-pulse` vào các cell của bảng `LeadCard` khi nhận được ID row cập nhật qua Zero-cache / action dispatch.
- [x] Task 5: Testing & Verification (AC: 1-5)
  - [x] 5.1 Unit tests backend: `tests/unit/tasks/chat/test_suggested_actions_generator.py`.
  - [x] 5.2 Unit tests frontend: `nowing_web/components/chat/__tests__/suggested-action-pills.test.ts`.
  - [x] 5.3 Type check & linting checks: `ruff check` và `tsc --noEmit` & `biome check` đều 100% PASS.

### Review Findings

- [x] [Review][Patch] Keyboard shortcut collision guard for form inputs/textareas/dialogs [nowing_web/components/chat/suggested-action-pills.tsx:54-77]
- [x] [Review][Patch] Synchronous re-entrancy lock & isRunning check on action dispatch [nowing_web/lib/hooks/use-suggested-action-dispatch.ts:18-36]
- [x] [Review][Patch] Module-level compiled regex with VN operator prefixes & flexible masking symbols [nowing_backend/app/services/chat/suggested_actions_generator.py:16-23]
- [x] [Review][Patch] Floating-point rounding & format for credit cost projection [nowing_backend/app/services/chat/suggested_actions_generator.py:84-113]

## Dev Notes

- **Design Tokens:** Dùng chuẩn màu Mint Green `var(--color-primary-subtle)` (`#ECFDF5`) và `var(--color-primary)` (`#10B981`) từ `DESIGN.md`.
- **Zero-Cache Sync:** Không trigger full table re-render; chỉ cập nhật mutation state trên từng Row ID để giữ hiệu năng 60fps.
- **Maximum 3 Pills:** Luôn giới hạn tối đa 3 pills để không làm loãng giao diện và giảm cognitive load (theo nguyên tắc "Less, but better").

### References
- [Architecture Spine: epic21-architecture-update.md]
- [UX Design: _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/DESIGN.md]
- [UX Experience: _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/EXPERIENCE.md]
- [Mockup: _bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/mockups/workspace-lead-intelligence.html]

## Dev Agent Record

### Implementation Plan
- T1: Định nghĩa schema `SuggestedAction` và `SuggestedActionList` trong `nowing_backend/app/schemas/new_chat.py`. Xây dựng module sinh gợi ý hành động (`suggested_actions_generator.py`) và tích hợp vào SSE pipeline của `ChatOrchestrator` (`data-suggested-actions`).
- T2: Định nghĩa TypeScript interface & Zod schema cho `SuggestedAction` ở frontend (`chat-messages.types.ts`), handle SSE stream chunk `data-suggested-actions` trong `streaming-state.ts` và `stream-pipeline.ts`.
- T3: Xây dựng UI component `SuggestedActionPills`, phím tắt `Alt+1/2/3`, tích hợp vào assistant message bubble trong `assistant-message.tsx`.
- T4: Triển khai hook `useSuggestedActionDispatch` và CSS `.cell-pulse` animation cho Zero-cache table highlight trong `globals.css` và `LeadCard.tsx`.
- T5: Viết Unit tests & linting/typecheck đầy đủ (backend pytest, frontend tsc & biome check).

### Completion Notes
- Backend: Tạo schema `SuggestedAction` và `SuggestedActionList`, generator `generate_suggested_actions` tự động phân tích turn context (tools, keywords, selection count $N$ với $1.5 \times N$ credits projection) và stream SSE event `data-suggested-actions` (max 3 pills).
- Frontend: Cập nhật `chat-messages.types.ts`, `streaming-state.ts`, `stream-pipeline.ts`, `engine.ts` để nhận và lưu trữ `data-suggested-actions`.
- UI & Shortcuts: Tạo component `SuggestedActionPills` với style Mint Green, phím tắt `Alt+1`, `Alt+2`, `Alt+3` tự động dispatch prompt vào phiên chat hiện tại.
- Zero-Cache Highlight: Thêm `@keyframes pulse-highlight` và class `.cell-pulse` vào `globals.css`, kích hoạt hiệu ứng pulse trên card/row khi có action dispatch.
- Verification: 146/146 pytest tests pass, `ruff check` sạch, `pnpm tsc --noEmit` và `pnpm exec biome check` sạch 100%.

## File List
- `nowing_backend/app/schemas/new_chat.py`
- `nowing_backend/app/schemas/__init__.py`
- `nowing_backend/app/services/chat/suggested_actions_generator.py`
- `nowing_backend/app/services/new_streaming_service.py`
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py`
- `nowing_backend/app/tasks/chat/streaming/flows/resume_chat/orchestrator.py`
- `nowing_backend/app/tasks/chat/streaming/flows/shared/finalize_emit.py`
- `nowing_backend/tests/unit/tasks/chat/test_suggested_actions_generator.py`
- `nowing_web/contracts/types/chat-messages.types.ts`
- `nowing_web/lib/chat/streaming-state.ts`
- `nowing_web/lib/chat/stream-pipeline.ts`
- `nowing_web/lib/chat/stream-engine/engine.ts`
- `nowing_web/lib/hooks/use-suggested-action-dispatch.ts`
- `nowing_web/components/chat/suggested-action-pills.tsx`
- `nowing_web/components/assistant-ui/assistant-message.tsx`
- `nowing_web/components/leads/LeadCard.tsx`
- `nowing_web/components/chat/__tests__/suggested-action-pills.test.ts`
- `nowing_web/app/globals.css`

## Change Log
- 2026-08-15: Hoàn thành toàn bộ các tasks của Story 21.11 (Actionable Turn Dispatches). Chuyển trạng thái sang `review`.
- 2026-08-15: Hoàn thành code review BMAD, áp dụng 4 patches an toàn (keyboard focus guard, async re-entrancy lock & isRunning check, regex hardening, floating point formatting). Chuyển trạng thái sang `done`.
