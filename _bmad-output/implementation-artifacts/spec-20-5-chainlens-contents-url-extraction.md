---
title: 'Story 20.5: `chainlens.contents` URL Extraction'
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
      `sources` input khong validate enum (web/discussions/academic/crawl4ai) - pattern-wide issue, entity_search cung vay.
    evidence: |-
      Blind Hunter: typos silently produce empty upstream results. Can sua o tang capability framework, khong rieng contents.
    severity: low
  - summary: >-
      has_failure whitelist statuses - upstream hien chi co ok/error; reconsider khi upstream them status moi.
    severity: low
  - summary: >-
      401 retry khi dung api_key override (self-host path) - chua co self-host deployment thuc te.
    severity: low
  - summary: >-
      429 rate-limit message rieng + backoff - enhancement, khong blocker.
    severity: low
  - summary: >-
      ContentItem drop publishedDate/author fields - enhancement khi can.
    severity: low
  - summary: >-
      Test gaps: 401 rotate path, payload passthrough (subpages/livecrawl/maxAgeHours), highlights-as-string.
    severity: low
  - summary: >-
      workspace_id tu input vs CapabilityContext co the diverge - entity_search cung vay, pattern-wide.
    severity: low
  - summary: >-
      system_prompt.md/description.md chua update voi chainlens_contents - theo plan, apply sau khi du capabilities (SCP 6.4 gap #6).
    evidence: |-
      Prompt rewrite san tai _bmad-output/planning-artifacts/agent-prompts-chainlens-2026-09-20/; apply khi implement xong cac capability khac.
    severity: medium
  - summary: >-
      All-items-failed partial result van bill fallback flat rate - billing policy edge, can quyet rieng.
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Nowing sub-agents and scraper pipelines must read public web pages (articles, docs, competitor pages) without spinning up heavy headless-browser sandboxes. ChainLens exposes `output=contents` (Crawl4AI/Trafilatura) that returns clean, token-efficient markdown, but Nowing has no capability for it — only `chainlens.research` and `news.entity_search` are registered.

**Approach:** Add a `chainlens.contents` capability that calls ChainLens `POST /api/v1/search` with `output:"contents"`, `urls:[…]`, `stream:false`, then expose it to the chainlens sub-agent as `chainlens_contents`. Reuse the `entity_search` capability pattern (definition/executor/schemas) and `ChainLensServiceAuth` headers.

## Boundaries & Constraints

**Always:**
- Call `POST {CHAINLENS_API_URL}/api/v1/search` with `output:"contents"`, `urls:[…]` (1–100), `stream:false`, `summary`/`highlights`/`optimizationMode`/`subpages`/`subpageTarget`/`livecrawl`/`maxAgeHours` forwarded when set. `query` defaults to joined URLs when absent.
- Auth via `ChainLensServiceAuth.get_outbound_headers(workspace_id, …)` (Bearer + X-Workspace-Id + X-Correlation-Id); explicit `api_key` override for self-host/tests — mirror `EntitySearchExecutor._get_headers`.
- Redact outbound `query` via `redact_pii()` (AD-25/49); record `TokenUsage` `usage_type="chainlens_contents"` with `cost_micros` from `costDollars→micros` (AD-8).
- Return typed degradation (`engine_unavailable`) on missing URL/auth config or upstream 5xx — never raw errors (degradation-ux pattern).
- Register `Capability(name="chainlens.contents", billing_unit=BillingUnit.CHAINLENS_QUERY, context_aware=True)`; append `CHAINLENS_CONTENTS` to `_CI_VERBS` so `build_capability_tools` emits `chainlens_contents`.
- Capability `description` = UX spec Part A contents-tool wording (verbatim) so the LLM routes correctly.

**Block If:**
- The upstream response shape diverges from `{results:[{url,title,content,summary,highlights:[{excerpt}],status}]}` (would change the parser) — HALT `blocked`.

**Never:**
- Do NOT reuse/widen `ResearchInput.output` Literal for contents (`schemas.py:116` is `answer|research|table` only) — dedicated `ContentsInput`/`ContentsOutput`.
- Do NOT add SSE parsing — `stream:false` returns plain JSON, not the `searchStream` event contract.
- Do NOT handle auth-walled/login pages here — surface `unsupported_auth_wall`; Browser Operator (Epic 32) owns those.
- No code comments with epic/story refs; comments explain why, not what.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY single URL | `urls=[u]`, no query | `contents` with item content+sources, `cost_micros` set | none |
| HAPPY multi-URL | `urls=[u1..uN]`, query set | results aggregated in order | none |
| Partial failure | some item `status!="ok"` | `status="partial"`, failed items flagged | surface per-item status |
| Auth-walled URL | item `status`/`unsupported_auth_wall` | typed `unsupported_auth_wall` result | route hint to Browser Operator |
| Missing API URL | `CHAINLENS_API_URL` unset | `status="engine_unavailable"`, degraded | typed degradation msg |
| Missing auth | no service token | `status="engine_unavailable"`, degraded | typed degradation msg |
| Upstream 5xx/timeout | error response | `status="engine_unavailable"` | typed degradation msg |
| PII in query | query with names/phone/email | redacted before send | `redact_pii()` first |

</intent-contract>

## Code Map

- `app/capabilities/chainlens/contents/__init__.py` — NEW: export capability.
- `app/capabilities/chainlens/contents/schemas.py` — NEW: `ContentsInput`{`urls` (1–100), `query?`, `optimizationMode?` (`instant|fast|balanced|auto`), `sources?`, `subpages?` (0–10), `subpageTarget?`, `livecrawl?` (`always|fallback|never`), `maxAgeHours?` (1–2160), `summary?`, `highlights?` (bool|list), `workspace_id`, `correlation_id?`}; `ContentsOutput`{`items`/`sources`, `content`, `status`, `degraded`, `cost_micros`, `message?`}.
- `app/capabilities/chainlens/contents/executor.py` — NEW: `ContentsExecutor` — mirrors `EntitySearchExecutor` (auth via `ChainLensServiceAuth`, `redact_pii` on query, `httpx.AsyncClient` `stream:false`, retry-once-on-401 pattern, map `{results:[]}`→`ContentsOutput`).
- `app/capabilities/chainlens/contents/definition.py` — NEW: `CHAINLENS_CONTENTS = Capability(name="chainlens.contents", …)` + `register_capability`.
- `app/capabilities/news/entity_search/{definition,executor,schemas}.py` — REUSE pattern (copy structure; do NOT modify).
- `app/services/chainlens/auth.py` — REUSE `get_outbound_headers`, `cost_dollars_to_micros` (`:222`,`:319`).
- `app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py:18` — EDIT: append `CHAINLENS_CONTENTS` to `_CI_VERBS` so `build_capability_tools` emits `chainlens_contents`.
- `app/services/pii/redact.py` — REUSE `redact_pii`.
- `app/capabilities/core/access/agent.py` — no change (auto tool generation).

## Tasks & Acceptance

**Execution:**
- `app/capabilities/chainlens/contents/schemas.py` — create `ContentsInput`/`ContentsOutput` (PII validators like entity_search) — input contract.
- `app/capabilities/chainlens/contents/executor.py` — `ContentsExecutor.execute` POST `/api/v1/search` `output=contents` `stream:false`; auth; `redact_pii(query)`; parse `results`→items; map `costDollars`→`cost_micros`; typed degradation — core logic.
- `app/capabilities/chainlens/contents/definition.py` — register `CHAINLENS_CONTENTS` (`description` verbatim UX-spec Part A contents wording) — expose capability.
- `app/capabilities/chainlens/contents/__init__.py` — export `CHAINLENS_CONTENTS`.
- `app/agents/…/builtins/chainlens/tools/index.py` — append `CHAINLENS_CONTENTS` to `_CI_VERBS` — surface `chainlens_contents` to agent.
- `tests/unit/capabilities/chainlens/contents/` — unit tests: happy single/multi-URL, partial, auth-wall, missing-URL/auth, 5xx, PII redaction, `cost_micros`, tool registration (mock httpx + cassette) — AC coverage.

**Acceptance Criteria:**
- Given a request to read 1+ URLs (optional query), when `chainlens.contents` runs, then it calls `POST /api/v1/search` `output=contents` `stream:false` and returns `ContentsOutput` with clean `content`, `sources`, `cost_micros` (AC-1/AC-2).
- Given an auth-walled/dynamic-JS URL, when crawled, then it returns `unsupported_auth_wall` typed result (not raw error) (AC-3).
- Given completion, when billed, then `TokenUsage` `usage_type="chainlens_contents"` is recorded (AC-4).
- Given outbound `query`, when leaving Nowing, then it passed `redact_pii()` (AC-5).
- Given `_CI_VERBS` includes `CHAINLENS_CONTENTS`, when agent tools load, then `chainlens_contents` is in `<available_tools>` (AC-6).

## Spec Change Log

## Review Triage Log

### 2026-09-20 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 10 (high 2, medium 5, low 3)
- defer: 9 (medium 2, low 7)
- reject: 9
- addressed_findings:
  - `[high]` `[patch]` Default URL-join query bi redact_pii lam hong → chi redact user-supplied query
  - `[high]` `[patch]` URL scheme validation (http/https only) — chan javascript:/file:/SSRF-adjacent
  - `[medium]` `[patch]` estimated_units scale theo len(urls) (min 100)
  - `[medium]` `[patch]` combined_content cap 50K chars + truncation marker
  - `[medium]` `[patch]` Timeout default 60s → 120s
  - `[medium]` `[patch]` correlation_id propagate vao headers + log extras
  - `[medium]` `[patch]` Item ok nhung rong content/summary → error
  - `[medium]` `[patch]` Results rong → partial (khong complete)
  - `[low]` `[patch]` Log warning chainlens_contents_unusable_cost cho non-finite cost
  - `[low]` `[patch]` Dedupe URLs + detect missing URLs trong response

## Design Notes

Upstream contract (verified `chainlens-research` `apiClient.ts:715+`): request `{output:'contents', urls[], query, sources, optimizationMode, stream:false, subpages?, subpageTarget?, livecrawl?, maxAgeHours?, summary?, highlights?}` → response `{results:[{url,title,content,summary,highlights:[{excerpt}],status}], costDollars}`. `anyError = any item.status!='ok'` → `partial`. `query` defaults to `urls.join('\n')`.

## Verification

**Commands:**
- `cd nowing_backend && python -c "from app.capabilities.chainlens.contents.definition import CHAINLENS_CONTENTS; print(CHAINLENS_CONTENTS.name)"` — expected: `chainlens.contents`
- `cd nowing_backend && pytest tests/unit/capabilities/chainlens/contents -q` — expected: all pass
- `cd nowing_backend && python -c "from app.agents.chat.multi_agent_chat.subagents.builtins.chainlens.tools.index import _CI_VERBS; print([v.name for v in _CI_VERBS])"` — expected: includes `chainlens.contents`

## Auto Run Result

Status: done

### Tom tat thay doi
Them `chainlens.contents` capability — doc token-efficient markdown tu 1-100 URLs qua ChainLens `POST /api/v1/search` (`output=contents`, `stream:false`), expose tool `chainlens_contents` cho chainlens sub-agent.

### Files changed
- `nowing_backend/app/capabilities/chainlens/contents/schemas.py` — ContentsInput/ContentsOutput/ContentItem + validators (scheme http/https, estimated_units scale)
- `nowing_backend/app/capabilities/chainlens/contents/executor.py` — ContentsExecutor: POST contents, PII redact (user query only), auth + 401 rotate retry, parse results, cost_micros, typed degradation, content cap 50K, dedupe/missing-URL detection
- `nowing_backend/app/capabilities/chainlens/contents/definition.py` — Capability registration (billing_unit=CHAINLENS_QUERY, context_aware=True)
- `nowing_backend/app/capabilities/chainlens/contents/__init__.py` — exports
- `nowing_backend/app/capabilities/chainlens/__init__.py` — import contents definition
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/tools/index.py` — `_CI_VERBS` += CHAINLENS_CONTENTS
- `nowing_backend/tests/unit/capabilities/chainlens/contents/test_contents.py` — 27 tests

### Review findings breakdown
- Patches applied: 10 (high 2, medium 5, low 3)
- Deferred: 9 (medium 2, low 7)
- Rejected: 9
- Follow-up review: patched counts (high 2, medium 5, low 3) → score = 3×5 + 1×3 = 18 ≥ 5 → **true**

### Verification
- `python -c "...CHAINLENS_CONTENTS.name"` → `chainlens.contents` ✅
- `_CI_VERBS` includes chainlens.contents ✅
- `pytest tests/unit/capabilities/chainlens/contents -q` → **27 passed** (sau patches, re-verified doc lap) ✅
- Matrix Test Audit: 8/8 I/O matrix rows covered boi tests da chay & pass ✅

### Residual risks
- Billing edge: all-items-failed partial van bill fallback flat rate (deferred, can policy quyet)
- system_prompt.md/description.md chua expose chainlens_contents — theo plan, apply batch sau khi du capabilities
