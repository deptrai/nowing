---
title: 'Story 43.1 — CampaignSpec direction fields + AD-5 joint validation'
type: 'feature'
created: '2026-11-17'
status: 'done'
baseline_revision: 'cd5c18aed82bb023b433e2f234a04a1a336fbcc4'
review_loop_iteration: 1
followup_review_recommended: false
context: []
warnings: []
deferred:
  - summary: >-
      CampaignSpec không bật validate_assignment; model_copy(update=...) bypass
      model_validator → mutation post-construction vi phạm AD-5.
    evidence: >-
      Latent — không consumer nào mutate spec hiện nay (verification-gap
      verify). Revisit nếu xuất hiện caller đổi direction/fields.
    location: nowing_backend/app/lead_intelligence/campaign/schemas.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** `CampaignSpec` chỉ hiểu một chiều demand (seller → tìm buyer). Epic 43 cần chiều supply (buyer → tìm nhà cung cấp) trên cùng engine — bước đầu là schema phải khai báo được direction mà không phá demand path hiện tại.

**Approach:** Thêm 5 field direction-scoped vào `CampaignSpec` + nested `SupplyCriteria` + `model_validator(mode="after")` reject mọi tổ hợp vô nghĩa semantics ngay tại schema layer (AD-5) — không rải check ở routes/orchestrator.

## Boundaries & Constraints

**Always:**
- 5 field mới: `direction: Literal["demand","supply"]="demand"`, `match_mode: Literal["mine","pool","hybrid"]="mine"`, `supply_criteria: SupplyCriteria|None=None`, `corpus_scope: Literal["workspace","platform_b2b"]="workspace"`, `visibility: Literal["private","poolable"]="private"` — tất cả default-safe (demand-shaped spec cũ parse không đổi).
- `SupplyCriteria`: `categories: list[str]` (min_length=1), `locations: list[str]` (min_length=1), `require_tax_id: bool=True`, `min_rating: float=0.0` (ge=0.0, le=5.0), `require_verified: bool=False`.
- Validation tập trung `model_validator(mode="after")` trên `CampaignSpec` — truth-table đầy đủ (mọi ô = 1 case parametrize, xem matrix dưới).
- Phép so sánh icp non-default pin: `spec.icp_criteria != ICPCriteria()` — instance tương đương default PHẢI pass (executor cũ build `ICPCriteria(target_categories=[], min_fit_score=0.0)`).
- Extra-config của `SupplyCriteria` theo convention `CampaignSpec` hiện có trong file (check `model_config` của class cha rồi copy — KHÔNG tự quyết `extra="forbid"`).

**Never:**
- KHÔNG đụng `adapters/registry.py`, `planner.py`, `lead_gen_orchestrator.py` — routing/post-filter là story 43.2/43.3.
- KHÔNG đổi field cũ của `CampaignSpec` hay `ICPCriteria` — chỉ additive.
- KHÔNG thêm `campaign_id`/`id` — campaign identity là `spec.name` (documented limitation).
- KHÔNG đổi signature `from_payload`/`from_campaign_create_input` — chúng đọc dict, field mới vào qua key mặc định; story 43.5 mới nối supply branch.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| DEMAND_DEFAULT | payload thiếu 5 field mới | parse OK, `direction="demand"`, hành vi y hệt cũ | — |
| SUPPLY_OK | `direction="supply"` + `supply_criteria{categories:["trầm hương"],locations:["Khánh Hòa"]}` | parse OK | — |
| SUPPLY_NO_CRITERIA | `direction="supply"`, `supply_criteria=None` | — | 422 ValidationError |
| DEMAND_WITH_CRITERIA | `direction="demand"` + `supply_criteria` set | — | 422 |
| POOL_GATED | `match_mode="pool"` hoặc `"hybrid"` (mọi direction) | — | 422 (platform phase) |
| CORPUS_GATED | `corpus_scope="platform_b2b"` | — | 422 |
| SUPPLY_EMPTY | `supply_criteria{categories:[],locations:[]}` | — | 422 (min_length) |
| SUPPLY_ICP_MIX | `direction="supply"` + `icp_criteria` non-default | — | 422 |
| SUPPLY_ICP_EQUIV | `direction="supply"` + `icp_criteria == ICPCriteria()` | parse OK | — |
| SUPPLY_TRIGGERS | `direction="supply"` + `signal_triggers`/`intent_tags` non-empty | — | 422 |
| SUPPLY_TARGET_SRC | `direction="supply"` + `target_sources=["enterprise"]` | parse OK (escape hatch, documented) | — |
| DEMAND_VISIBILITY | `direction="demand"` + `visibility="poolable"` | parse OK (nhãn inert) | — |
| BOUNDS | `min_rating=-1` / `min_rating=5.1` | — | 422 |
| FE_OLD | `from_campaign_create_input` với payload cũ (không key mới) | parse OK | — |

</intent-contract>

## Code Map

- `nowing_backend/app/lead_intelligence/campaign/schemas.py` — FILE SỬA DUY NHẤT phía model: `CampaignSpec` (:113-159, Pydantic-only, không persisted), `ICPCriteria` (:96-113), `from_payload` (:162), `from_campaign_create_input` (:169). Check `model_config` của `CampaignSpec` để copy convention sang `SupplyCriteria`.
- `nowing_backend/tests/unit/lead_intelligence/` — test dir convention (đã có `test_lead_stream_buffer.py` từ epic 42). File mới `test_campaign_spec_direction.py`.
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:64-78` — caller build `ICPCriteria(target_categories=[], min_fit_score=0.0)` (default-equivalent) — test `SUPPLY_ICP_EQUIV` phải cover trường hợp này.
- `nowing_backend/app/routes/campaign_routes.py:137-152` — route catch `ValidationError` → 422 (đã tồn tại, không sửa).

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/lead_intelligence/campaign/schemas.py` — thêm `SupplyCriteria` BaseModel + 5 field vào `CampaignSpec` + `model_validator(mode="after")` truth-table — validation tập trung.
- `nowing_backend/tests/unit/lead_intelligence/test_campaign_spec_direction.py` — NEW — `pytest.mark.parametrize` mọi ô truth-table + bounds + `from_payload`/`from_campaign_create_input` old-payload regression — AC pin "không ô nào silently pass".

**Acceptance Criteria:**
- Given spec demand-shaped hiện tại (thiếu field mới), when `model_validate`/`from_payload`/`from_campaign_create_input`, then parse y hệt cũ — regression test.
- Given mỗi ô I/O matrix, when construct `CampaignSpec`, then hành vi đúng bảng — parametrize, không silent pass.
- Given `supply_criteria` bounds ngoài (`min_rating<0`, `>5`, categories/locations rỗng), when validate, then 422.

## Spec Change Log

### 2026-11-17 — post-review

1. **Deviation vs Never "đừng đụng routes"**: thêm guard `spec.direction != "demand" → 422` tại `campaign_routes.py` plan + execute, và guard non-default direction keys trong `from_campaign_create_input`. Lý do: review phát hiện supply intent silently chạy demand pipeline (billing harm) — intent-gap spec chưa lường (spec chỉ định schema, không định boundary giữa 43.1 và 43.5). Guards đánh dấu "gỡ ở 43.5/43.6".
2. `SupplyCriteria.categories/locations` items: `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]` (item-level, thay vì chỉ list-level).
3. Validator docstring liệt kê rõ demand-shaped fields ĐƯỢC phép trên supply (query, location_profile, target_sources, source_budgets, excluded_sources) — chốt allowed-side thay vì để ngầm.

## Review Triage Log

### 2026-11-17 — Review pass 1 (4 layers)

Layers: blind-hunter (N=5, 8 findings) · edge-case-hunter (9) · verification-gap (2 gaps + 2 latent) · intent-alignment (COMPLIANT — khớp trục B model_validator; lưu ý intent "→ 422" là model-level `ValidationError`, route 422 đi qua except sẵn có).

Verdicts: **3 medium / 4 low / 2 deferred / rest false**. ~20 raw findings → dedupe thành 6 nhóm.

#### [medium] [patch] Supply intent silently mất giữa parse và execution (BH1+VG1+EC1+EC8+BH2 — 5 layer hội tụ)

Hai mặt cùng một gốc:
1. `from_campaign_create_input` không forward 5 direction field → FE payload mang `direction:"supply"` silently thành demand spec.
2. Spec supply hợp lệ đi thẳng vào demand engine qua `/campaigns/plan` + `/campaigns/execute` → tốn credits quét rác (VG: billing endpoint).
3. Test `test_from_campaign_create_input_still_rejects_supply_direction_keys` KHÔNG chứa key direction — coverage giả.

Patch (deviation có chủ đích vs Never "đừng đụng routes" — intent-gap, xem Change Log):
- `from_campaign_create_input`: raise ValueError khi payload mang direction-scoped key non-default (`direction/match_mode/corpus_scope/visibility` khác default hoặc `supply_criteria` set). Gỡ ở 43.5.
- `campaign_routes.py` plan + execute: `spec.direction != "demand"` → 422 "chưa được hỗ trợ thực thi (Epic 43 in progress)". Guard tạm, gỡ ở 43.6.
- Test sửa: payload thật chứa direction keys → assert raise; +2 test route guard (direct async call, `TestSupplyExecutionGuard`).

#### [medium] [patch] Item-level validation cho categories/locations (BH3+EC6)

`min_length=1` chỉ chặn list rỗng; `[""]`/`["   "]` pass. → `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]` trên items + 2 test mới.

#### [low] [patch] Matrix cells thiếu + match= (BH5+EC9+IA)

Thêm: corpus_gated × {demand,supply} parametrize; supply+visibility=poolable; categories=[] vs locations=[] tách case; direction literal lạ → ValidationError; `match=` pin "requires supply_criteria"/"platform phase"/"must not set non-default icp_criteria".

#### [low] [patch] Demand-shaped fields allowed vs forbidden — docstring (BH4+EC2+EC3+BH7)

EC2 (reject location_profile) + EC3 (reject query) **reject** — phá design 43.5: wire contract derive `location_profile` từ `supply_criteria.locations[0]`, form có free-text `query`. → Không guard; docstring validator liệt kê rõ field được phép trên supply (query, location_profile, target_sources, source_budgets, excluded_sources). `description=` thêm cho 5 field (BH8).

#### [defer] Mutation bypass: validate_assignment/model_copy (VG+EC4+EC5)

`model_validator` không chạy lại khi assign/`model_copy(update=)`. Không consumer nào mutate spec hiện nay (VG verify). → deferred-work, kèm note khi nào revisit.

#### [reject/false]

- EC7 `ICPCriteria` extra='ignore' nuốt typo key → convention sẵn có, ngoài scope diff.
- IA A2-reading (422 HTTP-level tests) → intent đọc A1 model-level đúng; HTTP-level là việc 43.6 e2e.
- EC2/EC3 guard location_profile/query → phá 43.5 design (trên).

#### Spec doc sửa

Code Map note `ICPCriteria` default-equivalent: builder programmatic thật là `executor.py`/`orchestrator_tool.py` (build NON-default ICP) — đường supply tuyệt đối không reuse chúng.

## Design Notes

- `visibility` là nhãn inert phase này (persist no-op ở story 43.4) — hợp lệ cả 2 direction, không nằm trong truth-table reject.
- `match_mode`/`corpus_scope` tồn tại chỉ để reject — contract đặt trước, engine pool phase Platform.
- `supply_criteria={}` (object rỗng) tự fail min_length của `SupplyCriteria` trước khi đến truth-table — không cần ô riêng.

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/test_campaign_spec_direction.py -x -q` — expected: all pass
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/ -x -q` — expected: không regression

## Auto Run Result

- **Implement (subagent)**: `SupplyCriteria` (categories/locations `Annotated` item-level, `require_tax_id`, `min_rating` 0–5, `require_verified`) + 5 fields `direction/match_mode/supply_criteria/corpus_scope/visibility` + `model_validator` truth-table. Test mới `test_campaign_spec_direction.py`.
- **Review (4 layers)**: 1 intent-gap lớn — supply intent silently thành demand tại 2 boundary (converter + route). Patch: guard 422 tạm cả hai phía + item-level validation + test matrix bổ sung.
- **Verification**: 29 passed (file spec); regression `tests/unit/lead_intelligence/` + route sweeps = 383 passed.
- **Files**: `nowing_backend/app/lead_intelligence/campaign/schemas.py` (M), `nowing_backend/app/routes/campaign_routes.py` (M — guard tạm, gỡ 43.6), `nowing_backend/tests/unit/lead_intelligence/test_campaign_spec_direction.py` (new).
