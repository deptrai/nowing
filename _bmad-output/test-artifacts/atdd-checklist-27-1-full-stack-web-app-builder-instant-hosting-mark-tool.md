---
stepsCompleted:
  - 'step-01-preflight-and-context'
  - 'step-02-generation-mode'
  - 'step-03-test-strategy'
  - 'step-04c-aggregate'
  - 'step-05-validate-and-complete'
lastStep: 'step-05-validate-and-complete'
lastSaved: '2026-08-24'
workflowType: 'testarch-atdd'
storyId: '27.1'
storyKey: '27-1-full-stack-web-app-builder-instant-hosting-mark-tool'
storyFile: '_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md'
atddChecklistPath: '_bmad-output/test-artifacts/atdd-checklist-27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md'
generatedTestFiles:
  - 'nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py'
  - 'nowing_backend/tests/unit/services/web_builder/test_mark_tool.py'
  - 'nowing_backend/tests/unit/capabilities/test_web_builder_capability.py'
  - 'nowing_backend/tests/integration/routes/test_web_builder_routes.py'
  - 'nowing_web/tests/web-builder/web-builder.spec.ts'
inputDocuments:
  - '_bmad-output/implementation-artifacts/stories/27-1-full-stack-web-app-builder-instant-hosting-mark-tool.md'
  - '_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-unified-nowing-chainlens-dsh-2026-08-17/ARCHITECTURE-SPINE.md'
  - '_bmad/custom/nowing-quality-pipeline.md'
---

# ATDD Checklist - Epic 27, Story 27.1: Full-Stack Web App Builder, 1-Click Hosting `*.apps.nowing.net` & Design View Mark Tool

**Date:** 2026-08-24  
**Author:** Luisphan  
**Primary Test Level:** Fullstack (Backend Unit/Integration + Frontend Playwright E2E)  

---

## Story Summary

Nowing cung cấp một **Autonomous Workstation Full-Stack Web App Builder** cho phép người dùng mô tả ý tưởng ứng dụng bằng ngôn ngữ tự nhiên (tiếng Anh hoặc tiếng Việt). Hệ thống tự động sinh mã nguồn Next.js 16 + React 19 + Tailwind CSS hoàn chỉnh vào thư mục scoped, mở live preview iframe, cho phép can thiệp trực quan qua **Mark Tool** (DOM-to-JSX AST mutation), và xuất bản 1-click lên subdomain HTTPS `https://[app-slug].apps.nowing.net` (hoặc custom domain CNAME).

---

## Acceptance Criteria & Test Scaffolds

### AC-1: LLM Web App Generation & Project Scaffold
- [ ] **Given** natural-language description, **When** submitted to builder, **Then** `WebBuilderService` prompts LLM and writes Next.js + Tailwind project (`package.json`, `app/page.tsx`, `app/layout.tsx`, `tailwind.config.ts`, `next.config.js`, `Dockerfile`) into `FILE_STORAGE_LOCAL_PATH/web-app/{workspace_id}/{app_id}/` and returns `preview_url`.
- [ ] **Given** malformed/non-JSON LLM response, **When** parsed, **Then** returns `status="validation_failed"` without writing files.
- [ ] **Given** file writing operations, **When** path traversal payload is supplied, **Then** `ProjectWriter` strictly raises `ValueError("Path traversal detected")`.
- **Test Scaffold:** `nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py` (RED: `pytest.mark.skip`)

### AC-2: 1-Click Publish to `*.apps.nowing.net`
- [ ] **Given** generated app passes build/lint validation, **When** user clicks Publish, **Then** `WebAppDeployService` builds Docker image, starts container, registers Traefik/Caddy dynamic route at `https://{app-slug}.apps.nowing.net` with valid SSL.
- [ ] **Given** slug collision between workspaces, **When** published, **Then** slug is automatically disambiguated (`{slug}-{short_id}`) without domain collision.
- [ ] **Given** build failure or unhealthy container, **When** deploy runs, **Then** returns `status="deploy_failed"` and preserves build logs.
- **Test Scaffold:** `nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py` & `nowing_backend/tests/integration/routes/test_web_builder_routes.py` (RED: `pytest.mark.skip`)

### AC-3: Custom CNAME / Domain Connect
- [ ] **Given** custom domain configured by user, **When** points CNAME to `cname-ingress.apps.nowing.net`, **Then** `WebAppDeployService` validates DNS and adds dynamic host route.
- [ ] **Given** unresolvable CNAME or domain collision, **When** saved, **Then** returns `409 Conflict` / `422 Unprocessable`.
- **Test Scaffold:** `nowing_backend/tests/integration/routes/test_web_builder_routes.py` (RED: `pytest.mark.skip`)

### AC-4: Design View Mark Tool
- [ ] **Given** Mark Tool active on preview iframe, **When** user clicks element, **Then** captures bounding box, extracts stable DOM selector (XPath/CSS), and sends `{selector, rect, component_hint}`.
- [ ] **Given** selector received, **When** mapped to JSX AST, **Then** applies structured patch (text change, style/className change) to JSX file and triggers live preview update.
- [ ] **Given** unresolvable selector, **When** processed, **Then** returns `status="mark_unresolvable"` without corrupting project files.
- **Test Scaffold:** `nowing_backend/tests/unit/services/web_builder/test_mark_tool.py` & `nowing_web/tests/web-builder/web-builder.spec.ts` (RED: `pytest.mark.skip` / `test.skip`)

### AC-5: Workspace-Scoped App Registry & Cost Observability
- [ ] **Given** app creation, **When** persisted, **Then** `WorkspaceApp` row is recorded in PostgreSQL.
- [ ] **Given** generation, build, and deploy steps, **When** executed, **Then** records `TokenUsage` with `usage_type="web_builder_*"` and `cost_micros`.
- [ ] **Given** `web_builder.build_app` capability, **When** registered, **Then** binds `BillingUnit.WEB_BUILDER_GENERATE`.
- **Test Scaffold:** `nowing_backend/tests/unit/capabilities/test_web_builder_capability.py` (RED: `pytest.mark.skip`)

---

## Red-Phase Test Files Created

1. `nowing_backend/tests/unit/services/web_builder/test_web_builder_service.py` (4 tests - RED)
2. `nowing_backend/tests/unit/services/web_builder/test_mark_tool.py` (3 tests - RED)
3. `nowing_backend/tests/unit/capabilities/test_web_builder_capability.py` (2 tests - RED)
4. `nowing_backend/tests/integration/routes/test_web_builder_routes.py` (4 tests - RED)
5. `nowing_web/tests/web-builder/web-builder.spec.ts` (3 tests - RED)

---

## TDD Implementation Workflow (Task-by-Task Activation)

Khi bắt đầu triển khai code (qua `/bmad-dev-story`):
1. Mở test tương ứng với task hiện tại và bỏ `pytest.mark.skip(...)` hoặc `test.skip()`.
2. Chạy test để xác nhận test **FAIL** đúng với lỗi chưa có code (Red phase verification).
3. Viết code implementation để test **PASS** (Green phase).
4. Refactor và chạy toàn bộ test suite.
