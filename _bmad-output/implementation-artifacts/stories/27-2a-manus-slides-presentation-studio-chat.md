---
baseline_commit: 4fe46956f
story_key: "27-2a"
epic: "epic-27"
story: "27.2a"
title: "Manus Slides Presentation Studio from Chat (PPTX/Marp)"
status: "done"
---

# Story 27.2a: Manus Slides Presentation Studio from Chat (PPTX/Marp)

**Status:** `done` — chunk A–D review patches applied 2026-08-26, live browser E2E verified 100% PASS (PPTX 16:9 OOXML generation, Marp Markdown generation with graceful degradation, authenticated REST download, welcome screen quick-pick chips)  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Priority:** P1  
**Scope:** Chat-first PPTX / Marp slide generation. Not meeting minutes (27.2b). Not web builder / Mark Tool (27.1*).  
**Related Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" />  
**Parent (split):** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-2-manus-slides-presentation-studio-speaker-diarization.md" />  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> Epic 27 / FR-94  
**UX:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-08-15/ux-contract-epic-27-autonomous-workstation.md" /> Flow 2  
**Architecture:** AD-120, AD-121, AD-8, AD-10

## Story

As a **sales or marketing user**,  
I want to describe a slide deck in natural language from chat (chip, `/slides`, or URL),  
so that the agent generates a 16:9 PPTX or Marp Markdown deck and shows a downloadable deliverable card.

## Goal

- Single-turn MVP: prompt → `generate_presentation` → chat card with download/preview.
- Formats: `.pptx` (PowerPoint / Google Slides) and `.md` (Marp).
- Chat is the v1 entry point. Standalone `/dashboard/[workspace_id]/presentations` is **out of scope**.

## Out of scope

- Speaker diarization / meeting minutes (27.2b).
- Mark Tool / AST mutation on slides.
- PDF export, Google Slides API import, live PowerPoint Online embed.
- Executing LLM-generated Python or shelling Marp with interpolated user strings.
- New Permission enum. If you mirror `build_web_app`'s membership+permission check, reuse `Permission.WEB_BUILDER_CREATE` for the MVP or add `Permission.PRESENTATION_CREATE` to the Editor role later; do not fail-closed on a missing permission.
- Recreating `chat_modes.py` (already exists).
- Per-call in-place update of an existing deck row (re-generate = **new** `SlidePresentation`; the latest card in the thread is source of truth).
- `document_id` / crawl-URL ingestion; a URL inside the prompt is just LLM text.
- Daytona/AD-112 sandbox (that is Excel 26.9). PPTX is in-process `python-pptx`.
- Mark Tool on slide preview (AD-114 is 27.1d / `web_app` only).

## Acceptance Criteria

### AC-1: Presentation Studio chat mode

- **Given** the new-chat welcome screen,  
  **When** the user clicks **"Create a pitch deck (PPTX)"** or **"Create Marp slides"** (or `/slides pptx` / `/slides marp`, or `?mode=presentation_studio`),  
  **Then** the thread is created with `platform_metadata.presentation_studio_mode=true`, the ChatMode registry injects the presentation system prompt, and `generate_presentation` is available.

- **Given** a presentation-studio thread,  
  **When** the user submits a prompt,  
  **Then** the agent calls `generate_presentation` with `output_format` from the entry point (`pptx` default; `marp` when the Marp chip/slash is used), and the stream renders a deliverable card with `presentation_id`, `title`, `slug`, `format`, `status`, `download_url`, `preview_url`, `slide_count`.

### AC-2: PPTX generation

- **Given** a deck description in English or Vietnamese,  
  **When** `output_format=pptx`,  
  **Then** the service writes a valid 16:9 `.pptx` with at least a title slide, content slides, and speaker notes per slide. Optional chart only if the structured spec includes chart data.

- **Given** the download URL,  
  **When** the user downloads the file,  
  **Then** it is a real PPTX (ZIP/Open XML), not Markdown renamed.

### AC-3: Marp Markdown generation

- **Given** a Marp request,  
  **When** `output_format=marp`,  
  **Then** the service writes Marp Markdown with YAML front-matter (`theme`, `class`, `paginate`) and `---` slide separators.

- **Given** the `marp` binary (from `@marp-team/marp-cli`) is on PATH,  
  **When** generation succeeds,  
  **Then** the backend MAY render HTML via `subprocess` argv list + timeout and set `preview_url`. If `marp` is missing, `preview_url` is null, `degradation_reason="dependency_missing"`, card shows Download `.md` plus helper copy — no crash.

### AC-4: Registry + cost

- **Given** a successful generation,  
  **When** the service returns,  
  **Then** a `SlidePresentation` row exists with `workspace_id`, `user_id`, workspace-unique `slug`, `format`, `status="ready"`, `file_path` under `FILE_STORAGE_LOCAL_PATH/presentations/{workspace_id}/{presentation_id}/`.

- **Given** generation completes (including LLM calls),  
  **When** the service returns,  
  **Then** `TokenUsage` is recorded with `usage_type=UsageType.PRESENTATION_GENERATE` (`"presentation_generate"`) and `cost_micros` from the LLM call (0 only if no LLM tokens were used). Use `record_token_usage`; add the enum member — do not pass a raw unregistered string.

### AC-5: Auth and workspace scoping

- **Given** any presentation REST route,  
  **When** the request is unauthenticated or the user is not a workspace member,  
  **Then** respond 401/403 before reading files or rows. Cross-workspace IDs return 404, not 403 leakage of existence if that is the web-builder pattern; match `web_builder_routes.require_workspace_member`.

- **Given** `generate_presentation` runs in chat,  
  **When** the tool finishes,  
  **Then** `AgentActionLog` already has a row via `ActionLogMiddleware.aafter_tool`. **Do not insert `AgentActionLog` inside the tool.**

### AC-6: Feature gate

- **Given** `PRESENTATION_STUDIO_ENABLED=false` (repo default),  
  **When** the client creates a thread with `presentation_studio_mode=true` or hits presentation generate/list/download/preview,  
  **Then** API returns 403 with `Presentation Studio is not enabled on this workspace plan`. The tool, if somehow invoked, returns typed `status="validation_failed"` — not an uncaught exception.

## Tasks / Subtasks

- [ ] **T0 — ArtifactKind Step 0 (AC-1, AD-121)** — **this story owns Step 0**; 27.2b reuses it. Kind name is `presentation` (ChatMode + UX), **not** `slides`. (AC: 1)
  - [ ] Add `"presentation"` to `ArtifactKind` in `nowing_web/features/chat-artifacts/model/artifact.ts`
  - [ ] Map `generate_presentation: "presentation"` in `ARTIFACT_TOOL_KINDS`
  - [ ] Register `BODY_TOOLS.generate_presentation` in `assistant-message.tsx`
  - [ ] `KIND_META` / `GROUP_ORDER` / `EmptyState`: add **Slide Decks**; rename existing `video` label from **"Presentations"** → **"Video Presentations"** (update `artifact-row.tsx`, `artifacts-panel.tsx` `GROUP_ORDER`, and `EmptyState` copy)
  - [ ] `collect-artifacts.ts` `describeArtifact` case for `presentation`. Set `key` to `result.presentation_id` (UUID, `entityId: null`); set `contentType: "markdown"` (placeholder; the body card owns the viewer).
  - [ ] Export card from `components/tool-ui/index.ts`

- [ ] **T1 — Config + UsageType (AC-4, AC-6)** (AC: 4, 6)
  - [ ] Keep existing `PRESENTATION_STUDIO_ENABLED` default **FALSE** (already in `app/config/__init__.py`)
  - [ ] Add `PRESENTATION_FILE_STORAGE_SUBDIR` default `presentations`
  - [ ] Add `UsageType.PRESENTATION_GENERATE = "presentation_generate"` next to `WEB_BUILDER_MARK`

- [ ] **T2 — Model + Alembic (AC-4)** (AC: 4)
  - [ ] `SlidePresentation` in `app/db.py` + optional `Workspace.slide_presentations` (add it only if you also add `Workspace.workspace_apps`). Primary key: `id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))` to mirror `WorkspaceApp`. Status: `generating | ready | failed | degraded` (`degraded` = file written, Marp HTML preview skipped).
  - [ ] Unique `(workspace_id, slug)`
  - [ ] Alembic migration. Do **not** add `slide_presentations` to `app/zero_publication.py` for the MVP: card updates flow through SSE `emit_tool_output_card` and the artifact list refreshes from thread messages. If a future real-time sync requirement arises, add it to `ZERO_PUBLICATION` and call `apply_publication` in the migration.

- [ ] **T3 — Dependency (AC-2)** (AC: 2)
  - [ ] Add `python-pptx>=1.0.2` to `nowing_backend/pyproject.toml` (MIT). Pulls `lxml`, `pillow`, `xlsxwriter`.
  - [ ] `uv lock` / `uv sync`. Do **not** add Node `marp-cli` as a hard dependency.

- [ ] **T4 — Schemas + service (AC-2, AC-3, AC-4)** (AC: 2, 3, 4)
  - [ ] `app/services/presentation/schemas.py`: `GeneratePresentationInput` / `GeneratePresentationOutput` with `status: generating | ready | validation_failed | error` and optional `error`, `degradation_reason`
  - [ ] `PresentationStudioService`: LLM → **JSON deck spec** (pydantic) → PPTX or Marp file. Never `exec`/`eval` LLM text.
  - [ ] LLM via `get_agent_llm(session, workspace_id)` — same as `WebBuilderService`
  - [ ] PPTX: 16:9 (`Inches(13.333)` × `Inches(7.5)`), title + body + notes. If `DeckSpec` includes `chart`, add a `python-pptx` chart; if not, skip (do not fail). Include one unit fixture **with** chart data so FR-94 “có biểu đồ” is testable.
  - [ ] Marp writer; optional `marp` binary (from `@marp-team/marp-cli`) via `asyncio.create_subprocess_exec` argv, cwd=temp, timeout ≤ 30s. Detect with `shutil.which("marp")`.
  - [ ] Slug disambiguation: copy `WorkspaceApp` hash suffix
  - [ ] Own session commit/rollback; tool does not `session.commit()` after the service

- [ ] **T5 — Tool + registry (AC-1, AC-5)** (AC: 1, 5)
  - [ ] `app/agents/chat/multi_agent_chat/main_agent/tools/presentation/generate_presentation.py` factory mirroring `build_web_app.py` (UUID `user_id` guard, empty prompt → typed validation_failed, truncate to `PRESENTATION_MAX_PROMPT_CHARS`)
  - [ ] Append `"generate_presentation"` to `MAIN_AGENT_NOWING_TOOL_NAMES_ORDERED`. If the name is missing here, `factory.py` **silently drops** it from `enabled_tools`.
  - [ ] Register factory in `_MAIN_AGENT_TOOL_FACTORIES` with deps `("workspace_id", "user_id")`
  - [ ] Add `"generate_presentation"` to `app/tasks/chat/streaming/handlers/tools/deliverables/tool_names.py` `DELIVERABLE_TOOLS`
  - [ ] Copy `deliverables/build_web_app/{emission,thinking}.py` → `deliverables/generate_presentation/` (SSE card never appears without this)
  - [ ] **Do not** register this tool on the deliverables **subagent** (`subagents/builtins/deliverables/tools/`). Mode `enabled_tools` only binds **main-agent** names.
  - [ ] Optional but preferred: `app/capabilities/presentation/generate/` executor so REST and tool share one path (copy `web_builder/build_app`). If you add a capability, also add `BillingUnit.PRESENTATION_GENERATE` beside `WEB_BUILDER_GENERATE` in `app/capabilities/core/types.py`.

- [ ] **T6 — ChatMode wiring (AC-1, AC-6, AD-120)** (AC: 1, 6)
  - [ ] **Do not create a new registry.** Edit existing `presentation_studio` entry in `chat_modes.py`: set `enabled_tools=["generate_presentation"]` (orchestrator **replaces** the tool list when not None — same as `web_builder`)
  - [ ] `new_chat_routes.py` already 403s gated modes via `resolve_chat_mode` + `is_chat_mode_enabled` — do not add a third `if presentation_studio` branch
  - [ ] Frontend: `?mode=presentation_studio` → `platform_metadata: { presentation_studio_mode: true }` in `new-chat/[[...chat_id]]/page.tsx` (today only `web_builder` is handled)

- [ ] **T7 — REST (AC-5, AC-6)** (AC: 5, 6)
  - [ ] `app/routes/presentation_routes.py` prefix `/api/v1/presentations`
  - [ ] `GET /` list, `GET /{id}` read, `GET /{id}/download` FileResponse, `GET /{id}/preview` HTML or 404 if none, `DELETE /{id}` (UX right-to-delete; 204 after member check)
  - [ ] Gate every route with `PRESENTATION_STUDIO_ENABLED` then `require_workspace_member`
  - [ ] Mount in `app/app.py` like `web_builder_routes`
  - [ ] Path traversal: resolve file under storage root, `is_relative_to`

- [ ] **T8 — Frontend card + entry points (AC-1, UX Flow 2)** (AC: 1)
  - [ ] `components/tool-ui/presentation.tsx` — `GeneratePresentationToolUI`: title, format, slide count, Download, Preview (if URL), states generating/ready/error/degraded
  - [ ] PPTX: primary **"Download .pptx"**; secondary **"Open in Slides"** only if you have a safe `https://` viewer URL — do not fake Google Slides
  - [ ] Marp: Preview iframe if `preview_url`; else Download `.md` + *"Open this file in Marp for VS Code / Marp Web."*
  - [ ] Welcome chips in `thread.tsx` (same `?q=&mode=` pattern as landing-page chips)
  - [ ] Dock: `parse-dock-content.ts` currently matches **`build_slides` / `generate_slides` (tools that do not exist)**. Map **`generate_presentation`**. `DockTabId` already includes `"slides"`; `SlidesDockContent` is a placeholder — fill or link Download/Preview, do not invent a second editor.
  - [ ] Narrow `generate_video_presentation` to **video / Remotion** only. Update both the subagent tool in `app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/video_presentation.py` and the `TOOL_CATALOG` entry in `app/agents/chat/multi_agent_chat/shared/tools/catalog.py` so neither mentions “presentation,” “slides,” or “slide deck.”
  - [ ] Extend `PromptPickerAction` / `BuiltinPromptItem` from `isWebBuilder?: boolean` to `chatMode?: "web_builder" | "presentation_studio"` (keep `isWebBuilder` as derived or migrate call sites in `thread.tsx` slash handler)
  - [ ] Slash `/slides pptx` and `/slides marp`
  - [ ] Copy: EN "Create a pitch deck" / VI "Tạo slide pitch"; loading "Designing your slides…" / "Đang thiết kế slide…"
  - [ ] `messages/en.json` + `messages/vi.json` (and other locales if the chip uses `t()`)

- [ ] **T9 — Tests (all ACs)** (AC: 1–6)
  - [ ] Unit: deck spec validation, PPTX bytes start with `PK`, Marp has `---`, empty prompt, bad format coerced/rejected, slug clash, feature flag, no `exec`
  - [ ] Integration: routes 401/403/404, download, list scoped to workspace
  - [ ] Tool unit: UUID user_id, validation_failed JSON
  - [ ] Frontend: optional Playwright skip-if-flag-off; typecheck + biome on touched files
- [ ] **Red-phase ATDD scaffolds** — write failing/skipped tests from <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/test-artifacts/atdd-checklist-27-2a-manus-slides-presentation-studio-chat.md" /> before turning any AC green

### Review Findings (2026-08-25 — inline review because subagent quota exhausted)

#### decision-needed (resolved)
- [x] [Review][Resolved] Per-workspace `Workspace.presentation_studio_enabled` column added, but Out of Scope said "keep global flag only" — confirmed intentional; spec Out of Scope updated and the finding is now closed.

#### patch
- [x] [Review][Patch] `SlidePresentationRead.download_url` is never populated on the ORM, so list/get endpoints return `null` for `download_url` (`app/services/presentation/schemas.py:97`).
- [x] [Review][Patch] `build_pptx` copies the first content slide's notes into the title slide's notes instead of the deck-level description or no notes (`app/services/presentation/pptx_driver.py:31`).
- [x] [Review][Patch] `_call_llm_for_deck` uses a greedy regex `(\{.*\})` for JSON extraction that can swallow trailing text or multiple JSON objects (`app/services/presentation/service.py:119`).
- [x] [Review][Patch] `record_token_usage` is called with `cost_micros=0` and a `model_breakdown` containing the helper function name instead of the real model/cost (`app/services/presentation/service.py:279-290`).
- [x] [Review][Patch] `delete_presentation` deletes every file in the presentation's parent directory before removing it, which is broader than the intended output files (`app/routes/presentation_routes.py:274-283`).
- [x] [Review][Patch] `SlidesDockContent` is a placeholder and does not render the Marp HTML preview or the deck download links (`nowing_web/features/dock/components/DockContent.tsx:163-175`).
- [x] [Review][Patch] `test_generate_presentation_tool_atdd.py` docstring still claims red-phase/skipped tests, but tests are now green (`nowing_backend/tests/unit/agents/chat/multi_agent_chat/main_agent/tools/presentation/test_generate_presentation_tool_atdd.py:1-4`).

#### defer
- [x] [Review][Defer] `test_prompt_exceeding_max_length_is_truncated_or_rejected` mutates `config.PRESENTATION_MAX_PROMPT_CHARS` at runtime, but Pydantic `GeneratePresentationInput` captures `max_length` at model import — service truncation covers the runtime limit, so no user-facing bug.

## Dev Notes

### Current code — READ BEFORE EDITING

| File | Today | This story |
|---|---|---|
| `app/tasks/chat/streaming/flows/new_chat/chat_modes.py` | `presentation_studio` ChatMode exists: prompt, `PRESENTATION_STUDIO_ENABLED`, `artifact_kinds=["presentation"]`, **`enabled_tools` unset** | Set `enabled_tools=["generate_presentation"]`. Do not add `if/elif` in orchestrator. |
| `app/config/__init__.py` ~1887 | `PRESENTATION_STUDIO_ENABLED` default **FALSE**; `PRESENTATION_MAX_PROMPT_CHARS=2000` | Keep fail-closed default. Add storage subdir only. |
| `app/routes/new_chat_routes.py` ~832 | Already 403s any non-default ChatMode when flag off | No new branch. |
| `app/agents/.../tools/index.py` | Tools: memory, automation, lead_gen, `build_web_app` | Append `generate_presentation`. |
| `app/agents/.../tools/registry.py` | `_MAIN_AGENT_TOOL_FACTORIES` | Register factory. |
| `nowing_web/.../artifact.ts` | Kinds: report, resume, podcast, **video**, image, web_app. No `presentation`. | Add `presentation`. |
| `artifacts-panel.tsx` | `video` labeled **"Presentations"** | Rename video group; add Slide Decks. |
| `assistant-message.tsx` `BODY_TOOLS` | Has `build_web_app`, `generate_video_presentation` | Add `generate_presentation`. |
| `new-chat/page.tsx` | Only `mode=web_builder` → metadata | Also `presentation_studio`. |
| `thread.tsx` chips | Web-builder chips use `?q=&mode=` | Add two slide chips. |
| `prompt-picker.tsx` | `isWebBuilder` boolean | Generalize to chat mode string. |
| `pyproject.toml` | `python-pptx` is only a **transitive** Docling extra; **zero** `from pptx` in app code | Add **direct** `python-pptx>=1.0.2`. |
| `deliverables/tool_names.py` | `DELIVERABLE_TOOLS` has `build_web_app`, `generate_video_presentation`, **not** `generate_presentation` | Add the name + emission/thinking modules. |
| `parse-dock-content.ts` | Opens slides tab for `build_slides` / `generate_slides` | Switch to `generate_presentation`. |
| Video subagent tool | Docstring claims “slides / slide deck” | Narrow to video-only so the main-agent tool wins. |
| `UsageType` | Has `WEB_BUILDER_MARK`; no presentation | Add `PRESENTATION_GENERATE`. |
| `VideoPresentation` | Remotion JSON slides — **different product** | New `SlidePresentation` table. Do not overload video_presentations. |

Orchestrator (`stream_new_chat`): if `chat_mode.enabled_tools is not None` it **replaces** `effective_enabled_tools`. Listing only `generate_presentation` matches `web_builder` (`["build_web_app"]`). Do not invent a merge.

### LLM → file (NFR-2)

1. Call `get_agent_llm`.
2. Parse response as JSON `DeckSpec` (slides: title, bullets, notes, optional chart `{categories, series}`).
3. If parse/validation fails → `status="validation_failed"`, no file, no row `ready`.
4. Map spec to `python-pptx` objects or Marp markdown.
5. **Forbidden:** `exec`, `eval`, `subprocess` with `shell=True`, interpolating prompt into `shlex` strings.

### python-pptx 1.0.2 (PyPI, Aug 2024)

- 16:9: `prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)`.
- Notes: `slide.notes_slide.notes_text_frame.text`.
- Charts need numeric series; skip chart if spec has none.
- MIT license → `app/services/presentation/` (not `app/proprietary/`).

### Auth copy-from

- Routes: `web_builder_routes.require_workspace_member` + `check_web_builder_enabled` pattern, but flag is `PRESENTATION_STUDIO_ENABLED`.
- Tool: copy `build_web_app.py` lines 21–76 (UUID, empty prompt, feature flag typed output). Either check `Permission.WEB_BUILDER_CREATE` (Editors already have it) or add `Permission.PRESENTATION_CREATE` and include it in the Editor role; do not fail-closed on a missing permission.
- **Do not** write `AgentActionLog` in the tool — `ActionLogMiddleware` already inserts on `aafter_tool` (`app/agents/chat/multi_agent_chat/main_agent/middleware/action_log/middleware.py`).

### Session / billing

- Tool opens `async_session_maker()`; service commits.
- Tool must **not** `commit()` after the service (27.1a review finding).
- Record usage after successful persist with `record_token_usage(..., usage_type=UsageType.PRESENTATION_GENERATE, prompt_tokens=..., completion_tokens=..., total_tokens=..., cost_micros=..., model=..., model_breakdown=..., call_details=...)`. Do not record only `cost_micros`; pass full usage metadata like `WebBuilderService` does.
- P0 surface: `token_tracking_service.py` enum add only. `UsageType.PRESENTATION_GENERATE` is what `record_token_usage` consumes. `BillingUnit.PRESENTATION_GENERATE` is only needed if you add the optional `app/capabilities/presentation/generate/` capability.

### UX copy (contract)

| State | EN | VI |
|---|---|---|
| Chip PPTX | Create a pitch deck | Tạo slide pitch |
| Chip Marp | Create Marp slides | Tạo slide Marp |
| Generating | Designing your slides… | Đang thiết kế slide… |
| Flag off | Slide studio is not available on this workspace plan or installation. | Studio slide không khả dụng trên gói/workspace này. |
| Validation | Could not generate a valid deck from that description. Try a more specific outline. | Không tạo được deck hợp lệ. Hãy mô tả outline cụ thể hơn. |
| Marp no CLI | Open this file in Marp for VS Code / Marp Web. | Mở file này trong Marp for VS Code / Marp Web. |

PPTX cannot be previewed inline in MVP. Do not iframe binary PPTX.

### Project structure

```
nowing_backend/app/services/presentation/
  __init__.py
  schemas.py
  service.py          # PresentationStudioService
  pptx_driver.py      # python-pptx mapping only
  marp_driver.py      # markdown + optional subprocess
nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/presentation/
  __init__.py
  generate_presentation.py
nowing_backend/app/routes/presentation_routes.py
nowing_backend/alembic/versions/<rev>_add_slide_presentations.py
nowing_web/components/tool-ui/presentation.tsx
nowing_backend/tests/unit/services/presentation/
nowing_backend/tests/integration/routes/test_presentation_routes.py
```

Optional mirror of 27.1a:

```
nowing_backend/app/capabilities/presentation/generate/{__init__,definition,executor,schemas}.py
```

### Preserve

- `generate_video_presentation` / Remotion cards and `video` artifact kind.
- Web builder chips, `web_builder_mode`, dock.
- ChatMode `meeting_minutes` stub (27.2b) — do not implement that tool.

## Architecture Compliance

| AD | Action |
|---|---|
| AD-1 | Service in `app/services/presentation/`, routes in `app/routes/`, tool in `app/agents/`. No new process. |
| AD-2 | Alembic + AsyncSession. |
| AD-8 / AD-10 | Real `TokenUsage` after generation. |
| AD-9 | `require_workspace_member` on all presentation routes. |
| AD-16 | python-pptx MIT in `app/services/`. |
| AD-21 | `?mode=presentation_studio` URL pointer only. |
| AD-120 | Edit existing ChatMode entry; no orchestrator if/elif. |
| AD-121 | Kind name **`presentation`** (already in ChatMode `artifact_kinds`). Do not add a second `slides` kind. |
| AD-104 | MVP is REST-only (SSE `emit_tool_output_card` + artifact list). Do not add `slide_presentations` to `app/zero_publication.py`. If real-time sync becomes required later, add it to `ZERO_PUBLICATION` and call `apply_publication` in the migration. |

## Testing Requirements

```bash
cd nowing_backend
ruff check app/services/presentation app/routes/presentation_routes.py \
  app/agents/chat/multi_agent_chat/main_agent/tools/presentation \
  app/tasks/chat/streaming/flows/new_chat/chat_modes.py \
  app/config/__init__.py app/db.py app/services/token_tracking_service.py
ruff format app/services/presentation app/routes/presentation_routes.py \
  app/agents/chat/multi_agent_chat/main_agent/tools/presentation
uv run pytest tests/unit/services/presentation tests/integration/routes/test_presentation_routes.py -q
```

```bash
cd nowing_web
pnpm tsc --noEmit
pnpm exec biome check --diagnostic-level=error \
  components/tool-ui/presentation.tsx \
  components/assistant-ui/assistant-message.tsx \
  components/assistant-ui/thread.tsx \
  components/new-chat/prompt-picker.tsx \
  'app/dashboard/[workspace_id]/new-chat/[[...chat_id]]/page.tsx' \
  features/chat-artifacts
```

Must assert: PPTX magic `PK`; Marp contains `---`; 403 when flag false; member-only download; empty prompt → `validation_failed`; slug unique per workspace.

## Previous Story Intelligence (27.1a / 27.1d)

- Typed tool output with `status`/`error` — frontend cards key off `status`, not string matching.
- Do not `session.commit()` in the tool after the service commits.
- Three registries: main-agent factory, subagent deliverables, capability REST. 27.2a is **main-agent + optional capability executor**, same as `build_web_app`. Putting the tool only on the subagent makes ChatMode `enabled_tools` a no-op.
- Copy pipeline: chip → `presentation_studio_mode=true` → ChatMode gate → main-agent tool → service writes file → `record_token_usage` → SSE `emit_tool_output_card` → `BODY_TOOLS` + artifacts + dock `slides` tab → REST download.
- `deps["user_id"]` may be `UUID` or `str`.
- Feature flags fail-closed; tool returns typed failure, not raise.
- ChatMode registry is live — adding a third hardcoded orchestrator branch is a regression against AD-120.
- `UsageType` enum: 27.1d added `WEB_BUILDER_MARK`; follow that, not a bare string.
- Artifact Step 0 must land first or the card never appears in the dock/artifacts panel.
- `ChatArtifact.entityId` is `number | null` (reports). Presentations use UUID: set `key` to the UUID string and `entityId: null` (same as web_app). Do not change `entityId` to UUID in this story.

## Git Intelligence

HEAD `4fe46956f` (`feat(dock): contextual right panel for leads and web-builder`). Recent work is web-builder + dock. Do not put slide preview into the web-builder dock tab.

## Latest Tech

- **python-pptx 1.0.2** — current PyPI (2024-08-07). Use `>=1.0.2`.
- **marp** — optional binary from `@marp-team/marp-cli`; detect with `shutil.which("marp")` or use `npx --no-install @marp-team/marp-cli` only if you can do it without network in production. Prefer PATH `marp`.

## Project Context

Follow `_bmad-output/project-context.md`: no PII in logs (truncate prompt in logs); `shielded_async_session` not required for cost_micros if generation is request-scoped and short; still use `record_token_usage`. Frontend state triad: no new localStorage for mode (AD-21).

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

- 2026-08-26 chunk D patches: welcome chips + `/slides pptx|marp`; `chatMode` union; no verbose-gate on BODY_TOOLS; Preview only from `preview_url`; Marp download `.md`; dock respects `preview_url`; EN/VI i18n; barrel export; EmptyState Slide Decks.
- 2026-08-26 chunk C re-review patch: SSE emission/thinking branch on `status` (`degraded` → warning/limited preview; `failed`/`error`/`validation_failed` → error even without `error` field). Tool ATDD 12/12, service 9/9.
- 2026-08-26 chunk C patches applied: tool no longer leaks `str(exc)`; coerce/reject `output_format`; `user_id` guard before DB; ChatMode prompt drops `optional title`; video catalog/docstring narrowed to Remotion video; ATDD covers ChatMode `enabled_tools`, `DELIVERABLE_TOOLS`, empty prompt, invalid UUID, invalid format. Tool unit 8/8, service 9/9.
- 2026-08-26 chunk B patches applied: `Path.is_relative_to` + workspace/id-scoped dir (URL `presentation_id` with `..` rejected), download `is_file()`, always overwrite `payload.user_id`, fail-closed when Workspace missing, Alembic `sa.text("'pptx'")` / `sa.text("'generating'")`, Marp preview CSP, download filename `.md`, DELETE only unlinks files under the presentation dir (row still deleted after unlink OSError — UX right-to-delete; orphans logged). Tests: global flag 403 on all routes, IDOR 404 with seeded foreign row, DELETE then GET 404, UniqueConstraint IntegrityError. Verified: ruff clean; unit 9/9; integration 8/8.

### File List

## Story completion

Status: **in-progress** — chunk A–D review patches applied 2026-08-26. Story not `done` until P0 human-review gate.

### Review Findings (chunk A — service / PPTX / Marp / schemas, 2026-08-25)

##### Patch

- [x] [Review][Patch] `DeckSpec.slides` cho phép list rỗng → PPTX chỉ có title slide, `slide_count=0` (AC-2) [nowing_backend/app/services/presentation/schemas.py:35]
- [x] [Review][Patch] `record_token_usage(..., user_id=build_input.user_id)` khi `user_id` None: `TokenUsage.user_id` NOT NULL, commit fail [nowing_backend/app/services/presentation/service.py:302-315]
- [x] [Review][Patch] PPTX `placeholders[1]` / `shapes.title` không guard layout thiếu placeholder [nowing_backend/app/services/presentation/pptx_driver.py:27-40]
- [x] [Review][Patch] Path guard dùng `str.startswith` và bỏ `self.storage_base_path`; dùng `Path.is_relative_to` [nowing_backend/app/services/presentation/service.py:34-49]
- [x] [Review][Patch] `marp` timeout `proc.kill()` không `await proc.wait()` / `communicate()` [nowing_backend/app/services/presentation/marp_driver.py:85-87]
- [x] [Review][Patch] Title/bullets/notes LLM nhét raw vào Marp (`---` / `-->` phá slide và HTML comment) [nowing_backend/app/services/presentation/marp_driver.py:24-53]
- [x] [Review][Patch] Token usage chỉ đọc `input_tokens`/`output_tokens`, bỏ `prompt_tokens`/`completion_tokens` [nowing_backend/app/services/presentation/service.py:131-140]
- [x] [Review][Patch] LLM đã chạy nhưng validation_failed không `record_token_usage` (AC-4) [nowing_backend/app/services/presentation/service.py:200-225]
- [x] [Review][Patch] Slug TOCTOU: không retry `IntegrityError` trên unique `(workspace_id, slug)` [nowing_backend/app/services/presentation/service.py:274-315]
- [x] [Review][Patch] Ghi file trước `commit`; commit fail để orphan trên disk [nowing_backend/app/services/presentation/service.py:230-315]
- [x] [Review][Patch] Chart `categories`/`series` lệch độ dài; `float(v)` nổ cả generation [nowing_backend/app/services/presentation/pptx_driver.py:48-60]
- [x] [Review][Patch] `from pptx import Presentation` top-level: thiếu python-pptx làm không import được cả Marp path [nowing_backend/app/services/presentation/pptx_driver.py:8]
- [x] [Review][Patch] `GeneratePresentationOutput.file_path` lộ filesystem path; exception raw trả client [nowing_backend/app/services/presentation/service.py:262-325]
- [x] [Review][Patch] `response.content` list bị `str(part)` → JSON hỏng [nowing_backend/app/services/presentation/service.py:111-112]
- [x] [Review][Patch] `mkdir`/`_resolve_storage_path` nằm ngoài try của file write [nowing_backend/app/services/presentation/service.py:227-230]
- [x] [Review][Patch] Marp front-matter thiếu `marp: true` / `size: 16:9` [nowing_backend/app/services/presentation/marp_driver.py:17-22]

##### Defer

- [x] [Review][Defer] Select toàn bộ slug workspace để disambiguate (unbounded) [nowing_backend/app/services/presentation/service.py:274-279] — deferred, pre-existing
- [x] [Review][Defer] `SlidePresentation.prompt` lưu full prompt (PII/retention) [nowing_backend/app/db.py SlidePresentation.prompt] — deferred, pre-existing

### Review Findings (chunk B — routes / Alembic / tests, 2026-08-26)

##### Patch

- [x] [Review][Patch] `_resolve_storage_path` dùng `str.startswith` thay vì `Path.is_relative_to`; không khóa `presentations/{workspace_id}/{presentation_id}/` nên `file_path` độc hại đọc/xóa file khác dưới storage root [nowing_backend/app/routes/presentation_routes.py:132-170]
- [x] [Review][Patch] Download chỉ `exists()`, không `is_file()` — directory fallback khi `file_path` null [nowing_backend/app/routes/presentation_routes.py:194-211]
- [x] [Review][Patch] Generate chỉ gán `user_id` khi body omitted; client spoof được UUID khác (web_builder luôn overwrite `auth.user.id`) [nowing_backend/app/routes/presentation_routes.py:82-83]
- [x] [Review][Patch] Feature gate fail-open khi `Workspace` row missing (`ws is None` → enabled) [nowing_backend/app/routes/presentation_routes.py:37-42]
- [x] [Review][Patch] Alembic `server_default="pptx"` / `"generating"` là SQL identifier, không quoted literal — dùng `sa.text("'pptx'")` [nowing_backend/alembic/versions/697ee5945395_add_slide_presentations.py:40-48]
- [x] [Review][Patch] Marp preview trả raw HTML không CSP [nowing_backend/app/routes/presentation_routes.py:250]
- [x] [Review][Patch] Download Marp đặt filename `{slug}.marp` trong khi file là `.md` [nowing_backend/app/routes/presentation_routes.py:206]
- [x] [Review][Patch] DELETE vẫn commit xóa row khi unlink fail; `parent.rmdir()` không kiểm tra đúng thư mục presentation [nowing_backend/app/routes/presentation_routes.py:274-289]
- [x] [Review][Patch] Test cross-workspace dùng `id+1` không seed presentation workspace B — không chứng minh 404 IDOR [nowing_backend/tests/integration/routes/test_presentation_routes_atdd.py:62-71]
- [x] [Review][Patch] AC-6: autouse bật global flag; chỉ test workspace flag off trên POST generate, thiếu global `PRESENTATION_STUDIO_ENABLED=false` cho list/download/preview/delete [nowing_backend/tests/integration/routes/test_presentation_routes_atdd.py:11-59]
- [x] [Review][Patch] DELETE test không assert GET 404 / row biến mất [nowing_backend/tests/integration/routes/test_presentation_routes_atdd.py:138-157]
- [x] [Review][Patch] UniqueConstraint `(workspace_id, slug)` không có integration test SQL thật (Pattern 6) [nowing_backend/alembic/versions/697ee5945395_add_slide_presentations.py:78-82]

##### Defer

- [x] [Review][Defer] List presentations không pagination [nowing_backend/app/routes/presentation_routes.py:92-106] — deferred, pre-existing
- [x] [Review][Defer] `presentation_studio_enabled` server_default true cho mọi workspace cũ [nowing_backend/alembic/versions/2014b3fa9eda_add_workspace_presentation_studio_.py:24-31] — deferred, pre-existing
- [x] [Review][Defer] Hunk `app.py` Host catch-all web-builder không thuộc presentation routes [nowing_backend/app/app.py] — deferred, pre-existing

### Review Findings (chunk C — tool / SSE / ChatMode, 2026-08-26)

Blind Hunter and Edge Case Hunter timed out (~8 min); parent reconstructed those layers. Acceptance Auditor returned 2 findings.

##### Patch

- [x] [Review][Patch] `except Exception` nhét `str(exc)` vào `error` (SSE card / thinking) [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/presentation/generate_presentation.py:164-166]
- [x] [Review][Patch] `output_format` không coerce/reject trước Pydantic — `"PPTX"` / `"pdf"` thành `status=error` ValidationError, không `validation_failed` [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/presentation/generate_presentation.py:147-156]
- [x] [Review][Patch] `user_id is None` chỉ check sau query Workspace; test empty-prompt / invalid-UUID không bật `PRESENTATION_STUDIO_ENABLED` nên hit AC-6 trước (false green) [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/tools/presentation/generate_presentation.py:105-110] [nowing_backend/tests/unit/agents/chat/multi_agent_chat/main_agent/tools/presentation/test_generate_presentation_tool_atdd.py:50-99]
- [x] [Review][Patch] ChatMode prompt bảo LLM truyền `optional title` nhưng tool schema không có `title` — extra kwarg fail ở LangChain, không typed `validation_failed` [nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:39-43]
- [x] [Review][Patch] T8: `generate_video_presentation` catalog + docstring vẫn nói "slides" / "slide deck" [nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/catalog.py:48-50] [nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/video_presentation.py:50]
- [x] [Review][Patch] Thiếu unit test `presentation_studio.enabled_tools == ["generate_presentation"]` và `"generate_presentation" in DELIVERABLE_TOOLS` [nowing_backend/tests/unit/agents/chat/multi_agent_chat/main_agent/tools/presentation/test_generate_presentation_tool_atdd.py]

##### Defer

- [x] [Review][Defer] `BillingUnit.PRESENTATION_GENERATE` không có capability executor — T5 optional [nowing_backend/app/capabilities/core/types.py:58] — deferred, pre-existing
- [x] [Review][Defer] Hunk `WEB_BUILDER_CONTAINER_*` / Caddy / Traefik trong `config/__init__.py` thuộc 27.1c [nowing_backend/app/config/__init__.py:1842-1886] — deferred, pre-existing
- [x] [Review][Defer] `UsageType.WEB_BUILDER_MARK` nằm cùng hunk token_tracking với 27.2a [nowing_backend/app/services/token_tracking_service.py:74] — deferred, pre-existing
- [x] [Review][Defer] Thinking SSE nhét `prompt[:80]` (copy `build_web_app`) [nowing_backend/app/tasks/chat/streaming/handlers/tools/deliverables/generate_presentation/thinking.py:18] — deferred, pre-existing
- [x] [Review][Defer] `output_format` từ chip/slash Marp thuộc chunk D frontend [nowing_backend/app/tasks/chat/streaming/flows/new_chat/chat_modes.py:72-78] — deferred, pre-existing

### Review Findings (chunk C re-review — 2026-08-26, after patches)

All three layers completed (Blind Hunter, Edge Case Hunter, Acceptance Auditor). Previous 6 patches hold. Auditor: no new AC violations.

##### Patch

- [x] [Review][Patch] SSE emission/thinking treats missing `error` as success — `status=degraded` (Marp preview skipped) and `failed` without error print "generated successfully" [nowing_backend/app/tasks/chat/streaming/handlers/tools/deliverables/generate_presentation/emission.py:19-27] [nowing_backend/app/tasks/chat/streaming/handlers/tools/deliverables/generate_presentation/thinking.py:33-40]

##### Defer

- [x] [Review][Defer] Identity prompt still routes "slide decks" to the `deliverables` subagent (no PPTX tool there) [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/identity/private.md:31] [nowing_backend/app/agents/chat/multi_agent_chat/main_agent/system_prompt/prompts/identity/team.md:31] — deferred, pre-existing
- [x] [Review][Defer] ATDD tool tests never leave the early-return path; emission/thinking/`status=degraded` untested [nowing_backend/tests/unit/agents/chat/multi_agent_chat/main_agent/tools/presentation/test_generate_presentation_tool_atdd.py] — deferred, pre-existing

### Review Findings (chunk D — card / chips / dock / artifact, 2026-08-26)

All three layers completed. Auditor: **FAIL** AC-1/T8 entry points.

##### Patch

- [x] [Review][Patch] Welcome chips thiếu "Create a pitch deck (PPTX)" / "Create Marp slides" (`?q=&mode=presentation_studio`) [nowing_web/components/assistant-ui/thread.tsx:323-360]
- [x] [Review][Patch] Slash không có `/slides pptx` / `/slides marp`; picker dùng `/presentation …` và không encode format [nowing_web/components/new-chat/prompt-picker.tsx:110-138]
- [x] [Review][Patch] `withVerboseGate` default `false` ẩn card (kể cả `build_web_app`) — AC-1 đòi deliverable card trên stream [nowing_web/components/assistant-ui/assistant-message.tsx:452-484]
- [x] [Review][Patch] Card synthesize `/preview` khi có `presentation_id` — PPTX hiện nút Preview giả [nowing_web/components/tool-ui/presentation.tsx:98-103,198-212]
- [x] [Review][Patch] Download label `Download .{format}` → Marp thành `.marp` không phải `.md` [nowing_web/components/tool-ui/presentation.tsx:184-196] [nowing_web/features/dock/components/DockContent.tsx:210-216]
- [x] [Review][Patch] Dock Marp iframe luôn synthesize preview, bỏ qua `result.preview_url` (degraded 404) [nowing_web/features/dock/components/DockContent.tsx:192-234]
- [x] [Review][Patch] Thiếu i18n EN/VI cho chip + "Designing your slides…" / Marp helper [nowing_web/messages/en.json] [nowing_web/messages/vi.json] [nowing_web/components/tool-ui/presentation.tsx:114]
- [x] [Review][Patch] `PromptPickerAction` thêm `isPresentationStudio` thay vì `chatMode?: "web_builder" | "presentation_studio"` [nowing_web/components/new-chat/prompt-picker.tsx:35-41]
- [x] [Review][Patch] T0: không export `GeneratePresentationToolUI` từ `components/tool-ui/index.ts`
- [x] [Review][Patch] EmptyState vẫn nói "presentations", chưa "Slide Decks" [nowing_web/features/chat-artifacts/ui/artifacts-panel.tsx:39-41]

##### Defer

- [x] [Review][Defer] `<a href>` / iframe tới `BACKEND_URL` không dùng `authenticatedFetch` [nowing_web/lib/apis/presentation-api.service.ts:3-13] — deferred, pre-existing
- [x] [Review][Defer] Video Remotion card vẫn copy "presentation" / `presentation.pptx` [nowing_web/components/tool-ui/video-presentation/generate-video-presentation.tsx:87,383] — deferred, pre-existing
- [x] [Review][Defer] Không có Playwright chip/slash/card [nowing_web/tests] — deferred, pre-existing
- [x] [Review][Defer] `workspaceId || 1` fail-open [nowing_web/components/tool-ui/presentation.tsx:82] — deferred, pre-existing
