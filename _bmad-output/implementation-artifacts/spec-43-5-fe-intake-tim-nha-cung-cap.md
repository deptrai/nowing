---
title: 'Story 43.5 — FE intake "Tìm nhà cung cấp" + wire contract'
type: 'feature'
created: '2026-11-17'
status: 'draft'
baseline_revision: ''
review_loop_iteration: 0
followup_review_recommended: false
context:
  - _bmad-output/implementation-artifacts/epic-43-context.md
warnings:
  - has-fe
deferred: []
---

<intent-contract>

## Goal

Form "Tìm nhà cung cấp" trong campaign-intake gửi `direction:"supply"` +
`supply_criteria` top-level trong campaign create input; backend
`from_campaign_create_input`/`from_payload` dispatch đúng keys đó (bỏ guard 422
tạm thời đã thêm ở 43.1). Demand UX không đổi.

## Always

- Wire contract pin: `direction` + `supply_criteria:{categories, locations,
  min_rating, require_tax_id, require_verified}` ở TOP-LEVEL của payload
  (không lồng trong icp_config/launch_config).
- `from_campaign_create_input` supply branch: đọc keys đó, map sang
  `CampaignSpec(direction="supply", supply_criteria=SupplyCriteria(...),
  query=<free-text query nếu có>)`, derive `location_profile` từ
  `supply_criteria.locations[0]` (cho preflight coverage/telemetry).
- Bỏ guard "direction-scoped keys → ValueError" đã thêm ở 43.1 trong
  `from_campaign_create_input` (thay bằng xử lý đúng); giữ cảnh báo nếu key
  `direction` không hợp lệ (non-literal) — vẫn reject.
- Form FE: mode selector supply; fields — categories (multi-select/free-text
  chips), locations, free-text query (optional), min_rating (number 0–5),
  require_tax_id (checkbox default ON), require_verified (checkbox).
- Client-side validation khớp server: categories/locations non-empty (sau trim),
  min_rating ∈ [0,5] — không submit thô để server 422.
- Demand flow bit-for-bit — payload demand không chứa direction keys.
- i18n vi/en (project convention: messages/*.json đủ 7 locale nếu file dùng
  hệ thống messages; tối thiểu vi + en).

## Never

- Không đổi demand payload contract.
- Không hiển thị supply form trên màn hình khác ngoài campaign intake.
- Không thêm scope/route/permission mới (AI-42.4 đã cover — PAT `leads:write`
  gọi supply persist vẫn qua seam chung).
- Không sửa server-side validation (43.1) hay execution guard ở routes —
  guard `direction != "demand"` ở `plan_campaign`/`execute_campaign` vẫn giữ
  đến khi 43.6 e2e chứng minh supply chạy end-to-end (spec 43.6 gỡ).

## Decisions

- D1: FE wire keys top-level (không lồng) — đã chốt trong plan Epic 43 D-review.
- D2: `require_tax_id` default ON trong form (đúng semantics legal-entity).
- D3: `location_profile` derive từ `locations[0]` — supply chỉ dùng cho
  preflight coverage/telemetry, không quyết định kết quả (post-filter 43.3
  lo phần lọc location thực).
- D4: form là phần mở rộng của intake hiện tại — reuse màn hình campaign,
  thêm mode supply; KHÔNG tạo page mới.

</intent-contract>

## I/O & Edge-Case Matrix

| Case | Payload | Expected |
|---|---|---|
| SUPPLY_CREATE | `{name, direction:"supply", supply_criteria:{...}}` | `CampaignSpec.direction=="supply"`, criteria đúng |
| SUPPLY_LOC_DERIVE | `locations:["Khánh Hòa","HCM"]` | `location_profile` = "Khánh Hòa" |
| SUPPLY_QUERY_OPT | supply + `query:"nhà phân phối"` | `spec.query=="nhà phân phối"` |
| DEMAND_UNCHANGED | `{name, icp_config:{...}}` (không direction keys) | `direction=="demand"`, không đổi |
| BAD_DIRECTION | `direction:"sideways"` | Reject (ValueError→422) |
| CLIENT_VALID | categories `[]` | Form không submit (client-side chặn) |
| EMPTY_ITEMS | categories `["  "]` | Client chặn (post-strip empty) |

## Code Map

| File | Vai trò |
|---|---|
| `nowing_backend/app/lead_intelligence/campaign/schemas.py` (`from_campaign_create_input` ~:290-330, guard 43.1) | supply branch + bỏ guard |
| `nowing_web/` campaign intake components (tìm component campaign create form — khám phá khi implement) | FE form |
| `nowing_web/messages/*.json` | i18n |
| `nowing_backend/tests/unit/lead_intelligence/test_campaign_spec_direction.py` | update guard tests → supply accepted |
| `nowing_backend/tests/unit/lead_intelligence/test_supply_wire_contract.py` | NEW — wire matrix |

## Tasks

- T1: `from_campaign_create_input` — supply branch đọc top-level keys; bỏ
  blanket guard (giữ reject non-literal direction + demand+criteria conflict);
  derive `location_profile` từ `locations[0]`; map query free-text.
- T2: FE form "Tìm nhà cung cấp" + mode selector + client validation + i18n.
- T3: Tests — `test_supply_wire_contract.py` (supply accepted, location derive,
  query pass, demand unchanged, bad direction reject); update guard tests 43.1
  (supply giờ ACCEPTED qua converter, không phải ValueError).
- T4: `pnpm tsc --noEmit` (hoặc `bunx tsc --noEmit` theo repo convention) sạch.

## Acceptance Criteria

1. POST create campaign với top-level `direction:"supply"` + `supply_criteria`
   → `CampaignSpec.direction=="supply"`, criteria chính xác.
2. Guard tạm 43.1 (direction keys → ValueError) đã gỡ cho keys hợp lệ.
3. Demand payload cũ không thay đổi parse (`direction=="demand"`).
4. Client validation chặn categories/locations rỗng trước khi gọi API.
5. `tsc --noEmit` clean; i18n đủ cho labels mới (ít nhất vi + en).

## Spec Change Log

## Review Triage Log

## Design Notes

- Guard ở `plan_campaign`/`execute_campaign` (routes, `direction != "demand"`
  → 422) VẪN giữ trong story này — chỉ gỡ ở 43.6 sau khi e2e chứng minh. Điều
  đó nghĩa là sau 43.5, supply submit sẽ parse đúng rồi bị chặn 422 ở route
  — KHÔNG phải bug, là trạng thái chờ 43.6.
- `from_payload` dispatch: `"icp_config" in payload or "source_budget_config"
  in payload` → converter. Supply payload KHÔNG nên chứa icp_config; nếu có
  cả direction + icp_config → direction guard 43.1 vẫn bắt (icp_config non-default
  + supply → 422 từ model_validator).

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/test_supply_wire_contract.py tests/unit/lead_intelligence/test_campaign_spec_direction.py -x -q`
- `cd nowing_web && pnpm tsc --noEmit`
