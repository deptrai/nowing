---
title: 'Story 3.18: Projects Persistent Workspace & Modular Skills Hub'
type: feature
created: '2026-09-02'
baseline_commit: 0bd64b972d8f038864c038134c355a9d1ff74856
status: done
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/epic-3-context.md
  - _bmad-output/implementation-artifacts/stories/3-18-projects-persistent-workspace-modular-skills-hub.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Người dùng mất thời gian copy-paste master instructions và tài liệu tham khảo vào mỗi lượt chat, và agent không thể gọi workflow chuyên biệt theo domain.

**Approach:** Thêm lớp Project trong workspace: mỗi project có master instructions, pinned documents, và skill hub `.skill.md`; project context tự động inject vào system prompt mỗi lượt chat; skill có thể kích hoạt prompt hoặc enqueue DSH mission.

## Boundaries & Constraints

**Always:**
- Dữ liệu project/skill/pin thuộc về một workspace và tuân theo RBAC hiện có (`check_permission`, `check_workspace_access`).
- Context injection bounded: tổng pinned doc summary tối đa 4,000 tokens, project master instructions nằm trong 8,000 chars clamp của `_clamp_agent_instructions`.
- Không tạo thêm bảng mission/skill run; DSH skill dùng `DshMissionService.create_mission` với `mission_type='skill'`.
- Mọi migration phải backwards-compatible: `project_id` trên `new_chat_threads` nullable, `NewChatThread` model thêm relationship.

**Ask First:**
- Nếu workspace plan `free` cần giới hạn số project hoặc pinned doc/skill: hỏi trước khi thêm workspace limits.
- Nếu skills cần expose thành MCP tools ngay trong story này.

**Never:**
- Không chỉnh sửa frontend (story này backend + chat context only).
- Không tách `Project` thành microservice.
- Không dùng `frontmatter` package chưa có trong deps; parse `.skill.md` bằng `pyyaml` + regex (có sẵn).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_CREATE_PROJECT | `POST /workspaces/{id}/projects` với `{name, description?, master_instructions?}` | `ProjectRead` 201, scoped workspace | 403 nếu không có `projects:create` |
| HAPPY_PIN_DOC | `POST /workspaces/{id}/projects/{pid}/documents/{did}/pin` | 200, document xuất hiện trong `GET /projects/{pid}` | 404 nếu doc không thuộc workspace; 403 nếu thiếu quyền |
| HAPPY_CHAT_WITH_PROJECT | Thread có `project_id` set; project active + pinned docs | System prompt được prepend master instructions + doc summaries trước khi `_clamp_agent_instructions` | Bỏ qua nếu project archived hoặc không tồn tại |
| HAPPY_SKILL_UPLOAD | `POST /workspaces/{id}/skills` với `.skill.md` body | `WorkspaceSkillRead` 201, parsed frontmatter | 400 nếu frontmatter thiếu `name`/`trigger` |
| HAPPY_SKILL_TRIGGER | `/skill-name` trong user query hoặc agent detect pattern | Skill prompt được thêm vào context hoặc DSH mission enqueued | 404 nếu skill không active |
| ERROR_DUPLICATE_PIN | Pin document đã pinned | 409 conflict hoặc idempotent 200 (chọn 200 idempotent) | N/A |
| ERROR_ARCHIVED_PROJECT | Thread có `project_id` nhưng project `is_archived=true` | Không inject project context | N/A |
| ERROR_SKILL_INVALID_YAML | `.skill.md` frontmatter parse fail | 400 với `detail=Invalid YAML frontmatter` | N/A |

</frozen-after-approval>

## Code Map

- `nowing_backend/app/models/projects.py` -- Tạo mới: `Project`, `ProjectPinnedDocument`, `WorkspaceSkill`, `ProjectSkill`.
- `nowing_backend/app/models/chat.py` -- Thêm `project_id` (Integer, FK projects.id, nullable) và `project` relationship vào `NewChatThread`.
- `nowing_backend/app/models/users.py` -- Nguồn `WorkspaceMembership`, `WorkspaceRole`, `User` (cần `created_by` cho project/skill).
- `nowing_backend/app/models/workspaces.py` -- `Workspace` cần relationship mới `projects` (nếu muốn navigate), không bắt buộc.
- `nowing_backend/app/models/documents.py` -- `Document` cần relationship/presence check khi pin.
- `nowing_backend/app/db/enums.py` -- Thêm `PROJECTS_CREATE/READ/UPDATE/DELETE`, `SKILLS_CREATE/READ/UPDATE/DELETE/EXECUTE` vào `Permission`.
- `nowing_backend/app/db/__init__.py` -- Export các model mới.
- `nowing_backend/app/schemas/projects_schemas.py` -- Mới: `ProjectCreate`, `ProjectUpdate`, `ProjectRead`, `ProjectListParams`.
- `nowing_backend/app/schemas/skills_schemas.py` -- Mới: `SkillCreate`, `SkillUpdate`, `SkillRead`, `SkillParseRequest`.
- `nowing_backend/app/schemas/__init__.py` -- Export schema mới.
- `nowing_backend/app/schemas/new_chat.py` -- Thêm `project_id` vào `NewChatThreadCreate`, `NewChatThreadUpdate`, `NewChatThreadRead`.
- `nowing_backend/app/routes/projects_routes.py` -- Mới: CRUD + pin/unpin endpoints.
- `nowing_backend/app/routes/skills_routes.py` -- Mới: CRUD + parse upload.
- `nowing_backend/app/routes/__init__.py` -- Include 2 routers mới.
- `nowing_backend/app/routes/new_chat/threads.py` -- Thêm `project_id` vào create/update logic.
- `nowing_backend/app/services/project_context_service.py` -- Mới: `build_project_context(project, pinned_docs, llm=None) -> str` bounded 4,000 tokens pinned summaries.
- `nowing_backend/app/services/skill_parser.py` -- Mới: `SkillParser.parse(content: str) -> SkillDefinition`; validate YAML frontmatter.
- `nowing_backend/app/services/skill_execution_service.py` -- Mới: `execute(skill, params)` hoặc `enqueue_skill_mission(skill, params)`.
- `nowing_backend/app/services/dsh_mission_service.py` -- Dùng `create_mission` với `mission_type='skill'`.
- `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` -- Inject context sau `get_chat_mode_system_prompt` (dòng 572-578) và trước `_clamp_agent_instructions`.
- `nowing_backend/app/tasks/chat/streaming/flows/resume_chat/orchestrator.py` -- Tái sử dụng cùng `_merge_project_context` helper.
- `nowing_backend/app/agents/chat/shared/context.py` -- Có thể thêm `project_id` vào `NowingContextSchema` nếu middleware cần, nhưng không bắt buộc cho v1.
- `nowing_backend/alembic/versions/` -- Migration mới tạo 4 bảng + `project_id` trên `new_chat_threads`.
- `nowing_backend/tests/unit/routes/test_projects_routes.py` -- Mới.
- `nowing_backend/tests/unit/services/test_project_context_service.py` -- Mới.
- `nowing_backend/tests/unit/services/test_skill_parser.py` -- Mới.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/db/enums.py` -- Thêm permission constants `projects:*`, `skills:*`, `skills:execute` -- RBAC cho project và skill.
- [x] `nowing_backend/app/models/projects.py` -- Định nghĩa `Project`, `ProjectPinnedDocument`, `WorkspaceSkill`, `ProjectSkill` với FK đúng.
- [x] `nowing_backend/app/models/chat.py` -- Thêm `project_id` nullable, `project` relationship.
- [x] `nowing_backend/alembic/versions/` -- Tạo migration tạo 4 bảng mới + `project_id` trên `new_chat_threads`.
- [x] `nowing_backend/app/schemas/projects_schemas.py` -- Pydantic schemas CRUD project.
- [x] `nowing_backend/app/schemas/skills_schemas.py` -- Pydantic schemas CRUD skill + parse.
- [x] `nowing_backend/app/schemas/new_chat.py` -- Thêm `project_id` vào create/update/read thread schemas.
- [x] `nowing_backend/app/schemas/__init__.py` -- Export schemas mới.
- [x] `nowing_backend/app/routes/projects_routes.py` -- CRUD + pin/unpin endpoints dưới `/workspaces/{id}/projects`.
- [x] `nowing_backend/app/routes/skills_routes.py` -- CRUD + `POST /skills/parse` endpoints.
- [x] `nowing_backend/app/routes/__init__.py` -- Include 2 routers mới.
- [x] `nowing_backend/app/routes/new_chat/threads.py` -- Cho phép `project_id` trong create/update thread.
- [x] `nowing_backend/app/services/project_context_service.py` -- Build bounded project context, truncate pinned docs theo `pinned_at` desc.
- [x] `nowing_backend/app/services/skill_parser.py` -- Parse `.skill.md` YAML frontmatter + Markdown body.
- [x] `nowing_backend/app/services/skill_execution_service.py` -- Execute prompt skill hoặc enqueue DSH skill mission.
- [x] `nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py` -- Inject project context vào `agent_config.system_instructions` trước `_clamp_agent_instructions`; cập nhật resume chat.
- [x] `nowing_backend/tests/unit/routes/test_projects_routes.py` -- Test project CRUD + pinning.
- [x] `nowing_backend/tests/unit/services/test_project_context_service.py` -- Test bounded context building.
- [x] `nowing_backend/tests/unit/services/test_skill_parser.py` -- Test frontmatter parse + validation.

**Acceptance Criteria:**
- Given authenticated user, when create/list/update/archive project, then project scoped to workspace_id with RBAC enforcement.
- Given active project with master instructions and pinned docs, when chat on a thread with project_id, then system prompt includes bounded master instructions + pinned doc summaries.
- Given workspace document, when pinned to a project, then appears in project's pinned list and unpinning does not delete document.
- Given `.skill.md` with valid frontmatter, when uploaded, then parsed and stored in workspace_skills.
- Given registered active skill, when agent detects trigger or user invokes `/skill-name`, then skill prompt executes or DSH mission is enqueued.

## Spec Change Log

## Design Notes

**Context injection order:**
1. Resolve base `agent_config.system_instructions`.
2. Merge with `get_chat_mode_system_prompt` (mode prompt).
3. Prepend `ProjectContextService.build_context(project, pinned_docs, llm)`.
4. Gọi `_clamp_agent_instructions(combined)` (8k char limit).
5. Truyền vào `build_main_agent_for_thread`.

**Token counting:** Dùng cùng pattern `knowledge_tree/middleware.py`: thử `litellm.token_counter` với model profile, fallback `len(text)/4`.

**Skill parser:** YAML frontmatter tách bằng regex `^---\n(.*?)\n---\n(.*)$`. Required fields: `name`, `trigger`. Optional: `description`, `skill_type` (`prompt` | `workflow`, default `prompt`), `parameters` (JSON Schema dict). Body là `content_markdown`.

**Skill execution:**
- `skill_type='prompt'`: thêm content_markdown vào context như một system prompt phụ.
- `skill_type='workflow'`: gọi `DshMissionService.create_mission(session, workspace_id, user_id, mission_type='skill', payload={skill_id, parameters})`.

## Verification

**Commands:**
- `cd nowing_backend && uv run ruff check app/models/projects.py app/routes/projects_routes.py app/routes/skills_routes.py app/services/project_context_service.py app/services/skill_parser.py app/tasks/chat/streaming/flows/new_chat/orchestrator.py` -- expected: no errors.
- `cd nowing_backend && uv run pytest tests/unit/routes/test_projects_routes.py tests/unit/services/test_project_context_service.py tests/unit/services/test_skill_parser.py -q` -- expected: all pass.
- `cd nowing_backend && uv run alembic upgrade head` -- expected: migration applies cleanly.
- `cd nowing_backend && uv run pytest tests/unit/tasks/chat/test_new_chat_orchestrator.py -q` -- expected: existing tests pass.

**Manual checks:**
- Confirm project context appears in prompt when chat with `project_id` set.
- Confirm `_clamp_agent_instructions` still clamps total combined instructions to 8k chars.
