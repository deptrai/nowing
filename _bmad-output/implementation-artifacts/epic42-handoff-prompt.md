# HANDOFF PROMPT — Epic 42 Implementation (Nowing)

Bạn là coding agent (Pi) trong repo `/Users/luisphan/Documents/GitHub/nowing`, branch `epic/42-agent-experience` (base commit `44391035c` "Epic 42 groundwork" — đã chứa mọi bug fix session trước: save_leads tool, billing advisory lock, checkpointer ping, medirus_gateway fullData, tiktok/gmaps routing, muasamcong SSL, document_converters embed fix + toàn bộ Epic 42 planning docs). Giao tiếp và viết docs 100% bằng tiếng Việt.

## GOAL (tổng)

Implement tuần tự toàn bộ **8 stories của Epic 42 "Agent Experience & Lead Pipeline Hardening"** theo thứ tự dependency đã quyết định:

**42.1 → 42.2 → 42.7 → 42.4 → 42.3 → 42.5 → 42.6 → 42.8**

Mỗi story chạy đúng quy trình sau:
1. Invoke skill `bmad-build-auto` (đọc `/Users/luisphan/Documents/GitHub/nowing/.agents/skills/bmad-build-auto/SKILL.md` rồi chạy lệnh `render_skill.py` trong đó → follow file `workflow.md` được in ra; workflow tự đi qua step-01-clarify → step-02-plan → step-03-implement → step-04-review).
2. Sau khi story xong (status `done`), invoke skill `bmad-qa-generate-e2e-tests` (`/Users/luisphan/Documents/GitHub/nowing/.agents/skills/bmad-qa-generate-e2e-tests/SKILL.md`) để generate e2e tests cho story đó.
3. **CHỈ khi e2e tests của story hiện tại PASS** (và suite hiện có không regression) mới chuyển sang story tiếp theo — lặp lại bước 1.
4. Cập nhật `sprint-status.yaml` key của story → `done` khi hoàn tất.

**Non-Goals (TUYỆT ĐỐI không làm):** CampaignSpec supply (epic 43), credential provisioning, refactor Medirus daemon, `_prepare_lead_record` contact_name drop, E1 memory-spike fix (investigation lane riêng), deferred scope (single lock rule, single credit authority, config contract ports/env).

**Constraints:** Invariants AD-1..6 (xem `_bmad-output/planning-artifacts/epics.md` §Epic 42 header ~line 5580, và `_bmad-output/implementation-artifacts/epic-42-context.md` đã compile sẵn); mọi lead-write qua `LeadBatchService.ingest_batch`; file edits CHỈ qua tools edit/write — CẤM ghi file qua bash (heredoc/sed/echo>); story nào block bởi credential/infra thật → báo rõ, không bỏ qua lặng lẽ; bị block → dừng hỏi user.

## TRẠNG THÁI HIỆN TẠI (đã làm xong)

- Goal tracker `mwjf06zq-gj8f5l` (có thể bị paused — nếu có goal tools, `/goal-resume` hoặc cứ làm theo instructions này).
- `epic-42-context.md` đã compile: `_bmad-output/implementation-artifacts/epic-42-context.md` (đọc lại trước mỗi story).
- Sprint keys `42-1`..`42-8` = `backlog` trong `_bmad-output/implementation-artifacts/sprint-status.yaml`.
- Epic 42 spec đã được review (34 findings) và PATCH vào `_bmad-output/planning-artifacts/epics.md` lines ~5579–5698 — ĐỌC BẢN PATCH mới nhất, không đọc bản cũ.
- Story 42.1 đang ở **step-02 (plan)**: `spec_file` đã resolve = `_bmad-output/implementation-artifacts/spec-42-1-pat-scoped-batch-ingest-verify-harden.md` (chưa viết). Investigation bên dưới đã hoàn tất — dùng luôn làm Code Map, đừng điều tra lại.
- Rendered workflow dir của lần render trước (tham khảo format, có thể render lại): `_bmad/render/bmad-build-auto/nowing-a18a34d834f1/378c84a6db11bf6ce6de/` chứa `workflow.md`, `step-01..04`, `spec-template.md`, `compile-epic-context.md`.

## INVESTIGATION ĐÃ XONG CHO STORY 42.1 (Code Map, đừng làm lại)

**Route & auth (đã verify):**
- `nowing_backend/app/routes/lead_batch_routes.py`: `POST /workspaces/{workspace_id}/leads/batch-ingest` đã tồn tại — `RequirePermission(Permission.LEADS_WRITE.value)` + `@limiter.limit("30/minute")`; `BatchLeadIngestRequest._reject_degenerate` (pydantic) đã reject-all ở level ValidationError khi lead thiếu cả phone+email+domain — nhưng shape là generic 422, CHƯA có `{status:'failed', rejected_indexes:[...], reason_map:{idx:reason}}` và chưa xử lý `Idempotency-Key` header.
- `app/users.py:get_auth_context` (~line 336): resolve PAT khi token bắt đầu `PAT_PREFIX` → `resolve_pat` → `AuthContext.pat_auth(user, pat)`.
- `app/auth/context.py`: `AuthContext{user, method('session'|'pat'|'system'), pat, ...}`; `is_gated` = `method=='pat'`; `is_session`.
- `app/models/users.py:549` `PersonalAccessToken`: `workspace_id` (nullable, scoped token bind 1 workspace), `client_id`, `agent_id`, `scopes` (JSONB list), `token_kind` ('legacy'|'agent_chat'), `token_hash`/`token_prefix`, `expires_at`, `last_used_at`. CheckConstraint: agent_chat phải có workspace_id+client_id+scopes.
- `app/utils/rbac.py`: `check_permission` (:130) check membership của **user** trong workspace + permission — rồi gọi `_enforce_api_access_gate` (:106): chỉ chặn `auth.is_gated and not workspace.api_access_enabled` → 403.

**GAPS cần implement (theo AC 42.1):**
- PAT `scopes` KHÔNG được check ở đâu — PAT của user là member vẫn qua được dù thiếu scope `leads:write` → cần enforce scope (vào seam chung `check_permission`/`_enforce_api_access_gate` hoặc riêng route — chọn 1 chỗ, không duplicate).
- PAT `workspace_id` binding không enforce vs path — PAT user member nhiều workspace có thể inject cross-workspace → thêm guard `pat.workspace_id is not None and pat.workspace_id != path.workspace_id → 403`.
- `actor_pat_token_id` ledger/attribution: chưa có — PAT ingest cần attribution (ghi vào `extra_metadata` của lead hoặc audit event — quyết định nhỏ nhất đúng convention, xem cách `pii_access_audit_logs`/BillingEventService log actor).
- `Idempotency-Key` header: chưa xử lý — dedupe thật sự hiện nhờ upsert `(workspace_id, value_hmac)`; quyết định: header chỉ là passthrough/safety-net hay cần lưu key → chọn minimal đúng intent AC (không duplicate lead, không double-debit; re-push same batch = no-op nhờ upsert).
- Batch mixed degenerate+valid: đã reject-all ở pydantic — cần formalize shape 422 `{status:'failed', rejected_indexes:[...], reason_map:{idx:reason}}` (đổi validator thành per-item collect + custom exception → HTTPException với detail dict).
- `UNIQUE(client_id, value_hmac)`: AC literal nói verify constraint này — thực tế dedupe key hiện tại là `(workspace_id, value_hmac)` qua `on_conflict_do_update` trong `app/services/lead_batch_service.py:_build_batch_upsert_stmt` (giữ fit_score cao hơn, merged metadata). **Quyết định planner đã ghi**: giữ dedupe `(workspace_id, value_hmac)` vì mạnh hơn (cùng lead 2 client khác nhau không tạo duplicate); document deviation trong spec — intent AC (re-push không duplicate/double-debit) đã thỏa. Nếu implementer thấy cần literal AC thì phải migration — cân nhắc kỹ.
- Doc-persist guard (A3): embed nằm ở `app/agents/chat/multi_agent_chat/main_agent/middleware/kb_persistence/_helpers.py` (`embed_texts` ~line 212 summary + 216 chunks; update path ~265/:271). `commit_staged_filesystem_state` ở `_commit.py:80`. `Document` model `app/models/documents.py` — CHƯA có column `unindexed`/`index_status` → cần migration thêm flag (ví dụ `indexed: bool` hoặc `index_status`), embed fail → doc vẫn commit với `unindexed:true` + reindex retry/backfill.

## ENVIRONMENT & CONVENTIONS

- Backend: `cd nowing_backend`, Python + `uv run`, FastAPI; env cho chạy thủ công: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/nowing REDIS_URL=redis://localhost:6380/0` (docker `nowing-deps-db-1` postgres :5434, redis :6380).
- Test: `uv run pytest tests/unit/ -m unit -q` (không cần DB); integration cần `docker compose -f docker/docker-compose.deps-only.yml up -d db redis` + `uv run alembic upgrade head`, DB `nowing_test`. Lint: `.venv/bin/ruff check` + `ruff format` (ruff không có trong PATH — dùng `.venv/bin/ruff` hoặc `uv run ruff`).
- Frontend: `cd nowing_web`, `pnpm tsc --noEmit`, `pnpm exec biome check ...` (story 42.7 có phần FE).
- Migrations: `cd nowing_backend && uv run alembic revision --autogenerate` → review → `upgrade head`.
- KHÔNG tự start/restart services (backend, Medirus, FE) — để user chạy; unit/integration tests chạy qua pytest là OK.
- Git: đang ở `epic/42-agent-experience`, tree sạch sau commit groundwork. Commit mỗi story một commit rõ ràng. Trước commit có thể chạy Jev gate `typesafe_ask` với `~/.pi/agent/jev-gates/code_review_gate.yaml` (bind `diff`,`files`) — fail-open.
- AGENTS.md repo root có verification commands từng story cũ — tham khảo pattern.
- `medirus_proxy` thật ra TỒN TẠI tại `app/capabilities/core/medirus_proxy.py` (khác với `medirus_gateway.py` ở `app/agents/chat/multi_agent_chat/shared/tools/mcp/`) — đừng nhầm.

## STORY OUTLINE (chi tiết đọc epics.md ~L5591+)

- 42.1 PAT-scoped batch ingest verify & harden + doc-persist `unindexed` guard (ở trên).
- 42.2 `ToolResultEnvelope` module `app/capabilities/core/tool_result.py` — `{status:'success'|'empty_result'|'failed'|'degraded'|'preview', reason, recovery_hint(≤500, untrusted), items}`; `from_medirus`/`from_exception`; hint map MEDIRUS_4001/4010/4030/5000 + default branch; emit ở `medirus_gateway._format_result`/`execute` + executors; dryRun → `preview` không phải success.
- 42.7 IA fix: route thật `/dashboard/{id}/leads` (FE) + auto-table get-or-create TRONG `LeadBatchService.ingest_batch` (AD-1b — race-safe `UNIQUE(workspace_id,key)`+`ON CONFLICT DO NOTHING`+re-select; dangling table_id → recreate+relink; backfill orphans) + empty state.
- 42.4 `nowing_mcp` tools: `leads.ingest`/`tables.create`/`leads.list`/`credits.balance` ≤40 lines mỗi, reuse REST semantics (limit clamp 1..200, offset≥0; no_wallet → failed envelope; actor attribution).
- 42.3 `GET /api/v1/scrapers/health`: aggregate `runs` table 24h `GROUP BY capability`, `success_rate=null` khi idle, `unknown` cho channel chưa chạy, workspace-scoped authz, <200ms/10k, KHÔNG live-probe.
- 42.5 HITL approve/reject → Gemini `functionResponse` count mismatch fix — AD-6 repro fixture (~52 msgs) TRƯỚC rồi mới fix; cả approve VÀ reject path (drop pending + `cancelled` functionResponse).
- 42.6 Step-cap degradation: `run_limit=80` (`app/agents/chat/anonymous_chat/agent.py`/`tool_call_limit.py:19`) → force-synthesize partial + `partial:true` status_marker (enumerated, consumer ignore-unknown); synthesize fail → notice-only; 0 tool results → "no tool calls completed".
- 42.8 forward `context.workspaceId` qua medirus_gateway (fix ở tool-wiring layer `create_medirus_meta_tools(deps)` → `_execute_medirus_tool`) + `NOWING_DEV_BYPASS_QUOTA` flag chỉ honor khi `is_self_hosted AND not production` (prod self-hosted vẫn chặn; DEBUG không đủ) + warning log.

## BÁO CÁO

Sau mỗi story: tóm tắt 3-6 dòng — implemented gì, files touched, test results, story key → done. Kết thúc goal: bảng 8 stories + tổng files + verification evidence. Nếu story nào không làm được do credential/infra → liệt kê rõ và dừng hỏi.
