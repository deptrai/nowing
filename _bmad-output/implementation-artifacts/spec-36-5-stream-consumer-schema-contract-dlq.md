---
title: 'Story 36.5: Stream Consumer Schema Contract & DLQ Routing'
type: 'feature'
created: '2026-09-14'
status: 'done'
baseline_commit: '6bb056d3b93e4a5d31b18f08f3e7d525c5e736db'
review_loop_iteration: 1
context:
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-3'
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-4'
  - '../planning-artifacts/XACTIONS-REQUIREMENTS-2026-09-13.md#req-x2'
  - 'epic-36-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Khi XActions REQ-X2 live, mọi crawler sẽ emit thin event vào `stream:social:raw_posts` theo schema `{..., content_snippet, workspace_id, schema_version}`. Consumer `social_stream_worker` hiện tại (a) chỉ đọc field `content` (bỏ sót `content_snippet`), (b) `ValidationError` → `return None` → **message vẫn nằm trong PEL** và bị re-deliver mãi, (c) drop ngầm event thiếu `workspace_id`/`target_id` mà không vào DLQ, (d) không có lag probe nên khi consumer chết, stream cứ tích tới `MAXLEN ~1M` rồi truncate mất data.

**Approach:** Siết contract ở consumer theo AD-3/AD-4: (1) thêm `AliasChoices("content","content_snippet")` và `schema_version` vào `SocialPostEvent`; (2) phân loại lỗi thành schema-violation (thiếu field bắt buộc, `schema_version` quá max) vs runtime-failure, cả hai đều route sang `stream:social:failed` kèm `dlq_reason` rồi `XACK` — message không bao giờ nằm lại trong PEL; (3) wrap `json.dumps` DLQ bằng try/except fallback `repr()`; (4) thêm lag probe `XINFO GROUPS`/`XPENDING` trong consumer loop log warning khi vượt ngưỡng.

## Boundaries & Constraints

**Always:**
- **Alias `content_snippet`:** `SocialPostEvent.content` chấp nhận `validation_alias=AliasChoices("content","content_snippet")`; khi cả hai field có mặt, `content` thắng (Pydantic lấy alias đầu khớp).
- **Schema version gate:** định nghĩa `SUPPORTED_SCHEMA_VERSION_MAX = 1` module-level. Event có `schema_version > SUPPORTED_SCHEMA_VERSION_MAX` → DLQ với `dlq_reason="UNSUPPORTED_SCHEMA_VERSION"`, XACK, không raise.
- **Required fields:** thiếu `workspace_id` **hoặc** thiếu content (cả `content` lẫn `content_snippet` đều rỗng) → DLQ với `dlq_reason` tương ứng (`MISSING_WORKSPACE_ID` / `MISSING_CONTENT`) + log warning + XACK. Event `workspace_id` có thể được forward qua `target_id` lookup (existing logic trong `process_social_post_event`); chỉ DLQ khi cả hai đường đều không resolve được.
- **DLQ write robust:** `xadd(STREAM_SOCIAL_DEAD_LETTER, {...})` bọc `json.dumps(payload)` trong try/except — khi serialize fail, dùng `repr(payload)`. Mọi nhánh DLQ phải `XACK` message gốc (kể cả khi `xadd` DLQ thành công).
- **Lag probe:** trong `run_social_stream_consumer` sau mỗi `xreadgroup` batch, gọi `XINFO GROUPS stream:social:raw_posts` + `XPENDING` (chỉ count, không fetch full). Nếu `pending_count > SOCIAL_STREAM_LAG_WARN_THRESHOLD` (constant, default `1000`) → `logger.warning` với lag/pending/consumer count. Probe bọc try/except — không bao giờ crash consumer vì probe fail.
- **Backward compat:** event cũ không có `schema_version` → coi như `1`, accept. Event dùng field `content` (legacy adapter_v2 emit) vẫn parse được.

**Ask First:**
- Thay đổi giá trị `SUPPORTED_SCHEMA_VERSION_MAX` hoặc `SOCIAL_STREAM_LAG_WARN_THRESHOLD` sau khi approve.
- Đưa lag probe ra Celery beat task riêng (thay vì nhúng trong consumer).

**Never:**
- Không đổi tên `STREAM_SOCIAL_DEAD_LETTER` (đã chốt `stream:social:failed` ở cả 2 phía).
- Không `XPENDING`/`XAUTOCLAIM` để reclaim messages từ consumer khác (out of scope — là story khác).
- Không để message valid-schema nhưng fail DB/parse lặp vô hạn trong PEL — nếu `process_social_post_event` raise, DLQ path hiện có đã handle; spec này chỉ thêm nhánh schema-violation DLQ.
- Không thêm feature flag mới — schema validation là hardening luôn-bật ở consumer.
- Không thay đổi signature `process_social_post_event` return type (`dict | None`) — caller đang dựa vào `None` để skip XACK; schema-violation xử lý ở tầng caller trước khi gọi hàm này.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Happy path — `content_snippet` | `{platform, external_post_id, content_snippet, workspace_id, target_id, schema_version:1}` | Parse OK, `event.content == content_snippet`, upsert `social_post`, XACK | N/A |
| Happy path — legacy `content` | `{platform, external_post_id, content, workspace_id, ...}` (không có `schema_version`) | Parse OK, upsert + XACK như hiện tại | N/A |
| Cả `content` và `content_snippet` | cả 2 field có giá trị | `event.content` lấy từ `content` (alias order) | N/A |
| Missing `workspace_id` + không resolve được từ `target_id` | `{platform, external_post_id, content_snippet}` không có `workspace_id`, `target_id` null/invalid | DLQ với `dlq_reason=MISSING_WORKSPACE_ID`, XACK, không tạo `social_post` | `logger.warning` kèm msg_id |
| Missing content (cả 2 field rỗng/không có) | `{platform, external_post_id, workspace_id, target_id}` không có `content`/`content_snippet` | DLQ với `dlq_reason=MISSING_CONTENT`, XACK | `logger.warning` kèm msg_id |
| `workspace_id` valid + `target_id` missing | `{..., workspace_id: 1}` không có `target_id` | DLQ với `dlq_reason=MISSING_TARGET_ID`, XACK — `social_posts.target_id NOT NULL` không thể insert | `logger.warning` kèm msg_id |
| `schema_version` vượt max | `{..., schema_version: 2}` khi `SUPPORTED_SCHEMA_VERSION_MAX=1` | DLQ với `dlq_reason=UNSUPPORTED_SCHEMA_VERSION`, XACK | `logger.warning` kèm version |
| `schema_version` không parse được int | `{..., schema_version: "abc"}` | DLQ với `dlq_reason=INVALID_SCHEMA_VERSION`, XACK | `logger.warning` |
| `json.dumps(payload)` throw khi DLQ | payload chứa non-serializable (vd bytes, datetime raw) | `xadd` DLQ với `payload=repr(payload)`, vẫn XACK | `logger.exception` |
| `xadd` DLQ fail | Redis down / OOM | `logger.exception`, vẫn cố `XACK` (trong finally của nhánh DLQ) | message KHÔNG nằm lại PEL nếu XACK thành công |
| Pydantic `ValidationError` (field type sai, platform rỗng) | `{platform: "", external_post_id: "x", ...}` | DLQ với `dlq_reason=SCHEMA_VALIDATION_ERROR` + `errors` từ ValidationError, XACK | `logger.warning` |
| Lag probe — pending vượt ngưỡng | `XPENDING` trả `pending_count=2500` > `1000` | `logger.warning` kèm `lag`, `pending`, `consumer_count`; consumer vẫn chạy tiếp | probe fail → `logger.debug`, không crash |
| Lag probe — stream chưa có group | `XINFO GROUPS` throw `NOGROUP` | skip warning, log debug | không crash |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/tasks/social_stream_worker.py` — file duy nhất sửa logic. Cụ thể:
  - `SocialPostEvent` (line ~47-90): thêm `content: str = Field(default="", validation_alias=AliasChoices("content","content_snippet"))` và `schema_version: int = 1` (default `1` cho backward compat).
  - Module constants (line ~36-40): thêm `SUPPORTED_SCHEMA_VERSION_MAX = 1`, `SOCIAL_STREAM_LAG_WARN_THRESHOLD = 1000`, và constants `DLQ_REASON_*` cho các reason string.
  - `run_social_stream_consumer` (line ~530-651): bọc `process_social_post_event` bằng `_validate_event_schema(payload)` trước — hàm này trả `(ok, dlq_reason)`; nếu `not ok` → DLQ + XACK, skip `process_social_post_event`. Trong DLQ write path, bọc `json.dumps(payload)` bằng `_safe_serialize_payload(payload)` trả `str`.
  - Thêm `_check_stream_lag(redis_client)` async helper: `XINFO GROUPS` + `XPENDING` count-only, log warning khi `pending > SOCIAL_STREAM_LAG_WARN_THRESHOLD`. Gọi 1 lần mỗi consumer run (không phải mỗi message).
- `nowing_backend/app/proprietary/platforms/xactions/constants.py` — tái sử dụng `STREAM_SOCIAL_DEAD_LETTER` đã có (hiện tại `social_stream_worker` đang hard-code chuỗi; cân nhắc unify nhưng không bắt buộc).
- `nowing_backend/tests/unit/tasks/test_social_stream_worker.py` — thêm unit tests cho `SocialPostEvent` alias + version gate + DLQ routing + lag probe.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/tasks/social_stream_worker.py` — mở rộng `SocialPostEvent` (alias + `schema_version`), thêm module constants, thêm `_validate_event_schema` + `_safe_serialize_payload` + `_check_stream_lag` helpers, sửa `run_social_stream_consumer` để route schema-violation vào DLQ + XACK.
- [x] `nowing_backend/tests/unit/tasks/test_social_stream_worker.py` — thêm tests cover I/O matrix: alias content_snippet, missing workspace_id, missing content, schema_version > max, schema_version invalid type, ValidationError → DLQ, `json.dumps` fallback `repr()`, lag probe trigger + NOGROUP case.

**Acceptance Criteria:**
- Given event XActions-format `{content_snippet, workspace_id, target_id, schema_version:1}`, when consumer parse, then `event.content` chứa giá trị `content_snippet` và upsert `social_post` thành công.
- Given event thiếu `workspace_id` VÀ `target_id` không resolve được workspace, when consumer nhận, then message vào `stream:social:failed` với `dlq_reason=MISSING_WORKSPACE_ID` và được XACK (không còn trong PEL).
- Given event `schema_version=2` khi `SUPPORTED_SCHEMA_VERSION_MAX=1`, when consumer nhận, then message vào DLQ với `dlq_reason=UNSUPPORTED_SCHEMA_VERSION`, XACK, không raise.
- Given `json.dumps(payload)` throw `TypeError`, when DLQ write path chạy, then `xadd` vẫn thành công với `payload=repr(payload)` và message được XACK.
- Given consumer group có `pending_count > 1000`, when consumer chạy, then `logger.warning` emit với lag metrics; probe exception không làm consumer crash.

## Spec Change Log

## Design Notes

**Tại sao không feature-flag:** Spec gốc Epic 36 ghi 36.5 "Depends on 36.4 + REQ-X2", nhưng phụ thuộc đó là *thứ tự deploy* (consumer phải sẵn sàng trước khi XActions emit), không phải *toggle runtime*. Schema validation + DLQ routing là pure hardening — event format cũ vẫn parse được (alias + default `schema_version=1`), nên không cần flag.

**Tại sao lag probe nhúng trong consumer thay vì Celery beat riêng:** giữ blast radius tối thiểu — một chỗ sửa, một task test. Nếu cần probe độc lập sau, tách ra story riêng.

**Phân biệt 3 nhánh DLQ:**
1. **Schema violation** (thiếu `workspace_id`/`content`, `schema_version` vượt max) → detected trước `process_social_post_event`, reason cụ thể.
2. **`ValidationError` Pydantic** (type sai, `platform` rỗng) → catch ở `_validate_event_schema`, reason `SCHEMA_VALIDATION_ERROR`.
3. **Runtime failure** trong `process_social_post_event` (DB, extractor) → đã có DLQ path, chỉ thêm `_safe_serialize_payload`.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/tasks/test_social_stream_worker.py -v` — expected: all pass.
- `cd nowing_backend && uv run pytest tests/unit/tasks/ tests/unit/platforms/xactions/ -q` — expected: no regression.
- `cd nowing_backend && uv run ruff check app/tasks/social_stream_worker.py tests/unit/tasks/test_social_stream_worker.py` — expected: clean.

## Suggested Review Order

**Schema contract & DLQ entry point**

- Consumer pipeline entry — how schema validation gates processing before DB hit.
  [`social_stream_worker.py:901`](../../nowing_backend/app/tasks/social_stream_worker.py#L901)
- Schema gate — all validation logic + DLQ reason routing before persistence.
  [`social_stream_worker.py:600`](../../nowing_backend/app/tasks/social_stream_worker.py#L600)
- Event model — `content_snippet` alias + `schema_version` field + coalesce validator.
  [`social_stream_worker.py:77`](../../nowing_backend/app/tasks/social_stream_worker.py#L77)

**DLQ routing & serialization**

- Safe payload serialization — `json.dumps` fallback `repr()` + `default=str`.
  [`social_stream_worker.py:752`](../../nowing_backend/app/tasks/social_stream_worker.py#L752)
- DLQ write path — `xadd` to `stream:social:failed` with `maxlen`, then XACK.
  [`social_stream_worker.py:763`](../../nowing_backend/app/tasks/social_stream_worker.py#L763)

**Lag probe**

- Probe implementation — `XINFO GROUPS`/`XPENDING` count, threshold check, dynamic warning.
  [`social_stream_worker.py:809`](../../nowing_backend/app/tasks/social_stream_worker.py#L809)
- Probe throttle — module-scoped `_LAG_STATE` + 30s interval inside consumer loop.
  [`social_stream_worker.py:901`](../../nowing_backend/app/tasks/social_stream_worker.py#L901)

**Persistence & workspace resolution**

- Workspace/target resolution — `target_id` required by DB `NOT NULL`; workspace fallback.
  [`social_stream_worker.py:432`](../../nowing_backend/app/tasks/social_stream_worker.py#L432)
- UPSERT + error propagation — `SQLAlchemyError` re-raise → caller routes `RUNTIME_FAILURE`.
  [`social_stream_worker.py:432`](../../nowing_backend/app/tasks/social_stream_worker.py#L432)

**Tests**

- Validation cases — `_validate_event_schema` matrix covering all DLQ reasons.
  [`test_social_stream_worker.py`](../../nowing_backend/tests/unit/tasks/test_social_stream_worker.py)
- Consumer DLQ + XACK — mock Redis verify `xadd` + `xack` for each failure mode.
  [`test_social_stream_worker.py`](../../nowing_backend/tests/unit/tasks/test_social_stream_worker.py)
- Lag probe tests — warning emission, NOGROUP handling, throttle behavior.
  [`test_social_stream_worker.py`](../../nowing_backend/tests/unit/tasks/test_social_stream_worker.py)

### Review Findings

- [x] [Review][Decision] `process_social_post_event` return type `dict | None` → `ProcessResult` — spec "Never" cấm đổi signature (line 42), impl đã đổi sang `ProcessResult` dataclass. **Resolved 2026-09-14**: reverted code — `process_social_post_event` trả `dict | None` đúng contract; `_validate_event_schema` (trả `ValidationResult` tuple) vẫn là nơi phân loại `dlq_reason` theo spec. Bỏ `ProcessResult` dataclass.
- [x] [Review][Decision] `DLQ_REASON_MISSING_TARGET_ID` không nằm trong spec I/O matrix — **Resolved 2026-09-14**: spec updated — thêm row "workspace_id valid + target_id missing → DLQ `MISSING_TARGET_ID`" vào I/O matrix. `_validate_event_schema` (schema-layer) giữ `MISSING_TARGET_ID`; `process_social_post_event` chỉ trả `dict | None`.
- [x] [Review][Patch] Thiếu unit test assert `call_args.args[1]` payload — **Resolved 2026-09-14**: thêm `test_ingest_raw_post_to_stream_payload_has_no_none_values` verify None-filter, ISO datetime, JSON collection, `schema_version="1"`. [`tests/unit/platforms/test_xactions_adapter_v2.py`]
- [x] [Review][Patch] `adapter_v2.ingest_raw_post_to_stream` không emit `schema_version` — **Resolved 2026-09-14**: thêm `"schema_version": "1"` vào payload. [`app/proprietary/platforms/xactions/adapter_v2.py`]
- [x] [Review][Defer] `_LAG_STATE` module-global throttle không hiệu quả multi-process — mỗi worker process probe độc lập. Trade-off có chủ đích, probe cost nhỏ (30s interval). [`app/tasks/social_stream_worker.py:64`] — deferred, design trade-off
