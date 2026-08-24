---
baseline_commit: d06d121a0
story_key: 27-1
epic: epic-27
story: "27.1"
title: "Full-Stack Web App Builder, 1-Click Hosting *.apps.nowing.net & Design View Mark Tool"
status: "in-progress"
---

# Story 27.1: Full-Stack Web App Builder, 1-Click Hosting `*.apps.nowing.net` & Design View Mark Tool

**Status:** `in-progress` (parent/tracking story — 27.1a `done`; 27.1b/c/d `in-progress` per audit 2026-08-25)  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Priority:** P1  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, Story 27.1; FR-93, FR-94)  
**Related PRD:** FR-93, FR-94 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> §4.10  
**Related Architecture:** AD-113, AD-114 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md" /> §8  
**PRD Amendment:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md" />  

> **Resolved by architect (Winston) + PO confirmation:** Production Dokploy/Nowing runs **Traefik**. Story 27.1 targets **Traefik for v1 production**. Caddy 2 in `docker/docker-compose.yml` is **self-host / local dev fallback**. Deployment uses **Traefik Docker provider** (labels or file provider) to register `*.apps.nowing.net` and custom CNAME.

## Story

As a Nowing user,  
I want to describe a web app in natural language and have the agent generate, preview, and deploy it to `https://[app].apps.nowing.net` (or a custom domain),  
So that I can ship a working full-stack application without writing code.

## Scope

This parent story tracks the full-stack web app builder. It was split because the original file bundled four subsystems into one oversized story. Implementation is now divided into child stories.

## Child Stories

| Child | Status | Scope |
|---|---|---|
| <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> | `done` | Chat-first sales/marketing MVP; static publish via backend wildcard route (Option A). |
| <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1b-web-app-build-preview-runner.md" /> | `in-progress` | Generation/validation/registry/cost done; missing real `npm install` + `next build`/preview runner. See audit. |
| <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1c-web-app-container-deploy-cname.md" /> | `in-progress` | Static publish / host route / Dockerfile / custom-domain endpoint done; missing real Docker build/run, Traefik/Caddy route, and DNS CNAME validation. See audit. |
| <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1d-web-app-mark-tool-ast-mutator.md" /> | `in-progress` | UI/iframe postMessage/regex-based patch endpoint done; missing real AST parser and `web_builder_mark` TokenUsage. See audit. |

## Acceptance Criteria (aggregated from child stories)

- **AC-1 (27.1b):** Natural-language prompt generates a runnable Next.js + Tailwind project into `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/` and returns a `preview_url`.
- **AC-2 (27.1b):** Local build/preview runner executes `npm install` + `next build` and returns a workspace-scoped preview URL; build failures return `status="build_failed"`.
- **AC-3 (27.1c):** 1-click publish builds a Docker image, starts a container, and registers a route at `https://{app-slug}.apps.nowing.net` with valid SSL; slug collisions are disambiguated.
- **AC-4 (27.1c):** Custom CNAME pointing to the system ingress is validated and mapped to the app container; invalid/unresolvable CNAME returns `409`/`422`.
- **AC-5 (27.1b/27.1c):** `WorkspaceApp` registry tracks `workspace_id`, `slug`, `status`, `preview_url`, `public_url`, `custom_domain`; each step records `TokenUsage` (`web_builder_generate`, `web_builder_build`, `web_builder_deploy`).
- **AC-6 (27.1d):** Mark Tool captures an element bounding box and selector in the preview iframe and maps it to the generated JSX AST; unresolvable selectors return `status="mark_unresolvable"`.
- **AC-7 (27.1b/27.1c/27.1d):** Workspace feature gating returns `403 Forbidden` with an upgrade prompt when `web_builder_enabled` is `False`.

## Validation

- **Unit tests:** `tests/unit/services/web_builder/test_web_builder_service.py`, `test_build_runner.py`, `test_mark_tool.py`, `test_deploy_service.py`.
- **Integration tests:** `tests/integration/routes/test_web_builder_routes.py`, `tests/integration/services/web_builder/test_deploy_service.py`.
- **Frontend typecheck:** `cd nowing_web && pnpm tsc --noEmit`.
- **Ruff / format:** `ruff check app/services/web_builder app/routes/web_builder_routes.py app/capabilities/web_builder tests/unit/services/web_builder tests/integration/routes/test_web_builder_routes.py`.

## Tags

AD-113, AD-114, FR-93, FR-94, web-builder, nextjs, tailwind, caddy, traefik, mark-tool, ast-mutation, deploy, wildcard-domain, workspace-app

## Architecture Compliance

- **AD-113 — Full-Stack Web App Builder & Traefik/Caddy Instant Hosting:**
  - Agent generates Next.js/React in `/workspace/web-app`.
  - Deploy 1-click automatically to `https://[app-name].apps.nowing.net` with HTTPS and dynamic routing.
  - **Production target: Traefik (Dokploy).** Each web app is a container/service registered with Traefik via Docker labels and connected to `dokploy-network`.
  - **Self-host / local dev fallback: Caddy 2 file-provider** (`docker/proxy/web-apps.Caddyfile`).
  - Wildcard certificate `*.apps.nowing.net` requires DNS `A/AAAA` record and Traefik/Dokploy TLS provision.
  - Backend may mount Docker socket to build/run web app containers (PO confirmed).
- **AD-114 — Design View Visual "Mark Tool" Canvas AST Mutator:**
  - Iframe preview injects a Bounding Box Selector.
  - When a user marks a UI element, the agent extracts the DOM XPath/CSS and AST-mutates the correct JSX component.
- **NFR-1 (Performance):** build/preview does not block chat turn; deploy may be async.
- **NFR-2 (Security):** file write in sandbox path, no `eval`, sandboxed preview iframe, CNAME validation.
- **NFR-3 (Observability):** each step logs `web_builder_*` and writes `TokenUsage`.

## File Structure Requirements

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
- `nowing_backend/docker/web-app.Dockerfile`
- `nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py`
- `nowing_backend/tests/unit/services/web_builder/test_build_runner.py`
- `nowing_backend/tests/unit/services/web_builder/test_mark_tool.py`
- `nowing_backend/tests/integration/routes/test_web_builder_routes.py`
- `nowing_backend/tests/integration/services/web_builder/test_deploy_service.py`
- `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx`
- `nowing_web/lib/apis/web-builder-api.service.ts`
- `nowing_web/components/web-builder/prompt-input.tsx`
- `nowing_web/components/web-builder/preview-iframe.tsx`
- `nowing_web/components/web-builder/mark-tool-overlay.tsx`

**UPDATE files:**
- `nowing_backend/app/db.py` — add `WorkspaceApp` model.
- `nowing_backend/app/routes/__init__.py` — import `web_builder_routes`.
- `nowing_backend/app/capabilities/core/types.py` — add `WEB_BUILDER_*` billing units.
- `nowing_backend/app/config/__init__.py` — add `WEB_BUILDER_ENABLED`, `WEB_BUILDER_STORAGE_PATH`.
- `docker/docker-compose.yml` — volume `web_apps`, network `dokploy-network` if running Dokploy/Traefik, `web-app` service template.
- `docker/proxy/Caddyfile` (dev/self-host fallback) — wildcard `*.apps.nowing.net` + dynamic import `web-apps.Caddyfile`.

## Previous Story Intelligence

- **Là story đầu tiên của Epic 27**, không có story trước trong epic. Tuy nhiên, **reuse patterns từ các epic khác:**
  - `app/routes/reports_routes.py` / `app/routes/video_presentations_routes.py` — deliverable pattern: route → service → file/URL.
  - `app/services/memory/extraction.py` — workspace-scoped async service, record `TokenUsage`, degrade on failure.
  - `app/services/image_generation/` — workspace-scoped generation service, file output, cost tracking.
  - `app/capabilities/news/entity_search/` — new capability package pattern.

## Challenge Log

This parent story no longer carries detailed ACs; see child stories for detailed edge cases and test plans. Key cross-cutting risks to track:

1. **Slug global uniqueness.** Public subdomains require globally unique slugs; enforce `UNIQUE` on `workspace_apps.slug` and a collision check at publish time.
2. **CNAME validation / HTTPS failure.** CNAME may resolve but TLS cert provisioning can fail; consider `status=cert_pending` or early rejection.
3. **Build artifact disk cleanup.** Generated `node_modules` + `.next` can be hundreds of MB per app; add retention policy and cleanup job.
4. **Preview iframe security.** Generated app must be sandboxed and on a separate origin/subdomain.
5. **Mark Tool selector drift.** After regeneration, selectors break; consider stable `data-nowing-id` attributes or selector versioning.

## References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 27 / Story 27.1]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md` — §4.10 FR-93/FR-94]
- [Source: `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md` — §8 AD-113/AD-114]
- [Source: `nowing_backend/app/services/llm_service.py`]
- [Source: `nowing_backend/app/capabilities/core/types.py`]
- [Source: `nowing_backend/app/db.py` — Workspace, TokenUsage]
- [Source: `docker/docker-compose.yml`]
- [Source: `docker/proxy/Caddyfile`]
