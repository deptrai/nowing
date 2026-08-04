# Story 10.4 Create Report — Stage 1

**Story key:** 10-4-vn-bds-aggregator  
**Baseline commit:** `b9972636fa41737129a15463c37e2e334ed5e499` (develop HEAD)  
**Baseline branch:** develop  
**Working branch:** `story/10-4-vn-bds-aggregator`  
**Status:** ready-for-dev

---

## Outputs created

1. **Story artifact:**
   - `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/10-4-vn-bds-aggregator.md`
   - Contains full context: Goal, User Story, 10 Acceptance Criteria, Tasks/Subtasks, Dev Notes, References, Challenge Log.

2. **Sprint status update:**
   - `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml`
   - Updated line 118 from `10-4: backlog` → `10-4: ready-for-dev`.
   - No other lines were modified.

3. **This report:**
   - `/Users/luisphan/Documents/GitHub/nowing/_workspace/10-4/01_create.md`

---

## Inputs used

- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md` (Epic 10 + Story 10.4)
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/10-1-batdongsan-scraper.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/10-2-chotot-bds-scraper.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/10-3-muaban-bds-scraper.md`
- `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/research/market-vietnam-real-estate-research-data-scraping-landscape-research-2026-08-03.md`
- Architecture spine: `ARCHITECTURE-SPINE.md` §AD-3, AD-11.1, AD-16, AD-19
- Code reference: `nowing_backend/app/proprietary/platforms/{batdongsan,chotot,muaban_bds}/schemas.py`, `app/capabilities/batdongsan/scrape/executor.py`, `app/db.py` (`Memory` model)

---

## Key design decisions in the story

- **Capability name:** `vn_bds.aggregate` / `nowing_vn_bds_aggregate` (MCP tool).
- **Fan-out strategy:** gọi song song 3 scraper P0 (`batdongsan`, `chotot_bds`, `muaban_bds`) với cùng bộ lọc.
- **V1 trust score:** rule-based/heuristic (source trust + overlap + freshness + price consistency), không dùng ML.
- **Deduplication:** phone, normalized address, image hash (tùy chọn).
- **Conflict detection:** cùng canonical listing, giá chênh >20% → flag `price_conflict`.
- **License boundary:** source-specific parsers/fetchers vẫn ở `app/proprietary/` (BSL); aggregator core (`app/services/bds_aggregator/`, `app/capabilities/vn_bds/aggregate/`) ở Apache-2.0 đúng AD-16.
- **Provenance:** theo AD-11.1, lưu `source_capability`, `source_input`, `source_run_id` khi ghi `Memory`.
- **Billing:** `VN_BDS_AGGREGATE_QUERY` fixed micros cộng với cost từ scraper con.

---

## Blockers / Notes

- **Không có blocker kỹ thuật.** Story chỉ yêu cầu tạo artifact, không implement code.
- **Giả định:** 10.1/10.2/10.3 đã `done` theo `sprint-status.yaml` và schema các nguồn đã tương thích (`listing_id`, `title`, `price`, `price_value`, `area`, `area_value`, `location`, `district`, `city`, `post_date`, `thumbnail_url`, `detail_url`, `phone`, `phone_display`).
- **Ghi chú cho dev tiếp theo:**
  - Cần quyết định chính thức về trọng số `confidence_score` và bảng `source_trust` — story đã đề xuất heuristic, dev có thể tinh chỉnh qua test.
  - Image hash là tùy chọn; nếu thêm dependency (vd `imagehash`) cần cân nhắc rủi ro license/network.
  - Cần verify `MemoryExtractionService` có source type mới `vn_bds_aggregate` khi lưu memory.

---

## Next stage

Stage 2 (dev-implementation) có thể bắt đầu khi artifact được approve.
