---
baseline_commit: b9972636fa41737129a15463c37e2e334ed5e499
baseline_branch: develop
story_key: 10-4-vn-bds-aggregator
status: ready-for-dev
---

# Story 10.4: Vietnam BĐS Listing Aggregator & Cross-Source Trust Score

**Story ID:** 10.4  
**Epic:** 10 — Connector & Scraper Expansion  
**Title:** Vietnam BĐS Listing Aggregator & Cross-Source Trust Score  
**Status:** ready-for-dev  
**Priority:** HIGH  
**Requirements:** FR-6 (Built-in Scraper Connectors), FR-32 (Memory deduplication & confidence), FR-39 (Memory→scraper-run provenance & re-validation)  
**Architecture:** AD-3 (capability tự đăng ký route), AD-11.1 (Memory tự chứa recipe, không phụ thuộc `Run` retention), AD-16 (ranh giới license Apache/BSL), AD-19 (anti-bot thuộc Nowing, degrade thay vì hard-fail)  
**Dependencies:** Story 10.1 (`batdongsan.scrape`), 10.2 (`chotot_bds.scrape`), 10.3 (`muaban_bds.scrape`) — tất cả đã `done` theo `sprint-status.yaml`; `market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`.

---

## 1. Goal

Thêm `vn_bds.aggregate` thành một built-in capability mới, gọi song song các scraper BĐS đã có (`batdongsan`, `chotot_bds`, `muaban_bds`), gộp kết quả thành một schema chung `VnBdsAggregatedListing`, tính `confidence_score` đa nguồn, phát hiện trùng lặp/xung đột giá, và expose qua REST, agent chat và MCP tool. Story này giúp người dùng tin tưởng dữ liệu hơn bằng cách so sánh giá/địa chỉ/số điện thoại giữa các nguồn, đồng thời tuân thủ provenance để mỗi fact có thể re-validate.

**Non-goal:**
- Không scrape thêm nguồn P1/P2 (`muabannhadat`, `dothi`, `nhadat24h`, `alonhadat`, v.v.) trong story này — chỉ dùng 3 nguồn P0 đã có.
- Không xây UI dashboard BĐS chuyên biệt — chỉ expose capability, REST endpoint, MCP tool; UI có thể dùng memory/chat.
- Không triển khai model ML phức tạp cho trust score — V1 dùng heuristic có giải thích (rule-based, auditable).

---

## 2. User Story

> As a real-estate researcher or investor in Vietnam,  
> I want the system to merge and score listings from multiple BĐS sources,  
> So that I can trust the price, detect fake/duplicate listings, and spot conflicts before making a decision.

---

## 3. Acceptance Criteria

### AC-1 — Gọi song song 3 scraper P0
**Given** một truy vấn với `listing_type` (mua / thuê), `property_type` (căn hộ / nhà riêng / đất / all), `city`, tùy chọn `district`, `min_price`, `max_price`, `min_area`, `max_area`, `max_items_per_source`, `sources` (`["batdongsan","chotot_bds","muaban_bds"]`, default cả 3),  
**When** tôi gọi `vn_bds.aggregate`,  
**Then** nó fan-out gọi các scraper được chọn song song với cùng bộ lọc, thu thập `BatdongsanListing`, `ChototBdsListing`, `MuabanBdsListing`, trả về `VnBdsAggregateOutput` chứa danh sách `VnBdsAggregatedListing` đã normalize.

### AC-2 — Normalize về schema chung
**Given** các listing từ 3 nguồn có field khác nhau (`price_raw`, `price_value`, `area_raw`, `area_value`, `district`, `ward`, `city`, `phone`, `phone_display`, v.v.),  
**When** aggregator chạy,  
**Then** mỗi `VnBdsAggregatedListing` chứa các trường chuẩn hóa: `canonical_id`, `source_ids` (map `source` → `listing_id`), `title`, `price`, `price_value` (VND, số nguyên), `price_per_m2` (nếu có area), `area`, `area_value` (m²), `location`, `district`, `ward`, `city`, `project`, `legal`, `post_date`, `contact` (phone đã mask/full theo policy), `thumbnail_url`, `detail_urls` (map theo nguồn), `sources`, `source_count`.

### AC-3 — Tính confidence score
**Given** một `VnBdsAggregatedListing` đã normalize,  
**When** aggregator đánh giá,  
**Then** nó gán `confidence_score` (0.0–1.0) dựa trên:
  - `source_trust` (nguồn xác thực: batdongsan cao nhất, chotot/muaban thấp hơn);
  - `overlap_score` (số nguồn trùng listing cùng canonical key);
  - `freshness_score` (`post_date` càng gần càng cao, giảm dần theo tuần);
  - `price_consistency_score` (variance giữa các nguồn; variance thấp = cao).

### AC-4 — Deduplicate theo phone, địa chỉ, image hash
**Given** hai listing từ cùng hoặc khác nguồn,  
**When** chúng có `phone` giống nhau (bỏ qua định dạng), hoặc địa chỉ chuẩn hóa trùng (`district` + `ward` + đường/phường normalize), hoặc `image_hash` trùng (nếu `thumbnail_url` tải được),  
**Then** chúng được gộp thành một `VnBdsAggregatedListing` duy nhất với `source_ids` và `sources` chứa tất cả các nguồn, `canonical_id` ổn định (deterministic hash của sorted source keys + ids).

### AC-5 — Flag conflict giá
**Given** cùng một `canonical_id` có ≥2 nguồn với `price_value` khác nhau,  
**When** độ chênh lệch > 20%,  
**Then** `VnBdsAggregatedListing.conflict_flags` chứa `price_conflict` kèm `conflict_reason`, `price_range` (min/max), `price_sources` map nguồn → giá; `confidence_score` bị giảm theo hệ số; listing vẫn trả về, không bị ẩn.

### AC-6 — Expose qua REST / Agent / MCP
**Given** capability đã build,  
**When** dùng REST, agent chat hoặc MCP,  
**Then** `nowing_vn_bds_aggregate` / `vn_bds.aggregate` khả dụng với input tương tự `batdongsan.scrape`, output là `VnBdsAggregateOutput`, hỗ trợ query theo `location`, `price range`, `source filter`, `min_confidence`.

### AC-7 — Provenance & re-validation
**Given** một aggregated listing được tạo ra,  
**When** lưu vào `Memory` hoặc trả về qua API,  
**Then** mỗi fact giữ `source_capability`, `source_input`, `source_run_id` (soft reference) theo AD-11.1; người dùng/agent có thể gọi lại với cùng `source_input` để re-validate.

### AC-8 — Billing & metering
**Given** một lần aggregate thành công,  
**When** run hoàn tất,  
**Then** `cost_micros` tổng hợp từ các scraper con (đã tính bởi `BATDONGSAN_ITEM`, `CHOTOT_BDS_ITEM`, `MUABAN_BDS_ITEM`) cộng thêm `VN_BDS_AGGREGATE_QUERY` fixed micros cho bước normalize/dedupe/conflict; `total_items` là số `VnBdsAggregatedListing` trả về; ghi `degraded` tổng hợp.

### AC-9 — Xử lý lỗi & degraded mode
**Given** một hoặc nhiều scraper con trả `degraded=true` hoặc fail,  
**When** aggregate,  
**Then** aggregator trả về kết quả từ các nguồn còn lại với `degraded=true`, `degradation_reasons` là list các lý do từng nguồn; không hard-fail; không charge cho nguồn không trả listing.

### AC-10 — Test coverage
**Given** code aggregator,  
**Then** có unit tests cho normalize/dedupe/conflict/score với fixture từ 3 nguồn, integration test gọi các scraper con (hoặc recorded fixtures), test provenance `Memory` write, và test billing aggregation.

---

## 4. Tasks / Subtasks

- [ ] Thêm `VN_BDS_AGGREGATE_QUERY` billing unit và rate config (AC #8)
  - [ ] Thêm enum vào `app/capabilities/core/types.py` hoặc `app/db.py`
  - [ ] Đăng ký micros/query trong `app/config/__init__.py` và `.env.example`
- [ ] Tạo Pydantic schemas (AC #2, #3, #4, #5)
  - [ ] `VnBdsAggregateInput` (`sources`, `listing_type`, `property_type`, `city`, `district`, `min_price`, `max_price`, `min_area`, `max_area`, `max_items_per_source`, `min_confidence`)
  - [ ] `VnBdsAggregatedListing` (schema chung + `confidence_score`, `conflict_flags`, `source_ids`, `detail_urls`, `provenance`)
  - [ ] `VnBdsAggregateOutput` (`items`, `total_items`, `cost_micros`, `degraded`, `degradation_reasons`, `source_breakdown`)
- [ ] Xây normalize engine `app/services/bds_aggregator/normalize.py` (Apache-2.0) (AC #2)
  - [ ] Map từ `BatdongsanListing`/`ChototBdsListing`/`MuabanBdsListing` sang `VnBdsAggregatedListing`
  - [ ] Normalize đơn vị giá (triệu, tỷ, tỷ/m², triệu/m², tỷ/căn, v.v.) về VND số nguyên
  - [ ] Normalize diện tích (m², hecta, v.v.) về m² float
  - [ ] Normalize địa chỉ (`district`, `ward`, đường) về lowercase, bỏ dấu, chuẩn hóa từ viết tắt
- [ ] Xây dedupe/conflict engine `app/services/bds_aggregator/dedupe.py` (AC #4, #5)
  - [ ] Blocking theo phone (bỏ khoảng trắng/dấu câu/leading 0/+84)
  - [ ] Blocking theo địa chỉ chuẩn hóa (district + ward + street, sau khi strip common words)
  - [ ] Blocking theo image hash (tùy chọn, tải thumbnail, dùng perceptual hash)
  - [ ] Tính `canonical_id` deterministic
  - [ ] Phát hiện conflict giá >20% giữa các nguồn trong cùng canonical group
- [ ] Xây trust-score engine `app/services/bds_aggregator/scoring.py` (AC #3)
  - [ ] `source_trust` lookup table
  - [ ] `overlap_score` theo số nguồn trùng
  - [ ] `freshness_score` theo `post_date`
  - [ ] `price_consistency_score` theo variance giá các nguồn
  - [ ] Blend thành `confidence_score` với trọng số có tài liệu hóa
- [ ] Xây aggregator orchestrator `app/services/bds_aggregator/orchestrator.py` (AC #1, #9)
  - [ ] Fan-out gọi các scraper con song song (`asyncio.gather` với return_exceptions)
  - [ ] Áp cap `max_items_per_source` cho mỗi scraper
  - [ ] Merge outputs, gọi normalize → dedupe → scoring
  - [ ] Trả về `degraded` tổng hợp
- [ ] Đăng ký capability `app/capabilities/vn_bds/aggregate/` theo pattern `reddit.scrape` / `batdongsan.scrape` (AC #6)
  - [ ] `definition.py` (`build_capabilities_router`)
  - [ ] `executor.py` (map input → orchestrator, tạo `Run`)
  - [ ] `schemas.py` (capability input/output)
- [ ] Wire MCP tool `nowing_mcp/mcp_server/features/scrapers/platforms/vn_bds.py` (AC #6)
- [ ] Cập nhật registry (AC #6)
  - [ ] `app/routes/__init__.py` import namespace
  - [ ] `app/mcp_tools.py`
  - [ ] `nowing_web/app/(home)/mcp-server/page.tsx` (nếu cần marketing page)
- [ ] Viết tests (AC #10)
  - [ ] Unit tests normalize/dedupe/score với fixture từ 3 nguồn
  - [ ] Integration test với `@pytest.mark.integration` và fixture recorded
  - [ ] Billing test: đảm bảo tổng hợp đúng cost từ scraper con + aggregate query
  - [ ] Provenance test: ghi `Memory` với `source_capability`, `source_input`, `source_run_id`

---

## 5. Dev Notes

### Architecture & License
- **AD-3:** `app/capabilities/vn_bds/aggregate/` export `build_capabilities_router()`; mỗi lần gọi tạo một `Run` row.
- **AD-16:** source-specific normalization logic (parser/field mapping) có thể nằm trong từng `app/proprietary/platforms/<source>/` (BSL 1.1) hoặc trong `app/services/bds_aggregator/` (Apache-2.0) — ưu tiên để `normalize.py` ở Apache-2.0 vì nó chỉ làm ánh xạ field chung, không chứa logic anti-bot/source-specific. Đảm bảo không move BSL logic ra ngoài và không copy logic fetch/parser BSL vào `app/services`.
- **AD-19:** Nếu một scraper con bị block/CAPTCHA, aggregator degrade thay vì hard-fail; kết quả partial vẫn có giá trị cross-source.
- **AD-11.1 / FR-39:** Khi lưu aggregated listing vào `Memory`, `source_capability` = `vn_bds.aggregate`, `source_input` = JSONB của input aggregate, `source_run_id` = `Run.id` UUID; các `source_ids` của từng listing cũng nằm trong `content` để re-validate được.

### Technical Details
- **Fan-out pattern:** dùng `asyncio.gather(*coros, return_exceptions=True)` hoặc `anyio.create_task_group` nếu repo đang dùng; mỗi scraper chạy độc lập.
- **Source trust weights (V1 heuristic):**
  - `batdongsan` = 0.45 (có tin xác thực, nhiều data, chuyên BĐS)
  - `chotot_bds` = 0.30 (classified rộng, ít kiểm duyệt hơn)
  - `muaban_bds` = 0.25 (classified rộng, ít kiểm duyệt)
  - `overlap_score` = `min(source_count, 3) / 3` → từ 0.33 đến 1.0
  - `freshness_score` = decay theo tuần, half-life 4 tuần
  - `price_consistency_score` = 1 - min(stddev/mean, 1) cho các nguồn có `price_value`
  - `confidence_score = 0.25*source_trust + 0.25*overlap_score + 0.20*freshness_score + 0.30*price_consistency_score` (có thể tinh chỉnh)
- **Conflict detection:** cùng `canonical_id`, nếu `max(price_value) / min(price_value) > 1.2` hoặc `abs_diff/mean > 0.2` → flag `price_conflict`.
- **Deduplicate keys:**
  - Phone: normalize `re.sub(r'\D', '', phone)`, bỏ leading `0` hoặc `84` khi so sánh.
  - Address: normalize unicode, lowercase, strip dấu, bỏ các từ dừng ("bán", "cho thuê", "m²", "m2"), dùng `district + ward + street` nếu parse được.
  - Image: tùy chọn, dùng `imagehash` hoặc perceptual hash đơn giản (nếu thêm dependency thì ghi nhận rủi ro).
- **Output:** `VnBdsAggregateOutput.items` là list `VnBdsAggregatedListing`, KHÔNG chứa raw HTML.
- **Billing:** `VN_BDS_AGGREGATE_QUERY` default 5,000 micros ($0.005) mỗi query; cộng với cost từ scraper con. Chỉ charge item parse thành công.

### Error Handling
- `degradation_reasons` typed list: `api_error`, `rate_limited`, `decode_error`, `empty`, `bot_detected`, `layout_changed`, `unknown`.
- Khi một nguồn fail, log warning và tiếp tục; `source_breakdown` báo rõ nguồn nào trả bao nhiêu items và degraded gì.
- Không log PII (phone đầy đủ, address chi tiết) ở level INFO trở lên.

### Testing
- Tạo fixture `_bmad-output/test-artifacts/fixtures/vn_bds_aggregate/` hoặc `tests/fixtures/vn_bds_aggregate.json` từ output thật của 3 scraper (trimmed).
- Integration test replay fixture, không gọi live trừ khi `SCRAPE_LIVE=1`.
- Kiểm tra billing bằng mock `BillingUnit` hoặc `charge_capability`.

---

## 6. References

- Research doc (chiến lược nguồn BĐS VN): `_bmad-output/planning-artifacts/research/market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md` §“Vietnam Real Estate Data Sources & Scrape Strategy”
- Story 10.1: `_bmad-output/implementation-artifacts/10-1-batdongsan-scraper.md`
- Story 10.2: `_bmad-output/implementation-artifacts/10-2-chotot-bds-scraper.md`
- Story 10.3: `_bmad-output/implementation-artifacts/10-3-muaban-bds-scraper.md`
- PRD FR-6 Built-in Scraper Connectors: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` §4.2
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md` §AD-3, AD-11.1, AD-16, AD-19
- Pattern capability: `nowing_backend/app/capabilities/batdongsan/scrape/`
- Pattern platform scraper: `nowing_backend/app/proprietary/platforms/batdongsan/`
- Pattern MCP tool: `nowing_mcp/mcp_server/features/scrapers/platforms/batdongsan.py`
- Memory model / provenance: `nowing_backend/app/db.py` (`Memory.source_capability`, `source_input`, `source_run_id`)
- Billing / types: `nowing_backend/app/capabilities/core/billing.py`, `nowing_backend/app/capabilities/core/types.py`

---

## Challenge Log (grill-me)

### Q1 — Already implemented?
- **Không tìm thấy** code `bds_aggregator`, `vn_bds_aggregate`, hay `confidence_score` cho BĐS trong repo (`rg -i` 0 kết quả).
- Tìm thấy `Memory.confidence` field sẵn có (`app/db.py:2203`) và `MemoryRelation`/`MemoryVersion` — **có thể tái dụng** để lưu aggregated listing với provenance.
- Tìm thấy `quality_score.py` — dùng cho OpenRouter model selection, **không liên quan** trực tiếp; không nên reuse.
- Tìm thấy `app/capabilities/core/billing.py` — **có thể reuse** `BillingUnit` pattern.

### Q2 — Simpler alternative?
- **Nên dùng** các scraper con đã có (`batdongsan.scrape`, `chotot_bds.scrape`, `muaban_bds.scrape`) thay vì gọi trực tiếp proprietary fetcher — giữ lớp capability và billing đúng AD-3.
- **Nên dùng** `Run.output_text` JSONL hoặc return trực tiếp từ executor thay vì tạo bảng `AggregatedListing` riêng — V1 không cần persistence riêng; lưu vào `Memory` theo AD-11.1 nếu user yêu cầu.
- Không cần thêm image hash nếu gây dependency mới hoặc network đáng kể; có thể đánh dấu ` ponytail: image dedupe deferred to P1`.

### Q3 — Edge cases spec misses (Pattern 3)
- [ ] **Boundary:** `max_items_per_source=0` → trả empty list, không charge.
- [ ] **Boundary:** `sources=[]` → 400/422 field error.
- [ ] **Boundary:** `min_price > max_price` hoặc `min_area > max_area` → 422 field error.
- [ ] **Boundary:** cả 3 nguồn đều degraded → vẫn trả `degraded=true` với `degradation_reasons`, items rỗng.
- [ ] **Boundary:** một nguồn trả `price_value=None` nhưng nguồn khác có giá → vẫn tính confidence dựa trên nguồn còn lại.
- [ ] **Null/empty:** `phone` bị mask hoặc thiếu → bỏ qua phone dedupe, fallback địa chỉ/image.
- [ ] **Concurrent:** 2 lần gọi `vn_bds.aggregate` cùng lúc → không dùng shared mutable state, mỗi `Run` riêng.
- [ ] **Deterministic:** `canonical_id` phải ổn định qua các lần gọi nếu source ids giống nhau.

### Q4 — Failure modes unspecified (Pattern 2, 4)
- [ ] **Một scraper con timeout:** đánh timeout nguồn đó là `degraded`, không charge cho nguồn đó.
- [ ] **Scraper con trả kết quả không hợp lệ:** catch validation error, mark `degraded`, không charge.
- [ ] **Normalize lỗi:** ví dụ `price_value` không parse được → lưu `price_value=None`, vẫn giữ `price_raw`.
- [ ] **Dedupe chặn sai:** địa chỉ giống nhau nhưng là 2 listing khác nhau (tầng/lô khác nhau) → future work, V1 ưu tiên recall over precision.
- [ ] **Billing miscalculation:** `cost_micros` = sum(scraper con `cost_micros`) + `VN_BDS_AGGREGATE_QUERY`; không charge scraper con nếu `degraded=true`.
- [ ] **Credit service fail:** nếu gọi credit deduction fail, run phải fail closed (không trả kết quả miễn phí).
- [ ] **Memory auto-extract không hiểu source type `vn_bds_aggregate`:** cần thêm mapping hoặc source type vào `MemoryExtractionService`.

### Triage
- **Clean — proceed.** Không có duplicate logic cấm, không có alternative đơn giản hơn đến mức phải HALT. Cần bổ sung edge cases / failure modes vào test skeleton.
