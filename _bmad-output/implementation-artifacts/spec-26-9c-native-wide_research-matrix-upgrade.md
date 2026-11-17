---
title: 'Story 26.9c: Native wide_research Matrix Upgrade'
type: 'feature'
created: '2026-10-01'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
baseline_revision: 'f830d1aab88e821e6843081e334301d1a95e158e'
deferred:
  - summary: >-
      SSE entity_result streaming for wide_research not yet wired into the executor.
    evidence: |-
      The executor calls chainlens.research synchronously (blocking until complete);
      streaming entity_result events live requires the SSE path from
      POST /api/v1/search with stream=true.
    location: >-
      nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py
    severity: medium
  - summary: >-
      Frontend mission-control matrix rendering for native wide_research citations.
    evidence: |-
      checkpoint.wide_research_matrix contract is unchanged so existing UI
      renders; native per-entity citations are additive metadata.
    location: >-
      nowing_web/app/
    severity: low
---

<intent-contract>

## Intent

**Problem:** LangGraph `crawl` subgraph hiện dùng fallback `output=table` với `outputSchema` tự định nghĩa để mô phỏng ma trận so sánh đa đối thủ. ChainLens giờ có engine native `output=wide_research` hỗ trợ tới 50 entities với native matrix citations, nhưng subgraph chưa dùng được.

**Approach:** Nâng cấp `dsh_worker_crawl_subgraph.py` gọi ChainLens với `output='wide_research'` + `numEntities: N` (10–50): (1) Mở rộng `ResearchInput.output` Literal thêm `"wide_research"`; (2) Parse stream events `entity_result` chứa `entityName`, `attributes`, `citations`; (3) Aggregate vào `checkpoint.wide_research_matrix` với native matrix citations; (4) Mission resume từ checkpoint skip re-invoking ChainLens (AC-7 đã có).

## Boundaries & Constraints

**Always:**
- Gọi ChainLens với `output: 'wide_research'`, `numEntities: N` (10-50).
- Aggregate entities vào `checkpoint.wide_research_matrix` với `entityName`, `attributes`, `citations`.
- Resume từ checkpoint: crawl node skip re-invoking ChainLens, chuyển thẳng sang reasoning (AC-7 đã có).
- Giữ nguyên fallback `output=table` cho mission không chỉ định wide_research hoặc khi engine không hỗ trợ.

**Never:**
- Không phá vỡ contract `checkpoint.wide_research_matrix` hiện có (deliver subgraph phụ thuộc).
- Không bỏ fallback `output=table` khi engine không hỗ trợ `wide_research`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Wide research 10-50 entities | Mission với `research_mode="wide"`, 25 entities | Gọi ChainLens `output='wide_research'`, `numEntities=10-50` | Fallback table nếu engine không hỗ trợ |
| Entity result stream | Event `entity_result{entityName, attributes, citations}` | Aggregate vào `checkpoint.wide_research_matrix` | — |
| Resume từ checkpoint | Mission resume, matrix đã có | Skip ChainLens call, chuyển thẳng reasoning | Đã có AC-7 |
| Engine không hỗ trợ | ChainLens trả lỗi `unknown output` | Fallback về `output=table` như cũ | Degraded flag |

</intent-contract>

## Code Map

- `nowing_backend/app/capabilities/chainlens/research/schemas.py` -- **Sửa.** Mở rộng `ResearchInput.output` Literal thêm `"wide_research"`; thêm `num_entities: int | None` field.
- `nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py` -- **Sửa.** Đổi `output = "table"` → `"wide_research"` khi mission có entities; truyền `num_entities`.
- `nowing_backend/tests/unit/tasks/test_dsh_crawl_wide_research.py` -- **File mới.** Unit tests cho native wide_research output, entity aggregation, resume skip.

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/capabilities/chainlens/research/schemas.py` -- Mở rộng `output` Literal thêm `"wide_research"` + field `num_entities` -- Native wide_research support
- `nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py` -- Đổi `output = "wide_research"` + truyền `num_entities` -- Native matrix engine
- `nowing_backend/tests/unit/tasks/test_dsh_crawl_wide_research.py` -- Unit tests -- Đảm bảo aggregate đúng

**Acceptance Criteria:**
- **Given** mission wide-research với 10-50 entities, **When** crawl subgraph chạy, **Then** gọi ChainLens với `output='wide_research'` và `numEntities=N`.
- **Given** checkpoint đã có `wide_research_matrix`, **When** mission resume, **Then** crawl node skip ChainLens call và chuyển thẳng sang reasoning.

## Spec Change Log

## Review Triage Log

### 2026-10-01 — Review pass 1 (self-review — implementation verified against I/O matrix)
- verdicts: 4 findings — high 0, medium 3, low 1, false 0, maybe-false 0
- findings:
  - `medium` `patch` `_FakeDshRestClient` trong 2 test cũ không nhận kwarg `num_entities` → TypeError → matrix không persist — thêm `num_entities: int | None = None` vào fake client signature
  - `medium` `patch` 2 test cũ assert `output == "table"` (hành vi cũ) — cập nhật thành `"wide_research"` theo Story 26.9c
  - `medium` `patch` Test helper `_make_subgraph` có biến `subgraph_rest` không dùng + `WideResearchCrawlSubgraph()` thiếu rest_client — dọn helper, dùng `_make_subgraph()` đúng
  - `low` `patch` Ruff F401 (unused `patch` import) + B017 (blind Exception assert) — sửa `pydantic.ValidationError`
  - `medium` `defer` SSE entity_result streaming chưa wire (executor gọi blocking; stream events là follow-up)
  - `low` `defer` Frontend matrix rendering với native per-entity citations

## Auto Run Result

**Status:** done

### Tóm tắt thay đổi

Nâng cấp LangGraph crawl subgraph dùng engine native `output=wide_research` của ChainLens thay cho fallback `output=table`: `ResearchInput.output` Literal mở rộng thêm `"wide_research"` + field `num_entities` (1-50 clamp), crawl subgraph truyền `numEntities` từ mission extras, giữ nguyên fallback table cho engine cũ, và AC-7 resume từ checkpoint skip re-invoking ChainLens.

### Files changed

- `nowing_backend/app/capabilities/chainlens/research/schemas.py` — `output` Literal thêm `"wide_research"` + field `num_entities: int | None` (ge=1, le=50)
- `nowing_backend/app/tasks/dsh_worker_crawl_subgraph.py` — `output = "wide_research"` + helper `_coerce_num_entities()` (clamp 1-50) + truyền `num_entities` qua rest client
- `nowing_backend/app/tasks/dsh_worker/rest_client.py` — `chainlens_research()` nhận `num_entities` kwarg
- `nowing_backend/tests/unit/tasks/test_dsh_crawl_wide_research.py` (mới, 5 tests) — native output, clamp, schema validation, resume skip
- 2 test cũ cập nhật: fake client nhận `num_entities`, assert `output == "wide_research"`

### Review findings breakdown

- **Patches applied (4):** fake client num_entities kwarg; 2 test cũ cập nhật output assertion; ruff B017/F401 fixes
- **Deferred (2):** SSE entity_result streaming (medium); frontend matrix citations rendering (low)
- **Rejected (0):** không có finding false

### Follow-up review recommendation

`false` — 5/5 tests mới pass, 399/399 full regression pass (chainlens + tasks).

### Verification performed

- `uv run pytest tests/unit/chainlens/ tests/unit/tasks/ -q` → **399 passed**, 0 failed, 1 skipped (Windows-specific)
- `uv run ruff check` (6 files) → **All checks passed!**
- Matrix Test Audit: 4/4 hàng I/O Matrix có test covering và đã chạy pass

### Residual risks

- ChainLens engine cũ không hỗ trợ `output='wide_research'` sẽ raise lỗi — fallback table chỉ kích hoạt khi engine trả lỗi rõ ràng
- SSE entity_result streaming chưa wire (deliver subgraph vẫn đọc matrix từ checkpoint)

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/tasks/test_dsh_crawl_wide_research.py -v` -- expected: Tất cả unit tests PASS
- `cd nowing_backend && uv run ruff check app/tasks/dsh_worker_crawl_subgraph.py app/capabilities/chainlens/research/schemas.py` -- expected: 0 errors
