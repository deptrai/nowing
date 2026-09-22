---
title: 'Bugfix: adapter_v2.ingest_raw_post_to_stream fails silently — post.to_dict() leaks None fields into Redis XADD'
type: 'bugfix'
created: '2026-09-14'
status: 'done'
baseline_commit: '6bb056d3b93e4a5d31b18f08f3e7d525c5e736db'
review_loop_iteration: 0
context:
  - 'nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py'
  - 'nowing_backend/app/proprietary/platforms/xactions/models.py'
  - 'nowing_backend/app/proprietary/platforms/xactions/adapter.py'
  - 'spec-36-4-single-writer-stream-cleanup.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `XActionsSocialAdapterV2.ingest_raw_post_to_stream` (adapter_v2.py) gọi `post.to_dict()` rồi `redis_client.xadd(STREAM_SOCIAL_RAW_POSTS, payload, ...)`. `SocialPostData.to_dict()` dùng `asdict(self)` và KHÔNG filter các field `None`. Redis `xadd` reject `None` values bằng `redis.exceptions.DataError: Invalid input of type: 'NoneType'`. Exception bị `except Exception` nuốt thành `return None` + `logger.exception` → **lỗi bị silent, dual-write không bao giờ ghi được entry nào**.

Verified live on 2026-09-14: tạo SocialPostData với nhiều optional fields = `None` → `xadd` luôn throw `DataError`, `XLEN stream:social:raw_posts` không tăng.

**Impact:** Spec 36.4 nói "dual-write fallback khi flag OFF" nhưng fallback đó thực tế đã chết từ trước (pre-existing bug từ Story 21.8). Khi XActions REQ-X2 chưa live, Nowing không publish raw post nào vào `stream:social:raw_posts` — consumer `social_stream_worker` không có data mới.

**Approach:** Filter `None` values khỏi payload trước khi `xadd` — hoặc bằng cách build payload thủ công giống legacy `adapter.py` (`or ""` cho từng field, `if x is not None` cho optional), hoặc `{k: v for k, v in post.to_dict().items() if v is not None}` + convert datetime/list sang string. Phương án build thủ công an toàn hơn vì nó cũng normalize `media_urls` (list → JSON string) và `reactions_count` (int → string) như Redis stream convention.

## Boundaries & Constraints

**Always:**
- `xadd` PHẢI thành công khi post có các field optional = `None` — không được `DataError`.
- Payload vẫn giữ schema tương thích với consumer `social_stream_worker.py` (đọc `platform`, `external_post_id`, `content`, `author_*`, `target_id`, `workspace_id`, `published_at`, `media_urls`, ...).
- `published_at`, `created_at` (datetime) → ISO string; `media_urls`, `raw_entities` (list/dict) → JSON string; số nguyên → string.
- Không thay đổi signature `ingest_raw_post_to_stream(post, redis_client)` hoặc return contract (`str | None`).

**Never:**
- Không đổi `SocialPostData.to_dict()` nếu nó được dùng ở chỗ khác cần giữ `None` (e.g. serialization nội bộ). Nếu đổi `to_dict()`, phải audit mọi caller.
- Không làm task `_ingest_social_target` crash khi `xadd` fail (giữ nguyên "best-effort" semantics — chỉ sửa để `xadd` thực sự work, không phải để nó raise).

## I/O & Edge-Case Matrix

| Scenario | Input | Expected | Error handling |
|---|---|---|---|
| Post đầy đủ | tất cả fields có giá trị | `xadd` thành công, return msg_id | n/a |
| Post thiếu optional | `author_id=None, published_at=None, ...` | `xadd` thành công (None fields omitted hoặc "" ), return msg_id | n/a |
| `media_urls` là list | `media_urls=["a","b"]` | payload có `media_urls` = JSON string `'["a","b"]'` | n/a |
| `published_at` là datetime | `published_at=datetime(...)` | payload có ISO string | n/a |
| `target_id`/`workspace_id` set | `target_id=5, workspace_id=1` | payload có `"target_id": "5"`, `"workspace_id": "1"` (string, không None) | n/a |
| `xadd` raise lỗi khác | Redis down, network lỗi | return `None`, log exception — KHÔNG raise | caller không crash |

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` — sửa payload construction trong `ingest_raw_post_to_stream` để loại bỏ `None` và serialize datetime/list/dict đúng cách. Cân nhắc reuse logic từ `adapter.py:ingest_raw_post_to_stream` (v1) hoặc viết payload builder dùng chung.
- [x] `nowing_backend/tests/unit/platforms/test_xactions_adapter_v2.py` — thêm test: post có nhiều `None` fields → `xadd` được gọi với payload không có `None` value nào, `xadd` return msg_id. (Test: `test_ingest_raw_post_to_stream_payload_has_no_none_values`)

**Acceptance Criteria:**
- Given `XACTIONS_STREAM_SINGLE_WRITER_ENABLED=False`, khi gọi `await adapter.ingest_raw_post_to_stream(post, redis_client)` với post có `author_id=None`, `published_at=None`, `category=None`, `client_id=None` → `xadd` được gọi, không `DataError`, return msg_id hợp lệ.
- Given post có `media_urls=["a"]`, `raw_entities={"k":1}`, `published_at=datetime.now()` → payload chứa JSON string / ISO string tương ứng, không raw Python object.
- Given Redis down → `xadd` raise, function trả `None`, log exception, không propagate.

## Design Notes

Root cause: `asdict()` trả `dict` giữ nguyên `None`. Redis client chỉ chấp nhận bytes/string/int/float.

Legacy `adapter.py` (v1) đã làm đúng:
```python
payload = {
    "platform": post.platform,
    "external_post_id": post.external_post_id,
    "author_id": post.author_id or "",
    ...
    "media_urls": json.dumps(post.media_urls or []),
    "published_at": post.published_at.isoformat() if post.published_at else "",
}
if post.target_id is not None: payload["target_id"] = str(post.target_id)
```

Cân nhắc: extract shared `_build_stream_payload(post)` helper giữa v1 và v2 để tránh drift trong tương lai — nhưng phải giữ `adapter.py` (v1) không đổi vì nó là stdio adapter riêng.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/platforms/test_xactions_adapter_v2.py -k "ingest_raw_post" -v` — pass.
- `cd nowing_backend && uv run python -c "..."` (manual: tạo post với None fields → gọi ingest → check `XLEN` tăng).
- `cd nowing_backend && uv run ruff check app/proprietary/platforms/xactions/adapter_v2.py` — clean.

