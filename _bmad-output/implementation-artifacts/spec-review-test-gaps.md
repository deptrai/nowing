---
title: 'Close test gaps from code reviews'
type: 'chore'
created: '2026-08-08'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: 3d63616b7
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Code reviews across 15 stories identified 18 test gaps where ACs are PARTIAL — implementation is correct but tests don't verify the behavior. These gaps mean regressions could ship silently.

**Approach:** Add targeted test cases to existing test files (and 2 new files) across 3 suites: backend pytest (9 items), eval pytest (6 items), frontend Playwright (2 items). One uncertain item (4-8h AC-3 quality mode gating) needs investigation before testing — the conditional gating logic may not exist in mode_budget.py.

## Boundaries & Constraints

**Always:**
- Each test must verify a specific AC from the original story spec
- Use existing test fixtures and patterns — no new test infrastructure
- Tests must pass against current code (we're verifying existing behavior, not writing tests for new code)
- Group tests by file to minimize PR size

**Ask First:**
- If 4-8h AC-3 (quality mode ChainLens conditional gating) turns out to be an implementation gap rather than a test gap — HALT and report. The spec only covers test additions, not feature implementation.

**Never:**
- Do not modify production code — this is test-only
- Do not add tests for deferred items (Nhóm 3/4/5) — those need design decisions first
- Do not create new test frameworks or fixtures

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Non-superuser calls admin route | Regular user session + POST/PUT/DELETE to admin global model routes | 403 Forbidden | N/A |
| Non-member calls revalidate | User not in workspace + POST /memories/{id}/revalidate | 403 Forbidden | N/A |
| Capability fails during revalidation | Capability executor raises exception | RevalidationResult status="failed" | Logged, not 500 |
| Archived doc in citation lookup | Document with archived_at set + citation query | Document not returned | N/A |
| Speed mode search params | mode=speed + search_knowledge_base call | top_k=1, max_passages_per_doc=4 | N/A |
| Quality mode budget | mode=quality + 3 KB calls + 2 non-KB calls | All 5 allowed, 6th blocked | N/A |
| Sampler CLI non-superuser | Non-superuser PAT + sample_chat_queries.py | Exit code 1, error message | N/A |

</frozen-after-approval>

## Code Map

- `nowing_backend/tests/integration/routes/test_admin_global_model_connections.py` — add non-superuser 403 tests for all write routes + audit log assertions
- `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/test_mode_budget.py` — add quality mode tests (budget 3,2,5)
- `nowing_backend/tests/integration/admin/test_chat_query_sampler.py` — add superuser enforcement test
- `nowing_backend/tests/integration/memory/test_memory_revalidation.py` — add non-member 403 + capability failure "failed" status tests
- `nowing_backend/tests/integration/workspaces/test_data_retention.py` — add archived doc citation exclusion test
- `nowing_backend/tests/integration/capabilities/vn_bds/` — add REST auto-exposure test for aggregator
- `nowing_evals/tests/suites/chat/test_regression.py` — add p95 threshold assertions against gate.yaml
- `nowing_evals/tests/suites/chat/test_quality.py` — NEW: quality benchmark + JSON regex + judge error logging tests
- `nowing_evals/tests/core/test_cli_ingest_report.py` — add ingest compatibility test with sampler output format
- `nowing_web/tests/workspace-settings/data-retention.spec.ts` — extend with validation edge cases
- `nowing_web/tests/zero/` — NEW: real-time sync test for archived_at

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/tests/integration/routes/test_admin_global_model_connections.py` -- add non-superuser 403 tests for POST/PUT/DELETE/discover-preview/test-preview routes + caplog assertions for _log_admin_action -- verify AC-5 and AC-11
- [x] `nowing_backend/tests/unit/agents/multi_agent_chat/middleware/test_mode_budget.py` -- add quality mode tests: budget (3,2,5), ChainLens allowed, 6th call blocked -- verify AC-7 coverage ≥90%
- [x] `nowing_backend/tests/integration/admin/test_chat_query_sampler.py` -- add test that non-superuser PAT is rejected with exit code 1 -- verify AC-1
- [x] `nowing_backend/tests/integration/memory/test_memory_revalidation.py` -- add non-member 403 test + capability failure "failed" status test -- verify AC-5 and AC-6
- [x] `nowing_backend/tests/integration/workspaces/test_data_retention.py` -- add test that archived documents are excluded from citation/hybrid search results -- verify AC-3
- [x] `nowing_backend/tests/integration/capabilities/vn_bds/` -- add test that capability registration auto-exposes REST endpoint -- verify AC-6
- [x] `nowing_evals/tests/suites/chat/test_regression.py` -- add p95 e2e/TTFB/cost threshold assertions against gate.yaml -- verify AC-5
- [x] `nowing_evals/tests/suites/chat/test_quality.py` -- NEW file: quality benchmark tests (correctness ≥3.5, citation faithfulness ≥3.0, completeness ≥3.0) + JSON regex nesting test + judge error logging test -- verify AC-6 and 4-8d gaps
- [x] `nowing_evals/tests/core/test_cli_ingest_report.py` -- add test that sampler JSONL output is accepted by ingest command -- verify AC-5
- [x] `nowing_web/tests/workspace-settings/data-retention.spec.ts` -- extend with validation edge cases (0 days, negative days, invalid action) -- verify AC-1
- [x] `nowing_web/tests/zero/test-archived-sync.spec.ts` -- NEW file: test that archived_at changes sync via Zero and document list updates without page reload -- verify AC-6

**Acceptance Criteria:**
- Given non-superuser session, when POST/PUT/DELETE to admin global model routes, then 403
- Given caplog capture, when admin creates/updates/deletes model connection, then log contains actor, action, source, success fields
- Given mode=quality, when 3 KB + 2 non-KB calls made, then all allowed; 6th call blocked with jump_to="end"
- Given non-superuser PAT, when sample_chat_queries.py runs, then exit code 1 with error message
- Given non-workspace-member, when POST /memories/{id}/revalidate, then 403
- Given capability executor raises, when revalidate runs, then result.status="failed" (not 500)
- Given archived document, when citation/hybrid search runs, then document not returned
- Given vn_bds aggregator capability registered, when REST router loads, then endpoint auto-exposed
- Given regression suite runs, when p95 metrics computed, then thresholds from gate.yaml asserted
- Given quality suite runs, when judge evaluates, then correctness/faithfulness/completeness scores asserted
- Given nested JSON in judge response, when regex parses, then outer object extracted correctly
- Given judge fails, when error occurs, then error logged with context
- Given sampler JSONL output, when nowing_evals ingest runs, then dataset accepted without error
- Given owner enters 0 days, when saving retention settings, then validation error shown
- Given document archived, when Zero sync runs, then web document list updates without page reload

## Spec Change Log

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/integration/routes/test_admin_global_model_connections.py tests/unit/agents/multi_agent_chat/middleware/test_mode_budget.py tests/integration/admin/test_chat_query_sampler.py tests/integration/memory/test_memory_revalidation.py tests/integration/workspaces/test_data_retention.py -q` -- expected: all pass
- `cd nowing_evals && python -m pytest tests/suites/chat/test_regression.py tests/suites/chat/test_quality.py tests/core/test_cli_ingest_report.py -q` -- expected: all pass
- `cd nowing_web && pnpm test:e2e tests/workspace-settings/data-retention.spec.ts tests/zero/test-archived-sync.spec.ts` -- expected: all pass

## Suggested Review Order

**Admin auth boundary + audit logging**

- Non-superuser 403 on all write routes — verify fixture isolation
  [`test_admin_global_model_connections.py:413`](../../nowing_backend/tests/integration/routes/test_admin_global_model_connections.py#L413)

- Caplog audit log assertions — actor/action/source/success fields
  [`test_admin_global_model_connections.py:470`](../../nowing_backend/tests/integration/routes/test_admin_global_model_connections.py#L470)

**Mode budget quality mode coverage**

- Quality mode budget (3,2,5) — ChainLens allowed, 6th call blocked
  [`test_mode_budget.py:180`](../../nowing_backend/tests/unit/agents/multi_agent_chat/middleware/test_mode_budget.py#L180)

**Memory revalidation auth + failure**

- Non-member 403 + capability failure "failed" status
  [`test_memory_revalidation.py:345`](../../nowing_backend/tests/integration/memory/test_memory_revalidation.py#L345)

**Data retention archived doc exclusion**

- Archived doc excluded from hybrid search — visible vs archived assertion
  [`test_data_retention.py:447`](../../nowing_backend/tests/integration/workspaces/test_data_retention.py#L447)

**Sampler superuser enforcement**

- Non-superuser PAT rejected with exit code 1
  [`test_chat_query_sampler.py:60`](../../nowing_backend/tests/integration/admin/test_chat_query_sampler.py#L60)

**vn_bds REST auto-exposure**

- Capability registration auto-exposes REST endpoint
  [`test_vn_bds_aggregate.py:1`](../../nowing_backend/tests/integration/capabilities/vn_bds/aggregate/test_vn_bds_aggregate.py#L1)

**Eval regression thresholds**

- p95 e2e/TTFB/cost thresholds asserted against gate.yaml
  [`test_regression.py:539`](../../nowing_evals/tests/suites/chat/test_regression.py#L539)

**Eval quality benchmark + JSON regex + judge logging**

- Quality gate thresholds + JSON regex nesting + judge error logging
  [`test_quality.py:1`](../../nowing_evals/tests/suites/chat/test_quality.py#L1)

**Eval ingest compatibility**

- Sampler JSONL output accepted by ingest command
  [`test_cli_ingest_report.py:64`](../../nowing_evals/tests/core/test_cli_ingest_report.py#L64)

**Frontend data retention validation**

- 0 days, negative days validation edge cases
  [`data-retention.spec.ts:1`](../../nowing_web/tests/workspace-settings/data-retention.spec.ts#L1)

**Frontend Zero sync archived_at**

- Archived_at changes sync via Zero, document list updates without reload
  [`test-archived-sync.spec.ts:1`](../../nowing_web/tests/zero/test-archived-sync.spec.ts#L1)
