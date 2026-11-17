---
title: 'Story 43.4 — Lead role + visibility tagging qua extra_metadata'
type: 'feature'
created: '2026-11-17'
status: 'draft'
baseline_revision: ''
review_loop_iteration: 0
followup_review_recommended: false
context:
  - _bmad-output/implementation-artifacts/epic-43-context.md
warnings: []
deferred: []
---

<intent-contract>

## Goal

Supply leads được đánh dấu `lead_role="supplier"` + `campaign_direction` +
`campaign_key` + `visibility` trong `extra_metadata` tại call-site orchestrator —
KHÔNG trong `ingest_batch`. Demand không ghi `lead_role`. AD-1/AD-4 giữ nguyên.

## Always

- Tag nằm trong `lead_dict["extra_metadata"]` — dict merge JSONB đã có sẵn trong
  `_build_batch_upsert_stmt` (excluded wins theo key).
- Tag chỉ khi `direction == "supply"`:
  `{"campaign_direction": "supply", "lead_role": "supplier",
    "campaign_key": <spec.name>, "visibility": <spec.visibility>}`.
- Demand path KHÔNG thêm bất kỳ key nào trong 4 key trên.
- `campaign_key = spec.name` — CampaignSpec không có `id` (documented).
- `poolable` visibility = label thuần — không side-effect gì khác.
- Đặt tag tại chỗ build `lead_dicts` trong orchestrator (trước `ingest_batch`),
  không sửa `LeadBatchService`, `ingest_batch`, hay upsert stmt.

## Never

- Không sửa dedupe key `(workspace_id, value_hmac)` — AD-4.
- Không thêm column/field vào `Lead` DB model — không migration.
- Không tạo `campaign_leads` junction — deferred platform phase.
- Không tag khi direction demand.
- Không đổi semantics `client_id`.

## Decisions

- D1: `campaign_key` = `spec.name` (non-unique) — documented limitation, không
  có `campaign_id` trong mô hình hiện tại.
- D2: `lead_role` single-key last-write-wins — entity thuộc nhiều campaign
  đều là "supplier" theo lần ghi sau; accepted, junction table deferred.
- D3: tag merge qua `extra_metadata` có sẵn — upsert `concat` giữ key cũ của
  existing row khi excluded thiếu key; lead supply mới đè role đúng vì tag
  luôn được set ở excluded (dòng mới vào).

</intent-contract>

## I/O & Edge-Case Matrix

| Case | Input | Expected |
|---|---|---|
| SUPPLY_TAG | supply spec → ingest 1 lead | `extra_metadata` chứa đủ 4 key |
| DEMAND_CLEAN | demand spec → ingest | `extra_metadata` KHÔNG có `lead_role`/`campaign_direction` |
| ROLE_LWW | lead cũ role "buyer" → supply ghi lại | `lead_role="supplier"` (excluded wins) |
| VIS_LABEL | visibility="poolable" | `extra_metadata.visibility=="poolable"`, không hành vi khác |
| CAMPAIGN_KEY | spec.name="Thu mua trầm KH" | `campaign_key=="Thu mua trầm KH"` |
| METADATA_MERGE | lead có extra_metadata cũ `{foo:1}` | merge giữ `foo:1` + 4 key mới |

## Code Map

| File | Vai trò |
|---|---|
| `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:848` | `lead_dicts` build — chỗ thêm tag |
| `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:882` | `ingest_batch` call — tag đã vào `extra_metadata` trước đó |
| `nowing_backend/app/services/lead_batch_service.py:203-205` | upsert merge JSONB (tham chiếu, KHÔNG sửa) |
| `nowing_backend/app/services/lead_batch_service.py:106-108` | `extra_metadata` passthrough (tham chiếu) |
| `nowing_backend/tests/unit/lead_intelligence/test_supply_role_tagging.py` | NEW |

## Tasks

- T1: tại persist seam của orchestrator, khi `direction == "supply"`, inject
  4 key vào `lead_dict["extra_metadata"]` của từng lead (đọc direction theo
  cùng cơ chế `_spec_direction` đã dùng ở 43.2 — getattr/dict.get).
- T2: tests `test_supply_role_tagging.py`: supply → 4 keys đúng; demand → không
  key; last-write-wins role; visibility poolable là label; campaign_key =
  spec.name.

## Acceptance Criteria

1. Supply ingest → mọi lead có `extra_metadata.lead_role == "supplier"`,
   `campaign_direction == "supply"`, `campaign_key == spec.name`,
   `visibility == spec.visibility`.
2. Demand ingest → `extra_metadata` không chứa 4 key trên (không có `lead_role`).
3. Dedupe key/`ingest_batch` contract không đổi.
4. `visibility="poolable"` = label thuần.

## Spec Change Log

## Review Triage Log

## Design Notes

- Vì sao tag ở orchestrator không ở `ingest_batch`: service layer không biết
  direction (chỉ nhận dicts) — AD-1 giữ funnel nhưng tag là concern của
  campaign layer. Giống cách `source`/`client_id` được set ở caller.
- Last-write-wins trên `lead_role`: upsert merge `extra_metadata` — excluded
  (incoming) key thắng. Đúng mong muốn: cùng entity vào campaign supply mới
  → role mới nhất.
- Không dùng `LeadActivityLog` — đó là activity stream, không phải entity attr.

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/test_supply_role_tagging.py -x -q` — all pass
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/ -x -q` — regression
