# Kiến trúc - Nowing Desktop

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

Ứng dụng desktop Electron cung cấp General Assist, Quick Assist, Screenshot Assist, và đồng bộ thư mục local.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Framework | Electron 42, TypeScript |
| Build | esbuild, electron-builder |
| State | electron-store |
| Permissions | node-mac-permissions |
| Auto-update | electron-updater |
| Analytics | posthog-node |

## Cấu trúc

| File/Thư mục | Mục đích |
|---|---|
| `src/main.ts` | Main process entry |
| `src/preload.ts` | Preload script, exposes contextBridge |
| `src/ipc/channels.ts`, `src/ipc/handlers.ts` | IPC definitions & handlers |
| `src/modules/` | Modules: active-workspace, agent-filesystem, auto-launch, auto-updater, deep-links, screenshot, hotkey, tray, window |
| `scripts/` | Build & dev scripts |
| `electron-builder.yml` | Electron Builder config |

## Entry point

`src/main.ts` khởi tạo Electron window, load web app từ `http://localhost:3000` (dev) hoặc production URL.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
