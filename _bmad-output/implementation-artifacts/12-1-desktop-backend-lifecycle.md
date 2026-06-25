# Story 12.1: Quản lý Vòng đời Backend Binary trong Electron (Desktop Backend Lifecycle)

Status: ready-for-dev

## Story

As a Kỹ sư Hệ thống,
I want đóng gói FastAPI Backend thành file binary và tích hợp vào tiến trình nền của Electron,
so that người dùng chỉ cần mở 1 file ứng dụng duy nhất là có thể sử dụng đầy đủ tính năng mà không cần cài đặt Python thủ công.

## Acceptance Criteria

1. **Khởi chạy tự động:** 
   - **Given** ứng dụng Desktop được khởi động
   - **When** main process của Electron chạy
   - **Then** hệ thống tự động tìm và khởi chạy FastAPI binary trên một cổng (port) trống.
2. **Dọn dẹp an toàn (Graceful Shutdown):**
   - **And** khi tắt ứng dụng Electron, tiến trình Backend cũng được đóng (cleanup) an toàn.
3. **Xử lý lỗi khởi chạy:**
   - **And** Ứng dụng hiển thị thông báo lỗi rõ ràng nếu Backend không thể khởi chạy.

## Tasks / Subtasks

- [ ] Task 1: Xây dựng module quản lý tiến trình nền (Background Process Manager) trong Electron (AC: 1, 2)
  - [ ] Subtask 1.1: Viết script/logic tìm port khả dụng ngẫu nhiên hoặc cố định để tránh conflict.
  - [ ] Subtask 1.2: Spawn tiến trình FastAPI binary bằng `child_process.spawn`.
  - [ ] Subtask 1.3: Lắng nghe sự kiện `will-quit` hoặc `window-all-closed` của Electron để gửi tín hiệu SIGTERM dọn dẹp tiến trình FastAPI.
- [ ] Task 2: Giao diện và thông báo lỗi (AC: 3)
  - [ ] Subtask 2.1: Bắt các luồng stderr từ tiến trình FastAPI để log.
  - [ ] Subtask 2.2: Nếu tiến trình exit với mã lỗi (non-zero exit code) trong lúc khởi động, gửi IPC message đến renderer process để hiển thị UI thông báo lỗi (graceful degradation / alert).

## Dev Notes

- **Architecture Compliance:**
  - Ứng dụng cần hỗ trợ Desktop (Electron 41+ + TypeScript + esbuild) theo yêu cầu kiến trúc chung.
  - Quá trình build Backend sẽ sử dụng các công cụ như PyInstaller/PyOxidizer (cần tài liệu/kịch bản build tách biệt nhưng story này tập trung vào lifecycle manager phía Electron). Giả định file binary (ví dụ `nowing-backend-mac`, `nowing-backend-win.exe`) sẽ có sẵn trong thư mục resources khi build app.
  - Cần bảo đảm IPC communication (Inter-Process Communication) an toàn giữa Main Process và Renderer Process cho các cảnh báo lỗi.
- **Source Tree Components:**
  - Thư mục Desktop app: `nowing_desktop/main/` (Nơi chứa logic Electron Main Process)
  - Quản lý process có thể đặt tại: `nowing_desktop/main/backendManager.ts`
- **Testing Standards:**
  - Mock function `child_process.spawn` để viết Unit Test.
  - Đảm bảo kiểm tra việc tìm empty port hoạt động tốt trong unit test.

### Project Structure Notes

- Cần thêm module/helper class độc lập trong Electron Main (ví dụ `BackendManager`) để không làm phình file `main.ts` hoặc `index.ts`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 12]
- [Source: PRD - FR46]

## Dev Agent Record

### Agent Model Used



### Debug Log References

### Completion Notes List

### File List
