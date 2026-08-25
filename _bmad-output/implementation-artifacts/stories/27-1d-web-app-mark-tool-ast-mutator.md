---
baseline_commit: d06d121a0
story_key: 27-1d
epic: epic-27
story: "27.1d"
title: "Web App Mark Tool & JSX AST Mutator"
status: "done"
---

# Story 27.1d: Web App Mark Tool & JSX AST Mutator

**Status:** `done` — Mark Tool AST mutator + 2026-08-25 review patches: force rebuild without debit, Referer allowlist, compiled-HTML Mark Tool bridge, selector/attr/style hardening, `UsageType.WEB_BUILDER_MARK`.  
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

### Review Findings

##### Patch

- [x] [Review][Patch] Endpoint `POST /api/v1/web-builder/apps/{app_id}/mark` chưa được đăng ký route, hiện trả 501 [nowing_backend/app/routes/web_builder_routes.py:343-353]
- [x] [Review][Patch] Mutator `MarkToolASTMutator` dùng regex thay vì AST parser Babel (`@babel/parser`, `@babel/traverse`, `@babel/types`, `@babel/generator`) trong subprocess có giới hạn [nowing_backend/app/services/web_builder/mark_tool.py:15-99]
- [x] [Review][Patch] Patch thành công không ghi file và không trigger rebuild preview [nowing_backend/app/services/web_builder/mark_tool.py:95-99, nowing_backend/app/routes/web_builder_routes.py:343-353]
- [x] [Review][Patch] Regex sửa nhầm tag lồng nhau, corrupt JSX con bên trong [nowing_backend/app/services/web_builder/mark_tool.py:31-42, 67-78, 83-93]
- [x] [Review][Patch] `patch.value` không escape/validate, cho phép injection JSX attribute hoặc tag [nowing_backend/app/services/web_builder/mark_tool.py:37-41, 52-58]
- [x] [Review][Patch] Selector không unique vẫn patch phần tử đầu tiên thay vì trả `mark_unresolvable` [nowing_backend/app/services/web_builder/mark_tool.py:69-78, 81-93]
- [x] [Review][Patch] Chỉ hỗ trợ `text`, chưa hỗ trợ `attribute` / `replace` và frontend hardcode `type: "text"` [nowing_backend/app/services/web_builder/mark_tool.py:24-62, nowing_web/app/dashboard/\[workspace_id\]/web-builder/page.tsx:274-281, 697-723]
- [x] [Review][Patch] postMessage giữa parent và preview iframe không verify `origin`/`source`; iframe sandbox có `allow-forms`; preview chạy cùng origin [nowing_web/app/dashboard/\[workspace_id\]/web-builder/page.tsx:136-158, 807-815, nowing_backend/app/services/web_builder/preview_renderer.py:76, 241-250, 284-290]
- [x] [Review][Patch] Frontend không capture/transmit `rect` và `component_hint` theo AC-1 [nowing_web/app/dashboard/\[workspace_id\]/web-builder/page.tsx:136-148, 274-281]
- [x] [Review][Patch] Không record `TokenUsage` với `usage_type="web_builder_mark"` [nowing_backend/app/routes/web_builder_routes.py:343-353, nowing_backend/app/services/web_builder/mark_tool.py:1-99]
- [x] [Review][Patch] Thiếu file `mark-tool-overlay.tsx` và `preview-iframe.tsx` theo File Structure Requirements [nowing_web/components/web-builder/]
- [x] [Review][Patch] Unit test quá nông, thiếu integration test cho `/mark` [nowing_backend/tests/unit/services/web_builder/test_mark_tool.py:15-82, nowing_backend/tests/integration/routes/test_web_builder_routes.py]

### Review Findings (code review 2026-08-25)

##### Decision needed

- [x] [Review][Decision] Mark trên app `preview_ready` không rebuild — resolved: `trigger_async_build(..., force=True, skip_debit=True)`. Rebuild để compiled preview khớp source; không debit vì mark không phải lượt build mới. Frontend set `status=building` và poll tới `preview_ready`.
- [x] [Review][Decision] Preview iframe vẫn cùng origin API — resolved: giữ preview trên API origin (cần auth cookie) + allowlist parent origin (`NEXT_FRONTEND_URL` / localhost). Tách `*.apps.nowing.net` là public deploy 27.1c, không phải authenticated preview.

##### Patch

- [x] [Review][Patch] `_allowed_preview_origin` tin raw `Referer` scheme/netloc, không allowlist `NEXT_FRONTEND_URL` [nowing_backend/app/routes/web_builder_routes.py:612-622]
- [x] [Review][Patch] Nhánh compiled preview HTML không inject `__wbAllowedOrigin` / Mark Tool bridge [nowing_backend/app/routes/web_builder_routes.py:736-745]
- [x] [Review][Patch] Selector rỗng/`#`/`.` match mọi JSX element (single-element file bị patch nhầm) [nowing_backend/app/services/web_builder/mark_tool.py:117-187]
- [x] [Review][Patch] `attr_name` viết raw vào source; không allowlist JSX identifier [nowing_backend/app/services/web_builder/mark_tool.py:316-329]
- [x] [Review][Patch] `file_path` không giới hạn `.tsx`/`.jsx` [nowing_backend/app/routes/web_builder_routes.py:373-383]
- [x] [Review][Patch] Source TSX `has_error` vẫn walk/match; replace snippet không re-parse full file [nowing_backend/app/services/web_builder/mark_tool.py:68-80, 348-369]
- [x] [Review][Patch] Không có first-class `style` patch (AC-2: text/style/className/replace) [nowing_backend/app/services/web_builder/mark_tool.py:267-287]
- [x] [Review][Patch] Selector DOM nông (id hoặc tag+firstClass); class token rỗng khi `className` leading space [nowing_backend/app/services/web_builder/preview_renderer.py:282-291]
- [x] [Review][Patch] `usage_type="web_builder_mark"` không có `UsageType`; record+commit trước `write_text` [nowing_backend/app/routes/web_builder_routes.py:405-434]
- [x] [Review][Patch] Text patch thay toàn bộ children, gồm nested JSX [nowing_backend/app/services/web_builder/mark_tool.py:289-314]
- [x] [Review][Patch] Apply không disable khi `patchType=attribute` mà `attributeName` rỗng [nowing_web/components/web-builder/mark-tool-overlay.tsx:81-84]
- [x] [Review][Patch] Thiếu unit/integration test cho empty selector, attr-name, Referer allowlist, compiled-HTML bridge, `web_builder_mark` call_details [nowing_backend/tests/unit/services/web_builder/test_mark_tool.py, nowing_backend/tests/integration/routes/test_web_builder_routes.py]
- [x] [Review][Patch] Selector `tag.a.b` giữ mọi class (không chỉ class cuối) [nowing_backend/app/services/web_builder/mark_tool.py]

##### Defer

- [x] [Review][Defer] Concurrent mark read–mutate–write không file lock [nowing_backend/app/routes/web_builder_routes.py:385-442] — deferred, pre-existing
- [x] [Review][Defer] className/id expression (`className={cn("foo")}`) không match selector DOM [nowing_backend/app/services/web_builder/mark_tool.py:227-237] — deferred, pre-existing
