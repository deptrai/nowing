---
title: 'Story 18.8: Enforce composite RLS on memories and patch all call sites'
type: 'feature'
created: '2026-08-10'
status: 'done'
baseline_commit: '5f39890e088c598615f7dfc382d5bdb943e9d7e0'
review_loop_iteration: 0
context:
  - _bmad-output/implementation-artifacts/epic-18-context.md
  - _bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/epic-18-pat-scope-rls-threat-model.md
---

## Intent

**Problem:** Bảng `memories` đã có `client_id`/`agent_id` từ migration `10127c164b44` nhưng chưa có RLS policy; các `Memory` call site chưa đảm bảo set GUC tenant trước khi query. Điều này vi phạm AD-31 và có nguy cơ leak dữ liệu giữa các vertical client.

**Approach:** Thêm composite RLS migration cho `memories`, audit tất cả call site, và patch chúng để set `app.workspace_id`/`app.current_client_id` trước khi đọc/ghi. Viết L1 RLS tests theo threat model.

## Boundaries & Constraints

**Always:**
- RLS policy phải khớp pattern của `token_usage` và `runs` (`workspace_id` + `client_id`, `IS NOT DISTINCT FROM`, `FORCE ROW LEVEL SECURITY`).
- Mọi `Memory` query phải set tenant GUC hoặc dùng `app.internal_service` cho internal sweep.
- Không dùng BYPASSRLS; app role phải bị RLS bắt.
- `SET LOCAL` GUC để reset khi transaction kết thúc.

**Ask First:**
- Nếu phát hiện `Memory` query nào cần cross-workspace (không thuộc một tenant cụ thể), hỏi trước khi thêm bypass.
- Nếu migration cần xóa/sửa RLS đã tồn tại trên bảng khác, hỏi trước.

**Never:**
- Không scope creep sang rate limiter, middleware, hay `GET /threads/{thread_id}` trong spec này.
- Không sửa schema `memories` (cột đã có).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | Query `Memory` với GUC workspace/client đúng | Trả về rows thuộc workspace/client | N/A |
| Wrong client | GUC client khác với row client | Row bị RLS ẩn | N/A |
| Missing context | Không set GUC trước query | `SELECT` trả về rỗng, `INSERT/UPDATE/DELETE` bị block | N/A (RLS default-deny) |
| Internal service | `app.internal_service = 'true'` | Bypass RLS cho startup/maintenance | GUC bị reset khi transaction kết thúc |
| NULL client | `app.current_client_id` unset hoặc empty | Chỉ thấy rows có `client_id IS NULL` | N/A |

## Code Map

- `nowing_backend/alembic/versions/` -- migration RLS pattern từ `f7471a265bc5` (token_usage) và `7c4fc2d307b2` (runs).
- `nowing_backend/app/db.py` -- `Memory` model (`client_id`, `workspace_id`).
- `nowing_backend/app/canonical/tenant_context.py` -- helper `set_request_tenant_context`.
- `nowing_backend/app/services/memory/` -- all Memory read/write call sites (search, extraction, revalidation, provenance).
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/` -- Memory recall in agent flow.
- `nowing_backend/app/routes/memory_routes.py` -- REST CRUD.
- `nowing_backend/app/routes/new_chat_routes.py` -- internal chat memory paths.
- `nowing_backend/app/routes/agent_chat_routes.py` -- public chat memory paths.
- `tests/integration/rls/test_composite_client_rls.py` -- L1 RLS tests (mới).

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/alembic/versions/da595e4c316a_add_memories_rls_policies.py` -- migration composite RLS cho `memories` (workspace + client, ENABLE + FORCE, `app.internal_service` bypass) -- AD-31 hard isolation.
- [x] `nowing_backend/app/services/memory/search.py` -- set workspace/client GUC trước các query `Memory`.
- [x] `nowing_backend/app/services/memory/extraction.py` -- set workspace/client GUC trước `INSERT/UPDATE` memory.
- [x] `nowing_backend/app/services/memory/run_extraction.py` -- `Run` GUC + `Memory` GUC trước khi lưu memory từ run.
- [x] `nowing_backend/app/services/memory/revalidation.py` -- set GUC trước memory provenance/revalidation queries.
- [x] `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py` -- không query `Memory` trực tiếp, không cần patch trong story này.
- [x] `nowing_backend/app/routes/memory_routes.py` -- REST CRUD sử dụng `MemoryRepository` đã set GUC.
- [x] `nowing_backend/app/routes/new_chat_routes.py` -- set GUC trước các memory operations trong internal chat.
- [x] `nowing_backend/app/routes/agent_chat_routes.py` -- set GUC trước public chat memory operations (PAT cung cấp client_id).
- [x] `tests/integration/rls/test_composite_client_rls.py` -- L1 tests no-GUC, correct-GUC, wrong-client, NULL-client, internal-service-bypass, memory-id-token, repository create/isolation.

**Acceptance Criteria:**
- Given `memories` có RLS FORCE, when query không set GUC, then không row nào trả về.
- Given workspace/client GUC đúng, when query `Memory`, then chỉ rows thuộc workspace/client được trả về.
- Given `app.internal_service = 'true'`, when startup sweep query `Memory`, then bypass được phép.
- Given `ruff check` và `alembic upgrade head`, then clean và migration apply thành công.
- Given `pytest tests/integration/rls/test_composite_client_rls.py`, then all pass.

## Design Notes

Policy shape giống `token_usage`:

```sql
SELECT: workspace_id IS NOT DISTINCT FROM current_setting('app.workspace_id', true)::int
        AND client_id IS NOT DISTINCT FROM current_setting('app.current_client_id', true)
INSERT/UPDATE/DELETE: workspace_id = app.workspace_id AND client_id = app.current_client_id
```

Khi `current_client_id` unset (`NULL`), `IS NOT DISTINCT FROM NULL` sẽ match `client_id IS NULL` (Nowing internal). Các public chat routes phải set `client_id` từ PAT scope.

## Verification

**Commands:**
- `uv run ruff check alembic/versions/XXX_add_memories_rls_policies.py app/services/memory/ app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py app/routes/memory_routes.py app/routes/new_chat_routes.py app/routes/agent_chat_routes.py` -- expected: clean.
- `uv run alembic upgrade head` -- expected: apply migration successfully.
- `uv run pytest tests/integration/rls/test_composite_client_rls.py -q` -- expected: all pass.
- `uv run pytest tests/integration/memory/ tests/integration/routes/test_new_chat_routes.py tests/integration/routes/test_agent_chat_routes.py -q` -- expected: no regression.
