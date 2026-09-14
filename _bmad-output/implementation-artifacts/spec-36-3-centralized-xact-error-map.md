---
title: 'Story 36.3: Centralized XACT_* → Task-Behavior Error Map'
type: 'feature'
created: '2026-09-14'
status: 'done'
baseline_commit: 'a523ca7777eaf71e58e3cf9c27892c0e23f86579'
review_loop_iteration: 1
context:
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-10'
  - 'epic-36-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `social_xactions_ingest.py:196-218` xử lý lỗi `XACT_*` bằng chuỗi `if/elif` hardcoded trực tiếp trong Celery task — adapter giao thức bị lẫn với quyết định retry/pause/halt, mỗi caller muốn xử lý khác đi phải sao chép lại toàn bộ chain, và `XACT_5000`/`XACT_4001` chưa đi qua một bản đồ thống nhất (vi phạm AD-10).

**Approach:** Định nghĩa một module bản đồ lỗi tập trung: enum `TaskBehavior` (RETRY, PAUSE, HALT, RAISE) + `XACT_ERROR_BEHAVIOR` map từ `code` → behavior kèm metadata (countdown, max_retries, cooldown). Adapter/task resolve `XActionsMcpError.code` qua map → trả `TaskBehavior` + metadata, Celery layer thực thi hành vi đó; non-Celery callers (API/CLI/health probe) đọc cùng map mà không phụ thuộc `task.retry`.

## Boundaries & Constraints

**Always:**
- **Một nguồn chân lý:** Mọi quyết định retry/pause/halt cho `XActionsMcpError.code` phải đi qua `XACT_ERROR_BEHAVIOR` map — không rẽ nhánh `exc.code == "..."` rời rạc trong task/adapter.
- **Bản đồ canonical (epics.md 4838):**
  - `XACT_4291` → `RETRY` với `countdown=clamp(retry_after, 5..3600)`, `max_retries=5`.
  - `ACCOUNT_HIBERNATION` / `PROXY_EXHAUSTED` / `XACT_5030` → `PAUSE` target (đẩy `last_scraped_at` ra tương lai `retry_after` hoặc cooldown mặc định).
  - `XACT_4010` → `HALT` target (`status='error'`, `is_active=False`).
  - `XACT_5000` → `RETRY` `countdown=60` `max_retries=3`; khi cạn retry → ghi `stream:social:failed` (DLQ) rồi `HALT`.
  - `XACT_4001` → `PAUSE` + log `exc.suggested_action`.
- **Adapter trả enum, không gọi Celery:** Lớp resolve trả `TaskBehavior` + metadata (countdown, reason); KHÔNG bao giờ gọi `task.retry` bên trong — Celery task là nơi duy nhất thực thi.
- **Fallback an toàn:** `code` không có trong map hoặc `code=None` → default `PAUSE` (hoặc `RAISE`), KHÔNG `KeyError`.
- **Clamp countdown:** `clamp(retry_after, 5, 3600)` — None/0 dùng default; không để countdown âm/0.
- **Giữ nguyên helper hiện có:** Tái dùng `_pause_target`, `_halt_target`, `_mark_target_unsupported`; DLQ ghi theo schema `{original_id, payload, error, failed_at}` như `social_stream_worker.py:623`.
- **Persist trước khi raise retry:** Mọi mutation `target` (status/last_scraped_at/is_active) phải `session.commit()` trước khi re-raise Celery retry, tránh rollback mất trạng thái.

**Ask First:**
- Thêm `TaskBehavior` mới (ngoài RETRY/PAUSE/HALT/RAISE) hoặc thay đổi ngữ nghĩa status của `SocialMonitoredTarget` (vd thêm status mới ngoài `paused`/`error`/`unsupported`/`active`).

**Never:**
- Không gọi `task.retry` / import Celery bên trong module map hoặc adapter_v2 — map phải thuần logic, test được không cần Celery worker.
- Không để `code` lạ/`None` raise `KeyError` hoặc crash task.
- Không nuốt `XACT_5000` cạn retry thành `PAUSE` im lặng — bắt buộc ghi DLQ `stream:social:failed` + halt (không crash-loop mỗi interval).
- Không thay đổi hành vi `TargetUnsupportedError` (Story 36.1) — nó xử lý riêng trước map.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rate limit | `XActionsMcpError(code="XACT_4291", retry_after=45)` | `RETRY`, `countdown=45` → `task.retry(countdown=45)` | countdown clamp trong 5..3600 |
| Rate limit không có retry_after | `code="XACT_4291", retry_after=None` | `RETRY`, countdown default (≥5) | Dùng default clamped |
| Rate limit quá lớn | `code="XACT_4291", retry_after=99999` | `RETRY`, `countdown=3600` | Clamp trần 3600 |
| Hibernation/Proxy | `code="ACCOUNT_HIBERNATION"/"PROXY_EXHAUSTED"/"XACT_5030"` | `PAUSE`, `last_scraped_at` + `retry_after`/cooldown | `_pause_target`, commit, return 0 |
| Auth fatal | `code="XACT_4010"` | `HALT` → `status='error'`, `is_active=False` | `_halt_target`, commit, return 0 |
| Signer crash còn retry | `code="XACT_5000"`, `task.request.retries < 3` | `RETRY` `countdown=60` `max_retries=3` | `task.retry(countdown=60, max_retries=3)` |
| Signer crash cạn retry | `code="XACT_5000"`, `retries >= max_retries` | Ghi `stream:social:failed` + `HALT` | XADD DLQ, `_halt_target`, không crash-loop |
| Bad request | `code="XACT_4001", suggested_action="..."` | `PAUSE` + log `suggested_action` | `_pause_target`, log reason |
| Code lạ | `code="XACT_9999"` hoặc `code=None` | Default `PAUSE`/`RAISE`, không `KeyError` | Log warning kèm code |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/proprietary/platforms/xactions/error_map.py` — **FILE MỚI**: enum `TaskBehavior` (StrEnum: RETRY/PAUSE/HALT/RAISE), `BehaviorDecision` (frozen dataclass: `behavior`, `countdown`, `max_retries`, `cooldown_seconds`, `reason`, `suggested_action`, `exhausted_behavior`), `XACT_ERROR_BEHAVIOR` map, `clamp_countdown()`, `clamp_cooldown()`, `resolve_task_behavior(exc) -> BehaviorDecision`. Thuần logic — KHÔNG import Celery, KHÔNG gọi `task.retry`. Mọi branching trên `exc.code` phải nằm TRONG map này.
- `nowing_backend/app/proprietary/platforms/xactions/mcp_client.py` — `XActionsMcpError` (line 51) có sẵn `code`, `retry_after`, `suggested_action`; `__all__` (line 478). Không sửa.
- `nowing_backend/app/proprietary/platforms/xactions/constants.py` — `STREAM_SOCIAL_DEAD_LETTER="stream:social:failed"` (line 4) đã có sẵn — dùng hằng này, KHÔNG hardcode chuỗi.
- `nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py` — Thay khối `if/elif exc.code` (line 196-218) bằng `decision = resolve_task_behavior(exc)` + dispatch **CHỈ** trên `decision.behavior` / `decision.*` fields — task layer KHÔNG được so sánh `exc.code` string trực tiếp. Giữ `_pause_target` (88), `_halt_target` (104), `_mark_target_unsupported` (117).
- `nowing_backend/app/tasks/social_stream_worker.py` — schema DLQ `{original_id, payload, error, failed_at}` (623-636) làm mẫu; mở rộng payload thêm `code`, `suggested_action`, `retries`.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/xactions_gateway.py` — caller non-Celery (206-217): chứng minh decouple. Out of scope cho refactor — chỉ cần `error_map` dùng được không-Celery.
- `nowing_backend/tests/unit/platforms/xactions/test_error_map.py` — **FILE MỚI**: unit test thuần cho map (mọi code, clamp bounds, code=None/int/lạ → default, metadata `suggested_action`, không-import-Celery).
- `nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py` — Cập nhật test hiện có (4291/hibernation/4010/5000 line 523-676) + thêm test `XACT_5000` cạn retry → DLQ+halt, `XACT_4291` cạn retry → behavior `exhausted_behavior`, `XACT_4001` pause+log `suggested_action` (assert caplog), `code lạ/None` → default + assert `last_scraped_at` vào future, `xadd` DLQ raise → vẫn halt.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/proprietary/platforms/xactions/error_map.py` — Tạo `TaskBehavior`, `BehaviorDecision`, `XACT_ERROR_BEHAVIOR`, `clamp_countdown()`, `clamp_cooldown()`, `resolve_task_behavior()` — single source of truth cho XACT_* → behavior; mọi rẽ nhánh `code` nằm đây.
- [x] `nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py` — Refactor `except XActionsMcpError` dùng `resolve_task_behavior` + dispatch **chỉ** trên `decision.*` (không so `exc.code` trực tiếp); DLQ+halt khi `decision.behavior==RETRY` và `retries>=max_retries` với `decision.exhausted_behavior==HALT`; commit trước retry; trailing `else: raise` cho behavior lạ.
- [x] `nowing_backend/tests/unit/platforms/xactions/test_error_map.py` — Unit test map độc lập Celery: mọi code, clamp bounds (countdown & cooldown), `code=None`/int/lạ → default, metadata `suggested_action` giữ cả `message`, test không-import-Celery (assert `__module__`).
- [x] `nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py` — Cập nhật + thêm: 4291 retry-clamp + cạn retry→halt, 5030/hibernation/proxy pause + assert `last_scraped_at` future, 4010 halt, 5000 retry→DLQ+halt, `xadd` fail → vẫn halt, 4001 pause + assert caplog `suggested_action`, unknown/None → default + `last_scraped_at` future.

**Acceptance Criteria:**
- Given `fetch_posts_for_target` raise `XActionsMcpError` với `code`, when `_ingest_social_target` xử lý, then hành vi được dispatch qua `XACT_ERROR_BEHAVIOR` map duy nhất (4291→retry clamp, 5030/hibernation/proxy→pause, 4010→halt, 5000→retry-3→DLQ+halt, 4001→pause+log) — task layer không chứa `exc.code == "..."` nào.
- And lớp resolve trả `TaskBehavior` enum + metadata, không gọi `task.retry` bên trong — caller non-Celery dùng được mà không import Celery.
- And `code` không map, `None`, hoặc non-string → default `PAUSE` thay vì `KeyError`/`AttributeError`.
- And `code` có `max_retries` cạn retry → hành vi `exhausted_behavior` (5000→DLQ+halt; 4291→halt) thay vì `MaxRetriesExceededError` crash-loop mỗi interval.
- And mọi PAUSE đều đặt `last_scraped_at` vào future (cooldown clamped), kể cả khi `retry_after=None` — paused target không bị scheduler re-queue ngay tick sau.

## Spec Change Log

- **Loop 1 (2026-09-14) — bad_spec:** Review phát hiện (a) task layer vẫn rẽ `exc.code` string (`XACT_5000`/`XACT_4001`/`not in(...)`) vi phạm AD-10 single-source; (b) `XACT_4291` cạn `max_retries=5` → `MaxRetriesExceededError` crash-loop; (c) `cooldown_seconds` không clamp → pause ~0s hoặc vô hạn; (d) `exc.code` non-string/`.strip()` crash + `clamp_countdown` không coerce str/NaN/inf; (e) `_pause_target` bỏ qua `last_scraped_at` khi cooldown falsy → paused target due ngay. **Amended:** `BehaviorDecision` thêm `suggested_action` + `exhausted_behavior`; thêm `clamp_cooldown()`; `resolve_task_behavior` coerce `str(exc.code).strip().upper()` + safe-numeric; task dispatch chỉ trên `decision.*` + trailing `else: raise`; `_pause_target` luôn đặt `last_scraped_at` future khi PAUSE (dùng cooldown đã resolve, default khi None). **Avoids:** leaky-abstraction, crash-loop khi cạn retry, spin-loop paused target, crash trên code non-string. **KEEP:** `error_map.py` module tách riêng; `BehaviorDecision` frozen dataclass; `TaskBehavior` StrEnum; `session.commit()` trước `task.retry`; DLQ schema `{original_id,payload,error,failed_at}`; tên `resolve_task_behavior`/`clamp_countdown`; `XACT_ERROR_BEHAVIOR` dict-of-lambda; không import Celery trong error_map.

## Design Notes

`resolve_task_behavior` là hàm thuần: nhận `XActionsMcpError`, trả `BehaviorDecision` — tách protocol-error (adapter) khỏi execution (Celery). Mọi so sánh `code` nằm TRONG map; task layer chỉ đọc `decision.*`. Sketch:

```python
class TaskBehavior(StrEnum):
    RETRY = "retry"; PAUSE = "pause"; HALT = "halt"; RAISE = "raise"

@dataclass(frozen=True)
class BehaviorDecision:
    behavior: TaskBehavior
    countdown: int | None = None
    max_retries: int | None = None
    cooldown_seconds: int | None = None
    reason: str = ""
    suggested_action: str | None = None      # surface exc.suggested_action (e.g. XACT_4001)
    exhausted_behavior: TaskBehavior | None = None  # hành vi khi cạn max_retries (HALT)
    write_dlq: bool = False                     # True → XADD stream:social:failed khi cạn retry (XACT_5000)

def clamp_countdown(v, default=30, lo=5, hi=3600) -> int: ...   # coerce safe, finite, clamp
def clamp_cooldown(v, default=600, lo=60, hi=86400) -> int: ... # coerce safe, finite, clamp

XACT_ERROR_BEHAVIOR = {
    "XACT_4291": lambda e: BehaviorDecision(RETRY, countdown=clamp_countdown(e.retry_after), max_retries=5, exhausted_behavior=HALT, reason=e.message),
    "ACCOUNT_HIBERNATION": lambda e: BehaviorDecision(PAUSE, cooldown_seconds=clamp_cooldown(e.retry_after), reason=e.message),
    "PROXY_EXHAUSTED": lambda e: BehaviorDecision(PAUSE, cooldown_seconds=clamp_cooldown(e.retry_after), reason=e.message),
    "XACT_5030": lambda e: BehaviorDecision(PAUSE, cooldown_seconds=clamp_cooldown(e.retry_after), reason=e.message),
    "XACT_4010": lambda e: BehaviorDecision(HALT, reason=e.message),
    "XACT_5000": lambda e: BehaviorDecision(RETRY, countdown=60, max_retries=3, exhausted_behavior=HALT, write_dlq=True, reason=e.message),
    "XACT_4001": lambda e: BehaviorDecision(PAUSE, cooldown_seconds=clamp_cooldown(e.retry_after), suggested_action=e.suggested_action, reason=f"{e.message} (suggested: {e.suggested_action})" if e.suggested_action else e.message),
}

def resolve_task_behavior(exc, default=TaskBehavior.PAUSE) -> BehaviorDecision:
    code = str(exc.code).strip().upper() if exc.code is not None else ""
    h = XACT_ERROR_BEHAVIOR.get(code)
    return h(exc) if h else BehaviorDecision(default, cooldown_seconds=clamp_cooldown(None), reason=f"unmapped code {exc.code}: {exc.message}")
```

**Numeric coercion:** `clamp_countdown`/`clamp_cooldown` bọc `(TypeError, ValueError, OverflowError)` + `math.isfinite` — `retry_after` str/NaN/inf/None → default. `exc.code` non-string → `str(...).strip().upper()` trước `.get`.

**Task dispatch (chỉ `decision.*`, KHÔNG `exc.code`):**
```python
decision = resolve_task_behavior(exc)
if decision.behavior is TaskBehavior.RETRY:
    retries = int(getattr(getattr(task,"request",None),"retries",0) or 0)
    if decision.max_retries is not None and retries >= decision.max_retries:
        if decision.exhausted_behavior is TaskBehavior.HALT:
            if decision.write_dlq:  # DLQ flag thuộc decision — không so exc.code
                await _write_dlq(...)  # {original_id,payload,error,code,suggested_action,retries,failed_at}
            await _halt_target(session, target, decision.reason); return 0
    await session.commit()  # persist mutations trước retry
    raise task.retry(countdown=decision.countdown, max_retries=decision.max_retries) from exc
if decision.behavior is TaskBehavior.PAUSE:
    await _pause_target(session, target, decision.reason, retry_after_seconds=decision.cooldown_seconds); return 0
if decision.behavior is TaskBehavior.HALT:
    await _halt_target(session, target, decision.reason); return 0
raise exc  # trailing else — behavior lạ không rơi qua post-processing
```

`_pause_target` phải set `target.last_scraped_at = now + timedelta(seconds=cooldown)` **kể cả khi cooldown falsy** (dùng `decision.cooldown_seconds` đã resolve — luôn có giá trị ≥ lo sau clamp, không bao giờ None cho PAUSE). `suggested_action` được log qua `decision.suggested_action`/`decision.reason` — không đọc `exc.suggested_action` trong task.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/platforms/xactions/test_error_map.py -v` — expected: pass, độc lập Celery.
- `cd nowing_backend && uv run pytest tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py -v` — expected: pass.
- `cd nowing_backend && uv run pytest tests/unit/ -m unit -q` — expected: không regression.

### Review Findings

<!-- Code review of story-36.3 (2026-09-14) — 4 layers: blind-hunter (10 findings), edge-case-hunter (0), verification-gap (0), acceptance-auditor (0). -->

- [x] [Review][Fixed] Successful ingest leaves paused target in `status="paused"` indefinitely [social_xactions_ingest.py:322] — **resolved 2026-09-14**: success path now resets `target.status` to `"active"` when prior status was `"paused"`; test `test_ingest_social_target_resumes_paused_to_active_on_success` covers.
- [x] [Review][Fixed] Paused target waits `cooldown + scrape_interval` before re-due [social_xactions_ingest.py:370-374] — **resolved 2026-09-14**: scheduler due-check now branches by status — `paused` uses `last_scraped_at <= now` (cooldown-expired), `active` keeps `last_scraped_at <= now - scrape_interval`; tests `test_check_social_targets_paused_due_when_cooldown_expired` and `test_check_social_targets_paused_not_due_during_cooldown` cover both branches.
- [x] [Review][Patch] `suggested_action` dropped for non-`XACT_4001` codes [error_map.py:96-130] — `ACCOUNT_HIBERNATION`/`PROXY_EXHAUSTED`/`XACT_5030`/`XACT_5000` lambdas don't extract `suggested_action`; unmapped-code fallback does. Inconsistent surface policy.
- [x] [Review][Patch] Duplicate `suggested_action` warning log for `XACT_4001` [social_xactions_ingest.py:294-303 + error_map.py:137] — `reason` embeds `(suggested: ...)` then dispatch separately logs `decision.suggested_action` before `_pause_target` logs `decision.reason` again.
- [x] [Review][Patch] `_write_dlq` reads `exc.code` instead of `decision.code` [social_xactions_ingest.py:134] — bypasses `resolve_task_behavior`'s `str.strip().upper()` normalization; DLQ payload may contain unnormalized code strings.
- [x] [Review][Patch] `clamp_countdown`/`clamp_cooldown` don't bound `default` within `[lo,hi]` [error_map.py:42-77] — `return default` path skips clamping; caller-supplied `default < lo` or `> hi` escapes range.
- [x] [Review][Patch] Test omits `failed_at` assertion in DLQ entry [test_social_xactions_ingest.py:836-852] — spec schema `{original_id, payload, error, failed_at}` is required but `failed_at` field unverified in `entry_data`.

**Rejected findings:**
- `false` — `_get_task_retries` `"3.0"` string parse: `task.request.retries` is always `int` in Celery; `"3.0"` never occurs in production. Defensive fallback is sufficient.
- `false` — `exhausted_behavior` non-HALT fall-through: current map only emits `HALT` for exhausted retry; no other enum value exists for `exhausted_behavior` in `XACT_ERROR_BEHAVIOR`. Guard is correct for the actual domain.
- `false` — `XACT_ERROR_BEHAVIOR` mutable dict race condition: map is read-only after module init; no code mutates it at runtime. `MappingProxyType` adds no real protection here.

## Suggested Review Order

**Core Error Behavior Mapping (Pure Logic)**

- Single source of truth resolving XACT error codes to task behavior decisions.
  [`error_map.py:153`](../../nowing_backend/app/proprietary/platforms/xactions/error_map.py#L153)

- Canonical mapping table binding error codes to retry, pause, and halt behaviors.
  [`error_map.py:95`](../../nowing_backend/app/proprietary/platforms/xactions/error_map.py#L95)

- Decoupled dataclass and enum contracts isolating error classification from Celery runtime.
  [`error_map.py:16`](../../nowing_backend/app/proprietary/platforms/xactions/error_map.py#L16)

- Safe boundary clamping keeping retry countdown and pause cooldown within operational limits.
  [`error_map.py:40`](../../nowing_backend/app/proprietary/platforms/xactions/error_map.py#L40)

**Celery Ingest Task Execution & DLQ Routing**

- Dispatches worker task retry, pause, and halt strictly via decision metadata fields.
  [`social_xactions_ingest.py:271`](../../nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py#L271)

- Publishes structured error event to stream:social:failed before permanently halting exhausted targets.
  [`social_xactions_ingest.py:138`](../../nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py#L138)

- Guarantees future last_scraped_at timestamp for paused targets avoiding immediate scheduler spin-loops.
  [`social_xactions_ingest.py:99`](../../nowing_backend/app/tasks/celery_tasks/social_xactions_ingest.py#L99)

**Verification Suites**

- Comprehensive unit tests verifying error mapping, clamping boundaries, and Celery independence.
  [`test_error_map.py:1`](../../nowing_backend/tests/unit/platforms/xactions/test_error_map.py#L1)

- Unit tests verifying worker retry limits, DLQ event publication, and cooldown scheduling.
  [`test_social_xactions_ingest.py:530`](../../nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py#L530)

