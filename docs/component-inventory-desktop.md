# SurfSense Desktop - Component Inventory

**Ngày tạo:** 2026-07-21 16:49:13

## Tổng quan

Desktop Electron chia thành main process, preload, IPC channels, và các modules chức năng.

## Components chính

| Module | File | Mục đích |
|---|---|---|
| Main Process | `src/main.ts` | Khởi tạo cửa sổ, menu, tray, lifecycle |
| Preload | `src/preload.ts` | Expose contextBridge APIs |
| IPC Channels | `src/ipc/channels.ts` | Định nghĩa IPC channels |
| IPC Handlers | `src/ipc/handlers.ts` | Xử lý IPC calls |
| Active Workspace | `src/modules/active-workspace.ts` | Quản lý workspace đang active |
| Agent Filesystem | `src/modules/agent-filesystem.ts` | Truy cập filesystem cho agent |
| Folder Watcher | `src/modules/agent-filesystem-tree-watcher.ts` | Watch local folder |
| Analytics | `src/modules/analytics.ts` | PostHog analytics |
| Auto-launch | `src/modules/auto-launch.ts` | Khởi động cùng OS |
| Auto-updater | `src/modules/auto-updater.ts` | Electron auto-updater |
| Deep Links | `src/modules/deep-links.ts` | Xử lý deep links |
| Screenshot | `src/modules/screenshot-*.ts` | Screenshot assist |
| Quick Assist | `src/modules/quick-assist*.ts` | Text selection shortcut |
| Global Shortcut | `src/modules/global-shortcut*.ts` | Global hotkey |
| Tray | `src/modules/tray*.ts` | System tray menu |

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
