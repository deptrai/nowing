# Acceptance Auditor Review — Story 27.1a Web Builder Chat Mode MVP (Backend Diff)

**Diff reviewed:** `/_bmad-output/implementation-artifacts/review/27-1a-diff-backend.md`  
**Spec:** `/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md`

## Findings

- **Web Builder chat mode does not restrict the main agent to the `build_web_app` tool.**
  - Violates: AC-1 ("the chat runtime injects ... the `build_web_app` tool"), AD-4 / Technical Requirements (`stream_new_chat` must set `enabled_tools=["build_web_app"]`).
  - Evidence: `nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:60-70` defines the `web_builder` `ChatMode` with `system_prompt` and `workspace_feature_field` but leaves `enabled_tools=None`; `orchestrator.py:572-573` only assigns `effective_enabled_tools` when `chat_mode.enabled_tools is not None`, so the agent is not forced to use `build_web_app`.

- **`resolve_chat_mode` treats any truthy `platform_metadata` value as Web Builder mode, not only boolean `true`.**
  - Violates: AC-1a addendum ("`platform_metadata.web_builder_mode` is not boolean `true` ... is treated as `false`").
  - Evidence: `nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:94-102` uses `if metadata.get(mode.flag_key):` (Python truthiness), so strings/objects/non-empty values would activate web-builder mode.

- **The `build_web_app` chat tool bypasses the existing `web_builder.build_app` capability and `execute_build_app`.**
  - Violates: AC-1 ("the agent calls `build_web_app` (wrapping `web_builder.build_app`)"), Technical Requirements (tool "calls `execute_build_app`").
  - Evidence: `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:156-157` calls `WebBuilderService.generate_project(..., session=session)` directly, not `app.capabilities.web_builder.build_app.executor.execute_build_app`.

- **`WebBuilderService` prompts the LLM for a generic "full-stack web application", with no sales/marketing single-page guardrail or predefined templates.**
  - Violates: AC-2 ("single-page Next.js + Tailwind app ... scoped to one of the predefined templates"), AC-5 (out-of-scope guardrail must respond with a scope message for multi-page/complex backend requests), Technical Requirements ("Override the `WebBuilderService` system prompt with a sales/marketing single-page constraint").
  - Evidence: `nowing_backend/app/services/web_builder/generator.py:43-78` (`_call_llm_for_spec` system instruction says "The user will describe a full-stack web application. Generate a production-ready, beautiful, and fully-functional web application"), and `generator.py:144-158` (`_call_llm_for_refinement`) also lacks the landing/pricing/lead-capture/waitlist/report template constraint and single-page guardrail.

- **Multi-turn `app_id` refinement is exposed in the `build_web_app` tool and `WebBuilderService`, contradicting the single-turn MVP scope.**
  - Violates: Scope IN/OUT table (IN: "Single-turn chat generate"; OUT: "Multi-turn file patch via chat"), story goal ("single-turn, single-page generator"), Technical Requirements (tool accepts only `prompt`, `app_name`, `language`).
  - Evidence: `build_web_app.py:32-37` declares `app_id: str | None = None`; `generator.py:207-234` implements an existing-app branch that calls `_call_llm_for_refinement` and overwrites the project, enabling conversational regeneration.

- **Web Builder REST endpoints do not enforce the per-workspace `Workspace.web_builder_enabled` gate.**
  - Violates: AC-5 ("workspace is on a plan where `WEB_BUILDER_ENABLED=False` ... API returns `403 Forbidden`"), AC-6a ("workspace with `WEB_BUILDER_ENABLED=False` ... any web-builder endpoint ... returns `403`"), Technical Requirements ("Free plan gating: Check `Workspace.web_builder_enabled` or feature flag `WEB_BUILDER_ENABLED`").
  - Evidence: `nowing_backend/app/routes/web_builder_routes.py:58-64` `check_web_builder_enabled()` only checks the global `config.WEB_BUILDER_ENABLED`; `generate_web_app`/`publish_web_app`/`get_workspace_app_preview`/`get_workspace_app_files` call `check_web_builder_enabled()` and `require_workspace_member()` (which only checks the `web_builder:create` permission) but never read `Workspace.web_builder_enabled`. The host route (`:433-437`) and the `build_web_app` tool (`build_web_app.py:119-127`) do check it, making the REST endpoints inconsistent.

- **WorkspaceApp slug is not bounded to 63 DNS label chars and global uniqueness is not enforced at the DB level.**
  - Violates: AC-6 ("service normalizes/truncates to `[a-z0-9-]{1,63}` and disambiguates"), Technical Requirements ("Slug bounds: `WorkspaceApp.slug` `max_length=63`"), Technical Additions ("public URL ... must be unique across all workspaces ... A unique index on `WorkspaceApp.slug` is preferred").
  - Evidence: `nowing_backend/app/db.py:6563-6565` keeps a per-workspace `UniqueConstraint("workspace_id", "slug")`; `app/db.py:6582-6583` keeps `slug = Column(String(100), ...)`. The migration `alembic/versions/232_add_web_builder_enabled_and_permission.py:33-54` does not alter `workspace_apps.slug`. `nowing_backend/app/services/web_builder/schemas.py:20-28` `GeneratedProjectSpec.slug` has no `max_length`/`pattern`. `generator.py:26-32` `slugify()` cleans spaces/underscores but does not truncate to 63.

- **Stored `WorkspaceApp.preview_url` omits the `workspace_id` query parameter now required by the preview endpoint.**
  - Violates: AC-2 ("`preview_url` pointing to the backend preview endpoint"), AC-3 (preview must load from the standalone page).
  - Evidence: `nowing_backend/app/services/web_builder/generator.py:313` builds `preview_url = f"{app_config.BACKEND_URL.rstrip('/')}/api/v1/web-builder/apps/{app_id}/preview"` without `?workspace_id=...`; `nowing_backend/app/routes/web_builder_routes.py:269-277` `get_workspace_app_preview` declares `workspace_id: int` as a required query parameter and `require_workspace_member`. The integration test at `tests/integration/routes/test_web_builder_routes.py:260` is updated to add `?workspace_id=1`, confirming the mismatch.

- **Wildcard host serve route is not mounted at `/` and no ingress rewrite/Traefik config is included.**
  - Violates: AC-4 ("the wildcard router forwards to the backend, the backend reads the `Host` header ... and serves the static HTML"), Technical Requirements ("Backend adds `GET /` with `Host: {slug}.apps.nowing.net` or a dedicated `/host/{slug}` route behind Traefik rewrite").
  - Evidence: `nowing_backend/app/routes/web_builder_routes.py:383` creates `@host_router.get("/web-apps/host")` (mounted at root via `routes/__init__.py:263-265`), but there is no `GET /` handler; the same function is also decorated `@router.get("/host")` (`/api/v1/web-builder/host`), which does not handle `*.apps.nowing.net` root requests. No Traefik/Caddy rewrite configuration appears in the diff.

- **`WebAppDeployService.deploy_app` returns `published` without verifying the wildcard DNS/ingress or setting `public_url_status`.**
  - Violates: AC-4 step 3 ("Ensures `*.apps.nowing.net` wildcard DNS points to the Dokploy/Traefik ingress"), Technical Requirements ("Set `public_url_status` ... and return `published` only after ... a health check via the wildcard route succeeds").
  - Evidence: `nowing_backend/app/services/web_builder/deploy_service.py:118-152` writes the snapshot and immediately returns `status="published"` and `public_url`; there is no DNS/ingress health check and no `public_url_status` field in `WebAppDeployOutput` or `WorkspaceApp`.

- **`PreviewRenderer` CDN fallback cannot display because it is defined in `<head>` before `<div id="root">` exists.**
  - Violates: AC-6 ("the page shows a graceful fallback ... instead of a blank screen"), Review Findings ("`PreviewRenderer` has no CDN-fallback ... Add an inline error/fallback").
  - Evidence: `nowing_backend/app/services/web_builder/preview_renderer.py:77-86` defines `window.__webBuilderCdnFallback` in a `<script>` inside `<head>` and calls `document.getElementById('root')`, but the `<div id="root">` is in `<body>` and not yet in the DOM when the CDN `onerror` handlers fire. The fallback HTML also uses Tailwind utility classes, so if Tailwind itself fails the message is unstyled.

- **The `apply_mark_tool_patch` (AST mutation) endpoint remains active and callable.**
  - Violates: AD-114 ("Mark Tool: only the visual selector is exposed; mutation is out of scope"), Scope IN/OUT table (OUT: "AST mutation / auto-patch from Mark Tool"), Dev Notes ("Mark Tool should remain a read-only selector; do not enable patch in MVP").
  - Evidence: `nowing_backend/app/routes/web_builder_routes.py:164-173` keeps `@router.post("/apps/{app_id}/mark")` with `check_web_builder_enabled()` and `require_workspace_member()` rather than disabling/removing it; `app/routes/web_builder_routes.py:21` still imports `MarkToolASTMutator`.

- **The provided diff is backend-only and omits all required frontend implementation.**
  - Violates: AC-1 (quick chips, `/web` slash prompt, `?mode=web_builder` URL, deliverable card), AC-3 (standalone `/dashboard/[workspace_id]/web-builder` integration), Technical Requirements (frontend entry points, `ArtifactKind.web_app`, `GenerateWebAppToolUI`, `BODY_TOOLS` mapping, artifact panel/collection).
  - Evidence: `27-1a-diff-backend.md` contains only `nowing_backend/` files; no `nowing_web/` changes are present. `chat_modes.py:67` defines `artifact_kinds=["web_app"]` but `orchestrator.py` does not consume `artifact_kinds`, and there is no backend artifact/deliverable plumbing. The `build_web_app` tool returns JSON but the chat deliverable rendering is a frontend responsibility not present in this artifact.

- **`WebBuilderService` validation failures populate `message` while the UI contract expects `error`.**
  - Violates: AC-1 (response stream must surface deliverable/error state correctly), Technical Additions ("Return a `validation_failed` status that `GenerateWebAppToolUI` renders as an error card with a retry prompt and no Publish CTA").
  - Evidence: `nowing_backend/app/services/web_builder/schemas.py:71-72` adds an `error: str | None` field to `WebAppBuildOutput`, but `generator.py:250-262` and `generator.py:268-282` set `status="validation_failed"` with `message=...` and leave `error=None`. The `build_web_app` tool sets `error` for its own input validation (`build_web_app.py:67-69`, `:125-127`, `:204-208`) but passes through service-generated failures that lack the field.

- **`WebAppDeployService.deploy_app` can publish an app that has no valid source files by writing a default scaffold into the public snapshot directory.**
  - Violates: AC-4 ("Given a generated app with valid files and no slug collision"), Technical Requirements (save snapshot keyed by slug, not create a fallback project in the public path).
  - Evidence: `nowing_backend/app/services/web_builder/deploy_service.py:68-79` falls back to `project_path = public_apps_base / str(workspace_id) / app_id` and calls `ProjectWriter.write_minimal_nextjs_scaffold(...)` when `app_entity.storage_path` is missing, then renders and publishes that fallback. This mixes source and published snapshot paths and can publish a generic page for an un-generated/missing app.
