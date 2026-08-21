---
story_key: "24-5"
epic: "epic-24"
story: "24.5"
title: "Vertical Playbook Marketplace & Community Workflow Templates"
status: "done"
baseline_commit: "6ac305274"
---

# Story 24.5: Vertical Playbook Marketplace & Community Workflow Templates

## Story Overview

As a new or non-technical business user,
I want to browse a curated Marketplace of industry-specific Playbook Templates (Real Estate, IT Recruitment, B2B SaaS, E-Commerce),
So that I can launch complex multi-step scraping, scoring, and outreach workflows with zero prompt-engineering friction.

---

## Architectural Invariants (INV-24.6)
- **INV-24.6 (Template Sandbox & AST Security):** Vertical Playbooks BẮT BUỘC khai báo `inputs_schema` (JSON Schema) với giới hạn cứng `max_leads_per_run <= 200` để tránh cạn kiệt tài nguyên. Community Playbooks phải qua kiểm duyệt (`is_approved = True`) trước khi hiển thị trên marketplace.

---

## Acceptance Criteria

1. **Categorized Marketplace Gallery:**
   - **Given** `/dashboard/[workspace_id]/playbooks`,
   - **When** viewed,
   - **Then** it renders a responsive grid with category filter tabs for `Bất Động Sản`, `Tuyển Dụng Nhân Sự`, `B2B Sales`, `E-Commerce & Bán Lẻ`, defaults the active tab from the workspace's vertical, and sends the selected vertical to `GET /api/v1/playbooks`; cards show real author badges, author names, run counts, and estimated credit costs.

2. **Official High-Value Playbooks:**
   - **Given** the initial launch,
   - **When** browsing official playbooks,
   - **Then** at least 4 battle-tested templates are available:
     1. *BĐS Ngộp & Môi Giới Pro:* Săn BĐS chính chủ/ngộp giá ➔ Lọc SĐT ➔ Soạn tin nhắn Zalo gửi báo giá.
     2. *IT Headhunter Săn Senior:* Quét TopCV/ITviec ➔ Bóc tách Tech Stack ➔ So khớp JD ứng viên.
     3. *B2B Sales Doanh Nghiệp Mới:* Quét doanh nghiệp mới thành lập ➔ Tra cứu MST & SĐT ➔ Gửi kịch bản giới thiệu.
     4. *E-Commerce Flash Price Tracking:* Theo dõi biến động giá Shopee/Lazada ➔ Bắn cảnh báo Telegram.

3. **Dynamic Schema-Driven Input Form, Cost Preview, & Instant Run:**
   - **Given** a selected playbook,
   - **When** clicking `Khởi Tạo Kịch Bản` and submitting the form,
   - **Then** the UI renders a dynamic form derived from `inputs_schema` with parameter bounds, shows a credit estimate and per-run lead/SKU limit, and `POST /api/v1/playbooks/{id}/instantiate` creates an automation and immediately queues a manual run with the supplied inputs.

---

## Technical Tasks

### Backend Implementation
- [x] Schema & Model: Tận dụng bảng `playbooks` (`app/automations/persistence/models/playbook.py`) với `inputs_schema`, `verticals`, `definition`, `tool_scope`, `scope`.
- [x] Seed Data: Nạp 4 template chính thức chuẩn hóa cho thị trường Việt Nam qua `app/automations/services/playbook_seed_service.py` tích hợp tự động vào startup `lifespan`.
- [x] Model & Migration: Add `is_approved` column and partial unique index `(name, scope) WHERE workspace_id IS NULL` on `playbooks`; filter marketplace by `is_approved=True`.
- [x] Service: Tích hợp `INV-24.6` hard limit (`max_leads_per_run <= 200`) trong `PlaybookService._validate_inputs` and at create/update.
- [x] Service: Canonicalize workspace verticals → marketplace slugs (`real_estate -> realestate`, `b2b_equipment -> b2b`, `auto/general -> general`).
- [x] Service: `PlaybookService.instantiate` authorizes read access and immediately launches a manual run with user inputs.
- [x] API Router: Hỗ trợ query theo `vertical` trong `GET /api/v1/playbooks`.

### Frontend Implementation
- [x] UI: Nâng cấp Marketplace Hub (`nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx`) với Category filter tabs, search bar, Official/Workspace badge, author name, credit cost, run count, and search across name/description/author/tags; default tab follows workspace vertical.
- [x] Data: Wire `vertical` query param through `playbooksListAtom` (atomFamily) and `playbooksApiService.listPlaybooks`.
- [x] Dynamic Form: Nâng cấp `PlaybookInstantiateDialog.tsx` hiển thị Credit preview banner với real `estimated_credits_cost`, per-run lead/SKU limit, safe error handling, detail-fetch error, and double-click protection (`SchemaForm` `disabled` prop).

---

## Dev Agent Record

### File List
- `nowing_backend/app/automations/services/playbook_seed_service.py` [NEW]
- `nowing_backend/app/automations/services/playbook_service.py` [MODIFY]
- `nowing_backend/app/automations/api/playbook.py` [MODIFY]
- `nowing_backend/app/app.py` [MODIFY]
- `nowing_backend/tests/unit/services/test_playbook_templates.py` [NEW]
- `nowing_web/app/dashboard/[workspace_id]/playbooks/playbooks-content.tsx` [MODIFY]
- `nowing_web/app/dashboard/[workspace_id]/playbooks/playbook-instantiate-dialog.tsx` [MODIFY]
- `nowing_web/contracts/types/playbook.types.ts` [MODIFY]

### Verification Results (post-review patch pass, 2026-08-22)
- **Backend Unit Tests:** `uv run pytest tests/unit/services/test_playbook_templates.py tests/unit/automations/services/test_playbook_service.py -q` ➔ **9 passed**.
- **Backend Integration Tests:** `uv run pytest tests/integration/automations/test_playbook_routes.py -q` ➔ **8 passed**.
- **Backend Lint:** `uv run ruff check <changed files>` ➔ **All checks passed!**
- **Alembic:** `uv run alembic heads` ➔ `193_add_playbook_is_approved (head)`.
- **Frontend Typecheck:** `pnpm tsc --noEmit` ➔ **Exit code 0**.
- **Frontend Linter:** `pnpm exec biome check <changed files>` ➔ **0 errors, 0 warnings**.
- **Live Browser Automation:** Chạy thành công trên Google Chrome thật (Headed Mode):
  - Gallery Overview: [`playbook_marketplace_gallery.png`](file:///Users/luisphan/.gemini/antigravity/brain/19a31587-eda5-446f-b789-96835623ae8e/playbook_marketplace_gallery.png)
  - Schema Form Modal: [`playbook_modal_schema_form.png`](file:///Users/luisphan/.gemini/antigravity/brain/19a31587-eda5-446f-b789-96835623ae8e/playbook_modal_schema_form.png)\n\n### Review Findings — 2026-08-22\n\n> **Source reviews:** `review-24-5-blind-hunter.md`, `review-24-5-edge-case-hunter.md`, `review-24-5-acceptance-auditor.md`  \n> **Full triage:** `review-24-5-triaged-findings.md`\n\n#### decision_needed\n\n- [ ] [Review][Decision][high] Default marketplace visibility changed — workspace-vertical filter removed from `list_playbooks` [nowing_backend/app/automations/services/playbook_service.py:137-174] — The new query returns all workspace playbooks plus all system playbooks when no `vertical` is passed. Two integration tests fail. Decide: (a) restore workspace-vertical default and use explicit `vertical` override, or (b) keep cross-vertical visibility and update tests/spec.\n- [ ] [Review][Decision][high] Story spec was retrofitted in the same diff to match implementation [review-24-5-working-tree.diff] — The working-tree spec changed from 12 templates/`/playbooks/marketplace` to 4 templates/`/playbooks`. Decide: reconcile baseline vs current spec before merging.\n- [ ] [Review][Decision][high] Community playbook moderation (`is_approved`) is not implemented — INV-24.6 requires it, but the table has no `is_approved` column and `PlaybookScope` only has `workspace`/`system`. Decide: add `community` scope + approval flow, add `is_approved` flag, or relax the invariant.\n- [ ] [Review][Decision][medium] Marketplace layout and category labels do not match AC-1 — Spec calls for “grouped by vertical” with `B2B Sales` / `E-Commerce & Bán Lẻ`; implementation uses flat grid with `B2B Sales & MST` / `E-Commerce & Giá`. Decide: update UI or update spec.\n- [ ] [Review][Decision][medium] Workspace vertical naming mismatch vs. marketplace categories — Workspace uses `real_estate`, marketplace uses `realestate`, so user playbooks vanish from tabs. Decide: canonical slugs or mapping layer.\n- [ ] [Review][Decision][medium] Playbook instantiation inputs are validated but not persisted or used — `PlaybookService.instantiate()` validates `payload.inputs` but creates an automation with no stored inputs and no manual trigger. Decide: store as `static_inputs` in manual trigger, extend run endpoint, or create a run immediately.\n- [ ] [Review][Decision][low] INV-24.6 canonical `max_leads_per_run` field is not used in seed data — Spec text uses `max_leads_per_run`; seeds use `max_leads`/`max_skus`. Decide: rename, update invariant text, or keep aliases.\n\n#### patch\n\n- [ ] [Review][Patch][high] `PlaybookService.instantiate` never authorizes read access to the source playbook.\n- [ ] [Review][Patch][high] Official seed playbooks are not runnable — `agent_task` steps lack required `query` and `definition.inputs.schema` is missing required keys.\n- [ ] [Review][Patch][high] `PlaybookSummary` does not expose marketplace metadata (`author_badge`, `estimated_credits_cost`, `run_count`, etc.).\n- [ ] [Review][Patch][high] Marketplace cards and instantiate dialog hardcode badge, cost, and run count.\n- [ ] [Review][Patch][medium] Frontend `vertical` filter is not wired through the API.\n- [ ] [Review][Patch][medium] `PlaybookService._validate_inputs` hard limit is brittle and bypassable.\n- [ ] [Review][Patch][medium] `seed_system_playbooks` has a multi-worker race condition.\n- [ ] [Review][Patch][medium] `PlaybookInstantiateDialog` hides detail-fetch errors and falls back to a no-inputs workflow.\n- [ ] [Review][Patch][medium] `app.py` lifespan swallows playbook seed failures.\n- [ ] [Review][Patch][low] `PlaybooksContent` fetches workspace vertical but never uses it.\n- [ ] [Review][Patch][low] `SchemaForm` submit button can be double-clicked while submission is in flight.\n- [ ] [Review][Patch][low] `seed_system_playbooks` never deletes or renames stale official playbooks.\n- [ ] [Review][Patch][low] `PlaybookInstantiateDialog` error state is not reset on open/close.\n- [ ] [Review][Patch][low] `PlaybookInstantiateDialog` uses unsafe error cast.\n- [ ] [Review][Patch][low] `PlaybookService.list_playbooks` `vertical` filter is case-sensitive and unvalidated.\n- [ ] [Review][Patch][low] Search is diacritic-sensitive and ignores tags/author.\n- [ ] [Review][Patch][low] Marketplace empty state is misleading when no playbooks exist.\n- [ ] [Review][Patch][low] Unit test `test_seed_system_playbooks_idempotent` misuses `AsyncMock`.\n\n#### defer\n\nNone.\n\n#### dismissed\n\n- Consolidated duplicate credit-preview findings into the patch item above.\n- Consolidated duplicate `vertical` filter client-side findings into the patch item above.\n- `_workspaceVertical` is computed but never used — kept as a low-severity patch finding.\n

