---
baseline_commit: 5389b069779e94702bfdeeef9dfc17205677f98f
---

# Story 21.20: Mở rộng Adapter Multi-Source Lead Gen

Status: done

Story ID: 21.20
Epic: Epic 21 — Lead Gen Intelligence & Social Graph
Baseline: develop

## Story

Là một sales rep hoặc broker BĐS tại Việt Nam,
Tôi muốn `multi_source_lead_gen` thực sự chạy được các nguồn mà prompt/routing đã quảng cáo (`muaban_bds`, `vn_jobs`/`VietnamWorks`, `Mua Sắm Công` / `muasamcong`),
Để prompt, routing, registry và thực thi đồng nhất, và tôi có thể tìm kiếm các nguồn này qua một công cụ duy nhất bằng ngôn ngữ tự nhiên.

## Acceptance Criteria

1. **Given** người dùng hỏi về BĐS (ví dụ: "Tìm nhà đất Hà Nội dưới 5 tỷ"), **when** `multi_source_lead_gen` chạy, **then** `MuabanBdsLeadAdapter` được dispatch cùng `batdongsan`/`chotot`, trả về `RawLeadRecord` từ `muaban_bds.scrape`, và `last_execution_status` được set `degraded` khi scraper degraded. [PENDING]
2. **Given** người dùng hỏi về tuyển dụng (ví dụ: "công ty AI tuyển dụng tại TP.HCM"), **when** `multi_source_lead_gen` chạy, **then** `VnJobsLeadAdapter` gọi `aggregate_jobs(..., ctx=None)` từ `app.services.jobs_aggregator` để lấy danh sách tổng hợp từ TopCV/ITviec/VietnamWorks mà không tự persist; `VietnamWorksLeadAdapter` chỉ chạy khi query chứa từ khóa "vietnamworks". [PENDING]
3. **Given** người dùng hỏi về gói thầu / doanh nghiệp công (ví dụ: "gói thầu xây dựng TP.HCM"), **when** `multi_source_lead_gen` chạy, **then** `MuaSamCongLeadAdapter` gọi `MuasamcongScraper.search_tenders()` và trả về tender leads. [PENDING]
4. **Given** các adapter mới, **when** `LeadSourceAdapterRegistry.resolve_adapters_for_intent(query)` được gọi, **then** registry trả về đúng adapter cho từ khóa BĐS/job/enterprise, tránh gọi trùng lặp cùng một nguồn nhiều lần (ví dụ `vn_jobs` không chạy đồng thời với `job_market`/`vietnamworks` cho cùng một generic query). [PENDING]
5. **Given** adapter mới chạy xong, **when** `LeadGenOrchestrator` aggregate, **then** các lead được `normalize_lead`, deduplicate bởi `EntityDeduplicationService`, và persist qua `LeadBatchService.ingest_batch` như các adapter 21.19. [PENDING]
6. **Given** các adapter mới, **when** `ruff check` và `pytest` chạy, **then** lint/type sạch, unit + integration test pass, và `python -c "from app.app import app; print('app import OK')"` thành công. [PENDING]

## Quyết định thiết kế chưa giải quyết / Cần định hình khi dev

- **`vn_jobs` (aggregate) vs `VietnamWorks` (direct) vs `job_market` (TopCV+ITviec):** Hiện tại `job_market` đã chạy TopCV + ITviec. `vn_jobs.aggregate` đã tồn tại và bao gồm cả VietnamWorks. AC-2 yêu cầu `VnJobsLeadAdapter` dùng aggregate, `VietnamWorksLeadAdapter` dùng `scrape_vietnamworks` cho query cụ thể. AC-4 yêu cầu `resolve_adapters_for_intent` tránh duplicate call. Dev cần đảm bảo một generic job query chỉ chạy `vn_jobs`, không chạy thêm `job_market`/`vietnamworks`.
- **`muasamcong` category:** Tender là `ENTERPRISE` (doanh nghiệp công / chủ đầu tư). Dùng `LeadSourceCategory.ENTERPRISE` cho `MuaSamCongLeadAdapter`.
- **`muaban_bds` city input:** `MuabanBdsScrapeInput.city` nhận slug (ví dụ `ha-noi`). Có thể tái sử dụng `_query_parser.resolve_chotot_city()` để lấy chuỗi không dấu rồi để `scrape_muaban_bds._resolve_city_slug()` map sang slug, hoặc thêm `resolve_muaban_bds_city` nếu cần.

## Tasks / Subtasks

- [x] **T1 — Mở rộng `_query_parser.py` nếu cần** (AC-1, AC-3)
  - [x] T1.1 Kiểm tra `resolve_chotot_city` + `extract_price_range` + `extract_listing_type_chotot` + `extract_property_type_chotot` đã đủ cho `muaban_bds` hay không.
  - [x] T1.2 Thêm alias `resolve_muaban_bds_city = resolve_chotot_city` để `muaban_bds.py` gọi rõ ràng.
  - [x] T1.3 `extract_price_range` trả về `int` VND; `MuaSamCongScraper` nhận `float`, đã cast trong adapter.
- [x] **T2 — Implement `MuabanBdsLeadAdapter`** (AC-1)
  - [x] T2.1 Tạo `app/lead_intelligence/adapters/muaban_bds.py`.
  - [x] T2.2 `source_name = "muaban_bds"`, `category = LeadSourceCategory.REAL_ESTATE`.
  - [x] T2.3 `_query_muaban_bds_api`: gọi `scrape_muaban_bds(MuabanBdsScrapeInput(...))`, parse `output.degraded`.
  - [x] T2.4 `normalize_lead`: map `listing_id/title/price_value/area/city/district/ward/phone/detail_url` sang `NormalizedLead`.
  - [x] T2.5 `extract_contact_candidates`: lấy `phone`/`phone_display`/`phone_enc`, rồi extract phones từ `title`/`description`.
- [x] **T3 — Implement `VnJobsLeadAdapter` (aggregate)** (AC-2)
  - [x] T3.1 Tạo `app/lead_intelligence/adapters/vn_jobs.py`.
  - [x] T3.2 `source_name = "vn_jobs"`, `category = LeadSourceCategory.JOB_MARKET`.
  - [x] T3.3 `_aggregate_job_listings`: gọi `aggregate_jobs(VnJobAggregateInput(...), ctx=None)` để lấy `VnJobAggregateOutput` mà không persist.
  - [x] T3.4 `normalize_lead`: map `VnJobAggregatedListing` (`id/title/company/location/salary_min/salary_max/source_urls/skills`) sang `NormalizedLead`.
  - [x] T3.5 `extract_contact_candidates`: gọi `extract_phones_from_text` trên `job_description`/`job_requirement` đã được `jobs_aggregator` redact; đồng thời tạo candidate `jobs@{domain}` từ `source_urls`.
- [x] **T4 — Implement `VietnamWorksLeadAdapter` (direct)** (AC-2)
  - [x] T4.1 Tạo `app/lead_intelligence/adapters/vietnamworks.py`.
  - [x] T4.2 `source_name = "vietnamworks"`, `category = LeadSourceCategory.JOB_MARKET`.
  - [x] T4.3 `_fetch_vietnamworks_jobs`: gọi `scrape_vietnamworks({"keyword": query, "max_items": limit, "max_pages": 5})` với `salary_min`/`salary_max` từ query parser.
  - [x] T4.4 `normalize_lead`: map dict item từ scraper sang `NormalizedLead`.
  - [x] T4.5 PII redact: áp dụng `redact_job_pii` từ `app.services.pii.redact` cho `job_description`/`job_requirement` trước khi extract.
- [x] **T5 — Implement `MuaSamCongLeadAdapter` (public procurement)** (AC-3)
  - [x] T5.1 Tạo `app/lead_intelligence/adapters/muasamcong.py`.
  - [x] T5.2 `source_name = "muasamcong"`, `category = LeadSourceCategory.ENTERPRISE`.
  - [x] T5.3 `_search_public_tenders`: khởi tạo `MuasamcongScraper()` và gọi `search_tenders(keyword, min_price, max_price, location, size)`.
  - [x] T5.4 `normalize_lead`: map `ProcurementTenderItem` sang `NormalizedLead`.
  - [x] T5.5 `extract_contact_candidates`: extract phones từ `raw_specs`/`project_name`/`procuring_entity`/`investor`.
- [x] **T6 — Đăng ký adapter** (AC-4)
  - [x] T6.1 Cập nhật `app/lead_intelligence/adapters/__init__.py` export 4 adapter mới.
  - [x] T6.2 Cập nhật `app/lead_intelligence/adapters/registry.py::_register_defaults` import và `register()` 4 adapter.
  - [x] T6.3 Cập nhật `resolve_adapters_for_intent` để tránh duplicate trong `JOB_MARKET`: generic job query -> `vn_jobs`; query chứa "vietnamworks" -> `vietnamworks`; query chứa "topcv" / "itviec" -> `job_market`.
- [x] **T7 — Cập nhật prompt/routing/capability description** (AC-4)
  - [x] T7.1 `app/capabilities/leads/orchestrator/definition.py`: cập nhật `description`.
  - [x] T7.2 `multi_source_lead_gen/description.md`: liệt kê đầy đủ nguồn.
  - [x] T7.3 `multi_source_lead_gen/example.md`: thêm ví dụ procurement và cập nhật ví dụ BĐS/job.
  - [x] T7.4 `routing.md`: bổ sung `Mua Sắm Công` vào mô tả `multi_source_lead_gen`.
  - [x] T7.5 `core_behavior.md`: không cần thay đổi (failover examples vẫn hợp lệ).
- [x] **T8 — Tests** (AC-6)
  - [x] T8.1 Unit test cho mỗi adapter mới với scraper mock.
  - [x] T8.2 Cập nhật / thêm test cho `resolve_adapters_for_intent` để cover 4 adapter mới và job deduplication.
  - [x] T8.3 `test_lead_gen_orchestrator.py` integration pass.
  - [x] T8.4 `ruff check app/lead_intelligence` pass; `pytest tests/unit/lead_intelligence` 191 pass; `python -c "from app.app import app; print('app import OK')"` pass.

## Dev Notes

### Kiến trúc & Pattern bắt buộc

- Kế thừa `LeadSourceAdapter` từ `app/lead_intelligence/adapters/base.py`, implement 3 phương thức: `search_leads`, `normalize_lead`, `extract_contact_candidates`.
- Mỗi adapter phải set `source_name` (duy nhất, lowercase, khớp key trong registry), `category` (`REAL_ESTATE`, `JOB_MARKET`, `ENTERPRISE`), và `last_execution_status` (`ok`/`degraded`).
- `search_leads` trả về `list[RawLeadRecord]`; `RawLeadRecord.data` là `dict` từ scraper item.
- `normalize_lead` trả về `NormalizedLead` với `source_name`, `source_id`, `title`, `company_name`, `primary_phone`, `primary_email`, `city`, `price`, `confidence_score`, `contact_candidates`, `raw_data`.
- `extract_contact_candidates` trả về `list[ContactCandidate]`; mỗi candidate có `channel` (`phone`/`email`), `value`, `confidence` (0.0–1.0), `metadata`.

### Xử lý degraded & exception (học từ 21.19)

- Không bao `scrape_*` bằng `try/except` rồi trả `[]` một cách âm thầm. Nếu scraper raise exception, để nó bubble lên `LeadGenOrchestrator._run_single_adapter` (đã có `try/except` ở đó) để set `last_execution_status = "degraded"`.
- Nếu scraper trả về object có `degraded=True` (ví dụ `MuabanBdsScrapeOutput.degraded`, `VnJobAggregateOutput.degraded`, `ScrapeResult.degraded`, dict `scrape_vietnamworks["degraded"]`), adapter phải set `self.last_execution_status = "degraded"` và log `degradation_reason`.
- `MuasamcongScraper.search_tenders` trả về `ScrapeResult` với `degraded`/`degradation_reason`.
- `scrape_vietnamworks` trả về dict với `degraded`/`degradation_reason`/`items`.
- `aggregate_jobs` trả về `VnJobAggregateOutput` với `degraded`/`degradation_reasons`/`degraded_source_ids`.

### Reuse query parser (21.19)

- `app/lead_intelligence/adapters/_query_parser.py` đã có:
  - `resolve_batdongsan_city(query, filters)` -> code cho BĐS.
  - `resolve_chotot_city(query, filters)` -> chuỗi không dấu, cách bởi khoảng trắng, phù hợp với `scrape_chotot` và có thể dùng cho `scrape_muaban_bds._resolve_city_slug`.
  - `extract_price_range(query)` -> `(min_price, max_price)` int VND.
  - `extract_listing_type_bds(query)` / `extract_listing_type_chotot(query)` -> `"buy"` / `"rent"`.
  - `extract_property_type_chotot(query)` -> `"apartment"` / `"house"` / `"land"` / `"office"` / `"all"`.
- `MuabanBdsScrapeInput` dùng `listing_type: Literal["buy","rent"]`, `property_type: Literal["apartment","house","land","office","all"]`, `min_price`, `max_price` int, `city` str, `district` str. Có thể dùng `extract_listing_type_chotot`, `extract_property_type_chotot`, `extract_price_range`, `resolve_chotot_city`.
- `MuaSamCongLeadAdapter` có thể dùng `extract_price_range` rồi cast `int` -> `float`; location dùng `resolve_chotot_city` (chuỗi không dấu) hoặc `filters["locations"][0]`.
- `VnJobsLeadAdapter` / `VietnamWorksLeadAdapter` có thể dùng `extract_price_range` cho `salary_min` / `salary_max`; location dùng `resolve_chotot_city` (aggregator tự lọc theo location).

### PII & DNC

- `VnJobsLeadAdapter` dùng `aggregate_jobs`, đã redact PII trong `jobs_aggregator`.
- `VietnamWorksLeadAdapter` gọi `scrape_vietnamworks` trực tiếp, cần redact `job_description`/`job_requirement` trước khi extract text. Tái sử dụng `app.services.jobs_aggregator.redact.redact_canonical_data` hoặc ít nhất chỉ extract phone/email từ trường đã biết an toàn.
- `LeadBatchService.ingest_batch` thực hiện DNC filtering, HMAC, PII encryption. Adapter chỉ cần cung cấp `company_name` (hoặc `title`) để tạo `value_hmac`.

### Registration & Routing

- `LeadSourceAdapterRegistry._register_defaults` phải import adapter bên trong hàm để tránh import cycle.
- `resolve_adapters_for_intent` hiện dùng category. Khi thêm 3 adapter `JOB_MARKET` (`vn_jobs`, `vietnamworks`, `job_market`), cần post-filter:
  - Generic job keywords -> ưu tiên `vn_jobs`.
  - Query chứa "vietnamworks" -> ưu tiên `vietnamworks`.
  - Query chứa "topcv" / "itviec" -> ưu tiên `job_market`.
  - Không bao giờ chạy cả `vn_jobs` + `vietnamworks` + `job_market` cho cùng một query.
- `muaban_bds` keyword BĐS sẽ tự động được chọn qua `find_by_category(REAL_ESTATE)`.
- `muasamcong` keyword enterprise ("gói thầu", "đấu thầu", "mua sắm công", "dự thầu") đã có trong `ent_keywords` của `resolve_adapters_for_intent`; đảm bảo `MuaSamCongLeadAdapter` category là `ENTERPRISE`.

### Prompt / Routing / Capability description alignment

- Tất cả các nơi liệt kê nguồn của `multi_source_lead_gen` phải đồng nhất. Ví dụ:
  - Real estate: `batdongsan`, `chotot`, `muaban_bds`
  - Job market: `vn_jobs` (aggregate TopCV + ITviec + VietnamWorks), `vietnamworks` (direct nếu user hỏi cụ thể)
  - Enterprise: `masothue` (doanh nghiệp), `muasamcong` (gói thầu)
- `description.md` dòng 2 hiện có: "(Batdongsan, Chợ Tốt, Mua Bán, TopCV, ITviec, VietnamWorks, Masothue)". Cần bổ sung `muasamcong` và rõ `vn_jobs`.
- `routing.md` dòng 67 nói `multi_source_lead_gen` gồm real estate (Batdongsan, Chợ Tốt, Mua Bán), recruitment (TopCV, ITviec, VietnamWorks), corporate (Masothue). Cần thêm `muasamcong`.
- `app/capabilities/leads/orchestrator/definition.py` dòng 16 hiện có "Batdongsan, Chợ Tốt, TopCV, ITviec, Masothue, Mua Sắm Công, and Social groups". Cần bổ sung `muaban_bds`, `vn_jobs`, `VietnamWorks`.

### Testing

- Unit test pattern: mock `scrape_*` hoặc `aggregate_jobs` trả về dữ liệu mẫu có `degraded=False`, assert `RawLeadRecord` count, assert `NormalizedLead` fields, assert `last_execution_status`.
- Kiểm tra `resolve_adapters_for_intent` với query "vietnamworks" chỉ trả về `vietnamworks`, query "tuyển dụng" trả về `vn_jobs` (không có `job_market`/`vietnamworks`).
- Integration test: `LeadGenOrchestrator.execute_and_persist` với adapter mới, assert `Lead` rows được tạo trong DB.

## Project Structure Notes

- Các adapter mới phải nằm trong `app/lead_intelligence/adapters/` cùng pattern với `batdongsan.py`, `chotot.py`, `job_market.py`.
- Cố gắng KHÔNG tạo thêm file nếu logic có thể tái sử dụng. Ví dụ: dùng chung `_query_parser.py`; không tạo query parser riêng cho từng adapter.
- Nếu `resolve_chotot_city` không đủ cho `muaban_bds`, mở rộng `_query_parser.py` thay vì tạo parser mới.

## Implementation Details per Adapter

### `MuabanBdsLeadAdapter`

```python
from app.proprietary.platforms.muaban_bds.schemas import MuabanBdsScrapeInput
from app.proprietary.platforms.muaban_bds.scraper import scrape_muaban_bds

input_model = MuabanBdsScrapeInput(
    city=resolve_chotot_city(query, filters) or "ho-chi-minh",
    listing_type=extract_listing_type_chotot(query),
    property_type=extract_property_type_chotot(query) or "all",
    min_price=extract_price_range(query)[0],
    max_price=extract_price_range(query)[1],
    max_items=min(limit, 20),
    max_pages=5,
)
output = await scrape_muaban_bds(input_model)
```

- `output.items` là `list[MuabanBdsListing]`; gọi `item.to_output()` để lấy `dict`.
- `data["price_vnd"] = data.get("price_value") or data.get("price")`
- `data["contact_phone"] = data.get("phone") or data.get("phone_display") or data.get("phone_enc")`

### `VnJobsLeadAdapter`

```python
from app.services.jobs_aggregator import aggregate_jobs
from app.services.jobs_aggregator.schemas import VnJobAggregateInput

input_model = VnJobAggregateInput(
    keyword=query,
    location=resolve_chotot_city(query, filters),
    salary_min=extract_price_range(query)[0],
    salary_max=extract_price_range(query)[1],
    sources=["topcv", "itviec", "vietnamworks"],
    max_items_per_source=min(limit, 20),
    max_pages=5,
)
output = await aggregate_jobs(input_model, None)  # ctx=None => không persist
```

- `output.items` là `list[VnJobAggregatedListing]`; gọi `item.model_dump()`.
- `source_id = item.id`
- `company_name = item.company`
- `canonical_domain` từ `source_urls[0]` nếu có.

### `VietnamWorksLeadAdapter`

```python
from app.proprietary.platforms.vietnamworks.scraper import scrape_vietnamworks

raw = await scrape_vietnamworks({
    "keyword": query,
    "max_items": min(limit, 20),
    "max_pages": 5,
    # locationId bỏ qua ở v1; aggregator xử lý location tốt hơn
})
```

- `raw["items"]` là `list[dict]`.
- Redact `job_description` / `job_requirement` trước khi extract phone/email.

### `MuaSamCongLeadAdapter`

```python
from app.proprietary.platforms.muasamcong.scraper import MuasamcongScraper

scraper = MuasamcongScraper()
min_price, max_price = extract_price_range(query)
result = await scraper.search_tenders(
    keyword=query,
    min_price=float(min_price) if min_price else None,
    max_price=float(max_price) if max_price else None,
    location=resolve_chotot_city(query, filters),
    size=min(limit, 20),
)
```

- `result.items` là `list[ProcurementTenderItem]`; gọi `item.model_dump()`.
- `source_id = item.bid_no`
- `company_name = item.procuring_entity or item.investor or "Gói thầu công"`
- `price = item.bid_price`
- `source_url = item.dossier_url`

## References

- `app/lead_intelligence/adapters/base.py` — `LeadSourceAdapter`, `RawLeadRecord`, `NormalizedLead`, `ContactCandidate`, `LeadSourceCategory`
- `app/lead_intelligence/adapters/_query_parser.py` — parser city/price/listing type/property type
- `app/lead_intelligence/adapters/registry.py` — `LeadSourceAdapterRegistry._register_defaults`, `resolve_adapters_for_intent`
- `app/lead_intelligence/adapters/__init__.py` — export adapter
- `app/lead_intelligence/adapters/batdongsan.py` — mẫu BĐS adapter sau 21.19
- `app/lead_intelligence/adapters/chotot.py` — mẫu BĐS adapter sau 21.19
- `app/lead_intelligence/adapters/job_market.py` — mẫu job adapter
- `app/lead_intelligence/adapters/enterprise.py` — mẫu enterprise adapter
- `app/lead_intelligence/services/lead_gen_orchestrator.py` — `LeadGenOrchestrator`, `LeadGenOrchestratorResult`
- `app/lead_intelligence/schemas.py` — `MultiSourceLeadGenRequest`, `MultiSourceLeadGenResponse`
- `app/services/lead_batch_service.py` — `ingest_batch`, `_prepare_lead_record`, `_build_batch_upsert_stmt`
- `app/proprietary/platforms/muaban_bds/schemas.py` — `MuabanBdsScrapeInput`, `MuabanBdsListing`, `MuabanBdsScrapeOutput`
- `app/proprietary/platforms/muaban_bds/scraper.py` — `scrape_muaban_bds`, `_resolve_city_slug`
- `app/proprietary/platforms/vietnamworks/scraper.py` — `scrape_vietnamworks`
- `app/services/jobs_aggregator/orchestrator.py` — `aggregate_jobs`
- `app/services/jobs_aggregator/schemas.py` — `VnJobAggregateInput`, `VnJobAggregateOutput`, `VnJobAggregatedListing`
- `app/proprietary/platforms/muasamcong/schemas.py` — `ProcurementTenderItem`, `ScrapeResult`
- `app/proprietary/platforms/muasamcong/scraper.py` — `MuasamcongScraper.search_tenders`
- `app/capabilities/leads/orchestrator/definition.py` — capability `leads.multi_source_gen` description
- `app/capabilities/leads/orchestrator/executor.py` — gọi `LeadGenOrchestrator`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/description.md`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/example.md`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md`
- `app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/core_behavior.md`
- `tests/unit/lead_intelligence/test_lead_source_adapters.py`
- `tests/integration/lead_intelligence/test_lead_gen_orchestrator.py`

## Previous Story Intelligence (21.19)

- Sau review 21.19, 12 patch findings đã được apply (2026-08-21): query parser mới, adapter degraded handling, `LeadBatchService` upsert bảo vệ status, `LeadGenOrchestrator` cập nhật persistence counts, `lead_generation.py` rollback, `TelegramLeadAdapter` bỏ `object.__setattr__`.
- `multi_source_lead_gen` đã có `BatdongsanLeadAdapter`, `ChototLeadAdapter`, `JobMarketLeadAdapter`, `EnterpriseProcurementLeadAdapter`, `SocialLeadAdapter`, `TelegramLeadAdapter`. Các adapter này chạy concurrently qua `LeadGenOrchestrator` với `asyncio.Semaphore(5)` và timeout 12s.
- `SocialLeadAdapter` và `TelegramLeadAdapter` vẫn trả rỗng và tự đánh `degraded` sau patch; việc làm live được defer sang Epic 22 / story khác.
- `EntityDeduplicationService.apply_dnc_compliance` đã bị loại bỏ khỏi `LeadGenOrchestrator`; DNC thực sự xảy ra trong `LeadBatchService.ingest_batch`.
- `lead_intelligence/adapters/_query_parser.py` là mới; cần mở rộng hoặc tái sử dụng cho `muaban_bds` / `vn_jobs` / `muasamcong`.

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

- Deferred from review of `stories/21-19-lead-source-adapter-live-integration.md` (2026-08-21)

### Completion Notes List

- Implemented 4 new lead source adapters: `MuabanBdsLeadAdapter`, `VnJobsLeadAdapter`, `VietnamWorksLeadAdapter`, `MuaSamCongLeadAdapter`.
- Wired each adapter to the existing live scrapers (`scrape_muaban_bds`, `aggregate_jobs` with `ctx=None`, `scrape_vietnamworks`, `MuasamcongScraper.search_tenders`).
- Reused `_query_parser` for city/price/listing-type extraction and added `resolve_muaban_bds_city` alias.
- Added job-market source deduplication in `resolve_adapters_for_intent`: generic job query -> `vn_jobs`; explicit `vietnamworks` -> `vietnamworks`; explicit `topcv`/`itviec` -> `job_market`.
- Updated `multi_source_lead_gen` prompt/routing/capability description to reflect the live source list.
- Added unit tests for all 4 new adapters and 2 new registry intent-routing tests; all 22 tests in `test_lead_source_adapters.py` pass.
- `ruff check app/lead_intelligence` pass; `pytest tests/unit/lead_intelligence` 191 pass; `python -c "from app.app import app; print('app import OK')"` pass.
- `pytest tests/integration/lead_intelligence/test_lead_gen_orchestrator.py` 3 pass.
- Pre-existing integration failures in `test_contact_enrichment.py` and `test_lead_scoring.py` (`value_hmac` NOT NULL constraint) are unrelated to 21.20 scope.

### File List

- `nowing_backend/app/lead_intelligence/adapters/_query_parser.py`
- `nowing_backend/app/lead_intelligence/adapters/__init__.py`
- `nowing_backend/app/lead_intelligence/adapters/muaban_bds.py`
- `nowing_backend/app/lead_intelligence/adapters/vn_jobs.py`
- `nowing_backend/app/lead_intelligence/adapters/vietnamworks.py`
- `nowing_backend/app/lead_intelligence/adapters/muasamcong.py`
- `nowing_backend/app/lead_intelligence/adapters/registry.py`
- `nowing_backend/app/capabilities/leads/orchestrator/definition.py`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/description.md`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/tools/multi_source_lead_gen/example.md`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/routing.md`
- `nowing_backend/tests/unit/lead_intelligence/test_lead_source_adapters.py`
- `_bmad-output/implementation-artifacts/stories/21-20-extend-lead-source-adapters.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Review Findings

#### Decision Needed
- [ ] [Review][Decision] `VnJobs` / `VietnamWorks` `canonical_domain` source — Spec says derive from `source_urls[0]` (reviewer argues it should be the hiring company's `company_website`). Which source should be authoritative for HMAC dedup and outreach? [`vn_jobs.py:131`, `vietnamworks.py:135`]
- [ ] [Review][Decision] `VietnamWorks` PII redaction order — Spec explicitly says redact `job_description` / `job_requirement` before extracting phone/email, which removes all contact signals. Keep this privacy-first ordering or extract first then redact for display? [`vietnamworks.py:48-85`]
- [ ] [Review][Decision] `resolve_adapters_for_intent` multi-source selection — `break` after first keyword match means a query like "TopCV và VietnamWorks" only runs one. Should two explicitly named job sources both run? [`registry.py:260-265`]

#### Patch
- [ ] [Review][Patch] Adapter `last_execution_status` stays `degraded` forever — `search_leads` should reset status to `ok` at the start of each call so a prior degraded run does not poison the next successful run. Same pattern in `batdongsan.py`, `chotot.py`, `enterprise.py` (pre-existing, fix as part of this patch to keep behavior consistent). [`muaban_bds.py:71-90`, `vn_jobs.py:81-94`, `vietnamworks.py:87-100`, `muasamcong.py:62-75`]
- [ ] [Review][Patch] `resolve_chotot_city` default `Hà Nội` leaks into `vn_jobs` / `muasamcong` — Nationwide or remote job/procurement queries are silently filtered to Hà Nội. Introduce a no-default location resolver for non-BĐS adapters. [`_query_parser.py:182-196`, `vn_jobs.py:57`, `muasamcong.py:43`]
- [ ] [Review][Patch] `_first_location` does not guard against string `filters["locations"]` — Passing a single string location iterates per character and produces `H`, `à`, ... . [`_query_parser.py:133-139`]
- [ ] [Review][Patch] `extract_price_range` cannot match unaccented `ti` — `remove_diacritics` turns "tỉ" into "ti", but `_PRICE_*_RE` and `_PRICE_UNITS` only match `tỉ` (with diacritic). Add `ti` as a valid unit. [`_query_parser.py:31-57`]
- [ ] [Review][Patch] Job adapters cast `salary_min`/`salary_max` = 0 to `price=0.0` — Salary "thỏa thuận" or unset should be `None`, not zero. [`vn_jobs.py:120-136`, `vietnamworks.py:126-140`]
- [ ] [Review][Patch] `source_url` is dropped from `NormalizedLead` — `muasamcong.py` passes `source_url` to a model that has no such field (Pydantic ignores it); `vn_jobs` never sets one. `LeadGenOrchestrator.execute_and_persist` only reads `raw_data.get("url")`, `source_url`, or `detail_url`. Add `source_url` to `NormalizedLead` and set it from `dossier_url` / `source_urls[0]`; update orchestrator fallback. [`base.py:54-76`, `muasamcong.py:114-128`, `vn_jobs.py:120-141`, `lead_gen_orchestrator.py:358-362`]
- [ ] [Review][Patch] Unprotected `float()` on price/salary strings — `muaban_bds` and `vn_jobs`/`vietnamworks` call `float()` on values that may be strings like "Thỏa thuận" or "6.5 tỷ", crashing normalization. Wrap in try/except. [`muaban_bds.py:121-127`, `vn_jobs.py:136`, `vietnamworks.py:140`]
- [ ] [Review][Patch] `resolve_adapters_for_intent` fallback returns all adapters without dedup — If no keyword matches, `self.list_all()` returns 10 adapters without JOB_MARKET deduplication. Apply the dedup logic to the fallback. [`registry.py:278-281`]
- [ ] [Review][Patch] Job adapters fabricate `jobs@{platform_domain}` email — `vn_jobs` and `vietnamworks` derive `canonical_domain` from the job-board URL and add a fake `jobs@...` contact. Remove fake email; use real `hr_email` if available. [`vn_jobs.py:155-166`, `vietnamworks.py:155-166`]
- [ ] [Review][Patch] `muasamcong.extract_contact_candidates` casts `raw_specs` dict to `str` for phone regex — This matches numeric codes in the dict serialization as false phone numbers. [`muasamcong.py:138-158`]
- [ ] [Review][Patch] `ent_keywords` "công ty" / "doanh nghiệp" trigger enterprise for recruitment queries — A job query like "công ty AI tuyển dụng..." also runs `MuaSamCongLeadAdapter` and `EnterpriseProcurementLeadAdapter`. Remove or require additional enterprise-specific keywords. [`registry.py:197-214`]
- [ ] [Review][Patch] `muaban_bds` uses `seller_type` as `company_name` and `contact_name` — Values like `individual` or `pro` become the lead/company name. Use `contact_name` / `seller_name` / `company` fields. [`muaban_bds.py:129-135`]
- [ ] [Review][Patch] `_PRICE_RANGE_RE` does not support shorthand ranges — "3-5 tỷ", "20 - 30 triệu", and "lương 20 - 30 triệu" are not matched. [`_query_parser.py:40-45`]
- [ ] [Review][Patch] Registry test does not assert `muasamcong` / `enterprise` absent for job query — `test_resolve_job_intent_deduplicates_to_vn_jobs` only checks `batdongsan` and `vietnamworks`. [`tests/unit/lead_intelligence/test_lead_source_adapters.py:647-654`]
- [ ] [Review][Patch] Missing test for `last_execution_status` recovery after a degraded run — Add test that a second successful call resets `last_execution_status` from `degraded` to `ok`. [`tests/unit/lead_intelligence/test_lead_source_adapters.py`]

#### Defer
- [x] [Review][Defer] `resolve_muaban_bds_city` un-diacritized output vs `MuabanBdsScraper._CITY_ALIASES` — The scraper accepts both Vietnamese names and slugs and normalizes input, so mismatch is benign for common cities. Revisit if less common provinces fail. [`_query_parser.py:253`, `app/proprietary/platforms/muaban_bds/scraper.py:79-84`]
- [x] [Review][Defer] `VietnamWorks` location filter not wired — Spec explicitly states `locationId` is out of scope for v1 (`# locationId bỏ qua ở v1`). Revisit when VietnamWorks location API is available. [`vietnamworks.py:56-76`]

### Review Resolution

All review findings from 2026-08-21 were triaged and applied in the same session. Decisions were taken without further human input based on the spec and existing patterns:

1. `canonical_domain` for job adapters is derived from `company_website` when present, otherwise from the job-board `source_url` (matches the spec's `source_urls[0]` fallback and the existing `JobMarketLeadAdapter` pattern).
2. `VietnamWorks` PII redaction order remains **redact before extract**, matching the spec and the `jobs_aggregator` redaction policy; fake `jobs@domain` emails were removed.
3. `resolve_adapters_for_intent` now returns **all explicitly named** job sources; if none are named, it still deduplicates to one via the priority list.

Verification: `ruff check app/lead_intelligence` passed; `pytest tests/unit/lead_intelligence` 192 passed; `pytest tests/integration/lead_intelligence/test_lead_gen_orchestrator.py` 3 passed; `python -c "from app.app import app"` passed.
