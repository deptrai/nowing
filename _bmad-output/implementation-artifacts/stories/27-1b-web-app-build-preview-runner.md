---
baseline_commit: d06d121a0
story_key: 27-1b
epic: epic-27
story: "27.1b"
title: "Web App Build & Preview Runner"
status: "in-progress"
---

# Story 27.1b: Web App Build & Preview Runner

**Status:** `in-progress` — generation/validation/registry/cost done; missing real `npm install` + `next build`/preview runner. See `web-builder-27-1-status-audit-2026-08-25.md`.  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Parent Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md" /> — Story 27.1 split container.  
**Related Story (MVP):** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> — 27.1a chat-first static publish (done).  
**Sibling Stories:** 27.1c (container deploy + CNAME), 27.1d (Mark Tool).  
**Priority:** P1  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, Story 27.1; FR-93)  
**Related PRD:** FR-93 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> §4.10  
**Related Architecture:** AD-113 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md" /> §8  

## Story

As a Nowing user,  
I want to describe a web app in natural language and have the agent generate a runnable Next.js + Tailwind project,  
So that I can preview it locally at a workspace-scoped preview URL before publishing.

## Scope

This story owns the **generate → validate → build → preview** slice of the full-stack web app builder. It does **not** own container deploy, custom CNAME, or the Mark Tool (27.1c/27.1d).

## [BUILT] vs [GAP]

### [BUILT] — existing patterns to reuse

- **Workspace model & RBAC** (`app/db.py:1897-2050`). `Workspace` already has `user_id`, `plan_tier`, `credit_micros_balance`, `api_access_enabled`, `memory_auto_extract_enabled`; easy to add `web_builder_enabled` flag.
- **TokenUsage & cost tracking** (`app/db.py:1200-1293`, `app/services/token_tracking_service.py`). `usage_type` is `String(50)`, `cost_micros` is `BigInteger`, with `workspace_id` index.
- **Capability framework** (`app/capabilities/core/`). Register `Capability` with `input_schema`, `output_schema`, `executor`, `billing_unit`.
- **LLM service** (`app/services/llm_service.py:385-394`). `get_agent_llm(session, workspace_id)` async returns `ChatLiteLLM` for workspace.
- **File storage local** (`FILE_STORAGE_LOCAL_PATH=/app/.local_object_store`, `docker-compose.yml:119,184,196`). Used to write generated project files before build.
- **Deliverables routes pattern** (`app/routes/reports_routes.py`, `app/routes/video_presentations_routes.py`). Prompt → service → URL/file.
- **Frontend Next.js 16 + React 19** (`nowing_web/app/dashboard/[workspace_id]/...`). Dashboard page pattern with `[workspace_id]` layout.

### [GAP] — new code required

1. **Web builder module.** No `app/services/web_builder/` or `app/routes/web_builder_routes.py`.
2. **Project generation engine.** LLM prompt + parser to generate Next.js + Tailwind project, write to `/workspace/web-app` (`FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/`).
3. **Build/preview runner.** Run `npm install` + `next build` / `next dev` and expose a preview URL.
4. **Workspace app registry.** DB table `workspace_apps` to store `app_id`, `name`, `slug`, `workspace_id`, `status`, `preview_url`.

## Acceptance Criteria

### AC-1: LLM Web App Generation

- **Given** a natural-language description of a web app (English or Vietnamese),  
  **When** the user submits it to the builder,  
  **Then** `WebBuilderService` calls the workspace LLM with a structured prompt and receives a Next.js + Tailwind project specification,  
  **And** the service writes a runnable project into `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/` and returns a `preview_url`.

- **Given** the generated project,  
  **When** it is written to disk,  
  **Then** it contains at minimum `package.json` with `next`, `react`, `react-dom`, `tailwindcss` dependencies, `app/page.tsx`, `app/layout.tsx`, `tailwind.config.ts`, `next.config.js` (standalone output), and `Dockerfile`.

- **Given** the LLM returns malformed or non-JSON output,  
  **When** `WebBuilderService` parses it,  
  **Then** it returns a degraded result with `status="validation_failed"`, `message` explaining the failure, and no files are written.

### AC-2: Build & Preview Runner

- **Given** a generated project in `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/`,  
  **When** `BuilderService` runs `npm install` followed by `next build` (or `next dev` for preview),  
  **Then** build output and logs are preserved, and a workspace-scoped `preview_url` is returned.

- **Given** the build succeeds,  
  **When** the preview is requested,  
  **Then** the built app is served at the preview URL and loads without errors.

- **Given** the build fails (syntax, type error, or missing dependency),  
  **When** `BuilderService` finishes,  
  **Then** it returns `status="build_failed"`, preserves build logs, and does not return a public preview URL.

- **Given** two workspaces create apps with the same intended slug,  
  **When** the second app is generated,  
  **Then** the slug is disambiguated (`{slug}-{short_id}`) within the workspace and the user is notified; no workspace-scoped slug collision.

### AC-3: Workspace-Scoped App Registry & Cost Observability

- **Given** a generated app,  
  **When** it is created,  
  **Then** a `WorkspaceApp` row is written with `workspace_id`, `user_id`, `name`, `slug`, `status="generated"`, `preview_url`, `created_at`, `updated_at`.

- **Given** an app is generated or built,  
  **When** the generate/build steps complete,  
  **Then** each step records `TokenUsage` with `usage_type="web_builder_generate"` / `"web_builder_build"` and `cost_micros` so workspace usage is visible.

### AC-4: Workspace Feature Gating

- **Given** a workspace is on the `free` plan and `web_builder_enabled` is `False`,  
  **When** the builder is accessed,  
  **Then** it returns `403 Forbidden` with an upgrade prompt (if gating is enabled; default `True` for v1 behind feature flag).

## Validation

- **Unit tests:** `tests/unit/services/web_builder/test_web_builder_service.py` — project generation, validation failure, slug disambiguation.
- **Unit tests:** `tests/unit/services/web_builder/test_build_runner.py` — build success/failure, preview URL generation.
- **Integration tests:** `tests/integration/routes/test_web_builder_routes.py` — generate → preview flow with mocked build.
- **Frontend typecheck:** `cd nowing_web && pnpm tsc --noEmit`.
- **Ruff / format:** `ruff check app/services/web_builder app/routes/web_builder_routes.py app/capabilities/web_builder tests/unit/services/web_builder`.

## Tags

AD-113, FR-93, web-builder, nextjs, tailwind, build-runner, preview, workspace-app

## Architecture Compliance

- **AD-113 — Full-Stack Web App Builder & Instant Hosting:**
  - Agent generates Next.js/React in `/workspace/web-app`.
  - Preview is workspace-scoped and served before any public deploy.
  - Build runner is separate from deploy service so failures can be debugged before containerization.
- **NFR-1 (Performance):** build/preview does not block chat turn; use async subprocess with timeout.
- **NFR-2 (Security):** file write in sandbox path, no `eval`/`exec`, validate path with `Path.is_relative_to`.
- **NFR-3 (Observability):** each step logs `web_builder_*` and writes `TokenUsage`.

## File Structure Requirements

**NEW files (expected):**
- `nowing_backend/app/services/web_builder/__init__.py`
- `nowing_backend/app/services/web_builder/schemas.py`
- `nowing_backend/app/services/web_builder/generator.py`
- `nowing_backend/app/services/web_builder/project_writer.py`
- `nowing_backend/app/services/web_builder/validator.py`
- `nowing_backend/app/services/web_builder/builder.py`
- `nowing_backend/app/capabilities/web_builder/build_app/__init__.py`
- `nowing_backend/app/capabilities/web_builder/build_app/definition.py`
- `nowing_backend/app/capabilities/web_builder/build_app/executor.py`
- `nowing_backend/app/capabilities/web_builder/build_app/schemas.py`
- `nowing_backend/app/routes/web_builder_routes.py` (generate, list, get, preview endpoints)
- `nowing_backend/alembic/versions/xxx_add_workspace_apps_table.py`
- `nowing_backend/docker/web-app.Dockerfile` (shared template; build/preview also validates it)
- `nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py`
- `nowing_backend/tests/unit/services/web_builder/test_build_runner.py`
- `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx`
- `nowing_web/lib/apis/web-builder-api.service.ts`
- `nowing_web/components/web-builder/prompt-input.tsx`
- `nowing_web/components/web-builder/preview-iframe.tsx`

**UPDATE files:**
- `nowing_backend/app/db.py` — add `WorkspaceApp` model.
- `nowing_backend/app/routes/__init__.py` — import `web_builder_routes`.
- `nowing_backend/app/capabilities/core/types.py` — add `WEB_BUILDER_*` billing units.
- `nowing_backend/app/config/__init__.py` — add `WEB_BUILDER_ENABLED`, `WEB_BUILDER_STORAGE_PATH`.
