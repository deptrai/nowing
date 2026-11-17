---
title: 'Epic 44.4 — Per-run usage accounting + vertical #2 e2e proof'
type: 'feature'
created: '2026-11-18'
status: 'done'
baseline_revision: '81607ed32c089932ad180761467853a4089e1235'
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

### 2026-11-18 — Review pass
- verdicts: 19 findings — high 0, medium 0, low 13, false 6, maybe-false 0
- findings:
  - `[low]` `[reject]` Thiếu expression index cho `call_details->>'campaign_run_id'` — finalize chạy 1 lần/run (hiếm); fix là migration + index surface, hơn direct correction; xem lại khi 44.3 scheduler làm run thường xuyên
  - `[low]` `[reject]` Không có read-path API cho `cost_micros` — intent cấm sửa `campaign_routes` (44.2 territory); e2e đọc trực tiếp run row đã là bằng chứng giá trị; fix đề xuất là spec-note
  - `[low]` `[reject]` FAILED_RUN_COST chỉ unit-level (AsyncMock) — matrix không bắt buộc e2e; sum-path unconditional trước status branch nên unit pin đủ
  - `[false]` `[reject]` Contextvar rò rỉ vào background task sau reset — mọi usage call site thực đều awaited (`_record_free_usage` session riêng commit trước finalize; `billable_call` qua `wait_for`); không tồn tại fire-and-forget usage writer trong run path
  - `[low]` `[reject]` Nhân đôi param list wrapper/impl — divergence tự lộ qua test (param mới dùng mà không forward → impl thấy default → fail); fix kwargs làm mất signature
  - `[low]` `[patch]` Trùng cost tests giữa `test_campaign_service.py` và `test_campaign_cost_finalize.py` — đã xóa 2 test trùng ở test_campaign_service.py (:363, :379)
  - `[low]` `[reject]` `_sum_run_cost_micros` chạy trước `session.get` — path run-missing không reachable từ caller thật (run row luôn tồn tại khi finalize); UPDATE cũng unconditional nên reorder không lợi
  - `[low]` `[patch]` Comment hardcode "8 call sites" ở orchestrator docstring + token_tracking comment — đã reword thành mốc relative
  - `[low]` `[patch]` `_impl(_self=None, **kwargs)` dead-default ×3 trong test — đã bỏ `=None`
  - `[low]` `[patch]` e2e `cost_micros == 0` dựa giả định ngầm scrape-only — đã thêm SELECT count tagged rows == 0 tường minh
  - `[low]` `[patch]` `template: "b2b_saas"` cho vertical TMĐT — đã đổi `"fmcg_distributor"` (VerticalPresetId có sẵn); không có preset TMĐT riêng nào tồn tại
  - `[false]` `[reject]` `setdefault` giữ `campaign_run_id: None` nếu caller truyền sẵn — không call site nào truyền key đó (8 call sites billing.py nguyên trạng); caller-tường-minh chỉ là giả thuyết
  - `[false]` `[reject]` `campaign_run_id` không kèm `campaign` → tag orphan — guard thật là `campaign_run_id is not None` (:941), snippet edge-hunter quote sai; caller duy nhất `campaign_routes.py:187` truyền cả hai; tag-only caller nếu có vẫn đúng contract "usage thuộc run X" — orphan là trách nhiệm run lifecycle owner
  - `[low]` `[reject]` Sum query raise → finalize abort + leads rollback — cùng blast radius với mọi query finalize hiện có (atomic T0 semantics của 44.1); wrap try/except = guard state chưa demonstrate
  - `[false]` `[reject]` Wrapper set quanh cả impl vs "set trước :934" trong spec — behavioral superset tương đương; reset trong finally kể cả khi impl raise (có test pin)
  - `[false]` `[reject]` `cost_micros` ≈ luôn 0 trên free-tier path (`_record_free_usage` hardcode 0) — spec chủ đích sum `token_usage.cost_micros` column; free usage đúng nghĩa cost 0; "usage ≠ charge" là design intent — ghi nhận làm residual risk
  - `[low]` `[patch]` Docstring e2e :487 ghi "Patch record_token_usage" sai mechanism — đã sửa đúng (patch `micro_batch`, `record_token_usage` bản thật)
  - `[false]` `[reject]` (intent-alignment) Rename→execute tên gốc thay vì spec tên mới như matrix — pin cùng invariant "campaign mới + membership cũ nguyên"; nhánh đã test còn chứng minh tên cũ được free
  - `[false]` `[reject]` (intent-alignment) E2e cost ở mechanism-level không qua billing.py call site thật — contract là contextvar; vgap trace xác nhận mọi call site kế thừa qua context-copy; call-site e2e cần LLM billing thật, infeasible

## Design Notes

- Contextvar thay vì param-threading: `record_token_usage` nằm sau capability layer, 8 call sites — sửa signature = ripple lớn; contextvar zero-touch. Downside (implicit context) ghi rõ trong docstring.
- `cost_micros` là usage accounting, không phải charge — charge door thiết kế ở Platform phase.

## Verification

**Commands:**
- `cd nowing_backend && pytest tests/unit/services/test_token_usage_campaign_tag.py tests/unit/services/test_campaign_cost_finalize.py tests/integration/campaigns/test_campaign_persistence_e2e.py -x -q` -- expected: pass
- `pytest tests/integration/campaigns/ tests/unit/lead_intelligence/ -x -q` -- expected: không regression

## Auto Run Result

### Summary of implemented change

Per-run usage accounting qua contextvar propagation + e2e proof vertical #2 (TMĐT supply). `execute_and_persist` set `current_campaign_run_id` (module-level ContextVar trong `token_tracking_service`) quanh toàn bộ execution, reset trong `finally`; `record_token_usage` tự merge `campaign_run_id` vào `call_details` bằng `setdefault` (signature nguyên, explicit value thắng). `finalize_campaign_run` sum `token_usage.cost_micros` theo JSONB path → ghi `campaign_runs.cost_micros` cho cả succeeded lẫn failed run (0 rows → 0, không NULL).

### Files changed

- `app/services/token_tracking_service.py` — module-level `current_campaign_run_id` ContextVar + merge `setdefault` vào `call_details` trong `record_token_usage`
- `app/lead_intelligence/services/lead_gen_orchestrator.py` — `execute_and_persist` refactor thành wrapper set/reset contextvar; body gốc giữ nguyên ở `_execute_and_persist_impl`
- `app/lead_intelligence/services/campaign_service.py` — `_sum_run_cost_micros` (COALESCE SUM trên JSONB path) + `finalize_campaign_run` ghi `cost_micros` cả success lẫn failed
- `tests/unit/services/test_token_usage_campaign_tag.py` (NEW) — 8 test: tag trong/ngoài context, explicit-value precedence, không mutate caller dict, wrapper set/reset/reset-on-failure
- `tests/unit/services/test_campaign_cost_finalize.py` (NEW) — 7 test: sum, COALESCE 0-not-NULL, JSONB filter, failed-run cost
- `tests/integration/campaigns/test_campaign_persistence_e2e.py` (NEW) — 4 test e2e PAT thật: TMĐT supply (junction role='supplier', cost=0 scrape-only + tagged-count==0 tường minh), relaunch no-dup, rename→campaign mới, usage-tag→finalize `cost_micros=10_000` trên DB thật
- `tests/unit/services/test_campaign_service.py` — update `TestFinalizeCampaignRun` cho execute-count mới; xóa 2 test trùng coverage với file dedicated

### Review findings breakdown

- Patches applied: **6** (tất cả `low`) — xóa test trùng, reword "8 call sites" → relative, bỏ dead-default `_self=None`, thêm assert tagged-count==0, đổi template `fmcg_distributor`, sửa docstring e2e mechanism
- Deferred: 0
- Rejected: 7 (`low`/`false` kèm lý do trong triage log) — index JSONB (migration surface cho query hiếm), read-path API (44.2 territory), failed-run e2e (matrix không bắt buộc), param-dup wrapper/impl (test tự catch), sum-trước-get (path unreachable), sum-raise abort (cùng blast radius finalize hiện có), `campaign_run_id`-alone orphan (caller duy nhất truyền cả hai; snippet quote sai)
- False: 6 — contextvar-vào-bg-task (mọi call site awaited), setdefault-None (không caller nào truyền key), wrapper-scope (behavioral superset), cost≈0 semantics (spec-prescribed), rename-branch (invariant tương đương), mechanism-vs-call-site e2e (contextvar là contract)

### Follow-up review recommendation

`false` — 6 patched entries đều `low` (0 high, 0 medium patched). Không có unverified risk nào chưa đặt tên.

### Verification performed

- `pytest tests/unit/services/test_token_usage_campaign_tag.py tests/unit/services/test_campaign_cost_finalize.py tests/integration/campaigns/test_campaign_persistence_e2e.py -x -q` → **19 passed** (post-patch)
- `pytest tests/integration/campaigns/ tests/unit/lead_intelligence/ tests/unit/services/test_campaign_service.py -x -q` → **438 passed** (post-patch, +billing regression 97 passed từ implement phase)
- Matrix audit: 8/8 rows có test cover và pass — USAGE_TAG/NOTAG, COST_FINALIZE/ZERO, FAILED_RUN_COST (unit), E2E_SUPPLY, RENAME_SURVIVES, RELAUNCH_NODUP

### Residual risks

- `cost_micros` ≈ 0 trên free-tier path (`_record_free_usage` hardcode `cost_micros=0` — hybrid_llm_router.py:610); chỉ khác 0 khi run rơi premium tier. Đây là semantics đúng của column (cost tiền, không phải token count) — nếu product muốn usage-level visibility thì cần field khác (tokens/request count) ở story sau.
- Seq-scan `token_usage` mỗi finalize — chấp nhận ở tần suất campaign-run hiện tại; xem lại index khi 44.3 scheduler làm run thường xuyên.
- Run kẹt `'running'` nếu exception thoát ra từ `execute_multi_source_lead_gen` trước `_finalize` — pre-existing từ 44.1, diff không làm tệ hơn.
