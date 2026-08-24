---
baseline_commit: d06d121a0
story_key: 27-1c
epic: epic-27
story: "27.1c"
title: "Web App Container Deploy & Custom CNAME"
status: "in-progress"
---

# Story 27.1c: Web App Container Deploy & Custom CNAME

**Status:** `in-progress` — static publish / host route / Dockerfile / custom-domain endpoint done; missing real Docker build/run, Traefik/Caddy route, and DNS CNAME validation. See `web-builder-27-1-status-audit-2026-08-25.md`.  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Parent Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md" /> — Story 27.1 split container.  
**Related Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> — 27.1a chat-first static publish (done).  
**Prerequisite Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1b-web-app-build-preview-runner.md" /> — build/preview runner.  
**Sibling Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1d-web-app-mark-tool-ast-mutator.md" /> — Mark Tool.  
**Priority:** P1  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, Story 27.1; FR-93)  
**Related PRD:** FR-93 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> §4.10  
**Related Architecture:** AD-113 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md" /> §8  

## Story

As a Nowing user,  
I want to publish my validated web app to a public container with one click and optionally use my own custom domain,  
So that it is reachable at `https://[app].apps.nowing.net` or my CNAME.

## Scope

This story owns **1-click container deploy, dynamic wildcard routing on `*.apps.nowing.net`, and custom CNAME support**. It assumes the project has already been generated and built/previewed by Story 27.1b.

## [BUILT] vs [GAP]

### [BUILT] — existing patterns to reuse

- **Workspace app registry.** Created by Story 27.1b (`WorkspaceApp` table with `workspace_id`, `slug`, `status`, `preview_url`).
- **TokenUsage & cost tracking** (`app/services/token_tracking_service.py`). `usage_type` is `String(50)`, `cost_micros` is `BigInteger`.
- **Deliverables routes pattern** (`app/routes/reports_routes.py`, `app/routes/image_generation_routes.py`). CRUD route pattern for `web_builder_routes.py` publish/CNAME endpoints.
- **Caddy reverse proxy** (`docker/proxy/Caddyfile`). Caddy supports wildcard certificate and dynamic reverse proxy; used as self-host/dev fallback.

### [GAP] — new code required

1. **Deploy service.** `WebAppDeployService` builds a Docker image, starts a container, registers a Traefik/Caddy route.
2. **Dynamic host routing.** Traefik Docker labels or Caddy file provider for `*.apps.nowing.net`; custom CNAME validation and route.
3. **DNS/CNAME validation.** Validate that a custom domain points to the ingress before registering the route.

## Acceptance Criteria

### AC-1: 1-Click Publish to `*.apps.nowing.net`

- **Given** a generated app passes local build/preview validation (Story 27.1b),  
  **When** the user clicks `Publish`,  
  **Then** `WebAppDeployService` builds a Docker image from `docker/web-app.Dockerfile`, starts a container, and registers a Caddy/Traefik route so the app is reachable at `https://{app-slug}.apps.nowing.net` with a valid SSL certificate.

- **Given** two workspaces create apps with the same slug,  
  **When** the second app is published,  
  **Then** the slug is disambiguated (`{slug}-{short_id}`) globally and the user is notified; no domain collision.

- **Given** the app build fails or the container exits unhealthy,  
  **When** the deploy step runs,  
  **Then** it returns `status="deploy_failed"`, preserves build/container logs, and does not register a public route.

### AC-2: Custom CNAME / Domain Connect

- **Given** a user wants a custom domain,  
  **When** they configure a CNAME pointing to `cname-ingress.apps.nowing.net` (or the system ingress),  
  **Then** `WebAppDeployService` validates the CNAME and adds a dynamic host route to Caddy/Traefik mapping the custom domain to the app container.

- **Given** the CNAME does not resolve or the domain is already in use by another workspace,  
  **When** the user saves the custom domain,  
  **Then** the API rejects with `409 Conflict` / `422 Unprocessable` and a clear message.

### AC-3: Workspace-Scoped App Registry & Deploy Cost

- **Given** an app is published,  
  **When** the deploy step completes,  
  **Then** the `WorkspaceApp` row is updated to `status="published"` with `public_url` and `custom_domain`.

- **Given** an app is published,  
  **When** the deploy step completes,  
  **Then** `TokenUsage` with `usage_type="web_builder_deploy"` and `cost_micros` is recorded.

### AC-4: Feature Gating

- **Given** a workspace is on the `free` plan and `web_builder_enabled` is `False`,  
  **When** the user tries to publish or set a custom CNAME,  
  **Then** it returns `403 Forbidden` with an upgrade prompt.

## Validation

- **Unit tests:** `tests/unit/services/web_builder/test_deploy_service.py` — Caddy config rendering, domain collision.
- **Integration tests:** `tests/integration/services/web_builder/test_deploy_service.py` — publish/CNAME flow using mocked Docker build.
- **Frontend typecheck:** `cd nowing_web && pnpm tsc --noEmit`.
- **Ruff / format:** `ruff check app/services/web_builder app/routes/web_builder_routes.py`.

## Tags

AD-113, FR-93, web-builder, deploy, docker, traefik, caddy, wildcard-domain, custom-cname, container

## Architecture Compliance

- **AD-113 — Full-Stack Web App Builder & Instant Hosting:**
  - Deploy 1-click automatically to `https://[app-name].apps.nowing.net` with HTTPS and dynamic routing.
  - **Production target: Traefik (Dokploy).** Each web app is a container/service registered with Traefik via Docker labels and connected to `dokploy-network`.
  - **Self-host / local dev fallback: Caddy 2 file-provider** (`docker/proxy/web-apps.Caddyfile`).
  - Wildcard certificate `*.apps.nowing.net` requires DNS `A/AAAA` record and Traefik/Dokploy TLS provision.
  - Backend may mount Docker socket to build/run web app containers (PO confirmed).
- **NFR-2 (Security):** validate CNAME, no `eval` in container, sandbox file writes.
- **NFR-3 (Observability):** deploy step logs and writes `TokenUsage`.

## File Structure Requirements

**NEW files (expected):**
- `nowing_backend/app/services/web_builder/deploy_service.py`
- `nowing_backend/docker/web-app.Dockerfile` (multi-stage Next.js standalone)
- `nowing_backend/app/services/web_builder/schemas.py` (`WebAppDeployInput` / `WebAppDeployOutput`)
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py`

**UPDATE files:**
- `nowing_backend/app/routes/web_builder_routes.py` — add publish, custom-domain endpoints.
- `nowing_backend/app/services/web_builder/schemas.py` — `WorkspaceApp` deploy fields.
- `nowing_backend/docker/proxy/Caddyfile` — wildcard `*.apps.nowing.net` + dynamic import.
- `docker/docker-compose.yml` — volume `web_apps`, network `dokploy-network` (if Dokploy/Traefik).

## External Dependency Gating

- **Reverse proxy target resolved: Traefik (Dokploy).** Caddy 2 in repo is fallback.
- **Docker socket / build capabilities:** backend container mounts Docker socket (PO confirm).
- **Wildcard DNS `*.apps.nowing.net`** must point to Dokploy/Traefik ingress.
- **Node runtime:** build Next.js requires Node.js in backend container or sandbox.
