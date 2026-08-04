---
baseline_commit: cca81a7f6d5060ada95766d2fec418375f09fd9a
baseline_branch: develop
story_key: 10-4-vn-bds-aggregator
status: done
---

# Story 10.4: Vietnam BĐS Listing Aggregator & Cross-Source Trust Score

**Story ID:** 10.4
**Epic:** 10 — Connector & Scraper Expansion
**Title:** Vietnam BĐS Listing Aggregator & Cross-Source Trust Score
**Status:** in-progress
**Priority:** HIGH
**Requirements:** FR-6, FR-32, FR-39
**Architecture:** AD-3, AD-11.1, AD-16, AD-19
**Dependencies:** 10.1 batdongsan.scrape, 10.2 chotot_bds.scrape, 10.3 muaban_bds.scrape

---

## 1. Goal

Thêm capability `vn_bds.aggregate` gom dữ liệu tin rao bất động sản từ các nguồn Vietnamese BĐS hiện có (`batdongsan`, `chotot_bds`, `muaban_bds`), chuẩn hóa về schema chung, loại trùng, phát hiện xung đột giá, tính `confidence_score`, và expose qua REST, agent chat và MCP.

**Non-goal:**
- Không scrape thêm nguồn mới — chỉ sử dụng P0 scrapers đã có.
- Không lưu aggregated listing vào `Memory`/`ResearchThread` trong V1 — output là capability result.
- Không resolve ảnh hash / địa chỉ bằng geocoding — dùng heuristic cơ bản.

---

## 2. User Story

> As a real-estate researcher,
> I want the system to merge and score listings from multiple Vietnamese BĐS sources,
> So that I can trust the price and detect fake/duplicate listings.

---

## 3. Acceptance Criteria

### AC-1 — Normalize listings từ nhiều nguồn
**Given** input `vn_bds.aggregate` chỉ định `sources` (`batdongsan`, `chotot_bds`, `muaban_bds`), `city`, tùy chọn `district`, `property_type`, `min/max price/area`,
**When** capability chạy,
**Then** nó gọi song song các child scrapers, parse kết quả về schema chung `VnBdsAggregatedListing` với `title`, `price`, `price_value`, `area`, `district`, `city`, `phone_key`, `contact`, `post_date`, `detail_urls`, `thumbnail_url`, `source_ids`.

### AC-2 — Tính `confidence_score`
**Given** một listing đã chuẩn hóa,
**When** qua scoring,
**Then** `confidence_score` trong `[0.0, 1.0]` được tính từ: `source_trust` (nguồn xác thực), `overlap_score` (số nguồn trùng), `freshness_score` (post_date), và `price_consistency_score` (độ tương đồng giá giữa các nguồn).

### AC-3 — Phát hiện xung đột giá
**Given** cùng listing xuất hiện ở >=2 nguồn với giá parse được,
**When** khoảng cách giá lệch >20%,
**Then** `conflict_flags` chứa `ConflictFlag(type="price_conflict", reason="...", price_range, price_sources)`.

### AC-4 — Deduplicate
**Given** nhiều listing từ các nguồn khác nhau,
**When** chúng có cùng `phone_key`, `address_key` hoặc `image_key`,
**Then** chúng merge thành một `VnBdsAggregatedListing` duy nhất với `source_count > 1`, `sources` đầy đủ, `source_prices` mapping, và `canonical_id` xác định.

### AC-5 — Billing & metering
**Given** một lần aggregate thành công,
**When** run hoàn tất,
**Then** nó tính phí `VN_BDS_AGGREGATE_QUERY` (default 5,000 micros/query) cộng chi phí child scrapers theo số item mỗi nguồn, trả về `cost_micros`, `degraded`, `degradation_reasons`.

### AC-6 — MCP / REST / Agent exposure
**Given** capability đã build,
**When** dùng REST, agent chat hoặc MCP,
**Then** `vn_bds.aggregate` / `nowing_vn_bds_aggregate` khả dụng với input `VnBdsAggregateInput` và output `VnBdsAggregateOutput`.

### AC-7 — Test coverage
**Given** code aggregator,
**Then** có unit tests cho normalize, dedupe, scoring, orchestrator; integration test cho billing, provenance; và billing test cho `VN_BDS_AGGREGATE_QUERY`.

---

## 4. Tasks / Subtasks

- [x] Thêm `VN_BDS_AGGREGATE_QUERY` billing unit và rate config (AC #5)
  - [x] Thêm enum vào `app/capabilities/core/types.py`
  - [x] Đăng ký micros/query trong `app/config/__init__.py` và `.env.example`
  - [x] Cập nhật `app/capabilities/core/billing.py` để xử lý unit mới
- [x] Tạo Pydantic schemas (AC #1, #6)
  - [x] `VnBdsAggregateInput` / `VnBdsAggregateOutput`
  - [x] `VnBdsAggregatedListing`, `ConflictFlag`, `VnBdsProvenance`
- [x] Xây service modules `app/services/bds_aggregator/` (AC #1, #2, #3, #4)
  - [x] `normalize.py` — chuẩn hóa từng listing, parse price/area/date/phone, mask PII
  - [x] `dedupe.py` — merge theo phone/address/image, giữ `source_prices`
  - [x] `scoring.py` — tính confidence, conflict, freshness
  - [x] `orchestrator.py` — fan-out to child scrapers, aggregate, filter theo `min_confidence`
- [x] Đăng ký capability `app/capabilities/vn_bds/aggregate/` theo pattern `batdongsan.scrape` (AC #6)
  - [x] `definition.py` (`build_capabilities_router`)
  - [x] `executor.py` (wrap orchestrator, handle exception → degraded)
  - [x] `schemas.py` (capability input/output)
- [x] Wire registries (AC #6)
  - [x] `app/routes/__init__.py` import namespace
  - [x] `app/mcp_tools.py`
  - [x] `nowing_mcp/mcp_server/features/scrapers/platforms/vn_bds.py`
  - [x] `nowing_mcp/mcp_server/features/scrapers/__init__.py`
  - [x] `nowing_mcp/mcp_server/server.py`
  - [x] `nowing_web/app/(home)/mcp-server/page.tsx`
- [x] Viết tests (AC #7)
  - [x] Unit tests `tests/unit/services/bds_aggregator/`
  - [x] Capability unit tests `tests/unit/capabilities/vn_bds/aggregate/`
  - [x] Integration tests `tests/integration/capabilities/vn_bds/aggregate/`

---

## Traceability

| AC | Code chính | Test |
|---|---|---|
| AC-1 | `app/services/bds_aggregator/normalize.py`, `orchestrator.py` | `tests/unit/services/bds_aggregator/test_normalize.py`, `test_orchestrator.py` |
| AC-2 | `app/services/bds_aggregator/scoring.py` | `tests/unit/services/bds_aggregator/test_scoring.py` |
| AC-3 | `app/services/bds_aggregator/scoring.py` (`ConflictFlag`) | `tests/unit/services/bds_aggregator/test_scoring.py` |
| AC-4 | `app/services/bds_aggregator/dedupe.py` | `tests/unit/services/bds_aggregator/test_dedupe.py` |
| AC-5 | `app/capabilities/core/billing.py`, `app/capabilities/vn_bds/aggregate/executor.py` | `tests/integration/capabilities/vn_bds/aggregate/test_vn_bds_aggregate.py` |
| AC-6 | `app/capabilities/vn_bds/aggregate/definition.py`, `app/routes/__init__.py`, `nowing_mcp/...` | `tests/unit/capabilities/vn_bds/aggregate/test_executor.py` |
| AC-7 | — | `tests/unit/services/bds_aggregator/*`, `tests/unit/capabilities/vn_bds/aggregate/*`, `tests/integration/capabilities/vn_bds/aggregate/*` |

---

## 5. Dev Notes

### Architecture & License
- **AD-3:** `app/capabilities/vn_bds/aggregate/` export `build_capabilities_router()`; mỗi lần gọi tạo một `Run` row.
- **AD-11.1:** Mỗi `VnBdsAggregatedListing` có `provenance` liên kết `source_capability = "vn_bds.aggregate"` và `source_input`.
- **AD-16:** Logic aggregator (normalize/dedupe/scoring/orchestrator) nằm trong `app/services/bds_aggregator/` (Apache-2.0, shared service); capability contract nằm trong `app/capabilities/vn_bds/aggregate/` (Apache-2.0). Không có logic proprietary mới.
- **AD-19:** Một child scraper bị lỗi/rate-limit không làm fail toàn bộ aggregate — chúng được đánh dấu `degraded=true` trong `source_breakdown` và aggregate tiếp tục với các nguồn còn lại.

### Technical Details
- **Fan-out:** `asyncio.gather` các child `*.scrape` capability theo `payload.sources`.
- **Child payload:** tự động map `city`, `district`, `property_type`, `min/max_price`, `min/max_area`, `max_items_per_source`, `max_pages`, `resolve_phones`.
- **Batdongsan city code:** `to_batdongsan_city_code()` hỗ trợ alias tự do (`Hà Nội`, `Hồ Chí Minh`, `Đà Nẵng`, ...) → `HN`, `SG`, `DN`.
- **Phone normalization:** bỏ `0`/ `+84`/ `84`, dùng 9 chữ số lõi để dedupe; `contact` mask dạng `0901xxx67` để tránh leak PII.
- **Price parsing:** hỗ trợ `Tỷ` / `Triệu` / `Nghìn`, ký hiệu `m²`/`m2`; `thỏa thuận` trả `None`.
- **Area parsing:** hỗ trợ `m²`, `m2`, `mét vuông`, `ha`, và kích thước dạng `5x20m`.
- **Confidence:**
  - `source_trust` = tĩnh theo nguồn (`batdongsan=0.45`, `chotot_bds=0.35`, `muaban_bds=0.35`).
  - `overlap_score` = `source_count / 3` (vì tối đa 3 nguồn P0).
  - `freshness_score` = 1.0 nếu post_date <= 7 ngày, giảm dần về 0.0 ở >=90 ngày.
  - `price_consistency_score` = `1 - (std / mean)` giữa các `source_prices`, clamp `[0, 1]`.
  - `confidence_score` = weighted sum: `0.25*source_trust + 0.35*overlap + 0.15*freshness + 0.25*price_consistency`.
- **Conflict:** khi `price_consistency_score < 0.8`, tạo `ConflictFlag` với `price_range` và `price_sources`.

### Output & Billing
- `VnBdsAggregateOutput` chứa `items`, `cost_micros`, `degraded`, `degradation_reasons`, `source_breakdown`.
- `VN_BDS_AGGREGATE_QUERY` default 5,000 micros ($0.005) mỗi aggregate query.
- Chi phí child scraper cộng thêm dựa trên số item mỗi nguồn × rate tương ứng (`BATDONGSAN_SCRAPE_MICROS_PER_ITEM`, `CHOTOT_BDS_SCRAPE_MICROS_PER_ITEM`, `MUABAN_BDS_SCRAPE_MICROS_PER_ITEM`).
- Child run bị `degraded=true` không bị tính phí.

### Error Handling
- `degradation_reasons` typed: `api_error`, `rate_limited`, `unknown_city`, `invalid_input`, `unknown`.
- Tổng lỗi orchestrator → executor trả `degraded=true` với `degradation_reasons=["api_error"]`.
- Không log PII; `phone_key` bị `exclude=True`, `contact` đã mask.

### Testing
- Unit tests cover normalize, dedupe, scoring, orchestrator với fake child executors.
- Integration test verify billing gate + charge via `TokenUsage` và provenance propagation.
- Billing test verify `BillingUnit.VN_BDS_AGGREGATE_QUERY` và config rate.

---

## 6. References

- Epic: `_bmad-output/planning-artifacts/epics.md` §Story 10.4
- PRD FR-6 Built-in Scraper Connectors: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §4.2
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-3, AD-11.1, AD-16, AD-19
- Pattern capability: `nowing_backend/app/capabilities/batdongsan/scrape/`
- Pattern aggregate service: `nowing_backend/app/services/bds_aggregator/`
- Billing / types: `nowing_backend/app/capabilities/core/billing.py`, `nowing_backend/app/capabilities/core/types.py`

---

## Dev Agent Record

### Implementation Notes

- Triển khai theo pattern capability hiện có: `app/capabilities/vn_bds/aggregate/` gồm `definition.py`, `executor.py`, `schemas.py`.
- Tách core aggregator thành `app/services/bds_aggregator/` (`normalize.py`, `dedupe.py`, `scoring.py`, `orchestrator.py`, `schemas.py`) để reusable và dễ test.
- Orchestrator gọi child scrapers qua `get_capability(...).executor` trong production; hỗ trợ inject `source_executors` dict cho unit test.
- Thêm `VN_BDS_AGGREGATE_QUERY` billing unit, rate default 5000 micros, và cập nhật `charge_capability`/`gate_capability` trong `app/capabilities/core/billing.py`.
- Đăng ký đầy đủ: REST (`app/routes/__init__.py`), MCP tool (`app/mcp_tools.py`, `nowing_mcp/...`), marketing page (`nowing_web/app/(home)/mcp-server/page.tsx`).
- Mở rộng `app/capabilities/vn_bds/__init__.py` để auto-register `vn_bds.aggregate` cùng với các capability `batdongsan`/`chotot_bds`/`muaban_bds` hiện có.

### Debug Log

- `ruff format` reformat nhiều file mới và file test.
- `ruff check` sạch trên `app/capabilities/vn_bds`, `app/services/bds_aggregator`, và các test package.
- `pytest` unit 28 tests pass; integration 3 tests pass.
- Không có type checker (`mypy`/`pyright`) được cài trong môi trường hiện tại nên chưa chạy typecheck.
- Pre-existing test failures bên ngoài scope (ví dụ `test_research_fallback.py` liên quan relation `chunks` test DB) không đề cập.

### Completion Notes

- ✅ Story 10.4 hoàn thành implementation: toàn bộ AC 1-7 được đáp ứng, unit + integration tests pass, ruff sạch.
- Trạng thái cần chuyển `sprint-status.yaml` từ `in-progress` sang `review` hoặc `done` sau khi code-review hoàn tất.
