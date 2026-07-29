---
title: Sprint Change Proposal — Nowing (2026-07-22)
description: ''
createdAt: '2026-07-28T12:47:48.325Z'
updatedAt: '2026-07-28T15:17:33.319Z'
tags:
  - bmad
  - bmad-source-bmad-output-planning-artifacts-sprint-change-proposal-2026-07-22-md
---

# Sprint Change Proposal — Nowing (2026-07-22)

**Workflow:** `bmad-correct-course`  
**Project:** Nowing  
**Date:** 2026-07-22  
**Author:** AI-assisted planning  
**Affected artifacts:**
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md`
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`

---

## 1. Issue Summary

Các tài liệu công khai (README, landing page) và một số planning artifacts cũ mô tả Nowing với các tính năng không còn tồn tại hoặc chưa được implement trong code:

- **RBAC “Admin” role** đã bị xóa ở migration 72 (`72_simplify_rbac_roles.py`) nhưng README vẫn ghi “Owner/Admin/Editor/Viewer”.
- **AI File Sorting** đã bị gỡ bỏ ở migration 172 (`172_remove_ai_file_sort.py`) nhưng README vẫn ghi “AI file sorting auto-organizes documents...”.
- **Automation direct write-back** đến Notion/Slack/Linear/Jira chưa có dưới dạng action type; chỉ có `agent_task` trong `app/automations/actions/builtin/`. Agent vẫn có thể viết lại qua agent tools, nhưng không có action chuyên dụng.
- **Citation click** trong chat mở citation panel highlight chunk, nhưng mở full document editor không scroll/highlight đoạn snippet tương ứng (`editorPanelAtom` không có `chunkId`).
- **Per-workspace MCP tool enable/disable toggle** chưa tồn tại; MCP server expose toàn bộ tools.
- **Per-workspace document retention/archive policy** chưa tồn tại trong schema.
- **Usage/Credit dashboard** chưa được surface dù `TokenUsage` và `User.credit_micros_balance` đã được track.

Đề xuất này cập nhật planning artifacts để phản ánh code reality, đánh dấu các tính năng removed và ghi rõ các gap cần bổ sung.

---

## 2. Impact Analysis

### 2.1 Epic / Story Impact

| Epic | Story | Ảnh hưởng |
|---|---|---|
| Epic 1: Identity/Auth | 1.5 | Cập nhật: RBAC chỉ Owner/Editor/Viewer; Admin system role đã xóa. |
| Epic 2: Connectors | 2.5 | Mới: per-workspace MCP tool toggle. |
| Epic 3: Knowledge Base | 3.5 | Đánh dấu removed: AI File Sorting. |
| Epic 3: Knowledge Base | 3.6 | Mới: citation scroll-to-highlight trong full editor. |
| Epic 3: Knowledge Base | 3.7 | Mới: data retention & lifecycle. |
| Epic 6: Automations | 6.4 | Mới: direct write-back actions (Notion/Slack/Linear/Jira). |
| Epic 8: Platform Operations | 8.3 | Mới: usage & credit dashboard. |

### 2.2 Artifact Impact

| Artifact | Thay đổi |
|---|---|
| `prd.md` | Cập nhật FR-10 (Admin removed), FR-5 (AI File Sorting removed), FR-18 (direct write-back gap), FR-24 (ChainLens Research exists), NFR-6 (citation full-editor gap), NFR-7 (usage dashboard gap), OQ-3/OQ-4 (retention & MCP toggle gaps). |
| `epics.md` | Cập nhật Story 1.5, Story 3.5; thêm Story 2.5, 3.6, 3.7, 6.4, 8.3; cập nhật coverage map. |
| `ARCHITECTURE-SPINE.md` | Thêm AD-REMOVED (AI File Sorting) và AD-DEFER-1..5 cho 5 gap; cập nhật capability map. |

### 2.3 Technical Impact

- **Không cần deploy code ngay.** Đây là artifact correction.
- Các story gap sẽ cần thêm migrations, API endpoints, UI components, và có thể ảnh hưởng Zero sync / MCP tool catalog khi implement.
- README và marketing copy cần được cập nhật để tránh sai lệch với khách hàng.

---

## 3. Recommended Approach

1. **Chấp nhận đề xuất này** để artifacts phản ánh đúng code reality.
2. **Tạo backlog stories** cho 5 gap (citation full editor, direct write-back, MCP tool toggle, retention, usage dashboard) với priority do PM quyết định.
3. **Cập nhật README và public docs** loại bỏ/correct các mô tả về Admin, AI file sorting, automation direct write-back.
4. **Implementation handoff** giao cho backend/web team theo acceptance criteria trong `epics.md`.

---

## 4. Detailed Change Proposals

### Change 1 — PRD: Mark RBAC chỉ Owner/Editor/Viewer (Admin removed)

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Before (trạng thái cũ / README):**
> “RBAC with Owner, Admin, Editor, and Viewer roles.”

**After (text trong PRD):**
> #### FR-10: RBAC với ba system roles
> System roles mặc định chỉ có **Owner**, **Editor**, **Viewer**. Migration 72 đã xóa role `Admin` và chuyển thành viên Admin sang Editor; `get_default_roles_config()` chỉ trả 3 role. README/public docs cần cập nhật.

---

### Change 2 — PRD: Mark AI File Sorting removed

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Before (README):**
> “AI file sorting auto-organizes documents by source, date, and topic.”

**After (text trong PRD):**
> #### FR-5: AI File Sorting (REMOVED)
> Tính năng sắp xếp file tự động bằng AI đã từng được thêm cờ `ai_file_sort_enabled` ở migration 124 nhưng đã bị gỡ bỏ hoàn toàn ở migration 172. Không còn UI, API, hay logic liên quan.

---

### Change 3 — PRD: Mark automation direct write-back là gap

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Before (README):**
> “Scheduled and event-triggered agents turn what they find into briefs and alerts, and … written back to Notion, Slack, Linear, and Jira.”

**After (text trong PRD):**
> #### FR-18: Automation Action Types
> Automation action registry hiện chỉ có action `agent_task` — chạy một turn của multi_agent_chat. Direct write-back actions (Notion, Slack, Linear, Jira) chưa được implement dưới dạng action type riêng. Agent vẫn có thể dùng các tool như `create_notion_page` trong `agent_task`.

---

### Change 4 — PRD: Add citation full-editor highlight gap

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Before (giả định cũ):**
> Click citation mở/mở rộng tài liệu tại đúng đoạn trích dẫn.

**After (text trong PRD):**
> #### NFR-6: Citation Full-Editor Highlight (GAP)
> Click citation trong chat **không** scroll/highlight đoạn snippet tương ứng trong full document editor. Right panel citation có scroll/highlight chunk, nhưng nút “Open” chỉ mở editor với `documentId` (không truyền `chunkId`); `editorPanelAtom` không có trường `chunkId` hay highlight state.

---

### Change 5 — PRD: Add MCP tool toggle & retention gaps

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Before (không có):** Không đề cập.

**After (text trong PRD):**
> #### OQ-3: Per-workspace document retention/archive policy
> Chưa có cột/policy cho retention, auto-archive, hoặc xóa tài liệu theo tuổi. `Document` model không có `retention_days`/`archived_at`; `Workspace` không có retention settings.
>
> #### OQ-4: Per-workspace MCP tool enable/disable toggle
> Chưa có cơ chế cho phép workspace owner bật/tắt từng MCP tool. MCP server hiện expose toàn bộ tools cho mọi workspace mà API key có quyền truy cập.

---

### Change 6 — PRD: Add usage/credit dashboard gap

**Artifact:** `prds/prd-Nowing-2026-07-22/prd.md`  
**Before (không có):** Dữ liệu được track nhưng không thấy dashboard.

**After (text trong PRD):**
> #### NFR-7: Usage & Credit Dashboard (GAP)
> `TokenUsage` và `credit_micros_balance` được lưu nhưng chưa có trang/dashboard tổng hợp cho user xem lịch sử sử dụng, chi phí theo workspace/model/thời gian. Buy-credits page chỉ hiển thị current balance.

---

### Change 7 — Epics.md: Update RBAC story (Admin removed)

**Artifact:** `epics.md`  
**Before (giả định cũ):**
> Story RBAC bao gồm Admin role trong system roles.

**After (text trong epics.md):**
> ### Story 1.5: RBAC with Owner/Editor/Viewer (Admin Removed)
> As a workspace Owner, I want system roles to be Owner, Editor, and Viewer only, so that the role model matches the actual schema and migration history.
> **AC:** Given `get_default_roles_config()` được gọi khi tạo workspace, when workspace được khởi tạo, then chỉ tạo 3 system roles: Owner, Editor, Viewer; and không có system role tên “Admin” (migration 72 đã xóa); and README/docs cập nhật loại bỏ “Admin”.

---

### Change 8 — Epics.md: Mark AI File Sorting removed

**Artifact:** `epics.md`  
**Before (giả định cũ):**
> Story AI file sorting vẫn active.

**After (text trong epics.md):**
> ### Story 3.5: AI File Sorting (Removed)
> As a product manager, I want AI File Sorting removed from scope and docs, so that artifacts reflect the actual schema.
> **AC:** Given migration 124 từng thêm cột, when migration 172 chạy, then cột `ai_file_sort_enabled` bị xóa khỏi `workspaces`; and không còn API/UI/logic AI file sorting; and README/docs cập nhật loại bỏ “AI file sorting auto-organizes documents”.

---

### Change 9 — Epics.md: Add new gap stories

**Artifact:** `epics.md`  
**Before (không có):** Không có stories cho 5 gap.

**After (text trong epics.md):**
> - Story 2.5: Workspace MCP Tool Enable/Disable Toggle (OQ-4)
> - Story 3.6: Citation Scroll-to-Highlight in Full Document Editor (NFR-6)
> - Story 3.7: Data Retention & Lifecycle (OQ-3)
> - Story 6.4: Direct Write-Back Actions (FR-18)
> - Story 8.3: Usage & Credit Dashboard (NFR-7)

---

### Change 10 — ARCHITECTURE-SPINE.md: Add AD-REMOVED và AD-DEFER

**Artifact:** `architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`  
**Before (spine cũ):** Không phản ánh AI File Sorting removed hoặc các gap.

**After (text trong spine):**
> ### AD-REMOVED — AI File Sorting đã bị gỡ bỏ
> - Binds: FR-5
> - Prevents: lập kế hoạch xây dựng tính năng không còn tồn tại
> - Rule: Migration `172_remove_ai_file_sort.py` đã `DROP COLUMN workspaces.ai_file_sort_enabled`. Không thêm lại cột/API/UI.
>
> ### AD-DEFER-1 — Citation scroll/highlight trong full document editor
> - Reason: Citation panel đã cung cấp chunk window với highlight. Cần map `chunkId` -> block/range trong Plate/Monaco và thêm state `chunkId` vào `editorPanelAtom`.
> - Linked: NFR-6 / Story 3.6
>
> ### AD-DEFER-2 — Direct write-back automation actions
> - Reason: Agent có thể viết lại qua `agent_task` tools. Direct action types riêng cần retry/audit/rollback chuyên biệt.
> - Linked: FR-18 / Story 6.4
>
> ### AD-DEFER-3 — Per-workspace MCP tool enable/disable toggle
> - Reason: MCP server hiện expose tất cả tools. Cần schema `workspace_mcp_tool_enabled` và filter `tools/list` server-side.
> - Linked: OQ-4 / Story 2.5
>
> ### AD-DEFER-4 — Data retention & lifecycle per workspace
> - Reason: Chưa có yêu cầu rõ ràng về retention; cần thiết kế soft-delete/archive và tác động tới Zero sync.
> - Linked: OQ-3 / Story 3.7
>
> ### AD-DEFER-5 — Usage & credit dashboard
> - Reason: Dữ liệu `TokenUsage`/`credit_micros_balance` đã có nhưng chưa có aggregate API và UI.
> - Linked: NFR-7 / Story 8.3

---

## 5. Implementation Handoff

### Các artifact đã cập nhật
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md`
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/epics.md`
- `/Users/luisphan/Documents/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md`

### Việc cần làm tiếp theo

| Owner | Task | Acceptance |
|---|---|---|
| PM / Content | Cập nhật `README.md`, landing page, docs site: loại bỏ “Admin”, “AI file sorting”, và automation direct write-back (hoặc diễn giải rõ là agent_task). | Không còn mô tả sai về Admin/AI file sorting trong public docs. |
| Backend | Đánh giá 5 gap stories: Story 2.5, 3.6, 3.7, 6.4, 8.3. | Mỗi gap có decision: implement / defer / split. |
| Backend | Nếu implement gap: viết migrations, API, handlers theo acceptance criteria trong `epics.md`. | Pass unit/integration tests; không phá vỡ AD-1..AD-10. |
| Web | Nếu implement UI gaps: cập nhật `editorPanelAtom` (Story 3.6), workspace MCP settings (Story 2.5), retention settings (Story 3.7), usage dashboard (Story 8.3). | UI hiển thị đúng trạng thái và gọi API mới. |
| QA | Đối chiếu artifacts với code: migration 72, 124, 172; `app/automations/actions/builtin/`; `editorPanelAtom`; `mcp_server/server.py`; `TokenUsage`/`wallet_credit.py`. | Không còn mâu thuẫn giữa artifact và code. |

### Cách tiếp cận ưu tiên (ponytail)
- Đừng implement gap cho đến khi PM xác nhận priority.
- Nếu implement, dùng code/state hiện có trước (ví dụ: dùng `TokenUsage` cho dashboard trước khi tạo aggregate cache).
- Các tính năng removed (Admin, AI File Sorting) không được thêm lại nếu không có quyết định rõ ràng.

### Lưu ý
- Các artifact này là “correct-course” — chúng thay thế hoặc cập nhật các planning artifacts cũ, không phải refactor code.
- Nếu có thêm gap phát hiện trong quá trình implement, cập nhật lại 3 artifacts và append vào `sprint-change-proposal`.

---

## 6. Approval

**Approved by:** Luisphan  
**Date:** 2026-07-22  
**Decision:** Approved for implementation. PM/team to prioritize 5 gap stories and update public docs before code changes.
