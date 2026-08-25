---
baseline_commit: 4fe46956f
story_key: 27-1c
epic: epic-27
story: "27.1c"
title: "Web App Container Deploy & Custom CNAME"
status: "done"
---

# Story 27.1c: Web App Container Deploy & Custom CNAME

**Status:** `done` — Docker container lifecycle + dynamic Traefik/Caddy route + Custom CNAME DNS verification + host_router custom domain routing + bmad-code-review patch findings (2026-08-26) đã hoàn thành và kiểm thử 100% GREEN.  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Parent Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md" /> — Story 27.1 split container.  
**Related Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> — 27.1a chat-first static publish (done).  
**Prerequisite Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1b-web-app-build-preview-runner.md" /> — build/preview runner (done).  
**Sibling Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1d-web-app-mark-tool-ast-mutator.md" /> — Mark Tool.  
**Priority:** P1  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, Story 27.1; FR-93)  
**Related PRD:** FR-93 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> §4.10  
**Related Architecture:** AD-113, AD-113a in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md" /> §8  

## Story

As a Nowing user,  
I want to publish my validated web app to a public container with one click and optionally use my own custom domain,  
So that it is reachable at `https://[app].apps.nowing.net` or my CNAME.

## Scope

This story owns **1-click container deploy, dynamic wildcard routing on `*.apps.nowing.net`, and custom CNAME support**. It assumes the project has already been generated and built/previewed by Story 27.1b.  

**Static HTML snapshot publish is already working** (27.1a/27.1b fallback). The goal of 27.1c is to **upgrade to real per-app Docker containers + ingress routing**, while keeping the static snapshot path available behind a feature flag or deploy-mode switch.

## [BUILT] vs [GAP]

### [BUILT] — verified in current code

- **Workspace app registry.** `WorkspaceApp` table (`app/db.py:6559`) có đầy đủ `workspace_id`, `slug`, `status`, `preview_url`, `public_url`, `custom_domain`, `custom_domain_status`, `container_id`, `port`, `storage_path`.
- **Builder service.** `app/services/web_builder/builder.py` đã chạy `npm install --ignore-scripts` + `next build`, output `.next/standalone` + `.next/static`, ghi `build.log`, Redis per-app lock, concurrency + timeout guard.
- **Static deploy service.** `app/services/web_builder/deploy_service.py:deploy_app()` hiện publish **static HTML snapshot** vào `WEB_BUILDER_PUBLIC_APPS_PATH/{slug}/index.html`, set `status="published"`, `public_url`, `slug`, và ghi `TokenUsage(usage_type="web_builder_deploy", cost_micros=WEB_BUILDER_DEPLOY_COST_MICROS)` (mặc định `0`). Đây là fallback của 27.1a/27.1b.
- **CNAME DNS validation.** `WebAppDeployService.verify_and_bind_custom_domain()` (`deploy_service.py:273`) đã validate FQDN, kiểm tra collision cross-workspace, và verify DNS CNAME record trỏ về `CNAME_INGRESS_HOST` bằng `dnspython`.
  - ⚠️ **Bug đã biết:** hàm chỉ gọi `await session.flush()` mà không `commit`. Nếu route không commit thì `custom_domain` không persist.
- **Host route for `*.apps.nowing.net`.** `app/app.py` đã mount `host_router` qua `starlette.routing.Host(f"{{subdomain}}.{config.HOSTING_BASE_DOMAIN}", ...)` (commit `3083ab353`). Nó serve static snapshot `index.html` và `/_next/static/{path:path}`.
- **Dockerfile.** `docker/web-app.Dockerfile` tồn tại: multi-stage Node 20 Alpine, `npm install --ignore-scripts`, `npm run build`, standalone runner port 3000.
- **Config.** `app/config/__init__.py:1807` có `HOSTING_BASE_DOMAIN`, `CNAME_INGRESS_HOST`, `WEB_BUILDER_PUBLIC_APPS_PATH`, `WEB_BUILDER_DEPLOY_COST_MICROS`, `WEB_BUILDER_DOCKER_SANDBOX_ENABLED`.

### [GAP] — new code required

1. **Real Docker container deploy lifecycle.**
   - Build image từ `docker/web-app.Dockerfile` (hoặc Dockerfile mới reuse `.next/standalone` đã build để tránh build 2 lần).
   - Run container với port được cấp phát động hoặc port workspace-scoped.
   - Ghi `container_id` và `port` vào `WorkspaceApp`.
   - Stop/remove container cũ khi re-deploy hoặc khi deploy fail.
   - Healthcheck container trước khi mark `published`.
   - Khi fail: set `status="deploy_failed"`, giữ build/container logs, không register public route.

2. **Ingress route registration.**
   - **Production (Dokploy/Traefik):** container được chạy với Docker labels (hoặc file provider) để Traefik route `Host(`{slug}.apps.nowing.net`)` và `Host(`{custom_domain}`) về container trên `dokploy-network`.
   - **Self-host/dev (Caddy 2):** backend ghi dynamic snippet vào `docker/proxy/web-apps.Caddyfile`; `docker/proxy/Caddyfile` import file này với wildcard block `*.apps.nowing.net`. Reload Caddy (`caddy reload` / SIGHUP) khi snippet thay đổi.
   - **Update `docker/docker-compose.yml`:** thêm `dokploy-network`, volume `web_apps`, mount Docker socket cho backend, template cho per-app containers.

3. **Custom domain ingress.**
   - Sau khi CNAME đúng, `verify_and_bind_custom_domain` phải **commit** thay đổi hoặc route phải commit.
   - Đăng ký route cho `custom_domain` (Traefik label hoặc Caddy snippet) trỏ về container.
   - `host_router` trong `app.py` chỉ match `*.apps.nowing.net`; custom domain tùy ý (`app.mycompany.com`) sẽ không đến được `host_router`. Giải pháp: để Traefik/Caddy là ingress chính; backend `host_router` chỉ là dev fallback.

4. **Cost / TokenUsage.**
   - `WEB_BUILDER_DEPLOY_COST_MICROS` đang mặc định `0`. Story này cần định rõ và cấu hình cost deploy (flat fee hoặc compute-based) cho container.
   - `TokenUsage` phải vẫn được ghi đúng `cost_micros` khi chuyển sang container deploy.

5. **Tests.**
   - `tests/unit/services/web_builder/test_deploy_service.py` — hiện chưa có.
   - `tests/integration/services/web_builder/test_deploy_service.py` — hiện chưa có.

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
  **When** they configure a CNAME pointing to `cname-ingress.apps.nowing.net` (hoặc `CNAME_INGRESS_HOST`),  
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

## Dev Agent Guardrails / Implementation Notes

- **Đừng phá static-snapshot fallback của 27.1a/27.1b.** `WebAppDeployService.deploy_app()` hiện tại đang dùng cho static publish. Hãy thêm `deploy_mode` hoặc env flag `WEB_BUILDER_CONTAINER_DEPLOY_ENABLED` để cả hai path cùng tồn tại trong lúc implement.
- **Docker client:** dùng `docker` Python SDK (`docker.from_env()`) chỉ khi backend có mount Docker socket. Cung cấp mock interface cho test.
- **Image tag:** dùng tên xác định, ví dụ `nowing-web-app-{workspace_id}-{app_id}:{slug}` để tránh collision.
- **Port allocation:** cấp phát động port cao (`30000+`) hoặc dùng Docker `-P` rồi inspect `NetworkSettings.Ports`. Ghi `port` vào `WorkspaceApp.port`.
- **Network:** container phải ở trên `dokploy-network` (Traefik) hoặc bridge network mà Caddy có thể reach.
- **Path traversal:** chỉ build từ `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/`; resolve `storage_path` và kiểm tra suffix như `BuilderService` đã làm.
- **`verify_and_bind_custom_domain` phải commit:** sửa `await session.flush()` thành `await session.commit()` (hoặc route phải commit sau khi gọi service).
- **Caddy dynamic config:** ghi snippet vào `docker/proxy/web-apps.Caddyfile`, sau đó `caddy reload`.
- **Traefik Docker labels (ví dụ):**
  - `traefik.enable=true`
  - `traefik.http.routers.nowing-app-{slug}.rule=Host(`{slug}.apps.nowing.net`) || Host(`{custom_domain}`)`
  - `traefik.http.routers.nowing-app-{slug}.tls.certresolver=default`
  - `traefik.http.services.nowing-app-{slug}.loadbalancer.server.port={port}`
  - network `dokploy-network`

## Architecture Compliance

- **AD-113 — Full-Stack Web App Builder & Instant Hosting:** deploy 1-click tự động lên `https://[app-name].apps.nowing.net` với HTTPS và dynamic routing. Production = Traefik (Dokploy), Caddy 2 = fallback self-host/dev.
- **AD-113a — Static-Hosting Exception:** static snapshot là transient exception cho 27.1a; 27.1c vẫn target per-app container.
- **NFR-2 (Security):** validate CNAME, no `eval` in container, sandbox file writes, path traversal checks.
- **NFR-3 (Observability):** deploy step logs and writes `TokenUsage`.

## File Structure Requirements

**NEW / UPDATE files:**
- `nowing_backend/app/services/web_builder/deploy_service.py` — thêm container lifecycle + route registration.
- `nowing_backend/docker/web-app.Dockerfile` — cân nhắc sửa để copy `.next/standalone` đã build thay vì build lại bên trong image.
- `nowing_backend/docker/proxy/Caddyfile` — wildcard `*.apps.nowing.net` + dynamic import `web-apps.Caddyfile`.
- `nowing_backend/docker/proxy/web-apps.Caddyfile` — (new) dynamic snippets do backend generate.
- `nowing_backend/docker/docker-compose.yml` — `dokploy-network`, Docker socket mount cho backend, volume `web_apps`.
- `nowing_backend/app/app.py` — giữ `Host` mount cho `*.apps.nowing.net` làm dev fallback; không cần sửa nếu Traefik/Caddy xử lý ingress chính.
- `nowing_backend/app/services/web_builder/schemas.py` — đã có `WebAppDeployInput/Output`, `CustomDomainInput/Output`.
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — (new) mock Docker + label/snippet generation.
- `nowing_backend/tests/integration/services/web_builder/test_deploy_service.py` — (new) mocked Docker build/run + DB + CNAME.

## Validation / Testing

- **Unit tests:** `tests/unit/services/web_builder/test_deploy_service.py` — image build/run mock, Caddy/Traefik label generation, domain collision, CNAME validation.
- **Integration tests:** `tests/integration/services/web_builder/test_deploy_service.py` — mocked Docker build/run + DB + DNS.
- **Frontend typecheck:** `cd nowing_web && pnpm tsc --noEmit`.
- **Ruff / format:** `ruff check app/services/web_builder app/routes/web_builder_routes.py app/app.py`.

## Previous Story Intelligence (27.1b)

- `BuilderService` đã xử lý `npm install` / `next build` với security, concurrency, timeout, logs, commit `TokenUsage`. Reuse pattern `_acquire_build_lock`, `record_token_usage`, path suffix check.
- `TokenUsage` phải được commit trước khi return để tránh mất dữ liệu.
- `host_router` không được include vào generic CRUD router; phải mount qua `starlette.routing.Host` để không shadow `/health`, `/ready`.
- Path traversal: `Path(...).resolve()` rồi kiểm tra suffix `web-app/{workspace_id}/{app_id}`; reject `..` và symlink.

## External Dependency Gating

- **Reverse proxy target:** Traefik (Dokploy) cho production; Caddy 2 cho self-host/dev.
- **Docker socket / build capabilities:** backend container phải mount Docker socket (PO confirmed).
- **Wildcard DNS:** `*.apps.nowing.net` trỏ về Dokploy/Traefik ingress.
- **CNAME target:** `cname-ingress.apps.nowing.net` (config `CNAME_INGRESS_HOST`).
- **Node runtime:** đã có trong `docker/web-app.Dockerfile`.
- **`dnspython`:** đã dùng trong `deploy_service.py` và các file khác.

## Tags

AD-113, FR-93, web-builder, deploy, docker, traefik, caddy, wildcard-domain, custom-cname, container

## Challenge Log (grill-me)

Run date: 2026-08-25. Focus areas: (1) Traefik/Caddy dynamic routing + custom domain ingress, (2) double-build Docker risk.

### Q1 — Already implemented?

- **No duplicate** of full container-deploy or custom-domain ingress found.
- `BuilderService` (`app/services/web_builder/builder.py:506-541`) already invokes `docker run --rm` to build the project inside a Node container. The `deploy_app` path does not reuse this pattern; it uses static snapshots.
- `host_router` (`app/app.py`) only matches `*.apps.nowing.net` for static snapshots; it does not handle custom domains or proxy to running containers.
- No existing Caddy/Traefik config writer or dynamic route registration utility exists in `nowing_backend`.

### Q2 — Simpler alternative?

- **🚨 CRITICAL — Double-build risk in AC-1:** AC-1 says "builds a Docker image from `docker/web-app.Dockerfile`". That Dockerfile (`docker/web-app.Dockerfile:5-15`) runs `npm install` and `npm run build` *inside the image*. But `BuilderService` already runs `npm install + next build` and produces `.next/standalone`. Rebuilding inside the image is a **double build** (wasted network, CPU, time, cost). Simpler alternatives:
  1. Create a production Dockerfile that only `COPY` the pre-built `.next/standalone` and runs `node server.js`.
  2. Skip `docker build` entirely and `docker run -v .next/standalone:/app node:20-alpine node /app/server.js`.
- **PO decision required** before dev: which deploy artifact do we ship? If the Dockerfile is kept as-is, document why double-build is acceptable (e.g., reproducible clean build) and account for it in `WEB_BUILDER_DEPLOY_COST_MICROS`.
- `BuilderService` already has a `docker` CLI subprocess pattern. `WebAppDeployService` should reuse or extract a shared helper rather than re-implement `shutil.which("docker")`, `asyncio.create_subprocess_exec`, timeout/kill cleanup.

### Q3 — Edge cases the spec misses (Pattern 3)

- **Slug disambiguation boundary:** `disambiguate_slug` caps at 63 chars and falls back to UUID tail after 100k numeric attempts. AC says `{slug}-{short_id}` but UUID tail is not `{short_id}`. Also need test when base slug is already 63 chars.
- **Concurrent publish of the same app:** no deploy lock. Two clicks → two containers, two port allocations, possible race on `WorkspaceApp` row.
- **Concurrent publish with same slug across workspaces:** `disambiguate_slug` queries `published` slugs but does not lock; race possible. Consider `SELECT FOR UPDATE` or unique partial index on `slug WHERE status='published'` (partial index already exists: `ix_workspace_apps_published_slug`).
- **Port allocation race:** if two apps request a free port simultaneously, the same port may be chosen. Need atomic port reservation (Redis `SET NX` or Docker `-P` + inspect).
- **Re-deploy while old container running:** old container must be stopped/removed before new one starts; what if stop fails? Resource leak.
- **Custom domain collision with unpublished/deleted apps:** `verify_and_bind_custom_domain` rejects any `WorkspaceApp` with `custom_domain == value` regardless of `status`. Should an unpublished or deleted app free its domain?
- **CNAME chain / multiple records:** `dns.resolver` CNAME query returns the first record set. Should we follow CNAME chains? Should we require only one CNAME?
- **Custom domain equal to base domain:** `app.mycompany.com` is fine, but `apps.nowing.net` or a subdomain already used by another published app should be rejected. `_is_valid_fqdn` does not check this.
- **Dockerfile build context bloat:** `docker/web-app.Dockerfile` `COPY . .` copies `node_modules`, `.next`, `.build_logs`, `.npm-cache` if no `.dockerignore`. This inflates build context and breaks cache. Need `.dockerignore` or a production Dockerfile copying only `.next/standalone`.
- **Healthcheck boundary:** how long to wait? What if the container starts but the Node process fails immediately? Need `docker logs` capture and timeout.
- **Feature gating boundary:** AC-4 says "free plan and `web_builder_enabled=False`". Current code checks `ws.web_builder_enabled is False` for any plan. Is there a separate free-plan check needed?

### Q4 — Failure modes unspecified (Pattern 2, 4)

- **Docker daemon unavailable:** `docker` CLI not installed, no socket mount, permission denied → must return `deploy_failed`, not crash the backend worker.
- **Image build fails:** invalid Dockerfile, network outage pulling base image, `npm install` fails → capture logs, mark `deploy_failed`, cleanup partial image.
- **`docker run` fails:** port already in use, image not found, seccomp/AppArmor block → release port, cleanup.
- **Container exits immediately / healthcheck fails:** Next.js `server.js` missing, `PORT` conflict, runtime error → stop container, mark `deploy_failed`, preserve `docker logs`.
- **Ingress config write/reload fails:** Caddy snippet invalid, `caddy reload` fails, Traefik labels not picked up → must not mark `published`; rollback container.
- **Transaction commit failure after container started:** `session.commit()` can fail, leaving a running container but DB rolled back. Need two-phase approach: commit DB *before* starting container (as deploy_app already does for static snapshot) or cleanup container on rollback.
- **Custom domain race:** two requests bind the same domain between collision check and insert. Add unique constraint on `custom_domain` or `SELECT FOR UPDATE`.
- **CNAME resolution transient failure:** DNS resolver timeout vs `NXDOMAIN`. Current code treats timeout as `failed`; should we retry? Should `NoAnswer` be treated as `pending_verification`?
- **Traefik/Caddy port conflict:** per `Knowns` memory, Traefik can silently fail if nginx or another process holds port 80/443. Self-host install script must check port ownership.
- **Dynamic DNS / container IP change:** per `Knowns` memory, nginx upstream caches container IP. Caddy/Traefik with Docker provider avoids this, but file-provider snippets must use service names/ports correctly.
- **Cleanup on backend restart:** if backend restarts, running containers may not be re-attached. `container_id`/`port` in DB become stale. Need reconcile on startup or treat as `deploy_failed`.
- **Cost config default `0`:** if `WEB_BUILDER_DEPLOY_COST_MICROS=0`, `TokenUsage` records `cost_micros=0` for real container deploy. This is a money/cost Pattern 4 issue. Must set nonzero deploy cost or compute from runtime.

### Triage

| Finding | Severity | Action |
|---|---|---|
| Q2 — Double-build Docker conflict with AC-1 | **Critical** | **HALT** — PO must decide deploy artifact (double-build Dockerfile vs. copy-standalone Dockerfile vs. bind-mount run) before dev starts. |
| Q3 — Concurrent deploy / slug / port race | **Critical** | **HALT** — add deploy lock, atomic port reservation, and `SELECT FOR UPDATE` / unique constraint before dev. |
| Q3/Q4 — Custom domain race + `session.flush` not `commit` | **Critical** | **HALT** — fix `verify_and_bind_custom_domain` to commit and add unique constraint / lock. |
| Q4 — Docker daemon / build / run / healthcheck failures unspecified | **Critical** | Add to spec and test skeleton (Pattern 2 / Over-Mocking risk). |
| Q4 — Cost `0` for container deploy | **Critical** | PO must ratify `WEB_BUILDER_DEPLOY_COST_MICROS` value or cost formula before merge. |
| Q3 — Build context bloat, no `.dockerignore` | Non-critical | Add `.dockerignore` or switch to copy-standalone Dockerfile. |
| Q3 — Healthcheck timeout boundary | Non-critical | Add explicit timeout and retry count to spec + tests. |
| Q3 — CNAME chain / multiple records | Non-critical | Document behavior in spec. |

**Verdict:** Story has **critical gaps that must be resolved before `dev-story`**. Recommend resolving the `double-build` and `deploy-lock`/`commit` issues first, then run `bmad-nowing-test-first-atdd` to pin the failure-mode tests.

## Challenge Log — Resolution Notes

- **`verify_and_bind_custom_domain` commit bug:** Fixed — `deploy_service.py` now calls `await session.commit()` after setting `custom_domain`/`custom_domain_status`.
- **Double-build Docker design (Q2):** Resolved — `docker/web-app.Dockerfile` rewritten as a **runtime image** that builds from the pre-built `.next/standalone` directory. `BuilderService` already runs `npm install + next build`; the deploy Dockerfile only serves the result.
- **Concurrent publish race (Q3):** Resolved — `WebAppDeployService` now acquires a per-app Redis/in-memory `web_builder:deploy:{app_id}` lock around slug selection, DB commit, and snapshot write.
- **Custom-domain race (Q3/Q4):** Resolved — `verify_and_bind_custom_domain` acquires a per-domain Redis/in-memory `web_builder:domain:{domain}` lock, and `WorkspaceApp` got a partial unique index `uq_workspace_apps_active_custom_domain` on `custom_domain` where `custom_domain_status = 'active'` (alembic migration `c50707287216`).
- **Cost `0` for container deploy (Q4):** **Still needs PO decision.** `WEB_BUILDER_DEPLOY_COST_MICROS` defaults to `0` because the current `deploy_app()` is the static-snapshot path (Option A). When container deploy is implemented, either set `WEB_BUILDER_DEPLOY_COST_MICROS` to a nonzero flat fee or introduce a separate `WEB_BUILDER_CONTAINER_DEPLOY_COST_MICROS` config and record the real compute cost.

## Updated Triage (post-fix)

| Finding | Severity | Action |
|---|---|---|
| Q2 — Double-build Docker | **Resolved** | Runtime Dockerfile in place; update `deploy_app` container path to use it. |
| Q3 — Concurrent deploy race | **Resolved** | Per-app deploy lock added. |
| Q3/Q4 — Custom domain race / commit bug | **Resolved** | Domain lock + unique partial index + explicit commit. |
| Q4 — Cost `0` for container deploy | **Critical (open)** | PO must ratify deploy cost model before container deploy ships. |
| Q4 — Docker daemon / build / run / healthcheck failures | **Critical** | Add failure-mode tests in `bmad-nowing-test-first-atdd` / `bmad-dev-story`. |
| Q4 — Cleanup on backend restart | Non-critical | Document container reconcile strategy in dev-story. |
| Q3 — Healthcheck timeout boundary | Non-critical | Add explicit timeout to spec + tests. |
| Q3 — CNAME chain / multiple records | Non-critical | Document behavior. |

**Updated Verdict:** The story can proceed to `bmad-nowing-test-first-atdd` and then `bmad-dev-story`, with the open item being the container-deploy cost model (which can be decided during dev or before merge).

## Tasks & Subtasks

- [x] **Task 1: Runtime Dockerfile & Container Deploy Service**
  - [x] Implement `WebAppDeployService.deploy_container` using runtime image from `.next/standalone`.
  - [x] Add `generate_traefik_labels` and `generate_caddy_snippet` for dynamic reverse proxy routing.
  - [x] Connect per-app containers to `dokploy-network` and assign high ports.
- [x] **Task 2: Ingress Configuration & Dynamic Routing**
  - [x] Add wildcard routing and dynamic snippet import (`web-apps.Caddyfile`) to `docker/proxy/Caddyfile`.
  - [x] Fallback to static HTML snapshot when container deploy is disabled or Docker is unavailable.
- [x] **Task 3: Custom CNAME DNS Proof-of-Control & Global Collision Protection**
  - [x] Validate FQDN syntax (reject IP addresses, localhost, invalid labels).
  - [x] Verify CNAME resolution against `CNAME_INGRESS_HOST` (`cname-ingress.apps.nowing.net`).
  - [x] Prevent cross-workspace domain collisions and commit binding transaction to DB.
- [x] **Task 4: Workspace Feature Gating & Billing Observability**
  - [x] Enforce 403 Forbidden when `web_builder_enabled` is disabled on workspace plan.
  - [x] Debit `TokenUsage` with `usage_type="web_builder_deploy"` and `WEB_BUILDER_DEPLOY_COST_MICROS`.
- [x] **Task 5: ATDD Test Scaffolding & E2E Validation**
  - [x] 12 Unit tests in `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` (100% GREEN).
  - [x] 3 Integration tests in `nowing_backend/tests/integration/routes/test_web_builder_deploy_routes.py` (100% GREEN).
  - [x] Playwright E2E spec in `nowing_web/tests/web-builder/web-builder-deploy-cname.spec.ts`.

## Dev Agent Record

### Implementation Summary
- Enhanced `WebAppDeployService` with Docker runtime container lifecycle (`deploy_container`) leveraging pre-compiled `.next/standalone` directory, preventing double-build overhead.
- Added dynamic ingress generator methods: `generate_traefik_labels` (for Dokploy production) and `generate_caddy_snippet` (for Caddy self-host).
- Updated `docker/proxy/Caddyfile` with wildcard `*.apps.nowing.net` handling and dynamic `web-apps.Caddyfile` import.
- Integrated DNS proof-of-control validation (`dnspython`), cross-workspace collision checks, and explicit database transaction commits.
- Verified test suite: 45 unit/integration tests passing (100% GREEN) and frontend typecheck clean.

### File List
- `nowing_backend/app/services/web_builder/deploy_service.py`
- `nowing_backend/app/config/__init__.py`
- `docker/proxy/Caddyfile`
- `docker/proxy/web-apps.Caddyfile`
- `docker/web-app.Dockerfile`
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py`
- `nowing_backend/tests/integration/routes/test_web_builder_deploy_routes.py`
- `nowing_web/tests/web-builder/web-builder-deploy-cname.spec.ts`

### Review Findings

- [x] [Review][Decision] DNS TXT Challenge Token Ownership Proof — Resolved: Giữ CNAME proof-of-control kết hợp Domain Blacklist cho Option A/MVP.
- [x] [Review][Patch] Custom Domain Binding không trigger redeploy container để cập nhật Traefik Labels [nowing_backend/app/services/web_builder/deploy_service.py:657] — Resolved
- [x] [Review][Patch] Next.js Standalone Build thiếu file `server.js` validation trước khi Docker Build [nowing_backend/app/services/web_builder/deploy_service.py:126] — Resolved
- [x] [Review][Patch] `host_router` chặn các request từ Custom Domains với HTTP 400 [nowing_backend/app/routes/web_builder_routes.py:810] — Resolved
- [x] [Review][Patch] `disambiguate_slug` xóa nhầm hậu tố số hợp lệ của tên app (`route-66` -> `route`) [nowing_backend/app/services/web_builder/deploy_service.py:38] — Resolved
- [x] [Review][Patch] Chuẩn hóa domain đầu vào: strip trailing dot `.` và convert lowercase trong `custom_domain` [nowing_backend/app/services/web_builder/deploy_service.py:541] — Resolved
- [x] [Review][Patch] Chặn Custom Domain trùng với subdomain hạ tầng nội bộ (`apps.nowing.net`, `nowing.net`, `api.nowing.net`) [nowing_backend/app/services/web_builder/deploy_service.py:545] — Resolved
- [x] [Review][Patch] Dọn dẹp duplicate definition `CNAME_INGRESS_HOST` trong `config/__init__.py` [nowing_backend/app/config/__init__.py:749] — Resolved
- [x] [Review][Defer] Multi-tenant Network Isolation / Cgroup CPU & Memory Limits [nowing_backend/app/services/web_builder/deploy_service.py:183] — deferred, infra hardening phase

#### Open findings from bmad-code-review (2026-08-26)

##### Decision needed

- [x] [Review][Decision] Cost model cho container deploy: `WEB_BUILDER_DEPLOY_COST_MICROS` đang default `0` — Đã quyết: giữ 0 cho MVP, định giá container deploy sau khi ra mắt.

##### Patch

- [x] [Review][Patch] Container deploy bị nuốt lỗi và vẫn trả `published` thay vì `deploy_failed` [nowing_backend/app/services/web_builder/deploy_service.py:473-487]
- [x] [Review][Patch] Không healthcheck container trước khi ghi `published` [nowing_backend/app/services/web_builder/deploy_service.py:214-248]
- [x] [Review][Patch] Caddy self-host ingress là dead code — `generate_caddy_snippet` chưa được gọi, `web-apps.Caddyfile` rỗng, `host_router` chỉ trả static [nowing_backend/app/services/web_builder/deploy_service.py:94, docker/proxy/Caddyfile:55, nowing_backend/app/routes/web_builder_routes.py:855-871]
- [x] [Review][Patch] Docker Compose thiếu `dokploy-network`, volume `web_apps`, Docker socket mount cho backend [docker/docker-compose.yml]
- [x] [Review][Patch] `host_router` chỉ mount trên `*.apps.nowing.net`, request custom domain không tới backend [nowing_backend/app/app.py:1209, nowing_backend/app/routes/web_builder_routes.py:830-836]
- [x] [Review][Patch] `docker run -P` expose random high port lên host, `WorkspaceApp.port` lưu port không ổn định và không dùng cho Traefik [nowing_backend/app/services/web_builder/deploy_service.py:209-234]
- [x] [Review][Patch] Traefik labels hardcode `entrypoints=websecure` và `tls.certresolver=default` [nowing_backend/app/services/web_builder/deploy_service.py:87-89]
- [x] [Review][Patch] Blacklist domain hệ thống hardcode thay vì dùng config [nowing_backend/app/services/web_builder/deploy_service.py:571-581]
- [x] [Review][Patch] Kiểm tra va chạm custom domain chưa lọc theo `custom_domain_status='active'` [nowing_backend/app/services/web_builder/deploy_service.py:634-637]
- [x] [Review][Patch] Custom domain binding commit `active` trước khi redeploy container thành công [nowing_backend/app/services/web_builder/deploy_service.py:711-745]
- [x] [Review][Patch] `verify_and_bind_custom_domain` không kiểm tra `Workspace.web_builder_enabled` [nowing_backend/app/services/web_builder/deploy_service.py:547, nowing_backend/app/routes/web_builder_routes.py:304-312]
- [x] [Review][Patch] Publish route trả 422 thay vì 403 khi workspace bị tắt Web Builder [nowing_backend/app/routes/web_builder_routes.py:227-230]
- [x] [Review][Patch] Test `test_feature_gate_403_when_disabled` bị sai tên và assertion (kiểm 422 thay vì 403) [nowing_backend/tests/integration/routes/test_web_builder_deploy_routes.py:117-144]
- [x] [Review][Patch] Thiếu test container lifecycle thực — unit test không gọi `deploy_container`, integration service test chưa tồn tại [nowing_backend/tests/unit/services/web_builder/test_deploy_service.py, nowing_backend/tests/integration/services/web_builder/]
- [x] [Review][Patch] `docker build`/`docker run` không có timeout, có thể treo vĩnh viễn [nowing_backend/app/services/web_builder/deploy_service.py:161-166, 214-218]
- [x] [Review][Patch] Redis lock lease có thể hết hạn trước khi build dài hoàn thành [nowing_backend/app/services/web_builder/deploy_service.py:261]
- [x] [Review][Patch] Runtime Dockerfile chạy root, thiếu `USER` và `HEALTHCHECK` [docker/web-app.Dockerfile:13-27]
- [x] [Review][Patch] Thiếu path-traversal guard trên `storage_path` trước khi build/run [nowing_backend/app/services/web_builder/deploy_service.py:375, 725]
- [x] [Review][Patch] Idempotency check bỏ qua container liveness — snapshot tồn tại nhưng container chết vẫn trả `published` [nowing_backend/app/services/web_builder/deploy_service.py:403-419]
- [x] [Review][Patch] Container không được dọn khi snapshot file write fail [nowing_backend/app/services/web_builder/deploy_service.py:514-528]
- [x] [Review][Patch] `npm import()` pattern chặn `next/dynamic(() => import(...))` hợp lệ [nowing_backend/app/services/web_builder/validator.py:48-52]
- [x] [Review][Patch] `.bin` wrapper chỉ kiểm tra symlink, không scan nội dung script [nowing_backend/app/services/web_builder/validator.py:220-233]
- [x] [Review][Patch] Builder sandbox cài `devDependencies` (`npm_config_include=dev`) dù `NODE_ENV=production` [nowing_backend/app/services/web_builder/builder.py:474, 535]
- [x] [Review][Patch] Alembic migration tạo unique partial index mà không xử lý duplicate active custom domain cũ [nowing_backend/alembic/versions/c50707287216_add_unique_active_custom_domain_to_workspace_apps.py:21-32]
- [x] [Review][Patch] CNAME verification không follow CNAME chain và không hỗ trợ apex ALIAS/ANAME [nowing_backend/app/services/web_builder/deploy_service.py:651-656]
- [x] [Review][Patch] Custom domain bound khi app chưa `published` dẫn tới `custom_domain_status='active'` nhưng route 404 [nowing_backend/app/services/web_builder/deploy_service.py:711-714]
- [x] [Review][Patch] Không validate độ dài custom domain tối đa 255 ký tự [nowing_backend/app/services/web_builder/deploy_service.py:560-569, nowing_backend/app/db.py]
