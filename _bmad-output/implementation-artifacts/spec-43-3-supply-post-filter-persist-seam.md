---
title: 'Story 43.3 — Supply post-filter tại persist seam + NormalizedLead rating/verified'
type: 'feature'
created: '2026-11-17'
status: 'done'
baseline_revision: 'ba4f3de45'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - _bmad-output/implementation-artifacts/epic-43-context.md
warnings: []
deferred: []
---

<intent-contract>

## Goal

Post-filter `supply_criteria` được áp tại **persist seam** trong orchestrator
(ngay trước `ingest_batch`) — KHÔNG ở planner/preflight. `NormalizedLead` có
`rating`/`verified` mới để filter hoạt động. Mỗi drop có counter rõ ràng.

## Always

- Filter chỉ chạy khi `direction == "supply"` (demand path bit-for-bit).
- Một chỗ filter duy nhất — sau khi leads được chuẩn hoá, trước `ingest_batch`.
- Quy tắc drop:
  - `require_tax_id == True` → drop lead không có `tax_id` → counter `filtered_no_tax_id`.
  - `min_rating > 0` → drop lead có `rating < min_rating`; lead `rating is None`
    ĐƯỢC GIỮ → counter `unrated_kept`.
  - `require_verified == True` → drop trừ khi `verified is True` (strict, None drop).
  - Sparse-identity guard: drop lead thiếu cả `company_name` lẫn `tax_id`
    → counter `filtered_sparse_identity` (ngăn "Doanh nghiệp" HMAC-merge rác).
  - `outside_locations` guard: `supply_criteria.locations` non-empty → lead
    không match location bị drop → counter `filtered_outside_locations`; tái dùng
    `evaluate_hierarchical_location_match` trên `lead.city`/`lead.address`.
- Counters xuất hiện trong `LeadGenOrchestratorResult` (hoặc meta dict của nó —
  implementer pin tên field).
- `NormalizedLead`: `rating: float | None = None`, `verified: bool | None = None`;
  `enterprise` adapter set `verified=True` cho bản ghi masothue.
- Demand bit-for-bit — filter không chạy, field mới default-None không đổi
  serialization path cũ.

## Never

- Không filter ở planner/preflight (preflight không thấy lead).
- Không drop `rating is None` khi `min_rating > 0` — chỉ drop rated-thấp.
- Không sửa dedupe key, `ingest_batch`, hoặc adapter contracts khác.
- Không tạo thêm field trên `Lead` DB model — `rating`/`verified` chỉ ở NormalizedLead.
- Không migration.

## Decisions

- D1: filter site = trong `execute_and_persist`/`execute_multi_source_lead_gen`
  chỗ `lead_dicts` được build trước `ingest_batch` (~orchestrator.py:848).
- D2: `require_verified` strict (None drop) — muasamcong không set verified nên
  campaign cần verified thực chất chỉ lấy enterprise; đúng semantics.
- D3: `min_rating` fail-open cho `rating=None` (phần lớn adapter chưa emit rating);
  test pin `unrated_kept > 0` khi không adapter nào có rating.

</intent-contract>

## I/O & Edge-Case Matrix

| Case | Input | Expected |
|---|---|---|
| TAX_DROP | supply + require_tax_id, lead không tax_id | Drop, `filtered_no_tax_id+=1` |
| TAX_KEEP | lead có tax_id | Keep |
| RATING_DROP | min_rating=4.0, lead rating=3.0 | Drop |
| RATING_KEEP | min_rating=4.0, lead rating=4.5 | Keep |
| RATING_NONE | min_rating=4.0, lead rating=None | Keep, `unrated_kept+=1` |
| VERIFIED_STRICT | require_verified, lead verified=None/False | Drop |
| VERIFIED_OK | verified=True | Keep |
| SPARSE_DROP | lead không company_name & không tax_id | Drop, `filtered_sparse_identity+=1` |
| OUTSIDE_LOC | lead city không match locations | Drop, `filtered_outside_locations+=1` |
| DEMAND_UNTOUCHED | direction=demand | Không filter, không counters |
| COUNTERS_VIZ | supply run | Counters trong result/meta đúng số |

## Code Map

| File | Vai trò |
|---|---|
| `nowing_backend/app/lead_intelligence/adapters/base.py:58-86` | `NormalizedLead` + `rating`/`verified` |
| `nowing_backend/app/lead_intelligence/adapters/enterprise.py` | set `verified=True` cho masothue records |
| `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:808-882` | `execute_and_persist` — filter seam trước `ingest_batch` |
| `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:74` | `LeadGenOrchestratorResult` — chỗ counters |
| `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` (`evaluate_hierarchical_location_match` / `pre_filter_by_icp`) | tái dùng location eval |
| `nowing_backend/tests/unit/lead_intelligence/test_supply_post_filter.py` | NEW — matrix trên |

## Tasks

- T1: `NormalizedLead` + `rating: float | None`, `verified: bool | None`; enterprise
  adapter set `verified=True` cho masothue records (kiểm chứng field serialize an toàn).
- T2: `_apply_supply_post_filter(leads, supply_criteria) -> tuple[kept, counters]`
  trong orchestrator (hoặc helper module nhỏ nếu cleaner) — gọi tại persist seam
  khi `direction == "supply"`.
- T3: Counters vào `LeadGenOrchestratorResult` (thêm field hoặc metadata dict —
  pin tên trong test).
- T4: `outside_locations` guard dùng `evaluate_hierarchical_location_match`.
- T5: Tests `test_supply_post_filter.py` — toàn bộ matrix + demand-untouched +
  counters-visibility.

## Acceptance Criteria

1. `require_tax_id` drop đúng, counter hiện diện trong result.
2. `min_rating` chỉ drop rated-thấp; `rating=None` giữ + `unrated_kept` đếm.
3. `require_verified` strict — None/False drop, True keep.
4. Sparse-identity guard drop lead thiếu cả company_name lẫn tax_id.
5. `outside_locations` drop lead không match `supply_criteria.locations`.
6. Demand path không filter, không counter — regression bit-for-bit.
7. Một filter site duy nhất — không filter ở planner.

## Spec Change Log

## Review Triage Log

## Design Notes

- `require_verified` + `muasamcong`: adapter này không set verified → với
  `require_verified=True` mọi lead của nó bị drop. Đúng semantics (hồ sơ đấu thầu
  không phải legal entity verified), đã chốt khi quyết giữ muasamcong.
- Counters nằm ở orchestrator result, không phải envelope — route `/campaigns/execute`
  trả `LeadGenOrchestratorResult` nguyên bản.
- Sparse-identity guard bắt buộc vì `generate_lead_hmac` fallback "Doanh nghiệp"
  khi thiếu company_name — lead sparse cùng value_hmac sẽ merge bẩn.

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/test_supply_post_filter.py -x -q` — all pass
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/ -x -q` — regression
