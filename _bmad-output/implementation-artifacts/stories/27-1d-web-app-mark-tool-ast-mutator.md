---
baseline_commit: d06d121a0
story_key: 27-1d
epic: epic-27
story: "27.1d"
title: "Web App Mark Tool & JSX AST Mutator"
status: "in-progress"
---

# Story 27.1d: Web App Mark Tool & JSX AST Mutator

**Status:** `in-progress` — UI/iframe postMessage/regex-based patch endpoint done; missing real AST parser and `web_builder_mark` TokenUsage. See `web-builder-27-1-status-audit-2026-08-25.md`.  
**Epic:** Epic 27 — Full-Stack Web App Builder, Instant Hosting & Creative Studio  
**Parent Story:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md" /> — Story 27.1 split container.  
**Related Story (MVP):** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1a-web-builder-chat-mode-sales-marketing-mvp.md" /> — 27.1a chat-first static publish (done; visual selector only, no mutation).  
**Prerequisite Stories:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1b-web-app-build-preview-runner.md" /> — build/preview runner; <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/stories/27-1c-web-app-container-deploy-cname.md" /> — container deploy.  
**Priority:** P1  
**Source:** <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/epics.md" /> (Epic 27, Story 27.1; FR-94)  
**Related PRD:** FR-94 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md" /> §4.10  
**Related Architecture:** AD-114 in <ref_file file="/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md" /> §8  

## Story

As a Nowing user,  
I want to click an element in the web app preview and have the agent mutate the corresponding JSX source,  
So that I can visually edit generated apps without writing code.

## Scope

This story owns the **Design View Mark Tool**: iframe element selector, DOM-to-JSX mapping, and AST mutation. It depends on a generated/previewed app (Story 27.1b) and the public/preview URL (27.1c).

## [BUILT] vs [GAP]

### [BUILT] — existing patterns to reuse

- **Workspace app registry.** `WorkspaceApp` table created by Story 27.1b; stores `app_id`, `workspace_id`, `status`, `preview_url`, `public_url`.
- **Preview iframe pattern.** 27.1a MVP already renders a preview iframe in `nowing_web`.
- **Deliverables routes pattern** (`app/routes/image_generation_routes.py`). CRUD route pattern for `mark_patch` endpoint.

### [GAP] — new code required

1. **Mark Tool backend.** `app/services/web_builder/mark_tool.py` — DOM/XPath/CSS selector → JSX AST mapping.
2. **JSX AST mutation.** Parser/mutator (Node subprocess with `@babel/parser` / `@babel/generator` / `@babel/traverse` / `@babel/types`) to apply structured patches and rebuild the preview.
3. **Frontend overlay.** Bounding-box selector overlay in `nowing_web`.

## Acceptance Criteria

### AC-1: Visual Element Selection

- **Given** the `Mark Tool` is active on a web preview iframe,  
  **When** the user clicks or hovers an element,  
  **Then** the frontend captures a bounding box, extracts a stable DOM selector (XPath or CSS selector), and sends `{selector, rect, component_hint}` to the backend.

- **Given** the selected element is inside an iframe,  
  **When** the selector is captured,  
  **Then** it is relative to the generated app document and includes enough context to map to a JSX source node.

### AC-2: JSX AST Mutation

- **Given** the backend receives a selector,  
  **When** it maps the selector to the generated JSX AST,  
  **Then** it applies a structured patch (text change, style change, className change, or component replacement) to the corresponding JSX file and re-runs the build/preview.

- **Given** a patch is applied,  
  **When** the build completes,  
  **Then** the preview iframe reloads with the mutated output and the `WorkspaceApp` status is updated.

### AC-3: Unresolvable Selector Handling

- **Given** the selector cannot be mapped to a unique JSX node,  
  **When** the backend processes it,  
  **Then** it returns `status="mark_unresolvable"` and does not mutate the project.

### AC-4: Preview Iframe Security

- **Given** the preview iframe is rendered,  
  **Then** it uses `sandbox="allow-scripts allow-same-origin"` and a separate origin/subdomain where possible to prevent generated scripts from accessing Nowing cookies.

## Validation

- **Unit tests:** `tests/unit/services/web_builder/test_mark_tool.py` — DOM selector to JSX AST mapping, unresolvable selector.
- **Integration tests:** `tests/integration/routes/test_web_builder_routes.py` — `POST /api/v1/web-builder/apps/{app_id}/mark` with mocked AST mutation.
- **Frontend typecheck:** `cd nowing_web && pnpm tsc --noEmit`.
- **Ruff / format:** `ruff check app/services/web_builder app/routes/web_builder_routes.py tests/unit/services/web_builder/test_mark_tool.py`.

## Tags

AD-114, FR-94, web-builder, mark-tool, ast-mutation, jsx, iframe, design-view

## Architecture Compliance

- **AD-114 — Design View Visual "Mark Tool" Canvas AST Mutator:**
  - Iframe preview injects a Bounding Box Selector.
  - When a user marks a UI element, the agent extracts the DOM XPath/CSS and AST-mutates the correct JSX component.
- **NFR-2 (Security):** preview iframe is sandboxed; AST mutation runs in a restricted subprocess, no `eval`/`exec` of generated code.
- **NFR-3 (Observability):** mark operations log and record `TokenUsage` with `usage_type="web_builder_mark"`.

## File Structure Requirements

**NEW files (expected):**
- `nowing_backend/app/services/web_builder/mark_tool.py`
- `nowing_backend/tests/unit/services/web_builder/test_mark_tool.py`
- `nowing_web/components/web-builder/mark-tool-overlay.tsx`

**UPDATE files:**
- `nowing_backend/app/routes/web_builder_routes.py` — add `POST /api/v1/web-builder/apps/{app_id}/mark`.
- `nowing_web/app/dashboard/[workspace_id]/web-builder/page.tsx` — add Mark Tool toggle and overlay.
- `nowing_web/components/web-builder/preview-iframe.tsx` — inject selector overlay.
