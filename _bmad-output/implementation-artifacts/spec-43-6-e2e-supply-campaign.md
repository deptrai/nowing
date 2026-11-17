---
title: 'Story 43.6 — E2E supply campaign (enterprise/masothue path thật) + gỡ route guard'
type: 'story'
created: '2026-11-17'
status: 'done'
baseline_revision: '90f1e37bd0d2d47923191c016e2a467a08039902'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - _bmad-output/implementation-artifacts/epic-43-context.md
warnings: []
deferred: []
---

# Story 43.6 — E2E supply campaign + gỡ route guard

## Goal

Chứng minh pipeline supply end-to-end trên dev (spec → routing → post-filter →
persist → role-tag), và gỡ guard tạm `direction != "demand" → 422` đã gắn ở
`campaign_routes.py` từ spec 43.1 — sau khi e2e chứng minh path thật hoạt động.

## Intent Contract

### Always

- E2E dùng PAT thật (mint qua `POST /api/v1/pats`, `token_kind="legacy"`,
  `workspace_id=<ws>`, `scopes=["leads:write"]`) — auth path thật qua
  `Authorization: Bearer`, unified seam AI-42.4.
- E2E payload: `CampaignSpec{direction:"supply", supply_criteria:{categories:
  ["nhà phân phối"], locations:["Khánh Hòa"], require_tax_id:true}}` — vertical
  legal-entity có MST (KHÔNG dùng BĐS/cá nhân).
- Assert supply path thật: adapters resolve = supply_eligible set (enterprise +
  muasamcong — KHÔNG batdongsan/chotot); leads persist qua `ingest_batch` với
  auto-table + `extra_metadata.lead_role="supplier"` + `campaign_key=spec.name`;
  counter `filtered_no_tax_id` hiện trong result/meta.
- Joint-validation e2e: `match_mode="pool"` → 422; `direction="supply"` thiếu
  `supply_criteria` → 422 — không chạm orchestrator.
- Demand regression: demand spec cũ → adapter set + outcome không đổi.
- Gỡ guard tạm ở `campaign_routes.py` (2 chỗ: `plan_campaign` + `execute_campaign`)
  VÀ class `TestSupplyExecutionGuard` trong test_campaign_spec_direction.py —
  thay bằng test path thật.

### Never

- Không chạy scraping thật trong unit/integration test — e2e live-smoke là bước
  dev riêng (mock adapter `search_leads` ở tầng DB+route, KHÔNG call mạng).
- Không đổi demand contract; không thêm endpoint/scope mới.
- Không dùng BĐS/cá nhân cho e2e (không có MST).
- Không tạo campaigns/campaign_runs table — identity = `spec.name`.

## Code Map (verify trước)

- `nowing_backend/app/routes/campaign_routes.py:93` `plan_campaign` + `:124`
  `execute_campaign` — guard `spec.direction != "demand"` → 422 cần gỡ.
- `nowing_backend/tests/unit/lead_intelligence/test_campaign_spec_direction.py`
  class `TestSupplyExecutionGuard` — test pin guard cũ, gỡ/thay.
- `nowing_backend/tests/integration/lead_batch/test_pat_batch_ingest_e2e.py` —
  pattern PAT thật + `client_real_auth` (fixture tái sử dụng).
- `nowing_backend/tests/integration/lead_batch/conftest.py:44-101` — `client`,
  `db_workspace`, `db_user`, `pat_workspace`, `db_pat` fixtures.
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:808`
  `execute_and_persist` — seam nơi supply post-filter (43.3) + role-tag (43.4)
  áp dụng. `:546` `effective_query` synthesis (43.2).

## Tasks

- T1: File test mới `nowing_backend/tests/integration/campaigns/
  test_supply_campaign_e2e.py` — PAT thật → POST `/campaigns/execute` supply spec
  (mock `LeadSourceAdapter.search_leads` trả NormalizedLead giả: 1 có tax_id,
  1 không có tax_id, 1 sparse-identity) → assert persist + counters + role-tag +
  auto-table trong DB.
- T2: Joint-validation e2e — `match_mode="pool"` → 422; supply thiếu
  `supply_criteria` → 422.
- T3: Demand regression e2e — demand spec cũ → adapters demand set, outcome
  không đổi.
- T4: Gỡ route guard (2 chỗ) + gỡ `TestSupplyExecutionGuard` + pin regression.
- T5: Live smoke trên dev stack (backend :4445 + DB :5434) — chạy POST thật 1
  lần, log kết quả vào test-summary (không bắt buộc CI).

## Acceptance Criteria

1. E2E supply → leads persist + `lead_role="supplier"` + `campaign_key` +
   auto-table; `filtered_no_tax_id` counter đúng số lead thiếu MST.
2. Adapters resolve chỉ supply_eligible (enterprise + muasamcong).
3. `match_mode="pool"` → 422; supply thiếu criteria → 422.
4. Demand e2e không đổi.
5. Route guard đã gỡ — supply POST không còn 422 "chưa được hỗ trợ thực thi".
6. `pytest tests/integration/campaigns/ -x -q` + `tests/unit/lead_intelligence/`
   xanh.

## Verification

- `cd nowing_backend && .venv/bin/python -m pytest tests/integration/campaigns/ -x -q`
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/ -x -q`
- Dev smoke: curl POST execute trên :4445 (cookie/PAT), quan sát result JSON.
