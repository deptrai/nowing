# Kiến trúc - SurfSense Browser Extension

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

Tiện ích trình duyệt dùng Plasmo framework, thu thập lịch sử duyệt web và gửi về backend SurfSense.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Framework | Plasmo 0.90.5, React 18, TypeScript |
| Styling | Tailwind CSS v3, Radix UI |
| Storage | `@plasmohq/storage` |
| Messaging | `@plasmohq/messaging` (background/popup/content) |
| Icons | lucide-react |

## Cấu trúc

| File/Thư mục | Mục đích |
|---|---|
| `popup.tsx` | Entry popup UI |
| `content.ts` | Content script inject |
| `background/index.ts` | Service worker |
| `background/messages/` | Message handlers (`savedata.ts`, `savesnapshot.ts`) |
| `routes/index.tsx` | In-extension router |
| `routes/pages/` | Pages (ApiKeyForm, HomePage, Loading) |
| `routes/ui/` | UI primitives |
| `utils/backend-url.ts` | Backend URL config |
| `utils/interfaces.ts` | TypeScript interfaces |

## Entry point

`popup.tsx` hoặc `background/index.ts` tùy context.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
