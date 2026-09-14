---
title: 'Story 36.4: Single-Writer Stream — Stop Nowing Publishing to stream:social:raw_posts'
type: 'feature'
created: '2026-09-14'
status: 'done'
baseline_commit: '9ec360991d3dca09f272693c590f5e2edf76f85e'
review_loop_iteration: 0
context:
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-3'
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-4'
  - 'epic-36-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hiện tại Nowing đang tự thực hiện `XADD` các bài post cào được vào `stream:social:raw_posts` qua `adapter_v2.ingest_raw_post_to_stream`, dẫn đến mô hình dual-writer khi XActions stream hook (REQ-X2) kích hoạt. Điều này gây nguy cơ trùng lặp dữ liệu, lệch schema, và phân mảnh nguồn ghi (vi phạm AD-3, AD-4).

**Approach:** Đưa vào feature flag `XACTIONS_STREAM_SINGLE_WRITER_ENABLED` (mặc định `False`). Khi cờ bật, Nowing ngừng `XADD` vào `stream:social:raw_posts` trong Celery ingest task (XActions trở thành sole writer), chỉ cập nhật tiến độ target (`last_scraped_at`, status lifecycle); khi cờ tắt, tiếp tục duy trì luồng ghi legacy để đảm bảo không mất mát dữ liệu trước khi REQ-X2 sẵn sàng.

## Boundaries & Constraints

**Always:**
- **Feature flag an toàn:** Chuyển đổi phải được bảo vệ bằng feature flag `XACTIONS_STREAM_SINGLE_WRITER_ENABLED` (mặc định `False` trong môi trường sản xuất cho đến khi REQ-X2 live).
- **Không mất trạng thái target:** Khi cờ bật (`True`), Celery task `_ingest_social_target` vẫn phải cập nhật `target.last_scraped_at = datetime.now(UTC)`, phục hồi `status = "active"` nếu trước đó là `"paused"`, và gọi `session.commit()` đầy đủ.
- **Tương thích ngược (Dual-write fallback):** Khi cờ tắt (`False`), toàn bộ logic `adapter.ingest_raw_post_to_stream` hiện có phải chạy bình thường không thay đổi.
- **Consumer không bị ảnh hưởng:** Consumer `social_stream_worker.py` tiếp tục đọc từ `stream:social:raw_posts` như bình thường.

**Ask First:**
- Xóa bỏ vĩnh viễn hàm `ingest_raw_post_to_stream` khỏi `XActionsSocialAdapterV2` trước khi XActions REQ-X2 được xác nhận triển khai trên production.

**Never:**
- Không tự ý bật `XACTIONS_STREAM_SINGLE_WRITER_ENABLED = True` làm giá trị mặc định trong code khi XActions REQ-X2 chưa live.
- Không để việc tắt publish làm gián đoạn việc cập nhật chu kỳ cào (`last_scraped_at`) của `SocialMonitoredTarget`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Flag OFF (mặc định) | `XACTIONS_STREAM_SINGLE_WRITER_ENABLED=False`, fetch 5 posts | Gọi `adapter.ingest_raw_post_to_stream` 5 lần, cập nhật `last_scraped_at`, trả về `ingested=5` | Giữ nguyên xử lý ngoại lệ Redis XADD như cũ (log exception, không crash task) |
| Flag ON (Single-Writer) | `XACTIONS_STREAM_SINGLE_WRITER_ENABLED=True`, fetch 5 posts | Bỏ qua gọi `ingest_raw_post_to_stream`, cập nhật `last_scraped_at`, trả về `ingested=5` (hoặc số posts fetched), log info | Bỏ qua XADD nên không có lỗi Redis stream |
| Flag ON + Paused Target | Target `status="paused"`, fetch thành công | Reset `status="active"`, cập nhật `last_scraped_at`, commit session, không gọi XADD | DB commit bình thường |
| Flag ON + Empty Posts | Adapter trả 0 posts | Không có post để lặp, cập nhật `last_scraped_at`, trả về 0 | Bình thường |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/config/entities.py` -- Khai báo cấu hình `XACTIONS_STREAM_SINGLE_WRITER_ENABLED = os.getenv("XACTIONS_STREAM_SINGLE_WRITER_ENABLED", "false").strip().lower() == "true"` và export trong `__all__`.
- `nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py` -- Trong `_ingest_social_target`: kiểm tra `config.XACTIONS_STREAM_SINGLE_WRITER_ENABLED`. Nếu True, bypass `adapter.ingest_raw_post_to_stream`; nếu False, gọi như cũ.
- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` -- Ghi chú docstring deprecation/migration cho `ingest_raw_post_to_stream` hướng tới mô hình AD-4 Sole Writer.
- `nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py` -- Thêm unit tests bao phủ hành vi cờ bật (bỏ qua XADD, target vẫn cập nhật) và cờ tắt (gọi XADD).

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/config/entities.py` -- Thêm cấu hình `XACTIONS_STREAM_SINGLE_WRITER_ENABLED` (default: False).
- [x] `nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py` -- Kiểm tra `XACTIONS_STREAM_SINGLE_WRITER_ENABLED` để bypass `adapter.ingest_raw_post_to_stream` khi bật.
- [x] `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` -- Cập nhật docstring `ingest_raw_post_to_stream` nêu rõ vai trò legacy dual-write bridge và cờ kiểm soát.
- [x] `nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py` -- Thêm unit tests cho `XACTIONS_STREAM_SINGLE_WRITER_ENABLED` cả 2 nhánh (True và False).

**Acceptance Criteria:**
- Given `XACTIONS_STREAM_SINGLE_WRITER_ENABLED=False`, when `_ingest_social_target` chạy thành công, then `adapter.ingest_raw_post_to_stream` được gọi cho từng post và `stream:social:raw_posts` nhận event (legacy dual-write).
- Given `XACTIONS_STREAM_SINGLE_WRITER_ENABLED=True`, when `_ingest_social_target` chạy thành công, then `adapter.ingest_raw_post_to_stream` KHÔNG được gọi (Nowing không XADD vào stream), nhưng `target.last_scraped_at` vẫn được cập nhật và `target.status` được phục hồi `"active"` nếu trước đó là `"paused"`.
- Given default environment, when config loads, then `XACTIONS_STREAM_SINGLE_WRITER_ENABLED` có giá trị `False`.

### Review Findings

- [ ] [Review][Patch] Missing direct unit test for adapter_v2 single-writer guard [nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py:376-380] — defense-in-depth guard `getattr(config, "XACTIONS_STREAM_SINGLE_WRITER_ENABLED", False)` in `ingest_raw_post_to_stream` is unexercised: all task-level tests mock `adapter.ingest_raw_post_to_stream`, and `tests/unit/platforms/test_xactions_adapter_v2.py` has no direct tests for the method under either flag state.

**Rejected:**

- `test_single_writer_config_default_and_parsing` reloads `entities_mod` but not `app.config` — **false**: test only asserts `entities_mod.XACTIONS_STREAM_SINGLE_WRITER_ENABLED` (module-level), which reload correctly updates; `config.XACTIONS_STREAM_SINGLE_WRITER_ENABLED` staying `False` is expected for that assertion target, and separate task tests monkeypatch `config` directly.
- Inconsistent access (`config.X` vs `getattr(config, "X", False)`) — **low**, rejected: attr always exists via `from app.config.entities import *`; adding `getattr` in task buys nothing.
- Legacy `adapter.py` lacks flag check — **false**: `XActionsSocialAdapter` (v1) has zero callers outside `__init__.py` re-export; no live path bypasses the flag.
- Unrelated `elif` consolidation in `fetch_posts_for_target` — **low**, rejected: semantically equivalent refactor; reverting adds more diff noise than it removes.
- Spec Code Map shows `== "true"` but impl uses tuple — rejected: fix would edit the frozen spec; impl (multi-value parse) is strictly better.
- Truthy tuple missing `"t"` test / `"y"` omitted — **low**, rejected: `"t"` is covered implicitly; `"y"` omission is intentional (avoid ambiguous single-char).
- No runtime `DeprecationWarning` on `ingest_raw_post_to_stream` — rejected: codebase does not use `DeprecationWarning` pattern; docstring + guard suffice.
- Docstring of `_ingest_social_target` still says "push to Redis stream" — **low**, rejected: cosmetic only.
- Flag ON skips `post.target_id`/`post.workspace_id` assignment — **false**: `fetch_posts_for_target` already sets both fields on each `SocialPostData`; the loop assignment was only a refresh, and posts are unused afterward (only `len(posts)` counts).

## Spec Change Log

## Design Notes

Theo AD-4 trong `ARCHITECTURE-SPINE.md`:
"Nowing chỉ consume (consumer group); không publish raw post vào stream này. Nguồn nội bộ khác của nowing ghi stream riêng tên khác hoặc thẳng DB."

Việc ngắt lệnh publish phía Nowing thông qua feature flag cho phép triển khai an toàn theo 2 giai đoạn:
1. Giai đoạn chuẩn bị (Story 36.4): Mã nguồn Nowing sẵn sàng chế độ Single-Writer, deploy lên production với cờ `False`.
2. Giai đoạn kích hoạt: Khi XActions triển khai REQ-X2 (stream publish hook ở `AbstractCrawler`), chỉ cần bật env `XACTIONS_STREAM_SINGLE_WRITER_ENABLED=true` trên worker mà không cần redeploy.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py -k "single_writer" -v` -- expected: pass.
- `cd nowing_backend && uv run pytest tests/unit/platforms/xactions/ tests/unit/tasks/celery_tasks/ -q` -- expected: 134+ passed.
- `cd nowing_backend && uv run ruff check app/config/entities.py app/tasks/celery_tasks/social_xactions_ingest.py app/proprietary/platforms/xactions/adapter_v2.py tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py` -- expected: all checks passed.

## Suggested Review Order

**Feature Flag & Core Gate**

- Cấu hình feature flag kiểm soát chế độ single-writer, hỗ trợ linh hoạt boolean-like env vars.
  [`entities.py:89`](../../nowing_backend/app/config/entities.py#L89)

- Kiểm tra feature flag để bypass publish raw post vào Redis Stream khi cờ bật.
  [`social_xactions_ingest.py:317`](../../nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py#L317)

**Adapter Deprecation & Guard**

- Docstring deprecation và single-writer guard bên trong adapter_v2.
  [`adapter_v2.py:366`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L366)

**Configuration & Documentation**

- Khai báo mẫu biến môi trường XACTIONS_STREAM_SINGLE_WRITER_ENABLED.
  [`.env.example:787`](../../nowing_backend/.env.example#L787)

**Automated Tests**

- Bộ unit tests kiểm tra cả hai trạng thái flag True/False, parsing và target lifecycle.
  [`test_social_xactions_ingest.py:1840`](../../nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py#L1840)
