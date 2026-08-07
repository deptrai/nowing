---
story: "13.1 Canonical Persistence, Tenancy & Convention"
reviewed_commit: 72806b18d
parent_commit: c0ff272d2
reviewer: bmad-code-review
review_date: "2026-08-07"
verdict: changes_requested
---

# BMAD Code Review — Story 13.1 "Canonical Persistence, Tenancy & Convention"

## Tóm tắt phán quyết

- **Mức độ:** `CHANGES_REQUESTED` — còn **2 must-fix**, **5 should-fix**, **4 watch**, **4 non-issue**.
- **Rủi ro chính:** Celery backfill embedding bị **RLS chặn hoàn toàn** vì không truyền `workspace_id` và không `set_config` trước lần SELECT; version **compare-and-swap (CAS)** trong `upsert_canonical_entity` không bảo vệ đúng vì điều kiện `WHERE` so sánh với `new_version` thay vì `previous_version` và không raise `ConcurrentUpdateError`; một số hàm outbox/context chưa tenant-aware.
- **Kiểm thử:** `ruff check` pass trên các file thay đổi; 18 test liên quan đều pass. Test được chạy tại working tree hiện tại; riêng đoạn mã tại commit `72806b18d` vẫn chứa các lỗi nêu dưới.

## Thống kê diff

- 20 files thay đổi, +1944 / −7 dòng (xem `13-1-canonical-persistence-tenancy-convention.diff` trong cùng thư mục).
- Phạm vi: `nowing_backend/alembic/versions/193_add_canonical_entities.py`, `nowing_backend/app/db.py`, `nowing_backend/app/canonical/`, `nowing_backend/app/celery_app.py`, `nowing_backend/app/services/{bds,jobs}_aggregator/dedupe.py` + `__init__.py`, `nowing_backend/app/zero_publication.py`, tests.

## Kiểm thử đã chạy

```bash
cd nowing_backend
ruff check app/db.py app/canonical/ app/services/bds_aggregator/dedupe.py app/services/bds_aggregator/__init__.py app/services/jobs_aggregator/dedupe.py app/services/jobs_aggregator/__init__.py app/zero_publication.py app/celery_app.py tests/unit/canonical/test_canonical_conventions.py tests/integration/canonical/test_canonical_persistence.py tests/integration/canonical/test_canonical_embedding.py alembic/versions/193_add_canonical_entities.py
# -> All checks passed

python -m pytest tests/unit/canonical/test_canonical_conventions.py tests/integration/canonical/test_canonical_persistence.py tests/integration/canonical/test_canonical_embedding.py -q
# -> 18 passed
```

## Đánh giá Acceptance Criteria

| AC | Đánh giá | Ghi chú |
|----|----------|---------|
| AC-1 — Migration | **Đạt** | `193_add_canonical_entities.py` tạo 4 bảng, indexes, RLS, `apply_publication`, downgrade. Test `test_migration_upgrade_and_downgrade` xác nhận. |
| AC-2 — Entity columns | **Đạt** | Đầy đủ các cột yêu cầu. Chú ý: migration tạo thêm `updated_at` cho `canonical_entities` nhưng model SQLAlchemy `CanonicalEntity` không khai báo cột này (S3). |
| AC-3 — Fingerprint uniqueness | **Đạt** | Unique constraint `(workspace_id, entity_type, fingerprint)` và upsert trên đúng cặp. Test `test_unique_constraint_on_entity_fingerprint`. |
| AC-4 — Source provenance | **Đạt** | `canonical_entity_sources` có đầy đủ workspace, canonical_entity_id, entity_type, source_name, source_record_id, snapshot, URL, timestamps, fingerprint. |
| AC-5 — Source uniqueness | **Đạt** | Unique constraint `(workspace_id, entity_type, source_name, source_record_id)`; source record có thể chuyển sang entity mới. Test `test_source_uniqueness_constraint`. |
| AC-6 — Conflict flag shape | **Đạt** | `conflict_flags` là JSONB list; test `test_merge_history_conflicts_shape` dùng shape `{type, reason, price_range, price_sources}`. |
| AC-7 — Version CAS | **Cần sửa** | Có `with_for_update()` nhưng guard `UPDATE ... WHERE version == new_version` là sai (phải là `previous_version`), và không raise `ConcurrentUpdateError` (M2). |
| AC-8 — Per-transaction tenant context | **Đạt** | `set_canonical_workspace_id` dùng `SELECT set_config('app.workspace_id', ..., true)` (tương đương `SET LOCAL`). |
| AC-9 — RLS fail-closed | **Đạt** | Tất cả 4 bảng `ENABLE` + `FORCE RLS`, policy theo `current_setting`. Test RLS SELECT pass. Tuy nhiên chưa test INSERT/UPDATE dưới app role. |
| AC-10 — Domain convention boundary | **Hầu hết** | BDS/Jobs `dedupe.py` + `__init__.py` export `fingerprint/merge/search_text`. Còn edge case xử lý input rỗng/thay đổi key (W1). |
| AC-11 — Embedding backfill | **Cần sửa** | `embedding_status='pending'` đúng, enqueue đúng, nhưng Celery task không set workspace context trước SELECT nên bị RLS chặn (M1); chưa re-check version trước commit (S2). |
| AC-12 — Required indexes | **Đạt** | Tất cả indexes theo yêu cầu được tạo và kiểm tra trong `test_migration_upgrade_and_downgrade`. |
| AC-13 — Zero publication | **Đạt** | `zero_publication.py` bổ sung 4 bảng/cột tối thiểu; snapshot/payload dạng JSONB không được publish. |
| AC-14 — BDS/Jobs execution context contract | **Cần sửa** | Tại commit `72806b18d`, `vn_bds.aggregate` (executor + `app/services/bds_aggregator/orchestrator.py::aggregate`) và `vn_jobs.aggregate`/`aggregate_jobs` chưa nhận `workspace_id` một cách explicit (S4). |

## Findings (theo lớp review)

### [must-fix]

#### M1. Celery backfill embedding bị RLS chặn vì thiếu workspace context
- **File/lines:** `nowing_backend/app/canonical/tasks/backfill_canonical_embedding.py:31-49`, `canonical_persist_service.py:45-48`.
- **Mô tả:** `_backfill_canonical_embedding_with_session` thực hiện `SELECT CanonicalEntity` **trước** khi gọi `set_canonical_workspace_id(session, entity.workspace_id)`. Với app role `NOBYPASSRLS` và `FORCE RLS`, policy `workspace_id = current_setting(...)` sẽ trả về `NULL` khi chưa `set_config`, nên worker không thể đọc dòng nào. Hơn nữa task signature `(entity_id, expected_version, embedding_model_name)` không chứa `workspace_id`, nên ngay cả khi muốn set trước SELECT cũng không có giá trị để set.
- **Bằng chứng:** `set_canonical_workspace_id` được gọi ở dòng 49, sau khi `result.scalar_one_or_none()` đã chạy ở dòng 31-34. `_enqueue_embedding_backfill` chỉ truyền `[str(entity.id), entity.version, model_name]` (dòng 46-47).
- **Đề xuất sửa:**
  1. Truyền `workspace_id` thêm vào `args` của `backfill_canonical_embedding.apply_async`.
  2. Đổi signature task thành `(entity_id, workspace_id, expected_version, embedding_model_name)`.
  3. Gọi `set_canonical_workspace_id(session, workspace_id)` **trước** `SELECT CanonicalEntity`.

#### M2. Version compare-and-swap guard không bảo vệ và không raise ConcurrentUpdateError
- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:253-254, 307-327`.
- **Mô tả:** Code đọc `previous_version = existing.version`, tính `new_version = previous_version + 1`, rồi flush thay đổi (trong `record_merge_history` -> `session.flush()`). Sau đó thực hiện `UPDATE ... WHERE CanonicalEntity.id == existing.id AND CanonicalEntity.version == new_version`. Điều kiện `WHERE` dùng `new_version` — một giá trị vừa được gán bởi chính transaction — nên guard này không bao giờ phát hiện xung đột. AC-7 yêu cầu expected-version check raise `ConcurrentUpdateError`, nhưng class/exception này chưa tồn tại trong file ở commit này.
- **Đề xuất sửa:**
  - `WHERE CanonicalEntity.version == previous_version` (giá trị đọc lúc lock) và `values(version=new_version, ...)`.
  - Kiểm tra `result.rowcount == 1`; nếu bằng 0 thì raise `ConcurrentUpdateError`.
  - Thêm `class ConcurrentUpdateError(Exception)` trong module (hoặc tái sử dụng pattern đã có ở các story khác).

### [should-fix]

#### S1. `create_persist_outbox` và `retry_persist_outbox` chưa tenant-aware
- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:88-112, 384-397`.
- **Mô tả:** Hai hàm ghi `canonical_persist_outbox` nhưng không gọi `set_canonical_workspace_id(session, workspace_id)`. Vì bảng này `FORCE RLS`, insert/update dưới app role sẽ bị từ chối hoặc không nhìn thấy dòng. Test `test_persist_outbox` pass vì `db_session` fixture kết nối bằng owner.
- **Đề xuất sửa:** Gọi `set_canonical_workspace_id(session, workspace_id)` ngay đầu mỗi hàm; `retry_persist_outbox` cần đọc `workspace_id` từ dòng outbox (hoặc nhận thêm tham số).

#### S2. Embedding backfill dễ ghi đè vector đã stale do concurrent merge
- **File/lines:** `nowing_backend/app/canonical/tasks/backfill_canonical_embedding.py:39-82`.
- **Mô tả:** Task kiểm tra `entity.version == expected_version` ở đầu, sau đó gọi `asyncio.to_thread(embed_texts, ...)` — một bước chậm. Trong khoảng thời gian đó, một `upsert_canonical_entity` khác có thể thay đổi `search_text` và bump version. Khi task commit, nó ghi đè `embedding` lên dòng đã có `version` mới, dẫn đến vector không khớp nội dung `search_text`. AC-11 yêu cầu backfill chỉ chạy "if the version still matches" — hiện chỉ check ở đầu.
- **Đề xuất sửa:** Thực hiện `UPDATE ... WHERE id = ... AND version = expected_version` ở cuối task và kiểm tra `rowcount`; nếu version đã thay đổi thì bỏ qua (log + return) hoặc để `embedding_status` vẫn `pending`.

#### S3. Model `CanonicalEntity` thiếu `updated_at` so với migration
- **File/lines:** `nowing_backend/alembic/versions/193_add_canonical_entities.py:53-54` vs. `nowing_backend/app/db.py:3721-3798`.
- **Mô tả:** Migration tạo `updated_at` cho `canonical_entities`, nhưng class `CanonicalEntity` (kế thừa `TimestampMixin` chỉ có `created_at`) không khai báo `updated_at`. Điều này gây sai lệch giữa SQLAlchemy metadata và schema, ảnh hưởng `Base.metadata.create_all` khi `DB_BOOTSTRAP_ON_STARTUP=TRUE` và có thể làm `alembic check` báo lỗi.
- **Đề xuất sửa:** Bổ sung `updated_at` vào `CanonicalEntity` hoặc loại bỏ cột khỏi migration nếu không cần, sao cho hai bên đồng nhất.

#### S4. BDS/Jobs execution context contract chưa explicit `workspace_id`
- **File/lines:** `nowing_backend/app/services/bds_aggregator/orchestrator.py:180-183`, `nowing_backend/app/capabilities/vn_bds/aggregate/executor.py:25-44`, `nowing_backend/app/services/jobs_aggregator/orchestrator.py:84`.
- **Mô tả:** AC-14 yêu cầu `vn_bds.aggregate` và `vn_jobs.aggregate` được document để nhận `workspace_id` một cách explicit. Tại `72806b18d`, `bds_aggregator.orchestrator.aggregate` chỉ nhận `payload` và `source_executors`; executor `vn_bds.aggregate` gọi `aggregate_fn(payload)` mà không truyền workspace. `jobs_aggregator.orchestrator.aggregate_jobs` nhận `ctx: Any` nhưng schema input không có `workspace_id` và hàm chưa sử dụng `ctx.workspace_id`.
- **Đề xuất sửa:** Thêm `workspace_id: int` (hoặc `ctx.workspace_id`) vào signature `aggregate`/`aggregate_jobs`; cập nhật capability executor để truyền xuống.

#### S5. `retry_persist_outbox` chưa hoàn chỉnh cho retry thực sự
- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:384-397`.
- **Mô tả:** Hàm chỉ đặt `status='processing'` và tăng `retry_count`, không cập nhật `next_attempt_at`, không ghi `error`, và không dispatch lại payload. Đối với một outbox pattern, thiếu logic retry dispatcher và quản lý `next_attempt_at` sẽ khiến bảng chỉ là staging chứ không tự phục hồi.
- **Đề xuất sửa:** Bổ sung `next_attempt_at` (ví dụ `_now() + backoff`) và wire với một Celery retry task hoặc ghi chú rõ ràng là placeholder.

### [watch]

#### W1. Domain convention edge cases trong BDS/Jobs `dedupe.py`
- **File/lines:** `nowing_backend/app/services/bds_aggregator/dedupe.py:231-259`, `nowing_backend/app/services/jobs_aggregator/dedupe.py:13-21, 142-153`.
- **Mô tả:**
  - BDS `fingerprint` fallback trả về cùng một hash (`sha256({"title":"","address":""})[:32]`) cho mọi record thiếu title và address, gây collision fingerprint.
  - Jobs `merge` gọi `deduplicate([canonical, new_listing])` và mutate `canonical` trực tiếp; nếu canonical keys khác nhau thì trả về `canonical` cũ mà không merge `new_listing`, dễ gây mất dữ liệu.
  - Jobs `_canonical_key` gọi `listing.company.lower().strip()` mà không kiểm tra `None`.
- **Đề xuất sửa:** Xử lý null/empty trong fingerprint; đảm bảo `merge` trả về object mới hoặc rõ ràng về mutation; thêm guard `company or ""`.

#### W2. Vector cũ không bị vô hiệu hóa khi thay đổi embedding model
- **File/lines:** `nowing_backend/app/db.py:3776`, `nowing_backend/app/canonical/tasks/backfill_canonical_embedding.py:42-47`.
- **Mô tả:** `embedding` dùng `Vector(config.embedding_model_instance.dimension)`; `embedding_model_name` lưu tên. Nếu `EMBEDDING_MODEL` thay đổi, các vector cũ có thể khác dimension và vẫn được xem là `ready`, gây lỗi tìm kiếm vector.
- **Đề xuất sửa:** Khi model thay đổi, đặt lại `embedding_status='pending'` cho các dòng có `embedding_model_name != current_model` (có thể làm ở migration/service sau).

#### W3. `source_count` có thể inconsistent khi source record di chuyển concurrent
- **File/lines:** `nowing_backend/app/canonical/services/canonical_persist_service.py:185-247, 281-290`.
- **Mô tả:** `_upsert_source` dùng `ON CONFLICT` để di chuyển source record giữa các entity, sau đó `_update_source_count` tính lại count. Tuy nhiên `with_for_update` chỉ khóa `canonical_entities`, không khóa `canonical_entity_sources`; trong tình huống concurrent, count có thể tính trên snapshot cũ trước khi source row được di chuyển.
- **Đề xuất sửa:** Cân nhắc `SELECT ... FOR UPDATE` trên source row trước khi tính count, hoặc dùng trigger/sum thay vì cache count.

#### W4. Test coverage chưa đủ các nhánh quan trọng
- **File/lines:** `tests/integration/canonical/test_canonical_persistence.py`, `tests/integration/canonical/test_canonical_embedding.py`.
- **Mô tả:** Thiếu test cho: (a) `ConcurrentUpdateError` khi version mismatch, (b) `create_persist_outbox`/`retry_persist_outbox` dưới app role RLS, (c) embedding backfill trong Celery worker role (non-owner), (d) fingerprint rỗng/empty `search_text`, (e) source record di chuyển concurrent.
- **Đề xuất sửa:** Bổ sung ít nhất test cho M1 và M2 khi sửa code.

### [non-issue]

- **N1.** `pyproject.toml` chỉ thêm marker `canonical` cho pytest — không ảnh hưởng runtime.
- **N2.** `TimestampMixin` chỉ có `created_at`; `CanonicalMergeHistory` và `CanonicalEntitySource` không có `updated_at`, phù hợp migration.
- **N3.** `EmbeddingStatus` và `PersistOutboxStatus` enum trong `db.py` khớp với migration `CHECK` constraints.
- **N4.** RLS policy dùng `NULLIF(current_setting(...), '')::integer`; nếu ứng dụng luôn set qua `set_canonical_workspace_id` thì không có injection; app role `NOBYPASSRLS` là đủ.

## Phân loại tổng hợp

| Loại | Số lượng | Danh sách ID |
|------|----------|--------------|
| must-fix | 2 | M1, M2 |
| should-fix | 5 | S1-S5 |
| watch | 4 | W1-W4 |
| non-issue | 4 | N1-N4 |

## Hành động tiếp theo

1. Dev agent thực hiện **M1** (truyền `workspace_id` qua Celery task và set RLS context trước SELECT) và **M2** (sửa guard CAS và thêm `ConcurrentUpdateError`) trước khi merge.
2. Sau M1/M2, bổ sung test cho backfill dưới non-owner role và concurrency CAS (W4).
3. Xử lý **S1** (tenant context cho outbox) và **S2** (version re-check trước commit embedding) trong cùng PR.
4. Re-run `ruff` + 3 file test; sau khi pass, có thể chạy lại `bmad-code-review`.
5. Cân nhắc **S3** (model/migration drift `updated_at`) và **S4** (workspace_id explicit cho aggregator) trong follow-up để tránh nợ kỹ thuật khi Epic 13.2/13.3 bắt đầu gọi `aggregate`.
