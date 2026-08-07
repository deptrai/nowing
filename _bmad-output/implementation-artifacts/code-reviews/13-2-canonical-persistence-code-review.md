---
story: '13.2 Canonical BDS/Jobs Persistence, Retry, Merge, PII, Dedup Benchmark'
reviewed_commit: 7f964ca4a
parent_commit: 82ed5f48a
reviewer: bmad-code-review
review_date: '2026-08-07'
verdict: changes_requested
---

# BMAD Code Review — Story 13.2 (a-e)

## Tóm tắt phán quyết

- **Mức độ:** `CHANGES_REQUESTED` — còn **3 must-fix**, **4 should-fix**, **6 watch**, **3 non-issue**.
- **Rủi ro chính:**
  - `canonical_persist_outbox` chỉ được stage nhưng **không có worker thực sự retry**; `retry_persist_outbox` chỉ đổi `status` và chưa dispatch lại payload.
  - `upsert_canonical_entity` vẫn dùng `WHERE version == new_version` trong guard compare-and-swap, khiến guard vô hiệu. `ConcurrentUpdateError` đã được thêm nhưng không raise tại đây.
  - Fallback `source_record_id` về tên source / `source:unknown` khi `id` thiếu có thể gây collision và làm mất / di chuyển sai source link.
  - `phone_key` dùng SHA-256 thuần (không keyed), không đáp ứng yêu cầu 'one-way keyed digest'.
- **Kiểm thử:** `ruff check` còn 3 lỗi trên các file thay đổi; `pytest` unit/integration/benchmark đều pass; `nowing_evals canonical dedup` pass 6/6 fixtures với P=R=F1=1.0.

## Thống kê diff

- 50 files thay đổi, +5694 / −254 dòng (theo `git diff --stat 82ed5f48a..7f964ca4a`).
- Phạm vi chính:
  - `nowing_backend/app/canonical/services/canonical_persist_service.py`, `canonical_pii.py`
  - `nowing_backend/app/services/{bds,jobs}_aggregator/orchestrator.py`, `dedupe.py`, `normalize.py`, `schemas.py`
  - `nowing_backend/app/routes/canonical_entities_routes.py`, `app/routes/__init__.py`, `app/zero_publication.py`
  - `nowing_backend/alembic/versions/194_add_canonical_merge_history_source_ids.py`
  - `nowing_evals/src/nowing_evals/suites/canonical/dedup.py`, `core/cli.py`, `core/registry.py`, fixtures
  - `scripts/canonical_dedup_gate.py`, tests mới trong `tests/unit/canonical/` và `tests/integration/canonical/`

## Kiểm thử đã chạy

```bash
# Ruff trên file Python bị ảnh hưởng
cd nowing_backend
ruff check $(git -C .. diff --name-only --diff-filter=ACM 82ed5f48a..7f964ca4a -- '*.py' | grep '^nowing_backend/' | sed 's|^nowing_backend/||')
# -> I001 alembic/versions/194_add_canonical_merge_history_source_ids.py

cd ../nowing_evals
ruff check $(git -C .. diff --name-only --diff-filter=ACM 82ed5f48a..7f964ca4a -- '*.py' | grep '^nowing_evals/' | sed 's|^nowing_evals/||')
# -> F841, SIM108 trong data/canonical/fixtures/generate_canonical_fixtures.py

ruff check ../scripts/canonical_dedup_gate.py
# -> pass

# Pytest
cd nowing_backend
pytest tests/unit/canonical -q
# -> 26 passed
pytest tests/integration/canonical -q
# -> 41 passed
pytest tests/integration/routes/test_canonical_routes.py -q
# -> 7 passed
pytest tests/unit/services/bds_aggregator/test_dedupe.py tests/unit/services/jobs_aggregator/test_dedupe.py -q
# -> 6 passed

# Dedup benchmark
cd ../nowing_evals
for d in bds jobs; do
  for o in 15 30 70; do
    python -m nowing_evals run canonical dedup --domain $d --fixture ${d}-overlap-$o
  done
done
# -> 6/6 PASS, P=1.0000 R=1.0000 F1=1.0000
```

## Đánh giá Acceptance Criteria

| AC | Đánh giá | Ghi chú |
|----|----------|---------|
| **13.2a** BDS persistence & retry | **Hầu hết** | `vn_bds.aggregate` truyền `workspace_id`/`session`, upsert idempotent, `source_count` tính từ DB, `persistence_status` trả về. **Thiếu worker retry** (M1). |
| **13.2b** Jobs persistence & retry | **Hầu hết** | `aggregate_jobs` dùng cùng contract, PII redaction trước dedup, partial persistence test pass. **Thiếu worker retry** (M1). |
| **13.2c** Merge history / conflict / revert | **Hầu hết** | `canonical_merge_history` ghi version/source set before/after. Revert check `current.version == history.new_version`. CAS trong `revert` đúng (`previous_version`). **CAS trong `upsert` sai** (M2). Concurrent merge test pass nhờ `expected_version`. |
| **13.2d** PII-safe canonicalization | **Hầu hết** | Dữ liệu canonical, source snapshot, merge history, outbox payload đều redacted. `phone_key` được digest, `contact`/`phone` bị loại bỏ. **SHA-256 không keyed** (M4). |
| **13.2e** Dedup benchmark & release gate | **Pass** | Fixtures 15/30/70% cho cả BDS/Jobs, hard gates `P>=0.95, R>=0.90, F1>=0.92` đạt. Benchmark đăng ký trong `nowing_evals`. Cảnh báo: fixtures quá dễ, P/R/F1=1.0 (W3). |

## Findings (theo lớp review)

### [must-fix]

#### M1. `canonical_persist_outbox` được tạo nhưng không có worker retry thực sự

- **File/lines:**
  - `nowing_backend/app/canonical/services/canonical_persist_service.py:109-134` (`create_persist_outbox`), `628-641` (`retry_persist_outbox`)
  - `nowing_backend/app/services/bds_aggregator/orchestrator.py:231-267` (`_stage_bds_persist_outbox`), `295-303`
  - `nowing_backend/app/services/jobs_aggregator/orchestrator.py:151-183` (`_stage_jobs_persist_outbox`), `249-257`
- **Mô tả:** Khi persistence fail, hai orchestrator gọi `create_persist_outbox` để ghi payload đã redact và metric `record_canonical_persist_failure`. Tuy nhiên `retry_persist_outbox` chỉ đặt `status='processing'` và tăng `retry_count`, nhưng **không cập nhật `next_attempt_at`, không dispatch lại payload, không chuyển sang `done/failed`, không gọi `upsert_canonical_entity`**. Không có Celery task nào lặp lấy `status='pending'` và xử lý. Do đó AC 'retries cannot create duplicate entities or source links' chưa được thực hiện — không có retry.
- **Bằng chứng:** `grep -R retry_persist_outbox` chỉ tìm thấy định nghĩa, không có caller. `grep -R canonical_persist_outbox` trong Celery tasks / workers cho 0 kết quả ngoài model.
- **Đề xuất sửa:**
  1. Hoàn thiện `retry_persist_outbox` để cập nhật `next_attempt_at`, chuyển status, log error, và gọi `upsert_canonical_entity` với payload.
  2. Thêm Celery task (ví dụ `process_canonical_persist_outbox`) lên lịch chạy định kỳ hoặc retry backoff, query `canonical_persist_outbox` theo `(status, next_attempt_at)`.
  3. Đảm bảo `set_canonical_workspace_id(session, outbox.workspace_id)` được gọi trước khi đọc/ghi bảng có RLS.

#### M2. Version compare-and-swap trong `upsert_canonical_entity` vẫn sai

- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:358-378`
- **Mô tả:** Code đọc `previous_version = existing.version`, tính `new_version = previous_version + 1`, sau đó thực hiện `UPDATE ... WHERE CanonicalEntity.id == existing.id AND CanonicalEntity.version == new_version`. Điều kiện `WHERE` so sánh với `new_version` — một giá trị **chưa tồn tại trong DB** — nên guard này không bao giờ match. Kết quả `rowcount == 0` nhưng không được kiểm tra. Thực tế update phụ thuộc vào SQLAlchemy ORM flush, không phải CAS. 13.1 review đã chỉ ra lỗi này (M2) và phiên bản 13.2 chưa sửa ở `upsert`.
- **Đề xuất sửa:**
  - `WHERE CanonicalEntity.version == previous_version`.
  - Kiểm tra `result.rowcount == 1`, nếu 0 thì raise `ConcurrentUpdateError`.
  - Bổ sung test riêng cho trường hợp concurrent upsert mà không truyền `expected_version`.

#### M3. Fallback `source_record_id` khi thiếu `id` dễ gây collision và di chuyển sai source

- **File/lines:**
  - BDS: `nowing_backend/app/services/bds_aggregator/orchestrator.py:210-228`
  - Jobs: `nowing_backend/app/services/jobs_aggregator/normalize.py:121-151` và `orchestrator.py:212-229`
- **Mô tả:**
  - BDS: `source_record_id = str(raw_source_id if raw_source_id is not None else source)`. Nếu nhiều listing từ cùng source không có `id`, tất cả sẽ có `source_record_id == 'batdongsan'`. Vì unique constraint trên `canonical_entity_sources` là `(workspace, entity_type, source_name, source_record_id)` **không chứa `canonical_entity_id`**, các source sẽ bị di chuyển qua lại giữa các entity và `source_count` bị sai.
  - Jobs: `normalize_listing` gán `listing_id = f'{source}:unknown'` khi `raw.get('id')` là `None`, rồi `_source_record_ids = {source: str(listing_id)}`. Nhiều record thiếu `id` từ cùng source sẽ có cùng `source_record_id`, dẫn đến conflict khi upsert hoặc ghi đè trong `deduplicate` (`merged_record_ids.update(item._source_record_ids)`).
- **Bằng chứng:** Trong `test_bds_persistence.py` và `test_jobs_persistence.py`, mọi fixture đều cung cấp `id`. Không có test nào cho trường hợp `id` thiếu.
- **Đề xuất sửa:**
  - Từ chối record khi thiếu `id` nếu nó bắt buộc cho provenance.
  - Hoặc sinh `source_record_id` duy nhất từ hash nội dung record (title, company, source_url, …) thay vì dùng tên source.
  - Thêm test integration cho trường hợp thiếu `id` để đảm bảo `source_count` chính xác.

### [should-fix]

#### S1. `backfill_canonical_embedding` vẫn `SELECT` trước khi set workspace context

- **File/lines:** `nowing_backend/app/canonical/tasks/backfill_canonical_embedding.py:31-49`
- **Mô tả:** Task thực hiện `select(CanonicalEntity)` ở dòng 31-34, sau đó mới gọi `set_canonical_workspace_id` ở dòng 49. Dưới app role `NOBYPASSRLS` với `FORCE RLS`, SELECT đầu tiên sẽ không nhìn thấy dòng nào vì `current_setting('app.workspace_id', true)` là rỗng/NULL. Lỗi này đã được 13.1 (M1) chỉ ra và vẫn chưa khắc phục trong 13.2. `_enqueue_embedding_backfill` trong `canonical_persist_service.py:55-63` cũng không truyền `workspace_id` vào task.
- **Đề xuất sửa:** Truyền `workspace_id` trong `args` của Celery task, gọi `set_canonical_workspace_id` trước SELECT.

#### S2. `phone_key` dùng SHA-256 thuần thay vì keyed digest

- **File/lines:** `nowing_backend/app/canonical/services/canonical_pii.py:60-68`
- **Mô tả:** `_one_way_digest` dùng `hashlib.sha256(value.encode('utf-8')).hexdigest()` mà không dùng secret. AC 13.2d yêu cầu 'one-way keyed digest may be retained only when required for matching'. SHA-256 thuần dễ bị tấn công bảng băm với không gian số điện thoại nhỏ.
- **Đề xuất sửa:** Sử dụng HMAC-SHA256 với key từ `config` (ví dụ `CANONICAL_PII_DIGEST_KEY`). Nếu cần deterministic trong test, key cố định trong môi trường test.

#### S3. Ruff vẫn còn lỗi trên các file thay đổi

- **File/lines:**
  - `nowing_backend/alembic/versions/194_add_canonical_merge_history_source_ids.py:7-13` (`I001` import block)
  - `nowing_evals/data/canonical/fixtures/generate_canonical_fixtures.py:110` (`F841` `single_count` assigned but unused), `116-119` (`SIM108` ternary)
- **Mô tả:** Các lỗi lint còn sót. `F841` và `SIM108` không phải bug nhưng cho thấy fixture generator chưa dọn dẹp; `I001` trong migration cần format.
- **Đề xuất sửa:** Chạy `ruff check --fix` hoặc xóa biến `single_count`, dùng ternary, sắp xếp lại imports.

#### S4. `resolve_canonical_conflict` lưu `canonical_title` vào cả cột và `canonical_data` gây trùng lặp

- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:583-601`
- **Mô tả:** Khi `field == 'canonical_title'`, code cập nhật `entity.canonical_title = value`, đồng thời đưa `'canonical_title': value` vào `new_data` rồi gán `entity.canonical_data = new_data`. Cột `canonical_title` lưu ở bảng, còn `canonical_data` lưu ở JSONB. Dẫn đến hai nơi chứa cùng thông tin, dễ sai lệch khi revert hoặc merge sau này.
- **Đề xuất sửa:** Nếu `field == 'canonical_title'`, chỉ cập nhật cột `entity.canonical_title`, không đưa vào `canonical_data`.

### [watch]

#### W1. `retry_persist_outbox` không set RLS workspace context

- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:628-641`
- **Mô tả:** Hàm đọc/ghi `CanonicalPersistOutbox` nhưng không gọi `set_canonical_workspace_id`. Nếu được gọi từ Celery worker, RLS có thể chặn. Ngoài ra nó chỉ `SELECT ... get()` và `UPDATE`, chưa thực hiện payload.

#### W2. Revert không khôi phục `canonical_title` và `search_text`

- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:519-535`
- **Mô tả:** Hàm `revert_canonical_entity` chỉ khôi phục `canonical_data` và xóa embedding, còn `canonical_title` và `search_text` giữ nguyên giá trị hiện tại. Comment `ponytail` ghi nhận giới hạn này. Nếu merge thay đổi title/search_text, revert sẽ không trả về trạng thái cũ hoàn toàn.

#### W3. Fixtures benchmark quá dễ, P/R/F1 = 1.0 không phản ánh thực tế

- **File/lines:** `nowing_evals/data/canonical/fixtures/generate_canonical_fixtures.py:31-104`, `nowing_evals/src/nowing_evals/suites/canonical/dedup.py:183-225`
- **Mô tả:** Cả 6 fixtures đều cho P=R=F1=1.0 vì BDS multi-source record chia sẻ cùng `phone`/`address`, Jobs chia sẻ cùng `(company, title, location, posted_at)`. Hard gates (P≥0.95, R≥0.90, F1≥0.92) đạt nhưng không kiểm chứng khả năng phân biệt khi dữ liệu noisy. AC 13.2e cho phép dùng fixtures synthetic, nhưng nên bổ sung tier 'hard' với nhiễu thực tế hơn trước khi release.

#### W4. `source_count` vẫn dễ inconsistent khi source record di chuyển concurrent

- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:185-247`
- **Mô tả:** `_upsert_source` dùng `ON CONFLICT DO UPDATE` để di chuyển source, sau đó `_update_source_count` tính lại. Tuy nhiên `with_for_update` chỉ khóa `canonical_entities`, không khóa `canonical_entity_sources`. Trong concurrent, count có thể tính trên snapshot cũ.

#### W5. `canonical_pii` redact theo key, không xử lý PII lẫn trong văn bản tự do

- **File/lines:** `nowing_backend/app/canonical/services/canonical_pii.py:71-87`, `app/services/pii/redact.py:35-61`
- **Mô tả:**
  - BDS: chỉ drop theo key (`contact`, `phone`, `seller_name`, …). Nếu `title`, `location` chứa số điện thoại trực tiếp, nó vẫn lọt vào canonical.
  - Jobs: `redact_job_pii` xử lý JD text, nhưng danh sách họ Việt Nam cố định và pattern email/phone có thể bị bypass bởi các biến thể (dấu cách, dấu chấm, 'at' thay '@').

#### W6. Các route canonical load entity trước khi set RLS context

- **File/lines:** `nowing_backend/app/routes/canonical_entities_routes.py:250-268` (`get_canonical_entity`), `271-291` (`get_canonical_entity_history`), `294-335` (`revert`), `338-381` (`resolve`)
- **Mô tả:** Các route gọi `_load_entity_with_sources_and_history` hoặc `_load_entity_for_permission` trước khi `set_canonical_workspace_id`. Với app role `NOBYPASSRLS`, SELECT đầu tiên có thể trả về 0 dòng do RLS. `list_canonical_entities` đã set đúng thứ tự.

### [non-issue]

- **N1.** `sprint-status.yaml` ghi `13-2: done` trong khi hai file story `13-2b` và `13-2e` vẫn để `Status: in-progress`. Đây là drift tài liệu, không ảnh hưởng code.
- **N2.** `VnBdsAggregateOutput` và `VnJobAggregateOutput` bổ sung `persistence_status` và `persistence_message` đúng yêu cầu; schema additive, không break backward compatibility.
- **N3.** `canonical_merge_history` thêm `previous_source_ids` / `new_source_ids` qua migration 194; phù hợp AC 13.2c.

## Phân loại tổng hợp

| Loại | Số lượng | Danh sách ID |
|------|----------|--------------|
| must-fix | 3 | M1, M2, M3 |
| should-fix | 4 | S1, S2, S3, S4 |
| watch | 6 | W1-W6 |
| non-issue | 3 | N1-N3 |

## Hành động tiếp theo

1. **Dev agent thực hiện M1 và M2 trước mọi thứ:** thêm Celery worker cho `canonical_persist_outbox` và sửa guard CAS trong `upsert_canonical_entity`.
2. **Sửa M3** bằng cách sinh `source_record_id` duy nhất hoặc reject record thiếu `id`.
3. **Sửa S1/S2** để Celery embedding hoạt động dưới RLS và `phone_key` dùng keyed digest.
4. **Dọn dẹp S3** (ruff) và **S4** (trùng `canonical_title`) trong cùng PR.
5. Sau khi sửa, re-run:
   - `ruff check` trên toàn bộ file 13.2.
   - `pytest tests/unit/canonical tests/integration/canonical tests/integration/routes/test_canonical_routes.py`.
   - `python -m nowing_evals run canonical dedup --domain bds --fixture bds-overlap-30` và tương tự cho jobs.
6. Cập nhật `sprint-status.yaml` và các file story `13-2b`/`13-2e` sau khi pass để tránh drift trạng thái.
