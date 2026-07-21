# Kiến trúc - Nowing Obsidian Plugin

**Ngày tạo:** 2026-07-21 16:59:34

## Tóm tắt

Plugin Obsidian đồng bộ vault notes với Nowing, hỗ trợ desktop và mobile.

## Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Language | TypeScript |
| Bundler | esbuild |
| API | Obsidian API (`obsidian` package) |
| Auth | API key cá nhân |

## Cấu trúc

| File | Mục đích |
|---|---|
| `src/main.ts` | Plugin lifecycle, commands, settings tab |
| `src/sync-engine.ts` | Core sync logic, queue, reconciliation |
| `src/api-client.ts` | REST client gọi backend `/obsidian/*` |
| `src/queue.ts` | Persistent upload queue |
| `src/payload.ts` | Xây dựng payload cho từng note |
| `src/settings.ts` | Plugin settings |
| `src/excludes.ts` | Exclude patterns |
| `src/vault-identity.ts` | Vault UUID |
| `manifest.json` | Obsidian plugin manifest |

## Entry point

`src/main.ts` export default class kế thừa `Plugin` của Obsidian.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
