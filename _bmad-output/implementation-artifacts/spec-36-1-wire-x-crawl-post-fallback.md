---
title: 'Story 36.1: Wire x_crawl_post Fallback & Graceful Unsupported Marking'
type: 'feature'
created: '2026-09-13'
status: 'completed'
baseline_commit: '281072dd995a264bcab6bfff116915269b991b6a'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Các monitored target thuộc VN-domain (Chợ Tốt, Shopee, TopCV, BĐS,...) gọi tool `x_scrape` trên XActions nhưng tool này chưa tồn tại trong daemon, gây lỗi `XACT_404` (`tool_not_found`). Hàm `fallback_crawl_post` đã được định nghĩa nhưng chưa từng được gọi trong production code, thiếu tham số `platform` bắt buộc (gây `XACT_4001`), và quăng `ValueError` nếu target không có HTTP URL thay vì đánh dấu `unsupported`.

**Approach:** Khi `fetch_posts_for_target` bắt gặp lỗi `XACT_404`/`tool_not_found`, tự động kích hoạt fallback sang `x_crawl_post` với đủ tham số `{platform, url}`. Nếu target không có URL hợp lệ hoặc platform không hỗ trợ fallback, đánh dấu target thành `status='unsupported'`, `is_active=False` trong cơ sở dữ liệu để scheduler không lặp lại vô hạn.

## Boundaries & Constraints

**Always:**
- Bắt buộc truyền cả `platform` (chuẩn hóa từ `target.platform`) và `url` vào tham số của `x_crawl_post`.
- Khi target không có URL hợp lệ hoặc fallback thất bại với lỗi vĩnh viễn (`XACT_404`/`XACT_4001`), phải chuyển `status='unsupported'`, `is_active=False` và commit vào DB, dừng task mà không retry Celery.
- Các lỗi tạm thời (rate limit `XACT_4291`, signer `XACT_5000`, network) trong lúc fallback vẫn phải tuân thủ luồng retry/pause hiện tại.

**Ask First:**
- Thay đổi cấu trúc bảng `social_monitored_targets` hoặc thêm cột mới.

**Never:**
- Không nuốt lỗi silently mà không ghi log cảnh báo rõ ràng kèm `target.id` và `target.platform`.
- Không gọi `fallback_crawl_post` nếu lệnh ban đầu thành công hoặc gặp lỗi không phải `XACT_404`/`tool_not_found`.
- Không để xảy ra retry lặp vô hạn trên các target không có URL HTTP(S).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fallback thành công | Target có URL `https://...`, `x_scrape` trả `XACT_404` | Gọi `x_crawl_post` với `{"platform": "...", "url": "..."}`, parse và trả danh sách post | Bắt `XActionsMcpError(code="XACT_404")`, kích hoạt fallback |
| Target không có HTTP URL | Target chỉ có keyword/slug (vd `target_id="laptop"`, `target_url=None`), `x_scrape` trả `XACT_404` | Không raise `ValueError`; raise `TargetUnsupportedError`; Celery task set `status='unsupported'`, `is_active=False`, commit DB và return 0 | Không retry Celery |
| Fallback `x_crawl_post` cũng bị `XACT_404` hoặc `XACT_4001` | Daemon không hỗ trợ URL/platform cho `x_crawl_post` | Raise `TargetUnsupportedError`; task set `status='unsupported'`, `is_active=False` | Dừng retry, log warning |
| Fallback gặp rate limit `XACT_4291` | `x_crawl_post` trả 429 | Re-raise `XActionsMcpError` để Celery task kích hoạt `task.retry(countdown=...)` | Retry theo `retry_after` |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` -- Cập nhật `UniversalScrapeTargetMapper.fallback_crawl_post` bổ sung `platform`, định nghĩa `TargetUnsupportedError`, và cập nhật `XActionsSocialAdapterV2.fetch_posts_for_target` bắt `XACT_404` để gọi fallback.
- `nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py` -- Bổ sung handler cho `TargetUnsupportedError` trong `_ingest_social_target`, gọi hàm phụ trợ đánh dấu `status='unsupported'`, `is_active=False`, commit và dừng task.
- `nowing_backend/tests/unit/platforms/test_xactions_adapter_v2.py` -- Cập nhật và bổ sung unit tests cho luồng fallback, tham số `platform`, xử lý non-URL và `TargetUnsupportedError`.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` -- Thêm `TargetUnsupportedError`, sửa `fallback_crawl_post` bổ sung `platform` và kiểm tra HTTP URL an toàn, thêm logic try fallback trong `fetch_posts_for_target` khi gặp `XACT_404` -- Ngăn chặn crash và unblock target VN qua `x_crawl_post`.
- [x] `nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py` -- Bắt `TargetUnsupportedError` trong `_ingest_social_target`, cập nhật `target.status = 'unsupported'`, `target.is_active = False`, commit DB -- Ngăn chặn scheduler Celery beat lặp lại tác vụ không được hỗ trợ.
- [x] `nowing_backend/tests/unit/platforms/test_xactions_adapter_v2.py` -- Viết unit test cho `fallback_crawl_post` (truyền platform, kiểm tra non-URL), mock tool call trả `XACT_404` kích hoạt fallback thành công và thất bại -- Bảo đảm độ bao phủ và ngăn chặn regression.

**Acceptance Criteria:**
- Given a `SocialMonitoredTarget` with a valid HTTP URL whose primary tool call returns `XACT_404 (tool_not_found)`, when `fetch_posts_for_target` runs, then it retries with `x_crawl_post` including both `platform` and `url`.
- Given a `SocialMonitoredTarget` without an HTTP URL whose primary tool call returns `XACT_404`, when `fetch_posts_for_target` runs, then it raises `TargetUnsupportedError` without crashing with unhandled `ValueError`.
- Given a task catches `TargetUnsupportedError`, when handling the error, then `target.status` is set to `'unsupported'`, `target.is_active` is set to `False`, and no further Celery retries are scheduled.

## Design Notes

`TargetUnsupportedError` kế thừa `RuntimeError` để phân biệt với các lỗi tạm thời của transport MCP.
Trong `fallback_crawl_post(target)`:
```python
platform = _normalize_platform_for_post(getattr(target, "platform", ""))
target_url = getattr(target, "target_url", None) or getattr(target, "target_id", "")
if not target_url or not target_url.startswith(("http://", "https://")):
    raise TargetUnsupportedError(f"Target {getattr(target, 'id', None)} lacks valid HTTP(S) URL for x_crawl_post fallback")
return "x_crawl_post", {"platform": platform, "url": target_url}
```

## Verification

**Commands:**
- `pytest nowing_backend/tests/unit/platforms/test_xactions_adapter_v2.py` -- expected: 100% passed

## Suggested Review Order

**Fallback Dispatch & Protocol Adaptation**

- Tool not found and permanent error detection logic
  [`adapter_v2.py:112`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L112)

- Fallback crawl post target URL validation and platform injection
  [`adapter_v2.py:152`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L152)

- Primary tool failure interception, fallback execution, and dryRun handling
  [`adapter_v2.py:191`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L191)

**Celery Ingestion & Lifecycle Management**

- Target permanently unsupported state persistence without retry
  [`social_xactions_ingest.py:116`](../../nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py#L116)

- Ingest task TargetUnsupportedError interception and execution halting
  [`social_xactions_ingest.py:193`](../../nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py#L193)

**Test Verification**

- Unit tests for adapter fallback paths, permanent errors, and dict payloads
  [`test_xactions_adapter_v2.py:1`](../../nowing_backend/tests/unit/platforms/test_xactions_adapter_v2.py#L1)

- Ingestion task unsupported state handling and skipping tests
  [`test_social_xactions_ingest.py:1`](../../nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py#L1)
