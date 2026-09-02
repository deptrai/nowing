---
baseline_commit: b68173656c506d3c1fae361d751fd1df4d59ecf7
---

# Story 3.18: Projects Persistent Workspace & Modular Skills Hub

Status: ready-for-dev

<!-- Governed by PRD (Epic 3), Architecture Decisions AD-1, AD-112, and Skills Hub Specification -->

## Story

As a power user, business analyst, or multi-agent orchestrator,
I want to organize conversations and documents into structured **Projects** with **Master Instructions**, **Pinned Documents**, and a **Modular Skills Hub** (`.skill.md`),
So that every chat turn automatically inherits domain-specific guidelines, reference context, and specialized executable sub-workflows without manual copy-pasting.

## Context & Architecture Alignment

- **Existing Foundation:**
  - `workspaces_routes.py` (Workspace CRUD, member roles, limits, MCP tool toggles).
  - `prompts_routes.py` (Custom prompts, system prompt overrides).
  - `documents_routes.py` (File/Note/Extension attachments and knowledge indexing).
  - `new_chat_routes.py` & `agent_chat_routes.py` (Chat execution pipelines).
  - `LangGraphMissionExecutor` (`app/tasks/dsh_worker_langgraph.py`) for background workflows.
- **New Architecture Additions:**
  1. **Entity `Project`:**
     - Database schema: `projects` table (id, workspace_id, name, description, master_instructions, is_archived, created_at, updated_at).
     - Link table: `project_pinned_documents` (project_id, document_id, pinned_at).
     - Link table: `project_skills` (project_id, skill_id, is_active).
  2. **Context Injection Middleware:**
     - Hook before each chat turn in `new_chat_routes.py`: if `project_id` is supplied, load `project.master_instructions` and append summaries of pinned documents into the system prompt context.
  3. **Modular Skills Hub (`.skill.md`):**
     - Table `workspace_skills` (id, workspace_id, name, slug, description, trigger_pattern, content_markdown, skill_type, parameters_schema).
     - Parser for `.skill.md` format (YAML frontmatter + Markdown body with instruction prompts or LangGraph execution definitions).
     - Skill registry and tool dispatcher in agent execution loops.

## Acceptance Criteria

1. **Project CRUD & Workspace Isolation:**
   - **Given** an authenticated user in a workspace,
   - **When** the user creates/updates/lists/archives a project,
   - **Then** the project is scoped strictly to `workspace_id` with RBAC enforcement (owner/admin/member can access, observer read-only).

2. **Master Instructions & Pinned Documents:**
   - **Given** an active project with `master_instructions` and 1+ pinned documents,
   - **When** a user creates or sends a message to a chat thread associated with `project_id`,
   - **Then** the chat runtime automatically prepends the project's master instructions and pinned document summaries to the LLM system prompt without exceeding the context token limit.

3. **Document Pinning & Synchronization:**
   - **Given** a workspace document in `documents` table,
   - **When** pinned to a project via `POST /api/v1/projects/{project_id}/documents/{document_id}/pin`,
   - **Then** it appears in the project's pinned list, and unpinning removes it without deleting the underlying document.

4. **Modular Skills Parser & Registry (`.skill.md`):**
   - **Given** a `.skill.md` definition with YAML frontmatter (`name`, `description`, `trigger`, `parameters`),
   - **When** uploaded or created in the Skills Hub,
   - **Then** it is parsed, validated, and registered in `workspace_skills`.

5. **Skill Execution & Subgraph Dispatch:**
   - **Given** a registered skill in a project,
   - **When** an agent detects the skill trigger or the user invokes it via `/skill-name`,
   - **Then** the system executes the modular skill prompt (or dispatches a DSH mission/LangGraph task when `skill_type='workflow'`).

## Tasks / Subtasks

- [ ] Task 1: Database Migration & SQLAlchemy Models (AC: 1, 3, 4)
  - [ ] 1.1 Tạo `Project`, `ProjectPinnedDocument`, `WorkspaceSkill`, `ProjectSkill` models trong `nowing_backend/app/models/projects.py`.
  - [ ] 1.2 Viết Alembic migration tạo bảng và foreign keys kết nối với `workspaces` và `documents`.
- [ ] Task 2: Backend CRUD APIs & Schemas (AC: 1, 3, 4)
  - [ ] 2.1 Định nghĩa Pydantic schemas tại `nowing_backend/app/schemas/projects_schemas.py` và `skills_schemas.py`.
  - [ ] 2.2 Xây dựng REST routes tại `nowing_backend/app/routes/projects_routes.py` (`GET /`, `POST /`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/pin`, `DELETE /{id}/pin`).
  - [ ] 2.3 Xây dựng REST routes tại `nowing_backend/app/routes/skills_routes.py` cho Skills Hub.
- [ ] Task 3: Context Injection Hook in Chat Pipeline (AC: 2)
  - [ ] 3.1 Xây dựng `ProjectContextService` trong `nowing_backend/app/services/project_context_service.py` để format Master Instructions + Pinned Docs.
  - [ ] 3.2 Tích hợp hook vào `new_chat_routes.py` và chat orchestrator.
- [ ] Task 4: Modular `.skill.md` Parser & Execution Service (AC: 4, 5)
  - [ ] 4.1 Viết `SkillParser` đọc file `.skill.md` với frontmatter validation (`frontmatter` / `pyyaml`).
  - [ ] 4.2 Xây dựng `SkillExecutionService` điều phối prompt/subagent hoặc DSH mission.
- [ ] Task 5: Unit & Integration Tests (AC: 1-5)
  - [ ] 5.1 Test Project CRUD, RBAC, và pinning (`tests/unit/routes/test_projects_routes.py`).
  - [ ] 5.2 Test context injection hook (`tests/unit/services/test_project_context_service.py`).
  - [ ] 5.3 Test `.skill.md` parser và registry (`tests/unit/services/test_skill_parser.py`).

## Dev Notes

- **Workspace RBAC:** Sử dụng dependency `get_current_workspace_context` để validate `workspace_id` và roles.
- **Context Length Safety:** Giới hạn token của pinned document context (tối đa 4,000 tokens) để không lấn át user query và lịch sử hội thoại.
- **Skill Portability:** File format `.skill.md` tương thích với chuẩn Markdown + YAML frontmatter.
