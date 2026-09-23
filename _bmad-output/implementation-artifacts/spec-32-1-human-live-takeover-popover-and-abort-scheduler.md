---
title: 'Story 32.1: HumanLiveTakeoverPopover UI with Countdown Timer and Abort Scheduler'
type: 'feature'
created: '2026-09-17'
status: 'review'
baseline_commit: 'bbb49f65ee07cc3dddd676191337372d8a6cac72'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Khi mission chuyển sang `phase="waiting_for_human"` (do gặp CAPTCHA/challenge hoặc người dùng chủ động pause để can thiệp), Redis set takeover lock với TTL 15 phút (900s). Tuy nhiên, khi hết 15 phút mà không có tương tác, lock trong Redis tự biến mất nhưng bản ghi mission trong PostgreSQL vẫn kẹt ở `status="running", phase="waiting_for_human"` vô thời hạn (zombie mission), và giao diện phía frontend chỉ dừng đồng hồ ở 00:00 mà không tự hủy hoặc chuyển trạng thái sang `aborted_timeout`.

**Approach:** Xây dựng cơ chế quét dọn tự động (Takeover Timeout Sweeper) ở backend để phát hiện và chuyển các mission quá hạn 15 phút sang `status="cancelled", phase="aborted_timeout"`, giải phóng tài nguyên. Đồng thời bổ sung route `POST /dsh/missions/{id}/abort` cho phép hủy chủ động từ UI, và nâng cấp `HumanLiveTakeoverPopover` để hiển thị nút "Hủy nhiệm vụ (Abort)" kèm tự động đồng bộ khi hết giờ.

## Boundaries & Constraints

**Always:**
- Kiểm tra tính nguyên tử: khi mission bị timeout hoặc hủy, giải phóng takeover key `dsh:lock:takeover:{workspace}:{mission}` và chuyển `status="cancelled", phase="aborted_timeout"`.
- Giữ nguyên TTL 15 phút (900 giây) làm ngưỡng chuẩn cho takeover.
- Frontend `HumanLiveTakeoverPopover` phải hiển thị rõ ràng thời gian đếm ngược và trạng thái hết hạn.
- Hỗ trợ endpoint hủy chủ động `POST /api/v1/dsh/missions/{mission_id}/abort` để người dùng không phải chờ hết 15 phút nếu muốn bỏ qua.

**Ask First:**
- Tự động hoàn lại credit khi mission bị `aborted_timeout` (mặc định tuân thủ chính sách credit hiện tại của DSH).

**Never:**
- Không xóa vĩnh viễn (hard delete) bản ghi mission khi timeout; phải giữ audit trail với `status="cancelled"` và `phase="aborted_timeout"`.
- Không cho phép resume một mission đã rơi vào `aborted_timeout` (phải trả về HTTP 409 Conflict).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Countdown timer reaches 00:00 | Mission waiting_for_human > 15m; Redis lock expired | Sweeper / UI transitions mission to `status="cancelled", phase="aborted_timeout"`; popover closes / shows timeout state | Log mission timeout; release any lingering locks |
| User clicks "Abort" button in Popover | User clicks "Hủy nhiệm vụ" via UI | UI calls `POST /dsh/missions/{id}/abort`; backend sets `status="cancelled", phase="aborted_timeout"`; releases Redis lock immediately | 200 OK with updated mission state |
| Attempt to resume an aborted mission | Call `POST /dsh/missions/{id}/resume` on mission with `phase="aborted_timeout"` | Backend rejects with HTTP 409 Conflict: "Mission is not in waiting_for_human phase" | Return standard 409 error envelope |
| Sweeper runs with no expired missions | Active missions with lock alive (<15m) | Sweeper leaves active missions untouched; returns 0 swept | Safe no-op |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/services/dsh_mission_service.py` -- Bổ sung hàm `sweep_expired_takeovers(session)` và `abort_takeover_mission(session, mission_id)`.
- `nowing_backend/app/routes/dsh_routes.py` -- Thêm endpoint `POST /dsh/missions/{mission_id}/abort` và endpoint maintenance/trigger `POST /dsh/missions/sweep-takeovers`.
- `nowing_web/components/dsh/HumanLiveTakeoverPopover.tsx` -- Thêm nút "Hủy nhiệm vụ (Abort)", callback `onAbort`, và xử lý tự động khi đồng hồ về `00:00`.
- `nowing_web/lib/apis/dsh-api.service.ts` -- Thêm `abortMission(missionId, workspaceId)`.
- `nowing_backend/tests/unit/tasks/dsh_worker/test_takeover_abort_scheduler.py` -- Unit tests cho logic sweep timeout và abort takeover.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/services/dsh_mission_service.py` -- Cài đặt logic quét và chuyển trạng thái mission timeout sang `aborted_timeout`, xóa lock Redis -- Giải phóng tài nguyên các mission bị bỏ rơi.
- [x] `nowing_backend/app/routes/dsh_routes.py` -- Thêm route `POST /dsh/missions/{id}/abort` cho phép hủy mission đang chờ người dùng -- Cho phép người dùng can thiệp hủy chủ động.
- [x] `nowing_web/components/dsh/HumanLiveTakeoverPopover.tsx` & `dsh-api.service.ts` -- Bổ sung nút Abort và hàm gọi API hủy -- Hoàn thiện trải nghiệm người dùng trên popover.
- [x] `nowing_backend/tests/unit/tasks/dsh_worker/test_takeover_abort_scheduler.py` -- Viết bộ test kiểm tra sweep timeout và abort route -- Đảm bảo không hồi quy.

**Acceptance Criteria:**
- Given an active browser operator mission in `phase="waiting_for_human"`, when 15 minutes elapse without resume, then the backend marks the mission `status="cancelled"` and `phase="aborted_timeout"`.
- Given a user viewing `HumanLiveTakeoverPopover`, when they click "Hủy nhiệm vụ (Abort)", then the mission transitions to `aborted_timeout` immediately and the popover dismisses.
- Given an aborted mission, when calling resume, then the backend rejects with HTTP 409 Conflict.

## Verification

**Commands:**
- `uv run pytest tests/unit/tasks/dsh_worker/test_takeover_abort_scheduler.py -q` -- expected: All sweeper and abort tests pass.
- `cd nowing_web && pnpm tsc --noEmit` -- expected: Clean TypeScript check on frontend components.
