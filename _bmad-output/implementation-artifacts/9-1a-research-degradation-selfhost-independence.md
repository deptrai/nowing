---
baseline_commit: 25ba542c2a3dec95b0a4020da8c129242ba748e2
baseline_branch: develop
story_key: 9-1a-research-degradation-selfhost-independence
status: done
---

# Story 9.1a: Research Degradation & Self-Host Independence

**Status:** done
**Epic:** 9 — Deep Research dang tin cay: khong vo, khong treo, tinh phi dung
**Priority:** P0 — tien de truoc khi public repo
**Requirements:** FR-38; AD-15; AD-17; AD-19 measurement seam
**Baseline:** `25ba542c2a3dec95b0a4020da8c129242ba748e2` on `develop`
**Dependencies:** Existing capability REST/agent doors, run recorder, Nowing hybrid KB retrieval. No production-code dependency on Story 9.1b, 9.2, 9.3, 9.4 or 9.5.

## Story

La self-hoster,
toi muon Nowing dung duoc day du ma khong can deep-research engine, va deep research khong hard-fail khi engine cham, chet, bi rate-limit, bi 5xx, hoac chua cau hinh,
de toi khong cai xong moi phat hien mot tinh nang vo, va duong OSS/PLG cua Nowing khong sup.

## Current Reality

Tai baseline `25ba542c2a3dec95b0a4020da8c129242ba748e2`:

- `chainlens.research` da la capability that su: `definition.py` dang ky `Capability(name="chainlens.research")`, `ResearchInput`, `ResearchOutput`, executor `build_research_executor()`, va `BillingUnit.CHAINLENS_QUERY`.
- `_call_chainlens()` goi `POST {CHAINLENS_API_URL}/api/v1/search` voi Bearer service key. Neu `CHAINLENS_API_KEY` rong, ham raise `ConfigurationError(code="CHAINLENS_NOT_CONFIGURED")`; day la 500 tren REST/agent, khong phai degradation.
- `build_research_executor()` hien chi bat `httpx.TimeoutException` thanh `ExternalServiceError(code="CHAINLENS_TIMEOUT")` va `httpx.RequestError` thanh `ExternalServiceError(code="CHAINLENS_UNREACHABLE")`; upstream 401/429/5xx va SSE error deu thanh `ChainLensError`. Khong co fallback.
- `_parse_sse()` hien chi xu ly `error`, `done`, `block`, `updateBlock`; no bo im lang `partial`, `insufficientEvidence`, `heartbeat`, `progress`, `evidence_ready`, `synthesizing`, `noop`.
- `_parse_sse()` dang suy doan insufficient evidence bang heuristic: neu khong co `answer` va khong co `sources`, `saw_done=True` thi `status="insufficient_evidence"`, nguoc lai `timeout`. Dieu nay gop "engine noi khong du bang chung" voi "stream chet giua duong".
- `ResearchOutput.status` hien chi la `complete | partial | timeout | insufficient_evidence`. Chua co `engine_unavailable`; `billable_units` tra `0` khi khong co answer/sources, nen no-content degraded state co the khong bi tinh tien gia.
- REST door da co sync va async. Sync route goi executor inline, ghi `Run`, charge, tra typed output va `X-Run-Id`. Async `?mode=async` tao `Run` running, tra 202, stream `/runs/{id}/events`, cancel, history va terminal `run.finished`.
- Agent door hien sync-only, nhung dung cung registry executor, gate/charge, ghi `Run`, va tra inline output/preview. Story 9.3 moi so huu async agent door; 9.1a chi dam bao agent sync khong raise khi engine unavailable.
- MCP `nowing_chainlens_research` di qua `run_scraper()`, tuc goi REST scraper route. Neu REST output typed dung, MCP nhan cung degradation contract.
- Nowing co hybrid KB retrieval san co: `app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py::search_chunks()` nhan `AsyncSession`, `workspace_id`, `SearchScope`, `top_k`, loc `Document.workspace_id`, va tra `DocumentHit` voi real `document_id`/`chunk_id`. Legacy `app/retriever/chunks_hybrid_search.py::hybrid_search()` cung loc theo `workspace_id` va preserve chunk IDs.
- Quan trong: executor hien chi nhan `payload`. Fallback sang hybrid search can `session` va `workspace_id`, nen khong the lam dung bang cach sua rieng `executor.py` ma khong them context seam. Context san co o REST/agent doors la `CapabilityContext(session, workspace_id)`.
- PRD/AD-15 van co dong mo ta SSE theo `event:`/`data:` va `[DONE]`, nhung OQ-7/readiness da verify ChainLens thuc te phat NestJS `@Sse()` data-only frames, `type` nam trong JSON, terminal la `{"type":"done"}`. 9.1a phai parse typed degradation events theo wire behavior that; 9.1b moi so huu full contract-regression/doc correction.
- AD-19 da verify Nowing co `BlockType` classifier (`ok`, `cloudflare`, `captcha_recaptcha`, `captcha_hcaptcha`, `datadome`, `kasada`, `rate_limited`, `empty`, `unknown`). 9.1a khong build crawler escalation, nhung khi payload partial/insufficientEvidence co blocked URL/citation metadata thi phai do coverage counter theo taxonomy san co.

## Resolved Decisions

### D1 — Honest output, no fake success

Degradation is a successful transport response only, not a complete research result. REST/agent/MCP may return HTTP/tool success so self-host does not break, but `ResearchOutput.status` must be one of the degraded statuses and must never be `complete` unless ChainLens produced a complete result.

Required output taxonomy:

| Situation | `ResearchOutput.status` | Required details |
|---|---|---|
| ChainLens complete with answer/sources | `complete` | Preserve answer, sources order, chat_id, web_url |
| ChainLens explicit partial with usable partial evidence | `partial` | Preserve engine `reason`, partial evidence, citations |
| ChainLens explicit insufficient evidence and no useful evidence | `insufficient_evidence` | Preserve engine `reason`; do not re-derive by heuristic |
| Engine unavailable and KB fallback has citable hits | `partial` | `degraded=true`; reason identifies engine failure; sources are labelled KB citations |
| Engine unavailable and no citable fallback evidence | `engine_unavailable` | `degraded=true`; no fabricated answer or citation; human-readable `next_action` |
| Stream ends without terminal after heartbeat/no terminal and fallback unavailable | `engine_unavailable` or `timeout` only if preserving backward compatibility requires `timeout` | Must not be `insufficient_evidence` unless engine explicitly said so |

Additive schema fields are allowed and expected where needed, for example `degraded: bool`, `degradation_reason`, `engine_reason`, `source_type`, `document_id`, `chunk_id`, `block_type`. Do not remove existing fields or break existing successful responses.

### D2 — Self-host no-key is an expected runtime state

`CHAINLENS_API_KEY=""` is normal for self-host Phase 1. `_call_chainlens()` must not raise an uncaught `ConfigurationError` for this path. Deep research returns typed `engine_unavailable` with setup guidance; all other Nowing capabilities continue to run.

Do not add a fake local ChainLens, do not ship a closed-source engine binary, and do not point self-host directly at ChainLens. Phase 2 metered self-host access is Story 9.5 and must go through Nowing Cloud API.

### D3 — Bounded hybrid fallback uses Nowing KB, not open-web synthesis

Fallback is allowed only when the shared access layer has an authorized `CapabilityContext` with `workspace_id` and `AsyncSession`. It searches the caller's workspace KB using existing hybrid retrieval. It is not a replacement for open-web deep research and must be labelled as degraded workspace-KB evidence.

Fallback bounds:

- `top_k` fixed at a small constant, max 5 documents.
- Per-document chunks follow existing retriever bounds; do not full-scan all chunks.
- No LLM synthesis is required in this story. A deterministic answer may summarize that the engine is unavailable and list relevant KB passages; claims must come only from cited chunks.
- If no context is available, return `engine_unavailable` without fallback.
- If hybrid retrieval itself returns no hits, return `engine_unavailable` without fabricated citations.

### D4 — Add a minimal context seam in the shared doors

Do not use globals or request payload fields to infer tenant context. Implement a small explicit execution seam in the capability core so REST sync, REST async and agent calls can pass `CapabilityContext` to context-aware executors while preserving existing `executor(payload)` behavior for all other capabilities.

One acceptable shape: add a context-aware invocation helper in `app/capabilities/core/` and let only `chainlens.research` opt into it. REST and agent doors must both use the same helper. The seam must not require adding `workspace_id` or any Nowing tenancy concept to the ChainLens HTTP contract.

### D5 — Parse engine degradation events before heuristics

Parser priority is explicit engine event first, fallback heuristic second:

1. Parse data-only JSON frames where `type` is inside the payload.
2. Parse `partial` with `state`, `reason`, optional partial answer/sources.
3. Parse `insufficientEvidence` with `partial`, `reason`, optional source/citation metadata.
4. Parse `heartbeat` and record last-alive state so "engine alive but not terminal yet" is not classified as "no evidence".
5. Preserve forgiving behavior for unknown event types; unknown events are ignored with debug logging, not raised.
6. Keep defensive `event: error` handling if desired, but tests for 9.1a must use the verified data-only typed frames for partial/insufficientEvidence/heartbeat.

### D6 — Citations must stay real and typed

ChainLens web citations remain web `Source` entries in engine order. KB fallback citations must carry real Nowing locators (`document_id`, `chunk_id`) and must not fabricate web URLs. If an internal locator is placed in `Source.url`, it must be clearly internal, such as `nowing://documents/{document_id}/chunks/{chunk_id}`, with additive structured fields for clients that can render chunk citations.

Agent/subagent prompts must be updated so `engine_unavailable` and degraded `partial` are reported as partial/error-like states, not as success. Existing rule "never invent titles, URLs, or claims" stays binding.

### D7 — Failure taxonomy is stable and observable

Use stable reason strings for logs/metrics/output:

| Upstream/fallback condition | Reason |
|---|---|
| Missing API key | `not_configured` |
| Request timeout | `timeout` |
| DNS/connect/request error | `unreachable` |
| HTTP 401/403 | `auth_failed` |
| HTTP 429 | `rate_limited` |
| HTTP 5xx or typed upstream error | `upstream_error` |
| Explicit insufficient evidence | `insufficient_evidence` |
| Explicit partial | `partial` |
| Stream ended without terminal | `stream_incomplete` |
| KB fallback returned hits | `fallback_kb_hits` |
| KB fallback returned none | `fallback_kb_empty` |
| KB fallback failed | `fallback_kb_error` |

Observability must include fallback/degradation rate for SM-11c and a separate coverage counter for blocked URL/citation evidence when partial/insufficientEvidence payload permits. Metric labels must not contain raw query text, URL, API key, answer text, user id or workspace name.

### D8 — REST, agent, async and MCP doors must agree

The same typed output contract applies across:

- REST sync `POST /workspaces/{id}/scrapers/chainlens/research`;
- REST async `POST .../chainlens/research?mode=async` and stored `runs.output_text`;
- agent tool `chainlens_research`;
- MCP `nowing_chainlens_research`, because it goes through REST `run_scraper()`.

Async transport remains Story 9.3's domain. 9.1a must not build a new job table, new progress endpoint, Redis-backed bus, notification persistence or deliverable persistence.

### D9 — Security and tenant isolation are part of acceptance

Fallback search must use the `workspace_id` authorized by `check_workspace_access()` and passed through `CapabilityContext`. Never trust workspace information from `ResearchInput`, `system_instructions`, ChainLens payload, or agent text. Do not send `workspace_id`, user id, tenant metadata, API key or KB contents to ChainLens beyond the existing request fields.

No degraded output may leak whether another workspace has matching KB content. Logs and metrics use low-cardinality reasons only.

## Dev Notes (Ngữ cảnh phát triển)

### Architecture Compliance

- **AD-15 — ChainLens là external deep-research dependency, không phải scraper.** Giữ nguyên vị trí `app/capabilities/chainlens/` nhưng governance là external service. Nowing sở hữu billing, failure, degradation. Không merge code. Self-host Phase 1 chạy không có engine. Cấm self-host → engine trực tiếp.
- **AD-17 — Async door đã có.** `?mode=async` + `GET /runs/{id}/events` sẵn có. Story 9.1a KHÔNG xây bảng job/progress mới, Redis bus, notification hay deliverable persistence.
- **AD-19 — Năng lực vượt tường thuộc Nowing; engine có 0%.** Khi parse `partial`/`insufficientEvidence` có metadata URL/citation bị chắn, gắn `BlockType` coverage counter nhưng không build escalation/crawl mới.
- **AD-8 — Wallet thống nhất.** `CHAINLENS_QUERY_MICROS_PER_CALL` là fallback cho 9.2; 9.1a giữ `billable_units == 0` khi `engine_unavailable` không có nội dung.
- **AD-18 / 3.14 — Bounded retrieval.** Fallback dùng hybrid search có `top_k` ≤ 5, không full-scan, lọc `workspace_id`.
- **AD-2 — SQLAlchemy async + Alembic + pgvector.** Nếu thay đổi schema `ResearchOutput` thì dùng additive fields; nếu cần migration thì phải viết.
- **AD-3 — Capabilities tự đăng ký route.** Không refactor layout `app/capabilities/chainlens/`; chỉ thay đổi executor/parser/schemas.
- **AD-11.1 — Memory recipe (không phải mục tiêu 9.1a).** Nếu fallback tạo memory thì phải copy `capability` + `input` + soft `source_run_id`.

### Technical Requirements

- **`ResearchOutput` schema:** thêm `engine_unavailable` vào `status`; thêm các trường tùy chọn `degraded: bool`, `degradation_reason: str`, `engine_reason: str`, `source_type: str`, `document_id`, `chunk_id`, `block_type`; không xoá trường cũ, không break response thành công.
- **Parser `_parse_sse`:** ưu tiên data-only JSON frames (`{"type":"..."}`). Parse `partial`, `insufficientEvidence`, `heartbeat`; ghi nhận `saw_heartbeat` để không suy đoán heuristic. Giữ nhánh `event: error` defensive nếu muốn, nhưng test 9.1a phải dùng data-only frames. Unknown events bỏ qua, không raise.
- **Executor `_call_chainlens` / wrapper:** `CHAINLENS_API_KEY == ""` không raise `ConfigurationError`; trả `engine_unavailable` với `degradation_reason="not_configured"`. Timeout, DNS, 401/403/429/5xx, stream-incomplete đều map sang lý do ổn định (D7) và kích hoạt fallback khi có `CapabilityContext`.
- **Bounded KB fallback:** dùng `CapabilityContext(session, workspace_id)` từ REST/agent door. Gọi `search_chunks()`/`ChucksHybridSearchRetriever` hoặc `hybrid_search()` với `top_k ≤ 5`, `workspace_id` đã authorize. Map hit thành `Source` nội bộ với `document_id`/`chunk_id`, URL dạng `nowing://documents/{document_id}/chunks/{chunk_id}`. Không tổng hợp LLM, không crawl mở web.
- **Shared context-aware invocation seam:** thêm helper trong `app/capabilities/core/` (ví dụ `ContextAwareExecutor` hoặc `execute_with_context`) để REST sync, REST async, agent có thể truyền `CapabilityContext` cho `chainlens.research` mà vẫn giữ `executor(payload)` cho các capability khác. Không thêm `workspace_id` vào `ResearchInput` hay HTTP request ChainLens.
- **Billing:** `ResearchOutput.billable_units == 0` khi `status="engine_unavailable"` hoặc không có answer/sources. Fallback `partial` có citations vẫn dùng `BillingUnit.CHAINLENS_QUERY` (flat rate) — không thêm debit mới, Story 9.2 sẽ xử lý `costDollars`.
- **Observability:** low-cardinality counters (`degradation_reason`, `final_status`, `fallback_attempted`, `fallback_used`, `fallback_hit_count`, `blocked_url_coverage_by_block_type`). Redact query, URL, answer text, API key, user id, workspace name khỏi labels/logs.
- **Agent / MCP:** `agent.py` không raise cho trường hợp `engine_unavailable` dự kiến; trả dict/preview với `next_step`. Subagent prompt cập nhật để `engine_unavailable` và degraded `partial` được báo là partial/error, không là success.
- **REST async:** `runs.output_text` lưu cùng typed output với sync; SSE kết thúc bằng `run.finished` sạch.
- **Self-host / operator docs:** thêm ghi chú trong `nowing_backend/.env.example` (và `docker/.env.example` nếu có) rằng `CHAINLENS_API_KEY` để trống là hợp lệ, deep research là năng lực cloud, không hướng dẫn chạy engine local.

### Library & Framework Requirements

- **`httpx`** — giữ nguyên cho async HTTP; xử lý `TimeoutException`, `RequestError`, status codes.
- **Pydantic v2 (`BaseModel`)** — additive fields với default, backward-compatible; `Literal` mở rộng status enum.
- **SQLAlchemy async + `pgvector`** — fallback query nội bộ; reuse `Chunk`, `Document`, hybrid search CTE đã có.
- **`pytest` / `pytest-asyncio`** — mock `httpx.AsyncClient`, `_call_chainlens` injection, test DB cho fallback.
- **Không thêm dependency mới.** Dùng lại `BlockType` (`app/utils/crawl/classifier.py`), `CapabilityContext` (`app/capabilities/core/types.py`), `search_chunks` / `ChucksHybridSearchRetriever`.

### File Structure / Project Structure Notes

- `nowing_backend/app/capabilities/chainlens/research/executor.py` — **UPDATE**: parser `_parse_sse`, `_call_chainlens` failure taxonomy, fallback orchestration.
- `nowing_backend/app/capabilities/chainlens/research/schemas.py` — **UPDATE**: `ResearchOutput` status enum, additive fields, `billable_units`.
- `nowing_backend/app/capabilities/chainlens/research/definition.py` — **UPDATE**: đăng ký `Capability` với context-aware hook nếu cần.
- `nowing_backend/app/capabilities/core/types.py` — **UPDATE/REUSE**: `CapabilityContext`; có thể thêm helper context-aware executor.
- `nowing_backend/app/capabilities/core/access/rest.py` — **UPDATE**: truyền `CapabilityContext` vào executor sync/async.
- `nowing_backend/app/capabilities/core/access/agent.py` — **UPDATE**: truyền context, không raise cho degraded output dự kiến.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py` — **REUSE**: gọi `search_chunks()` với `workspace_id` + `SearchScope()`.
- `nowing_backend/app/retriever/chunks_hybrid_search.py` — **REUSE**: fallback cũng có thể dùng `hybrid_search()` nếu context cho phép; không duplicate SQL.
- `nowing_backend/app/utils/crawl/classifier.py` — **REUSE**: `BlockType` cho coverage counter khi payload có metadata.
- `nowing_backend/app/observability/metrics.py` — **UPDATE/ADD**: helpers ghi degradation/fallback counters.
- `nowing_backend/.env.example`, `docker/.env.example` (nếu có) — **UPDATE**: ghi chú `CHAINLENS_API_KEY` trống.
- `nowing_backend/tests/unit/capabilities/chainlens/research/` — **ADD**: parser unit tests (`partial`/`insufficientEvidence`/`heartbeat`/unknown), executor fallback tests, no-key tests.
- `nowing_backend/tests/unit/capabilities/access/` — **ADD/UPDATE**: REST sync/async + agent door consistency tests.
- `nowing_backend/tests/integration/retriever/` hoặc `tests/integration/capabilities/chainlens/research/` — **ADD**: fallback tenant-negative với 2 workspace.
- `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py` — **UPDATE chỉ khi** `run_scraper()` renderer che mất trạng thái degraded.
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/system_prompt.md` — **UPDATE**: mapping `engine_unavailable`/degraded `partial`.

> Xem chi tiết danh sách file và hành vi cần bảo toện trong `## Project Structure / File Ownership` bên dưới.

### Testing Standards Summary

- Unit tests trong `tests/unit/capabilities/chainlens/research/` dùng `monkeypatch` cho `httpx.AsyncClient` hoặc inject `fake_search` vào `build_research_executor`; KHÔNG dùng mạng thật.
- Mỗi trường hợp degrade (no-key, timeout, unreachable, 401/403/429/5xx, stream-incomplete, partial, insufficientEvidence, heartbeat-only) có test xác định.
- Integration tests cho fallback sử dụng test DB với 2 workspace, xác nhận tenant isolation và `top_k ≤ 5`.
- Parser tests dùng data-only SSE fixtures phản ánh wire behavior thật (`{"type":"done"}`, `{"type":"partial",...}`), không dựa tài liệu cũ `event:`/`data:[DONE]`.
- Billing test: `engine_unavailable` với no-content → `billable_units == 0`; `charge_capability` gọi với output degraded không tạo charge.
- Observability test: logs/metrics chứa reason/status, không chứa query/URL/answer/key/user/workspace name.
- Vì story P0 chạm DB logic (fallback), sau dev chạy `bmad-nowing-integration-test` và `bmad-nowing-mutation-gate` / `bmad-nowing-human-review-gate` theo pipeline.

## Acceptance Criteria

1. **Self-host without ChainLens is honest and non-breaking** (FR-38, D1, D2)
   - **Given** `CHAINLENS_API_KEY` is empty,
   - **When** REST sync, REST async, agent tool or MCP calls `chainlens.research`,
   - **Then** the call does not raise an uncaught `ConfigurationError`, does not return HTTP 500 for the no-key path, and returns typed output with `status="engine_unavailable"` unless authorized KB fallback provides citable evidence,
   - **And** `next_action` explains that hosted deep research is unavailable/configuration-gated,
   - **And** all other Nowing capabilities remain unaffected.

2. **Timeout, unreachable and upstream failures degrade instead of hard-failing** (FR-38, D1, D3, D7)
   - **Given** ChainLens times out, cannot be reached, returns 5xx, emits typed upstream error, rejects auth, or rate-limits,
   - **When** the caller has an authorized `CapabilityContext`,
   - **Then** Nowing attempts bounded hybrid KB fallback,
   - **And** returns `partial` with KB citations when fallback has evidence,
   - **And** returns `engine_unavailable` with no fabricated answer/citation when fallback has no evidence,
   - **And** the output carries a stable `degradation_reason`.

3. **Fallback is tenant-safe and bounded** (D3, D4, D9)
   - **Given** two workspaces contain different indexed documents,
   - **When** ChainLens is unavailable for a caller authorized only to workspace A,
   - **Then** fallback search can return only documents/chunks from workspace A,
   - **And** query, candidate pool and output size are bounded by explicit constants,
   - **And** no workspace or user identifiers are sent to ChainLens.

4. **Citations are preserved and never invented** (FR-24 carryover, FR-38, D6)
   - **Given** ChainLens returns sources in a complete or partial response,
   - **When** Nowing parses the stream,
   - **Then** source order and citation-bearing answer text are preserved.
   - **Given** fallback uses Nowing hybrid search,
   - **When** output is built,
   - **Then** every fallback source has a real `document_id` and `chunk_id`, internal sources are clearly labelled as KB evidence, and no external URL/title is fabricated.

5. **Explicit partial and insufficientEvidence events drive state** (FR-38, D5)
   - **Given** ChainLens emits data-only frames such as `{"type":"partial","state":"insufficient_evidence","reason":"..."}` or `{"type":"insufficientEvidence","partial":...,"reason":"..."}`,
   - **When** `_parse_sse()` runs,
   - **Then** Nowing maps the explicit event into `partial` or `insufficient_evidence`, preserves `reason`, preserves any partial evidence/citations,
   - **And** the old no-answer/no-sources heuristic is not the primary source of truth for insufficient evidence.

6. **Heartbeat is parsed as liveness, not progress scope creep** (FR-38, D5, non-goal 9.3)
   - **Given** ChainLens emits `{"type":"heartbeat"}` before a terminal event,
   - **When** parsing the stream,
   - **Then** Nowing records that the engine was alive and avoids classifying the run as insufficient evidence solely because no answer was seen yet,
   - **And** 9.1a does not map full phase progress to UI; that work remains Story 9.3.

7. **REST sync and async doors store the same typed degradation** (AD-17, D8)
   - **Given** REST sync receives degraded output,
   - **When** the response is returned,
   - **Then** the body has the typed degraded status and `X-Run-Id` points to a run whose serialized output contains the same status.
   - **Given** REST async receives degraded output,
   - **When** the background run finalizes,
   - **Then** `/runs/{id}` stores the same typed output and `/runs/{id}/events` terminates cleanly; no new async route, job table or Zero publication is created.

8. **Agent and MCP doors do not mask degraded states** (D6, D8)
   - **Given** the agent tool or `nowing_chainlens_research` receives `engine_unavailable`, `partial`, `timeout` or `insufficient_evidence`,
   - **When** it renders or maps output,
   - **Then** the result is reported as partial/error-like per subagent contract, includes `next_step`, and does not claim success.

9. **Observability proves degradation without leaking secrets** (SM-11c, AD-19, D7, D9)
   - **Given** any degraded path runs,
   - **When** logs/metrics are emitted,
   - **Then** counters include stable reason, final status, fallback attempted/used, and fallback hit count,
   - **And** partial/insufficientEvidence payloads that include blocked URL/citation metadata increment coverage counters using `BlockType` values where available,
   - **And** labels exclude query text, URLs, answer text, API keys, user ids and workspace names.

10. **Billing does not charge fake no-content success** (FR-38, AD-8 carryover)
    - **Given** output has `status="engine_unavailable"` and no answer/sources,
    - **When** `charge_capability()` runs,
    - **Then** `ResearchOutput.billable_units == 0` and no fake ChainLens query charge is created.
    - **Given** degraded `partial` returns citable KB evidence,
    - **Then** this story does not introduce new wallet debit semantics beyond existing capability billing; Story 9.2 owns real `deep_research` cost metering.

11. **Public-repo gate evidence is reproducible** (D5, FR-38)
    - **Given** reviewers run the targeted suite with ChainLens unconfigured,
    - **When** they inspect evidence for Story 9.1a,
    - **Then** it shows self-host no-key behavior, timeout/degrade behavior, parser partial/insufficientEvidence/heartbeat behavior, REST/agent consistency, no fabricated citations, and no secret-bearing logs,
    - **And** broad public docs positioning remains Story 9.4 while the minimal operator-facing no-key behavior is documented where this story touches config/self-host surfaces.

## Tasks / Subtasks

- [ ] **T1 — Extend research schemas for honest degraded state** (AC 1, 2, 4, 5, 8, 10)
  - [ ] Add `engine_unavailable` to `ResearchOutput.status`.
  - [ ] Add minimal additive fields for degradation/engine reason and KB citation locators.
  - [ ] Preserve backward-compatible fields for complete ChainLens success.
  - [ ] Keep no-answer/no-source `billable_units == 0`.

- [ ] **T2 — Add shared context-aware capability invocation seam** (AC 2, 3, 7, 8)
  - [ ] Implement one shared helper in capability core so REST sync, REST async and agent doors can pass `CapabilityContext`.
  - [ ] Preserve existing `executor(payload)` behavior for all non-ChainLens capabilities.
  - [ ] Use the same helper in `access/rest.py` and `access/agent.py`.
  - [ ] Do not add tenancy fields to `ResearchInput` or ChainLens HTTP request.

- [ ] **T3 — Implement bounded KB fallback for ChainLens failures** (AC 1, 2, 3, 4, 10)
  - [ ] Detect `not_configured`, timeout, unreachable, auth, rate-limit, upstream error and stream-incomplete cases.
  - [ ] When context exists, call existing hybrid retrieval with `workspace_id` from `CapabilityContext`, `SearchScope()` and `top_k <= 5`.
  - [ ] Map hits to degraded `ResearchOutput` with real `document_id`/`chunk_id` citation locators.
  - [ ] Return `engine_unavailable` without fallback when context is absent or fallback has no hits.
  - [ ] Do not run LLM synthesis or open-web crawling in fallback.

- [ ] **T4 — Parse ChainLens partial, insufficientEvidence and heartbeat events** (AC 5, 6, 9)
  - [ ] Parse verified data-only typed JSON frames.
  - [ ] Preserve explicit engine `reason`, partial content and citations.
  - [ ] Track heartbeat/liveness internally and use it to avoid the old insufficient-evidence heuristic.
  - [ ] Keep unknown event types forgiving.
  - [ ] Leave full progress-to-UI mapping for Story 9.3.

- [ ] **T5 — Keep REST, async, agent and MCP behavior consistent** (AC 1, 7, 8)
  - [ ] REST sync returns typed degraded output and records a run.
  - [ ] REST async stores the same typed output in `runs.output_text` and terminates the existing run event stream cleanly.
  - [ ] Agent tool returns degraded dict/preview instead of raising for expected engine-unavailable cases.
  - [ ] MCP inherits REST output via `run_scraper()`; update rendering only if needed to avoid masking status.
  - [ ] Update ChainLens subagent status mapping for `engine_unavailable` and degraded `partial`.

- [ ] **T6 — Observability and public-repo gate evidence** (AC 9, 11)
  - [ ] Add low-cardinality metrics/logs for degradation reason, final status, fallback attempted/used and fallback hit count.
  - [ ] Add blocked URL/citation coverage counters using `BlockType` when partial/insufficientEvidence payloads include enough metadata.
  - [ ] Verify logs do not include raw query text, URLs, API keys, answer text, user ids or workspace names.
  - [ ] Produce implementation evidence under `_bmad-output/implementation-artifacts/evidence/` for the public-repo gate.

- [ ] **T7 — Minimal self-host/operator documentation** (AC 1, 11)
  - [ ] Document in `nowing_backend/.env.example` and/or `docker/.env.example` that empty `CHAINLENS_API_KEY` is supported and yields `engine_unavailable`.
  - [ ] Do not write broad Nowing/ChainLens marketing or README positioning here; Story 9.4 owns that.
  - [ ] Do not instruct self-hosters to run ChainLens locally.

- [ ] **T8 — Deterministic tests** (AC 1-11)
  - [ ] Add parser unit tests for `partial`, `insufficientEvidence`, `heartbeat`, unknown event, and stream-incomplete cases.
  - [ ] Add executor/fallback unit tests for no key, timeout, unreachable, 401/403, 429 and 5xx.
  - [ ] Add tenant-negative fallback test with two workspaces.
  - [ ] Add REST sync and async tests for typed degraded output and stored run output.
  - [ ] Add agent-door test that expected degradation returns output rather than raising.
  - [ ] Add MCP or `run_scraper()` rendering test if status is currently hidden.
  - [ ] Add billing test for `engine_unavailable` no-content `billable_units == 0`.
  - [ ] Add observability tests with redaction assertions.

### Review Findings

Đã hoàn thành code review 3 lớp (Blind Hunter, Edge Case Hunter, Acceptance Auditor) ngày 2026-07-29.

#### patch

- [x] [Review][Patch] [MEDIUM] Bỏ `insufficient_evidence` khỏi tập trigger KB fallback [executor.py:421-425] — Quyết định best practice: theo D1 table, chỉ `engine_unavailable` là trigger fallback rõ ràng; `insufficient_evidence` là kết quả tường minh của engine ("tìm rồi không có"), fallback sẽ làm che/giả mạo kết quả thành `partial`. Cần cập nhật Failure Taxonomy cho khớp.

- [x] [Review][Patch] [HIGH] `execute_with_context` dùng try/except TypeError theo nội dung message để chọn signature [core/__init__.py:55-67] — Có thể gọi lại executor mất context khi executor context-aware raise TypeError nội bộ, gây double side-effect / che bug / mất tenant. Nên dùng `inspect.signature` hoặc cờ `Capability.context_aware` (đã định nghĩa nhưng chưa dùng) để chọn đúng arity trước khi gọi.
- [x] [Review][Patch] [HIGH] Log/metric vẫn tiếp xúc query/URL/answer/API key [executor.py:302-320,406,481,521,531; metrics.py:1117-1157] — Vi phạm D7/AC-9 redaction. Cần xóa query, url, answer, api_key khỏi log/progress và signature metric; chỉ giữ low-cardinality reason/status/run_id.
- [x] [Review][Patch] [HIGH] `charge_capability` không được bọc try/except trong REST sync và agent door [rest.py:427-428; agent.py:122-123] — Lỗi ghi credit sẽ làm mất output đã tính và trả 500. Spec Q4/AC-7/AC-10 yêu cầu credit error không làm request fail (đã làm trong async path nhưng sync/agent chưa).
- [x] [Review][Patch] [HIGH] `partial` event bỏ qua trường `state` [executor.py:194-217] — Nếu `{"type":"partial","state":"insufficient_evidence","answer":"","sources":[]}`, code vẫn set `status="partial"`, có thể tính phí/trả trạng thái sai. Cần đọc `state` và map sang `insufficient_evidence` khi đủ điều kiện.
- [x] [Review][Patch] [HIGH] `_parse_sse` vẫn dùng heuristic `saw_done` + no content để gán `insufficient_evidence` [executor.py:268-280] — Vi phạm D5/AC-5 (chỉ `insufficient_evidence` khi engine tường minh phát sự kiện). Stream chết giữa chừng sẽ bị gán nhầm `insufficient_evidence`. Cần đổi path này thành `engine_unavailable`/`stream_incomplete`.
- [x] [Review][Patch] [HIGH] `test_system_prompt.py` dùng đường dẫn tuyệt đối sai project root [tests/unit/agents/chat/multi_agent_chat/subagents/builtins/chainlens/test_system_prompt.py:10] — `/Users/luisphan/Documents/nowing/...` không khớp `/Users/luisphan/Documents/GitHub/nowing`, sẽ fail trên CI/máy khác. Dùng `Path(__file__).resolve()` để lấy path tương đối.
- [x] [Review][Patch] [MEDIUM] KB fallback tạo một `Source` cho mỗi chunk, không cap tổng số [executor.py:435-452] — `top_k <= 5` documents nhưng mỗi document có thể có nhiều chunk, tối đa có thể >60 sources, phình response và làm `fallback_hit_count` cardinality cao. Cần cap tổng `Source` ở `top_k` (5) hoặc ngưỡng rõ ràng.
- [x] [Review][Patch] [MEDIUM] `_parse_sources`, `partial` blob, `sources`, `blocked_metadata` không validate kiểu dữ liệu [executor.py:68-92,203-205,219-223] — `partial` có thể là string/list, `sources`/`blocked_metadata` có thể là dict/non-iterable, dẫn đến `AttributeError`/`TypeError`. Cần guard `isinstance(..., dict)`/`isinstance(..., list)` trước khi dùng.
- [x] [Review][Patch] [MEDIUM] `_call_chainlens` gửi `stream=False` nhưng parse SSE, và không guard non-200/empty body [executor.py:312-347] — Hidden assumption contract; 3xx/201/204 hoặc body rỗng sẽ rơi vào `_parse_sse` và bị gán `timeout`/`stream_incomplete` thay vì `engine_unavailable`/`upstream_error`. Cần kiểm tra `status_code == 200` và `response.text` non-empty; xác nhận giá trị `stream` phù hợp với ChainLens.
- [x] [Review][Patch] [MEDIUM] `ResearchOutput.__setattr__` + `model_post_init` gây side effect tự động recompute [schemas.py:171-181,189-231] — Dễ tạo unexpected mutation, khó debug. Nên dùng Pydantic v2 `field_validator` / `model_validator` / `@computed_field` thay vì override `__setattr__`.
- [x] [Review][Patch] [MEDIUM] `_recompute_degradation` mặc định `degradation_reason="not_configured"` cho mọi `engine_unavailable` thiếu reason [schemas.py:193-197] — Có thể gán nhãn sai cho `auth_failed`/`rate_limited`/`upstream_error`. Nên default `unknown` hoặc require reason qua factory.
- [x] [Review][Patch] [MEDIUM] Metric `fallback_hit_count` được dùng làm label, tạo cardinality cao [metrics.py:1134-1157] — Counter và histogram đều gán `fallback_hit_count` làm attribute/label. Với counter chỉ cần reason/status; với histogram giá trị đo đã đủ, không cần label trùng. Dùng bucket `0`/`1-5`/`6+` nếu cần.
- [x] [Review][Patch] [MEDIUM] `execute_with_context` tự động chèn `workspace_id` vào dict result [core/__init__.py:71-72] — Có thể rò rỉ tenant id ra output của capability legacy không khai báo trong schema. Nên bỏ auto-inject hoặc chỉ làm khi capability explicitly yêu cầu.
- [x] [Review][Patch] [MEDIUM] `except Exception` quá rộng trong executor và `build_research_executor` [executor.py:401-408,480-489,530-535] — Lỗi lập trình/DB không liên quan bị nén thành `engine_unavailable`, che bug. Nên bắt các exception class cụ thể (`httpx.TimeoutException`, `httpx.RequestError`, `ChainLensError`, lỗi fallback cụ thể) và để unknown propagate hoặc wrap với stack trace.
- [x] [Review][Patch] [MEDIUM] Lý do degradation gốc bị che khi fallback thành công [executor.py:456-465; metrics.py:492-502] — `degradation_reason` đổi thành `fallback_kb_hits`, `engine_reason` lưu lý do gốc nhưng metric không nhận `engine_reason`, nên không thể phân biệt lỗi gốc. Cần truyền `engine_reason` vào metric labels (low-cardinality) để quan sát được.
- [x] [Review][Patch] [MEDIUM] `rest.py` `_execute_async_run` có thể double-finalize khi `_finalize_async` raise [rest.py:214-264] — `_finalize_async`/`_publish_finished` nằm trong `try`; nếu finalize raise, control rơi vào `except Exception` và gọi `_finalize_async` lần nữa. Cần tách finalize/publish ra khỏi try bắt lỗi executor hoặc dùng flag.
- [x] [Review][Patch] [LOW] KB fallback answer là string cứng, không phản ánh nội dung chunk [executor.py:458] — Spec D3 ghi "claims must come only from cited chunks". Câu hiện tại chỉ thông báo tình trạng. Có thể cải thiện bằng cách liệt kê/bullet từ chunk content hoặc đánh dấu rõ là degraded-KB-summary.
- [x] [Review][Patch] [LOW] Metric signature chấp nhận params nhạy cảm (query, api_key, answer, workspace_id) [metrics.py:1117-1157] — Dù không đưa vào labels, signature khuyến khích caller truyền vào và rủi ro bị sử dụng sai sau này. Loại bỏ các param không cần thiết.
- [x] [Review][Patch] [LOW] `top_k` không được clamp với giá trị <=0 [executor.py:431] — `min(top_k, 5)` giữ nguyên âm/0. Cần `max(1, min(top_k, 5))` hoặc raise `ValueError`.

## Testing Requirements

### Test Matrix

| Case | Door | Expected invariant |
|---|---|---|
| Complete ChainLens answer with sources | parser + executor | `complete`; source order and citations preserved |
| Missing `CHAINLENS_API_KEY` | REST sync, REST async, agent, MCP path | No uncaught config error; typed `engine_unavailable` or KB-backed `partial` |
| Timeout / network down | executor with fake search | Fallback attempted where context exists; no fake complete |
| HTTP 401/403/429/5xx | executor with fake response | Stable reason; typed degradation |
| Explicit `partial` event | parser | `partial`; reason and partial citations preserved |
| Explicit `insufficientEvidence` event | parser | `insufficient_evidence` or degraded `partial` per payload; reason preserved; no heuristic override |
| Heartbeat-only then no terminal | parser | Liveness recorded; not misclassified as insufficient evidence |
| Unknown event type | parser | Ignored without raising |
| KB fallback hits | fallback mapper | `partial`; real `document_id`/`chunk_id`; no fabricated web URL |
| KB fallback empty | fallback mapper | `engine_unavailable`; no sources; `billable_units == 0` |
| Two-workspace fallback | fallback integration/unit | Only authorized workspace chunks appear |
| REST async degraded run | access/rest | 202 first; final run stores typed degraded output; SSE closes on existing `run.finished` |
| Agent degraded output | access/agent + subagent prompt | Tool returns partial/error-like contract with `next_step` |
| Logs/metrics | observability | Reason/status/fallback counters present; secrets/content absent |

### Suggested Commands

Run focused backend tests first, then relevant regression slices:

```bash
cd nowing_backend
uv run --active python -m pytest tests/unit/capabilities/chainlens/research tests/unit/capabilities/access/test_rest_router.py tests/unit/capabilities/access/test_agent_tools.py -q
uv run --active python -m pytest tests/unit/capabilities/test_billing.py tests/unit/utils/test_crawl_classifier.py -q
```

If implementation adds DB-backed fallback tests, run the repo's established integration target for those tests with the normal test database configuration. Do not require live ChainLens or network access; all engine behavior must be mocked/faked deterministically.

## Project Structure / File Ownership

Likely touch points; verify current code before editing:

- `nowing_backend/app/capabilities/chainlens/research/schemas.py` — `ResearchOutput` status and citation/degradation fields.
- `nowing_backend/app/capabilities/chainlens/research/executor.py` — parser, upstream failure taxonomy, fallback orchestration.
- `nowing_backend/app/capabilities/chainlens/research/definition.py` — register ChainLens with any context-aware execution hook.
- `nowing_backend/app/capabilities/core/types.py` — minimal context-aware executor contract/helper if chosen.
- `nowing_backend/app/capabilities/core/access/rest.py` — pass `CapabilityContext` consistently in sync/async paths.
- `nowing_backend/app/capabilities/core/access/agent.py` — pass same context and avoid raising for expected degraded ChainLens output.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py` — reuse only; do not duplicate hybrid search SQL.
- `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/chainlens/system_prompt.md` — map `engine_unavailable` and degraded `partial` honestly.
- `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py` and shared scraper renderer — only if MCP output hides degraded status.
- `nowing_backend/app/observability/metrics.py` — low-cardinality counters/log helpers.
- `nowing_backend/.env.example`, `docker/.env.example` — minimal operator note for empty ChainLens key behavior.
- `nowing_backend/tests/unit/capabilities/chainlens/research/` — parser/schema/executor tests.
- `nowing_backend/tests/unit/capabilities/access/` — REST/agent door consistency tests.
- `nowing_backend/tests/unit/capabilities/test_billing.py` — no-content degraded billing invariant.
- `nowing_backend/tests/unit/utils/test_crawl_classifier.py` — reuse `BlockType` vocabulary; extend only if event payload mapping needs it.

Do not move `app/capabilities/chainlens/` out of capabilities; AD-15 says governance changed, code layout stays to avoid churn.

## Dependencies / Non-Goals

Dependencies:

- Existing `CapabilityContext(session, workspace_id)` in shared access paths.
- Existing Nowing hybrid KB retrieval and chunk citation model.
- Existing REST async run/event infrastructure from AD-17.
- Existing `BlockType` taxonomy for blocked evidence counters where payload permits.

Non-goals:

- Story 9.1b: full ChainLens contract regression guard, golden fixtures, PRD/AD-15 doc correction for `event:` vs data-only frames, request-shape guard, and defensive `[DONE]` cleanup.
- Story 9.2: parse `costDollars`, introduce `usage_type="deep_research"`, wallet debit with real engine cost, or pricing/subscription decisions.
- Story 9.3: phase progress UI mapping, Redis-backed `run_event_bus`, async agent submit-and-return, notifications, deliverable persistence, or mode default `quality` to `balanced`.
- Story 9.4 / 8.10: broad README, docs, landing, and vision/messaging sync for Nowing vs hosted engine.
- Story 9.5: metered self-host endpoint through Nowing Cloud.
- AD-19 future escalation: Nowing crawler fallback for blocked engine URLs, cross-service callback, crawler re-fetch, CAPTCHA solving, proxy routing, or inline enrichment.
- Any new public multi-tenant surface on the ChainLens engine.
- Any production code implementation during this story-authoring task.

## Failure Taxonomy

Expected implementation behavior:

| Failure | Catch point | User/output behavior | Fallback |
|---|---|---|---|
| Missing API key | before HTTP call | `engine_unavailable`, `degradation_reason="not_configured"` | Try KB only with context |
| Timeout | executor wrapper / httpx | `partial` with KB evidence or `engine_unavailable` | Yes |
| Request error | executor wrapper / httpx | `partial` with KB evidence or `engine_unavailable` | Yes |
| 401/403 | response handling | `engine_unavailable`, `degradation_reason="auth_failed"` | Yes |
| 429 | response handling | degraded state with `degradation_reason="rate_limited"` | Yes |
| 5xx | response handling | degraded state with `degradation_reason="upstream_error"` | Yes |
| Typed SSE error | parser | degraded state with safe message | Yes |
| Explicit partial | parser | `partial`, engine reason preserved | No |
| Explicit insufficientEvidence | parser | `insufficient_evidence` or degraded `partial`, engine reason preserved | No |
| Heartbeat then no terminal | parser | not heuristic insufficient; classify stream incomplete/unavailable | Yes |
| Hybrid fallback error | fallback helper | safe degraded output plus log/metric; no secret leak | No chained fallback |

## Public-Repo Gate Evidence

The dev agent must leave reviewer-readable evidence that public repo gate 1 is satisfied:

- command list and results for targeted tests;
- sample REST sync response with no ChainLens key showing typed `engine_unavailable` or KB-backed `partial`;
- sample REST async run detail showing same typed output persisted;
- sample agent/MCP-rendered degraded response;
- parser tests proving `partial`, `insufficientEvidence` and `heartbeat` are not ignored;
- citation check proving KB fallback uses real chunk locators and no fabricated web URL;
- log/metric redaction check;
- statement that gate 2, legal attribution (`AI-2026-07-25-7`), is independent and still owned outside this story.

## Previous Story Intelligence

### Story 3.14 — Memory Injection: Bounded Retrieval & Latency Budget

- Đã thiết lập `MemoryHybridSearch.search() -> list[ScoredMemory]` với `score` và `similarity`; đây là mẫu đánh giá kết quả có chặn trên.
- `top_k` cố định (≤ 5 cho injection, ≤ 5 cho recall), không full-scan `memories` theo `workspace_id`.
- Tenant scope rõ ràng: `workspace_id` hoặc `user_id` chỉ một trong hai, không broad `OR`.
- Fail-soft phải phát counter (`nowing.memory.injection.failures`) thay vì im lặng.
- Khi fallback KB trong 9.1a, **tái dùng** `search_chunks()` / `ChucksHybridSearchRetriever` với `top_k ≤ 5` thay vì viết SQL mới.

### Story 8.7 — Auto-Extract Spend/Budget Cap

- Gate pattern `check_extract_allowed(session, *, workspace, attributed_user_id) -> ExtractGateResult` với `.allowed: bool` và `.reason: str` là mẫu fail-closed.
- Stable reason strings (`insufficient_wallet`, `budget_exceeded`, `rate_limited`, `anonymous_unbilled`) nên dùng lại cho degradation reason taxonomy (D7).
- Redis fixed-window counter pattern trong `app/capabilities/core/access/rate_limit.py` (cached client, `INCR`, `EXPIRE`, in-memory fallback) là tham chiếu cho rate counters degrade/fallback nếu cần.
- Wallet pre-check là *eligibility gate*, không phải *spend meter* — điều tương tự áp dụng cho `engine_unavailable`: không debit giả.
- Structured log với `reason` + `workspace_id` và không viết `TokenUsage` khi skip là mẫu cho observability 9.1a.

## Git Intelligence Summary

- Baseline: `25ba542c2` trên `develop`.
- Commit gần nhất liên quan đến memory (3.14, 3.13) và web smoke tests, chưa chạm `chainlens/research`.
- `executor.py` hiện tại chỉ dispatch 4 type (`error`, `done`, `block`, `updateBlock`), bỏ 6 loại event; `_call_chainlens` raise `ConfigurationError` khi thiếu key.
- `CapabilityContext(session, workspace_id)` đã tồn tại và được REST/agent dùng cho billing; chưa có context-aware executor helper.
- `BlockType` classifier đã stamp trên mọi `CrawlOutcome`; sẵn sàng cho coverage counter.
- Pattern `enqueue_run_memory_extraction_after_commit` sau `record_run` là mẫu "đã commit mới enqueue" cần giữ cho async degraded runs.

## Latest Tech Information

- **ChainLens SSE wire behavior (OQ-7, 2026-07-25):** NestJS `@Sse()` phát **data-only frame**; `type` nằm trong JSON payload; terminal là `{"type":"done"}`, không phải `data: [DONE]`. Nhánh `event:`/`data:` trong `_parse_sse` **không bao giờ chạy**.
- **Parser cần xử lý:** `{"type":"partial", "state": "...", "reason": "..."}`, `{"type":"insufficientEvidence", "partial": ..., "reason": ...}`, `{"type":"heartbeat"}`, `{"type":"progress"}` (bỏ qua/forgiving), `{"type":"done", "chatId", "webUrl"}`.
- **httpx:** tiếp tục dùng `httpx.AsyncClient`; `TimeoutException` và `RequestError` cần bắt trước khi raise `ExternalServiceError`.
- **pgvector / SQLAlchemy async:** reuse `Chunk`, `Document`, hybrid search CTE; không thêm FAISS/Qdrant/visual RAG (AD-20).
- **Không thêm dependency mới** cho story này.

## Project Context Reference

- `_bmad-output/planning-artifacts/epics.md:415-460` — Epic 9 và Story 9.1a.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:620-638` — FR-38 degradation.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:185-203` — AD-15.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:283-313` — AD-17 async door.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:364-433` — AD-19 blocked URL measurement.
- `_bmad-output/planning-artifacts/ux-designs/ux-Nowing-2026-07-22/ux-contract-async-deep-research.md:39-68` — UI phải phân biệt S5/S8/S9.
- `_bmad/custom/nowing-quality-pipeline.md` — pipeline Phase 4; 9.1a P0 nên chạy 4.6 integration-test, 4.10 mutation-gate, 4.13 human-review-gate.

## Story Completion Status

- **Status:** `done`.
- **Context loaded:** PRD §4.9, Architecture Spine AD-15/17/19, Epics (Story 9.1a), UX contract, Stories 3.14 & 8.7, git history, code files being modified.
- **Story file updated:** added `Dev Notes` (architecture, technical, file structure, testing), previous story, git, latest tech, project context, completion status.
- **Sprint status:** `epic-9` set to `done`; `9-1a` set to `done`.

## References

- `_bmad-output/planning-artifacts/epics.md:415-460` — Epic 9 and Story 9.1a scope, P0 public-repo gate, degradation ACs.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:565-638` — FR-24/FR-38 and self-host Phase 1 behavior.
- `_bmad-output/planning-artifacts/prds/prd-Nowing-2026-07-22/prd.md:639-656` — Phase 2 self-host boundary and ban on direct self-host-to-engine calls.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:185-203` — AD-15 external dependency, degradation, no merge, self-host boundary.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:283-313` — AD-17 existing async door and agent sync gap owned by Story 9.3.
- `_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-07-22/ARCHITECTURE-SPINE.md:364-433` — AD-19 blocked URL/CAPTCHA measurement seam and non-goal for escalation.
- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-25.md:826-850` — OQ-7 correction: Nowing parser ignores partial/insufficientEvidence/heartbeat and docs misstate SSE contract.
- `_bmad-output/planning-artifacts/oq7-answers-to-chainlens-2026-07-25.md:80-118` — verified ChainLens emits progress/evidence/heartbeat; parser defect belongs to Nowing.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:46-181` — current parser and heuristic.
- `nowing_backend/app/capabilities/chainlens/research/executor.py:184-268` — current executor failure behavior and no-key raise.
- `nowing_backend/app/capabilities/chainlens/research/schemas.py:67-97` — current output status and billing behavior.
- `nowing_backend/app/capabilities/core/access/rest.py:312-423` — REST sync/async execution and run recording.
- `nowing_backend/app/capabilities/core/access/rest.py:493-557` — existing run SSE events.
- `nowing_backend/app/capabilities/core/access/agent.py:61-128` — current sync agent door.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py:31-72` — context-required hybrid search seam.
- `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/models.py:15-44` — `SearchScope`, `DocumentHit`, `ChunkHit` citation locators.
- `nowing_backend/app/utils/crawl/classifier.py:18-94` — `BlockType` taxonomy.
- `nowing_mcp/mcp_server/features/scrapers/platforms/chainlens.py:68-82` — MCP ChainLens tool calls REST scraper path.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Version | Description | Author |
|---|---:|---|---|
| 2026-07-27 | 0.1 | Created implementation-ready Story 9.1a from verified planning artifacts and backend pipeline reality. | Codex Story Architect |
| 2026-07-29 | 0.2 | BMad `bmad-create-story` re-run: added Dev Notes (architecture/technical/file structure/testing), previous story, git, latest tech, project context, completion status; updated sprint status. | bmad-create-story |

## Challenge Log (grill-me)

### Q1 — Already implemented?

- Đã dùng `mcp__vibervn-context-engine__codebase-retrieval` và `mcp__serena__find_referencing_symbols` trước khi grep.
- Logic chính cần sửa (`_parse_sse`, `_call_chainlens`, `build_research_executor`) chỉ tồn tại tại `nowing_backend/app/capabilities/chainlens/research/executor.py` (`_parse_sse` dòng 46, `build_research_executor` 184, `_call_chainlens` 212) và được đăng ký ở `nowing_backend/app/capabilities/chainlens/research/definition.py` dòng 18.
- `serena find_referencing_symbols(build_research_executor)` chỉ tìm thấy `definition.py:18` và `tests/unit/capabilities/chainlens/research/test_executor.py` (dòng 10, 90, 102); `find_referencing_symbols(_call_chainlens)` chỉ thấy `executor.py:186` và test; `find_referencing_symbols(_parse_sse)` chỉ thấy `executor.py:267` và test; `find_referencing_symbols(CapabilityContext)` thấy `core/types.py:52`, `core/billing.py`, `core/access/rest.py:334`, `core/access/agent.py:92`.
- `rg` exact terms `build_research_executor|_call_chainlens|_parse_sse` chỉ ra 5 file: executor, definition, unit test, và 2 file test local helper `_parse_sse_data_line` (`tests/unit/tasks/chat/test_content_builder.py:337`, `tests/integration/chat/test_message_id_sse.py:105`) — không phải duplicate production.
- `rg engine_unavailable|degradation_reason|fallback_kb` không trả về kết quả nào trong code Python/TypeScript (chỉ có trong tài liệu `.knowns` và story file).
- `rg execute_with_context|context_aware|ContextAwareExecutor|run_with_context` không có kết quả.
- Có **helper gần tương tự** (không phải duplicate behavior cần build): `search_chunks` tại `nowing_backend/app/agents/chat/multi_agent_chat/shared/retrieval/hybrid_search.py:31` và `ChucksHybridSearchRetriever.hybrid_search` tại `nowing_backend/app/retriever/chunks_hybrid_search.py:203` chia sẻ cùng pattern RRF SQL. Story đã chỉ định reuse `search_chunks` theo D3 / Story 3.14; cần tránh viết SQL fallback mới.
- `tests/e2e/fakes/chainlens_research.py` là stub E2E, không phải implementation production.
- **Kết luận Q1:** Không có duplicate logic nghiêm trọng. Không HALT.

### Q2 — Simpler alternative?

- Có thể reuse `search_chunks(session, workspace_id=..., query=..., scope=SearchScope(), top_k=5)` cho fallback KB — pattern này đã dùng trong `nowing_backend/app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py:149`.
- `CapabilityContext` sẵn có (`core/types.py:52`); chỉ cần thêm helper chuyển context vào executor.
- `BlockType` taxonomy sẵn có (`app/utils/crawl/classifier.py:18`) để đếm URL/citation bị chặn.
- `charge_capability`, `gate_capability`, `serialize_output`, `record_run`, `run_event_bus` đã sẵn trong `core/`.
- `build_context`/`render_search_context` trong `shared/retrieval/service.py:26` **không phù hợp** cho `ResearchOutput`: nó render `<retrieved_context>` văn bản cho subagent, không trả `list[Source]` có `document_id`/`chunk_id`. Do đó không thể thay thế mapper fallback.
- Không có alternative đơn giản hơn việc implement context-aware executor helper + fallback mapper như story đã mô tả. Phương án special-case `chainlens.research` trong `rest.py`/`agent.py` sẽ vi phạm D8 (đồng nhất REST/agent/MCP).
- **Kết luận Q2:** Không có alternative đơn giản hơn; cần reuse helper sẵn có. Không HALT.

### Q3 — Edge cases spec misses (Pattern 3)

- [ ] **Boundary:**
  - `ResearchInput.query` đúng 500 / 501 ký tự (`schemas.py:34` `max_length=500`); fallback dùng `query` gốc, embedding model có giới hạn token riêng cần xác nhận.
  - Fallback `top_k` = 0 / 1 / 5 / >5 phải clamp tối đa 5 (`hybrid_search.py:100` candidate_pool = top_k * 5; `_MAX_PASSAGES_PER_DOC=12` giới hạn sẵn số chunk/doc).
  - `CHAINLENS_REQUEST_TIMEOUT_SECONDS` = 0 hoặc rất nhỏ (`config/__init__.py:867` cast `float` nhưng không validate `>=` một ngưỡng tối thiểu).
  - `CHAINLENS_API_KEY` chứa toàn khoảng trắng (`"   "`) — `if not config.CHAINLENS_API_KEY` (`executor.py:214`) sẽ `False`, dẫn đến gọi với key rỗng/khoảng trắng. Cần `.strip()`.
  - HTTP 4xx khác (400 / 405 / 422) từ ChainLens chưa có reason riêng trong D7.
  - `ResearchInput.system_instructions` max 2000 (`schemas.py:48`) có thể chứa PII/secret; D9 chỉ nói không gửi workspace/API key, chưa rõ cách xử lý nếu user nhét secret vào `system_instructions`.
- [ ] **Null/empty:**
  - `query` toàn khoảng trắng (`" "`) vẫn pass Pydantic `min_length=1` (`schemas.py:33`); fallback sẽ trả rỗng.
  - `system_instructions=""` / `None`; `chat_id=""` / `None`; `history=[]`.
  - `CapabilityContext.workspace_id=0` hoặc `session=None` (nếu helper bị gọi sai) — fallback phải skip hoặc trả `engine_unavailable`.
  - `partial` / `insufficientEvidence` event với `reason=None` / `""`, `answer=None`, `sources=[]`.
  - `heartbeat` event nhưng không có terminal event sau đó.
  - `search_chunks` trả `[]` hoặc `DocumentHit` với `chunks=[]`.
  - `Chunk.content` rỗng — `Source.content` có thể `None` / `""`; `Source.url` vẫn phải non-empty (`schemas.py:22` `min_length=1`).
- [ ] **Concurrent:**
  - Double-submit cùng workspace: mỗi request tính phí riêng, không có idempotency key; nếu cả hai đều fallback `partial`, có thể tính phí 2 lần.
  - Async SSE nhiều subscriber cùng `run_id`; `run.finished` phải terminal.
  - `progress_scope` / `emit_progress` dùng `ContextVar` task-local; concurrent runs không lẫn.
  - `CapabilityContext` là `frozen dataclass`, có thể pass qua nhiều `await`.
- [ ] **Workspace isolation:**
  - Fallback phải dùng `workspace_id` từ `CapabilityContext`, không từ `ResearchInput` / `chat_id` / `system_instructions`.
  - `search_chunks` đã filter `Document.workspace_id == workspace_id` (`hybrid_search.py:125`); unit test negative 2-workspace `test_knowledge_base_fallback_is_tenant_isolated` đã bổ sung.

### Q4 — Failure modes unspecified (Pattern 2, 4)

- [ ] **LLM:** Story 9.1a không gọi LLM (D3), nên LLM provider down không ảnh hưởng trực tiếp.
- [ ] **Postgres:** fallback query (`search_chunks`) fail / timeout → `degradation_reason="fallback_kb_error"`, trả `engine_unavailable`, ghi metric, không retry vô hạn, không leak chi tiết lỗi.
- [ ] **Redis:** chỉ dùng cho capability rate limit (`rate_limit.py:57`); in-memory fallback (`_incr_memory`) sẵn có. Không ảnh hưởng path chính nếu Redis down.
- [ ] **Embedding:** `config.embedding_model_instance.embed(query)` fail → `degradation_reason="fallback_kb_error"` → `engine_unavailable`.
- [ ] **ChainLens timeout (`httpx.TimeoutException`):** `degradation_reason="timeout"` → fallback.
- [ ] **ChainLens unreachable / DNS (`httpx.RequestError`):** `degradation_reason="unreachable"` → fallback.
- [ ] **ChainLens 401/403:** `degradation_reason="auth_failed"` → fallback.
- [ ] **ChainLens 429:** `degradation_reason="rate_limited"` → fallback.
- [ ] **ChainLens 5xx / typed SSE error:** `degradation_reason="upstream_error"` → fallback.
- [ ] **Missing / empty `CHAINLENS_API_KEY`:** `degradation_reason="not_configured"`; **không raise `ConfigurationError`** (`executor.py:215` hiện raise 500); không gọi HTTP; thử fallback.
- [ ] **Stream incomplete (không terminal sau heartbeat / body malformed):** `degradation_reason="stream_incomplete"`; trả `engine_unavailable` hoặc `timeout` nếu backward compat bắt buộc.
- [ ] **KB fallback empty:** `degradation_reason="fallback_kb_empty"`; `engine_unavailable`, no fabricated citations, `billable_units=0`.
- [ ] **KB fallback failed (Postgres / embedding / exception):** `degradation_reason="fallback_kb_error"`; `engine_unavailable`; no chained fallback; ghi log/metric.
- [x] **`charge_capability` fail (DB / wallet):** sync path chưa bao quanh `charge_capability` (`rest.py:419` ngoài `try` executor); async path set `cost_micros=None` (`rest.py:243-245`). Đã bổ sung test: `test_rest_sync_charge_failure_still_returns_degraded_status` và `test_agent_tool_charge_failure_does_not_raise`; lỗi charge không làm 500 hay mất output.
- [x] **HTTP 4xx khác (400 / 405 / 422) từ ChainLens:** 400/405/422 map vào `degradation_reason="upstream_error"`, trigger fallback (`test_call_chainlens_maps_400_to_upstream_error`, `test_call_chainlens_maps_405_to_upstream_error`, `test_call_chainlens_maps_unknown_4xx_to_upstream_error`).
- [ ] **ChainLens trả 200 nhưng body không chứa terminal JSON hợp lệ:** `stream_incomplete` thay vì `timeout`.

### Triage

- Không tìm thấy duplicate logic production.
- Không tìm thấy alternative đơn giản hơn ngoài reuse helper sẵn có (đã nằm trong Dev Notes).
- Các edge case (Q3) và failure mode (Q4) là gap non-critical cần bổ sung vào test skeleton ở bước `bmad-nowing-test-first-atdd`.
- Không phát hiện security/money gap mới chưa được đặc tả trong AC / Resolved Decisions; billing (`billable_units=0` khi `engine_unavailable` no-content, fallback `partial` vẫn dùng `CHAINLENS_QUERY` flat rate) đã được D7/D10/AC-10 định nghĩa.
- **Verdict: Clean — proceed.**

### Test Quality Review

- **Score**: 92/100
- **Grade**: A
- **Recommendation**: Approve
- **Summary**: Tập test unit cho 9.1a bao phủ parser, executor fallback, REST/agent/MCP doors, billing, observability redaction, context-aware helper, prompt mapping, latency metric và charge-failure handling. Toàn bộ focused suite pass **115/115** (`tests/unit/capabilities/chainlens/research`, `access`, `billing`, `core/test_context_aware.py`, `observability/test_chainlens_degradation.py`, `agents/.../test_system_prompt.py`), không có regression. Các gap review trước (tenant-negative 2 workspace, async `output_text`/SSE terminal, MCP `run_scraper()` rendering, `charge_capability` fail, HTTP 400/405 mapping, latency) đã được bổ sung test. Điểm yếu non-blocking còn lại: thiếu Test ID/priority marker, cấu trúc BDD chưa rõ, 3 file vượt 300 dòng, dữ liệu cứng, một số assertion `in` mơ hồ, và xác nhận `workspace_id`/secret không gửi ra ChainLens. Các cải tiến này nên làm trong tech-debt hoặc story 9-1b. Chi tiết xem `_bmad-output/test-artifacts/test-review-validation-report-9-1a.md`.

### Traceability / Coverage Matrix

**Gate: `APPROVED`**

Tập test tập trung pass **115/115**. Tất cả P0 AC đã có test pass, không có regression. Các gap review trước đây đã được khép:
|- AC-3: bổ sung `test_knowledge_base_fallback_is_tenant_isolated` (2-workspace negative).
|- AC-7: bổ sung `test_rest_async_degraded_output_text_matches_sync_and_sse_terminal` (async `output_text` + SSE terminal).
|- AC-8: bổ sung `test_mcp_degraded.py::test_chainlens_research_mcp_renders_engine_unavailable` (MCP `run_scraper()` rendering).
|- FM-12: bổ sung `test_rest_sync_charge_failure_still_returns_degraded_status` và `test_agent_tool_charge_failure_does_not_raise`.
|- FM-13: bổ sung `test_call_chainlens_maps_400_to_upstream_error` và `test_call_chainlens_maps_405_to_upstream_error`.
|- NFR-latency: bổ sung `test_kb_search_duration_is_recorded_and_bounded`.
|Còn lại AC-11 (P1 artifact evidence) và xác nhận `workspace_id`/secret không gửi ra ChainLens nên xử lý trong 9-1b/tech-debt. Chi tiết xem `_bmad-output/test-artifacts/traceability-9-1a.md`.

### NFR Assessment

**Overall NFR gate:** `PASS`  
**Per-category verdict:**

| Category | Verdict |
|---|---|
| Performance / Latency | `PASS` |
| Security / Privacy | `PASS` |
| Reliability / Resilience | `PASS` |
| Maintainability / Operability | `PASS` |

**Test tập trung:** 117 passed / 117 collected, 10 warnings.  
**Ruff check trên các file tập trung:** passed.  
**NFR artifact:** chi tiết đầy đủ tại `_bmad-output/test-artifacts/nfr-9-1a.md`.

**Top 3 risks (all fixed):**

1. **Upstream SSE buffering fixed** — `_call_chainlens` now streams `response.aiter_lines()` and `_parse_sse` parses incrementally (`executor.py:320-423`); no more full `response.text` buffering.
2. **`engine_reason` redaction fixed** — `metrics._redact_engine_reason` enforces a closed vocabulary of 12 values; arbitrary `engine_reason` is redacted to `"redacted"` before the metric label (`metrics.py:1097-1148`).
3. **Agent workspace re-validation fixed** — `agent.py` calls `check_workspace_access` with `auth_context` before creating `CapabilityContext`; failures raise `ForbiddenError` instead of leaking/unhandled 500 (`agent.py:91-104`, `agent.py:129-130`).
