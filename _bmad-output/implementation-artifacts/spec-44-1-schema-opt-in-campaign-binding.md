---
title: 'Epic 44.1 — Schema + opt-in campaign identity binding'
type: 'feature'
created: '2026-11-18'
status: 'done'
baseline_revision: 'be6370eff4f86a779f741d457f287ca4a3adc3bf'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-44-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Campaign chưa là entity durable — identity chỉ là `spec.name` free-text, không có run record nào, role nằm chết trong `extra_metadata` JSONB. **Và T0 trace (đã giải trong planning) phát hiện latent prod bug:** `/campaigns/execute?persist=true` chạy xong `ingest_batch` rồi `get_async_session` đóng **mà không ai commit** — leads rollback mất trong prod (test suite che bằng same-transaction visibility).

**Approach:** Thêm 3 bảng `lead_campaigns`/`campaign_runs`/`campaign_leads(role)` kèm tenant RLS; `campaign_service.open_campaign_run` là seam DUY NHẤT tạo run; `execute_and_persist` nhận opt-in `campaign`/`campaign_run_id` và commit tường minh ở cuối — một commit point cho route + agent paths.

## Boundaries & Constraints

**Always:**
- Bảng tên `lead_campaigns` (KHÔNG `campaigns` — `webset_campaigns` đã chiếm namespace, `app/models/webset_campaign.py:15`).
- `open_campaign_run(campaign_id, trigger, session)` trong `app/lead_intelligence/services/campaign_service.py` là CHỖ DUY NHẤT insert `campaign_runs`; acquire `pg_advisory_xact_lock(hashtext('campaign_run', campaign_id))` rồi reject nếu đã có run `'running'` (409 route / skip scheduled — concurrent-run guard v1, không queue).
- Bookkeeping OPT-IN: `execute_and_persist(*, campaign: LeadCampaign | None = None, campaign_run_id: UUID | None = None)` keyword-only — chỉ ghi khi `campaign` được truyền; KHÔNG BAO GIỜ suy ra từ `spec.name`. 3 caller agent (`orchestrator_tool.py:191`, `executor.py:86`) không truyền → 0 row, 0 throttle, nhưng VẪN được commit fix (leads của họ hiện cũng đang bị rollback).
- Junction `campaign_leads` chỉ dùng `summary["accepted_lead_ids"]` từ `ingest_batch` làm nguồn id DUY NHẤT (lead_batch_service.py ~:533-544); role = `'buyer'` (demand) | `'supplier'` (supply) khớp tag 43.4.
- Junction insert bọc `session.begin_nested()` SAVEPOINT — raise → release savepoint + log warn, ingest vẫn commit.
- `await session.commit()` TƯỜNG MINH ở CUỐI `execute_and_persist` (sau assignment + bookkeeping) — commit point duy nhất mới; KHÔNG sửa `get_async_session`, KHÔNG commit trong `ingest_batch`.
- `spec_snapshot = spec.model_dump(mode="json")` (python-mode crash trên UUID/datetime — schemas.py:164,33-35).
- Get-or-create campaign: `pg_insert(...).on_conflict_do_nothing(index_elements=["workspace_id","name","direction"])` + re-SELECT (precedent lead_batch_service.py:391).
- MỌI return path của `execute_and_persist` (no-leads early-return :942, supply-filter-empty :960, ingest exception :1029) phải finalize run (`succeeded`/`failed` + `finished_at` + `stats`) khi `campaign_run_id` có — không để run treo `'running'` (44.3 stale-reaper chỉ là safety net).
- Tenant RLS ENABLE + FORCE trên cả 3 bảng; predicate CHỈ `workspace_id IS NOT DISTINCT FROM NULLIF(current_setting('app.workspace_id', true), '')::int` — pattern migration 221 `:266-269,:349-372`, copy inline (helper không import được).
- `persist=false` preview tạo 0 row; implicit campaign (source='execute') status `'running'` khi run active → `'completed'` sau finalize; role visibility giữ dual-write `extra_metadata` (43.4) nguyên vẹn.

**Never:**
- KHÔNG replicate lead-visibility policy lên `campaign_leads` (membership là workspace-level — deviation có ghi chú trong migration).
- KHÔNG merge các alembic head cũ (39/51/69/71/89/18/07582243b847); chain off mainline head '250' (chạy `alembic heads` verify trước).
- KHÔNG backfill junction cho leads cũ; KHÔNG PAT scope `campaign:*`; KHÔNG đụng `webset_campaigns`; KHÔNG đổi dedupe key `(workspace_id, value_hmac)` (AD-4).
- KHÔNG implement quota check / scheduler / CRUD endpoints / celery task trong story này (44.2/44.3) — `open_campaign_run` chỉ làm lock + concurrent-guard + insert.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| DEMAND_EXECUTE | `/execute` spec demand | campaign `(ws,name,'demand')` source='execute' + run trigger='api' + junction role='buyer' | No error expected |
| SUPPLY_EXECUTE | spec supply | junction role='supplier'; dual-write `extra_metadata` giữ nguyên | No error expected |
| SAME_NAME_SAME_DIR | lặp spec.name+direction | cùng campaign row (unique key), run mới | No error expected |
| SAME_NAME_DIFF_DIR | cùng name khác direction | 2 campaign rows riêng (unique key gồm direction) | No error expected |
| AGENT_PATH | `orchestrator_tool`/`executor` gọi không campaign param | 0 campaign/run/junction row; leads COMMIT được (bug fix) | Không thay đổi call sites |
| PERSIST_FALSE | `persist=false` | 0 row mọi bảng | No error expected |
| JUNCTION_FAIL | junction insert raise | SAVEPOINT release, warn log, leads+run vẫn commit; run stats `junction_failed=true` | Fail-open theo design |
| CONCURRENT_CREATE | 2 request cùng (ws,name,dir) | ON CONFLICT → 1 campaign row, 2 runs | No error expected |
| CONCURRENT_RUN | run 'running' đang tồn tại | open_campaign_run reject → route 409 | HTTPException 409 |
| EARLY_RETURN | 0 leads / supply filter empty | run finalize `succeeded` + stats zero — không treo 'running' | No error expected |
| INGEST_FAIL | ingest_batch raise | run `failed` + error; degraded result như hiện tại | Existing fallback + run mark |
| CROSS_SESSION | sau execute, query session MỚI | campaign_runs + leads + junction nhìn thấy được (commit đã xảy ra) | Latent-bug proof |

</intent-contract>

## Code Map

- `app/models/leads/campaign.py` -- **NEW**: 3 models LeadCampaign/CampaignRun/CampaignLead + composite FK precedent `leads/signals.py:67`; re-export trong `app/models/leads/__init__.py` (convention :5-32)
- `app/db/enums.py` -- thêm `CampaignStatus`/`CampaignRunStatus`/`CampaignTrigger`/`CampaignSource` str-Enums (convention `Permission` :393); status FE `campaign.types.ts:4-11` = draft|scheduled|running|paused|completed|failed|archived
- `app/lead_intelligence/services/campaign_service.py` -- **NEW**: `get_or_create_campaign`, `open_campaign_run`, `persist_campaign_bookkeeping` (+ finalize run)
- `app/lead_intelligence/services/lead_gen_orchestrator.py` -- `execute_and_persist` :905 (signature += keyword-only params); supply_tags merge :962-994; junction attach sau `summary` :1044-1051; `_assign_new_leads` :1051; `LeadGenOrchestratorResult` :74-92 += campaign_id/campaign_run_id; **`await session.commit()` cuối hàm**
- `app/routes/campaign_routes.py` :115-157 -- `execute_campaign`: get-or-create campaign(source='execute') + `open_campaign_run(trigger='api')` + truyền params
- `app/services/lead_batch_service.py` :420-560 -- `ingest_batch` read-only reuse; `accepted_lead_ids` nguồn id duy nhất; ON CONFLICT precedent :391
- `alembic/versions/221_add_multi_seat_crm_and_credit_pooling.py` :266-372 -- RLS predicate + policy SQL cần copy inline
- `app/tenant_context.py` :17 -- `set_request_tenant_context` (GUCs `app.workspace_id`…) — route path đã set sẵn qua `require_session_context`/check_permission
- `app/tasks/phone_waterfall_worker.py` :84-115 -- `auto_refund_lead_task` pattern (own `async_session_maker` + tenant ctx) — reference cho 44.2 task, KHÔNG code story này
- `tests/unit/services/test_campaign_service.py` + `tests/unit/lead_intelligence/test_campaign_binding.py` + `tests/integration/campaigns/test_campaign_persist_commit.py` -- NEW test targets (conftest real-PAT pattern `tests/integration/lead_batch/conftest.py:44-101`)

## Tasks & Acceptance

**Execution:**
- `alembic/versions/<rev>_lead_campaigns.py` -- migration 3 bảng + composite FK `(lead_id, workspace_id)→leads(id,workspace_id)` + UniqueConstraint `(workspace_id,name,direction)` / `(campaign_id,lead_id)` + 5 index (context file) + tenant RLS 3 bảng + downgrade sạch -- `alembic heads` trước, `down_revision` = mainline head '250'
- `app/db/enums.py` -- 4 enums -- convention Permission
- `app/models/leads/campaign.py` + `app/models/leads/__init__.py` -- models + re-export -- schema đúng context file (`input_payload` nullable, `spec_snapshot` trên RUNS, `schedule_*`/`next_run_at`/`source`/`skipped_by_quota` trên campaigns, String columns + Python enums, TimestampMixin `app/db/base.py:30`)
- `app/lead_intelligence/services/campaign_service.py` -- `get_or_create_campaign` (ON CONFLICT+re-SELECT), `open_campaign_run` (advisory lock + concurrent-guard + insert status='running'), `persist_campaign_bookkeeping` (junction savepoint + run finalize + campaign status running→completed) -- seam duy nhất
- `app/lead_intelligence/services/lead_gen_orchestrator.py` -- signature opt-in params, bookkeeping hook (god-class chỉ +1 thin call), result += 2 fields, finalize mọi exit path, `session.commit()` cuối -- **commit point fix**
- `app/routes/campaign_routes.py` -- execute_campaign wire campaign+run vào persist path -- route giữ thin, logic trong service
- tests (3 file trên) -- unit: seam, opt-in, agent-path regression, junction accepted ids, savepoint fail-open, enum/status; integration: cross-session commit proof + run row + junction role qua real PAT

**Acceptance Criteria:**
- Given migration applied, khi `POST /execute` persist=true spec demand, then `lead_campaigns`+`campaign_runs`+`campaign_leads` rows tồn tại VÀ nhìn thấy được từ session mới (commit proof — latent bug fixed)
- Given supply spec, khi execute persist, then junction `role='supplier'` và `campaign_leads.lead_id` ⊆ `accepted_lead_ids`
- Given agent path (`orchestrator_tool`) gọi execute_and_persist không truyền campaign, then 0 campaign rows VÀ leads vẫn commit
- Given run `'running'` cùng campaign, khi open_campaign_run lần 2, then raise → route trả 409
- Given junction insert fail (mock raise), khi execute, then leads vẫn persist + run succeeded + log warn
- Given persist=false, khi execute, then 0 row cả 3 bảng
- Given alembic downgrade+upgrade, then apply sạch không lỗi

## Spec Change Log

## Review Triage Log

## Design Notes

- **Commit point (T0 resolved):** chain `get_async_session`(yield-only) → `check_permission` → `execute_and_persist` → `ingest_batch`/`_assign_new_leads`/`LeadAssignmentService` — grep 0 commit; `app/users.py:145` commit chỉ chạy lúc auth dep (trước route body). Fix: commit cuối `execute_and_persist` — durable-by-name, sửa luôn agent paths đang mất leads. Caller-nào-commit convention vẫn đúng: hàm này LÀ boundary.
- **Atomicity là feature:** campaign+run+leads+junction+finalize commit 1 transaction — partial-persist không tồn tại.
- Role derive: `spec.direction=='supply' → 'supplier'` else `'buyer'` — khớp `supply_tags` :983-988.

## Verification

**Commands:**
- `cd nowing_backend && alembic heads` -- expected: hiện đúng new revision là head (cạnh các nhánh cũ, không merge)
- `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` -- expected: sạch, không lỗi
- `pytest tests/unit/services/test_campaign_service.py tests/unit/lead_intelligence/test_campaign_binding.py tests/integration/campaigns/ -x -q` -- expected: all pass
- `pytest tests/unit/lead_intelligence/ -x -q` -- expected: 406+ pass, không regression
- `python -c "from app.models import LeadCampaign, CampaignRun, CampaignLead"` -- expected: import OK
