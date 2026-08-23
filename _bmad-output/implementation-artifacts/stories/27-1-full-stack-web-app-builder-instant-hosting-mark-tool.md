---
baseline_commit: d06d121a0
story_key: 27-1
epic: epic-27
story: "27.1"
title: "Full-Stack Web App Builder, 1-Click Hosting *.apps.nowing.net & Design View Mark Tool"
status: "ready-for-dev"
---

# Story 27.1: Full-Stack Web App Builder, 1-Click Hosting `*.apps.nowing.net` & Design View Mark Tool

**Status:** `ready-for-dev`  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Priority:** P1  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, Story 27.1; FR-93)  
**Related PRD:** FR-93, FR-94 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> §4.10  
**Related Architecture:** AD-113, AD-114 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md" /> §8  
**PRD Amendment:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md" />  
**Resolved by architect (Winston) + PO confirmation:** Production Dokploy/Nowing chạy **Traefik**. Story 27.1 vì vậy **target Traefik cho v1 production**. Caddy 2 trong `docker/docker-compose.yml` chỉ là **self-host / local dev fallback**. Deployment cần dùng **Traefik Docker provider** (labels hoặc file provider) để đăng ký `*.apps.nowing.net` và custom CNAME.

> **Scope warning:** `epics.md` đánh dấu Story 27.1 là **"toàn bộ code mới" và "scope lớn nhất trong roadmap"**. Bao gồm 4 sub-system lớn: (1) LLM code generator, (2) build/preview runner, (3) 1-click hosting + custom CNAME, (4) Design View Mark Tool. Nếu sprint không đủ thời gian, ưu tiên sinh project + preview URL trước, deploy và Mark Tool theo sau.

## Story

As a Nowing user,  
I want to describe a web app in natural language and have the agent generate, preview, and deploy it to `https://[app].apps.nowing.net` (hoặc custom domain),  
So that I can ship a working full-stack application without writing code.

## [BUILT] vs [GAP]

### [BUILT] — existing patterns to reuse

- **Workspace model & RBAC** (`app/db.py:1897-2050`). `Workspace` đã có `user_id`, `plan_tier`, `credit_micros_balance`, `api_access_enabled`, `memory_auto_extract_enabled`; dễ dàng thêm `web_builder_enabled` flag. Permission workspace-scoped đã chuẩn hóa qua dependency `get_current_active_user`.
- **TokenUsage & cost tracking** (`app/db.py:1200-1293`, `app/services/token_tracking_service.py`). `usage_type` là `String(50)`, `cost_micros` là `BigInteger`, có `workspace_id` index. Pattern record cost post-hoc quen thuộc.
- **Capability framework** (`app/capabilities/core/`). Đăng ký `Capability` với `input_schema`, `output_schema`, `executor`, `billing_unit` qua `register_capability`. `BillingUnit` là `StrEnum` và cũng là `usage_type`.
- **LLM service** (`app/services/llm_service.py:385-394`). `get_agent_llm(session, workspace_id)` async trả `ChatLiteLLM` cho workspace; dùng cho generator.
- **File storage local** (`FILE_STORAGE_LOCAL_PATH=/app/.local_object_store`, `docker-compose.yml:119,184,196`). Dùng để ghi project Next.js tạm trước khi build/deploy.
- **Deliverables routes pattern** (`app/routes/reports_routes.py`, `app/routes/video_presentations_routes.py`, `app/routes/export_routes.py`). Các route nhận prompt, gọi service, trả URL/file.
- **Caddy reverse proxy** (`docker/proxy/Caddyfile`). Caddy hỗ trợ wildcard certificate (`*.apps.nowing.net`) và dynamic reverse proxy qua `CADDY_ADAPTER_API` hoặc config file mount. Production hiện dùng Caddy, không phải Traefik.
- **Frontend Next.js 16 + React 19** (`nowing_web/app/dashboard/[workspace_id]/...`). Có pattern dashboard page với `[workspace_id]` layout.

### [GAP] — new code required

1. **No web builder module.** Không có `app/services/web_builder/`, `app/capabilities/web_builder/`, hay `app/routes/web_builder_routes.py`.
2. **No project generation engine.** Cần LLM prompt + parser để sinh Next.js + Tailwind project từ description, ghi file vào `/workspace/web-app` (hoặc `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}`).
3. **No build/preview runner.** Cần `next build`/`next dev` trong container hoặc sandbox, expose preview URL.
4. **No deploy service.** Cần Dockerfile template + Caddy/Traefik dynamic config + DNS wildcard flow.
5. **No workspace app registry.** Cần DB table `workspace_apps` lưu `app_id`, `name`, `slug`, `workspace_id`, `status`, `url`, `custom_domain`.
6. **No Mark Tool.** Cần iframe preview + bounding box selector + DOM-to-JSX mapping + AST mutation.
7. **No frontend builder page.** Cần `/dashboard/[workspace_id]/web-builder/` page + prompt input + preview iframe + publish/CNAME UI.

## Acceptance Criteria

### AC-1: LLM Web App Generation

- **Given** a natural-language description of a web app (English or Vietnamese),  
  **When** the user submits it to the builder,  
  **Then** a `WebBuilderService` calls the workspace LLM with a structured prompt and receives a Next.js + Tailwind project specification,  
  **And** the service writes a runnable project into `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/` and returns a `preview_url`.

- **Given** the generated project,  
  **When** it is written to disk,  
  **Then** it contains at minimum `package.json` with `next`, `react`, `react-dom`, `tailwindcss` dependencies, `app/page.tsx`, `app/layout.tsx`, `tailwind.config.ts`, `next.config.js` (standalone output), and `Dockerfile`.

- **Given** the LLM returns malformed or non-JSON output,  
  **When** `WebBuilderService` parses it,  
  **Then** it returns a degraded result with `status="validation_failed"`, `message` explaining the failure, and no files are written.

### AC-2: 1-Click Publish to `*.apps.nowing.net`

- **Given** a generated app passes local validation (`next build` succeeds or `next lint` passes),  
  **When** the user clicks `Publish`,  
  **Then** `WebAppDeployService` builds a Docker image from `docker/web-app.Dockerfile` template, starts a container, and registers a Caddy/Traefik route so the app is reachable at `https://{app-slug}.apps.nowing.net` with a valid SSL certificate.

- **Given** two workspaces create apps with the same slug,  
  **When** the second app is published,  
  **Then** the slug is disambiguated (`{slug}-{short_id}`) and the user is notified; no domain collision.

- **Given** the app build fails or the container exits unhealthy,  
  **When** the deploy step runs,  
  **Then** it returns `status="deploy_failed"`, preserves build logs, and does not register a public route.

### AC-3: Custom CNAME / Domain Connect

- **Given** a user wants a custom domain,  
  **When** they configure a CNAME pointing to `cname-ingress.apps.nowing.net` (hoặc ingress của hệ thống),  
  **Then** `WebAppDeployService` validates the CNAME and adds a dynamic host route to Caddy/Traefik mapping the custom domain to the app container.

- **Given** the CNAME does not resolve or the domain is already in use by another workspace,  
  **When** the user saves the custom domain,  
  **Then** the API rejects with `409 Conflict` / `422 Unprocessable` and a clear message.

### AC-4: Design View Mark Tool

- **Given** the `Mark Tool` is active on a web preview iframe,  
  **When** the user clicks an element,  
  **Then** the frontend captures a bounding box, extracts a stable DOM selector (XPath or CSS selector), and sends `{selector, rect, component_hint}` to the backend.

- **Given** the backend receives a selector,  
  **When** it maps the selector to the generated JSX AST,  
  **Then** it applies a structured patch (text change, style change, or component replacement) to the corresponding JSX file and re-builds the preview.

- **Given** the selector cannot be mapped to a unique JSX node,  
  **When** the backend processes it,  
  **Then** it returns `status="mark_unresolvable"` and does not mutate the project.

### AC-5: Workspace-Scoped App Registry & Cost Observability

- **Given** a published app,  
  **When** it is created,  
  **Then** a `WorkspaceApp` row is written with `workspace_id`, `user_id`, `name`, `slug`, `status`, `preview_url`, `public_url`, `custom_domain`, `created_at`, `updated_at`.

- **Given** an app is published,  
  **When** the build/generate/deploy steps complete,  
  **Then** each step records `TokenUsage` with `usage_type="web_builder_*"` (`web_builder_generate`, `web_builder_build`, `web_builder_deploy`) and `cost_micros` so workspace usage is visible.

- **Given** a workspace is on the `free` plan and `web_builder_enabled` is `False`,  
  **When** the builder is accessed,  
  **Then** it returns `403 Forbidden` with an upgrade prompt (if gating is enabled; default `True` for v1 behind feature flag).

## Validation

- **Unit tests:** `tests/unit/services/web_builder/test_web_builder_service.py` — project generation, validation failure, slug disambiguation.
- **Unit tests:** `tests/unit/services/web_builder/test_mark_tool.py` — DOM selector to JSX AST mapping, unresolvable selector.
- **Integration tests:** `tests/integration/routes/test_web_builder_routes.py` — generate/publish/CNAME flow using mocked Docker build.
- **Integration tests:** `tests/integration/services/web_builder/test_deploy_service.py` — Caddy config rendering, domain collision.
- **Frontend typecheck:** `cd nowing_web && pnpm tsc --noEmit`.
- **Ruff / format:** `ruff check app/services/web_builder app/routes/web_builder_routes.py app/capabilities/web_builder tests/unit/services/web_builder tests/integration/routes/test_web_builder_routes.py`.

## Tags

AD-113, AD-114, FR-93, FR-94, web-builder, nextjs, tailwind, caddy, traefik, mark-tool, ast-mutation, deploy, wildcard-domain, workspace-app

## Tasks / Subtasks

- [ ] **AC-1** Define `WebBuilderService` and project scaffold
  - [ ] Create `app/services/web_builder/__init__.py`, `schemas.py`, `generator.py`, `validator.py`, `project_writer.py`.
  - [ ] Define `WebAppBuildInput` (prompt, language, workspace_id, user_id) and `WebAppBuildOutput` (app_id, status, preview_url, files[], message).
  - [ ] Implement LLM prompt for Next.js + Tailwind JSON spec; parse with Pydantic.
  - [ ] Write project to `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/`.
  - [ ] Add `next.config.js` standalone output and `Dockerfile` template.
  - [ ] Add local validation: `package.json` exists, `page.tsx` exists, `tailwind.config.ts` exists.

- [ ] **AC-2** Implement build, preview, and deploy
  - [ ] Create `app/services/web_builder/builder.py` — run `npm install && next build` in workspace-scoped temp dir.
  - [ ] Create `app/services/web_builder/deploy_service.py` — build container image, assign slug, register Caddy/Traefik route.
  - [ ] Create `docker/web-app.Dockerfile` template (multi-stage, Next.js standalone).
  - [ ] Create `WebAppDeployInput` / `WebAppDeployOutput` schemas.
  - [ ] Implement domain collision check via `workspace_apps.slug` unique per workspace.
  - [ ] Add `WorkspaceApp` DB model and Alembic migration.

- [ ] **AC-3** Custom CNAME support
  - [ ] Add `custom_domain` field to `WorkspaceApp`.
  - [ ] Create DNS/CNAME validation helper.
  - [ ] Add Caddy/Traefik dynamic host route generation.
  - [ ] Add `POST /api/v1/web-builder/apps/{app_id}/custom-domain` route.

- [ ] **AC-4** Design View Mark Tool
  - [ ] Create `app/services/web_builder/mark_tool.py` — selector → AST mapping.
  - [ ] Choose and add JSX parser (`babel` via `@babel/parser` in Python wrapper, or `tsx`/`recast` if Node subprocess; if pure Python, `jscodeshift` not available; simplest v1: Babel AST through a Node child process or `babel-parser` Python port).
  - [ ] Implement `mark_patch` endpoint: `POST /api/v1/web-builder/apps/{app_id}/mark` with `{selector, patch}`.
  - [ ] Implement frontend Mark Tool iframe overlay in `nowing_web`.

- [ ] **AC-5** Capability, routes, and cost tracking
  - [ ] Create `app/capabilities/web_builder/build_app/` with `definition.py`, `executor.py`, `schemas.py`.
  - [ ] Register a `web_builder.build_app` capability with billing unit `WEB_BUILDER_GENERATE` (new) or reuse `WEB_BUILDER_*`.
  - [ ] Create `app/routes/web_builder_routes.py` (generate, publish, list, get, delete, mark, custom-domain).
  - [ ] Wire routes in `app/routes/__init__.py` and `app/app.py`.
  - [ ] Record `TokenUsage` for generate/build/deploy steps.

- [ ] **Frontend**
  - [ ] Create `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx`.
  - [ ] Create components: prompt input, app list, preview iframe, publish button, CNAME form, Mark Tool overlay.
  - [ ] Add API service `lib/apis/web-builder-api.service.ts`.

- [ ] **Tests**
  - [ ] Write unit tests for `WebBuilderService`, `DeployService`, `MarkTool`.
  - [ ] Write integration tests for routes with mocked Docker/build.
  - [ ] Update `tests/unit/routes/test_import_registrations.py` or add new canary if needed.

## Dev Notes

### Previous Story Intelligence

- **Là story đầu tiên của Epic 27**, không có story trước trong epic. Tuy nhiên, **reuse patterns từ các epic khác:**
  - `app/routes/reports_routes.py` / `app/routes/video_presentations_routes.py` — deliverable pattern: route → service → file/URL.
  - `app/services/memory/extraction.py` — workspace-scoped async service, record `TokenUsage`, degrade on failure.
  - `app/services/image_generation/` — workspace-scoped generation service, file output, cost tracking.
  - `app/capabilities/news/entity_search/` — gần đây nhất: new capability package, executor, schema, test pattern.

### Git Intelligence Summary

- **Baseline commit:** `d06d121a0`.
- **Recent pattern:** new capabilities đặt trong `app/capabilities/<domain>/<name>/` với `definition.py` + `executor.py` + `schemas.py` + `__init__.py`; tests unit trong `tests/unit/capabilities/<domain>/` hoặc `tests/unit/services/<domain>/`; routes trong `app/routes/<name>_routes.py`.
- **Frontend pattern:** `nowing_web/app/dashboard/[workspace_id]/<feature>/page.tsx` + `lib/apis/<feature>-api.service.ts` + `components/<feature>/`.

### Technical Requirements

- **Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, LangChain/LiteLLM, Celery (nếu deploy async), Docker, Traefik (production/Dokploy), Caddy 2 (self-host/dev fallback), Next.js 16, React 19, Tailwind CSS v4.
- **Project generation:** Dùng `get_agent_llm(session, workspace_id)` hoặc `get_planner_llm()` để sinh spec. Prompt phải trả về JSON với `files[]` hoặc `description` đủ để ghi disk. **Không dùng `eval` hoặc `exec` trên output LLM.**
- **File writer:** Ghi text files an toàn, validate path nằm trong `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/` (ngăn path traversal).
- **Build runner:** Chạy `npm install` + `next build` trong subprocess. Cân nhắc timeout, sandbox, và resource limit. V1 có thể chạy sync trong request nếu build nhẹ; nếu nặng thì Celery task.
- **Deploy service:** Tạo Docker image từ `docker/web-app.Dockerfile` với `context` là thư mục project.
  - **Production (Traefik/Dokploy):** `WebAppDeployService` khởi chạy app container với Docker labels `traefik.enable=true`, `traefik.http.routers.<slug>.rule=Host(\`<slug>.apps.nowing.net\`)`, `traefik.http.services.<slug>.loadbalancer.server.port=<port>`, và nối vào network `dokploy-network`. Nếu backend không có quyền gọi Docker socket trực tiếp, v1 dùng một `web-apps-router` trung gian hoặc Dokploy compose service.
  - **Self-host/dev (Caddy):** fallback dùng Caddy file-provider (`docker/proxy/web-apps.Caddyfile`).
- **Mark Tool AST:** Vì Python không có parser JSX native mạnh, v1 có thể dùng Node subprocess với `@babel/parser` và `@babel/traverse` để map selector đến JSX node. Cần giữ project `node_modules` để chạy parser, hoặc dùng `npx` tạm thời.

### Architecture Compliance

- **AD-113 — Full-Stack Web App Builder & Traefik/Caddy Instant Hosting (resolved):**
  - Agent sinh Next.js/React trong `/workspace/web-app`.
  - Deploy 1-click tự động lên `https://[app-name].apps.nowing.net` có HTTPS và dynamic routing.
  - **Production target: Traefik (Dokploy).** Mỗi web app là một container/service được đăng ký với Traefik qua Docker labels (ví dụ: `traefik.enable=true`, `traefik.http.routers.<slug>.rule=Host(\`<slug>.apps.nowing.net\`)`) và nối vào `dokploy-network`.
  - **Self-host / local dev fallback: Caddy 2 file-provider** (`docker/proxy/web-apps.Caddyfile`) nếu chạy stack `docker-compose.yml` của repo.
  - Wildcard certificate `*.apps.nowing.net` cần DNS `A/AAAA` record trỏ đến server và Traefik/Dokploy provision TLS (Let's Encrypt hoặc custom resolver).
  - Cần quyết định thêm: backend có quyền mount Docker socket / gọi Docker API trên Dokploy server không? Nếu không, v1 phải dùng một `web-apps-router` service do chúng ta quản lý.
- **AD-114 — Design View Visual "Mark Tool" Canvas AST Mutator:**
  - Iframe preview inject Bounding Box Selector.
  - Khi user khoanh vùng phần tử UI, agent bóc DOM XPath/CSS và AST-mutate chính xác component JSX.
- **NFR-1 (Performance):** build/preview không block chat turn; deploy có thể async. `p95` chưa cần hard bound vì là tính năng nền.
- **NFR-2 (Security):** file write trong sandbox path, no `eval`, CORS chặt cho preview iframe, custom domain validation.
- **NFR-3 (Observability):** mỗi bước log `web_builder_*` và ghi `TokenUsage`.

### File Structure Requirements

**NEW files (expected):**
- `nowing_backend/app/services/web_builder/__init__.py`
- `nowing_backend/app/services/web_builder/schemas.py`
- `nowing_backend/app/services/web_builder/generator.py`
- `nowing_backend/app/services/web_builder/project_writer.py`
- `nowing_backend/app/services/web_builder/validator.py`
- `nowing_backend/app/services/web_builder/builder.py`
- `nowing_backend/app/services/web_builder/deploy_service.py`
- `nowing_backend/app/services/web_builder/mark_tool.py`
- `nowing_backend/app/capabilities/web_builder/build_app/__init__.py`
- `nowing_backend/app/capabilities/web_builder/build_app/definition.py`
- `nowing_backend/app/capabilities/web_builder/build_app/executor.py`
- `nowing_backend/app/capabilities/web_builder/build_app/schemas.py`
- `nowing_backend/app/routes/web_builder_routes.py`
- `nowing_backend/alembic/versions/xxx_add_workspace_apps_table.py`
- `nowing_backend/docker/web-app.Dockerfile` (hoặc `docker/web-app.Dockerfile`)
- `nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py`
- `nowing_backend/tests/unit/services/web_builder/test_mark_tool.py`
- `nowing_backend/tests/integration/routes/test_web_builder_routes.py`
- `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx`
- `nowing_web/lib/apis/web-builder-api.service.ts`
- `nowing_web/components/web-builder/prompt-input.tsx`
- `nowing_web/components/web-builder/preview-iframe.tsx`
- `nowing_web/components/web-builder/mark-tool-overlay.tsx`

**UPDATE files:**
- `nowing_backend/app/db.py` — add `WorkspaceApp` model (hoặc tách file model riêng).
- `nowing_backend/app/routes/__init__.py` — import `web_builder_routes`.
- `nowing_backend/app/app.py` — include router nếu không tự động.
- `nowing_backend/app/capabilities/core/types.py` — add `WEB_BUILDER_*` billing units.
- `nowing_backend/app/config/__init__.py` — add `WEB_BUILDER_ENABLED`, `WEB_BUILDER_STORAGE_PATH` config.
- `docker/docker-compose.yml` — thêm volume `web_apps`, network `dokploy-network` nếu chạy trên Dokploy, và `web-app` service template với Traefik labels (self-host vẫn dùng Caddy overlay).
- `docker/proxy/Caddyfile` (dev/self-host fallback) — wildcard `*.apps.nowing.net` + dynamic import `web-apps.Caddyfile`.
- `docker/web-app.Dockerfile` — Dockerfile template cho generated Next.js app.

**DO NOT create:**
- Không tạo bảng `Apps` global — phải workspace-scoped.
- Không `eval`/`exec` output LLM.
- Không deploy trực tiếp từ generated code chưa qua validation/lint.

### Testing Requirements

- **Unit tests:** `pytest -m unit tests/unit/services/web_builder/`. Mock LLM, filesystem, Docker, Babel parser.
- **Integration tests:** `pytest -m integration tests/integration/routes/test_web_builder_routes.py`. Dùng real Postgres, mock Docker build bằng monkeypatch.
- **Frontend:** `pnpm tsc --noEmit`; `pnpm exec biome check` nếu có Biome.
- **Ruff / format:** chạy trước commit.
- **Target scenarios:**
  - Generate thành công → project hợp lệ.
  - Generate trả malformed → degrade.
  - Publish slug duplicate → disambiguation.
  - Build fail → `deploy_failed`, no public route.
  - CNAME không resolve → 422.
  - Mark Tool selector không map được → `mark_unresolvable`.

### External Dependency Gating

- **Reverse proxy target đã resolve: Traefik (Dokploy).** Production dùng Traefik Docker provider. Caddy 2 trong repo là fallback self-host/dev.
- **Docker socket / build capabilities:** deploy container cần quyền build image và khởi chạy container trên host Dokploy (Docker socket mount hoặc remote builder). Cần xác nhận Dokploy cho phép backend container gọi Docker socket không.
- **Wildcard DNS `*.apps.nowing.net`** phải đã được cấu hình ở DNS provider. Nếu chưa, chỉ test local với `*.localhost` hoặc mock.
- **Node runtime:** build Next.js cần Node.js trong backend container hoặc sandbox. Kiểm tra `Dockerfile` base image đã có Node chưa (nếu không, thêm stage `node:22-alpine`).

### Latest Tech / Web Research

- **Next.js 16 standalone output** là best practice cho container deployment (`output: 'standalone'` trong `next.config.js`), giảm image size và tự host server.
- **Tailwind CSS v4** đang ra mắt; nếu dùng v4 thì config file có thể khác v3. Cân nhắc pin `tailwindcss@^3.4` trong v1 để ổn định.
- **Traefik Docker provider** là cách Dokploy đăng ký route. Dynamic routing bằng cách thêm Docker labels khi khởi chạy container (quy tắc `Host`/`HostRegexp`) hoặc ghi file `traefik/dynamic/web-apps.yml` nếu có quyền truy cập Traefik config trên server.
- **Caddy 2 wildcard certificates** hỗ trợ `*.example.com` qua ACME + DNS challenge. **Dùng làm fallback self-host/dev** với `docker/proxy/web-apps.Caddyfile`.
- **JSX AST mutation in Python:** không có thư viện mạnh. V1 nên dùng Node subprocess với `@babel/parser` + `@babel/generator` + `@babel/traverse` + `@babel/types`.

### Project Context Reference

- Nowing quality pipeline: `_bmad/custom/nowing-quality-pipeline.md`.
- Story này là P1, nhưng scope lớn nhất roadmap — khuyến nghị chạy `bmad-grill-me` trước khi dev để quyết định split hoặc POC.

## Story Completion Status

- **Status:** `ready-for-dev` (re-validated 2026-08-25: added comprehensive architecture, BDD acceptance criteria, file structure, testing requirements, and AD-113/Caddy conflict note).
- **Validation note:** Story file đã được mở rộng với full dev context, previous story intelligence, technical requirements, and references.
- **Open blocker / decision:** AD-113 names Traefik but production Docker stack uses Caddy 2. Resolve reverse-proxy target before implementation.

## Dev Agent Record

### Agent Model Used

SWE-1.7 Max

### Debug Log References

### Completion Notes List

### File List

- `_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md`

## Challenge Log (grill-me)

### Q1 — Already implemented?

- **No dedicated web builder, deploy, or Mark Tool found.** Codebase search (`vibervn-context-engine` + grep) found no `app/services/web_builder/`, `app/routes/web_builder_routes.py`, `mark_tool`, JSX AST mutation, or `*.apps.nowing.net` deployment code.
- **Close relatives to REUSE (not duplicate):**
  - `app/routes/image_generation_routes.py` — CRUD deliverable route pattern; reuse for `web_builder_routes.py`.
  - `app/routes/reports_routes.py` / `app/routes/video_presentations_routes.py` — prompt → service → file/URL deliverable pattern; reuse.
  - `app/services/billable_calls.py` `billable_call` context manager — reuse for cost reservation/finalization around the generate LLM call.
  - `app/agents/video_presentation/nodes.py:244-265` — `asyncio.create_subprocess_exec` pattern for `ffprobe`; reuse for `npm install && next build`.
  - `app/capabilities/core/` — capability registration pattern; reuse for `web_builder.build_app`.
- **Verdict:** Safe to build new `app/services/web_builder/` and `app/capabilities/web_builder/`; reuse existing route/billing/subprocess patterns.

### Q2 — Simpler alternative?

- **Critical finding:** The requested behavior (full-stack web app builder + deploy + Mark Tool) is greenfield in this codebase. No existing helper satisfies the ACs.
- **Reusable primitives that reduce scope:**
  1. **Cost tracking** → `billable_call` (`app/services/billable_calls.py:217`) wraps the generate LLM call, reserve/finalize credit, and record `TokenUsage`. Do not invent a new billing lifecycle.
  2. **File writes** → `pathlib.Path` + `Path.is_relative_to` for safe workspace-scoped writes. No need for a new `safe_file` util unless used elsewhere.
  3. **Subprocess build** → `asyncio.create_subprocess_exec` + timeout. Do not pull in a build runner library.
  4. **Custom domain/DNS** → no existing helper; implement minimal DNS-over-HTTPS or `socket.gethostbyname` validation.
- **Possible v1 MVP scope reductions (if time-bound):**
  1. Generate + preview only; deploy manual in v1.1.
  2. Deploy to `https://apps.nowing.net/{workspace-id}/{slug}` path instead of `*.apps.nowing.net` subdomain (avoids wildcard DNS/TLS).
  3. Mark Tool v1 supports text edits only; layout/style mutation v1.2.
- **Money/billing risk:** A new `BillingUnit.WEB_BUILDER_GENERATE` (or reuse `WEB_BUILDER_*`) must record `TokenUsage` once per step, not double-charge. The `billable_call` reserve/finalize lifecycle already handles reserve/finalize.
- **Verdict:** Proceed with full scope; reuse `billable_call` and existing route patterns. Defer to v1.1 only if architect/PM decides after seeing POC.

### Q3 — Edge cases spec misses (Pattern 3)

1. **Slug global uniqueness.** AC-2 disambiguates per workspace but `*.apps.nowing.net` requires globally unique slug. Need `UNIQUE` on `workspace_apps.slug` and a collision check.
2. **CNAME validation / HTTPS failure.** CNAME may resolve but TLS cert provisioning can fail or take minutes. Need `status=cert_pending` and retry, or reject early.
3. **Build artifact disk cleanup.** Generated `node_modules` + `.next` can be hundreds of MB per app. Need retention policy and cleanup job.
4. **Preview iframe security.** Generated app can run arbitrary JS. Iframe must `sandbox="allow-scripts allow-same-origin"` and use separate subdomain/origin to avoid SameSite/cookie issues.
5. **Mark Tool selector drift.** After regeneration, component tree changes; stored selectors break. Need stable `data-nowing-id` attribute or selector versioning.
6. **Empty / malformed prompt.** Blank prompt, only whitespace, or prompt > model context length must return `422`/degraded.
7. **LLM output not valid project.** JSON missing required files, or non-JSON. Need validation and no disk write.
8. **Concurrent builds for same app.** Two publish clicks in quick succession must not create two containers/routes.
9. **Workspace deletion / app orphan cleanup.** Deleting a workspace should delete `WorkspaceApp` rows and stop running containers.
10. **Free plan gating.** `web_builder_enabled` default and plan-tier gate not in current `Workspace` schema; needs decision.

### Q4 — Failure modes unspecified (Pattern 2, 4)

| Dependency / Failure | Behavior when it fails | Spec answer (must add to ACs/tests) |
|---|---|---|
| `get_agent_llm(session, workspace_id)` returns `None` | Cannot generate; return `503` or degrade with `model_unavailable`. | Add AC: degrade with `status=model_unavailable` and no charge. |
| LLM call exceeds timeout | Cancel call, return `status=timeout`, do not write files, do not charge (or reserve only). | Add to `billable_call` timeout handling. |
| `npm install` fails (network/registry) | Build fails; return `status=build_failed` with npm logs; do not register public URL. | AC-2 already covers build fail. |
| `next build` fails (syntax/type error) | Same as above; preserve build output for debugging. | Add test for `next build` failure. |
| Docker socket unavailable / build permission denied | Cannot deploy; return `503` or `500`. | Add `deploy_failed` with `reason=docker_unavailable`. |
| Traefik/Caddy admin API or Docker socket unreachable | Cannot publish route; return `503`; do not mark `status=published`. | Add retry + failure. |
| Redis down (if rate-limit or lock used) | Build/publish must still work or fail gracefully (in-memory fallback). | Document `RedisDown` behavior. |
| Postgres `workspace_apps.slug` unique constraint violation | Race on global slug; retry with new slug or return `409`. | Add global slug collision AC. |
| Custom CNAME points to wrong IP | Reject with `422` after DNS check. | Add CNAME validation AC. |
| User cancels build/publish mid-flight | Need idempotency key and cleanup. | Add `publish_id`/`build_id` idempotency. |
| Disk full during `npm install` | Build fails; log `disk_full`; do not retry indefinitely. | Add failure mode test. |
| Generated app contains `eval` or unsafe code | `npm audit`/`next lint` should catch; if not, container still executes. Need sandbox. | Add security scan or use restricted container. |

### Triage

| Finding | Severity | Action |
|---|---|---|
| Q1: No duplicate logic found; reuse helpers | — | Clean |
| Q2: Reuse `billable_call`, route patterns, `asyncio.subprocess` | — | Continue; add to dev notes |
| Q3: Slug global uniqueness, iframe security, disk cleanup | Non-critical | Continue; add test cases to test-first-atdd |
| Q4: Model unavailability, Docker/Caddy API down, CNAME failure, disk full | Non-critical | Continue; add `deploy_failed` reason codes and degraded responses |
| **Open AD-113/Caddy vs Traefik conflict** | **Critical** | **HALT before deployment code** — resolve with architect/PM whether to use Caddy (existing) or amend AD-113 to Caddy/keep Traefik |

**Verdict:** Proceed to `bmad-test-first-atdd` (Step 2) **only after** resolving the reverse-proxy target decision and adding the missing edge/failure cases to the test skeleton.

## References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 27 / Story 27.1]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — §4.10 FR-93/FR-94]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` — §8 AD-113/AD-114]
- [Source: `nowing_backend/app/services/llm_service.py`]
- [Source: `nowing_backend/app/capabilities/core/types.py`]
- [Source: `nowing_backend/app/db.py` — Workspace, TokenUsage, SearchSourceConnector]
- [Source: `docker/docker-compose.yml`]
- [Source: `docker/proxy/Caddyfile`]
