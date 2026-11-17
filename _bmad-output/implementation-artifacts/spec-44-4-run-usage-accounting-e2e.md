---
title: 'Epic 44.4 — Per-run usage accounting + vertical #2 e2e proof'
type: 'feature'
created: '2026-11-18'
status: 'ready-for-dev'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-44-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-44-1-schema-opt-in-campaign-binding.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** `campaign_runs.cost_micros` luôn NULL — campaign path hoàn toàn unbilled (`LEADS_MULTI_SOURCE_GEN` có `billing_unit=None`, definition.py:20; `charge_capability` return 0 callers trong lead_intelligence). Không ai biết 1 run tốn bao nhiêu LLM/scrape usage. **Và** Epic 44 còn thiếu proof rằng campaign identity đúng trên vertical thứ 2 (trầm hương chỉ là n=1).

**Approach:** Contextvar propagation để `record_token_usage` tự tag `campaign_run_id` vào `call_details` khi chạy trong ngữ cảnh run; run finalize sum thành `cost_micros`. E2e chứng minh: rename giữ `campaign_id`, re-launch tạo run mới không duplicate membership, role supplier qua TMĐT supply path.

## Boundaries & Constraints

**Always:**
- **Propagation = contextvar**, KHÔNG sửa chữ ký `record_token_usage` trên 8 call sites: `app/services/token_tracking_service.py` += `current_campaign_run_id: ContextVar[str | None]` (module-level); trong `record_token_usage` (:581-634), nếu contextvar set → merge `{"campaign_run_id": <value>}` vào `call_details` trước khi insert.
- **Set context** ở `execute_and_persist` khi `campaign_run_id` được truyền: `token = current_campaign_run_id.set(str(run_id))` đầu hàm (trước `execute_multi_source_lead_gen` :934), `reset(token)` trong `finally` — mọi LLM/usage call trong run tự tag.
- **Cost finalize** trong `persist_campaign_bookkeeping` (campaign_service.py từ 44.1): `cost_micros = COALESCE(SUM(...))` trên `token_usage` rows where `call_details->>'campaign_run_id' = run_id` → write `campaign_runs.cost_micros` khi finalize. Scrape-only run (0 LLM usage) → `cost_micros=0` **là đúng** (usage ≠ charge — charge door là Platform non-goal).
- **Failed run** vẫn ghi usage đã phát sinh — finalize-failed cũng sum.
- E2e `tests/integration/campaigns/test_campaign_persistence_e2e.py`: real PAT (conftest `tests/integration/lead_batch/conftest.py:44-101`), mock adapter search như `test_supply_campaign_e2e.py`, vertical **TMĐT supply** (masothue path — `supply_eligible`, có `tax_id` để qua `require_tax_id` default).
- Rename campaign (`PATCH` hoặc trực tiếp update name nếu 44.2 chưa có — e2e CHỈ phụ thuộc 44.1 API surface = `/execute`) → `campaign_id` cũ giữ nguyên, `campaign_leads` membership vẫn gắn campaign đó; re-execute cùng spec sau rename → **campaign MỚI** (unique key name mới), không merge membership cũ — đây là documented behavior, test pin nó.
- Re-launch cùng campaign (execute 2 lần spec giống hệt, không rename) → 2 `campaign_runs` rows, `campaign_leads` không duplicate nhờ `UniqueConstraint(campaign_id, lead_id)` + ON CONFLICT/upsert-safe junction insert.

**Never:**
- KHÔNG sửa `record_token_usage` signature (contextvar only); KHÔNG thêm charge/billing door; KHÔNG sửa `charge_capability`; KHÔNG SLA auto-refund (`auto_refund_lead_task` dead producer — deferred); KHÔNG real scraping trong test (mock `search_leads` như Epic 43 e2e); KHÔNG sửa `campaign_routes.py` endpoints (44.2 territory — e2e chỉ dùng `/execute` từ 44.1); KHÔNG đụng `open_campaign_run` (44.3 territory).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| USAGE_TAG | `record_token_usage` chạy trong run context | `call_details.campaign_run_id = run_id` | contextvar unset → không tag |
| USAGE_NOTAG | gọi ngoài run context | `call_details` không có key | No error expected |
| COST_FINALIZE | run kết thúc, 3 usage rows tagged | `cost_micros` = tổng 3 rows | No error expected |
| COST_ZERO | scrape-only run, 0 usage | `cost_micros = 0` (không NULL) | No error expected |
| FAILED_RUN_COST | run failed giữa chừng | `cost_micros` = usage đã phát sinh | finalize-failed vẫn sum |
| E2E_SUPPLY | TMĐT supply execute persist | run row + junction role='supplier' + leads MST qua filter | No error expected |
| RENAME_SURVIVES | rename campaign rồi execute spec MỚI tên mới | campaign row MỚI, membership mới — cũ nguyên vẹn | documented, không merge |
| RELAUNCH_NODUP | execute lặp cùng spec | run #2, junction unique không dup | No error expected |

</intent-contract>

## Code Map

- `app/services/token_tracking_service.py` :581-634 -- += contextvar + merge vào `call_details` (đọc signature thật trước khi sửa — không đổi signature)
- `app/capabilities/core/billing.py` :428-931 -- 8 call sites record_token_usage (read-only — KHÔNG sửa, contextvar tự propagate)
- `app/lead_intelligence/services/lead_gen_orchestrator.py` :905-934 -- set/reset contextvar quanh `execute_multi_source_lead_gen` khi `campaign_run_id` có
- `app/lead_intelligence/services/campaign_service.py` -- `persist_campaign_bookkeeping` += cost sum query (SQLAlchemy func.sum trên token_usage.call_details JSONB path)
- `tests/unit/services/test_token_usage_campaign_tag.py` + `tests/unit/services/test_campaign_cost_finalize.py` -- NEW
- `tests/integration/campaigns/test_campaign_persistence_e2e.py` -- NEW (mock adapters, real PAT, assert DB rows)

## Tasks & Acceptance

**Execution:**
- `app/services/token_tracking_service.py` -- contextvar + merge -- signature nguyên
- `app/lead_intelligence/services/lead_gen_orchestrator.py` -- set/reset quanh execute -- try/finally
- `app/lead_intelligence/services/campaign_service.py` -- finalize += `cost_micros` sum -- query JSONB `call_details->>'campaign_run_id'`
- tests unit ×2 + integration e2e vertical #2 -- theo targets

**Acceptance Criteria:**
- Given `campaign_run_id` set, khi `record_token_usage` chạy, then `token_usage.call_details->>'campaign_run_id'` = run id; ngoài context → không tag
- Given 3 usage rows tagged run X, khi run X finalize, then `cost_micros` = tổng; 0 rows → 0
- Given supply TMĐT spec qua `/execute` (mock adapters, real PAT), then `campaign_runs` + `campaign_leads(role='supplier')` đúng số lượng post-filter
- Given rename campaign + execute spec tên mới, then campaign mới + membership mới; cũ nguyên vẹn
- Given execute lặp cùng spec, then run #2 tồn tại và `campaign_leads` không duplicate (count không đổi)

## Spec Change Log

## Review Triage Log

## Design Notes

- Contextvar thay vì param-threading: `record_token_usage` nằm sau capability layer, 8 call sites — sửa signature = ripple lớn; contextvar zero-touch. Downside (implicit context) ghi rõ trong docstring.
- `cost_micros` là usage accounting, không phải charge — charge door thiết kế ở Platform phase.

## Verification

**Commands:**
- `cd nowing_backend && pytest tests/unit/services/test_token_usage_campaign_tag.py tests/unit/services/test_campaign_cost_finalize.py tests/integration/campaigns/test_campaign_persistence_e2e.py -x -q` -- expected: pass
- `pytest tests/integration/campaigns/ tests/unit/lead_intelligence/ -x -q` -- expected: không regression
