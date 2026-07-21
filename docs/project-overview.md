# Nowing - Tổng quan dự án

**Ngày tạo:** 2026-07-21 16:57:34

## Executive Summary

Nowing là nền tảng nghiên cứu web mở (open-source NotebookLM alternative) cho AI agents, cung cấp live data connectors qua REST API và MCP server. Hệ thống gồm backend Python/FastAPI, frontend Next.js, desktop Electron, browser extension Plasmo, plugin Obsidian, MCP server Python, và evaluation harness.

## Phân loại dự án

- **Kiểu repository:** Monorepo
- **Số phần:** 7
- **Ngôn ngữ chính:** Python, TypeScript
- **Kiến trúc:** Multi-part (backend API + web app + desktop + extension + plugin + MCP + evals)

## Cấu trúc các phần

### Nowing Backend

- **Loại:** backend
- **Vị trí:** `/Users/luisphan/Documents/Nowing/nowing_backend`
- **Công nghệ:** Python 3.12 / FastAPI

### Nowing Web

- **Loại:** web
- **Vị trí:** `/Users/luisphan/Documents/Nowing/nowing_web`
- **Công nghệ:** Next.js 16 / React 19

### Nowing Browser Extension

- **Loại:** extension
- **Vị trí:** `/Users/luisphan/Documents/Nowing/nowing_browser_extension`
- **Công nghệ:** Plasmo / React 18

### Nowing Desktop

- **Loại:** desktop
- **Vị trí:** `/Users/luisphan/Documents/Nowing/nowing_desktop`
- **Công nghệ:** Electron 42 / TypeScript

### Nowing Obsidian Plugin

- **Loại:** extension
- **Vị trí:** `/Users/luisphan/Documents/Nowing/nowing_obsidian`
- **Công nghệ:** TypeScript / esbuild / Obsidian API

### Nowing MCP Server

- **Loại:** backend
- **Vị trí:** `/Users/luisphan/Documents/Nowing/nowing_mcp`
- **Công nghệ:** Python 3.11 / MCP SDK / Starlette

### Nowing Evals

- **Loại:** data
- **Vị trí:** `/Users/luisphan/Documents/Nowing/nowing_evals`
- **Công nghệ:** Python 3.12 / CLI

## Tổng quan công nghệ

| Phần | Công nghệ chính | Framework | Package Manager |
|---|---|---|---|
| Nowing Backend | Python 3.12 | FastAPI / MCP SDK / CLI | uv / pip |
| Nowing Web | Node.js 20+ | Next.js 16, React 19, Tailwind CSS v4 | pnpm |
| Browser Extension | Node.js 18+ | Plasmo, React 18, Tailwind CSS | pnpm |
| Desktop | Node.js | Electron 42, TypeScript | pnpm |
| Obsidian Plugin | Node.js | TypeScript, esbuild, Obsidian API | npm/pnpm |
| Nowing MCP Server | Python 3.11 | FastAPI / MCP SDK / CLI | uv / pip |
| Nowing Evals | Python 3.12 | FastAPI / MCP SDK / CLI | uv / pip |

## Điểm nổi bật kiến trúc

- Backend FastAPI sử dụng SQLAlchemy async + Alembic migration + PostgreSQL/pgvector.
- Web app Next.js App Router, sử dụng server proxy tới backend qua `/api/v1/[...path]`.
- Đồng bộ real-time giữa backend và web qua Rocicorp Zero (`app/api/zero/*`).
- Desktop Electron bọc web app, thêm global shortcut, quick assist, screenshot assist, folder watcher.
- Browser extension Plasmo thu thập lịch sử duyệt web và gửi về backend.
- Obsidian plugin đồng bộ vault qua REST API.
- MCP server expose các scrapers/knowledge base tools qua Model Context Protocol.
- Evals harness chạy benchmarks y tế và tài liệu đa phương thức, gọi backend qua HTTP.

## Hướng dẫn nhanh

Xem [index.md](./index.md) để tìm tài liệu chi tiết từng phần.

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
