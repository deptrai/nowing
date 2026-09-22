---
title: 'Story 20.6: `chainlens.code_search` Code Search'
type: 'feature'
created: '2026-09-20'
status: 'done'
baseline_revision: 657ac8101c732095586861f848d2415a35111a51
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '_bmad-output/planning-artifacts/ux-spec-epic20-chainlens-agent-tools-2026-09-20.md'
  - '_bmad-output/project-context.md'
warnings: []
deferred:
  - summary: >-
      system_prompt.md/description.md chua expose chainlens_code_search - theo plan, apply batch sau khi du capabilities (20.10, 20.11). Ban rewrite san tai _bmad-output/planning-artifacts/agent-prompts-chainlens-2026-09-20/.
    severity: medium
  - summary: >-
      `sources` input khong validate enum - pattern-wide (entity_search, contents cung vay); sua o tang capability framework.
    severity: low
  - summary: >-
      workspace_id input vs ctx diverge - pattern-wide known gap.
    severity: low
  - summary: >-
      docs_url 404 - metadata only (contents cung vay, khong co trang docs that).
    severity: low
  - summary: >-
      Timeout hardcode 120s khong env-configurable - chainlens-wide (contents cung vay).
    severity: low
  - summary: >-
      Executor[...] type annotation misleading - cosmetic.
    severity: low
  - summary: >-
      e2e fake _CI_VERBS[0] positional assumption - fragile but works.
    severity: low
---

<intent-contract>

## Intent

**Problem:** Coding sub-agents (Web Builder, automation scripts) cần code snippets + API docs chuẩn xác từ GitHub/StackOverflow/packages, nhưng Nowing chỉ có `chainlens.research` (prose) — trả về văn bản dài dòng, lãng phí token thay vì code-dense context.

**Approach:** Thêm capability `chainlens.code_search` gọi ChainLens `POST /api/v1/search` với `output:"code_context"`, `dataSources:["code"]`, `stream:false`, expose tool `chainlens_code_search` cho chainlens sub-agent. Copy pattern từ `chainlens.contents` (vừa implement, cùng structure).

## Boundaries & Constraints

**Always:**
- Call `POST {CHAINLENS_API_URL}/api/v1/search` với body: `{query, output:"code_context", dataSources:["code"], mode, numResults, sources:["web"], stream:false}`. `language` (optional) được append vào query (`"{query} {language}"`) — khớp upstream MCP contract.
- Auth qua `ChainLensServiceAuth.get_outbound_headers(workspace_id, correlation_id)` + `api_key` override; retry-once-on-401 (copy executor contents).
- `redact_pii()` trên user query trước khi gửi (AD-25/49).
- `TokenUsage` `usage_type="chainlens_code_search"` với `cost_micros` từ `costDollars→micros` (AD-8).
- Typed degradation (`engine_unavailable`) trên missing config/5xx/timeout/malformed JSON — copy `_degraded` pattern từ contents.
- Register `Capability(name="chainlens.code_search", billing_unit=BillingUnit.CHAINLENS_QUERY, context_aware=True)`; append `CHAINLENS_CODE_SEARCH` vào `_CI_VERBS`.
- Capability `description` = UX spec Part A code_search wording (verbatim).
- Timeout default 120s (khớp upstream MCP timeoutMs 120_000).

**Block If:**
- Upstream response shape khác `{sources:[{url,title,content,metadata:{source,sourceId,score,...}}], message, status, costDollars}` — HALT `blocked`.

**Never:**
- KHÔNG dùng SSE parsing — `code_context` trả JSON (stream:false implicit qua callSearchAPI non-stream path).
- KHÔNG widen `ResearchInput.output` Literal — dedicated `CodeSearchInput`/`CodeSearchOutput`.
- KHÔNG dùng cho câu hỏi prose — capability description phải nói rõ "programming questions ONLY".
- KHÔNG xử lý timeout bằng retry tự động — trả `nextAction` hint cho caller (khớp upstream MCP behavior).
- No epic/story refs trong code comments.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY single query | `query="how to use httpx"`, `language="python"` | snippets + `source:path:line` refs, `cost_micros` set | none |
| HAPPY no language | `query="httpx retry"`, no language | query gửi verbatim (không append) | none |
| Timeout w/ nextAction | upstream `status=timeout` | output có `next_action` hint | typed, không raw error |
| Missing API URL | `CHAINLENS_API_URL` unset | `engine_unavailable`, degraded | typed degradation |
| Missing auth | no service token | `engine_unavailable`, degraded | typed degradation msg |
| Upstream 5xx | error response | `engine_unavailable` | typed degradation msg |
| PII in query | query có tên/SĐT/email | redact trước khi gửi | `redact_pii()` |
| Empty results | upstream trả 0 snippets | `status="partial"`, message giải thích | không complete-rỗng |
| maxResults bounds | `maxResults=25` (>20) | ValidationError từ schema | pydantic reject |

</intent-contract>

## Code Map

- `app/capabilities/chainlens/code_search/__init__.py` — NEW: exports.
- `app/capabilities/chainlens/code_search/schemas.py` — NEW: `CodeSearchInput`{`query` (1–1000 chars), `language?` (regex `^[a-z0-9+#-]+$`), `maxResults` (1–20, default 8), `mode` (`instant|fast|balanced|auto`, default `fast`), `workspace_id`, `correlation_id?`}; `CodeSearchOutput`{`snippets` (list of {source, source_id, title, url, content, score}), `status`, `degraded`, `next_action?`, `cost_micros/cost_dollars/cost_basis`, `message?`}.
- `app/capabilities/chainlens/code_search/executor.py` — NEW: `CodeSearchExecutor` — POST `/api/v1/search` `output=code_context` `dataSources:["code"]`; parse `sources[]` với `metadata.source`/`metadata.sourceId`; timeout → `next_action` surface.
- `app/capabilities/chainlens/code_search/definition.py` — NEW: register `CHAINLENS_CODE_SEARCH`.
- `app/capabilities/chainlens/contents/{executor,schemas,definition}.py` — REUSE pattern (copy structure; do NOT modify).
- `app/services/chainlens/auth.py` — REUSE `get_outbound_headers`, `cost_dollars_to_micros`.
- `app/agents/.../builtins/chainlens/tools/index.py:17` — EDIT: append `CHAINLENS_CODE_SEARCH` to `_CI_VERBS`.
- `app/services/pii/redact.py` — REUSE `redact_pii`.
- `app/capabilities/core/billing.py` — no change (zero-content-free policy đã có từ 20.5 patch).

## Tasks & Acceptance

**Execution:**
- `app/capabilities/chainlens/code_search/schemas.py` — `CodeSearchInput`/`CodeSearchOutput` + validators (query 1–1000, language regex, maxResults 1–20) — input contract.
- `app/capabilities/chainlens/code_search/executor.py` — `CodeSearchExecutor.execute`: POST `output=code_context`, auth, redact, parse snippets, timeout→next_action, typed degradation, cost mapping — core logic.
- `app/capabilities/chainlens/code_search/definition.py` — register capability (description verbatim UX spec Part A) — expose.
- `app/capabilities/chainlens/code_search/__init__.py` — exports.
- `app/capabilities/chainlens/__init__.py` — import code_search definition.
- `app/agents/.../builtins/chainlens/tools/index.py` — `_CI_VERBS` += `CHAINLENS_CODE_SEARCH` — surface tool.
- `tests/unit/capabilities/chainlens/code_search/` — unit tests phủ đủ 9 rows I/O Matrix + cost mapping + tool registration — AC coverage.

**Acceptance Criteria:**
- Given a programming query (+optional language), when `chainlens.code_search` runs, then it calls `POST /api/v1/search` `output=code_context` `dataSources:["code"]` and returns snippets with `source:path` refs + `cost_micros` (AC-1/AC-2).
- Given upstream timeout, when resolving, then output carries `next_action` hint (AC-3).
- Given completion, when billed, then `TokenUsage` `usage_type="chainlens_code_search"` recorded (AC-3).
- Given outbound query, when leaving Nowing, then it passed `redact_pii()` (AC-4).
- Given `_CI_VERBS` includes `CHAINLENS_CODE_SEARCH`, when agent tools load, then `chainlens_code_search` is exposed (AC-5).
- Given zero usable content (empty results / engine unavailable), when billed, then charge = 0 (policy 2026-09-20) (AC-6).

## Spec Change Log

## Review Triage Log

### 2026-09-20 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 21 (high 4, medium 8, low 9)
- defer: 7 (medium 1, low 6)
- reject: 5
- addressed_findings:
  - `[high]` `[patch]` context_aware BROKEN — executor param `context` vs door contract `ctx` → renamed to `ctx`
  - `[high]` `[patch]` Citations missing — `snippets`→`items` rename + expose `sources` for `register_web_citations` door contract
  - `[high]` `[patch]` Serialization paging — `snippets`→`items` so `serialize_output` pages per-item
  - `[high]` `[patch]` has_content billing miss — extended `_charge_chainlens` has_content to check snippets/items/sources
  - `[medium]` `[patch]` cost_basis "estimated" dead Literal → read upstream `estimated:true` flag
  - `[medium]` `[patch]` non-string content guard (isinstance str check)
  - `[medium]` `[patch]` query+language 1000-char overflow → truncate
  - `[medium]` `[patch]` bool score accepted → exclude bool
  - `[medium]` `[patch]` sync-chat mode gate (auto/balanced can stall 120s)
  - `[medium]` `[patch]` 401 rotate headers=None path → early degraded
  - `[medium]` `[patch]` content size cap (MAX_COMBINED_CONTENT_CHARS)
  - `[medium]` `[patch]` degradation_reason field added to output
  - `[low]` `[patch]` tests: X-Workspace-Id/correlation-id, 401-rotation, serialization paging, citation, config-based missing-auth/api-url, content str type, bool score, maxResults alias, retry backoff note
- note: review ran inline first (gateway degraded), then re-spawned 4 subagent reviewers successfully — findings above are from the subagent pass

## Design Notes

Upstream contract (verified `chainlens-research` `apps/mcp/src/tools/codeSearch.ts`): `callSearchAPI({query: language ? `${query} ${language}` : query, output:'code_context', dataSources:['code'], mode ?? 'fast', numResults: maxResults ?? 8, sources:['web'], timeoutMs:120_000})`. Response: `{sources:[{url,title,content,metadata:{source,sourceId,score}}], message, status, nextAction, costDollars}`. Timeout → `status='timeout'` + `sourcesCollected` + `nextAction` hint.

## Verification

**Commands:**
- `cd nowing_backend && python -c "from app.capabilities.chainlens.code_search.definition import CHAINLENS_CODE_SEARCH; print(CHAINLENS_CODE_SEARCH.name)"` — expected: `chainlens.code_search`
- `cd nowing_backend && pytest tests/unit/capabilities/chainlens/code_search -q` — expected: all pass
- `cd nowing_backend && python -c "from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools.index import _CI_VERBS; print([v.name for v in _CI_VERBS])"` — expected: includes `chainlens.code_search`

## Auto Run Result

Status: done

### Tom tat thay doi
Them `chainlens.code_search` capability — tim code snippets + API docs tu GitHub/StackOverflow/packages qua ChainLens `POST /api/v1/search` (`output=code_context`, `dataSources=["code"]`), expose tool `chainlens_code_search` cho chainlens sub-agent.

### Files changed
- `nowing_backend/app/capabilities/chainlens/code_search/schemas.py` — CodeSearchInput/CodeSearchOutput/CodeSnippet + validators (query 1-1000, language regex, maxResults 1-20)
- `nowing_backend/app/capabilities/chainlens/code_search/executor.py` — CodeSearchExecutor: POST code_context, language-append contract, auth + 401 rotate, redact_pii, timeout→next_action, empty→partial, cost_micros, typed degradation
- `nowing_backend/app/capabilities/chainlens/code_search/definition.py` — Capability registration (billing_unit=CHAINLENS_QUERY, context_aware=True)
- `nowing_backend/app/capabilities/chainlens/code_search/__init__.py` — exports
- `nowing_backend/app/capabilities/chainlens/__init__.py` — import code_search
- `nowing_backend/app/agents/.../builtins/chainlens/tools/index.py` — `_CI_VERBS` += CHAINLENS_CODE_SEARCH
- `nowing_backend/tests/unit/capabilities/chainlens/code_search/test_code_search.py` — 20 tests

### Review findings breakdown
- Patches applied: 21 (high 4, medium 8, low 9)
- Deferred: 7 (medium 1, low 6)
- Rejected: 5
- Follow-up review: patched counts (high 4, medium 8, low 9) → score = 3×5 + 1×4 = 19 ≥ 5 → **true**

### Verification
- `python -c "...CHAINLENS_CODE_SEARCH.name"` → `chainlens.code_search` ✅
- `_CI_VERBS` → `[research, entity_search, contents, code_search]` ✅
- `pytest tests/unit/capabilities/chainlens/code_search -q` → **30 passed** (after 21 patches, re-verified doc lap) ✅
- Matrix Test Audit: 9/9 I/O matrix rows + extra patch tests ✅

### Residual risks
- system_prompt.md/description.md chua expose chainlens_code_search — theo plan, apply batch sau khi du capabilities (deferred).
- has_content billing extended to snippets/items/sources — check contents output also populates `sources` for the same door contract.

### Verification
- `python -c "...CHAINLENS_CODE_SEARCH.name"` → `chainlens.code_search` ✅
- `_CI_VERBS` → `[research, entity_search, contents, code_search]` ✅
- `pytest tests/unit/capabilities/chainlens/code_search -q` → **20 passed** ✅
- Matrix Test Audit: 9/9 I/O matrix rows covered ✅

### Residual risks
- system_prompt.md/description.md chua expose chainlens_code_search — theo plan, apply batch sau khi du capabilities (deferred).
- Inference gateway (proxy.chainlens.net) was degraded during review — subagent reviewers failed 502/503; parent reviewed full diff inline. Re-run review layer later if gateway recovers for extra confidence.
