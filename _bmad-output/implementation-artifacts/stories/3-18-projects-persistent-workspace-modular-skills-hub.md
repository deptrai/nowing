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
  - `new_chat_routes.py` & chat orchestrator `app/tasks/chat/streaming/flows/new_chat/orchestrator.py` (Chat execution pipelines). **Critical integration point is in `stream_new_chat` right before `build_main_agent_for_thread` where `agent_config.system_instructions` is set (`orchestrator.py:572-578`).**
  - `LangGraphMissionExecutor` (`app/tasks/dsh_worker_langgraph.py`) for background workflows.
- **New Architecture Additions:**
  1. **Entity `Project`:**
     - Database schema: `projects` table (id, workspace_id, name, description, master_instructions, is_archived, created_at, updated_at).
     - Link table: `project_pinned_documents` (project_id, document_id, pinned_at).
     - Link table: `project_skills` (project_id, skill_id, is_active).
  2. **Context Injection Middleware:**
     - Hook before each chat turn in the new chat pipeline: if `thread.project_id` is set, load `project.master_instructions` and append summaries of pinned documents into the system prompt context.
     - Integration must happen after `agent_config.system_instructions` is resolved and before `_clamp_agent_instructions` is called. This ensures project instructions are merged with chat-mode system prompt and clamped together.
  3. **Modular Skills Hub (`.skill.md`):**
     - Table `workspace_skills` (id, workspace_id, name, slug, description, trigger_pattern, content_markdown, skill_type, parameters_schema, is_active, created_at, updated_at).
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
   - **When** pinned to a project via `POST /api/v1/workspaces/{workspace_id}/projects/{project_id}/documents/{document_id}/pin`,
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
  - [ ] 1.2 Viết Alembic migration tạo bảng và foreign keys kết nối với `workspaces`, `documents`, `user` (created_by), and `new_chat_threads`.
  - [ ] 1.3 Thêm `project_id` nullable vào `NewChatThread` model và migration để liên kết thread với project.
  - [ ] 1.4 Bổ sung `PROJECTS_*` permission constants trong `Permission` enum (`app/db/enums.py`) để RBAC có quyền riêng cho project/skills.
- [ ] Task 2: Backend CRUD APIs & Schemas (AC: 1, 3, 4)
  - [ ] 2.1 Định nghĩa Pydantic schemas tại `nowing_backend/app/schemas/projects_schemas.py` và `skills_schemas.py`; export trong `nowing_backend/app/schemas/__init__.py`.
  - [ ] 2.2 Xây dựng REST routes tại `nowing_backend/app/routes/projects_routes.py` (`GET /workspaces/{workspace_id}/projects`, `POST /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/archive`, `POST /{id}/documents/{document_id}/pin`, `DELETE /{id}/documents/{document_id}/pin`).
  - [ ] 2.3 Xây dựng REST routes tại `nowing_backend/app/routes/skills_routes.py` cho Skills Hub (CRUD + parse upload).
- [ ] Task 3: Context Injection Hook in Chat Pipeline (AC: 2)
  - [ ] 3.1 Xây dựng `ProjectContextService` trong `nowing_backend/app/services/project_context_service.py` để format Master Instructions + Pinned Docs.
  - [ ] 3.2 Tích hợp hook vào `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` trước `_clamp_agent_instructions` và `build_main_agent_for_thread`; đảm bảo cả `stream_resume_chat` cũng tái sử dụng cùng một context builder.
- [ ] Task 4: Modular `.skill.md` Parser & Execution Service (AC: 4, 5)
  - [ ] 4.1 Viết `SkillParser` đọc file `.skill.md` với frontmatter validation (`python-frontmatter` hoặc `pyyaml` + regex split).
  - [ ] 4.2 Xây dựng `SkillExecutionService` điều phối prompt/subagent hoặc DSH mission enqueue (`DshMissionService` + `LangGraphMissionExecutor`).
- [ ] Task 5: Unit & Integration Tests (AC: 1-5)
  - [ ] 5.1 Test Project CRUD, RBAC, và pinning (`nowing_backend/tests/unit/routes/test_projects_routes.py`).
  - [ ] 5.2 Test context injection hook (`nowing_backend/tests/unit/services/test_project_context_service.py`).
  - [ ] 5.3 Test `.skill.md` parser và registry (`nowing_backend/tests/unit/services/test_skill_parser.py`).

## Dev Notes

- **Workspace RBAC:** Sử dụng dependency `get_auth_context` + `check_permission` / `check_workspace_access` từ `app/utils/rbac.py` để validate `workspace_id` và roles. Thêm permission mới `projects:create/read/update/delete`, `skills:create/read/update/delete`, `skills:execute` vào `app/db/enums.py:Permission`.
- **Context Length Safety:** Giới hạn token của pinned document context (tối đa 4,000 tokens) để không lấn át user query và lịch sử hội thoại. Dùng `litellm.token_counter` khi có model profile, fallback ước lượng 1 token ≈ 4 ký tự (xem `app/agents/chat/multi_agent_chat/main_agent/middleware/knowledge_tree/middleware.py:_count_tokens`). `ProjectContextService` cần truncate summaries theo thứ tự `pinned_at` mới nhất trước khi đạt ngưỡng.
- **Pinned Doc Summaries:** Lấy từ `Document.source_markdown` hoặc `Document.content` đã truncate; không cần re-chunk. Nếu document archived (`archived_at IS NOT NULL`) thì bỏ qua trong context dù vẫn còn trong pinned list.
- **Skill Portability:** File format `.skill.md` tương thích với chuẩn Markdown + YAML frontmatter.
- **Chat Thread Association:** Khi tạo thread hoặc update thread từ UI, cho phép gán `project_id` (nullable). Context chỉ inject khi `project_id` được set và project không `is_archived`.
- **Context Injection Order:** Project Master Instructions được prepend vào `agent_config.system_instructions` sau chat-mode prompt nhưng trước khi `_clamp_agent_instructions` cắt xén tổng chuỗi xuống 8,000 ký tự (`_MAX_INSTRUCTIONS_LEN`).
- **DSH Mission Skill:** Khi `skill_type='workflow'`, `SkillExecutionService` enqueue `DshMission` với `payload` chứa skill parameters; `LangGraphMissionExecutor` nhận `skill_id` để route vào subgraph phù hợp. Không tạo table mới cho skill run.
- **API Path Convention:** Tất cả project/skills routes nên nằm dưới `/api/v1/workspaces/{workspace_id}/projects` và `/api/v1/workspaces/{workspace_id}/skills` để tận dụng workspace RBAC middleware có sẵn.
- **Migration Command:** `cd nowing_backend && uv run alembic revision -m "add project and skills hub tables"` rồi edit file migration theo pattern `create_table` + `create_foreign_key` + `create_index`.
