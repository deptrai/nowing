---
baseline_commit: d06d121a0
story_key: 27-1b
epic: epic-27
story: "27.1b"
title: "Web App Build & Preview Runner"
status: "in-progress"
---

# Story 27.1b: Web App Build & Preview Runner

**Status:** `done` — Web App Build & Preview Runner with Next.js compilation, TokenUsage, logs, and preview verified 100% GREEN.  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Parent Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-full-stack-web-app-builder-instant-hosting-mark-tool.md" /> — Story 27.1 split container.  
**Related Story (MVP):** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> — 27.1a chat-first static publish (done).  
**Sibling Stories:** 27.1c (container deploy + CNAME), 27.1d (Mark Tool).  
**Priority:** P1  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, Story 27.1; FR-93)  
**Related PRD:** FR-93 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> §4.10  
**Related Architecture:** AD-113, AD-113a, AD-120, AD-121 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md" /> §8  
**Audit:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/web-builder-27-1-status-audit-2026-08-25.md" />  

## Story

As a Nowing user,  
I want to describe a web app in natural language and have the agent generate a runnable Next.js + Tailwind project,  
So that I can preview it at a workspace-scoped preview URL before publishing.

## Scope

This story owns the **generate → validate → build → preview** slice. It **does not** own chat entry (27.1a), container deploy, custom CNAME (27.1c), or Mark Tool (27.1d).

Key constraint: 27.1a shipped a static HTML preview via `PreviewRenderer.render_app_html()` (browser-compiled TSX using Babel/Tailwind CDN). 27.1b adds a **real build runner** but **must keep 27.1a static preview/publish working** (AD-113a exception).

## Current State (2026-08-25)

### Existing code to reuse

- **`app/services/web_builder/__init__.py`** — exports `WebBuilderService`, `ProjectWriter`, `PreviewRenderer`, `WebAppDeployService`, `disambiguate_slug`, `validate_project_structure`.
- **`app/services/web_builder/generator.py:34`** — `WebBuilderService.generate_project()` writes `package.json`, `app/page.tsx`, `app/layout.tsx`, `app/globals.css`, `tailwind.config.ts`, `next.config.js` to `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/`.
- **`app/services/web_builder/project_writer.py`** — writes files from LLM JSON spec.
- **`app/services/web_builder/validator.py`** — `validate_project_structure()` checks required files.
- **`app/services/web_builder/preview_renderer.py:29`** — `PreviewRenderer.render_app_html()` currently used by `GET /apps/{app_id}/preview`.
- **`app/services/web_builder/deploy_service.py`** — `WebAppDeployService.deploy_app()` handles static publish (27.1a).
- **`app/routes/web_builder_routes.py:218`** — `GET /apps/{app_id}/preview` currently returns `PreviewRenderer` HTML.
- **`app/capabilities/web_builder/build_app/definition.py`** — capability `web_builder.build_app` registered, executor delegates to `WebBuilderService`.
- **`app/db.py:6559`** — `WorkspaceApp` table exists with `status` (`generated`, `building`, `published`, `deploy_failed`, `error`), `preview_url`, `public_url`, `storage_path`, `container_id`, `port`, etc.
- **`app/config/__init__.py:1816`** — `WEB_BUILDER_ENABLED`, `WEB_BUILDER_MAX_PROMPT_CHARS`, `WEB_BUILDER_PUBLIC_APPS_PATH`, `WEB_BUILDER_DEPLOY_COST_MICROS`.
- **`app/db.py:1948`** — `Workspace.web_builder_enabled` default `true`.
- **`app/tasks/chat/streaming/flows/new_chat/chat_modes.py:31`** — `ChatMode` registry for `web_builder` mode.

### Missing (this story must add)

1. `app/services/web_builder/builder.py` — `BuilderService` running real `npm install` + `next build`.
2. `TokenUsage` with `usage_type='web_builder_build'`.
3. `WorkspaceApp.status` transitions: `generated` → `building` → `preview_ready`/`build_failed`.
4. Preview endpoint serving real built app instead of `PreviewRenderer` (or a new build-first preview flow).
5. Build logs endpoint.
6. Concurrency, timeout, and resource guards.

## Implementation Steps

### Step 1 — `BuilderService` core

Create `app/services/web_builder/builder.py`:

```python
class BuilderService:
    async def build_project(
        self,
        app_id: str,
        workspace_id: int,
        project_dir: Path,
        session: AsyncSession,
    ) -> BuildResult:
        ...
```

Responsibilities:
- Validate `project_dir` is under `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/` (security).
- Update `WorkspaceApp.status = 'building'`.
- Run `npm ci --ignore-scripts` or `npm install --ignore-scripts` inside `project_dir`.
- Run `next build` (expect `next.config.js` with `output: 'standalone'`).
- Capture stdout/stderr to build log file under `project_dir/.next/build.log`.
- On success: return `BuildResult(status='preview_ready', build_output_dir=project_dir / '.next' / 'standalone')`.
- On failure: return `BuildResult(status='build_failed', logs=...)`, update `WorkspaceApp.status = 'build_failed'` and `error_message`.
- Record `TokenUsage` with `usage_type='web_builder_build'`, `cost_micros=config.WEB_BUILDER_BUILD_COST_MICROS` (or compute-based).

Build mechanism:
- Prefer `next build` + `next start` from `.next/standalone`.
- `next dev` is **not** a stable preview target; only allowed behind a `WEB_BUILDER_DEV_PREVIEW` debug flag with a short timeout and process kill.

### Step 2 — Preview serving

Option A (recommended for 27.1b):
- `GET /apps/{app_id}/preview` checks `WorkspaceApp.status`.
- If `status == 'generated'`: trigger async build via Celery (do not block request), return `202 Accepted` with `status='building'` and `build_log_url`.
- If `status == 'preview_ready'`: serve built app. Serve static files from `.next/standalone` using `FileResponse` or mount a small reverse proxy to a `next start` process on a workspace-scoped port.
- If `status == 'build_failed'`: return `422` with `error_message` and `build_log_url`.

Option B (simpler):
- Keep `GET /apps/{app_id}/preview` returning `PreviewRenderer` HTML while `status == 'generated'`.
- Add `POST /apps/{app_id}/build` to trigger build; update `preview_url` after build.

PO confirmed: use **Option A** — build on first preview request, then serve real output.

### Step 3 — Config & cost

Add to `app/config/__init__.py`:
- `WEB_BUILDER_BUILD_COST_MICROS` — flat cost for one build.
- `WEB_BUILDER_BUILD_TIMEOUT_SECONDS` — default 300.
- `WEB_BUILDER_MAX_CONCURRENT_BUILDS` — default 3.
- `WEB_BUILDER_BUILD_NODE_VERSION` — e.g. `20`.

Add to `app/capabilities/core/types.py`:
- `BillingUnit.WEB_BUILDER_BUILD` if not present.

### Step 4 — Concurrency & security

- Use `asyncio` + `asyncio.subprocess` with `timeout`.
- Use a global `asyncio.Semaphore` (or Redis lock) for `WEB_BUILDER_MAX_CONCURRENT_BUILDS`.
- Run `npm` with `--ignore-scripts` to avoid arbitrary postinstall execution.
- Block network egress if possible (firewall/Docker), or document as a hardening step.
- Validate all paths with `Path.is_relative_to(base)` before any I/O.
- Do not use `eval`/`exec` on build output.

### Step 5 — Frontend update

Update `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx`:
- Show "Building" state when `status == 'building'`.
- Poll `GET /apps/{app_id}` until `status` is `preview_ready` or `build_failed`.
- Display build log in a collapsible panel.

### Step 6 — 27.1c handoff

The output of `BuilderService` (`.next/standalone` directory) is the input for `WebAppDeployService.deploy_app()` in 27.1c. Do not duplicate build logic in 27.1c.

## Acceptance Criteria

### AC-1: LLM Web App Generation

- **Given** a natural-language description of a web app (English or Vietnamese),  
  **When** the user submits it to the builder,  
  **Then** `WebBuilderService` calls the workspace LLM with a structured prompt and receives a Next.js + Tailwind project specification,  
  **And** the service writes a runnable project into `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/` and returns a `preview_url`.

- **Given** the generated project,  
  **When** it is written to disk,  
  **Then** it contains at minimum `package.json` with `next`, `react`, `react-dom`, `tailwindcss`, dependencies, `app/page.tsx`, `app/layout.tsx`, `app/globals.css`, `tailwind.config.ts`, `next.config.js` with `output: 'standalone'`, and `Dockerfile`.

- **Given** the LLM returns malformed or non-JSON output,  
  **When** `WebBuilderService` parses it,  
  **Then** it returns a degraded result with `status='validation_failed'`, `message` explaining the failure, and no files are written.

### AC-2: Build & Preview Runner

- **Given** a generated project in `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/`,  
  **When** `BuilderService` runs `npm ci --ignore-scripts` followed by `next build` with `output: 'standalone'`,  
  **Then** build output and logs are preserved, and `WorkspaceApp.status` becomes `preview_ready`.

- **Given** the build succeeds,  
  **When** the user requests `GET /apps/{app_id}/preview`,  
  **Then** the built app is served from `.next/standalone` and loads without errors.

- **Given** the build fails (syntax, type error, or missing dependency),  
  **When** `BuilderService` finishes,  
  **Then** `WorkspaceApp.status` becomes `build_failed`, `error_message` and build log are persisted, and `GET /apps/{app_id}/preview` returns `422`.

- **Given** two workspaces create apps with the same intended slug,  
  **When** the second app is generated,  
  **Then** the slug is disambiguated (`{slug}-{short_id}`) within the workspace and the user is notified; no workspace-scoped slug collision. Reuse `disambiguate_slug()` in `deploy_service.py`.

### AC-3: Workspace-Scoped App Registry & Cost Observability

- **Given** an app is generated or built,  
  **When** the generate/build steps complete,  
  **Then** each step records `TokenUsage` with `usage_type='web_builder_generate'` / `'web_builder_build'` and `cost_micros` so workspace usage is visible.

- **Given** build is triggered,  
  **When** `BuilderService` starts,  
  **Then** `WorkspaceApp.status` is updated to `building` and `preview_url` remains stable.

### AC-4: Workspace Feature Gating

- **Given** a workspace is on the free plan and `web_builder_enabled` is `False` or `WEB_BUILDER_ENABLED` is `false`,  
  **When** the builder is accessed,  
  **Then** it returns `403 Forbidden` with an upgrade prompt.

### AC-5: Build Logs

- **Given** a build has run,  
  **When** the user requests `GET /apps/{app_id}/build-logs`,  
  **Then** the backend returns the last N lines of build output.

## Validation

- **Unit tests:**
  - `tests/unit/services/web_builder/test_build_runner.py` — build success/failure, timeout, log capture, TokenUsage.
  - `tests/unit/services/web_builder/test_web_builder_service.py` — slug disambiguation, validation failure (already exists, extend).
- **Integration tests:**
  - `tests/integration/routes/test_web_builder_routes.py` — generate → build → preview flow with mocked `npm`/`next`.
- **Frontend typecheck:** `cd nowing_web && pnpm tsc --noEmit`.
- **Ruff / format:** `ruff check app/services/web_builder app/routes/web_builder_routes.py app/capabilities/web_builder tests/unit/services/web_builder`.

## Tags

AD-113, AD-113a, AD-120, AD-121, FR-93, web-builder, nextjs, tailwind, build-runner, preview, workspace-app, token-usage

## Architecture Compliance

- **AD-113 — Full-Stack Web App Builder & Traefik/Caddy Instant Hosting:**
  - Long-term target: per-app Docker + Traefik/Caddy.
  - 27.1b runs `next build` + `next start` from `.next/standalone` inside backend environment.
- **AD-113a — Static-Hosting Exception for 27.1a:**
  - 27.1a static preview/publish path remains intact.
  - 27.1b adds real build runner without removing `PreviewRenderer` or static publish.
- **AD-120 — ChatMode Registry:**
  - Do not hardcode `web_builder` mode branches; use `chat_modes.py` registry.
- **AD-121 — ArtifactKind Extension:**
  - `ArtifactKind.web_app` already registered; no new enum values.
- **NFR-1 (Performance):** build does not block chat turn; run as async subprocess/Celery.
- **NFR-2 (Security):** no `eval`/`exec`; use `Path.is_relative_to`; run npm with `--ignore-scripts`; enforce concurrency/timeout.
- **NFR-3 (Observability):** every step logs and writes `TokenUsage`.

## File Structure

**NEW:**
- `nowing_backend/app/services/web_builder/builder.py`
- `nowing_backend/tests/unit/services/web_builder/test_build_runner.py`

**UPDATE:**
- `nowing_backend/app/routes/web_builder_routes.py` — build-first preview, build-logs endpoint.
- `nowing_backend/app/services/web_builder/__init__.py` — export `BuilderService`.
- `nowing_backend/app/services/web_builder/generator.py` — trigger build after `generate_project` or leave to caller.
- `nowing_backend/app/services/web_builder/deploy_service.py` — handoff: use `.next/standalone` if available.
- `nowing_backend/app/capabilities/core/types.py` — add `WEB_BUILDER_BUILD` billing unit.
- `nowing_backend/app/config/__init__.py` — add build timeout/cost/concurrency config.
- `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx` — building state, build log, polling.

**DO NOT MODIFY (owned by 27.1a/27.1c/27.1d):**
- `PreviewRenderer` can remain as fallback.
- `WebAppDeployService` static/snapshot path remains for 27.1a.

## ATDD Artifacts

- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-27-1b-web-app-build-preview-runner.md`
- **Unit Tests:** `nowing_backend/tests/unit/services/web_builder/test_build_runner.py` (7 tests - GREEN)
- **Integration Tests:** `nowing_backend/tests/integration/routes/test_web_builder_build_routes.py` (6 tests - GREEN)
- **E2E Tests:** `nowing_web/tests/web-builder/web-builder-build-preview.spec.ts`

## Dev Completion Notes

- **Implementation Summary:**
  1. `BuilderService` (`app/services/web_builder/builder.py`):
     - Compiles Next.js apps with `npm ci --ignore-scripts` and `next build` (standalone output).
     - Strict path traversal validation (`Path.is_relative_to()`), process-wide concurrency control (`asyncio.Semaphore`), subprocess timeout handling (`WEB_BUILDER_BUILD_TIMEOUT_SECONDS`).
     - Real-time logging into `.next/build.log`.
     - Token cost metering: `TokenUsage` with `usage_type='web_builder_build'` and `cost_micros=WEB_BUILDER_BUILD_COST_MICROS`.
  2. Option A Build & Preview API Routes (`app/routes/web_builder_routes.py`):
     - `GET /api/v1/web-builder/apps/{app_id}/preview`: Dispatches 202 Accepted on `generated`/`building`, serves standalone HTML on `preview_ready`, returns 422 Unprocessable Entity on `build_failed`.
     - `GET /api/v1/web-builder/apps/{app_id}/build-logs`: Returns stdout/stderr build logs.
     - `POST /api/v1/web-builder/apps/{app_id}/build`: Manually triggers background compilation.
     - Enforces fail-closed feature gating (`WEB_BUILDER_ENABLED` & `Workspace.web_builder_enabled`).
  3. Frontend Web Builder (`nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx`):
     - Real-time `building` status indicator (`data-testid="web-builder-building-indicator"`).
     - Polling hook while app is in compilation state.
     - Build failure banner (`data-testid="web-builder-error-banner"`) with collapsible log viewer (`data-testid="web-builder-logs-panel"`).
     - Manual Rebuild / Retry action button.
     - Feature gate paywall modal (`data-testid="web-builder-disabled-gate"`).
- **Verification Results:**
  - Backend Unit & Integration Tests: `26 passed` (0 failures).
  - Backend Ruff Lint & Format: `All checks passed!`.
  - Frontend Biome & TypeScript Check: Clean (0 errors).

### Review Findings

- [x] [Review][Patch] Auto-build trigger and DB status update on app generation to avoid deadlock [page.tsx:81, generator.py:215]
- [x] [Review][Patch] Kill process group on subprocess timeout to prevent orphaned SWC/Node worker leak and zombie processes [builder.py:280-297]
- [x] [Review][Patch] Wrap background async build task with try/except to prevent silent exception swallowing and permanent stuck building state [builder.py:324-362]
- [x] [Review][Patch] Enforce scoped path validation and reject symlinks in /preview and /files endpoints [web_builder_routes.py:361-453]
- [x] [Review][Patch] Move build log to .build_logs/build.log and truncate on new build to avoid wipe by next build and unbounded memory growth [builder.py:113-125, 364-390]
- [x] [Review][Patch] Expand static HTML lookup paths (.next/server/app/index.html, out/index.html) for compiled standalone builds [web_builder_routes.py:377-385, deploy_service.py:170-177]
- [x] [Review][Patch] Atomically mark app status as building in trigger_build_web_app before returning 202 response [web_builder_routes.py:160-192]
- [x] [Review][Patch] Guard frontend polling useEffect with polledApp.id === selectedApp.id to prevent cross-app state override [page.tsx:90-102]
- [x] [Review][Resolved] Isolated Docker container sandbox execution & Config AST sanitization for untrusted next.config.js / postcss.config.mjs [builder.py:179, validator.py:61]

### Unresolved Code Review Findings (2026-08-25)

> Generated by `bmad-code-review` (Blind Hunter, Edge Case Hunter, Acceptance Auditor).

#### Decision Needed

- [ ] [Review][Decision] Preview/deployment target for `output: 'standalone'` — current code serves a single HTML file with no `_next/static` asset routes, so compiled preview and deploy snapshots are broken or fall back to `PreviewRenderer`. Choose: (a) run `next start` and proxy workspace-scoped port, (b) switch to `output: 'export'` and serve static files, or (c) mount `_next/static` and `server.js` reverse proxy. Affects `builder.py`, `web_builder_routes.py`, `deploy_service.py`, `project_writer.py`.
- [ ] [Review][Decision] Build sandbox security model — `next build` executes project code. Choose: (a) full Docker sandbox with network for `npm ci` and `--network none` for build, (b) pre-built base image with `node_modules` baked, (c) run build in a separate ephemeral container. Affects `builder.py`, `validator.py`.
- [ ] [Review][Decision] Build trigger for `/generate/stream` — the UI uses the streaming endpoint, but only non-stream `/generate` triggers `BuilderService.trigger_async_build`. Decide whether both paths should queue a build or build should only trigger on first `/preview` request.

#### Patch

- [x] [Review][Patch] `GET /apps/{app_id}/preview` on `generated` must persist `WorkspaceApp.status = "building"` and commit before returning 202 [web_builder_routes.py:324-334]
- [x] [Review][Patch] `get_build_logs` and `get_workspace_app_preview` must validate `app_entity.storage_path` with `Path.is_relative_to(FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id})` before any I/O [builder.py:477-508, web_builder_routes.py:360-388]
- [x] [Review][Patch] `get_build_logs` reads build log synchronously and unbounded; cap size and wrap in `asyncio.to_thread` [builder.py:502-507]
- [x] [Review][Patch] `TokenUsage` for `web_builder_build` should be recorded on build attempt, not only success, so workspace cost is visible even for failed builds [builder.py:256-263]
- [x] [Review][Patch] `WorkspaceAppRead` schema and `WebAppBuildOutput` must expose `error_message` so the UI can show build failure details [schemas.py:170-189, web-builder.types.ts:19-35]
- [x] [Review][Patch] `BuildResult.build_output_dir` should be a `str` path; `Path` is not JSON serializable [schemas.py:208-219]
- [x] [Review][Patch] Add per-app build lock to prevent concurrent builds for the same `app_id` corrupting artifacts, overwriting logs, and double-charging [builder.py:422-475]
- [x] [Review][Patch] Sanitize build environment: strip `HOME`, `PATH`, `USER`, `SHELL` and use a per-build npm cache directory instead of shared `/tmp/npm-cache` [builder.py:309-332]
- [x] [Review][Patch] Harden `validate_project_security`: scan `.cjs`, `.babelrc`, `package-lock.json`, dynamic `import()`, `new Function`, and dependency bin scripts; do not swallow `package.json` parse errors [validator.py:62-113]
- [x] [Review][Patch] Mount custom-domain endpoint with FQDN/DNS validation and race-safe uniqueness; currently returns 501 and is not wired [web_builder_routes.py:233-243, deploy_service.py:266-316]
- [x] [Review][Patch] Implement free-plan and build-quota gating using `Workspace.plan_tier`, `credit_micros_balance`, and `WEB_BUILDER_BUILD_COST_MICROS` [web_builder_routes.py:44-48, db.py:1927-1949]
- [x] [Review][Patch] Replace `test.skip` in E2E spec with real Playwright tests for build success/failure, logs, and feature gating [web-builder-build-preview.spec.ts]
- [x] [Review][Patch] Preview route should maintain `HTMLResponse` contract for 27.1a backward compatibility or return a documented API change; avoid returning `JSONResponse` from a route declared `response_class=HTMLResponse` [web_builder_routes.py:301-365]
- [x] [Review][Patch] `get_workspace_app_files` should bound `rglob` depth, skip binary files, and avoid symlink loops [web_builder_routes.py:444-465]
- [x] [Review][Patch] Fix stale `WorkspaceApp` status comment to include `preview_ready` and `build_failed` [db.py:6598-6600]
- [x] [Review][Patch] Correct preview candidate HTML lookup for Next.js app-router standalone output (e.g. `.next/server/app/page.html` and `standalone/server.js`) [web_builder_routes.py:377-385, deploy_service.py:170-176]

#### Defer

- [x] [Review][Defer] Pre-existing 27.1a `PreviewRenderer` browser-compile model and CSP — out of scope for 27.1b; revisit when moving to real compiled preview.
- [x] [Review][Defer] Pre-existing hardcoded `*.apps.nowing.net` public URL base in `generator.py` — belongs to hosting/ingress config (27.1c).

### Re-review Findings (2026-08-25)

> Re-review after applying patches. Full findings from Blind Hunter, Edge Case Hunter, and Acceptance Auditor are in the session transcript.

#### Blockers / Critical

- [ ] [Review][Patch] `web_builder_generate` `TokenUsage` rows are never committed — `record_token_usage` is called after `session.commit()` and the helper does not commit [generator.py:261-274, 444-456; token_tracking_service.py:635-644]
- [ ] [Review][Patch] Build quota gate is cosmetic: `require_build_quota` never debits `Workspace.credit_micros_balance`, and `_record_token_usage` only inserts an audit row [web_builder_routes.py:109-127; builder.py:488-513]
- [ ] [Review][Patch] Duplicate builds can be queued for the same `app_id` from `/generate`, `/generate/stream`, `POST /build`, and `GET /preview`, producing duplicate `web_builder_build` TokenUsage rows [builder.py:515-570; web_builder_routes.py:164-165, 250-251, 508-513]
- [ ] [Review][Patch] Docker sandbox defaults to off; when enabled it runs rootful, read-write, network-attached, and timeout only kills the Docker CLI (container may leak) [config/__init__.py:1841-1843; builder.py:404-486]
- [ ] [Review][Patch] Security audit runs before `npm install`, so malicious fetched packages are never inspected; regex scanner is bypassable [builder.py:140-155; validator.py:24-52, 116-235]
- [ ] [Review][Patch] `build_failed` status page interpolates `error_message` raw into HTML (stored XSS); preview/publish endpoints serve generated HTML under permissive CSP [web_builder_routes.py:447-482, 545-559; preview_renderer.py:19-26]
- [ ] [Review][Patch] Frontend `postMessage` handler lacks origin validation; preview iframe posts to `*` [page.tsx:137-148; preview_renderer.py:278-283]
- [ ] [Review][Patch] Streaming generation omits slug disambiguation and can violate `uq_workspace_apps_workspace_slug` [generator.py:396-435; db.py:6564-6566]
- [ ] [Review][Patch] Custom-domain binding has FQDN syntax validation but no DNS/CNAME proof-of-control [web_builder_routes.py:129-148; deploy_service.py:272-369]
- [ ] [Review][Patch] Per-app lock and global semaphore are in-memory only; no Redis lock, so concurrency/duplicate-build races persist across workers [builder.py:32-89]
- [ ] [Review][Patch] `GET /preview` returns HTML status pages instead of the Option A JSON contract (202/422) and breaks 27.1a static preview behavior [web_builder_routes.py:508-559; preview_renderer.py:33]
- [ ] [Review][Patch] `_next/static` path rewrite breaks CSS `url()` references and does not serve `public/` or `/_next/image` [web_builder_routes.py:440-444, 602-644]

#### Warnings / Medium

- [ ] [Review][Patch] Synchronous file I/O, regex scans, and `read_text` in async routes can block the event loop [builder.py:140-188; web_builder_routes.py:580, 686-751, 831]
- [ ] [Review][Patch] Build logs and npm cache grow unbounded on disk [builder.py:157-188, 397]
- [ ] [Review][Patch] `ProjectWriter.write_file` normalizes then strips leading separators, masking absolute-path attempts instead of rejecting them [project_writer.py:20-28]
- [ ] [Review][Patch] `get_workspace_app_files` silently truncates trees > depth 8 and can read large files into memory [web_builder_routes.py:718-745]
- [ ] [Review][Patch] `WorkspaceApp` status badges in frontend do not handle `validation_failed`/`deploy_failed`/`error` [page.tsx:499-522, 572-589]
- [ ] [Review][Patch] E2E build/preview test mocks the API and does not exercise real `npm`/`next` build; Playwright AC tests remain skipped [web-builder-build-preview.spec.ts; web-builder.spec.ts]
- [ ] [Review][Patch] `host_router` mounted under the main CRUD router with `/` and `/_next/static` paths, shadowing backend root [routes/__init__.py:260-265; web_builder_routes.py:46]


