---
baseline_commit: be2efe015
story_key: "27-2a"
epic: "epic-27"
story: "27.2a"
title: "Manus Slides Presentation Studio from Chat (PPTX/Marp)"
status: "ready-for-dev"
---

# Story 27.2a: Manus Slides Presentation Studio from Chat (PPTX/Marp)

**Status:** `ready-for-dev`  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Priority:** P1  
**Scope:** MVP chat-first slice for slide-deck generation. Generate PPTX or Marp Markdown from a chat prompt, render as an artifact card, and let the user download / open the deck.  
**Related Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> — 27.1a chat-mode/tool-binding pattern.  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, FR-94; AD-112, AD-114).  
**Replaces part of:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-2-manus-slides-presentation-studio-speaker-diarization.md" /> — this story takes the PPTX/Marp slice.

## Story

As a **sales or marketing user**,  
I want to describe a slide deck in natural language from the chat (or via a quick chip/URL),  
So that the agent generates a PPTX 16:9 deck or a Marp-compatible Markdown deck and surfaces it as a downloadable deliverable in the chat.

## Goal

- **Chat-first, like 27.1a:** the thread can be tagged with `platform_metadata.presentation_studio_mode=true` via a quick chip, `/slides` slash prompt, or `?mode=presentation_studio` URL.
- **Single-turn MVP:** user describes the deck → agent calls `generate_presentation` → deliverable card appears in chat.
- **Two output formats:** `.pptx` (for PowerPoint/Google Slides) and `.md` (Marp-compatible).
- **Standalone page optional:** `/dashboard/[workspace_id]/presentations` can list all generated decks; chat is the primary entry point for v1.

## UX Review Notes

- **Artifact group naming:** the existing `video` artifact kind is labeled **"Presentations"**. When adding `presentation`, rename `video` → **"Video Presentations"** and the new `presentation` kind → **"Slide Decks"** to avoid two groups with the same name.
- **Output format UX:** do not rely on the user typing "Marp slides". Provide quick chips `Create a pitch deck (PPTX)` and `Create Marp slides`, plus slash templates `/slides pptx` and `/slides marp`. The `output_format` parameter is set by the chosen entry point.
- **PPTX preview realism:** PPTX cannot be rendered inline reliably. The deliverable card shows **"Download .pptx"** as the primary CTA. A secondary **"Open in Slides"** link (Google Slides / PowerPoint online) is acceptable; true preview is out-of-scope for MVP.
- **Marp preview fallback:** if `marp-cli` is installed, render a HTML preview; otherwise show **"Download .md"** and a helper line *"Open this file in Marp for VS Code / Marp Web."*
- **Quick chip copy (bilingual):**
  - English: "Create a pitch deck"
  - Vietnamese: "Tạo slide pitch"
- **Prompt picker mode:** extend `PromptPickerAction` / `BuiltinPromptItem` from a boolean `isWebBuilder` to a `mode` string so `/slides` slash templates can set `?mode=presentation_studio`.
- **Loading / error / degraded copy:**
  - Generating: *"Designing your slides…"* / *"Đang thiết kế slide…"*
  - Dependency missing: *"Slide studio is not available on this workspace plan or installation."*
  - Validation failed: *"Could not generate a valid deck from that description. Try a more specific outline."*

## Architecture Review Notes

- **Avoid chat-mode if-else chains:** 27.1a currently hardcodes `web_builder_mode` in `orchestrator.py`. Adding `presentation_studio_mode` and `meeting_minutes_mode` on top would create a 3-way `if/elif`. Use a generic `ChatMode` registry instead:
  - `app/tasks/chat/streaming/flows/new_chat/chat_modes.py` maps `mode` → `{ enabled_tools, system_prompt_prefix, feature_flag, error_code }`.
  - `orchestrator.py` looks up the registry and applies it without new branches.
- **Do not exec LLM output:** `python-pptx` is safe, but only if the LLM outputs a **structured JSON deck spec** (slide list, titles, bullets, chart data) that the service maps to `pptx` objects. Never `exec()` or `eval()` generated Python/Marp code. See <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py" lines="49-73" /> for the validation-first pattern.
- **Typed tool output with status/error:** follow the 27.1a fix for `build_web_app`: return a Pydantic output (`GeneratePresentationOutput` / `WebAppBuildOutput`) with `status: "validation_failed" | "error" | "ready"` and `error` field. Do not return raw error strings; the frontend card uses `status` to render error state.
- **Tool session handling:** like `build_web_app`, do not call `session.commit()` in the tool after the service commits. Let `WebBuilderService` / `PresentationStudioService` own the unit of work and rollback on exception. The tool only opens the session and returns `result.model_dump_json()`.
- **User ID parsing:** `deps["user_id"]` may arrive as `UUID` or `str`. Use the same guard as <ref_snippet file="/Users/luisphan/Documents/GitHub/nowing/nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py" lines="21-34" />.
- **Slug disambiguation:** `SlidePresentation.slug` must be workspace-unique. Before insert, call a `disambiguate_slug` helper that appends a short hash if the slug already exists, mirroring `WorkspaceApp`.
- **`enabled_tools` should not isolate the agent:** the mode should inject a system prompt and keep base tools available (`memory`, `search`, etc.). Do not set `enabled_tools=["generate_presentation"]` exclusively; use a nudge prompt unless the product explicitly wants a single-tool thread.
- **Cross-cutting artifact system change:** adding `presentation` to `ArtifactKind` touches `model/artifact.ts`, `ARTIFACT_TOOL_KINDS`, `BODY_TOOLS`, `KIND_META`, `GROUP_ORDER`, `collect-artifacts.ts`, and potentially `artifacts-library`. Treat this as **Step 0** and land before the deliverable card.
- **Feature gate on all routes:** every `POST/GET/PUT/DELETE` in `app/routes/presentation_routes.py` must check `PRESENTATION_STUDIO_ENABLED` and return 403 if disabled, not just the chat tool.
- **Prompt validation returns typed output:** if `prompt` is empty or too long, return `GeneratePresentationOutput(status="validation_failed", error="...").model_dump_json()` instead of a string. This keeps the deliverable card from hanging.
- **Marp preview subprocess safety:** if `marp-cli` is invoked, run it in a temp directory, set a short timeout, validate output, and never pipe user input directly into shell arguments.

## Architecture Alignment (Nowing Spine)

| AD | Invariant | Alignment | Required action |
|---|---|---|---|
| AD-1 | Monolith module hóa | `PresentationStudioService` lives in `app/services/`, tool in `app/agents/`, routes in `app/routes/`. No new service. | ✅ None |
| AD-2 | Async SQLA + Alembic + pgvector | New `SlidePresentation` table, `AsyncSession`, Alembic migration. | ✅ None |
| AD-4 | Tool registry + permission middleware | Tool registered via `main_agent/tools/registry.py`; must log `AgentActionLog` and honor `PermissionMiddleware` on mutations. | ⚠️ Add `AgentActionLog` write and workspace auth to all `presentation_routes.py`. |
| AD-5 | Zero sync real-time | Deliverable generated in seconds; no long-running state. | ✅ None |
| AD-6 | Next.js server proxy | Frontend uses existing `/api/v1` proxy. | ✅ None |
| AD-8 | Unified credit wallet, real cost | `TokenUsage.cost_micros` recorded post-generation; no flat billing. | ✅ None |
| AD-9 | RBAC 3 roles | All REST routes must call `require_workspace_member` like `web_builder_routes.py`. | ⚠️ Add `require_workspace_member` to `presentation_routes.py`. |
| AD-10 | Token usage per msg/ws/user | `usage_type="presentation_generate"` recorded. | ✅ None |
| AD-16 | License boundary | `python-pptx` MIT, `marp-cli` MIT; code in `app/services/` (Apache/MIT), not `app/proprietary/`. | ✅ None |
| AD-17 | Async door | Generation is fast enough to stay sync (<10s target). No new async flow needed. | ✅ None |
| AD-21 | Client tab state pointer-only | `?mode=presentation_studio` is URL pointer; no local storage state. | ✅ None |
| AD-30 | AgentConfig registry | Mode mapping goes through `ChatMode` registry, not hardcoded `if/elif` in `orchestrator.py`. | ⚠️ Create `app/tasks/chat/streaming/flows/new_chat/chat_modes.py`. |

### Alignment action items for 27.2a

1. Add `require_workspace_member` dependency to all `presentation_routes.py` endpoints.
2. Write `AgentActionLog` entries for `generate_presentation` tool calls.
3. Implement `ChatMode` registry and avoid a hardcoded `if is_presentation_studio_mode` block in `orchestrator.py`.

## [BUILT] vs [GAP]

### [BUILT] — patterns to reuse

- **Video presentation model + routes** (`app/db.py:1682-1721`, `app/routes/video_presentations_routes.py`). `VideoPresentation` has `workspace_id`, `thread_id`, `title`, `status`, JSON `slides`. Good template for a `SlidePresentation` table.
- **Report / deliverable pattern** (`app/routes/reports_routes.py`, `app/routes/export_routes.py`, `app/db.py:1724-1760`). Pandoc/Typst export flow, file storage under `FILE_STORAGE_LOCAL_PATH`, download/preview URLs.
- **Chat tool + artifact pattern from 27.1a:** `build_web_app` in `app/agents/chat/multi_agent_chat/main_agent/tools/web_builder/build_web_app.py`, `BODY_TOOLS` and `ARTIFACT_TOOL_KINDS` in `nowing_web/components/assistant-ui/assistant-message.tsx` and `nowing_web/features/chat-artifacts/model/artifact.ts`.
- **Tool registry** (`app/agents/chat/multi_agent_chat/main_agent/tools/index.py` and `registry.py`): adding a new `generate_presentation` tool follows the same 3-line registration as `build_web_app`.
- **TokenUsage / cost tracking** (`app/services/token_tracking_service.py`, `app/db.py:1200-1293`): record `usage_type` and `cost_micros` post-hoc.
- **Chat mode gating** (`app/config/__init__.py`, `app/routes/new_chat_routes.py`, `app/tasks/chat/streaming/flows/new_chat/orchestrator.py`): reuse `WEB_BUILDER_ENABLED` pattern for `PRESENTATION_STUDIO_ENABLED`.
- **Workspace-scoped RBAC + slug uniqueness** (`WorkspaceApp.slug`, `app/db.py` unique pattern).

### [GAP] — new work

1. **Config + feature gate** (`app/config/__init__.py`):
   - `PRESENTATION_STUDIO_ENABLED = os.getenv("PRESENTATION_STUDIO_ENABLED", "TRUE").upper() == "TRUE"`
   - `PRESENTATION_MAX_PROMPT_CHARS` and `PRESENTATION_FILE_STORAGE_SUBDIR` (default `presentations/`).

2. **Database model** (`app/db.py` + alembic migration):
   - New `SlidePresentation` table: `id` (UUID PK), `workspace_id`, `user_id`, `thread_id`, `title`, `slug`, `format` (`pptx` | `marp`), `status` (`generating` | `ready` | `failed`), `file_path`, `download_url`, `preview_url`, `metadata` (JSONB slide count/theme), `created_at`, `updated_at`.
   - `Workspace.slide_presentations` relationship.

3. **Generation service** (`app/services/presentation/`):
   - `PresentationStudioService` with two output drivers:
     - **PPTX driver:** `python-pptx` → `Presentation` object, 16:9 `SLIDE_WIDTH/HEIGHT`, title/bullet/content placeholders, chart placeholder (`python-pptx.chart` optional), speaker notes.
     - **Marp driver:** render Marp-flavored Markdown (`---` slide separators, `theme`, `class` directives). Provide a raw `.md` and optionally call `marp-cli` (Node) to render to HTML/PDF if installed.
   - Prompt template for LLM: receive outline/theme and output structured deck spec (slides with title, bullets, notes, optional chart config).
   - Save generated file to `FILE_STORAGE_LOCAL_PATH/presentations/{workspace_id}/{presentation_id}/{slug}.{format}`.

4. **Pydantic schemas** (`app/services/presentation/schemas.py`):
   - `GeneratePresentationInput`: `prompt`, `workspace_id`, `user_id` (UUID), `output_format` (`pptx` | `marp`), `title` (optional), `language`.
   - `GeneratePresentationOutput`: `presentation_id`, `title`, `slug`, `format`, `status`, `download_url`, `preview_url`, `slide_count`.

5. **LangChain tool** (`app/agents/chat/multi_agent_chat/main_agent/tools/presentation/generate_presentation.py`):
   - Factory `create_generate_presentation_tool(deps)`.
   - Tool `generate_presentation(prompt, output_format="pptx", title=None, language="en")`.
   - Truncates prompt to `PRESENTATION_MAX_PROMPT_CHARS`.
   - Calls `PresentationStudioService` with a fresh `async_session_maker()` session.
   - Returns `GeneratePresentationOutput.model_dump_json()`.

6. **Tool registration** (`app/agents/chat/multi_agent_chat/main_agent/tools/index.py` and `registry.py`):
   - Add `generate_presentation` to `MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED`.
   - Register in `MAIN_AGENT_NOWING_TOOL_FACTORIES` with required deps `("workspace_id", "user_id")`.

7. **Chat mode wiring** (`app/routes/new_chat_routes.py`, `app/tasks/chat/streaming/flows/new_chat/orchestrator.py`):
   - Allow `platform_metadata.presentation_studio_mode=true` on thread creation.
   - 403 if `PRESENTATION_STUDIO_ENABLED=false`.
   - In `stream_new_chat`, when `presentation_studio_mode` is true, set `enabled_tools=["generate_presentation"]`, prepend a brief system prompt for slide-deck generation.
   - Per-turn override + thread fallback, like 27.1a.

8. **Frontend deliverable card** (`nowing_web/components/tool-ui/presentation.tsx` new file):
   - `GeneratePresentationToolUI` shows title, format icon (PPTX/Marp), slide count, Download button, Open Preview button.
   - States: `generating`, `ready`, `error`.

9. **Artifact mapping** (`nowing_web/components/assistant-ui/assistant-message.tsx`, `nowing_web/features/chat-artifacts/model/artifact.ts`, `nowing_web/features/chat-artifacts/ui/artifact-row.tsx`, `nowing_web/features/chat-artifacts/ui/artifacts-panel.tsx`, `nowing_web/features/chat-artifacts/lib/collect-artifacts.ts`):
   - Add `"presentation"` to `ArtifactKind`.
   - Map `generate_presentation: "presentation"` in `ARTIFACT_TOOL_KINDS` and `BODY_TOOLS`.
   - Add `KIND_META.presentation` icon and `GROUP_ORDER` entry.
   - Add `describeArtifact` case for `presentation`.

10. **Chat entry points** (`nowing_web/app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx`, `nowing_web/components/assistant-ui/thread.tsx`, `nowing_web/components/new-chat/prompt-picker.tsx`):
    - Quick chip "Create slide deck".
    - Slash prompt `/slides` with templates (sales pitch, pricing, report, pitch deck).
    - URL query `?mode=presentation_studio&q=...` pre-fills composer.

11. **REST routes for download/preview/list** (`app/routes/presentation_routes.py`):
    - `GET /api/v1/presentations` (list workspace decks).
    - `GET /api/v1/presentations/{presentation_id}` (read).
    - `GET /api/v1/presentations/{presentation_id}/download` (return `FileResponse` or redirect).
    - `GET /api/v1/presentations/{presentation_id}/preview` (for PPTX, stream to frontend; for Marp, render HTML or return raw MD).

12. **Cost tracking + feature gate on routes**:
    - Record `TokenUsage(usage_type="presentation_generate", cost_micros=...)` after generation.
    - `PRESENTATION_STUDIO_ENABLED` 403 on generation routes and thread creation.

## Acceptance Criteria

### AC-1: Chat Session in Presentation Studio Mode

- **Given** the user is on the new-chat welcome screen,  
  **When** they click the "Create slide deck" quick chip (or use `/slides` slash prompt or `?mode=presentation_studio` URL),  
  **Then** a thread is created with `platform_metadata: { "presentation_studio_mode": true }`, and the chat runtime injects a slide-generation system prompt plus the `generate_presentation` tool.

- **Given** a presentation-studio chat session,  
  **When** the user submits a prompt,  
  **Then** the agent calls `generate_presentation` with the user prompt and `output_format` defaulting to `pptx`, and the response stream includes a deliverable card with `presentation_id`, `title`, `slug`, `format`, `download_url`, `preview_url`, `slide_count`.

### AC-2: PPTX Generation

- **Given** a user describes a 16:9 slide deck in English or Vietnamese (e.g., "5-slide sales pitch for a B2B CRM"),  
  **When** `PresentationStudioService` generates with `output_format=pptx`,  
  **Then** it writes a valid `.pptx` file with at least a title slide and content slides, 16:9 aspect ratio, and speaker notes per slide.

- **Given** the generated PPTX,  
  **When** the user downloads it,  
  **Then** the file opens in PowerPoint / Google Slides without corruption.

### AC-3: Marp Markdown Generation

- **Given** a user requests "Marp slides",  
  **When** `PresentationStudioService` generates with `output_format=marp`,  
  **Then** it writes a Marp-compatible `.md` file with `---` slide separators, front-matter `theme` and `class`, and a download/preview URL.

- **Given** the Marp file,  
  **When** `marp-cli` is installed,  
  **Then** the backend can optionally render it to HTML via a subprocess and serve it at `preview_url`.

### AC-4: Workspace-Scoped Registry + Cost Tracking

- **Given** a generated deck,  
  **When** it is saved,  
  **Then** a `SlidePresentation` row is written with `workspace_id`, `user_id`, `title`, `slug`, `format`, `status="ready"`, and a workspace-unique `slug`.

- **Given** a deck generation completes,  
  **When** the service returns,  
  **Then** `TokenUsage` is recorded with `usage_type="presentation_generate"` and `cost_micros` computed from LLM token usage.

### AC-5: Auth, Audit, and Workspace Scoping

- **Given** any `POST/GET/PUT/DELETE` endpoint in `app/routes/presentation_routes.py`,  
  **When** a request is received,  
  **Then** the `require_workspace_member` dependency is applied and unauthenticated or non-member users receive `401`/`403` before any workspace data is accessed.

- **Given** the `generate_presentation` tool is invoked in a chat turn,  
  **When** the tool executes,  
  **Then** it writes an `AgentActionLog` entry recording the tool name, `workspace_id`, `user_id`, `thread_id`, prompt summary, and output status.

- **Given** a user tries to list, download, preview, or delete a presentation,  
  **When** the route is processed,  
  **Then** workspace RBAC is enforced via `require_workspace_member`; a user may not access decks outside their workspace.

### AC-6: Feature Gating

- **Given** `PRESENTATION_STUDIO_ENABLED=false`,  
  **When** a user tries to create a presentation-studio thread or call the generation route,  
  **Then** the API returns 403 with a clear message.

## Consequences

- New `app/services/presentation/` module.
- New `SlidePresentation` DB table + alembic migration.
- `python-pptx` dependency; `marp-cli` optional (Node) for HTML preview.
- New frontend tool card and artifact kind.
- TokenUsage usage_type `presentation_generate`.

## Edge Cases & Risks

| Edge | Handling |
|---|---|
| `prompt` empty or whitespace | Tool returns error string before calling service. |
| `output_format` not `pptx` or `marp` | Tool coerces to `pptx`; invalid enum from agent is logged and rejected. |
| `python-pptx` not installed / `marp-cli` missing | Service returns `status="failed"` with `degradation_reason="dependency_missing"`; frontend shows error card. |
| LLM returns malformed deck spec | Service returns `status="validation_failed"`, no file written. |
| Two decks in the same workspace with the same title | Slug disambiguated by appending a short hash (same pattern as `WorkspaceApp.slug`). |
| File storage path missing | `PresentationStudioService` creates directories before writing. |
| Large prompt | Truncated to `PRESENTATION_MAX_PROMPT_CHARS`. |
| `PRESENTATION_STUDIO_ENABLED=false` | 403 on thread creation and route; tool not built in chat runtime. |

## Verification Commands

Backend:
```bash
cd nowing_backend
ruff check app/services/presentation app/routes/presentation_routes.py app/agents/chat/multi_agent_chat/main_agent/tools/presentation app/db.py app/config/__init__.py app/schemas/presentation.py
ruff format app/services/presentation app/routes/presentation_routes.py app/agents/chat/multi_agent_chat/main_agent/tools/presentation app/db.py app/config/__init__.py app/schemas/presentation.py
uv run alembic upgrade head
uv run pytest tests/unit/services/presentation -q
uv run pytest tests/unit/agents/multi_agent_chat/ -q
```

Frontend:
```bash
cd nowing_web
pnpm tsc --noEmit
pnpm exec biome check components/tool-ui/presentation.tsx components/assistant-ui/assistant-message.tsx features/chat-artifacts features/new-chat --diagnostic-level=error
```
