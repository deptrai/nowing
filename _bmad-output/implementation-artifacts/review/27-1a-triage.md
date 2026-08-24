# Triage Report — Code Review 27.1a Web Builder Chat Mode MVP

**Story:** `27-1a-web-builder-chat-mode-sales-marketing-mvp.md`  
**Diff:** `27-1a-diff-backend.md`  
**Review date:** 2026-08-21  
**Layers run:** Blind Hunter, Edge Case Hunter, Acceptance Auditor  
**Failed layers:** none

## Summary

| Bucket | Count | Severity breakdown |
|---|---|---|
| `decision-needed` | 0 | — |
| `patch` | 28 | 12 high, 14 medium, 2 low |
| `defer` | 3 | 2 high, 1 medium |
| `dismiss` | 3 | — |

**Total actionable findings:** 31  
**Resolved decisions:** 4  
**Dismissed as noise/false-positive:** 3

---

## `decision-needed` (must be resolved before patches)

### D1 — Frontend implementation is missing from the reviewed diff
- **Source:** acceptance-auditor
- **Severity:** high
- **Location:** `nowing_web/` (none in diff)
- **Detail:** The AC and technical requirements require chat quick chips, `/web` slash prompt templates, `?mode=web_builder` URL handling, `ArtifactKind.web_app`, `GenerateWebAppToolUI`, `BODY_TOOLS` mapping, and the standalone page integration. The reviewed diff only contains `nowing_backend/` changes, so the feature is not reachable through the chat UI.
- **Options:**
  1. Implement the frontend work now as part of 27.1a.
  2. Split the frontend into a follow-up story and keep 27.1a backend-only (this would require updating the spec/AC).

### D2 — Content-Security-Policy is intentionally broad for generated/published apps
- **Source:** blind + edge
- **Severity:** high
- **Location:** `nowing_backend/app/services/web_builder/preview_renderer.py:19-26`
- **Detail:** CSP allows `https:` for default-src, img-src, font-src, connect-src, plus `unsafe-inline`/`unsafe-eval` scripts from unpkg and cdn.tailwindcss.com. This lets generated pages load arbitrary third-party scripts, post to any HTTPS endpoint, and use `eval`, creating XSS and data-exfiltration paths. Tightening it will likely break Tailwind/React/Babel CDN execution or restrict lead-form analytics.
- **Options:**
  1. Keep the broad CSP for the MVP and document the security trade-off / per-app allow-list as future work.
  2. Tighten to a strict allow-list of required CDN origins and remove `unsafe-eval`/`unsafe-inline`, accepting that some generated previews may break until the sanitizer/Babel pipeline is hardened.

### D3 — Plan gating defaults are `True` for every workspace
- **Source:** blind + edge
- **Severity:** high
- **Location:** `nowing_backend/app/config/__init__.py:1816`, `nowing_backend/app/db.py:1948-1950`, `alembic/versions/232_add_web_builder_enabled_and_permission.py:46-48`
- **Detail:** `WEB_BUILDER_ENABLED`, `Workspace.web_builder_enabled`, and the migration `server_default` are all `true`. This makes the feature available to all workspaces regardless of plan, contradicting the free-plan gating in AC-5 and the Technical Requirements. Turning it off by default requires a plan-aware backfill or explicit enablement logic.
- **Options:**
  1. Set `Workspace.web_builder_enabled` default to `false` and backfill only paid/allowed plan tiers.
  2. Keep defaults `true` and rely on `WorkspaceLimits` or a separate plan-entitlement service (out of this diff’s scope).

### D4 — `WebAppDeployService` returns `published` without DNS/ingress verification
- **Source:** acceptance-auditor
- **Severity:** medium
- **Location:** `nowing_backend/app/services/web_builder/deploy_service.py:118-152`
- **Detail:** AC-4 step 3 and the Technical Requirements ask to ensure `*.apps.nowing.net` DNS and to set a `public_url_status`. The code writes the snapshot and immediately returns `published`. There is no `public_url_status` column or schema field.
- **Options:**
  1. Add a lightweight `public_url_status` column and set it to `verified` after a best-effort HTTP GET to the public URL.
  2. Trust external DNS/ingress configuration and add `public_url_status` as a manual/admin-managed field without runtime verification.

---

## `patch` (fixable without further human input)

### P1 — `build_web_app` chat tool membership check is fail-open
- **Source:** blind + edge
- **Severity:** high
- **Location:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:140-154`
- **Detail:** `if membership and not (...)` allows generation when `membership` is `None` (invalid/missing `user_id` or non-member). It also checks only `is_owner` and the literal `web_builder:create` permission; a role with `FULL_ACCESS` (`*`) is denied. Combined with the invalid-`user_id` handling at lines 23-29, an unauthenticated or removed user can create apps.
- **Suggested fix:** Fail closed: deny if `membership` is `None`; allow if `membership.is_owner`, `Permission.FULL_ACCESS in role.permissions`, or `web_builder:create` in role.permissions.

### P2 — REST endpoints do not enforce per-workspace `Workspace.web_builder_enabled`
- **Source:** blind + edge + auditor
- **Severity:** high
- **Location:** `nowing_backend/app/routes/web_builder_routes.py:58-64` and all callers (`generate`, `publish`, `list`, `get`, `preview`, `files`)
- **Detail:** `check_web_builder_enabled()` only checks the global `config.WEB_BUILDER_ENABLED`. It never reads `Workspace.web_builder_enabled`, so a workspace with the feature disabled can still generate/list/preview/publish if the user has `WEB_BUILDER_CREATE`.
- **Suggested fix:** Load the workspace in the route and fail closed when `workspace.web_builder_enabled is False`; align with `is_chat_mode_enabled`.

### P3 — `WebAppDeployService.deploy_app` does not verify the workspace gate
- **Source:** blind
- **Severity:** high
- **Location:** `nowing_backend/app/services/web_builder/deploy_service.py:43-144`
- **Detail:** The service loads only the `WorkspaceApp` and writes the public snapshot without checking `Workspace.web_builder_enabled`. If the REST route is bypassed or another caller uses the service directly, the workspace flag is ignored.
- **Suggested fix:** Load `Workspace` inside `deploy_app` and `verify_and_bind_custom_domain` and raise/return failed when `web_builder_enabled is False`.

### P4 — Public host route is not at `/`
- **Source:** blind + edge + auditor
- **Severity:** high
- **Location:** `nowing_backend/app/routes/web_builder_routes.py:383` and `nowing_backend/app/routes/__init__.py:264`
- **Detail:** `host_router` is mounted at root but registers `GET /web-apps/host`, while `public_url` and the AC use `https://{slug}.apps.nowing.net/` (root). Unless an external ingress rewrites `/` to `/web-apps/host`, all public URLs 404.
- **Suggested fix:** Change `@host_router.get("/web-apps/host")` to `@host_router.get("/")` and keep the `Host` header/slug logic. Document or provide the Traefik/Caddy wildcard rewrite as secondary infra.

### P5 — Stored `preview_url` omits the required `workspace_id` query parameter
- **Source:** blind + edge + auditor
- **Severity:** high
- **Location:** `nowing_backend/app/services/web_builder/generator.py:313` and `generator.py:518`
- **Detail:** `get_workspace_app_preview` declares `workspace_id: int` as a required query parameter. The stored `preview_url` and the streaming `complete_payload` omit `?workspace_id=...`, so the preview endpoint returns 422.
- **Suggested fix:** Build `preview_url` as `.../api/v1/web-builder/apps/{app_id}/preview?workspace_id={workspace_id}`.

### P6 — `get_workspace_app_preview` 500 when `storage_path` is `None`
- **Source:** blind + edge
- **Severity:** high
- **Location:** `nowing_backend/app/routes/web_builder_routes.py:290-308`
- **Detail:** `project_dir` is only assigned inside `if app_entity.storage_path:`. If `storage_path` is `None`, the subsequent `if not project_dir.exists()` raises `UnboundLocalError` instead of 404.
- **Suggested fix:** Add an `else` branch that returns 404 or computes a safe fallback path.

### P7 — `PreviewRenderer` CDN fallback cannot render
- **Source:** acceptance-auditor
- **Severity:** medium
- **Location:** `nowing_backend/app/services/web_builder/preview_renderer.py:77-86`
- **Detail:** The fallback script lives in `<head>` and immediately calls `document.getElementById('root')`, but `<div id="root">` is in `<body>`. The fallback also uses Tailwind classes, so if Tailwind is the failed CDN the message is unstyled.
- **Suggested fix:** Move the fallback inline script after `<div id="root">` or wrap it in `window.addEventListener('load', ...)`. Use plain, non-Tailwind styles.

### P8 — `_sanitize_tsx_for_babel` mangles valid code and is bypassable
- **Source:** blind + edge
- **Severity:** high
- **Location:** `nowing_backend/app/services/web_builder/preview_renderer.py:224-256`
- **Detail:** The type-annotation regex `re.sub(r":\s*[A-Za-z_]...", "", code)` strips any colon-word, breaking object literals (`style={{ color: red }}`), JSX default props, and normal code. `document.cookie` replacement creates `'' = 'x'`. It does not cover `window.document.cookie`, `document["cookie"]`, `import("https://...")`, `require(...)`, or `</script >` variants.
- **Suggested fix:** Replace the regex with a lightweight TypeScript/JSX transformer (e.g. `babel` or a targeted parser) and a deny-list for storage/API accesses; or at minimum fix the regexes and add tests for the known bypasses.

### P9 — `WebBuilderService` system prompt does not enforce sales/marketing single-page scope
- **Source:** acceptance-auditor
- **Severity:** high
- **Location:** `nowing_backend/app/services/web_builder/generator.py:43-78` and `generator.py:144-158`
- **Detail:** The system prompt asks for a generic full-stack web application and does not list the sales/marketing templates (landing, pricing, lead capture, waitlist, report) or the single-page guardrail required by AC-2/AC-5.
- **Suggested fix:** Override the system prompt with a sales/marketing single-page constraint and the five templates; add an out-of-scope guardrail message for multi-page/complex backend requests.

### P10 — Web Builder chat mode does not restrict agent to `build_web_app`
- **Source:** acceptance-auditor
- **Severity:** high
- **Location:** `nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:60-70` and `orchestrator.py:572-573`
- **Detail:** The `web_builder` `ChatMode` has `enabled_tools=None`, so the orchestrator does not override the agent tool list. The agent may call other tools.
- **Suggested fix:** Set `enabled_tools=["build_web_app"]` in `CHAT_MODES["web_builder"]`.

### P11 — `resolve_chat_mode` accepts any truthy value as enabled
- **Source:** blind + edge + auditor
- **Severity:** medium
- **Location:** `nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:94-102`
- **Detail:** `if metadata.get(mode.flag_key):` treats strings/objects/non-empty values as true. AC-1a explicitly requires only boolean `true` to enable the mode.
- **Suggested fix:** Require `metadata.get(mode.flag_key) is True` and enforce mutual exclusivity (e.g. raise/return default if more than one flag is `True`).

### P12 — `build_web_app` tool should call the registered capability executor
- **Source:** acceptance-auditor
- **Severity:** medium
- **Location:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:156-157`
- **Detail:** The tool calls `WebBuilderService.generate_project` directly instead of `app.capabilities.web_builder.build_app.executor.execute_build_app`, bypassing capability-level validation, metering, and audit.
- **Suggested fix:** Route the tool through the existing `web_builder.build_app` capability executor.

### P13 — `WebAppBuildOutput` validation failures set `message` instead of `error`
- **Source:** acceptance-auditor
- **Severity:** medium
- **Location:** `nowing_backend/app/services/web_builder/generator.py:250-262` and `generator.py:268-282`
- **Detail:** The schema has an `error` field and the Technical Additions specify `validation_failed` with an `error` for the UI. The service sets `message` and leaves `error=None` for LLM/spec failures.
- **Suggested fix:** Set `error` on validation failures and keep `message` as the human-readable detail.

### P14 — `WebAppDeployService.deploy_app` can publish a missing app by writing a default scaffold
- **Source:** acceptance-auditor + edge
- **Severity:** high
- **Location:** `nowing_backend/app/services/web_builder/deploy_service.py:68-79`
- **Detail:** When `app_entity` is missing or `storage_path` is `None`, the service falls back to `public_apps_base / {workspace_id} / {app_id}`, writes a minimal scaffold, and publishes it. This mixes source and published snapshots and can publish a generic page for an un-generated app.
- **Suggested fix:** Return `deploy_failed` if the app source directory does not exist or is empty; do not create a fallback scaffold.

### P15 — `disambiguate_slug` can loop unbounded and the suffix can be truncated
- **Source:** blind + edge
- **Severity:** medium
- **Location:** `nowing_backend/app/services/web_builder/deploy_service.py:19-34` and `deploy_service.py:92-97`
- **Detail:** The `while` loop has no iteration cap; a hot collision can run indefinitely. The caller then re-sanitizes and `[:63].strip("-")`, which can remove the numeric suffix and re-create a collision or overwrite an existing app.
- **Suggested fix:** Cap the loop, re-use the disambiguated slug without re-sanitizing, and ensure the final slug is always `<=63` characters before adding the suffix.

### P16 — `deploy_app` writes snapshot before DB commit and uses generic commit suppression
- **Source:** blind
- **Severity:** medium
- **Location:** `nowing_backend/app/services/web_builder/deploy_service.py:119-169`
- **Detail:** The snapshot file is written inside the same `try` as the DB update. If an exception occurs after write but before `return`, the file is on disk while `WorkspaceApp.status` is `deploy_failed`. The `with contextlib.suppress(Exception): await session.commit()` can also flush unrelated uncommitted state from the caller.
- **Suggested fix:** Separate file I/O from DB commit; commit the DB transaction before writing the snapshot, and keep the file write outside the generic `except`.

### P17 — `host_web_app` accepts arbitrary hosts and does not re-check global config
- **Source:** blind + edge
- **Severity:** medium
- **Location:** `nowing_backend/app/routes/web_builder_routes.py:397-409` and `web_builder_routes.py:433-437`
- **Detail:** When `HOSTING_BASE_DOMAIN` is empty, the base-domain check is skipped and any two-part `Host` is accepted. It also does not verify that `config.WEB_BUILDER_ENABLED` is true or that exactly one label precedes the base domain.
- **Suggested fix:** Always enforce a non-empty base domain; reject hosts with extra sub-labels; check `config.WEB_BUILDER_ENABLED` at the top of the handler.

### P18 — Orchestrator recovery path does not re-apply chat mode `enabled_tools`
- **Source:** edge
- **Severity:** medium
- **Location:** `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:572-578` and `orchestrator.py:876-887`
- **Detail:** If a provider rate-limit triggers `reroute_to_next_auto_pin` and `_merge_registry_agent_config`, the agent is rebuilt with the registry’s full tool list. The chat-mode `enabled_tools` override is not re-applied.
- **Suggested fix:** Re-apply `chat_mode.enabled_tools` after the recovery rebuild.

### P19 — Empty `platform_metadata: {}` overwrites stored thread mode
- **Source:** edge
- **Severity:** medium
- **Location:** `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py:344-353`
- **Detail:** `if platform_metadata is not None:` overwrites `chat_thread.platform_metadata` even for an empty dict. On a follow-up turn this causes `resolve_chat_mode` to fall back to `default`.
- **Suggested fix:** Treat empty dict as missing and fall back to the thread’s stored metadata.

### P20 — Short prompts bypass the tool guard and raise Pydantic
- **Source:** edge
- **Severity:** low
- **Location:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:71-102`
- **Detail:** The tool checks `if not prompt or not prompt.strip():` but `WebAppBuildInput.prompt` has `min_length=3`. A 1–2 character prompt raises inside Pydantic, caught by the outer `except` and returned as `status="error"` instead of `validation_failed`.
- **Suggested fix:** Rely on Pydantic validation or add an explicit `len(prompt) < 3` check with a `validation_failed` return.

### P21 — Pydantic schemas lack `max_length` for DB-bound strings
- **Source:** edge
- **Severity:** medium
- **Location:** `nowing_backend/app/services/web_builder/schemas.py:20-56` and `nowing_backend/app/db.py:6582-6590`
- **Detail:** `GeneratedProjectSpec.name`/`slug`/`description`, `WebAppBuildInput.app_name`/`language`, and `WebAppBuildOutput` fields have no `max_length`. DB columns are `name String(255)`, `slug String(100)`, `language String(10)`. Oversized LLM output can cause 500s or silent truncation.
- **Suggested fix:** Add `max_length`/`pattern` to Pydantic and truncate/validate before DB inserts.

### P22 — `WorkspaceApp.slug` is `String(100)` and only per-workspace unique
- **Source:** acceptance-auditor + edge
- **Severity:** medium
- **Location:** `nowing_backend/app/db.py:6563-6565`, `nowing_backend/app/db.py:6582-6583`, `nowing_backend/app/services/web_builder/schemas.py:20-28`
- **Detail:** The slug column is 100 chars and has a per-workspace unique constraint. Public URLs require global uniqueness and a 63-char DNS label limit. The Pydantic `GeneratedProjectSpec.slug` also has no `max_length`/`pattern`.
- **Suggested fix:** Change `WorkspaceApp.slug` to `String(63)`, add a global unique index (or partial index on `status='published'`), and add Pydantic validation.

### P23 — `FILE_STORAGE_LOCAL_PATH` / `WEB_BUILDER_PUBLIC_APPS_PATH` can be relative and CWD-dependent
- **Source:** edge
- **Severity:** medium
- **Location:** `nowing_backend/app/config/__init__.py:1810-1823`, `nowing_backend/app/services/web_builder/deploy_service.py:65-66`, `nowing_backend/app/routes/web_builder_routes.py:439`
- **Detail:** The default is `./.local_object_store` when `/app` is absent. `Path(...).resolve()` depends on the process CWD, so a worker may write snapshots where the web server cannot find them.
- **Suggested fix:** Anchor the default to `BASE_DIR` (project root) so it is CWD-independent.

### P24 — Token usage is recorded with hard-coded estimates
- **Source:** blind
- **Severity:** medium
- **Location:** `nowing_backend/app/services/web_builder/generator.py:377-386` and `deploy_service.py:135-142`
- **Detail:** `prompt_tokens=500`, `completion_tokens=2000`, `cost_micros=15000` for generate and `0` for deploy are not actual usage. Billing and workspace limits may be inaccurate.
- **Suggested fix:** Capture real token counts from LLM responses where available; for deploy use a configured platform fee and record it explicitly.

### P25 — `build_web_app` returns a JSON string instead of a structured dict
- **Source:** blind
- **Severity:** low
- **Location:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:62-69, 157, 163-170`
- **Detail:** The LangChain tool returns `WebAppBuildOutput(...).model_dump_json()`. Other chat tools return `dict`s, and the deliverable/artifact extraction path may fail to parse `app_id`, `preview_url`, and `public_url`.
- **Suggested fix:** Return `WebAppBuildOutput(...).model_dump()` if LangChain and the orchestrator accept dict results; otherwise ensure the downstream deliverable parser handles JSON strings.

### P26 — Mark Tool AST-mutation endpoint is exposed in MVP
- **Source:** acceptance-auditor
- **Severity:** medium
- **Location:** `nowing_backend/app/routes/web_builder_routes.py:164-173`, `nowing_backend/app/services/web_builder/mark_tool.py`
- **Detail:** `apply_mark_tool_patch` is a POST endpoint that writes patched code back to disk. The story scope (OUT table and Dev Notes) says AST mutation / auto-patch from Mark Tool is out of 27.1a; only the visual selector is in scope.
- **Suggested fix:** Disable the POST endpoint (return 501/403) or remove it; keep the client-side visual selector in `PreviewRenderer`.

### P27 — Custom-domain binding endpoint is exposed in MVP
- **Source:** edge
- **Severity:** medium
- **Location:** `nowing_backend/app/routes/web_builder_routes.py:139-161`, `nowing_backend/app/services/web_builder/deploy_service.py:171-221`
- **Detail:** `verify_and_bind_custom_domain` persists any string as an active custom domain with no CNAME or ownership check. Custom CNAME is OUT of the 27.1a scope per the IN/OUT table (Option A uses `*.apps.nowing.net`).
- **Suggested fix:** Disable the custom-domain endpoint for 27.1a (return 501/403) and remove the partial custom-domain serving logic in `host_web_app`.

### P28 — Multi-turn `app_id` refinement is exposed in the chat tool
- **Source:** acceptance-auditor
- **Severity:** high
- **Location:** `nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py:32-37`, `nowing_backend/app/services/web_builder/generator.py:207-234`
- **Detail:** The `build_web_app` tool accepts an `app_id` argument and `generate_project` implements an existing-app refinement branch. The story scope explicitly says single-turn chat generate and marks multi-turn file patch as OUT.
- **Suggested fix:** Remove `app_id` from the chat tool signature and the refinement branch in `WebBuilderService`; generate a new `WorkspaceApp` on every call, or defer a proper multi-turn refinement to Story 27.4.

---

## `dismiss` (noise / false positive)

### R1 — `is_chat_mode_enabled` docstring contradicts implementation
- **Source:** blind
- **Severity:** low
- **Reason:** The fail-closed behavior is correct; the docstring is stale. This is a documentation cleanup, not a user-facing security or functionality issue.

### R2 — `WorkspaceMembership` `user_id == None` query
- **Source:** blind
- **Severity:** low
- **Reason:** This is a symptom of the fail-open membership check (P1), not a separate issue. Dismissed as duplicate detail.
