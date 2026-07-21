# Nowing Documentation Index

**Ngày tạo:** 2026-07-21 16:59:34

## Tổng quan dự án

Nowing là nền tảng nghiên cứu web mở (open-source NotebookLM alternative) cho AI agents, bao gồm backend FastAPI, web Next.js, desktop Electron, browser extension, plugin Obsidian, MCP server, và evaluation harness.

## Cấu trúc các phần

### Nowing Backend (backend)

- **Loại:** backend
- **Stack:** Python 3.12 / FastAPI
- **Entry:** `/Users/luisphan/Documents/Nowing/nowing_backend/main.py`

### Nowing Web (web)

- **Loại:** web
- **Stack:** Next.js 16 / React 19
- **Entry:** `/Users/luisphan/Documents/Nowing/nowing_web/app/layout.tsx`

### Nowing Browser Extension (browser_extension)

- **Loại:** extension
- **Stack:** Plasmo / React 18
- **Entry:** `/Users/luisphan/Documents/Nowing/nowing_browser_extension/popup.tsx`

### Nowing Desktop (desktop)

- **Loại:** desktop
- **Stack:** Electron 42 / TypeScript
- **Entry:** `/Users/luisphan/Documents/Nowing/nowing_desktop/src/main.ts`

### Nowing Obsidian Plugin (obsidian)

- **Loại:** extension
- **Stack:** TypeScript / esbuild / Obsidian API
- **Entry:** `/Users/luisphan/Documents/Nowing/nowing_obsidian/src/main.ts`

### Nowing MCP Server (mcp)

- **Loại:** backend
- **Stack:** Python 3.11 / MCP SDK / Starlette
- **Entry:** `/Users/luisphan/Documents/Nowing/nowing_mcp/mcp_server/__main__.py`

### Nowing Evals (evals)

- **Loại:** data
- **Stack:** Python 3.12 / CLI
- **Entry:** `/Users/luisphan/Documents/Nowing/nowing_evals/src/nowing_evals/__main__.py`

## Tài liệu chính

### Tổng quan

- [Project Overview](./project-overview.md) – Tóm tắt toàn bộ dự án
- [Source Tree Analysis](./source-tree-analysis.md) – Cây thư mục và thư mục quan trọng
- [Integration Architecture](./integration-architecture.md) – Cách các phần giao tiếp
- [Project Parts Metadata](./project-parts.json) – Cấu trúc machine-readable

### Backend

- [Architecture - Backend](./architecture-backend.md)
- [Development Guide - Backend](./development-guide-backend.md)
- [API Contracts - Backend](./api-contracts-backend.md)
- [Data Models - Backend](./data-models-backend.md)

### Web

- [Architecture - Web](./architecture-web.md)
- [Development Guide - Web](./development-guide-web.md)
- [Component Inventory - Web](./component-inventory-web.md)

### Các phần khác

- [Architecture - Browser Extension](./architecture-browser_extension.md)
- [Development Guide - Browser Extension](./development-guide-browser_extension.md)
- [Component Inventory - Browser Extension](./component-inventory-browser_extension.md)
- [Architecture - Desktop](./architecture-desktop.md)
- [Development Guide - Desktop](./development-guide-desktop.md)
- [Component Inventory - Desktop](./component-inventory-desktop.md)
- [Architecture - Obsidian](./architecture-obsidian.md)
- [Development Guide - Obsidian](./development-guide-obsidian.md)
- [Component Inventory - Obsidian](./component-inventory-obsidian.md)
- [Architecture - MCP](./architecture-mcp.md)
- [Development Guide - MCP](./development-guide-mcp.md)
- [API Contracts - MCP](./api-contracts-mcp.md)
- [Architecture - Evals](./architecture-evals.md)
- [Development Guide - Evals](./development-guide-evals.md)

## Tài liệu sẵn có trong dự án

- `README.md` – Giới thiệu dự án
- `CONTRIBUTING.md` – Hướng dẫn đóng góp
- `nowing_web/content/docs/` – Fumadocs docs website
- `.github/workflows/` – CI/CD pipelines
- `docs/chinese-llm-setup.md` – Hướng dẫn setup Chinese LLM

## Bắt đầu

### Backend

```bash
cd nowing_backend
uv sync
cp .env.example .env
alembic upgrade head
uv run python main.py --reload
```

### Web

```bash
cd nowing_web
pnpm install
cp .env.example .env.local
pnpm dev
```

## Hướng dẫn cho AI-assisted development

- **Tính năng UI-only:** xem `architecture-web.md`, `component-inventory-web.md`
- **Tính năng API/Backend:** xem `architecture-backend.md`, `api-contracts-backend.md`, `data-models-backend.md`
- **Tính năng full-stack:** xem tất cả architecture + `integration-architecture.md`
- **Thay đổi deployment:** xem `.github/workflows/`, `docker/`, `development-guide-*.md`

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
