# Nowing Obsidian Plugin - Component Inventory

**Ngày tạo:** 2026-07-21 16:49:13

## Tổng quan

Plugin Obsidian tổ chức theo module rõ ràng: lifecycle, sync engine, API client, settings, UI modals.

## Components chính

| Component | File | Mục đích |
|---|---|---|
| Plugin lifecycle | `src/main.ts` | onload, onunload, commands, settings tab |
| Sync Engine | `src/sync-engine.ts` | Core sync, queue, reconciliation |
| API Client | `src/api-client.ts` | Gọi backend `/obsidian/*` qua `requestUrl` |
| Upload Queue | `src/queue.ts` | Persistent queue xử lý uploads |
| Payload Builder | `src/payload.ts` | Xây dựng payload từ note |
| Settings | `src/settings.ts` | Plugin settings interface/defaults |
| Excludes | `src/excludes.ts` | Exclude glob patterns |
| Vault Identity | `src/vault-identity.ts` | UUID và thông tin vault |
| Status Bar | `src/status-bar.ts` | Hiển thị trạng thái sync |
| Status Modal | `src/status-modal.ts` | Modal chi tiết trạng thái |
| Attachments Confirm | `src/attachments-confirm-modal.ts` | Xác nhận đồng bộ attachments |
| Folder Suggest | `src/folder-suggest-modal.ts` | Chọn folder để sync |
| Types | `src/types.ts` | TypeScript interfaces |

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
