---
story: "13.3"
reviewed_commit: eda4fcd76
parent_commit: c504de1a7
reviewer: bmad-code-review
review_date: "2026-08-07"
verdict: changes_requested
---

# BMAD Code Review — Story 13.3: Unified canonical + document search API

## Tóm tắt phán quyết

- **Mức độ:** `CHANGES_REQUESTED` — còn **2 must-fix**, **5 should-fix**, **3 watch**.
- **Rủi ro chính:**
  - `view_sources.href` trong response trỏ đến route **404** (không có `GET /canonical-entities/{id}/sources`).
  - GIN index `canonical_entities_search_text` được tạo với `english` nhưng query dùng `simple`, khiến index **không bao giờ được dùng**, ảnh hưởng p95 và đồng thuận stop-word.
  - API thiếu pagination, `total` chỉ là số item trả về (`≤ top_k`), không phải tổng match.
- **Kiểm thử:** `ruff` pass; 34 test liên quan pass; fixture quality đạt recall@10 ≥ 0.85 và precision@5 ≥ 0.80.

> **Lưu ý quy trình:** File story `13-3-unified-canonical-document-search-api.md` không tồn tại dưới `_bmad-output/implementation-artifacts/stories/`. Review dựa trên AC tại `_bmad-output/planning-artifacts/epics.md:1419-1440` và UX contract tại `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-canonical-entity.md:24-32`.

## Diff phạm vi

- 9 file thay đổi, ~1592 dòng insert, ~8 dòng xóa.
- File mới chính: `nowing_backend/app/canonical/services/unified_search_service.py`.
- File sửa: `nowing_backend/app/routes/canonical_entities_routes.py`, `nowing_backend/app/retriever/documents_hybrid_search.py`, `nowing_backend/app/config/__init__.py`.
- Test mới: `tests/integration/canonical/test_unified_search.py`, `tests/integration/canonical/test_unified_search_quality.py`, `tests/integration/routes/test_canonical_routes.py`, `tests/unit/canonical/test_unified_search_rrf.py`, `tests/integration/canonical/conftest.py`.

## Static Analysis

```bash
cd nowing_backend
ruff check \
  app/canonical/services/unified_search_service.py \
  app/config/__init__.py \
  app/retriever/documents_hybrid_search.py \
  app/routes/canonical_entities_routes.py \
  tests/integration/canonical/conftest.py \
  tests/integration/canonical/test_unified_search.py \
  tests/integration/canonical/test_unified_search_quality.py \
  tests/integration/routes/test_canonical_routes.py \
  tests/unit/canonical/test_unified_search_rrf.py
```

**Result:** All checks passed.

## Automated Test Results

```bash
cd nowing_backend
pytest \
  tests/integration/canonical/test_unified_search.py \
  tests/integration/canonical/test_unified_search_quality.py \
  tests/integration/routes/test_canonical_routes.py \
  tests/unit/canonical/test_unified_search_rrf.py \
  tests/integration/google_unification/test_hybrid_search_type_filtering.py \
  tests/integration/agents/multi_agent_chat/shared/retrieval/test_hybrid_search.py -q
```

**Result:** `34 passed, 13 warnings in 4.21s`.

> Chú ý: Lần chạy test song song (hai shell pytest cùng lúc) gặp lỗi `CREATE EXTENSION IF NOT EXISTS vector` do race condition giữa các session trên cùng test DB. Khi chạy **một shell duy nhất** thì pass sạch.

## Đánh giá Acceptance Criteria

| AC (theo `epics.md`) | Đánh giá | Ghi chú |
|---|---|---|
| 1. Document + canonical chạy song song, dùng cùng workspace/date/status/type filter | **Hầu hết** | Cùng filter được áp, nhưng `start_date`/`end_date` dùng cột `last_seen_at` (canonical) và `updated_at` (document) — khác ngữ nghĩa. |
| 2. Weighted RRF `w_vector/(k+rank) + w_fts/(k+rank_fts)` với `k=60`, `0.7/0.3` | **Đạt** | Đúng cả canonical (Python fuse) và document (SQL CTE). Cho phép cấu hình non-negative. |
| 3. NULL/stale/non-ready embedding vẫn eligible qua FTS, bị loại khỏi vector | **Đạt** | Vector CTE lọc `embedding IS NOT NULL`, model đúng, `embedding_status = ready`; FTS CTE không lọc vector. |
| 4. Document/source row linked qua `canonical_entity_sources` được gộp dưới entity | **Hầu hết** | Gộp đúng trong test, nhưng chỉ khi `source_name == "document"` — bỏ lỡ source tên khác hoặc gây nhầm nếu `source_record_id` trùng doc id. |
| 5. API trả source count, source-link IDs, confidence, conflict, View N sources expansion | **Cần sửa** | `view_sources.href` là route 404; thiếu `canonical_data` preview (UX A5). |
| 6. Workspace isolation: cả hai corpus dùng cùng authenticated workspace context | **Đạt** | Route check `documents:read` + `canonical_entities:read`; canonical RLS context được `SET LOCAL` trước query. |
| 7. Benchmark recall@10 ≥ 0.85, precision@5 ≥ 0.80, duplicate top-level = 0, p95 < 500 ms | **Hầu hết** | Test fixture pass; nhưng FTS index mismatch đe dọa p95 khi bảng lớn. |
| 8. Metrics/alerts khi p95 vượt 500 ms hoặc embedding/outbox fail vượt ngưỡng | **Đạt** | `_record_embedding_status_counts` và `_check_outbox_failure_threshold` không log query PII. |

## Adversarial Findings

### [must-fix]

#### M1. `view_sources.href` trỏ đến route không tồn tại (404)

- **File/lines:** `nowing_backend/app/canonical/services/unified_search_service.py:439-443`
- **Mô tả:** Response của canonical entity chứa:
  ```python
  "view_sources": {
      "href": f"/canonical-entities/{entity['id']}/sources",
      "count": max(...),
  }
  ```
  Trong `nowing_backend/app/routes/canonical_entities_routes.py` (từ dòng 1 đến 531) **không có** route `GET /canonical-entities/{id}/sources`. Chi tiết entity (`GET /canonical-entities/{id}`) đã trả `sources`, nhưng href tích hợp sẵn vẫn 404. Vi phạm AC-5 ("workspace-authorized `View N sources` expansion contract") và UX contract A3 ("Click 'View N sources' → inline expand").
- **Bằng chứng:** Grep `canonical-entities.*sources` trong `nowing_backend/app/routes` trả về 0 kết quả.
- **Đề xuất sửa:**
  - Nhanh nhất: sửa `href` thành `/api/v1/canonical-entities/{entity['id']}` (endpoint detail đã có).
  - Hoặc thêm route `GET /api/v1/canonical-entities/{id}/sources` trả list source tương ứng.

#### M2. FTS index `canonical_entities.search_text` dùng `english`, query dùng `simple`

- **File/lines:**
  - Query: `nowing_backend/app/canonical/services/unified_search_service.py:224-225`
  - ORM index: `nowing_backend/app/db.py:3752-3755`
  - Migration: `nowing_backend/alembic/versions/193_add_canonical_entities.py:112`
- **Mô tả:** Query full-text canonical dùng `to_tsvector('simple', CanonicalEntity.search_text)` để không drop stop-word ngắn (ví dụ "By"). Index GIN lại được định nghĩa trên `to_tsvector('english', search_text)`. PostgreSQL **không dùng** GIN index khi expression trong query khác expression trong index; query sẽ table scan. Vi phạm ngầm AC-7 (p95 < 500 ms) và làm sai lệch kết quả nếu index và query xử lý stop-word khác nhau.
- **Bằng chứng:**
  - `app/db.py:3754`: `text("to_tsvector('english', search_text)")`
  - `alembic/versions/193_add_canonical_entities.py:112`: `CREATE INDEX ix_canonical_entities_search_text ON canonical_entities USING gin (to_tsvector('english', search_text));`
  - `unified_search_service.py:224`: `tsvector = func.to_tsvector("simple", CanonicalEntity.search_text)`
- **Đề xuất sửa:**
  - Sửa index và migration thành `to_tsvector('simple', search_text)` (đồng nhất với query và giữ yêu cầu không drop stop-word).
  - Hoặc sửa query về `english` nếu chấp nhận drop stop-word (không khuyến nghị).

### [should-fix]

#### S1. API thiếu pagination, `total` chỉ là số item trả về

- **File/lines:** `nowing_backend/app/routes/canonical_entities_routes.py:428-430, 494`
- **Mô tả:** `UnifiedSearchResponse` chỉ có `items` và `total`; `total = len(items)` (≤ `top_k` ≤ 50). Không có `skip`, `page`, `page_size`, `has_more`. Người dùng không thể duyệt trang thứ 2, và `total` dễ bị hiểu nhầm là tổng số match.
- **Đề xuất sửa:**
  - Hỗ trợ `skip`/`offset` (hoặc `page`) trong `UnifiedSearchRequest`.
  - Trả về `PaginatedResponse[UnifiedSearchResult]` đồng nhất với `list_canonical_entities`, hoặc đổi tên `total` thành `returned` nếu không muốn pagination.

#### S2. Document collapse chỉ xảy ra khi `source_name == "document"`

- **File/lines:** `nowing_backend/app/canonical/services/unified_search_service.py:399-404`
- **Mô tả:** Logic gộp document dưới canonical entity chỉ kích hoạt khi `row.source_name == "document"` **và** `source_record_id` parse được thành `int`. Nếu source thực sự là một document nhưng được lưu với tên khác (ví dụ `source_name` là connector/scraper tên), collapse sẽ bỏ lỡ. Ngược lại, nếu một source không phải document có `source_record_id` là số trùng `document.id`, việc gộp theo số sẽ nhầm.
- **Đề xuất sửa:**
  - Thêm trường `source_type` hoặc `is_document` trong `CanonicalEntitySource`, hoặc
  - Quy ước và **enforce** rằng mọi source liên kết với `Document` phải có `source_name="document"` tại `canonical_persist_service`.

#### S3. `document_types`, `entity_types`, `statuses`, `embedding_status` không được validate

- **File/lines:**
  - `nowing_backend/app/retriever/documents_hybrid_search.py:252-260` (silent `KeyError`)
  - `nowing_backend/app/routes/canonical_entities_routes.py:441` (`UnifiedSearchRequest` schema)
  - `nowing_backend/app/canonical/services/unified_search_service.py:229-236` (pass-through)
- **Mô tả:**
  - `document_types` chứa string lạ → `DocumentType[dt]` raise `KeyError` bị suppress, retriever trả `[]` mà không lỗi 400.
  - `embedding_status` nhận bất kỳ string nào; string sai cả hai CTE trả rỗng.
  - `statuses` không ràng buộc các giá trị hợp lệ của `Document.status["state"]`.
- **Đề xuất sửa:** Validate enum trong `UnifiedSearchRequest` bằng Pydantic `Field` hoặc `model_validator`, hoặc trong service raise `ValueError`/`HTTPException 400`.

#### S4. Unified canonical entity response thiếu `canonical_data` preview

- **File/lines:** `nowing_backend/app/canonical/services/unified_search_service.py:349-360`; `nowing_backend/app/routes/canonical_entities_routes.py:394-406`
- **Mô tả:** `UnifiedSearchEntity` chỉ có `canonical_title`. UX contract A5 yêu cầu "Canonical data preview — Card hiển thị canonical values (merged price, normalized location)". Hiện tại response không trả `canonical_data`; UI search card không thể hiển thị giá trị canonical đã merge.
- **Đề xuất sửa:** Thêm trường `canonical_data: dict[str, Any]` vào `UnifiedSearchEntity` và service. Nếu lo PII, trả một `preview` subset đã redact theo AD-25.

#### S5. `start_date`/`end_date` dùng cột timestamp khác nhau cho document và canonical

- **File/lines:**
  - Canonical: `nowing_backend/app/canonical/services/unified_search_service.py:232-234` (`last_seen_at`)
  - Document: `nowing_backend/app/retriever/documents_hybrid_search.py:101-104, 267-270` (`updated_at`)
- **Mô tả:** Cùng một cặp tham số `start_date`/`end_date` trong request nhưng áp lên cột khác nhau. User có thể ngạc nhiên khi document lọc theo `updated_at` còn entity lọc theo `last_seen_at`.
- **Đề xuất sửa:** Thống nhất ngữ nghĩa (ví dụ document dùng `updated_at` cũng đồng nhất với lịch sử re-index) hoặc tách thành `canonical_start_date`/`document_start_date` và document rõ ràng trong API docs.

#### S6. `w_vector` và `w_fts` có thể cùng bằng 0

- **File/lines:** `nowing_backend/app/canonical/services/unified_search_service.py:120-121`; `nowing_backend/app/routes/canonical_entities_routes.py:443-444`
- **Mô tả:** Chỉ từ chối số âm, không kiểm tra `w_vector + w_fts > 0`. Nếu cả hai bằng 0, mọi RRF score đều 0, ranking ngẫu nhiên (tie-break bằng `str(entity_id)`).
- **Đề xuất sửa:** Thêm validator `w_vector + w_fts > 0` trong service hoặc Pydantic `model_validator`.

### [watch]

#### W1. `source_count` trong DB có thể stale, fallback `max()` không đồng bộ

- **File/lines:** `nowing_backend/app/canonical/services/unified_search_service.py:430-432, 441-443`
- **Mô tả:** `source_count` lấy từ DB rồi `max` với `len(source_ids)` vừa load. Nếu DB count lớn hơn thực, response vẫn trả sai. Không có guard bắt buộc đồng bộ.
- **Đề xuất sửa:** Cân nhắc tính `source_count` từ `source_ids` thực tế trong response hoặc thêm check `source_count` đồng bộ khi upsert source.

#### W2. `matched_chunk_ids` luôn rỗng trong `UnifiedSearchDocument`

- **File/lines:** `nowing_backend/app/retriever/documents_hybrid_search.py:410`
- **Mô tả:** Response shape khai báo `matched_chunk_ids: list[int]` nhưng field này không bao giờ được populate trong `hybrid_search`.
- **Đề xuất sửa:** Populate (cần biết chunk nào match `tsquery`) hoặc xóa khỏi schema nếu không dùng.

#### W3. Kiểm thử RLS ở non-owner role chưa có

- **File/lines:** `tests/integration/canonical/test_unified_search.py:417-448`
- **Mô tả:** Test workspace isolation dựa trên explicit `workspace_id` filter; chưa có test đóng vai role non-owner `NOBYPASSRLS` hoặc `current_setting('app.workspace_id')` bị unset để xác minh RLS fail-closed. Story 13.1 đã có raw SQL test, nhưng 13.3 chưa kế thừa.
- **Đề xuất sửa:** Thêm integration test dùng asyncpg non-owner connection hoặc assert `SET LOCAL` bị xóa sau transaction.

## Những điểm làm tốt

- RRF k=60, trọng số mặc định 0.7/0.3, và xử lý missing rank bằng 0 contribution đúng spec.
- Vector eligibility: loại embedding NULL, stale model, non-ready khỏi vector CTE nhưng vẫn giữ trong FTS CTE.
- `query_embedding` chỉ tính một lần, dùng `asyncio.to_thread` cho sync embedder.
- Authz: route yêu cầu cả `documents:read` và `canonical_entities:read`, phù hợp AC-6.
- Canonical RLS context được `SET LOCAL` trước query, fail-closed khi context thiếu.
- Unit test `_rrf_score` và `_is_vector_eligible` đầy đủ; integration test collapse/isolation/filter đều pass.
- Quality benchmark với `bds-overlap-30.jsonl` đạt ngưỡng recall/precision.
- Metrics `_record_embedding_status_counts` và `_check_outbox_failure_threshold` không chứa query text.

## Phân loại tổng hợp

| Loại | Số lượng | Danh sách ID |
|---|---|---|
| must-fix | 2 | M1, M2 |
| should-fix | 5 | S1, S2, S3, S4, S5, S6 |
| watch | 3 | W1, W2, W3 |

## Hành động tiếp theo

1. Dev agent thực hiện **M1** (sửa `view_sources.href` hoặc thêm route) và **M2** (sửa GIN index `simple` / migration) trước khi merge/chuyển `done`.
2. Xử lý **S1** (pagination) và **S3** (validate filter enums) để API ổn định cho UI.
3. Cân nhắc **S2** (document collapse dựa trên source type), **S4** (`canonical_data` preview), **S5** (thống nhất date filter), **S6** (RRF weight > 0).
4. Sau khi sửa, re-run **4.8 BMAD code-review** trên cùng test matrix.
5. Tiếp tục pipeline:
   - **4.10 mutation gate** (khuyến nghị P0)
   - **4.13 human-review gate** (P0 cho authz/PII)

---

*BMAD review: tập trung search queries, RLS, pagination, filters, authz, response shape. Không push.*
