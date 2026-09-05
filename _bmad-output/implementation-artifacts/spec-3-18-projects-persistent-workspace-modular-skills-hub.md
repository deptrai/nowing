---
title: 'Story 3.18: Projects Persistent Workspace & Modular Skills Hub'
type: feature
created: '2026-09-02'
baseline_commit: 0bd64b972d8f038864c038134c355a9d1ff74856
status: review
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

## Review Findings

### Code review complete. 0 decision-needed, 19 patch, 3 defer, 4 dismissed as noise.

**Patch findings:**

- [ ] [Review][Patch] `project_context_service.py:170` — `raw_text[:allowed_chars].rsplit(" ", 1)[0]` fails on spaceless text (URLs, CJK, minified JSON). [patch]
- [ ] [Review][Patch] `project_context_service.py` — Pseudo-XML context tags interpolate raw content without escaping; prompt-injection/XML-breakout risk. [patch]
- [ ] [Review][Patch] `new_chat` / `resume_chat` orchestrator — Project context (up to 4,000 tokens ~ 16k chars) prepended before `_clamp_agent_instructions` (8k char limit) can starve base system prompt and tool rules. [patch]
- [ ] [Review][Patch] `project_context_service.py:54-65` — `_count_tokens` checks `getattr(llm, "model", None)` but misses LangChain `model_name` attribute. [patch]
- [ ] [Review][Patch] `routes/new_chat/threads.py:219` — `search_threads` constructs `ThreadListItem` without `project_id`, stripping project association from search results. [patch]
- [ ] [Review][Patch] `routes/new_chat/threads.py:308-317` / `536-538` — `create_thread` and `update_thread` accept `project_id` without validating workspace/archived ownership. [patch]
- [ ] [Review][Patch] `routes/projects_routes.py:86-95` — `_get_project_with_pins` loads `pinned_documents` but not nested `Document`, causing `document_title`/`document_type` to resolve as `None`. [patch]
- [ ] [Review][Patch] `routes/projects_routes.py:405-410` — `pin_document` does not reject archived documents or cross-workspace documents. [patch]
- [ ] [Review][Patch] `routes/projects_routes.py:423` / `skills_routes.py:688` — Duplicate pin/skill slug under concurrent requests not caught as `IntegrityError`, leading to 500 instead of idempotent 200/409. [patch]
- [ ] [Review][Patch] `app/zero_publication.py:61-65` — `NEW_CHAT_THREAD_COLS` missing `project_id`, breaking Zero publication for project-linked threads. [patch]
- [ ] [Review][Patch] `alembic/versions/237_add_projects_and_skills.py` — Migration does not call `apply_publication(op.get_bind())` per project invariants. [patch]
- [ ] [Review][Patch] `skill_parser.py:319-328` — Frontmatter regex `^---` fails with leading BOM/whitespace. [patch]
- [ ] [Review][Patch] `skill_parser.py:364-367` — Non-dict `parameters` silently reset to `{}` instead of raising `SkillParseError`. [patch]
- [ ] [Review][Patch] `skill_execution_service.py:253-255` — Naive `str.replace` template substitution allows cascading/re-entrant replacement. [patch]
- [ ] [Review][Patch] `schemas/skills_schemas.py:57` — `SkillParseResponse.skill_type` typed as `str` instead of `Literal["prompt", "workflow"]`. [patch]
- [ ] [Review][Patch] `routes/skills_routes.py:504-541` — `parse_skill_file` accepts unbounded `file_content`, risking ReDoS/memory exhaustion. [patch]
- [ ] [Review][Patch] `routes/skills_routes.py:755-797` — `execute_skill` passes `parameters` to `SkillExecutionService` without validating against `skill.parameters_schema`. [patch]
- [ ] [Review][Patch] `models/projects.py:36-38` — Single-column `is_archived` index has low cardinality; prefer composite `(workspace_id, is_archived)`. [patch]
- [ ] [Review][Patch] `models/projects.py` — `ProjectSkill` link table lacks `created_at`/`updated_at` audit timestamps. [patch]

**Defer findings:**

- [x] [Review][Defer] `alembic/versions/237_add_projects_and_skills.py` — Redundant explicit indexes on primary key columns (dismissed as minor optimization, Postgres creates unique indexes for PK automatically). [defer]
- [x] [Review][Defer] `schemas/projects_schemas.py:58-61` — `ProjectListParams` defined but not wired as `Depends()` in routes (future pagination refactor). [defer]
- [x] [Review][Defer] `tests/*` — Missing dedicated unit tests for `SkillExecutionService` and orchestrator project context injection (addressed in test-first hardening pass). [defer]

**Dismissed findings:**

- RLS policy gap (other tenant-scoped tables use RBAC in app layer; DB RLS not required by current spec). [dismiss]
- Migration docstring revision line mismatch (cosmetic). [dismiss]
- `Project.new_chat_threads` `foreign_keys` string syntax (functional in SQLAlchemy 2.0). [dismiss]
- `models/users.py` missing reciprocal relationships for `created_by` (optional navigation). [dismiss]
