# Web Builder 27.1 Status Audit — 2026-08-25

**Auditor:** Devin (bmad + code review)  
**Scope:** Determine what code from the split child stories 27.1b, 27.1c, 27.1d already exists and what is still missing.  
**Sources:** `nowing_backend/app/services/web_builder/`, `nowing_backend/app/routes/web_builder_routes.py`, `nowing_backend/app/capabilities/web_builder/`, `nowing_backend/app/db.py`, `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx`, `docker/web-app.Dockerfile`, `docker/proxy/Caddyfile`, unit/integration tests.

## TL;DR

- **27.1a is functionally done.** Chat entry, `build_web_app` tool, deliverable card, static publish via backend `/web-apps/host`, and workspace gating are in place and tests pass.
- **27.1b is ~60% done.** Generation, project writer, validation, registry, and cost for `web_builder_generate` are done. The **real `npm install` + `next build`/`next dev` preview runner is missing**; preview is rendered in-browser via `PreviewRenderer` + Babel CDN.
- **27.1c is ~40% done.** `WebAppDeployService.deploy_app()` and `/web-apps/host` serve a static HTML snapshot, but **no Docker build/run, no container lifecycle, no Traefik/Caddy route registration, and no real CNAME DNS validation/ingress config**.
- **27.1d is ~50% done.** Mark Tool endpoint, UI toggle, iframe postMessage, and a regex-based JSX mutator exist. It is **not a real AST parser** (`@babel/parser` etc.) and does **not record `TokenUsage` with `usage_type="web_builder_mark"`**.

All existing web_builder unit + integration tests pass (`17 passed`).

## Audit Method

1. Read every file under `nowing_backend/app/services/web_builder/` and `nowing_backend/app/routes/web_builder_routes.py`.
2. Cross-checked the implementation against the ACs of `stories/27-1b.md`, `27-1c.md`, `27-1d.md`.
3. Ran `ruff check` and `pytest tests/unit/services/web_builder tests/integration/routes/test_web_builder_routes.py tests/unit/capabilities/test_web_builder_capability.py -q`.
4. Inspected `WorkspaceApp` DB model, `docker/web-app.Dockerfile`, and `docker/proxy/Caddyfile`.

## 27.1b — Web App Build & Preview Runner

| AC | Status | Evidence | Gap |
|---|---|---|---|
| AC-1: LLM generates Next.js + Tailwind project, writes to disk, returns `preview_url` | **Done** | `WebBuilderService._call_llm_for_spec()` → `ProjectWriter.write_file()` → `validate_project_structure()`; `generate_project()` returns `WebAppBuildOutput.preview_url`. | LLM prompt is generic, not sales/marketing constrained for 27.1a; `WebAppBuildInput` does have `max_length` validator but it uses `app_config.WEB_BUILDER_MAX_PROMPT_CHARS`, so fine. |
| AC-2: `BuilderService` runs `npm install` + `next build` / `next dev` and exposes preview URL; build failures return `status="build_failed"` | **Missing** | No `builder.py`; `get_workspace_app_preview()` calls `PreviewRenderer.render_app_html()` which **in-browser-compiles TSX via Babel/Tailwind CDN**. | Need `app/services/web_builder/builder.py` with async subprocess `npm install && next build`, `workspace_apps.status="building"`, build log capture, and `TokenUsage` with `usage_type="web_builder_build"`. Preview should serve from `.next/standalone` or a dev server port. |
| AC-3: Workspace app registry tracks `workspace_id`, `slug`, `status`, `preview_url`, and cost | **Done** | `WorkspaceApp` table exists with all fields; `WebBuilderService.generate_project()` creates row and records `TokenUsage` with `usage_type="web_builder_generate"`. | Missing `web_builder_build` `TokenUsage`. |
| AC-4: Workspace feature gating returns `403` when `web_builder_enabled=False` | **Done** | `Workspace.web_builder_enabled` column; `build_web_app.py` re-checks; `web_builder_routes.py` `check_web_builder_enabled()` and `require_workspace_member()`. | Permission uses `Permission.WEB_BUILDER_CREATE` if role has it, else owner. This is OK. |

### 27.1b Verdict

**In Progress / Partial.** The generation, persistence, and validation slices are done. The actual build/preview runner is the missing core.

## 27.1c — Web App Container Deploy & Custom CNAME

| AC | Status | Evidence | Gap |
|---|---|---|---|
| AC-1: 1-click publish builds Docker image, starts container, registers `*.apps.nowing.net` route | **Partial** | `/apps/{app_id}/publish` calls `WebAppDeployService.deploy_app()`; `WorkspaceApp.container_id` and `port` columns exist; `docker/web-app.Dockerfile` exists. | `deploy_app()` only runs `PreviewRenderer.render_app_html()` and writes a static `index.html` snapshot to `WEB_BUILDER_PUBLIC_APPS_PATH/{slug}/`. No Docker build/run, no container start, no Traefik/Caddy route registration. `container_id`/`port` are never set. |
| AC-2: Custom CNAME validated and mapped | **Partial** | `/apps/{app_id}/custom-domain` calls `verify_and_bind_custom_domain()`; checks DB collision and sets `custom_domain_status="active"`. | No DNS resolution check (e.g. `dnspython` CNAME validation against `CNAME_INGRESS_HOST`), no Traefik/Caddy config update for custom host, no ingress certificate orchestration. |
| AC-3: Workspace app registry updated with `status="published"`, `public_url`, `custom_domain`, and `TokenUsage` | **Partial** | `deploy_app()` updates `status`, `public_url`, `slug`; records `TokenUsage` with `usage_type="web_builder_deploy"` and `cost_micros=0`. | `cost_micros=0` is a placeholder; once real container deploy is added it should reflect compute/hosting cost or a flat publish fee. |
| AC-4: Feature gating | **Done** | Same as 27.1b. | — |

### 27.1c Verdict

**In Progress / Partial.** Static-snapshot publish is working and is what 27.1a used. Real container deploy, ingress routing, and CNAME are missing.

## 27.1d — Web App Mark Tool & JSX AST Mutator

| AC | Status | Evidence | Gap |
|---|---|---|---|
| AC-1: Visual element selection in preview iframe | **Done** | `PreviewRenderer` injects JS that highlights hovered element and posts `MARK_ELEMENT_SELECTED` to parent. Frontend `web-builder/page.tsx` listens and updates `selectedSelector` / `patchText`. | Selector is a simple heuristic (`#id`, first class, tag), not a robust bounded-box / XPath mapping. |
| AC-2: JSX AST mutation and re-build/preview | **Partial** | `POST /apps/{app_id}/mark` calls `MarkToolASTMutator.apply_patch()` and overwrites `app/page.tsx`. UI reloads iframe via `iframeKey`. | Mutator is **regex-based**, not a real AST (`@babel/parser`, `@babel/traverse`, `@babel/types`). It only supports `type=text`, `className`, and `class` patches on `id`/`class`/tag selectors. It does not record `TokenUsage` with `usage_type="web_builder_mark"`. |
| AC-3: Unresolvable selector handling | **Done** | `MarkToolASTMutator` returns `MutationResult(status="mark_unresolvable")` when selector cannot be mapped. | — |
| AC-4: Preview iframe security | **Done** | Frontend `<iframe sandbox="allow-scripts allow-forms allow-same-origin" />` and CSP headers on preview/host. | — |

### 27.1d Verdict

**In Progress / Partial.** UI and a basic patcher work, but the mutation is not a real AST parser and lacks cost telemetry.

## Test & Lint Results

```text
$ ruff check app/services/web_builder app/routes/web_builder_routes.py app/capabilities/web_builder tests/unit/services/web_builder tests/integration/routes/test_web_builder_routes.py tests/unit/capabilities/test_web_builder_capability.py
# 0 errors (1 auto-fixed import sort in test_preview_renderer.py)

$ pytest tests/unit/services/web_builder tests/integration/routes/test_web_builder_routes.py tests/unit/capabilities/test_web_builder_capability.py -q
17 passed, 13 warnings in 0.38s
```

## Key Files Inventory

### Backend (existing)
- `nowing_backend/app/services/web_builder/__init__.py`
- `nowing_backend/app/services/web_builder/generator.py`
- `nowing_backend/app/services/web_builder/project_writer.py`
- `nowing_backend/app/services/web_builder/preview_renderer.py`
- `nowing_backend/app/services/web_builder/deploy_service.py`
- `nowing_backend/app/services/web_builder/mark_tool.py`
- `nowing_backend/app/services/web_builder/validator.py`
- `nowing_backend/app/services/web_builder/schemas.py`
- `nowing_backend/app/routes/web_builder_routes.py`
- `nowing_backend/app/capabilities/web_builder/build_app/`
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py`
- `nowing_backend/app/db.py` — `WorkspaceApp` model
- `nowing_backend/app/config/__init__.py` — `WEB_BUILDER_*` flags

### Backend (missing)
- `nowing_backend/app/services/web_builder/builder.py` — real `npm install` + `next build` runner
- `nowing_backend/tests/unit/services/web_builder/test_build_runner.py`
- `nowing_backend/tests/unit/services/web_builder/test_deploy_service.py` — real container deploy tests
- `nowing_backend/tests/unit/services/web_builder/test_mark_tool.py` — real AST tests (only regex tests exist)

### Frontend (existing)
- `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx` — full editor/preview/publish/Mark Tool UI
- `nowing_web/lib/apis/web-builder-api.service.ts`

### Infrastructure (existing)
- `docker/web-app.Dockerfile`

### Infrastructure (missing)
- `docker/proxy/Caddyfile` — no `*.apps.nowing.net` wildcard or dynamic `web-apps.Caddyfile` import
- `docker/docker-compose.yml` — no `dokploy-network`, no web-app container service template

## Recommendations

1. **If you want to ship full 27.1:** Implement `builder.py` first (27.1b), then real container deploy (27.1c), then real AST mutator (27.1d). This is the largest chunk of work.
2. **If you want to ship Epic 27 value quickly:** Continue with **27.2a/27.2b** (Presentation Studio + Meeting Minutes). They reuse the existing `ChatMode` registry and artifact patterns; 27.1b/c/d can be parallelized or deferred.
3. **Update sprint-status:** Change 27.1b/27.1c/27.1d from `backlog` to `in-progress` with the missing gaps above captured in the story files, **or** keep them `backlog` if no one is actively working and record this audit as the source of truth.

## Proposed Status Update

| Story | Proposed status | Rationale |
|---|---|---|
| 27.1a | `done` | Static chat-first MVP is complete, tested, and reviewed. |
| 27.1b | `in-progress` | Generation done; build/preview runner is the missing core. |
| 27.1c | `in-progress` | Static publish done; real container/CNAME is missing. |
| 27.1d | `in-progress` | UI + regex mutator done; real AST parser + cost telemetry missing. |
