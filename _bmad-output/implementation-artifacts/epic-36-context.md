# Epic 36 Context: XActions Unified Connection Contract (Nowing-side)

<!-- Compiled from epics.md Epic 36, ARCHITECTURE-SPINE.md (AD-1..10), and spec-xactions-connection/SPEC.md. -->

## Goal

Thiết lập hợp đồng kết nối dài hạn vững chắc giữa Nowing và XActions: unblock các monitored targets thuộc VN-domain thông qua fallback an toàn (P0), bảo đảm MCP client loop-scoped chống rò rỉ socket/event loop crash, chuẩn hóa bản đồ lỗi `XACT_*`, chuyển đổi sang mô hình single-writer trên Redis Stream, và chuyển từ cấu hình tĩnh `PLATFORM_TOOL_MAP` sang khám phá động thông qua `x_actions_list` theo danh mục hành động chính tắc (canonical action matrix).

## Stories

- **36.1**: Wire `x_crawl_post` Fallback & Graceful Unsupported Marking (P0 — unblock VN targets now)
- **36.2**: Loop-Scoped `XActionsMcpClient` Connection Cache
- **36.3**: Centralized `XACT_*` → Task-Behavior Error Map
- **36.4**: Single-Writer Stream — Stop Nowing Publishing to `stream:social:raw_posts` (Blocked by REQ-X2)
- **36.5**: Stream Consumer Schema Contract & DLQ Routing (Depends on 36.4, REQ-X2)
- **36.6**: Canonical Action Matrix & Legacy Tool Deprecation (Blocked by REQ-X1, REQ-X3)

## Requirements & Constraints

- **AD-1 / AD-2**: Nowing gọi XActions qua MCP streamable-http port 3001. Mọi tác vụ scrape mới hướng về công cụ tổng quát `x_scrape` với tham số lồng nhau `args: {...}` và phong bì ngữ cảnh `context: { targetId, workspaceId }`.
- **AD-3 / AD-4**: XActions là SOLE WRITER trên `stream:social:raw_posts`. Dữ liệu stream tuân thủ snake_case (`SocialPostEvent`). Nowing loại bỏ hành vi tự publish raw post vào stream này khi XActions REQ-X2 sẵn sàng.
- **AD-5**: `XActionsMcpClient` gắn vòng đời với `asyncio.get_running_loop()` (loop-scoped cache qua `WeakKeyDictionary`), tuần tự hóa lệnh gọi qua lock, không dùng proc-singleton để tránh lỗi `Event loop is closed` giữa các Celery task.
- **AD-6**: Khi `x_scrape` trả `XACT_404` (tool_not_found), adapter bắt buộc fallback về `x_crawl_post` với đủ 2 tham số `{platform, url}`. Nếu target không có URL http(s) hợp lệ, đánh dấu target là `unsupported` (`is_active=False`, commit DB) thay vì quăng lỗi crash task.
- **AD-8**: Toàn bộ Nowing là 1 consumer định danh `nowing` (quota 60 RPM / burst 15). Phân lập tenant bằng tham số `accountId` và `context.workspaceId`, tuyệt đối không tạo session MCP riêng cho từng user/workspace.
- **AD-10**: Bản đồ lỗi tập trung chuyển mã lỗi `XACT_*` thành enum hành vi (`TaskBehavior`), tách rời logic Celery khỏi adapter tầng giao thức.
- **Deploy order**: Nhóm Phase 1 (36.1, 36.2, 36.3) triển khai độc lập tại Nowing. Nhóm Phase 2 (36.4, 36.5, 36.6) bị chặn bởi các yêu cầu XActions (REQ-X1..X3) và phải được bảo vệ bởi feature flags (`XACTIONS_USE_UNIFIED_DISPATCH`, `XACTIONS_STREAM_SINGLE_WRITER_ENABLED`).
