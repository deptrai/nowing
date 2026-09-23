---
title: 'Story 36.2: Loop-Scoped XActionsMcpClient Connection Cache'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_commit: 'e3d05c15c'
review_loop_iteration: 1
context:
  - '../planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md#ad-5'
  - 'epic-36-context.md'
---

## Intent

**Problem:** Mỗi Celery task / mỗi MCP tool call hiện tự mở một `XActionsMcpClient` mới (TLS handshake + `session.initialize()` mỗi lần). `xactions_gateway.py:203` tạo client per-call trên FastAPI loop; `social_xactions_ingest.py:188` tạo adapter+client per-task trên Celery loop. Không có session keep-alive reuse; khi scale lên nhiều target/call, latency + session churn + socket churn tăng tuyến tính.

**Approach:** Thêm **loop-scoped shared-client cache** trong `mcp_client.py` — `_LOOP_CLIENTS: weakref.WeakKeyDictionary[AbstractEventLoop, _LoopClientEntry]` bảo vệ bởi `threading.Lock`. `get_shared_client()` trả client đã initialize cho `asyncio.get_running_loop()` hiện tại, re-init khi loop đổi/đóng. `call_tool` và `list_tools` serialize qua `client._serialize_lock` trên client instance. Cleanup hook đồng bộ `_dispose_loop_mcp_client(loop)` đóng client trước `loop.close()` trong `run_async_celery_task`. `XActionsSocialAdapterV2._get_client()` chuyển sang `get_shared_client()`; `adapter.close()`/`__aexit__` là no-op với shared client, bảo vệ session chung.

## Boundaries & Constraints

**Always:**
- **Loop-scoped cache:** Cache keyed by `asyncio.get_running_loop()` qua `weakref.WeakKeyDictionary` làm safety backstop; cleanup bắt buộc gọi explicit `_LOOP_CLIENTS.pop(loop, None)` trong `release_shared_client_for_loop` để bẻ chu trình tham chiếu mạnh (client -> transport -> session -> lock -> loop).
- **Thread-safety:** Mọi thao tác đọc/ghi `_LOOP_CLIENTS` phải được bảo vệ bằng `threading.Lock` cấp module (`_CLIENTS_LOCK`).
- **Atomic entry registration:** `_LoopClientEntry` phải được `setdefault` đồng bộ vào `_LOOP_CLIENTS[loop]` trước khi coroutine `await entry.connecting` để double-checked locking an toàn trên asyncio.
- **Readiness check:** `get_shared_client()` chỉ trả client khi cờ `entry.ready` bật; coroutine thức dậy sau `entry.connecting` phải kiểm tra lại `_LOOP_CLIENTS.get(loop) is entry` để tránh dùng entry đã bị evict do lỗi handshake trước đó.
- **Teardown khi init fail:** Nếu `session.initialize()` thất bại hoặc nhận `CancelledError`, bắt buộc gọi `await client.__aexit__(None, None, None)` (bọc suppress) để giải phóng transport, sau đó evict khỏi cache và giải phóng `connecting` lock.
- **Serialization on client instance:** `call_tool` và `list_tools` serialize qua `self._serialize_lock` gắn trên `XActionsMcpClient` instance (lazy-init trên loop hiện tại) — đảm bảo test unit standalone và unmanaged client không bị `KeyError`. `_fetch_artifact` chạy ngoài lock để tránh nghẽn I/O và deadlock.
- **Re-check session inside lock:** Trong `call_tool`, sau khi acquire `self._serialize_lock`, phải kiểm tra lại `if not self._session or getattr(self, "_tainted", False): raise RuntimeError(...)`.
- **Taint & evict on fatal transport:** Khi gặp `ConnectionError`, `ClosedResourceError`, `EndOfStream`, `httpx.TransportError` hoặc task bị hủy giữa chừng trong lúc gọi tool, đánh dấu `client._tainted = True` và evict khỏi cache nếu `_LOOP_CLIENTS[loop].client is self`.
- **Cleanup hook đồng bộ:** `run_async_celery_task` là hàm đồng bộ; khối `finally` phải gọi helper `_dispose_loop_mcp_client(loop)` chạy `loop.run_until_complete(asyncio.wait_for(release_shared_client_for_loop(loop), timeout=2.0))` bọc `contextlib.suppress(Exception)` TRƯỚC `loop.close()`. Trước khi chạy task, cũng gọi `_dispose_loop_mcp_client(loop)` để bảo vệ defense-in-depth như DB engine.
- **Release waits for in-flight calls:** `release_shared_client_for_loop` phải acquire `client._serialize_lock` trước khi `__aexit__`, và tạm tắt cờ `client._is_managed = False` để teardown thực sự diễn ra.
- **Adapter ownership:** `XActionsSocialAdapterV2` đặt `self._is_shared = client is None`. Hàm `close()`/`__aexit__` chỉ đóng client khi `not self._is_shared`. `_get_client()` luôn re-resolve qua `get_shared_client()` nếu `_is_shared` là True để không trả về client của loop đã đóng khi adapter được tái sử dụng.
- **Multi-tenant per-call (AD-8):** `accountId`, `proxyUrl`, và `context.workspaceId` truyền per-call trong request arguments — tuyệt đối không lưu trên session hoặc client instance attributes.

**Out of Scope:**
- Không migrate `xactions_gateway.py` hoặc `xactions_probe.py` trong Story 36.2: `xactions_gateway` truyền `url`/`api_key`/`consumer_id` động theo connector, đòi hỏi cache key phức hợp `(loop, url, consumer_id)` và hook dọn dẹp trong `FastAPI lifespan.py`. Việc này sẽ thực hiện ở story riêng. Story 36.2 chỉ phục vụ `adapter_v2.py` với cấu hình mặc định.
- Không áp dụng cho các tiến trình không có event loop.

**Never:**
- Không dùng proc-singleton (client sống qua loop boundary gây `RuntimeError: Event loop is closed` — lỗi C4).
- Không để client cache sống qua `loop.close()` mà không đóng transport (rò rỉ socket và task ngầm).
- Không serialize bằng lock tạo trên loop khác.
- Không nuốt lỗi hủy task (`asyncio.CancelledError`) trong quá trình init làm kẹt entry rác.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Reuse trong 1 task | Nhiều `fetch_posts_for_target` trên cùng loop | 1 session keep-alive duy nhất, 1 lần initialize | — |
| Loop mới (task 2) | `loop.close()` rồi `new_event_loop()` | Re-init client trên loop mới, không lỗi C4 | Cleanup task trước gọi `_LOOP_CLIENTS.pop` + `__aexit__` |
| Initialize fail | `session.initialize()` raise | `__aexit__` transport, pop entry, release lock, propagate lỗi | Không để lại transport rò rỉ hay entry mồ côi |
| Concurrent get_shared_client | Nhiều coroutine gọi đồng thời trên loop mới | Coroutine đầu khởi tạo, các coroutine sau đợi `entry.connecting`, kiểm tra `entry.ready` rồi tái sử dụng | Tránh thundering herd và double-handshake |
| Stranded waiter sau init fail | Coroutine A fail init & evict; Coroutine B đang chờ lock thức dậy | Coroutine B phát hiện entry không còn trong dict, retry `get_shared_client()` | Tự phục hồi, không thao tác trên entry chết |
| Concurrent call_tool | 2 coroutine cùng gọi tool trên 1 client | Serialize qua `client._serialize_lock`, không đan xen frame | `async with self._serialize_lock` |
| Transport đứt giữa chừng | `call_tool` gặp `httpx.TransportError` / peer close | Đánh dấu `_tainted=True`, pop khỏi `_LOOP_CLIENTS`, raise lỗi | Lần gọi sau re-init client mới |
| Release khi có in-flight call | `release_shared_client_for_loop` chạy | Đợi `_serialize_lock` trước khi đóng transport | Timeout 2.0s từ sync runner chống treo vĩnh viễn |
| Celery runner timeout/crash | Task Celery crash hoặc timeout | `_dispose_loop_mcp_client` dọn dẹp an toàn trong `finally` | Bọc `suppress(Exception)`, pop entry |
| Adapter tái sử dụng qua nhiều task | 1 instance adapter gọi trên loop A rồi loop B | `_get_client()` gọi `get_shared_client()` lấy client loop B | Không giữ `self.client` chết từ loop A |

## Code Map

- `nowing_backend/app/proprietary/platforms/xactions/mcp_client.py` — Thêm `_LOOP_CLIENTS`, `_CLIENTS_LOCK`, `_LoopClientEntry`, `get_shared_client()`, `release_shared_client_for_loop()`, `self._serialize_lock`, và cờ `_is_managed`.
- `nowing_backend/app/tasks/celery_tasks/__init__.py` — Thêm helper đồng bộ `_dispose_loop_mcp_client(loop)` và gọi trong `run_async_celery_task` (cả trước và sau task).
- `nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py` — Cập nhật `_get_client()` dùng `get_shared_client()`; đặt `self._is_shared = client is None`; `close()` chỉ đóng khi `not self._is_shared`.
- `nowing_backend/tests/unit/platforms/xactions/test_mcp_client_cache.py` (file mới) — Bộ test kiểm thử cache, vòng đời loop, lock serialization, và khả năng thu hồi bộ nhớ.
- `nowing_backend/tests/unit/tasks/test_celery_async_runner.py` — Bổ sung test kiểm tra `run_async_celery_task` gọi `_dispose_loop_mcp_client` trước khi đóng loop.

## Tasks & Acceptance

**Execution:**
- [x] `mcp_client.py`: Khai báo `_LoopClientEntry`, `_LOOP_CLIENTS`, `_CLIENTS_LOCK`. Cài đặt `get_shared_client()`, `release_shared_client_for_loop()`, `self._serialize_lock`, logic taint/evict trên fatal transport.
- [x] `celery_tasks/__init__.py`: Thêm `_dispose_loop_mcp_client(loop)` và tích hợp vào `run_async_celery_task`.
- [x] `adapter_v2.py`: Điều chỉnh `_get_client` và `close()` theo quy tắc `_is_shared`.
- [x] `test_mcp_client_cache.py` & `test_celery_async_runner.py`: Viết đầy đủ 16 kịch bản kiểm thử (7 kịch bản nền tảng + 9 kịch bản ranh giới).

**Acceptance Criteria (verbatim epics.md lines 4818-4829):**
- Given `run_async_celery_task` creates a `new_event_loop()` per task and closes it, when two ingest tasks run on the same worker, then each gets a working `XActionsMcpClient` session.
- And the client keys its session cache by `asyncio.get_running_loop()` and calls `session.initialize()` whenever the current loop differs from the cached loop or is closed; failed initialize evicts the cache entry rather than leaving a half-initialized client.
- And the cache is a `weakref.WeakKeyDictionary` keyed on the loop so dead loops and their clients are garbage-collected — no unbounded retention across thousands of tasks.
- And `call_tool` is serialized through a lock so concurrent coroutines on one loop cannot interleave streamable-http frames.
- And `accountId` and `proxyUrl` are passed per call via request arguments for multi-tenancy and are never stored on the session.

## Design Specifications & Correctness Invariants

1. **`_LoopClientEntry` & Cache Structure:**
   ```python
   class _LoopClientEntry:
       def __init__(self):
           self.client: XActionsMcpClient | None = None
           self.ready: bool = False
           self.connecting: asyncio.Lock = asyncio.Lock()
           self.init_error: BaseException | None = None

   _LOOP_CLIENTS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _LoopClientEntry] = weakref.WeakKeyDictionary()
   _CLIENTS_LOCK = threading.Lock()
   ```
2. **`get_shared_client()` Resolution Flow:**
   - Kiểm tra tham số kết nối: nếu caller truyền `url`, `api_key`, hoặc `consumer_id` khác mặc định, raise `ValueError` hướng dẫn dùng client unmanaged (tránh rò rỉ credential).
   - Lấy `loop = asyncio.get_running_loop()`. Đồng bộ kiểm tra `_LOOP_CLIENTS.get(loop)`. Nếu entry tồn tại và `entry.ready` và client không bị `_tainted`, trả về `entry.client`.
   - Nếu chưa có: bọc `with _CLIENTS_LOCK: entry = _LOOP_CLIENTS.setdefault(loop, _LoopClientEntry())`.
   - Bọc `async with entry.connecting:`
     - Sau khi có lock: kiểm tra lại `with _CLIENTS_LOCK: current = _LOOP_CLIENTS.get(loop)`. Nếu `current is not entry`: coroutine trước đã fail và evict -> đệ quy gọi lại `get_shared_client()`.
     - Nếu `entry.ready`: return `entry.client`.
     - Tạo `client = XActionsMcpClient()`; gán `client._is_managed = True`.
     - `try: await client.__aenter__(); entry.client = client; entry.ready = True; return client`
     - `except BaseException as exc:`
       - `with _CLIENTS_LOCK: _LOOP_CLIENTS.pop(loop, None)`
       - `with contextlib.suppress(Exception): await client._close_session()`
       - `raise`
3. **Serialization & Protocol Safety:**
   - Trên `XActionsMcpClient`:
     ```python
     @property
     def serialize_lock(self) -> asyncio.Lock:
         if self._serialize_lock is None or self._serialize_lock._loop is not asyncio.get_running_loop():
             self._serialize_lock = asyncio.Lock()
         return self._serialize_lock
     ```
   - Cả `call_tool` và `list_tools` đều chạy trong `async with self.serialize_lock:`.
   - Sau khi vào lock: kiểm tra `if not self._session or getattr(self, "_tainted", False): raise RuntimeError("Session is closed or tainted")`.
   - `_fetch_artifact` chạy HOÀN TOÀN NGOÀI `self.serialize_lock`.
   - Khi `call_tool` gặp lỗi mạng chết người (`ConnectionError`, `anyio.ClosedResourceError`, `anyio.EndOfStream`, `httpx.TransportError`):
     ```python
     self._tainted = True
     with _CLIENTS_LOCK:
         if _LOOP_CLIENTS.get(loop) is not None and _LOOP_CLIENTS[loop].client is self:
             _LOOP_CLIENTS.pop(loop, None)
     ```
4. **Cleanup & Lifecycle Management:**
   - Trong `mcp_client.py`:
     ```python
     async def release_shared_client_for_loop(loop: asyncio.AbstractEventLoop) -> None:
         with _CLIENTS_LOCK:
             entry = _LOOP_CLIENTS.pop(loop, None)
         if entry and entry.client:
             client = entry.client
             client._is_managed = False  # Bật lại để __aexit__ thực thi đóng session
             with contextlib.suppress(Exception):
                 async with asyncio.timeout(0.5):
                     async with client.serialize_lock:
                         await client._close_session()
             with contextlib.suppress(Exception):
                 await client._close_session()
     ```
   - Trong `celery_tasks/__init__.py`:
     ```python
     def _dispose_loop_mcp_client(loop: asyncio.AbstractEventLoop) -> None:
         if loop.is_closed():
             with _CLIENTS_LOCK:
                 _LOOP_CLIENTS.pop(loop, None)
             return
         with contextlib.suppress(Exception):
             loop.run_until_complete(
                 asyncio.wait_for(release_shared_client_for_loop(loop), timeout=2.0)
             )
     ```
   - Trong `run_async_celery_task`: gọi `_dispose_loop_mcp_client(loop)` ở đầu khối `try` (defense-in-depth) và ở khối `finally` trước `loop.shutdown_asyncgens()` và `loop.close()`.
5. **Adapter V2 Integration:**
   - `self._is_shared = client is None`
   - `async def _get_client(self) -> XActionsMcpClient:`
     - `if not self._is_shared and self.client: return self.client`
     - `return await get_shared_client()`
   - `async def close(self) -> None:`
     - `if not self._is_shared and self.client: await self.client.__aexit__(None, None, None)`

## Verification

**Commands:**
- `pytest nowing_backend/tests/unit/platforms/xactions/test_mcp_client_cache.py -v`
- `pytest nowing_backend/tests/unit/platforms/test_xactions_adapter_v2.py nowing_backend/tests/unit/tasks/celery_tasks/test_social_xactions_ingest.py nowing_backend/tests/unit/tasks/test_celery_async_runner.py -v`

**Required Test Scenarios:**
1. **2-Loop Sequential Lifecycle:** Loop 1 khởi tạo và gọi tool; đóng Loop 1. Loop 2 gọi `get_shared_client()` và gọi tool thành công. Khẳng định không bị lỗi `RuntimeError: Event loop is closed` hoặc `Future attached to a different loop`.
2. **Concurrent Tool Call Serialization:** Mock `_session.call_tool` có `await asyncio.sleep(0.02)`. Chạy `asyncio.gather` 5 cuộc gọi đồng thời. Khẳng định `in_flight <= 1` trong suốt thời gian chạy.
3. **List Tools & Call Tool Shared Lock:** Khẳng định `list_tools()` và `call_tool()` dùng chung `self.serialize_lock` và không thể chạy đan xen.
4. **Initialization Failure Cleanup & Retry:** Mock `session.initialize()` quăng lỗi. Khẳng định entry bị xóa khỏi cache, transport được `__aexit__`, và lần gọi `get_shared_client()` tiếp theo trên cùng loop khởi tạo lại thành công.
5. **Stranded Waiters Recovery:** Giả lập 2 coroutine đồng thời gọi `get_shared_client()` trên loop mới; coroutine đầu fail init; khẳng định coroutine thứ hai phục hồi sạch sẽ và re-init thành công.
6. **Passive & Active Memory Recovery:** Kiểm tra `release_shared_client_for_loop` gọi `_LOOP_CLIENTS.pop`; kiểm tra xóa loop và `gc.collect()` giải phóng toàn bộ entry mà không bị rò rỉ bộ nhớ.
7. **Default Adapter Integration:** Khẳng định `XActionsSocialAdapterV2()._get_client()` gọi `get_shared_client()`, và `adapter.close()` không làm đóng session dùng chung.
8. **Injected Standalone Adapter Integration:** Khẳng định `XActionsSocialAdapterV2(client=custom)` đóng `custom` khi `adapter.close()` được gọi.
9. **Direct Async With Protection:** Khẳng định gọi `async with client:` trên shared client không làm mất session của các coroutine khác trên cùng loop.
10. **Fatal Transport Drop Eviction:** Giả lập `httpx.TransportError` trong `call_tool`. Khẳng định client bị đánh dấu `_tainted` và evict khỏi `_LOOP_CLIENTS`.
11. **Artifact Fetching Outside Lock:** Khẳng định trong lúc `_fetch_artifact` đang chạy, `self.serialize_lock.locked()` là False.
12. **Celery Runner Hook Execution & Ordering:** Khẳng định `run_async_celery_task` gọi `_dispose_loop_mcp_client` trước khi `loop.close()`.
13. **Celery Runner Timeout Protection:** Khẳng định nếu `release_shared_client_for_loop` bị treo quá 2 giây, `run_async_celery_task` vẫn thoát bình thường và đóng loop an toàn mà không chặn tiến trình worker.
14. **Thread-Safety Multi-Thread Access:** Chạy `ThreadPoolExecutor` gọi `get_shared_client()` trên các thread khác nhau, khẳng định không bị lỗi `dictionary changed size during iteration`.
15. **Multi-Tenancy Arguments Non-Persistence:** Khẳng định `accountId` và `proxyUrl` truyền vào `call_tool` không bị lưu lại trên attributes hoặc header của client.
16. **Custom Parameters Rejection:** Khẳng định truyền `url="http://custom"` vào `get_shared_client()` quăng `ValueError`.

## Suggested Review Order

**Cache Core & Serialization**

- Loop-scoped WeakKey cache và hàm lấy client dùng chung an toàn đa luồng
  [`mcp_client.py:378`](../../nowing_backend/app/proprietary/platforms/xactions/mcp_client.py#L378)

- Khóa tuần tự hóa phiên làm việc MCP trên client instance
  [`mcp_client.py:105`](../../nowing_backend/app/proprietary/platforms/xactions/mcp_client.py#L105)

**Lifecycle & Cleanup Hooks**

- Giải phóng và đóng phiên MCP trước khi event loop kết thúc
  [`mcp_client.py:457`](../../nowing_backend/app/proprietary/platforms/xactions/mcp_client.py#L457)

- Hook dọn dẹp đồng bộ an toàn trong runner của Celery
  [`celery_tasks/__init__.py:112`](../../nowing_backend/app/tasks/celery_tasks/__init__.py#L112)

**Consumer Integration**

- Adapter chuyển sang client dùng chung và bảo vệ phiên khi thoát context
  [`adapter_v2.py:189`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L189)

- Ngăn ngừa đóng sớm phiên kết nối dùng chung trong adapter close
  [`adapter_v2.py:382`](../../nowing_backend/app/proprietary/platforms/xactions/adapter_v2.py#L382)

**Comprehensive Test Suite**

- Bộ kiểm thử toàn diện vòng đời, concurrency, và ranh giới bộ nhớ
  [`test_mcp_client_cache.py:1`](../../nowing_backend/tests/unit/platforms/xactions/test_mcp_client_cache.py#L1)

- Kiểm thử thứ tự dọn dẹp và giới hạn thời gian trong Celery runner
  [`test_celery_async_runner.py:434`](../../nowing_backend/tests/unit/tasks/test_celery_async_runner.py#L434)
