# Story 24.3 — BMAD Code Review Triage (2026-08-21)

**Diff source:** working tree (`git diff HEAD` + untracked files)  
**Spec:** `_bmad-output/implementation-artifacts/stories/24-3-multi-seat-team-crm-pipeline-and-shared-credits.md`  
**Invariants:** INV-24.4, INV-23.4, INV-23.6  
**Overall verdict:** **CHANGES REQUESTED / REJECT** — do not merge the working tree as the final 24.3 patch.

## decision_needed

- [x] [Review][Decision] **Working tree chứa scope-creep không thuộc Story 24.3**: `masothue/10.8` parser/tests, `MissionControlWidget.tsx` build fix, và toàn bộ `.agents/skills/bmad-agent-e2e-tester/` mới (XActions). Cần quyết định: (a) tách khỏi diff trước khi merge, (b) merge và chỉ định story sở hữu riêng, hay (c) giữ nguyên vì đã chọn review working tree.
- [x] [Review][Decision] **Hình dạng response 409 OCC conflict**: backend trả `{"detail": {"current_version": ..., "current_stage_id": ...}}`, frontend `LeadKanbanBoard.tsx` đọc `err.data.current_version`. Sửa ở backend (trả flat body) hay frontend (đọc `err.data.detail.current_version / current_stage_id`)?
- [x] [Review][Decision] **INV-23.6 role/assignment visibility**: chỉ owner/admin xem toàn bộ lead; member chỉ xem lead được assign. Enforce ở RLS policy (thêm `assigned_to_user_id` predicate) hay ở route query layer?

## patch

- [x] [Review][Patch] `nowing_backend/app/services/workspace_credit_service.py:163-215` — `deduct_credits` trừ `Workspace.credit_micros_balance` trước khi atomically check per-seat cap; nếu cap UPDATE fail, balance đã mất và không refund. (source: blind+edge+auditor)
- [x] [Review][Patch] `nowing_backend/app/services/workspace_credit_service.py:330-339` — `record_spend` trả no-op success khi `membership is None`; non-member billable user bypass per-seat cap. (source: blind+edge+auditor)
- [x] [Review][Patch] `nowing_backend/app/services/workspace_credit_service.py:449-489` — `refund_credits` tăng `Workspace.credit_micros_balance` trước khi decrement `monthly_spent_micros`; nếu member update fail, pool bị phình to. (source: blind+edge)
- [x] [Review][Patch] `nowing_backend/app/services/workspace_credit_service.py:582-598` — `set_member_spend_cap` không flush/commit, cho phép đặt cap < `monthly_spent_micros` hiện tại. (source: blind+edge)
- [x] [Review][Patch] `nowing_backend/app/services/billing_event_service.py:818-833` — `record_spend` gọi ngoài `try` và không convert `SpendCapExceededError` thành `InsufficientCreditsError`; caller trả 500. (source: blind+edge+auditor)
- [x] [Review][Patch] `nowing_backend/app/capabilities/core/billing.py:36-71` — `_debit_with_workspace_spend_cap` không refund `monthly_spent_micros` khi `wallet_credit.apply_debit` fail. (source: blind)
- [x] [Review][Patch] `nowing_backend/app/services/lead_assignment_service.py:208-223` — `assign_leads_batch` gọi `get_eligible_members` cho từng lead, tạo N+1 query và capacity TOCTOU. (source: blind+edge+auditor)
- [x] [Review][Patch] `nowing_backend/app/services/lead_assignment_service.py:130-188,225-315` — `assign_lead`/`reassign_lead` luôn insert `LeadAssignment` mới mà không upsert/vô hiệu hóa bản ghi cũ. (source: blind+edge)
- [x] [Review][Patch] `nowing_backend/app/services/lead_assignment_service.py:236-280` — reassign capacity check không atomic với insert; concurrent reassign có thể vượt `lead_capacity`. (source: blind+edge)
- [x] [Review][Patch] `nowing_backend/app/services/lead_assignment_service.py:264-280` — capacity check đếm cả lead đang được target sở hữu, từ chối reassign về chính chủ khi đã đầy. (source: edge)
- [x] [Review][Patch] `nowing_backend/app/services/lead_assignment_service.py:130-148` — `assign_lead` không từ chối lead đã assigned hoặc terminal (`lost`/`won`). (source: edge)
- [x] [Review][Patch] `nowing_backend/app/routes/lead_pipeline_routes.py:210-227` — transition lead trả 409 khi lead không tồn tại (current one_or_none trả None). (source: edge)
- [x] [Review][Patch] `nowing_backend/app/routes/lead_pipeline_routes.py:382-427` — `assign_leads_batch` không verify `lead_ids` tồn tại/trong workspace trước khi gọi service. (source: blind)
- [x] [Review][Patch] `nowing_backend/app/routes/lead_pipeline_routes.py:96-109,165-247,259-331,334-427` — các route pipeline không enforce INV-23.6; member bình thường có thể xem/timeline/transition/reassign mọi lead. (source: blind+auditor)
- [x] [Review][Patch] `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:87-110` — dùng raw `text(f"ALTER TABLE {table_name} ...")` thêm FK mà không `IF NOT EXISTS`; rủi ro fail trên partitioned tables. (source: blind)
- [x] [Review][Patch] `nowing_backend/alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py:270-302` — `_tenant_predicate` chỉ lọc `workspace_id`/`client_id`, chưa lọc theo role/assignment. (source: edge+auditor)
- [x] [Review][Patch] `nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx:420-431` — 409 merge cập nhật `stage_id` nhưng không cập nhật `status`. (source: edge)
- [x] [Review][Patch] `nowing_web/components/leads/pipeline/LeadKanbanBoard.tsx:275-289` — `loadData` swallow tất cả lỗi (auth/server) và render board rỗng. (source: edge)
- [x] [Review][Patch] `nowing_web/components/team/MemberSpendCapDialog.tsx:81-86` — catch generic, nuốt lỗi 403/409/422. (source: edge)
- [x] [Review][Patch] `nowing_web/components/team/MemberSpendCapDialog.tsx:52-66` — không reject monthly spend cap chứa decimal/fractional. (source: edge)
- [x] [Review][Patch] `nowing_web/components/leads/LeadDetailFlyoutDrawer.tsx:77-84` — lỗi load activity timeline bị ẩn. (source: edge)
- [x] [Review][Patch] `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts:46-50,92-94,105-110` — conditional drag, không assert 409 toast, không verify timeline. (source: edge+auditor)
- [x] [Review][Patch] `nowing_web/tests/zero/kanban-multicontext-sync.spec.ts:52-54` — `browser.newContext()` không dùng `storageState`; multi-user scenario không được test. (source: edge)
- [x] [Review][Patch] `nowing_backend/app/proprietary/platforms/masothue/parsers.py:197` (working tree) — `i + 0 < len(parts)` là tautology, gây `IndexError` khi district là phần cuối; mâu thuẫn với test mới thêm. (source: blind+edge+auditor)
- [x] [Review][Patch] `scripts/mutation-gate.py:329` (working tree) — `if step != "exec" and result.returncode != 0` bỏ qua lỗi `cosmic-ray exec`, có thể báo pass khi mutation suite thất bại. (source: blind)

## defer

- [x] [Review][Defer] `nowing_backend/app/services/workspace_credit_service.py:141-146,322-328` — `FakeAsyncSession` seam (`_deduct_credits_fake`, `_record_spend_fake`) cho phép unit test đi vào fake path, không test production SQL. Đã được ghi nhận trong `test-review-24-3.md`; xử lý trong 4.9/4.10 test review/mutation gate.
- [x] [Review][Defer] `nowing_backend/tests/integration/services/test_team_crm_pipeline.py` — integration test stub, không dùng DB/routes. Đã ghi trong `test-review-24-3.md`; xử lý trong 4.9.
- [x] [Review][Defer] `nowing_backend/tests/unit/services/test_billing_event_service.py` / `tests/unit/capabilities/test_billing.py` — monkeypatch `record_spend`. Đã ghi trong `test-review-24-3.md`; xử lý trong 4.9/4.10.
- [x] [Review][Defer] Các call site trực tiếp `wallet_credit.apply_debit` trong `phone_waterfall_service.py`, `outcome_pricing_service.py`, `etl_credit_service.py`, `zns_client.py`, `web_crawl_credit_service.py`, `platform_scrape_credit_service.py` — chưa route qua `WorkspaceCreditService.record_spend`. Là nợ kỹ thuật pre-existing/nằm trong scope story khác; revisit khi sửa từng service.
- [x] [Review][Defer] `nowing_web/components/leads/MissionControlWidget.tsx:239` — pre-existing TS build fix, không thuộc 24.3.
- [x] [Review][Defer] `.agents/skills/bmad-agent-e2e-tester/` và `_bmad/memory/bmad-agent-e2e-tester/` — skill mới liên quan XActions, hoàn toàn ngoài scope 24.3; xử lý trong story agent/skill riêng.

## dismissed

- None.

---

## Source artifacts

- `_bmad-output/implementation-artifacts/review-24-3-working-tree.diff`
- `_bmad-output/implementation-artifacts/review-24-3-blind-hunter.md`
- `_bmad-output/implementation-artifacts/review-24-3-edge-case-hunter.json`
- `_bmad-output/implementation-artifacts/review-24-3-acceptance-auditor.md`
