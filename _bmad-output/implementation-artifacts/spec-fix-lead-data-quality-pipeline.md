---
title: 'Sửa lỗi chất lượng dữ liệu pipeline lead (BĐS + Job boards)'
type: 'bugfix'
created: '2026-10-01'
status: 'done'
baseline_revision: '435220dad35d61313c77037b74223d159390c87d'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Pipeline trích xuất lead có 6 lỗi chất lượng dữ liệu: (1) Batdongsan gán nguyên tiêu đề tin rao vặt làm company_name, (2) phone trong title bị bỏ sót, (3) source_url=None cho 100% lead BĐS, (4) industry=None cho 100% lead, (5) domain=None cho 92% lead, (6) lead sai địa bàn lọt qua pre-filter.

**Approach:** Sửa trực tiếp tại các adapter normalize_lead() và extract_contact_candidates(), bổ sung industry/domain mặc định theo nguồn, cải thiện location pre-filter fallback.

## Boundaries & Constraints

**Always:** Giữ backward-compatible — không thay đổi schema DB, chỉ cải thiện dữ liệu trả về. Mọi phone phải qua normalize_vietnamese_phone(). Giữ ReDoS-safe regex.

**Never:** Không thay đổi model SQLAlchemy Lead, không thay đổi NormalizedLead schema, không refactor persistence pipeline, không ảnh hưởng adapter khác ngoài batdongsan/job_market/vietnamworks.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| BĐS listing cá nhân không có project_name | title="Bán nhà 496 Xã Đàn; 40m2" | company_name="BĐS Xã Đàn - Đống Đa" (location-derived) | Fallback "BĐS [location]" |
| Phone trong title | title="LH 0973668873 Mr. Dương" | phone extracted, VerifiedContact created | Chuẩn hóa qua normalize_vietnamese_phone |
| BĐS listing có project_name | project_name="Vista Nam An Khánh" | company_name="Vista Nam An Khánh" (giữ nguyên) | Không thay đổi |
| Job IT tại HCM khi yêu cầu HN | location="Hồ Chí Minh", icp city="HN" | location_match_score thấp, pre_filter_by_icp reject | Graceful skip, không crash |
| Adapter BĐS | bất kỳ listing | raw_data["industry"]="Bất động sản" | Không có |
| Adapter job_market / vietnamworks | bất kỳ job post | raw_data["industry"] lấy từ job category nếu có | Fallback "Tuyển dụng" |

</intent-contract>

## Code Map

- `nowing_backend/app/lead_intelligence/adapters/batdongsan.py:144-164` -- normalize_lead(): company_name fallback logic cần sửa; cần set raw_data["industry"]="Bất động sản"; cần set source_url
- `nowing_backend/app/lead_intelligence/adapters/batdongsan.py:166-200` -- extract_contact_candidates(): cần thêm scan phone từ data["title"]
- `nowing_backend/app/lead_intelligence/adapters/batdongsan.py:80-97` -- _fetch_raw_listings(): cần đảm bảo truyền detail_url vào result dict "url"
- `nowing_backend/app/lead_intelligence/adapters/base.py:54-82` -- NormalizedLead: READ-ONLY, không sửa
- `nowing_backend/app/lead_intelligence/adapters/base.py:181-201` -- extract_phones_from_text(): utility hiện có, dùng lại
- `nowing_backend/app/lead_intelligence/adapters/job_market.py:134+` -- normalize_lead(): cần set raw_data["industry"] từ job category
- `nowing_backend/app/lead_intelligence/adapters/vietnamworks.py:174+` -- normalize_lead(): cần set raw_data["industry"]
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:789-791` -- persistence: industry=raw_data.get("industry"), domain=canonical_domain — READ-ONLY, không sửa
- `nowing_backend/app/lead_intelligence/services/lead_gen_orchestrator.py:350-400` -- pre_filter_by_icp(): kiểm tra location matching logic

## Tasks & Acceptance

**Execution:**
- `nowing_backend/app/lead_intelligence/adapters/batdongsan.py` -- Sửa normalize_lead() company_name: khi không có project_name/agency_name, dùng location-derived name "BĐS [quận] - [thành phố]" thay vì title; set source_url từ raw_data["url"]; set raw_data["industry"]="Bất động sản". Sửa extract_contact_candidates() thêm scan phone từ title.
- `nowing_backend/app/lead_intelligence/adapters/job_market.py` -- Sửa normalize_lead() set raw_data["industry"] từ job category nếu có, fallback "Tuyển dụng IT"
- `nowing_backend/app/lead_intelligence/adapters/vietnamworks.py` -- Sửa normalize_lead() set raw_data["industry"] từ job category, fallback "Tuyển dụng"
- `nowing_backend/tests/lead_intelligence/adapters/test_batdongsan_adapter.py` -- Thêm test cho company_name fallback, phone extraction từ title, source_url propagation, industry default

**Acceptance Criteria:**
- Given listing BĐS không có project_name/agency_name, when normalize_lead(), then company_name KHÔNG chứa toàn bộ tiêu đề tin rao mà dùng tên rút gọn theo địa bàn
- Given title chứa số điện thoại VN hợp lệ, when extract_contact_candidates(), then phone được trích xuất và chuẩn hóa
- Given bất kỳ listing BĐS có detail_url, when persist, then source_url != None
- Given bất kỳ lead từ bất kỳ adapter, when persist, then industry != None
- Given yêu cầu "tại Hà Nội" và lead có location "Hồ Chí Minh", when pre_filter_by_icp, then lead bị reject hoặc nhận location_match_score thấp

## Spec Change Log


## Review Triage Log

| ID | Layer | Finding / Gap | Verdict | Disposition / Action Taken |
|---|---|---|---|---|
| EC-01 | Edge Case | Address comma-only `IndexError` khi split chuỗi địa chỉ rỗng/chỉ có dấu phẩy `, , ,` | high | **Patched**: Bổ sung guard lọc rỗng và fallback an toàn trong `_derive_bds_company_name()` |
| EC-02 | Edge Case | Regex quét SĐT trong `title` có thể bắt nhầm dãy số không phải SĐT VN | medium | **Patched**: Bổ sung xác thực tiền tố nhà mạng VN (`_VALID_VN_PREFIXES`) và giới hạn độ dài 10-11 chữ số |
| EC-03 | Edge Case | Lỗi duyệt từng ký tự (string iteration) khi `negative_keywords` hoặc `target_locations` là chuỗi thay vì list | medium | **Patched**: Ép kiểu/chuẩn hóa danh sách từ khóa và địa điểm thành list chuỗi hợp lệ |
| EC-04 | Edge Case | Lỗi so khớp chuỗi fallback địa điểm mục tiêu khi thiếu cấu trúc tỉnh/thành chuẩn | medium | **Patched**: Chuẩn hóa không dấu và so khớp mềm cho cả cấp tỉnh/thành lẫn quận/huyện |
| BH-01 | Blind Hunter | Deduplication BFS clustering gom toàn bộ lead chung domain nền tảng tuyển dụng/BĐS aggregator | high | **Patched**: Khai báo `AGGREGATOR_PLATFORM_DOMAINS` trong `deduplication_service.py` để bỏ qua cluster key `domain:...` cho các trang tổng hợp |
| BH-02 | Blind Hunter | `company_name` vượt quá giới hạn 200 ký tự gây lỗi ghi DB PostgreSQL `String(200)` | high | **Patched**: Cắt gọn chuỗi tên thực thể và cap tối đa 200 ký tự |
| VG-01 | Verification Gap | Thiếu test case kiểm thử `_fetch_raw_listings()` trả về `detail_url` | medium | **Patched**: Bổ sung test kiểm tra trích xuất và tổng hợp `url` từ listing data |
| VG-02 | Verification Gap | Thiếu test case ưu tiên trường `city` và trích xuất `source_url` từ `job_market` | medium | **Patched**: Bổ sung test kiểm thử precedence của `city` và kiểm tra `source_url` |
| VG-03 | Verification Gap | Thiếu test case cho trường hợp nhắm mục tiêu toàn quốc (`Toàn quốc`) | low | **Patched**: Bổ sung test case nhắm mục tiêu `Toàn quốc` không lọc bỏ lead |

## Auto Run Result

- **Trạng thái:** Thành công hoàn toàn (`success`).
- **Tổng hợp sửa đổi:**
  1. `batdongsan.py`: Tạo tên công ty rút gọn theo địa bàn (`BĐS {quận} - {thành phố}`), cap 200 ký tự, trích xuất SĐT từ title với regex an toàn, gán `industry = "Bất động sản"`, và bảo đảm `source_url` không bị `None`.
  2. `job_market.py` & `vietnamworks.py`: Gán mặc định ngành tuyển dụng thay vì `None`, trích xuất domain đúng nguồn, tối ưu type checks.
  3. `lead_gen_orchestrator.py`: Nâng cấp pre-filter vị trí hỗ trợ cả Pydantic criteria và dict, loại bỏ lead sai tỉnh thành, an toàn kiểu dữ liệu.
  4. `deduplication_service.py`: Loại trừ các aggregator domains khỏi cluster grouping.
- **Kết quả kiểm thử:**
  - `test_batdongsan_adapter.py`: 14/14 tests PASSED.
  - Regression test suites (`test_lead_source_adapters.py`, `test_location_prefilter.py`, `test_lead_gen_orchestrator.py`): 38/38 tests PASSED.
  - Linter Ruff: Sạch 100%, không còn warning hay error.


## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/python -m pytest tests/lead_intelligence/adapters/test_batdongsan_adapter.py -v` -- expected: all tests pass
- `cd nowing_backend && .venv/bin/python -m pytest tests/lead_intelligence/ -v -k "normalize"` -- expected: no regressions
