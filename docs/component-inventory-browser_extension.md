# Nowing Browser Extension - Component Inventory

**Ngày tạo:** 2026-07-21 16:49:13

## Tổng quan

Tiện ích Plasmo gồm popup, content script, background service worker, và các UI primitives.

## Components chính

| Component | File | Mục đích |
|---|---|---|
| `popup.tsx` | Root | Entry popup UI |
| `content.ts` | Root | Content script inject vào pages |
| `background/index.ts` | `background/` | Service worker khởi tạo |
| `savedata.ts` | `background/messages/` | Xử lý lưu dữ liệu |
| `savesnapshot.ts` | `background/messages/` | Lưu snapshot trang |
| `routes/index.tsx` | `routes/` | Router chính của extension |
| `ApiKeyForm.tsx` | `routes/pages/` | Nhập API key |
| `HomePage.tsx` | `routes/pages/` | Trang chủ popup |
| `Loading.tsx` | `routes/pages/` | Loading state |
| UI primitives | `routes/ui/` | button, dialog, command, popover, toast, etc. |
| `utils/backend-url.ts` | `utils/` | Cấu hình backend URL |
| `utils/commons.ts` | `utils/` | Common helpers |
| `utils/interfaces.ts` | `utils/` | TypeScript interfaces |

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
