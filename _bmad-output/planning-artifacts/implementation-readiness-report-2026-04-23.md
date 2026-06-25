---
date: 2026-04-23
project: Nowing
scope: Crypto Orchestra Initiative (Epic 0 + Epic 9)
stepsCompleted:
  - step-01-document-discovery.md
  - step-02-prd-analysis.md
  - step-03-epic-coverage-validation.md
  - step-04-ux-alignment.md
  - step-05-epic-quality-review.md
  - step-06-final-assessment.md
overallStatus: "🟡 NEEDS WORK — Conditional GO (Epic 0 ready; fix 2 critical + 2 major before Phase 1 Backend Week 2)"
issuesFound:
  critical: 2
  major: 2
  minor: 5
filesIncluded:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/ux-crypto-orchestra-handoff.md
  - _bmad-output/planning-artifacts/stories/0-1-crypto-tool-infrastructure.md
  - _bmad-output/planning-artifacts/stories/0-2-base-sub-agents.md
  - _bmad-output/planning-artifacts/stories/0-3-main-agent-prompt.md
  - _bmad-output/planning-artifacts/stories/0-4-api-integration-tests.md
  - _bmad-output/planning-artifacts/stories/0-5-parallel-execution-validation.md
  - _bmad-output/planning-artifacts/stories/0-6-error-handling-fallback.md
  - _bmad-output/planning-artifacts/stories/9-1-tokenomics-analyst.md
  - _bmad-output/planning-artifacts/stories/9-2-whale-tracker.md
  - _bmad-output/planning-artifacts/stories/9-3-token-unlock-scheduler.md
  - _bmad-output/planning-artifacts/stories/9-4-yield-optimizer.md
  - _bmad-output/planning-artifacts/stories/9-5-governance-analyst.md
  - _bmad-output/planning-artifacts/stories/9-6-technical-analyst.md
  - _bmad-output/planning-artifacts/sprints/sprint-plan-phase1-crypto-orchestra.md
  - _bmad-output/planning-artifacts/sprints/sprint-plan-phase2-crypto-orchestra.md
  - _bmad-output/planning-artifacts/sprints/sprint-plan-phase3-crypto-orchestra.md
  - _bmad-output/implementation-artifacts/sprint-status.yaml
knownGapFlags:
  - "Stories 9-1..9-6 thiếu explicit frontend AC — UX đề xuất Story 9-FE-1"
  - "5 open design questions từ UX §7 đã resolved bởi Architect §9 — chưa back-propagate vào UX spec"
  - "Architecture Phase 0 sequence ↔ Stories 0.1-0.6 timeline alignment"
---

# Implementation Readiness Assessment Report

**Date:** 2026-04-23
**Project:** Nowing — Crypto Orchestra Initiative
**Scope:** Epic 0 (Crypto Foundation) + Epic 9 (Crypto Orchestra)
**Assessor Role:** Expert PM — Requirements Traceability

---

## Step 1: Document Inventory

### Core Artifacts (confirmed)
| Type | File | Status |
|---|---|---|
| PRD | `prd.md` | ✅ Used |
| Architecture | `architecture.md` | ✅ Used (§9 Crypto Orchestra) |
| Epics | `epics.md` | ✅ Primary — Epic 0 + Epic 9 |
| UX Spec | `ux-design-specification.md` | ✅ Used (§7 Crypto Orchestra) |
| UX Handoff | `ux-crypto-orchestra-handoff.md` | ✅ Used |
| Stories Epic 0 | `stories/0-1..0-6-*.md` | ✅ 6 files |
| Stories Epic 9 | `stories/9-1..9-6-*.md` | ✅ 6 files |
| Sprint Plans | `sprints/sprint-plan-phase{1,2,3}-crypto-orchestra.md` | ✅ 3 files |
| Sprint Status | `implementation-artifacts/sprint-status.yaml` | ✅ Used |

### Out-of-scope / Flagged Duplicates
- `crypto-subagents-epics.md` — tiền thân của Epic 0/9 trong `epics.md`. KHÔNG dùng để assessment.
- `HANDOFF-crypto-orchestra.md` vs `ux-crypto-orchestra-handoff.md` — xác nhận dùng `ux-crypto-orchestra-handoff.md` (UX handoff chính thức).
- `implementation-readiness-report-2026-04-13.md` — báo cáo trước (10 ngày trước), chỉ tham chiếu khi cần so sánh delta.


---

## Step 2: PRD Analysis

### In-scope Functional Requirements (Crypto Orchestra)

| ID | Title | Summary |
|---|---|---|
| FR27 | Tokenomics Analyst | Sub-agent phân tích supply/vesting/distribution. Tools: `get_coingecko_token_info`, `chainlens_deep_research`. System prompt < 500 tokens. |
| FR28 | Whale Tracker | Large wallet movements, smart money flows. Tools: `chainlens_deep_research` (Arkham, Nansen, Etherscan). |
| FR29 | Token Unlock Scheduler | Vesting events, historical post-unlock price action, sell pressure. Tools: `chainlens_deep_research`. |
| FR30 | Yield Optimizer | Risk-adjusted DeFi yields, IL calc. Tools: `get_defillama_yields`, `get_defillama_protocol`, `check_token_security`. |
| FR31 | Governance Analyst | DAO proposals, voting outcomes, treasury health. Tools: `chainlens_deep_research`. |
| FR32 | Technical Analyst | Chart patterns, MA/RSI/MACD. Tools: `get_live_token_data`, `chainlens_deep_research`. |
| FR33 | Parallel Orchestration | Main agent spawn nhiều sub-agents song song qua `task()` trong 1 LangGraph ToolNode. |
| FR34 | Smart Agent Selection | Main agent prompt chọn subset agents phù hợp câu hỏi, không spawn full 10. |
| FR35 | Graceful Degradation | 1-2 agents fail → response vẫn đúng cấu trúc, mention source unavailable. |

**Total in-scope FRs:** 9 (FR27-FR35)

**Dependency FRs (upstream Epic 1-2/7):** FR24-FR26 (Chainlens Deep Research — pre-condition cho FR28/29/31/32 và supplementary FR27).

### In-scope Non-Functional Requirements

**Performance / Speed:**
- **NFR-P4** — Deep research timeout ≤ 120s (Chainlens path) — áp dụng cho 5/6 agents reuse `chainlens_deep_research`.
- **NFR-Q4** — P95 response time full-suite (6+ agents) < 90s.

**Crypto Orchestra-specific (NFR-CS):**
- **NFR-CS1** — Sub-agent system prompt < 500 tokens; tổng overhead khi spawn full suite < 5000 tokens.
- **NFR-CS2** — Parallel execution ratio `total_time / max(individual_time)` < 1.3x.
- **NFR-CS3** — API rate awareness: CoinGecko 30 req/min, GoPlus 2000 req/day, CryptoPanic public, DeFiLlama unlimited. Fallback sang `chainlens_deep_research`.
- **NFR-CS4** — Stateless tools: `requires=[]` trong tool registry, không DB/session/workspace context.

**Quality Gates (Epic 9 North Star):**
- **NFR-Q1** — Accuracy: factual error rate < 3% (sample QA 100 queries mỗi 2 tuần).
- **NFR-Q2** — Hallucination rate (fabricated numbers) < 1%.
- **NFR-Q3** — Graceful degradation success rate > 98%.
- **NFR-Q4** — (đã nêu trên) P95 < 90s.

**Total in-scope NFRs:** 10 (P4, CS1-4, Q1-4 cộng NFR-Q4 overlap).

### Additional Requirements

- **User Journey #8** (Crypto Power User — Khoa) đóng vai trò acceptance narrative: user hỏi "Phân tích toàn diện $UNI 6 tháng" → main agent spawn 6+ specialists song song → response < 90s P95 → graceful degradation khi 1-2 agents fail.
- **Integration Requirement (cross-ref):** Chainlens B2B API (đã có trong Epic 7) là hard dependency cho FR28, FR29, FR31, FR32. FR27 và supplementary lookups cũng dùng chainlens.
- **Epic 0 Prerequisite (audit 2026-04-23):** 4 base sub-agents + 11 tool files chưa tồn tại, cần Phase 0 implement trước Epic 9 Phase 1. Realistic timeline ~7-8 weeks thay vì 4 weeks standalone.
- **Phased rollout:** Phase 1 Tokenomics+Yield → Phase 2 Whale+Governance → Phase 3 Unlock+TA.

### PRD Completeness Assessment (initial)

🟢 **Strong points:**
- Numbered FRs rõ ràng, có phân loại theo agent.
- NFR-Q1..Q4 có metric cụ thể + phương pháp đo.
- User Journey #8 kể được end-to-end flow với pass/fail criteria (P95 < 90s, graceful degradation > 98%).
- Prerequisite note (Epic 0) đã được add vào Growth Features sau audit 2026-04-23.

🟡 **Attention points:**
- FR27-FR32 liệt kê tools scoped nhưng KHÔNG spec rõ error format khi tool fail (để FR35 xử lý) — cần đảm bảo sub-agent spec có convention chung.
- NFR-P4 (120s Chainlens timeout) vs NFR-Q4 (P95 < 90s full-suite): nếu 1 chainlens call mất 120s thì không thể đạt < 90s P95 cho full-suite — cần xác nhận 90s là budget tổng bao gồm tail calls (relax khi degraded).
- FR34 "Smart Agent Selection" — PRD mô tả concept nhưng chưa specify deterministic selection rule (để main agent prompt tự quyết, hoặc dùng keyword lookup table).
- FR27 "system prompt < 500 tokens" — lặp lại trong NFR-CS1, OK. Nhưng FR27 viết riêng, cần đảm bảo các FR khác (FR28-32) đều tuân NFR-CS1.

🔴 **Gaps (to validate in next steps):**
- Không có FR riêng cho **Frontend UX** của Crypto Orchestra trong PRD (streaming indicator, agent progress, source-unavailable badge). → khả năng xác nhận Known Gap #1.

---

## Step 3: Epic Coverage Validation

### Coverage Matrix — In-scope FRs

| FR | PRD Requirement | Epic / Story Coverage | Status | Notes |
|---|---|---|---|---|
| FR27 | Tokenomics Analyst | Epic 9 / Story 9.1 | 🟢 Covered | AC khớp với PRD spec |
| FR28 | Whale Tracker | Epic 9 / Story 9.2 | 🟡 Covered (drift) | Story dùng `web_search`, PRD nói `chainlens_deep_research` |
| FR29 | Token Unlock Scheduler | Epic 9 / Story 9.3 | 🟡 Covered (drift) | Cùng vấn đề `web_search` vs `chainlens_deep_research` + đánh dấu **needs spike** |
| FR30 | Yield Optimizer | Epic 9 / Story 9.4 | 🟢 Covered | Tool list khớp |
| FR31 | Governance Analyst | Epic 9 / Story 9.5 | 🟡 Covered (drift) | `web_search` thay cho `chainlens_deep_research` |
| FR32 | Technical Analyst | Epic 9 / Story 9.6 | 🟡 Covered (drift) | `web_search` thay cho `chainlens_deep_research` + **needs spike** |
| FR33 | Parallel Orchestration | Epic 0 / Story 0.2, 0.5 | 🟢 Covered | Validation criteria rõ |
| FR34 | Smart Agent Selection | Epic 0 / Story 0.3 | 🟢 Covered | Lookup table + ví dụ parallel calls |
| FR35 | Graceful Degradation | Epic 0 / Story 0.6 | 🟢 Covered | Acceptance > 98% rate gate |

### Coverage Matrix — In-scope NFRs

| NFR | Required by | Validated in | Status |
|---|---|---|---|
| NFR-P4 (120s deep research timeout) | FR28-32 (chainlens path) | _Inherited from Epic 7 Story 7.2_ — KHÔNG re-validate trong Epic 0/9 | 🟡 Implicit |
| NFR-CS1 (prompt < 500 tokens) | All sub-agents | Story 0.2 unit test (`tiktoken`); 9.1-9.6 Common AC | 🟢 Covered |
| NFR-CS2 (parallel < 1.3x) | FR33 | Story 0.2, 0.5 (trace logs ratio) | 🟢 Covered |
| NFR-CS3 (API rate awareness) | All tools | Story 0.1 (handle rate limit gracefully); Story 0.6 (CoinGecko 429 fallback) | 🟢 Covered |
| NFR-CS4 (stateless tools, `requires=[]`) | All tools | Story 0.1 AC; 9.1-9.6 Common AC | 🟢 Covered |
| NFR-Q1 (accuracy < 3%) | Epic 9 launch gate | Story 0.5 metric + 9.1-9.6 Common AC (sample 100 queries / 2 weeks) | 🟢 Covered |
| NFR-Q2 (hallucination < 1%) | Epic 9 launch gate | 9.1-9.6 Common AC (pattern check + sample QA) | 🟢 Covered |
| NFR-Q3 (graceful degrad. > 98%) | Epic 9 launch gate | Story 0.6 telemetry weekly | 🟢 Covered |
| NFR-Q4 (P95 < 90s full-suite) | Epic 9 launch gate | Story 0.5 (P95 measurement + dashboard) | 🟢 Covered |

### Coverage Statistics
- **Total in-scope FRs:** 9 (FR27-FR35)
- **FRs covered in epics/stories:** 9
- **Coverage percentage:** 100%
- **FRs with drift (tool spec mismatch):** 4 (FR28, FR29, FR31, FR32)
- **Total in-scope NFRs:** 9 unique (CS1-4 + Q1-4 + P4)
- **NFRs covered:** 8/9 (NFR-P4 chỉ implicit từ Epic 7)

### 🔴 Gap: Frontend AC missing trong Epic 9
- **Stories 9.1-9.6 hoàn toàn backend-focused.** Common AC chỉ nói về prompt size, accuracy, hallucination, source citation.
- **KHÔNG có AC nào cho frontend** liên quan đến: orchestra mode indicator, sub-agent progress streaming, source-unavailable badge, token-budget hint UI.
- Đây chính là Known Gap #1 user đã flag — **CONFIRMED**.
- UX Spec (xem Step 4) có thể đã propose Story 9-FE-1 nhưng chưa được wire vào `epics.md`.

### 🟡 Coverage Drift: tool spec mismatch
- **PRD FR28-32** liệt kê tool `chainlens_deep_research` (reuse Epic 7) cho Whale, Unlock, Governance, TA.
- **Epics.md Story 9.2-9.6** lại ghi `web_search` (raw web search tool).
- Hai tool này có overlap (cả hai search web) nhưng có ý nghĩa khác:
  - `chainlens_deep_research` = paid B2B API, có timeout 120s, cache, fallback logic.
  - `web_search` = generic Tavily/built-in tool.
- Drift này có thể do epics.md viết trước khi Epic 7 được decide làm engine chính. Cần align lại.

### 🟢 Strong coverage
- Epic 0 retroactive bundle là tốt — bao gồm cả tool infrastructure, base sub-agents, prompt update, **và** integration testing (0.4-0.6).
- NFR-Q1-Q4 north-star metrics có **launch gate** rõ ràng (rollback nếu fail).
- Story 0.5 yêu cầu telemetry dashboard realtime cho ops — đây là NFR enforcement đúng cách.

---

## Step 4: UX Alignment

### UX Document Status
✅ **Found:** `ux-design-specification.md` §"Crypto Orchestra UX" + `ux-crypto-orchestra-handoff.md` (dev brief).

### UX ↔ PRD Alignment

| PRD item | UX coverage | Status |
|---|---|---|
| Journey #8 "Khoa — Full $UNI analysis" | UX §7 "Interaction Flow Mapping (Journey 8 — Full sequence)" | 🟢 Aligned |
| FR33 Parallel orchestration | Orchestra Conductor Strip + AgentRow (UX §2) | 🟢 Aligned |
| FR35 Graceful degradation | `<DegradationNotice />` (UX §3) + "source-unavailable" badge | 🟢 Aligned |
| NFR-Q4 P95 < 90s | "Long-Running Progress Feedback" (UX §5) — bridging 90-second gap | 🟢 Aligned |
| FR28/29/31/32 multi-source citations | "Stacked Provenance Badges" (UX §4) — cross-agent citation | 🟢 Extends PRD |

### UX ↔ Architecture Alignment

| UX Need | Architecture coverage | Status |
|---|---|---|
| Per-agent SSE event spec (6 events) | `architecture.md` §1 + `app/schemas/sse_events.py` (decision documented) | 🟢 Defined |
| Throttle `orchestra.update` | §1 decision #2 — server-side 1 update/agent/500ms via `ParallelismTelemetryMiddleware` | 🟢 Defined |
| Agent retry semantics | §7 Q2 — query-level only v1 | 🟢 Resolved |
| Cancel cost accounting | §7 Q3 — best-effort terminate, tokens billed | 🟢 Resolved |
| Conflict threshold (`[2≠4]`) | §7 Q4 — FE detect, delta > 5% | 🟢 Resolved |
| i18n agent names | §7 Q1 — EN-only v1 | 🟢 Resolved |
| Cross-tab background mode | §7 Q5 — single-tab MVP | 🟢 Resolved |
| `orchestra_sessions` Rocicorp Zero table | Architecture §8 references FE schema; backend có orchestra_sessions? | 🟡 Partial — backend §11 nói "KHÔNG đổi DB schema", implying FE-only Rocicorp Zero table |

### Open Design Questions from UX §7 → Architect Resolution

All 5 questions from UX handoff §7 đã được **resolved** trong architecture.md §9 (Decision table §7):

| # | UX Question | Architect Decision | Back-propagated vào UX spec? |
|---|---|---|---|
| Q1 | i18n agent names | EN-only v1 | 🔴 **NO** — UX spec vẫn list as "open" |
| Q2 | Retry agent vs query | Query-level v1 | 🔴 **NO** |
| Q3 | Cancel cost | Best-effort, tokens billed | 🔴 **NO** |
| Q4 | Conflict threshold | 5% delta, FE-detect | 🔴 **NO** (UX đề xuất 5% được chấp thuận) |
| Q5 | Cross-tab | Single-tab MVP | 🔴 **NO** |

**Verdict: Known Gap #2 CONFIRMED.** 5 resolutions từ Architect §9/§7 không được back-propagate vào `ux-design-specification.md` hoặc `ux-crypto-orchestra-handoff.md` §7 (vẫn đang list là "Open Design Questions").

### Alignment Issues

🔴 **Critical:**
1. **Story 9-FE-1 missing from `epics.md`** — UX handoff (§5) đề xuất `9-FE-1: Orchestra Conductor Strip + Citation Stacking` nhưng `epics.md` Epic 9 KHÔNG có story này, cũng không có bất kỳ FE story nào cho Epic 9.
2. **UX §7 Open Questions chưa back-propagated** — UX spec vẫn mang dấu "Open Design Questions" trong khi Architect §9/§7 đã resolve 5/5. Dev reading UX sẽ tưởng còn pending.

🟡 **Minor:**
3. **`architecture.md` §4 NFR-Q1 measurement** được gán "Smart selection accuracy ≥ 90%" — khác với PRD NFR-Q1 "Factual error rate < 3%". Cần reconcile definition (possibly 2 gates khác nhau cùng tên Q1).
4. **`orchestra_sessions` Rocicorp Zero table** chỉ được nhắc trong UX handoff §8; architecture.md §11 nói "KHÔNG đổi DB schema". Chưa rõ ai own FE migration — cần add vào Story 9-FE-1 hoặc story riêng.

### Warnings
- UX spec §"Cross-References" list `architecture.md — TBD per-agent SSE event spec` — giờ đã RESOLVED. Cần update cross-reference.
- Architecture §10 Implementation Sequence rất tốt, chia Phase 1/2/3 có FE + BE pair → **có thể dùng làm base cho Story 9-FE-1** (FE phase 9.0 / 9.1 / 9.2).

---

## Step 5: Epic Quality Review

### Epic Structure Validation

#### Epic 0 — Crypto Foundation

**Title:** "Crypto Foundation (Tool Infrastructure + Base Sub-Agents + Testing)"

| Check | Finding | Verdict |
|---|---|---|
| User value focus | Technical foundation — no direct user value; **justified as retroactive drift closure + blocks Epic 9** | 🟡 Technical epic by design; explicitly labeled "Prerequisite" |
| Independence | Stand-alone; no forward dep on Epic 9 | 🟢 OK |
| Blocks declared | "Blocks: Epic 9 Phase 1" — explicit | 🟢 OK |
| NFR traceability | NFR-CS1-4, NFR-Q1-4 mapped | 🟢 OK |

**Note:** Epic 0 là technical epic nhưng có justification hợp lý (close drift giữa documentation và code reality). Pattern giống "Epic 1: Infrastructure" đã được accept trong dự án. Chấp nhận được với điều kiện clearly labeled prerequisite.

#### Epic 9 — Advanced Crypto Agents (Crypto Orchestra)

| Check | Finding | Verdict |
|---|---|---|
| User value focus | "As a crypto investor, I want specialist agents for tokenomics/whale/unlock..." — user value rõ | 🟢 OK |
| Phased rollout | Phase 1 (9.1+9.4) → 2 (9.2+9.5) → 3 (9.3+9.6); each phase has Quality Gates | 🟢 Excellent |
| Launch criteria | Q1-Q4 gates required before Phase 2 open | 🟢 Strong |
| Independence | Depends on Epic 0 (upstream) — properly declared | 🟢 OK |
| Backend-only focus | ⚠️ Không có FE story nào → UX work implied nhưng missing | 🔴 Gap (Story 9-FE-1) |

### Story Quality Assessment (Epic 0)

| Story | Size | AC Quality | Forward Dep? | Verdict |
|---|---|---|---|---|
| 0.1 Tool infrastructure | 1 week | G/W/T format, 11 tools enumerated, response time SLAs | None | 🟢 Strong |
| 0.2 Base sub-agents | 3 days | G/W/T, tiktoken unit test, parallelism check | Depends 0.1 ✓ (backward ok) | 🟢 Strong |
| 0.3 Main agent prompt | 2 days | G/W/T, lookup table + example | Depends 0.2 | 🟢 OK |
| 0.4 API integration tests | 3 days | Real API call AC, response format | Depends 0.1 | 🟢 OK |
| 0.5 Parallel execution validation | 3 days | Trace logs + ratio < 1.3x + dashboard | Depends 0.2 | 🟢 OK |
| 0.6 Error handling & fallback | 3 days | 429/timeout scenarios + > 98% rate | Depends 0.2 | 🟢 OK |

### Story Quality Assessment (Epic 9)

| Story | Size | AC Quality | Concerns | Verdict |
|---|---|---|---|---|
| 9.1 Tokenomics | 3 days | G/W/T, tool scoping, prompt size, Common AC (NFR-Q1/2) | 🟡 KHÔNG có frontend AC | 🟡 Backend-only |
| 9.2 Whale Tracker | 3 days | G/W/T, smart-money signal spec | 🟡 Tool drift (`web_search` vs `chainlens_deep_research`); no FE AC | 🟡 Needs align |
| 9.3 Token Unlock | 4 days (spike) | G/W/T, inline spike for tool research | 🟡 Spike merged — tốt; no FE AC | 🟡 OK but no FE |
| 9.4 Yield Optimizer | 3 days | G/W/T, IL calc, DeFiLlama+GoPlus | 🟡 No FE AC | 🟡 Backend-only |
| 9.5 Governance | 3 days | G/W/T, tracking framework | 🟡 Tool drift; no FE AC | 🟡 Needs align |
| 9.6 Technical Analyst | 4 days (spike) | G/W/T, indicators enumerated + inline spike | 🟡 Spike merged; no FE AC | 🟡 OK but no FE |

### 🔴 Critical Violations
1. **No FE story for Epic 9** — Journey #8 UX demands OrchestraStrip, DegradationNotice, stacked citations, 90s progress feedback. UX handoff §5 proposes `Story 9-FE-1`. Currently **missing from `epics.md` và `sprint-status.yaml`**.
2. **UX Open Questions stale** — 5/5 resolved by Architect §9/§7 but UX doc still shows "Open" status. Dev reading UX will be confused.

### 🟠 Major Issues
3. **Tool spec drift (FR28/29/31/32)** — Stories 9.2/9.3/9.5/9.6 list `web_search` as tool while PRD + Architecture §4 require `chainlens_deep_research`. Either:
   - (a) Update stories to match PRD (Chainlens primary, web_search fallback), or
   - (b) Update PRD to allow web_search as alternative.
   - Recommendation: **(a)** — keep Chainlens as primary (engine-of-record for deep research per Epic 7).
4. **NFR-Q1 definition ambiguity** — PRD defines as "factual error rate < 3%"; Architecture §4 table lists it as "Smart selection accuracy ≥ 90%". Two different gates under same NFR ID. Reconcile: possibly NFR-Q1a (accuracy) vs NFR-Q1b (selection accuracy).

### 🟡 Minor Concerns
5. `crypto-subagents-epics.md` và `crypto-subagents-guide.md` đang được reference trong Story 0.1 context nhưng không rõ có được move/archive sau Epic 0 hoàn thành. Risk: technical debt documentation.
6. `orchestra_sessions` Rocicorp Zero table ownership unclear — Backend Arch §11 says "KHÔNG đổi DB schema", implying FE-side Rocicorp Zero table. Phải gắn vào Story 9-FE-1 explicit.
7. Story 9.1 header có "CRITICAL PREREQUISITE — Code Reality Check" block — rất tốt nhưng nếu Epic 0 DONE thì block này trở thành stale. Cần pattern để auto-unblock hoặc Dev tự check sprint-status.yaml.

### Dependency Analysis

**Within-Epic (Epic 0):** No forward deps — 0.1→0.2→0.3 sequence, 0.4-0.6 parallel after 0.3. 🟢

**Within-Epic (Epic 9):** Phase 1 (9.1, 9.4) parallel; Phase 2 (9.2, 9.5) after Phase 1 gate; Phase 3 (9.3, 9.6) after Phase 2 gate. Each phase has `phase-N-quality-gate-review` entry trong sprint-status. 🟢

**Cross-Epic:** Epic 9 → Epic 0 (backward ✓). Epic 9 Stories 9.2/9.3/9.5/9.6 → Epic 7 Chainlens tool (backward ✓ — Epic 7 DONE). 🟢

**Proposed Story 9-FE-1 dependencies:** Requires Architecture §1 SSE events + Architecture §2 ParallelismTelemetryMiddleware (Story 0.5). Can start AFTER Epic 0 DONE in parallel with 9.1/9.4 backend. 🟢

### Sprint Plan Alignment Check

Sprint plan Phase 1 (sprint-plan-phase1-crypto-orchestra.md):
- ✅ Correctly declares Epic 0 prerequisite in `predecessorGates`
- ✅ Day 1 of Week 1 has "Epic 0 gate check — verify stories 0.4, 0.5, 0.6 passed"
- ✅ Timeline `~7-8 weeks from kick-off` reflects audit reality
- 🔴 **Gap:** Phase 1 sprint plan không mention Story 9-FE-1 hoặc bất kỳ FE work nào. FE team sẽ idle hoặc start late.

### Best Practices Compliance Checklist (Epic 0 + Epic 9)

- [x] Epic delivers user value (Epic 9; Epic 0 justified technical)
- [x] Epic can function independently (Epic 0 standalone; Epic 9 depends Epic 0 properly)
- [x] Stories appropriately sized (all ≤ 4 days)
- [x] No forward dependencies
- [x] Tables/DB creation timing — N/A (Epic 9 stateless tools per NFR-CS4)
- [x] Clear AC (Given/When/Then consistently)
- [x] Traceability to FRs (FR27-35 → stories 9.1-9.6; FR33-35 → 0.2-0.6)
- [ ] 🔴 **Frontend work explicitly planned** (MISSING — need Story 9-FE-1)
- [ ] 🟡 **Tool spec consistency** (drift on 4 stories)
- [ ] 🟡 **UX resolved questions back-propagated** (5 stale)

---

## Step 6: Summary and Recommendations

### Overall Readiness Status

🟡 **NEEDS WORK — Conditional GO**

> Foundation rất chắc (Epic 0 retroactive well-designed, Epic 9 phased rollout với quality gates rõ ràng, UX/Architecture alignment mature). **3 Known Gaps được confirmed**, tất cả đều có fix nhỏ (không phải structural rework). Có thể unblock Epic 0 start ngay trong khi fix Gap #2 và chuẩn bị Story 9-FE-1.

### Known Gap Verification Results

| # | User-flagged Gap | Verification | Status |
|---|---|---|---|
| 1 | Stories 9-1..9-6 thiếu explicit frontend AC — UX session đề xuất Story 9-FE-1 | Stories 9.1-9.6 backend-only; UX handoff §5 đề xuất Story 9-FE-1; `epics.md` + `sprint-status.yaml` KHÔNG có FE story | 🔴 **CONFIRMED** |
| 2 | 5 open design questions từ UX §7 đã resolved bởi Architect §9 — chưa back-propagate vào UX spec | UX spec §7 vẫn list 5 questions as "Open"; Architecture §9/§7 có decision table cho cả 5 | 🔴 **CONFIRMED** |
| 3 | Architecture Phase 0 sequence ↔ Stories 0.1-0.6 timeline alignment | Architecture §10 sequence (0.1→0.2→0.3→0.4→0.5→0.6 sequential) KHỚP với sprint-status + sprint-plan prerequisites. Sprint plan estimated "Epic 0 ~3-4 weeks" matches Architecture "Phase 0 (blocking Phase 1)" | 🟢 **NO ISSUE** |

### Critical Issues Requiring Immediate Action

#### 🔴 CRITICAL (block Phase 1 Backend go-live, not Epic 0)

**C1. Add Story 9-FE-1 to `epics.md` + `sprint-status.yaml`**
- **Owner:** PM (Mary) + UX Lead
- **Scope:** Story covering 7 new components + 3 modified components + Zustand store + telemetry helper (UX handoff §8) + FE Rocicorp Zero `orchestra_sessions` migration
- **Target sprint:** Start in parallel với Story 9.1 backend (Week 2 of Phase 1)
- **Deps:** Architecture §1 SSE event contract (DONE) + Story 0.5 ParallelismTelemetryMiddleware (Phase 0 done)
- **AC source:** UX handoff §2-7 + architecture.md §1-3 telemetry events

**C2. Back-propagate 5 Architect decisions vào UX spec**
- **Owner:** UX Lead
- **Scope:** Update `ux-crypto-orchestra-handoff.md` §7 từ "Open Design Questions" → "Resolved (cross-ref architecture.md §9/§7)"; update `ux-design-specification.md` §"Cross-References" (remove "TBD" note về SSE event spec)
- **Effort:** 1-2 hours, non-technical

#### 🟠 MAJOR (fix trước Phase 1 Backend Week 2)

**M1. Align tool spec cho FR28/29/31/32 trong stories**
- Stories 9.2/9.3/9.5/9.6 list `web_search`; should be `chainlens_deep_research` (primary) + `web_search` (fallback). Consistent with PRD FR28-32 + Architecture intent (reuse Epic 7 engine).
- **Owner:** PM + Dev Lead
- **Effort:** Update story AC sections (4 files × ~30 min).

**M2. Reconcile NFR-Q1 definition**
- PRD: "Factual error rate < 3%". Architecture §4: "Smart selection accuracy ≥ 90%". Two different gates.
- Recommend: split into NFR-Q1a (accuracy) và NFR-Q1b (selection routing). Update architecture.md table + PRD Quality Gates section.
- **Owner:** PM + Architect
- **Effort:** 1 hour + team sync.

#### 🟡 MINOR (nice-to-have before launch)

- **N1.** Archive `crypto-subagents-epics.md` + `crypto-subagents-guide.md` sau Epic 0 DONE (hoặc mark "historical reference") để tránh future drift.
- **N2.** Resolve `orchestra_sessions` Rocicorp Zero table ownership — add explicit migration item vào Story 9-FE-1 hoặc tạo Story 9-FE-2 cho FE data layer.
- **N3.** Add note vào Story 9.1 prerequisite block: "Dev must re-verify against current sprint-status.yaml before starting" để handle case Epic 0 DONE (tránh stale warning).
- **N4.** Cross-reference `HANDOFF-crypto-orchestra.md` với `ux-crypto-orchestra-handoff.md` — verify không phải 2 bản khác nhau; nếu cùng nội dung thì consolidate.

### Recommended Next Steps (ordered)

1. **(Fix Gap #2 first — cheapest)** UX Lead update `ux-crypto-orchestra-handoff.md` §7 + `ux-design-specification.md` Cross-References. Bring UX doc in sync với Architect decisions. 1-2h.
2. **(Fix Gap #1 — unblocks FE team)** PM + UX Lead draft Story 9-FE-1 in `stories/9-FE-1-orchestra-conductor-strip.md`. Use UX handoff §2-8 + Architecture §1-3 as AC source. Add entry vào `epics.md` Epic 9 + `sprint-status.yaml` under Phase 1. Target: 1 day drafting.
3. **(Fix M1 — tool drift)** Dev Lead update Stories 9.2/9.3/9.5/9.6 tool references to `chainlens_deep_research` (primary) + `web_search` (fallback). Verify consistency với Epic 7 integration. 2h.
4. **(Fix M2 — NFR clarity)** PM + Architect sync to reconcile NFR-Q1 definition split. Update both docs. 1h.
5. **(Start Phase 0 immediately)** Epic 0 Stories 0.1-0.6 are **GO** — ready-for-dev, prerequisites clearly declared, ACs strong. Start với Story 0.1 Mon 2026-04-27 (per sprint plan Week 1 Day 1).
6. **(Phase 1 kick-off gate)** Verify `phase-1-quality-gate-review` AFTER Stories 9.1 + 9.4 hit production 2 weeks. Only open Phase 2 when all 4 Q-gates pass.

### Final Readiness Matrix by Artifact

| Artifact | Completeness | Consistency | Traceability | Verdict |
|---|---|---|---|---|
| PRD (FR27-35, NFR-CS/Q, UJ#8) | 🟢 | 🟡 (NFR-Q1 ambiguity) | 🟢 | 🟢 Ready |
| Architecture §9 (Crypto Orchestra) | 🟢 | 🟢 | 🟢 | 🟢 Ready |
| Epic 0 (6 stories) | 🟢 | 🟢 | 🟢 | 🟢 **GO** |
| Epic 9 (6 stories, backend-only) | 🟡 (FE missing) | 🟡 (tool drift) | 🟢 | 🟡 Needs minor fixes |
| UX Spec § Crypto Orchestra | 🟢 | 🟡 (open Qs stale) | 🟢 | 🟡 Back-propagate decisions |
| UX Handoff | 🟢 | 🟡 (§7 stale) | 🟢 | 🟡 Update §7 resolutions |
| Sprint Plans (Phase 1/2/3) | 🟢 | 🟡 (no FE work scheduled) | 🟢 | 🟡 Add 9-FE-1 |
| Sprint Status YAML | 🟢 | 🟡 (no 9-FE-1 entry) | 🟢 | 🟡 Add entry |

### Final Note

Assessment identified **9 issues across 3 severity levels** (2 🔴 critical, 2 🟠 major, 5 🟡 minor/admin). **Good news:** foundation là mature — không có structural rework, tất cả issues là "alignment / documentation sync". Epic 0 có thể start **immediately** (Mon 2026-04-27). Parallel track: fix C1, C2, M1, M2 trong Week 1 của Epic 0 (~4-5 hours total PM/UX/Arch effort) để Phase 1 Backend + Frontend có thể kick-off đồng thời ở Week 2.

**Assessor:** PM readiness check skill (autonomous run 2026-04-23).
**Input corpus:** 21 artifacts (PRD + Architecture + Epics + 12 stories + 3 sprint plans + 2 UX docs + sprint-status).
**Output:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-04-23.md`
