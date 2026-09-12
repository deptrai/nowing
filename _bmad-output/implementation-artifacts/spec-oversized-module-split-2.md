---
title: 'Oversized module split — round 2 (agents/chat, chainlens, connectors)'
type: 'refactor'
created: '2026-09-12'
status: 'in-review'
baseline_commit: '127dde4ee4ccc0c29bea2870d11275cb1e5dbf39'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 9 backend modules vẫn >1000 dòng sau đợt tách đầu (workspaces/rbac/gateway/telemetry/limits đã xong ở `57befe8c0`, `faf343a9e`, `ef5248edb`). File lớn làm review khó, merge-conflict nhiều, và vi phạm invariant "no god-module" của project.

**Approach:** Tách từng file thành package/module theo ranh giới domain sẵn có trong code (section markers, nhóm method), giữ nguyên public import path bằng compat shim hoặc package `__init__`, một file = một commit.

## Boundaries & Constraints

**Always:**
- Public API & import path giữ nguyên: mọi `from <old_path> import X` hiện có phải chạy được sau split (shim re-export hoặc package `__init__`).
- Route files: route path set + tag + response model phải **identical** trước/sau (verify bằng diff của decorator paths).
- Monkeypatch/`patch()` targets trong test phải trỏ về module nơi name lookup thực sự xảy ra (bẫy đã gặp ở đợt 1 — `routes.persist_inbound_event` phải thành `webhook_routes.persist_inbound_event`).
- Single-class file → tách bằng mixin composition, giữ nguyên class name + instance/class method surface.
- Mỗi file tách xong: `ruff check --fix` + `ruff format` phạm vi file đó, chạy test liên quan, verify `python -c "import app.app"`, rồi mới commit.
- Module-level singleton/state (`_state_manager`, `_token_encryption`...) phải nằm ở **một** module duy nhất, các module khác import — tuyệt đối không copy.

**Ask First:**
- `app/routes/web_builder_routes.py`: user đang có Epic 31 work trong vùng web_builder. Nếu file có uncommitted change hoặc test mới liên quan, HALT hỏi user trước khi tách.
- Nếu phát hiện file nào đã được tách một phần hoặc đang được refactor bởi người khác.

**Never:**
- Không đụng `app/services/web_builder/deploy/service.py` (user Epic 31, đang dở).
- Không đổi behavior, không "fix nhân tiện" bug phát hiện trong lúc tách — log vào deferred-work thay vì sửa.
- Không tách file mà không có test nào cover phần bị move (ít nhất phải có import test hoặc smoke verify).
- Không dùng star-import (`from x import *`) để re-export trong production code.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| IMPORT_COMPAT | `from app.routes.web_builder_routes import router` (và các path cũ khác) | Import thành công, cùng object identity | N/A |
| ROUTE_PARITY | decorator path set trước/sau split | diff rỗng | Fail → hoàn tác file đó |
| PATCH_TARGET | test patch `old.module.attr` | Patch đến module mới nơi lookup xảy ra | Update test, không để patch trượt lặng |
| SINGLETON | module state (`_state_manager`...) | Một instance duy nhất sau split | Import về module chủ, không copy |
| CIRCULAR | method gọi singleton/class từ module khác | Lazy import trong hàm (pattern đã dùng ở `workspace_limits/checks.py`) | Không import vòng ở top-level |

</frozen-after-approval>

## Code Map

Đợt 1 pattern để tái dùng: `app/routes/workspaces/`, `app/routes/rbac/`, `app/routes/gateway_webhook/` (route split), `app/services/admin_telemetry/`, `app/services/workspace_limits/` (mixin split).

Files cần tách (theo thứ tự đề xuất — dễ → khó):

- `app/connectors/notion_history.py` (1081) — `NotionHistoryConnector` class 73-1081 + `NotionAPIError`. Mixin split: `notion_history/` package {`service`, `blocks`, `comments`, ...} hoặc extract helper module; giữ `NotionAPIError` + class name.
- `app/agents/chat/multi_agent_chat/shared/middleware/filesystem/backends/kb_postgres.py` (1069) — `KBPostgresBackend` class 110-1069, module fns `render_full_document`/`paginate_listing`. Mixin split theo op group (list/read/write/search) hoặc extract module fns ra `_helpers`.
- `app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/report.py` (1107) — helpers (27-562) + `create_generate_report_tool` (563+). Tách `_parsing.py` (sections/metadata/stitch) + `_revise.py`, giữ tool factory.
- `app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/task_tool.py` (1133) — helpers + `build_task_tool_with_parent_config` factory khổng lồ (142+). Extract internals ra `_impl.py`.
- `app/capabilities/chainlens/research/executor.py` (1151) — `_SSEParser` class 145-759 (~600 dòng!) + `_call_chainlens` + `execute_with_context` + `build_research_executor`. Tách `sse_parser.py`.
- `app/tasks/chat/streaming/flows/new_chat/orchestrator.py` (1202) — `stream_new_chat` 240-1202 (~960 dòng một hàm). Extract stage helpers ra `_stages.py` hoặc tách theo phase; `_AgentNotFoundError`, `_merge_registry_agent_config` giữ/extract.
- `app/agents/chat/multi_agent_chat/shared/tools/mcp/tool.py` (1496) — helpers + stdio (206-610) + http (314-857) + oauth (858-1050) + auth-error (1056+). Package `tool/` {`_helpers`, `stdio`, `http`, `oauth`} + shim `tool.py`.
- `app/agents/chat/multi_agent_chat/main_agent/middleware/kb_persistence/middleware.py` (1483) — helper sections (folder 83-175, document 181-310, move 316-388...) + middleware class. Extract helpers ra `_helpers.py`.
- `app/routes/web_builder_routes.py` (1150) — helpers 55-163 + endpoints theo nhóm generate/publish/build/apps. Package `web_builder/` — **Ask First** nếu có uncommitted Epic 31 change.

## Tasks & Acceptance

**Execution:**
- [x] Mỗi file trong Code Map — tách theo plan, một file = một commit theo thứ tự listed — mechanical split, verify per-file trước khi sang file kế
- [x] `tests/` — cập nhật patch target khi module path đổi — chỉ sửa patch string/import, không đổi test logic

**Acceptance Criteria:**
- Given file đã tách, when chạy `grep -rn "from <old_path> import" app/ tests/` và import mỗi symbol, then tất cả resolve được và `python -c "import app.app"` OK
- Given route file đã tách, when so sánh decorator path set trước/sau, then identical (route count + paths + tags)
- Given file đã tách, when chạy test suite liên quan (`pytest tests/unit/<area>` -q), then không test nào fail so với trước split
- Given tất cả 9 file, when `find app -name "*.py" | xargs wc -l | sort -rn | head`, then không file nào trong list còn >800 dòng (trừ file bị Ask First defer)

## Design Notes

Bẫy đã gặp ở đợt 1 — áp dụng cho toàn bộ đợt 2:

1. **Patch trượt**: `patch("old.module.attr")` không bắt được sau khi move → phải update string target. Check bằng `grep -rn "patch.*<module>" tests/` trước khi tách.
2. **Class-method patch vẫn ổn**: `patch("...WorkspaceLimitService.method")` patch trên class object → mixin composition không phá.
3. **Singleton trong method**: nếu code gọi module-global singleton → lazy import trong hàm thay vì top-level circular import.
4. **Module constants giữa imports**: đặt sau block import hoặc trong `_helpers.py`, không giữa hai import statement (E402).
5. **`inspect.getsource` trên re-exported fn** vẫn hoạt động (resolve về file thật).

## Verification

**Commands:**
- `cd nowing_backend && .venv/bin/ruff check app/` — expected: pass
- `cd nowing_backend && .venv/bin/python -c "import app.app; print('OK')"` — expected: `OK`
- Per file: `pytest tests/unit/<area liên quan> -q` — expected: pass như trước split
- Per route file: so sánh `git show HEAD:<f> | grep -oE '@router\.(get|post|patch|delete)\("[^"]*"'` với set mới — expected: diff rỗng

## Suggested Review Order

**Route Compatibility & Shims**

- Compat shim re-export facade — verifies every old import path still resolves
  [`web_builder_routes.py:1`](../../nowing_backend/app/routes/web_builder_routes.py#L1)
- Shared route helpers — single source of truth for member/quota checks
  [`_helpers.py:1`](../../nowing_backend/app/routes/web_builder/_helpers.py#L1)
- Core app lifecycle endpoints — publish/build endpoints moved here
  [`apps.py:45`](../../nowing_backend/app/routes/web_builder/apps.py#L45)
- Preview & static files serving — complex iframe proxy + routing logic
  [`preview.py:204`](../../nowing_backend/app/routes/web_builder/preview.py#L204)
- Streaming generation endpoints — SSE/SSE-like handler moved
  [`generate.py:31`](../../nowing_backend/app/routes/web_builder/generate.py#L31)
- Public host router — catches wildcard domains to serve apps
  [`host.py:17`](../../nowing_backend/app/routes/web_builder/host.py#L17)

**Chat Flow & Orchestrator**

- Main entry orchestrator — stream processing pipeline now delegates to stages
  [`orchestrator.py:1`](../../nowing_backend/app/tasks/chat/streaming/flows/new_chat/orchestrator.py#L1)
- Stream stage logic — extracted per-step logic (memory, tools, models)
  [`_stages.py:1`](../../nowing_backend/app/tasks/chat/streaming/flows/new_chat/_stages.py#L1)
- In-stream rate-limit recovery — dedicated error handling module
  [`_recovery.py:1`](../../nowing_backend/app/tasks/chat/streaming/flows/new_chat/_recovery.py#L1)

**Agent Tools & Middleware**

- Task tool factory split — registration/composition surface
  [`task_tool/__init__.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/task_tool/__init__.py#L1)
- Task tool core factory — internal builder helpers moved
  [`task_tool/_factory.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/checkpointed_subagent_middleware/task_tool/_factory.py#L1)
- MCP tool package init — dynamic `__getattr__` handles singletons
  [`tool/__init__.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/tool/__init__.py#L1)
- MCP tool HTTP logic — external API communication split
  [`tool/http.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/shared/tools/mcp/tool/http.py#L1)
- KB persistence middleware — LangGraph state bridging core
  [`middleware.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/kb_persistence/middleware.py#L1)
- KB persistence helpers — extracted I/O + serialization logic
  [`kb_persistence/_helpers.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/main_agent/middleware/kb_persistence/_helpers.py#L1)

**Backend & Capabilities**

- Postgres filesystem backend — read/write methods split into mixin
  [`backend.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/shared/middleware/filesystem/backends/kb_postgres/backend.py#L1)
- Postgres search queries — specialized Grep/Glob logic
  [`search.py:1`](../../nowing_backend/app/agents/chat/multi_agent_chat/shared/middleware/filesystem/backends/kb_postgres/search.py#L1)
- ChainLens executor core — streaming/coordination entrypoint
  [`executor.py:1`](../../nowing_backend/app/capabilities/chainlens/research/executor.py#L1)
- SSE parser split — specialized SSE chunk handling extracted
  [`sse_parser.py:1`](../../nowing_backend/app/capabilities/chainlens/research/sse_parser.py#L1)
- Notion history service — connector fetch logic modularized
  [`service.py:1`](../../nowing_backend/app/connectors/notion_history/service.py#L1)

**Peripherals (Tests)**

- Fixed shim monkeypatch — binds `require_workspace_member` to handler namespaces
  [`test_web_builder_routes.py:65`](../../nowing_backend/tests/integration/routes/test_web_builder_routes.py#L65)
- Fixed shim monkeypatch — applied identically to build routes
  [`test_web_builder_build_routes.py:63`](../../nowing_backend/tests/integration/routes/test_web_builder_build_routes.py#L63)
- Updated patch targets — `_stages` module monkeypatch updates
  [`test_new_chat_orchestrator.py:32`](../../nowing_backend/tests/unit/tasks/chat/test_new_chat_orchestrator.py#L32)
