---
title: 'Story 32.2: Chrome Extension chrome.debugger.onDetach Recovery & Reconnection'
type: 'feature'
created: '2026-09-16'
status: 'done'
baseline_commit: '9fc2691974974bd37595e6bad152ac8652fe6f23'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Khi người dùng đóng DevTools, bấm "Cancel" trên thanh infobar cảnh báo debug của Chrome, hoặc đóng tab đang điều khiển, `chrome.debugger` bị detach nhưng extension không lắng nghe sự kiện `onDetach`. Hậu quả là backend worker kẹt chờ kết quả qua `redis.blpop` tối đa 60 giây, các lệnh CDP tiếp theo bị gửi vào tab không còn debugger, và nếu xảy ra ngắt kết nối giữa chừng có thể dẫn đến race condition gửi trùng kết quả (duplicate result poisoning) vào Redis.

**Approach:** Lắng nghe `chrome.debugger.onDetach` trong extension `CdpBridge`, lập tức fail-fast gửi mã lỗi `DEBUGGER_DETACHED: <reason>` về `/dsh/cdp/result` để giải phóng backend worker ngay lập tức (<200ms). Đồng thời, bảo vệ chống race condition: triệt tiêu việc gửi đúp kết quả từ khối catch của lệnh đang chạy, phân biệt giữa detach chủ động (intentional) và bị hủy ngoài ý muốn, dọn sạch hàng đợi lệnh tồn đọng, và định nghĩa `CdpDebuggerDetachedError` ở backend.

## Boundaries & Constraints

**Always:**
- Đăng ký listener `chrome.debugger.onDetach.addListener` tại singleton `CdpBridge.getInstance()`.
- Phân biệt detach chủ động và bị hủy: trong `detachDebugger()`, đánh dấu cờ hoặc kiểm tra `this.activeDebuggeeTabId` sao cho lệnh kết thúc bình thường không kích hoạt cảnh báo detach giả (false-positive).
- Phòng chống gửi đúp kết quả (Single Result Guarantee): theo dõi `currentCommand` kèm trạng thái `alreadyHandled`. Nếu `onDetach` đã gửi lỗi về backend, khối `catch` của lệnh đang `await` tuyệt đối không gửi lại kết quả lần 2 để tránh làm bẩn hàng đợi Redis.
- Dọn dẹp hàng đợi: khi `onDetach` xảy ra, ngay lập tức xóa toàn bộ lệnh trong `this.queued = []` và đặt `this.processing = false`.
- Định nghĩa exception `class CdpDebuggerDetachedError(CdpExecutionError)` ở backend: bắt prefix `DEBUGGER_DETACHED` từ parsed result để phân loại lỗi rõ ràng và dừng worker fail-fast.

**Ask First:**
- Tự động attach lại tab mới nếu người dùng reload trang (mặc định giữ nguyên cơ chế fail-fast an toàn).

**Never:**
- Không gọi lại `chrome.debugger.detach()` nếu tab đã được Chrome thông báo `onDetach` (tránh exception "Debugger is not attached").
- Không retry lệnh tự động khi debugger bị người dùng chủ động bấm Cancel infobar hoặc đóng tab.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| User cancels debug infobar during execution | Chrome fires `onDetach` with reason `"canceled_by_user"` while command is running | Extension posts 1 lần `DEBUGGER_DETACHED: canceled_by_user` to `/dsh/cdp/result`; ongoing command's catch block suppresses secondary result; backend unblocks <200ms | Backend raises `CdpDebuggerDetachedError`; worker releases slot immediately |
| Target tab closed with queued commands | Chrome fires `onDetach` with reason `"target_closed"`; `this.queued.length > 0` | Extension posts detach error for active command; resets `activeDebuggeeTabId = null`; flushes `this.queued = []`; stops processing | Remaining queued commands discarded safely without errors |
| Normal command completion | Extension completes action and calls `detachDebugger()` | Intentional detach is flagged; `onDetach` event (if fired) is ignored; only the success result is posted | N/A |
| Detach for an unrelated tabId | `onDetach` fires for a tab that is not `this.activeDebuggeeTabId` | Event is ignored; active debuggee session remains unaffected | Debug log only |

</frozen-after-approval>

## Code Map

- `nowing_browser_extension/background/cdp-bridge.ts` -- Thêm listener `chrome.debugger.onDetach`, tracking `currentCommand`, cơ chế chống gửi đúp kết quả, phân biệt intentional detach, flush `this.queued`.
- `nowing_backend/app/tasks/dsh_worker_browser_operator.py` -- Định nghĩa `CdpDebuggerDetachedError(CdpExecutionError)`, bắt lỗi `DEBUGGER_DETACHED` từ extension response để fail-fast.
- `nowing_backend/tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py` -- Unit tests kiểm chứng: (1) `test_cdp_debugger_detached_raises_specific_error` và (2) không bị kẹt timeout 60s khi nhận `DEBUGGER_DETACHED`.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/tasks/dsh_worker_browser_operator.py` -- Định nghĩa `CdpDebuggerDetachedError` và xử lý kết quả `DEBUGGER_DETACHED` trong `_cdp_crawl_node` -- Đảm bảo backend nhận diện được sự cố detach và fail-fast.
- [x] `nowing_browser_extension/background/cdp-bridge.ts` -- Đăng ký `chrome.debugger.onDetach`, thêm tracking `currentCommand`, cờ intentional detach, và logic dọn dẹp hàng đợi an toàn -- Ngăn worker bị treo 60s và ngăn chặn hoàn toàn duplicate result poisoning vào Redis.
- [x] `nowing_backend/tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py` -- Bổ sung unit tests cho kịch bản `CdpDebuggerDetachedError` -- Đảm bảo độ tin cậy và không hồi quy cho backend CDP execution node.

**Acceptance Criteria:**
- Given a running CDP mission waiting on `blpop`, when the extension posts a result with error `DEBUGGER_DETACHED: canceled_by_user`, then the backend unblocks immediately (<200ms) and raises `CdpDebuggerDetachedError`.
- Given an active CDP command in extension, when Chrome triggers `onDetach`, then exactly ONE result is sent to `/dsh/cdp/result`, `this.queued` is emptied, and subsequent command rejection does not post a duplicate result.
- Given normal command execution, when `detachDebugger()` is invoked intentionally, then no spurious `DEBUGGER_DETACHED` error is dispatched.

## Verification

**Commands:**
- `uv run pytest tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py -q` -- expected: All unit tests pass including the new debugger detach tests.
- `cd nowing_browser_extension && npm run build` -- expected: Clean TypeScript compilation and build with no errors.

## Suggested Review Order

**CDP Lifecycle & Detach Handling**

- Listener chrome.debugger.onDetach and guarded result dispatch
  [`cdp-bridge.ts:70`](../../nowing_browser_extension/background/cdp-bridge.ts#L70)

- Single result guarantee and intentional detach tracking
  [`cdp-bridge.ts:228`](../../nowing_browser_extension/background/cdp-bridge.ts#L228)

**Backend Fail-Fast & Error Classification**

- CdpDebuggerDetachedError definition and error string prefix detection
  [`dsh_worker_browser_operator.py:32`](../../nowing_backend/app/tasks/dsh_worker_browser_operator.py#L32)

- Payload schema command_id preservation during errors
  [`dsh.py:218`](../../nowing_backend/app/schemas/dsh.py#L218)

- Endpoint result ingestion keeping command_id on error payloads
  [`dsh_routes.py:507`](../../nowing_backend/app/routes/dsh_routes.py#L507)

**Verification & Regression Suite**

- Unit tests asserting immediate unblock without 60s timeout
  [`test_browser_operator_cdp.py:125`](../../nowing_backend/tests/unit/tasks/dsh_worker/test_browser_operator_cdp.py#L125)
