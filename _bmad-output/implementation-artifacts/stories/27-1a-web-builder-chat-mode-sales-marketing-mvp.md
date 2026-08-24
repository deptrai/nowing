---
baseline_commit: f6166911d
story_key: 27-1a
epic: epic-27
story: "27.1a"
title: "Web Builder Chat Mode MVP for Sales & Marketing (Option A)"
status: "pending-human-review"
---

# Story 27.1a: Web Builder Chat Mode MVP for Sales & Marketing

**Status:** `pending-human-review`  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Priority:** P1  
**Scope:** MVP slice of Story 27.1 — chat-first entry, standalone page kept, lightweight static publish via backend wildcard route (`*.apps.nowing.net`).  
**Related Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md" />  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, FR-93; AD-113)  
**PRD Amendment:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/AMENDMENT-Epic-27-Manus-Autonomous-Workstation-2026-08-20.md" />  

## Story

As a **sales or marketing user**,  
I want to start a Web Builder chat from a quick chip or URL and describe a simple landing page or report in natural language,  
So that the agent generates a lightweight web app, shows a live preview, and publishes it to `https://[app].apps.nowing.net` with one click.

## Goal

- **Not Manus**: this is not a general-purpose multi-step agent. It is a **single-turn, single-page generator** for sales/marketing content.
- **Fastest path to value**: generate → preview → publish, all from chat.
- **Chat mode**: the chat is still a single input box. The user starts a Web Builder thread via a quick chip, slash prompt, or `?mode=web_builder` URL. The thread is tagged with `platform_metadata.web_builder_mode=true`.
- **Standalone page**: `/dashboard/[workspace_id]/web-builder` remains the editor/preview/publish surface. Chat only creates the app and links to it.

## [BUILT] vs [GAP]

### [BUILT] — reuse from Story 27.1

- `WebBuilderService` and `ProjectWriter` generate a Next.js + Tailwind project into `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/`.
- `PreviewRenderer` renders the project as a self-contained HTML page using React/Babel/Tailwind CDN.
- `WorkspaceApp` table stores `app_id`, `workspace_id`, `slug`, `status`, `preview_url`, `public_url`.
- `web_builder.build_app` capability is registered in `app/capabilities/web_builder/build_app/`.
- `/dashboard/[workspace_id]/web-builder` standalone page with streaming, preview iframe, code viewer, publish button.
- `NewChatThread.platform_metadata` field and chat runtime support for passing per-thread metadata.
- `features/chat-artifacts` deliverable panel in chat (`ArtifactKind`, `ARTIFACT_TOOL_KINDS`).

### [GAP] — new work for 27.1a

1. **Chat entry point:** expose "Web Builder" quick chips in the chat welcome screen, `/web` slash prompt templates, and a `?mode=web_builder` URL query.
2. **Tool binding:** add `build_web_app` to the main agent tool registry and enable it when `platform_metadata.web_builder_mode=true`.
3. **Deliverable UI:** render a web-app deliverable card in chat (BODY_TOOLS + ArtifactKind) with Open/Publish/Copy CTAs.
4. **Lightweight publish (Option A):** publish by registering `*.apps.nowing.net` wildcard route to the backend; backend serves the pre-rendered static HTML by `Host` header/slug lookup.
5. **Sales/marketing prompt templates:** quick-start templates for landing page, pricing, lead capture, report, waitlist.

## Acceptance Criteria

### AC-1: Chat Session in Web Builder Mode

- **Given** the user is on the new-chat welcome screen,  
  **When** they click the "Build a landing page" quick chip (or use a `/web` slash prompt / `?mode=web_builder` URL),  
  **Then** a thread is created with `platform_metadata: { "web_builder_mode": true }`, and the chat runtime injects a sales/marketing web-builder system prompt plus the `build_web_app` tool.

- **Given** a web-builder chat session,  
  **When** the user submits a prompt,  
  **Then** the agent calls `build_web_app` (wrapping `web_builder.build_app`) with `prompt` and `workspace_id`, and the response stream includes a deliverable card with `app_id`, `name`, `slug`, `preview_url`, and `public_url`.

### AC-2: Generate Sales/Marketing Page

- **Given** the user describes a sales/marketing page (e.g., "landing page for a sales course"),  
  **When** `WebBuilderService` generates the project,  
  **Then** it produces a single-page Next.js + Tailwind app with `app/page.tsx`, `app/layout.tsx`, `app/globals.css`, `package.json`, and `tailwind.config.ts`, scoped to one of the predefined templates.

- **Given** a generated project,  
  **When** it is saved,  
  **Then** `WorkspaceApp` row has `status="generated"`, `preview_url` pointing to the backend preview endpoint, and a workspace-unique `slug`.

### AC-3: Preview from Standalone Page

- **Given** the user clicks the deliverable card in chat or opens `/dashboard/[workspace_id]/web-builder?app_id=xxx`,  
  **When** the standalone page loads,  
  **Then** it fetches the app, displays the preview iframe, file tree, and a "Publish" button.

### AC-4: 1-Click Publish to `*.apps.nowing.net` (Option A)

- **Given** a generated app with valid files and no slug collision,  
  **When** the user clicks "Publish",  
  **Then** `WebAppDeployService`:
  1. Calls `PreviewRenderer.render_app_html` to produce a static HTML snapshot.
  2. Saves the snapshot to a public serve directory keyed by `slug`.
  3. Ensures `*.apps.nowing.net` wildcard DNS points to the Dokploy/Traefik ingress.
  4. Returns `public_url=https://{slug}.apps.nowing.net` and `status="published"`.

- **Given** a visitor accesses `https://{slug}.apps.nowing.net`,  
  **When** the request reaches Traefik/Caddy,  
  **Then** the wildcard router forwards to the backend, the backend reads the `Host` header, resolves the `WorkspaceApp` by `slug`, and serves the static HTML.

- **Given** a slug collision,  
  **When** the app is published,  
  **Then** the slug is disambiguated (`{slug}-{n}`) and the new `public_url` is returned.

### AC-5: Out-of-Scope Guardrails

- **Given** the user asks for a multi-page site, complex backend, or container lifecycle,  
  **When** the agent processes the request,  **Then** it responds with a scope message: v1 supports single-page sales/marketing sites only, and offers the appropriate template.

- **Given** the workspace is on a plan where `WEB_BUILDER_ENABLED=False`,  
  **When** the user tries to start a Web Builder thread,  **Then** the API returns `403 Forbidden` with an upgrade prompt.

### AC-6: Edge Cases & Guards

- **Given** the user submits a prompt longer than `WEB_BUILDER_MAX_PROMPT_CHARS`,  
  **When** the request is validated,  **Then** the API returns `422 Unprocessable Entity` with a clear message.

- **Given** the generated `slug` contains invalid characters or exceeds 63 chars,  
  **When** `WorkspaceApp` is persisted,  **Then** the service normalizes/truncates to `[a-z0-9-]{1,63}` and disambiguates if needed.

- **Given** the user republishes an already-published app,  
  **When** `WebAppDeployService.deploy_app` is called again,  **Then** it returns the existing `public_url` and does not regenerate unless `force=true`.

- **Given** the backend receives a request to `/web-apps/host` with `Host: {slug}.apps.nowing.net` for an unknown slug,  
  **When** it looks up `WorkspaceApp`,  **Then** it returns `404 Not Found`.

- **Given** the CDN scripts (React, Babel, Tailwind) are unreachable,  
  **When** the preview iframe loads,  
  **Then** the page shows a graceful fallback (plain HTML or error message) instead of a blank screen.

## Scope: IN vs OUT

| IN | OUT |
|---|---|
| Single-turn chat generate | Multi-turn file patch via chat |
| Single-page Next.js + Tailwind | Multi-page apps, API routes, DB |
| `PreviewRenderer` static preview | Real `next build` / Docker container per app |
| Wildcard host-based publish to `*.apps.nowing.net` (Option A) | Custom CNAME, container lifecycle (start/stop/logs/metrics) |
| Basic Mark Tool hover/click in preview | AST mutation / auto-patch from Mark Tool |
| Sales/marketing prompt templates | General-purpose app builder (Manus-like) |
| One published version | Version history, rollback |

## Architecture Compliance

- **AD-113 — Web Builder & Instant Hosting (clarified):** v1a uses **backend-served static HTML via wildcard host route** on Traefik/Caddy, not a per-app Docker container. Real container runtime is deferred to Story 27.4.
- **AD-114 — Mark Tool:** only the visual selector is exposed; mutation is out of scope.
- **AD-1 — Monolith:** new tool and route live inside the existing FastAPI monolith; no new service.
- **AD-4 — Multi-agent tool registry:** add `build_web_app` to `_MAIN_AGENT_TOOL_FACTORIES` and `MAIN_AGENT_NOWING_TOOL_NAMES`. `stream_new_chat` detects `platform_metadata.web_builder_mode=true` and sets `enabled_tools=["build_web_app"]` plus a focused web-builder system prompt.

## Technical Requirements

- **Chat mode gating (no AgentConfig):** Use `NewChatThread.platform_metadata` to flag `web_builder_mode=true`. `stream_new_chat` reads the thread's `platform_metadata` (or the per-turn payload) and, for any turn on that thread, enables the `build_web_app` tool and prepends a sales/marketing web-builder system prompt. This avoids needing `AgentConfig`/`client_id` for the internal web chat, which `new_chat_routes.py` rejects.
- **Tool binding:** Create `app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py` as a LangChain tool factory. Register it in `main_agent/tools/registry.py` and `main_agent/tools/index.py` as `build_web_app`. The tool accepts `prompt` and optional `app_name`/`language`, opens a fresh `AsyncSession`, calls `execute_build_app`, and returns the `WebAppBuildOutput` fields.
- **Frontend deliverable:** Add `web_app` to `ArtifactKind` and `ARTIFACT_TOOL_KINDS`; create `GenerateWebAppToolUI` in `components/tool-ui/web-builder.tsx`; map `build_web_app` in `BODY_TOOLS` in `assistant-message.tsx`.
- **Frontend entry points:**
  - Add "Build a landing page" quick chips to `ThreadWelcome` in `components/assistant-ui/thread.tsx` that link to `/dashboard/[workspace_id]/new-chat?mode=web_builder&q=...`.
  - Add `/web` slash prompt templates in `components/new-chat/prompt-picker.tsx` for landing page, pricing, lead capture, waitlist, report.
  - Handle `mode=web_builder` query in `app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx` so the new thread is created with `platform_metadata: { "web_builder_mode": true }`.
- **Artifact sidebar:** Add `web_app` group to `features/chat-artifacts/ui/artifacts-panel.tsx` `GROUP_ORDER` and `contentType` mapping; add describe logic in `collect-artifacts.ts`.
- **Mode persistence:** The frontend must include `platform_metadata` on every `NewChatRequest` for a web-builder thread; the backend falls back to the thread's stored `platform_metadata` when the per-turn payload is absent, so mode is not lost on regenerate/refresh.
- **Publish path (Option A):**
  - `WebAppDeployService.deploy_app` in MVP calls `PreviewRenderer.render_app_html`.
  - Snapshot saved under `FILE_STORAGE_LOCAL_PATH/web-apps/{slug}/index.html` (or similar).
  - Backend route added to serve HTML by `Host` header: `GET /` with `Host: {slug}.apps.nowing.net` or a dedicated `/host/{slug}` route behind Traefik rewrite.
  - Traefik: wildcard `HostRegexp(\`{subdomain:[a-z0-9-]+}.apps.nowing.net\`)` router to backend.
  - Caddy (dev): `*.apps.nowing.net` reverse proxy to backend with `Host` header preserved.
- **Cost tracking:** Record `TokenUsage` with `usage_type="web_builder_generate"` and `usage_type="web_builder_deploy"`. For Option A deploy, `cost_micros` is a small fixed platform fee (e.g., 0) because it only writes a static file; no LLM tokens.
- **Free plan gating:** Check `Workspace.web_builder_enabled` or feature flag `WEB_BUILDER_ENABLED`. Add `WEB_BUILDER_ENABLED` and `WEB_BUILDER_MAX_PROMPT_CHARS` to `app/config/__init__.py`.
- **Prompt bounds:** Enforce `WebAppBuildInput.prompt` `max_length=WEB_BUILDER_MAX_PROMPT_CHARS` (default 2000) to prevent token/DoS abuse.
- **Slug bounds:** `WorkspaceApp.slug` `max_length=63` (DNS label limit); lowercase, digits, hyphens only; reject invalid slug before save.
- **Publish idempotency:** `WebAppDeployService.deploy_app` must be idempotent: if `status="published"` and the static HTML already exists, return existing `public_url` without overwrite unless `force=true`.
- **Public URL verification:** Set `public_url_status` (`pending`, `verified`, `failed`) and return `published` only after the static file is written and a health check via the wildcard route succeeds (or DNS is known configured).
- **Static file safety:** Save snapshot under `FILE_STORAGE_LOCAL_PATH/web-apps/{sanitized_slug}/index.html` and validate `sanitized_slug` matches `^[a-z0-9-]+$`; reject path traversal.
- **Host-header route:** Backend adds `GET /web-apps/host` that reads `Host` header, looks up `WorkspaceApp` by `slug=Host.split('.')[0]`, and returns the static HTML with `404` for unknown slug and `403` for workspace where `web_builder_enabled=False`.
- **Public access semantics:** Public URL is world-readable by design (no auth) because it is a hosted landing page. Document this in UX and AC.
- **Mode stickiness:** A thread with `platform_metadata.web_builder_mode=true` stays in web-builder mode; the user must create a new thread to switch. The frontend does not let the user toggle mode mid-thread.

## File List

**New files:**
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py` — tool factory for `build_web_app`.
- `nowing_web/components/tool-ui/web-builder.tsx` — deliverable card UI with error state.
- `nowing_web/features/chat-artifacts/ui/artifacts-panel.tsx` — add `web_app` to `GROUP_ORDER`.
- `nowing_web/contracts/types/web-builder.types.ts` — already exists; may need `ArtifactKind` update elsewhere.

**Update files:**
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/registry.py` — register `build_web_app`.
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/index.py` — add `build_web_app` to `MAIN_AGENT_NOWING_TOOL_NAMES`.
- `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/runtime/factory.py` — ensure `additional_tools` can be passed if the tool is not in the main registry (fallback only; prefer registry).
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` — detect `platform_metadata.web_builder_mode` and override `enabled_tools` + system prompt.
- `nowing_backend/app/services/web_builder/deploy_service.py` — switch to Option A static publish.
- `nowing_backend/app/routes/web_builder_routes.py` — add static HTML serve route; keep existing preview.
- `nowing_backend/app/main.py` (or root router) — add root `/web-apps/host` route or include new `web_builder_host` router.
- `nowing_web/features/chat-artifacts/model/artifact.ts` — add `web_app` to `ArtifactKind` and `ARTIFACT_TOOL_KINDS`.
- `nowing_web/features/chat-artifacts/lib/collect-artifacts.ts` — add `web_app` describe logic.
- `nowing_web/components/assistant-ui/assistant-message.tsx` — add `build_web_app` to `BODY_TOOLS`.
- `nowing_web/components/assistant-ui/thread.tsx` — add "Build a landing page" quick chips and pre-fill composer for `mode=web_builder`.
- `nowing_web/components/new-chat/prompt-picker.tsx` — add `/web` slash prompt templates for sales/marketing.
- `nowing_web/app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx` — handle `mode=web_builder` query and create thread with `platform_metadata`.
- `nowing_backend/app/config/__init__.py` — add `WEB_BUILDER_ENABLED`, `WEB_BUILDER_MAX_PROMPT_CHARS`, `WEB_BUILDER_PUBLIC_APPS_PATH`.

**No new DB table for MVP.**

## External Dependency Gating

- **DNS `*.apps.nowing.net`** must already point to the Dokploy/Traefik ingress (PO/Dokploy).
- **Traefik wildcard router** must be configured to route `*.apps.nowing.net` to the backend service.
- No `AgentConfig` seed required for MVP. Internal web chat uses `platform_metadata`; future vertical-client or PAT-scoped paths may reuse `AgentConfig` later.

## Validation

- **Unit:** `tests/unit/services/web_builder/test_web_builder_service.py` — slug disambiguation, static publish path.
- **Integration:** `tests/integration/routes/test_web_builder_routes.py` — generate → preview → publish → host-header serve.
- **E2E:** Playwright `tests/web-builder/chat-mode.spec.ts` — click "Build a landing page" chip, prompt, see deliverable, open `/web-builder?app_id=...`, publish, curl public URL.
- **Frontend:** `pnpm tsc --noEmit` on changed TSX files.
- **Backend:** `ruff check` on changed Python files.

### Review Findings (bmad-code-review — chunk 1 backend routes/services)

#### decision-needed
- [ ] [Review][Decision] Web Builder workspace permission model — `require_workspace_member` currently requires `Permission.FULL_ACCESS` (owner only), blocking Editors. Should there be a new `WEB_BUILDER_CREATE` permission, or should it reuse `CHATS_CREATE`/`AUTOMATIONS_CREATE`? — `nowing_backend/app/routes/web_builder_routes.py:42-55`
- [ ] [Review][Decision] Per-workspace `WEB_BUILDER_ENABLED` vs global flag — `Workspace` has no `web_builder_enabled` column. Should the plan gating be global (`config.WEB_BUILDER_ENABLED` only) or per-workspace? If per-workspace, a migration is needed. — `nowing_backend/app/routes/new_chat_routes.py:830-838` / `nowing_backend/app/routes/web_builder_routes.py:413-417`
- [ ] [Review][Decision] CSP/connect-src for published web apps — public pages currently inherit `default-src 'self' https:`, allowing generated scripts to fetch any https origin. Should we lock `connect-src 'self'` and require explicit external APIs, or keep it open for CDN assets? — `nowing_backend/app/services/web_builder/preview_renderer.py:60` / `nowing_backend/app/routes/web_builder_routes.py:432-437`
- [ ] [Review][Decision] Refinement of existing app metadata — `generate_project` updates only `prompt`, `status`, `error_message` for an existing app. Should `name`, `slug`, `description`, `language` also be updated when the user passes `app_name` or the LLM returns new values? — `nowing_backend/app/services/web_builder/generator.py:310-316`

#### patch
- [x] [Review][Patch] `WebAppDeployService.deploy_app()` passes a `dict` to `PreviewRenderer.render_app_html()` which expects `Path | str` — publishing will raise `TypeError`. Pass `project_path` instead. — `nowing_backend/app/services/web_builder/deploy_service.py:123-126`
- [x] [Review][Patch] `WorkspaceAppRead.user_id` is typed `int | None` but DB is `UUID`, causing Pydantic validation errors in list/get routes. Change to `UUID | None`. — `nowing_backend/app/services/web_builder/schemas.py:146`
- [x] [Review][Patch] `WebAppBuildInput.prompt` has no `max_length`; direct API bypasses `WEB_BUILDER_MAX_PROMPT_CHARS` (DoS / token abuse). Add `max_length=2000` or a validator that uses `config.WEB_BUILDER_MAX_PROMPT_CHARS`. — `nowing_backend/app/services/web_builder/schemas.py:32-34`
- [x] [Review][Patch] `get_workspace_app_preview` is unauthenticated and unscoped (no workspace membership check). Anyone with `app_id` can preview. Add `require_workspace_member` or at least auth. — `nowing_backend/app/routes/web_builder_routes.py:258-305`
- [x] [Review][Patch] `WebBuilderService` hardcodes `preview_url` to `http://localhost:8000`. Use `config` backend base URL so preview loads in staging/prod. — `nowing_backend/app/services/web_builder/generator.py:305,484`
- [x] [Review][Patch] `host_web_app` accepts any 2-part `Host` header (e.g. `foo.bar`) and does not verify it ends with `HOSTING_BASE_DOMAIN`. Add domain suffix validation. — `nowing_backend/app/routes/web_builder_routes.py:369-396`
- [x] [Review][Patch] `WebAppDeployService`/`disambiguate_slug` do not enforce the 63-char DNS label limit. Slug can exceed 63 chars. Add `[:63]` after disambiguation. — `nowing_backend/app/services/web_builder/deploy_service.py:92-94`
- [x] [Review][Patch] `WebAppDeployService.deploy_app()` can publish a non-existent `WorkspaceApp` and return `published` without a DB record, so public URL 404s. Add 404 check before deploy or inside the route. — `nowing_backend/app/services/web_builder/deploy_service.py:56-63`
- [x] [Review][Patch] `build_web_app` tool uses `WEB_BUILDER_PUBLIC_APPS_PATH` as `WebBuilderService` storage base, mixing source projects and public snapshots. Use `FILE_STORAGE_LOCAL_PATH` for source and only write snapshots to `WEB_BUILDER_PUBLIC_APPS_PATH`. — `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:90-92`
- [x] [Review][Patch] `build_web_app` tool does not check `config.WEB_BUILDER_ENABLED` or workspace membership. A web-builder chat thread user could be downgraded but tool still works. Add the same gate as `create_thread`. — `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:32-62`
- [x] [Review][Patch] `PreviewRenderer._sanitize_tsx_for_babel` does not strip lowercase TS type annotations (`: string`, `: number`, `: boolean`) because the regex only matches capitalized type names. Babel will fail on common types. — `nowing_backend/app/services/web_builder/preview_renderer.py:232-233`
- [x] [Review][Patch] `PreviewRenderer` has no CDN-fallback for React/Babel/Tailwind; if CDNs are unreachable the preview is blank. Add an inline error/fallback or bundle the scripts. — `nowing_backend/app/services/web_builder/preview_renderer.py:64-96`
- [x] [Review][Patch] `WebBuilderService.generate_project` appends each new prompt to `existing_app.prompt` with `\n---\n` without a length cap, potentially creating an unbounded Text field. Truncate or rotate. — `nowing_backend/app/services/web_builder/generator.py:311`
- [x] [Review][Patch] `WebBuilderService._call_llm_for_refinement` reads every existing file and sends to LLM without context window / token limits. Large projects could exceed LLM context. Add a size/selection limit. — `nowing_backend/app/services/web_builder/generator.py:130-134`
- [x] [Review][Patch] `get_workspace_app_preview` builds a fallback project at `workspace_id=1` when `app_entity` is missing, which could accidentally serve another workspace's app. Return 404 when app not found. — `nowing_backend/app/routes/web_builder_routes.py:280`
- [x] [Review][Patch] `WebAppDeployService.deploy_app()` idempotency check only verifies `snapshot_file.exists()`, not that the file belongs to the `app_id` being published. Add `app_entity.slug == sanitized_slug` to the check. — `nowing_backend/app/services/web_builder/deploy_service.py:97-105`

#### defer
- [x] [Review][Defer] Synchronous file I/O in async web-builder service methods — `read_text`, `write_text`, `rglob` are called directly inside `async def`. Pre-existing blocking pattern in `WebBuilderService`/`WebAppDeployService`; revisit if latency spikes. — `nowing_backend/app/services/web_builder/generator.py`, `deploy_service.py`
- [x] [Review][Defer] `WebBuilderService.generate_project_stream` uses a new `uuid` and ignores `app_id`, so it cannot refine and does not record token usage. Story 27.1a uses the non-streaming `generate_project` path; streaming endpoint is existing pre-27.1a scope and out of MVP. — `nowing_backend/app/services/web_builder/generator.py:369-505`
- [x] [Review][Defer] `PreviewRenderer._sanitize_tsx_for_babel` strips only `document.cookie`, `localStorage`, `sessionStorage` and not `fetch`, `XMLHttpRequest`, `navigator.sendBeacon`, `window.parent`, etc. Broader sandbox hardening is a security enhancement beyond the current `unsafe-inline`/`unsafe-eval` CSP sandbox. — `nowing_backend/app/services/web_builder/preview_renderer.py:209-216`
- [x] [Review][Defer] `WebBuilderService.generate_project` records hardcoded `prompt_tokens=500`, `completion_tokens=2000`, `cost_micros=15000` for token usage. The spec requires recording `TokenUsage`, not exact metering. Accurate cost measurement depends on integrating with `TokenTrackingService` and LLM provider usage metadata, which can be improved later. — `nowing_backend/app/services/web_builder/generator.py:344-352`

## Challenge Log (grill-me)

### Q1 — Already implemented?

- `WebBuilderService`, `PreviewRenderer`, `WorkspaceApp`, `web_builder.build_app` capability, and standalone `/web-builder` page are already implemented in Story 27.1. **This story reuses those; it does not re-implement them.**
- No `platform_metadata`-based chat mode for Web Builder exists yet.
- No wildcard host-based static serve route exists yet; preview is by `app_id`, not by `Host` header.

**Verdict:** No duplicate for the new scope. Proceed.

### Q2 — Simpler alternative?

- **Option A (backend wildcard static serve)** is the simplest alternative to real Docker container per app. It avoids `npm install`/`next build`/Docker socket/Traefik labels and fits the single-page sales/marketing use case.
- Could publish as a static file directly from Caddy file server, but that would require managing Caddy config dynamically. Serving from the backend with a `Host` header lookup is simpler because the backend already owns `WorkspaceApp` data and auth.

**Verdict:** Option A is the simplest viable alternative. Proceed.

### Q3 — Edge cases the spec misses

- **Boundary:** prompt length; generated file count; slug max length; public URL length.
- **Null/empty:** empty prompt; whitespace-only prompt; prompt in unsupported language.
- **Concurrent:** two users in the same workspace submit prompts at the same time (slug collision race).
- **Idempotency:** user double-clicks "Publish"; backend must be idempotent or return existing `public_url`.
- **Host header spoofing:** user sends `Host: {other-slug}.apps.nowing.net` to access another workspace's app — must be handled by backend lookup + workspace auth.
- **Wildcard vs custom CNAME:** in MVP, custom CNAME is out of scope. A user pointing a CNAME to `*.apps.nowing.net` will hit the wildcard router; the backend must reject unknown slugs cleanly.
- **Mode loss across turns:** if the frontend omits `platform_metadata` on a follow-up turn, the backend must fall back to the thread's stored `platform_metadata` to keep the thread in web-builder mode.

### Q4 — Failure modes unspecified

- **LLM unavailable or timeout:** generation returns `validation_failed` with a fallback minimal scaffold or a friendly error.
- **Slug collision race:** Postgres unique constraint on `workspace_apps.slug`; backend disambiguates and retries.
- **DNS not configured for `*.apps.nowing.net`:** publish returns `published` but URL is not reachable; test/verify gate required.
- **Traefik/Caddy wildcard router missing:** public URL 404; deploy must fail closed if the wildcard route is not live.
- **Disk full:** writing static HTML snapshot fails; return `deploy_failed` and cleanup partial file.
- **PreviewRenderer fails to sanitize complex TSX:** fall back to a safe default HTML page.
- **Workspace plan gating:** if `web_builder_enabled=False`, all routes fail `403`.

### Triage

- No duplicate logic → proceed.
- Option A selected as simplest alternative → proceed.
- Edge cases and failure modes documented above; should be added to test-first ATDD skeleton before green phase.
- **Overall: clean — proceed to test-first ATDD or story refinement.**

## Edge Case Hunter Review (patched)

Agent `bmad-review-edge-case-hunter` walked the spec and identified the following unhandled paths. Each was patched in the ACs, Technical Requirements, or File List above.

| Unhandled path | Patched as |
|---|---|
| `platform_metadata.web_builder_mode` may not be set or may be lost across turns. | Mode persistence requirement + frontend sends `platform_metadata` on every turn + backend falls back to thread stored metadata. |
| Workspace `web_builder_enabled=False` not checked at tool/route boundary. | AC-5 + `WEB_BUILDER_ENABLED` config + `WorkspaceApp` host route returns `403`. |
| Prompt length unbounded; DoS/LLM cost risk. | `WEB_BUILDER_MAX_PROMPT_CHARS` + AC-6. |
| `slug` length/format not normalized; DNS/URL limits ignored. | Slug bounds `[a-z0-9-]{1,63}` + disambiguation + AC-6. |
| `public_url` returned before DNS/ingress is verified. | `public_url_status` + AC-4 verification step. |
| Double-click "Publish" can create duplicate/race. | Publish idempotency in Technical Requirements. |
| Host-header route does not specify behavior for unknown slug. | `GET /web-apps/host` returns `404` for unknown slug, `403` for disabled workspace. |
| Republish overwrites existing file without user confirmation. | `force=true` flag; default idempotent. |
| `PreviewRenderer` CDN unavailability leaves blank preview. | AC-6 graceful fallback. |
| Mode per thread cannot be switched; UI may allow it. | Mode stickiness note + frontend does not expose mid-thread toggle. |
| `web_app` artifact group missing from `GROUP_ORDER` and `contentType` mapping. | File List updated for `artifacts-panel.tsx` and `collect-artifacts.ts`. |
| No dedicated root route to serve `Host` header in backend. | File List updated for `app/main.py` and `/web-apps/host` route. |

## UX Design Notes (Sally)

### Entry points (most convenient first)

1. **Quick chip on welcome screen** — "Build a landing page 🌐", "Create pricing page", "Make a waitlist". One click creates a `web_builder_mode` thread and pre-fills the composer.
2. **`/web` slash command** in composer — type `/web` to pick a template, then edit the prompt.
3. **URL query `?mode=web_builder`** — for marketing CTAs outside chat (e.g. from the dashboard empty state or a docs page).

### Prompt templates

Localized (`en`/`vi`) sales/marketing starters:
- Landing page for a course / product / service
- Pricing table with 3 tiers
- Lead capture form for a webinar
- Waitlist / coming-soon page
- Downloadable report / whitepaper page

### Deliverable card

Three states in the chat body:
- **Generating** — app name + spinner.
- **Generated (unpublished)** — preview thumbnail, "Open editor" → `/web-builder?app_id=...`, "Publish".
- **Published** — public URL, "Copy", "Open", "Edit".

Use `SuggestedActionPills` for these CTAs.

### Artifact panel

Add `web_app` alongside reports/images. The artifact lists the generated page and jumps back to the chat message.

### Public URL

After publish, the public URL must be the most prominent element — sales/marketing users copy/share it immediately.

## Addendum — Post-Review Edge Cases (patched)

After the UX review and a second Edge Case Hunter pass, the following additional guards and implementation notes were added to the story.

### AC-1a: Mode query and `platform_metadata` validation

- **Given** the URL contains `?mode=web_builder` but also an existing `chat_id`,  
  **When** `new-chat/[[...chat_id]]/page.tsx` loads,  
  **Then** it **ignores** `mode=web_builder` for existing threads; mode is only applied when creating a new thread.

- **Given** `platform_metadata.web_builder_mode` is not boolean `true` (string, object, `null`, or missing),  
  **When** the chat runtime validates the thread,  
  **Then** it is treated as `false` and the thread falls back to normal chat; unknown keys inside `platform_metadata` are ignored.

### AC-6a: Additional route and host guards

- **Given** a request to `GET /web-apps/host` with `Host: {slug}.apps.nowing.net:443` or `Host: apps.nowing.net` (no subdomain),  
  **When** the backend parses the header,  
  **Then** it strips the port, validates the `*.apps.nowing.net` suffix, and returns `400` for malformed hosts and `404` for missing/unknown slugs.

- **Given** a workspace with `WEB_BUILDER_ENABLED=False`,  
  **When** the user calls any web-builder endpoint (`/generate`, `/publish`, `/apps/{app_id}/preview`, `/apps/{app_id}/files`),  
  **Then** the API returns `403 Forbidden`.

### Technical additions

- **Global slug uniqueness:** public URL `https://{slug}.apps.nowing.net` must be unique across **all** workspaces. Before writing a snapshot, `WebAppDeployService` performs a global lookup on `WorkspaceApp.slug`; if the slug is taken, it disambiguates to `{slug}-{n}` globally. A unique index on `WorkspaceApp.slug` is preferred over per-workspace uniqueness.
- **Public URL status tracking:** use the existing `WorkspaceApp.status` column (`generated` → `published`/`deploy_failed`) to track publish verification. If a separate `public_url_status` column is added, it must not change `WebAppDeployOutput` so Story 27.4 remains compatible.
- **Static snapshot path:** save to `WEB_BUILDER_PUBLIC_APPS_PATH/{sanitized_slug}/index.html` (default `FILE_STORAGE_LOCAL_PATH/web-apps/{sanitized_slug}/index.html`), keyed by the final globally unique `slug`. The path is validated against path traversal.
- **`build_web_app` tool details:**
  - Pass `user_id` from the chat dependency bag into `WebAppBuildInput` so `WorkspaceApp.user_id` and `TokenUsage.user_id` are recorded.
  - Override the `WebBuilderService` system prompt with a sales/marketing single-page constraint, or pass a `template_mode`, so the generated page matches the predefined templates.
  - Return a `validation_failed` status that `GenerateWebAppToolUI` renders as an error card with a retry prompt and **no Publish CTA**.
- **Frontend `platform_metadata` plumbing:**
  - `Composer` in `components/assistant-ui/thread.tsx` tracks `platform_metadata` when a user picks a `/web` slash prompt or quick chip.
  - `PromptPicker.onSelect` payload is extended to carry `platform_metadata: { "web_builder_mode": true }` for built-in web builder templates.
  - `app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx` creates a `NewChatThread` via `POST /threads` with `platform_metadata` before the first turn when `mode=web_builder` and no `chat_id` is present.
- **Artifact model for `web_app`:**
  - `ArtifactKind` becomes `"report" | "resume" | "podcast" | "video" | "image" | "web_app"`.
  - `ChatArtifact.contentType` accepts `"markdown" | "typst" | "web"` (or renders `web_app` as a markdown summary card with a deep link).
  - `collect-artifacts.ts` sets `entityId: null` for `web_app` and uses `toolCallId` as the artifact key.
- **Deliverable publish CTA:** `GenerateWebAppToolUI` calls `POST /api/v1/web-builder/apps/{app_id}/publish` and transitions the card to the `Published` state on success, displaying the public URL with Copy/Open/Edit actions.

## Edge Case Hunter Review (patched) — additional rows

| Unhandled path | Patched as |
|---|---|
| `?mode=web_builder` on existing `chat_id` overwrites mode. | AC-1a: only apply to new threads. |
| `platform_metadata.web_builder_mode` value not validated (string/object/null). | AC-1a: coerce only boolean `true`, unknown keys ignored. |
| `WorkspaceApp.slug` not globally unique → public URL collision. | Technical Additions: global lookup + disambiguation + unique index. |
| `public_url_status` column referenced but missing in `WorkspaceApp`. | Technical Additions: use `status` or add column without breaking `WebAppDeployOutput`. |
| `WebAppDeployService` snapshot overwritable by another workspace. | Technical Additions: path keyed by final, globally unique slug. |
| `GET /web-apps/host` does not handle port/missing subdomain. | AC-6a: strip port, validate suffix, return 400/404. |
| `WEB_BUILDER_ENABLED` not checked on `generate`/`publish`/`preview` routes. | AC-6a: 403 on all web-builder endpoints. |
| `build_web_app` tool does not pass `user_id`. | Technical Additions: pass `dependencies["user_id"]`. |
| `WebBuilderService` prompt generic, not sales/marketing. | Technical Additions: override system prompt / add `template_mode`. |
| `PromptPicker` cannot set `platform_metadata`. | Technical Additions: extend `onSelect` payload. |
| New chat page does not create thread with `platform_metadata` before first turn. | Technical Additions: create thread on load for `mode=web_builder`. |
| `GenerateWebAppToolUI` has no publish handler. | Technical Additions: call publish API and transition card. |
| `ChatArtifact` cannot represent `web_app`. | Technical Additions: extend `ArtifactKind` and `contentType`. |

## Dev Notes

- Keep the `WebAppDeployService` interface unchanged (`WebAppDeployOutput`) so Story 27.4 can swap in real container deploy later.
- `public_url` should be set only after the static HTML is successfully saved and a wildcard route is verified.
- Do not expose container lifecycle endpoints in MVP.
- Mark Tool should remain a **read-only selector**; do not enable patch in MVP.
- The chat deliverable card should deep-link to the existing standalone page; do not embed a full canvas inside chat.

### Review Findings

- [x] [Review][Decision] Implement Option A Static Publish & Host-Header Route (Step 4) — deploy_service static HTML snapshot with idempotency, GET /web-apps/host wildcard route, and session.commit() on publish
- [x] [Review][Patch] Fix UUID instantiation crash on dependencies['user_id'] in build_web_app [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:28]
- [x] [Review][Patch] Fix Deliverable Card loading hang on string error results [nowing_web/components/tool-ui/web-builder.tsx:1133]
- [x] [Review][Patch] Fix slash command /web mode activation state sync [nowing_web/components/assistant-ui/thread.tsx:1014]
- [x] [Review][Patch] Add WEB_BUILDER_ENABLED gate to all web_builder_routes endpoints [nowing_backend/app/routes/web_builder_routes.py:82]
- [x] [Review][Patch] Add require_workspace_member auth validation to Web Builder routes [nowing_backend/app/routes/web_builder_routes.py:40]
- [x] [Review][Patch] Remove duplicate session.commit in build_web_app tool [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:75]
- [x] [Review][Patch] Validate prompt length and return error instead of silent truncation [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:45]
- [x] [Review][Patch] Fix collect-artifacts validation_failed check [nowing_web/features/chat-artifacts/lib/collect-artifacts.ts:95]
- [x] [Review][Patch] Add disambiguate_slug before database insert in generator.py [nowing_backend/app/services/web_builder/generator.py:135]
- [x] [Review][Defer] Multi-turn chat AST editing & conversation refinement [nowing_backend/app/services/web_builder/generator.py] — deferred, scoped to Story 27.4
- [x] [Review][Defer] Isolated sandbox preview origin domain separation [nowing_backend/app/services/web_builder/preview_renderer.py] — deferred, pre-existing infra

### Review Findings — code review of story 27-1a (2026-08-21)

- [x] [Review][Dismiss] Frontend implementation is missing from the reviewed diff — False positive. The backend diff omitted frontend, but the required frontend files already exist in `nowing_web/` (quick chips, slash prompts, `?mode=web_builder`, `ArtifactKind.web_app`, `GenerateWebAppToolUI`, `BODY_TOOLS`, standalone page). Verified by `web-builder-27-1-status-audit-2026-08-25.md` and file scan. [nowing_web/]
- [x] [Review][Defer] Content-Security-Policy is intentionally broad for generated/published apps — Accepted for the MVP. The preview/public renderer relies on Babel/Tailwind/React CDN and generated apps may call external lead-form/analytics endpoints. Per-app CSP allow-lists and removal of `unsafe-eval` are deferred to Story 27.1c/d or a hardening pass. [nowing_backend/app/services/web_builder/preview_renderer.py:19-26]
- [x] [Review][Defer] Plan gating defaults are `True` for every workspace — The workspace-level toggle works and the chat tool/routes re-check `Workspace.web_builder_enabled`. Plan-tier entitlement integration (free vs. paid) is out of 27.1a scope and deferred to a follow-up story / `WorkspaceLimit` hook. [nowing_backend/app/config/__init__.py:1816, nowing_backend/app/db.py:1948-1950, alembic/versions/232_add_web_builder_enabled_and_permission.py:46-48]
- [x] [Review][Defer] `WebAppDeployService` returns `published` without DNS/ingress verification — Static-snapshot publishing for 27.1a assumes the wildcard DNS/ingress is provisioned externally (Traefik/Caddy). A real `public_url_status` health check and DNS validation belong to the container/CNAME work in Story 27.1c. [nowing_backend/app/services/web_builder/deploy_service.py:118-152]

- [x] [Review][Patch] `build_web_app` chat tool membership check is fail-open [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:140-154]
- [x] [Review][Patch] REST endpoints do not enforce per-workspace `Workspace.web_builder_enabled` [nowing_backend/app/routes/web_builder_routes.py:58-64]
- [x] [Review][Patch] `WebAppDeployService.deploy_app` does not verify the workspace gate [nowing_backend/app/services/web_builder/deploy_service.py:43-144]
- [x] [Review][Patch] Public host route is not at `/` [nowing_backend/app/routes/web_builder_routes.py:383]
- [x] [Review][Patch] Stored `preview_url` omits the required `workspace_id` query parameter [nowing_backend/app/services/web_builder/generator.py:313, nowing_backend/app/services/web_builder/generator.py:518]
- [x] [Review][Patch] `get_workspace_app_preview` raises 500 when `storage_path` is `None` [nowing_backend/app/routes/web_builder_routes.py:290-308]
- [x] [Review][Patch] `PreviewRenderer` CDN fallback cannot render [nowing_backend/app/services/web_builder/preview_renderer.py:77-86]
- [x] [Review][Patch] `_sanitize_tsx_for_babel` mangles valid code and is bypassable [nowing_backend/app/services/web_builder/preview_renderer.py:224-256]
- [x] [Review][Patch] `WebBuilderService` system prompt does not enforce sales/marketing single-page scope [nowing_backend/app/services/web_builder/generator.py:43-78, nowing_backend/app/services/web_builder/generator.py:144-158]
- [x] [Review][Patch] Web Builder chat mode does not restrict agent to `build_web_app` [nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:60-70, nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:572-573]
- [x] [Review][Patch] `resolve_chat_mode` accepts any truthy value as enabled [nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:94-102]
- [x] [Review][Patch] `build_web_app` tool should call the registered capability executor [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:156-157]
- [x] [Review][Patch] `WebAppBuildOutput` validation failures set `message` instead of `error` [nowing_backend/app/services/web_builder/generator.py:250-262, nowing_backend/app/services/web_builder/generator.py:268-282]
- [x] [Review][Patch] `WebAppDeployService.deploy_app` can publish a missing app by writing a default scaffold [nowing_backend/app/services/web_builder/deploy_service.py:68-79]
- [x] [Review][Patch] `disambiguate_slug` can loop unbounded and the suffix can be truncated [nowing_backend/app/services/web_builder/deploy_service.py:19-34, nowing_backend/app/services/web_builder/deploy_service.py:92-97]
- [x] [Review][Patch] `deploy_app` writes snapshot before DB commit and uses generic commit suppression [nowing_backend/app/services/web_builder/deploy_service.py:119-169]
- [x] [Review][Patch] `host_web_app` accepts arbitrary hosts and does not re-check global config [nowing_backend/app/routes/web_builder_routes.py:397-409, nowing_backend/app/routes/web_builder_routes.py:433-437]
- [x] [Review][Patch] Orchestrator recovery path does not re-apply chat mode `enabled_tools` [nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:572-578, nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:876-887]
- [x] [Review][Patch] Empty `platform_metadata: {}` overwrites stored thread mode [nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:344-353]
- [x] [Review][Patch] Short prompts bypass the tool guard and raise Pydantic [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:71-102]
- [x] [Review][Patch] Pydantic schemas lack `max_length` for DB-bound strings [nowing_backend/app/services/web_builder/schemas.py:20-56, nowing_backend/app/db.py:6582-6590]
- [x] [Review][Patch] `WorkspaceApp.slug` is `String(100)` and only per-workspace unique [nowing_backend/app/db.py:6563-6565, nowing_backend/app/db.py:6582-6583, nowing_backend/app/services/web_builder/schemas.py:20-28]
- [x] [Review][Patch] `FILE_STORAGE_LOCAL_PATH` / `WEB_BUILDER_PUBLIC_APPS_PATH` can be relative and CWD-dependent [nowing_backend/app/config/__init__.py:1810-1823, nowing_backend/app/services/web_builder/deploy_service.py:65-66, nowing_backend/app/routes/web_builder_routes.py:439]
- [x] [Review][Patch] Token usage is recorded with hard-coded estimates [nowing_backend/app/services/web_builder/generator.py:377-386, nowing_backend/app/services/web_builder/deploy_service.py:135-142]
- [x] [Review][Patch] `build_web_app` returns a JSON string instead of a structured dict [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:62-69, 157, 163-170]
- [x] [Review][Patch] Mark Tool AST-mutation endpoint is exposed in MVP [nowing_backend/app/routes/web_builder_routes.py:164-173, nowing_backend/app/services/web_builder/mark_tool.py]
- [x] [Review][Patch] Custom-domain binding endpoint is exposed in MVP [nowing_backend/app/routes/web_builder_routes.py:139-161, nowing_backend/app/services/web_builder/deploy_service.py:171-221]
- [x] [Review][Patch] Multi-turn `app_id` refinement is exposed in the chat tool [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:32-37, nowing_backend/app/services/web_builder/generator.py:207-234]

