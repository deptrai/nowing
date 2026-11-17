---
title: 'Story 43.2 — Direction-aware adapter resolution (supply_eligible capability)'
type: 'feature'
created: '2026-11-17'
status: 'done'
baseline_revision: 'c456623df'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - _bmad-output/implementation-artifacts/epic-43-context.md
warnings: ['multiple-goals']
deferred: []
---

<intent-contract>

## Goal

Resolver adapter nhận `spec.direction`: supply → chỉ adapter `supply_eligible`
(enterprise + muasamcong), demand → giữ nguyên từng bit hành vi cũ.
Supply branch luôn return — tuyệt đối không rơi xuống demand heuristics
(intent-routing hoặc all-adapters) khi không match.

## Always

- Adapter base có `supply_eligible: bool = False`; `enterprise` và `muasamcong` set True.
- `resolve_adapters_for_spec` (`adapters/registry.py:139`): khi `direction=='supply'` →
  match theo `supply_criteria.categories` keyword trên supply_eligible; không match →
  trả TẤT CẢ supply_eligible. Không bao giờ fall-through.
- `resolve_adapters_for_campaign` (`adapters/registry.py:680`): propagate direction —
  khi supply, fallback chain của nó (category → intent → list_all) phải trả
  supply_eligible, không đụng demand path.
- Supply ordering = **thứ tự đăng ký cố định** (`list(self._adapters)` lọc
  supply_eligible), KHÔNG đọc `priority` bị mutate — deterministic.
- Không mutate `priority`/`lead_quota` trên shared adapter instances ở nhánh supply.
- Query synthesis vá CẢ 2 seam: `_build_query_for_adapter` (planner preflight) VÀ
  `effective_query` trong `execute_multi_source_lead_gen`
  (`lead_gen_orchestrator.py:546`) — supply + query rỗng → build từ
  `categories + locations`, không đọc `icp_criteria`.
- Dict spec: `spec.get("direction") if isinstance(spec, dict) else getattr(spec, "direction", "demand")`.
- ICP pre-filter (`pre_filter_by_icp` trên orchestrator path) no-op khi supply.
- `target_sources` explicit thắng cả 2 direction.
- Tests: fail-closed pin (supply không trả demand adapter), demand bit-for-bit.

## Never

- Không sửa adapter internals hay demand heuristics.
- Không thêm adapter mới, không tạo Maps adapter.
- Không đụng `MedirusMcpClient`, `medirus_proxy.py`.
- Không đổi signature public của 2 resolver (chỉ thêm nhánh trong thân).
- Không migrate.

## Decisions

- D1: supply_eligible = enterprise + muasamcong (masothue/registry trong enterprise;
  muasamcong giữ dù noisy — require_tax_id filter ở 43.3 xử).
- D2: supply ordering = registration order cố định, deterministic.
- D3: direction đọc qua helper `_spec_direction(spec)` duck-type an toàn cả dict/spec.

</intent-contract>

## I/O & Edge-Case Matrix

| Case | Input | Expected |
|---|---|---|
| DEMAND_UNCHANGED | direction="demand" | Bit-for-bit như trước (regression pin) |
| SUPPLY_MATCH | supply + categories=["enterprise","b2b"] | ≥1 supply_eligible match, KHÔNG demand adapter |
| SUPPLY_NO_MATCH | supply + categories=["xyz-lạ"] | Tất cả supply_eligible (2 adapter) |
| SUPPLY_FAIL_CLOSED | supply, bất kỳ input nào | 0 demand adapter trong kết quả |
| SUPPLY_DETERMINISTIC | 2 lần resolve cùng spec | Cùng ordering, không đọc priority đã mutate |
| WRAPPER_SUPPLY | resolve_adapters_for_campaign supply | Propagate, không demand fallback |
| TARGET_SRC_WINS | supply + target_sources=["x"] | target_sources thắng, bỏ qua direction |
| DICT_SPEC | spec là dict | direction đọc đúng qua helper |
| QUERY_PREFLIGHT | supply + query="" (planner) | _build_query_for_adapter synthesize |
| QUERY_EXECUTE | supply + query="" (orchestrator) | effective_query synthesize categories+locations |
| ICP_PREFILTER_NOOP | supply path orchestrator | pre_filter_by_icp không chạy |

## Code Map

| File | Vai trò |
|---|---|
| `nowing_backend/app/lead_intelligence/adapters/base.py` | Adapter base — thêm `supply_eligible: bool = False` |
| `nowing_backend/app/lead_intelligence/adapters/registry.py:139` | `resolve_adapters_for_spec` — supply branch |
| `nowing_backend/app/lead_intelligence/adapters/registry.py:680` | `resolve_adapters_for_campaign` — propagate |
| `nowing_backend/app/lead_intelligence/adapters/registry.py:74-108` | `_register_defaults` — gán supply_eligible cho enterprise + muasamcong |
| `nowing_backend/app/lead_intelligence/adapters/enterprise.py` | set `supply_eligible = True` |
| `nowing_backend/app/lead_intelligence/adapters/muasamcong.py` | set `supply_eligible = True` |
| `nowing_backend/app/lead_intelligence/campaign/planner.py` | `_build_query_for_adapter` — supply query synthesis |
| `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:546` | `effective_query` — supply synthesis ở execute path |
| `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py` (pre_filter_by_icp) | no-op khi supply |
| `nowing_backend/tests/unit/lead_intelligence/test_adapter_resolution_direction.py` | NEW — 10+ case matrix trên |

## Tasks

- T1: `supply_eligible: bool = False` trên adapter base; gán True cho enterprise + muasamcong.
- T2: `resolve_adapters_for_spec` nhánh supply: match categories trên supply_eligible →
  fallback tất cả supply_eligible → luôn return; đọc direction qua helper an toàn dict/spec.
- T3: `resolve_adapters_for_campaign` propagate direction — supply branch của nó
  trả supply_eligible (không đi qua category→intent→all chain).
- T4: Query synthesis 2 seam — `_build_query_for_adapter` + `effective_query`:
  supply && query rỗng → `", ".join(categories) + " " + ", ".join(locations)` hoặc tương đương.
- T5: `pre_filter_by_icp` (nơi orchestrator gọi) no-op khi `direction == "supply"`.
- T6: Tests `test_adapter_resolution_direction.py` — toàn bộ matrix + fail-closed +
  demand regression pin (snapshot thứ tự demand hiện tại trước khi thêm nhánh).

## Acceptance Criteria

1. Supply resolve chỉ trả `supply_eligible` adapters — 0 demand adapter, mọi
   input **trừ `target_sources` explicit** (escape hatch, giữ quyền thắng cao nhất).
2. Không match categories → trả tất cả supply_eligible (không rơi demand heuristic).
3. Ordering supply deterministic — registration order, không phụ thuộc `priority` đã mutate.
4. Demand path bit-for-bit — test cũ xanh, snapshot ordering không đổi.
5. `target_sources` explicit thắng direction cả 2 phía.
6. Dict spec đọc direction đúng; `pre_filter_by_icp` no-op khi supply.
7. Query synthesis cả 2 seam khi supply + query rỗng.

## Spec Change Log

## Review Triage Log

### 2026-11-17 — Review pass 1 (verification-gap + edge-case, 1 layer gộp)

Ghi chú: 4 layer review gốc chết đồng loạt lỗi API 403 (upstream down) — chạy lại
thành 1 agent gộp verification-gap + edge-case + self-review coordinator.

Verdicts: 1 high, 4 medium, 4 low, 3 reject — 4 patch.

- [high] [patch] VG1+VG2: `test_supply_match_returns_only_supply_adapters` không
  test match thật — keyword 'thầu' không substring-match haystack nào, nhánh
  `matched_supply` có thể xóa mà suite vẫn xanh (verified bằng tay).
  **Đã vá**: thay bằng 3 test match thật — `categories=["muasamcong"]` → đúng
  `['muasamcong']` (phân biệt match vs fallback), `["enterprise"]` → cả 2,
  case/diacritics-insensitive → `['muasamcong']`.
- [medium] [patch] E1: dict-spec `categories` non-list → TypeError crash (hoặc
  string lặp từng ký tự match nhiễu) tại registry.py:188 — đã guard
  `isinstance(list)` + comment.
- [medium] [patch] E3: keyword match không bỏ dấu tiếng Việt — inconsistent
  demand path (`_strip_vietnamese_diacritics` :226). Đã strip cả keyword lẫn
  haystack (haystack thêm cho an toàn khi source_name tương lai có dấu).
- [medium] [patch] VG3: AC1 chữ "mọi input" mâu thuẫn escape hatch `target_sources`
  (AC5). Đã sửa AC1: "mọi input trừ target_sources explicit".
- [medium] [reject] E2: match granularity — haystack chứa `category.value`
  chung ENTERPRISE khiến keyword "enterprise" match cả 2. Fail-closed an toàn;
  spec vốn định là filter thô — giữ nguyên, document.
- [low] [reject] E5: orchestrator/planner đọc `spec.direction` trực tiếp thay
  `_spec_direction` — chỗ đó đã giả định pydantic object (`campaign_spec.query`
  attribute access ngay dòng trên) — dict chỉ phục vụ registry path.
- [low] [reject] VG4: test ordering tautological (so với list_all cùng nguồn) —
  smoke test chấp nhận được.
- [low] [defer] VG5/E7: supply + `excluded_sources` rỗng pool →
  `location_fallback=True` telemetry sai nguyên nhân thật (exclusion không phải
  location). Nhỏ, chỉ ảnh hưởng telemetry.
- [low] [defer] E4: supply prefilter no-op gán `loc_score=100.0` giả — nhiễu
  location telemetry. Đổi thành None cần chỉnh signature consumer; defer.
- [info] E6: query synthesis nhân bản 2 seam theo spec T4 chủ đích — ràng buộc
  ngầm đã ghi Design Notes.

0 findings báo cáo không chính xác nào còn lại sau verify.

## Design Notes

- `pre_filter_by_icp` nằm trong orchestrator path (không phải planner) — supply spec
  đã bị cấm ICP non-default ở 43.1 nên nó sẽ no-op tự nhiên, nhưng pin explicit vẫn
  tốt hơn cho đường code tương lai.
- `priority` mutation trên shared instances là vấn đề demand-side có sẵn — supply
  không đụng, để nguyên (ponytail).
- Query synthesis format đơn giản: `" ".join(categories + locations)` — implementer
  pin chính xác trong test, không cần over-engineer.

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/test_adapter_resolution_direction.py -x -q` — all pass
- `cd nowing_backend && .venv/bin/python -m pytest tests/unit/lead_intelligence/ -x -q` — regression
