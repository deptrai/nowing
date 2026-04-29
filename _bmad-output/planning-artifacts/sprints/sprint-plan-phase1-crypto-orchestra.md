---
documentType: sprint-plan
sprintName: "Phase 1 — Crypto Orchestra Quality Foundation"
phase: 1
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra)
stories:
  - 9.1 Tokenomics Analyst Sub-Agent
  - 9.4 Yield Optimizer Sub-Agent
duration: 4 weeks
startDate: 2026-04-27
endDate: 2026-05-22
author: Mary (Strategic Business Analyst)
createdAt: 2026-04-23
status: draft-ready-for-dev
predecessorGates:
  - "🆕 Epic 0 (Crypto Foundation) phải hoàn thành TRƯỚC (audit 2026-04-23 phát hiện chưa implement)"
  - Epic 0 Stories 0.4-0.6 (Testing) phải hoàn thành trước week 1 Phase 1
estimatedTotalDuration: "Epic 0 (~3-4 weeks incl. testing 0.4-0.6) → Phase 1 (4 weeks) = ~7-8 weeks from kick-off"
qualityGatesPhase1:
  - NFR-Q1 Accuracy < 3%
  - NFR-Q2 Parallelism ratio < 1.3x
  - NFR-Q3 Graceful degradation > 98%
  - NFR-Q4 Hallucination rate < 1%
---

# Sprint Plan — Phase 1: Quality Foundation

## 🚨 CRITICAL: Prerequisite Chain (cập nhật 2026-04-23)

Code audit phát hiện **Epic 0 (Crypto Foundation) chưa thực sự implement** mặc dù documentation cho thấy đã hoàn thành. Sprint plan Phase 1 phải chạy SAU chuỗi prerequisite này:

```
┌─────────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│ Epic 0: Foundation  │ ──> │ Epic 0 Testing   │ ──> │ Phase 1 Epic 9    │
│ (~2-3 weeks)        │     │ (~1 week)        │     │ (4 weeks)         │
│                     │     │                  │     │                   │
│ • 4 tool files      │     │ • API integration│     │ • Story 9.1       │
│ • 4 base sub-agents │     │ • Parallel exec  │     │ • Story 9.4       │
│ • Main prompt wired │     │ • Error handling │     │ • Quality Gates   │
└─────────────────────┘     └──────────────────┘     └───────────────────┘
```

**KHÔNG thể start Phase 1 Week 1 nếu Epic 0 (6 stories: 0.1-0.6) chưa DONE. Xem epics.md "Epic 0: Crypto Foundation" cho spec đầy đủ.

---

## 🎯 Sprint Goal

Triển khai 2 crypto sub-agents đầu tiên của Crypto Orchestra (Tokenomics + Yield Optimizer) trên foundation đã có, **đạt cả 4 Quality Gates** trong 2 tuần production validation trước khi mở Phase 2.

> **Tại sao 2 agents này?**
> - **Deterministic tools heavy**: dùng CoinGecko + DeFiLlama + GoPlus (không phụ thuộc Chainlens quá nặng) → easier accuracy baseline
> - **High user value**: Tokenomics + Yield là 2 câu hỏi crypto retail hỏi nhiều nhất
> - **Foundation validation**: Validate spawn pattern với **6 agents parallel** (4 Epic 1-2 + 2 mới) trước khi lên 8, 10

---

## 📅 Timeline — 4 Weeks

### Week 1 (Apr 27 – May 3) — Foundation & Tokenomics

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| Mon | Epic 0 gate check — verify stories 0.4, 0.5, 0.6 passed | Dev Lead | ✅/❌ go signal |
| Mon | Kick-off: align team on Phase 1 goals + Quality Gates | All | Sprint board ready |
| Tue-Wed | **Story 9.1 dev**: `tokenomics_spec.py` + system prompt < 500 tokens | Dev 1 | Spec file + prompt draft |
| Thu | Wire `tokenomics_analyst` vào `SubAgentMiddleware` trong `chat_deepagent.py` | Dev 1 | Registration code |
| Fri | Unit tests: system prompt token count, tool scoping, `requires=[]` check | Dev 1 | Green tests |

### Week 2 (May 4 – May 10) — Yield Optimizer + Integration

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| Mon-Tue | **Story 9.4 dev**: `yield_optimizer_spec.py` + IL risk calculation logic | Dev 2 | Spec file + prompt |
| Wed | Wire `yield_optimizer` vào middleware + update main agent orchestration prompt | Dev 2 | Integration code |
| Thu | Unit tests + integration test với 6 agents parallel spawn | Dev 2 | Green test suite |
| Fri | Internal dogfooding: team test live với $UNI, $AAVE, $CRV queries | All | Qualitative feedback doc |

### Week 3 (May 11 – May 17) — QA + Telemetry

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| Mon | Deploy to staging với telemetry logging (parallelism ratio, token count, agent success rate) | DevOps | Staging URL ready |
| Tue-Wed | **QA Sprint**: 100 sample queries (50 tokenomics + 50 yield) — factual check vs raw APIs | QA | QA spreadsheet với error rate |
| Thu | Hallucination pattern check — regex `[0-9]+%|\$[0-9]+` cross-check vs tool output | QA | Hallucination report |
| Fri | Bug fixing session dựa trên QA findings | Dev 1+2 | Fixed PRs |

### Week 4 (May 18 – May 22) — Production & Gate Decision

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| Mon | Production deploy với feature flag ON cho 10% users | DevOps | Canary live |
| Tue-Wed | Monitor telemetry — accuracy, parallelism ratio, degradation rate, hallucination | Dev Lead | Daily report |
| Thu | **Phase 1 Gate Review** — assess 4 Quality Gates | Mary + Stakeholders | Go/No-Go decision for Phase 2 |
| Fri | Retrospective + launch marketing if GO | All | Phase 1 retro doc + PR post |

---

## 📦 Deliverables

### Story 9.1 — Tokenomics Analyst

**Files to create:**
- `nowing_backend/app/agents/new_chat/subagents/crypto/tokenomics_spec.py` (~50 LOC)

**Files to modify:**
- `nowing_backend/app/agents/new_chat/chat_deepagent.py` — register `tokenomics_analyst` trong `SubAgentMiddleware`
- `nowing_backend/app/agents/new_chat/prompts/main_agent_prompt.md` — thêm lookup table entry

**Tools scoped (from PRD FR27):**
- `get_coingecko_token_info`
- `chainlens_deep_research` (supplementary — Messari, CryptoRank, official docs)

**System prompt hints (< 500 tokens):**
```
You are tokenomics_analyst. For a given token, analyze:
1. Supply: circulating vs total vs max (from get_coingecko_token_info)
2. Vesting schedule + cliff dates (from chainlens_deep_research)
3. Distribution % (team/investors/community/treasury)
4. Inflation/deflation mechanics
5. Buy pressure vs sell pressure signals

ALWAYS cite source from tool output. NEVER fabricate numbers.
Output format: 📊 Supply | 📅 Vesting | 🥧 Distribution | 🔄 Economics | ⚖️ Pressure | 💡 Insight
```

**Definition of Done:**
- [ ] Spec file created + wired in middleware
- [ ] System prompt token count < 500 (verified via `tiktoken`)
- [ ] Tool registry entries have `requires=[]`
- [ ] Unit test: agent only has scoped tools (không có access tool khác)
- [ ] Integration test: main agent spawn successfully qua `task(agent="tokenomics_analyst", ...)`
- [ ] QA: 50 tokenomics queries, factual error rate < 3%
- [ ] Hallucination check: < 1% fabricated numbers

---

### Story 9.4 — Yield Optimizer

**Files to create:**
- `nowing_backend/app/agents/new_chat/subagents/crypto/yield_optimizer_spec.py` (~50 LOC)

**Files to modify:**
- `chat_deepagent.py` — register `yield_optimizer`
- `main_agent_prompt.md` — thêm lookup entry

**Tools scoped (from PRD FR30):**
- `get_defillama_yields`
- `get_defillama_protocol`
- `check_token_security` (GoPlus)

**System prompt hints (< 500 tokens):**
```
You are yield_optimizer. User provides capital + risk preference.
Risk levels:
- Conservative: stablecoin pools only, TVL > $10M, audited protocols
- Moderate: blue-chip LPs (ETH/BTC pairs), TVL > $5M
- Aggressive: high-APY farms, accept IL risk

Steps:
1. Call get_defillama_yields filtered by symbol + min_tvl matching risk
2. For LP positions: calculate IL risk (volatility of pair)
3. For each protocol: call check_token_security — flag risks
4. Rank by (APY × security_score / IL_risk)

ALWAYS cite APY source + audit status. NEVER recommend without security check.
Output format: 🏆 Top picks (3) | 📈 APY | 🛡️ Security | ⚠️ IL Risk | 💡 Strategy
```

**Definition of Done:**
- [ ] Spec file created + wired
- [ ] System prompt < 500 tokens
- [ ] Tool scoping enforced
- [ ] IL risk calculation tested với synthetic pairs
- [ ] Security check tự động cho mọi protocol recommend
- [ ] Unit + integration tests green
- [ ] QA: 50 yield queries, factual error rate < 3%
- [ ] Hallucination check: < 1% fabricated APY numbers

---

## 🚦 Quality Gates Checklist (Week 4 — Go/No-Go Phase 2)

| Gate | Metric | Target | Measurement Window | Owner |
|------|--------|--------|-------------------|-------|
| 🎯 NFR-Q1 | Factual error rate | **< 3%** | 100 sample queries (Week 3 QA + Week 4 canary) | QA |
| 🎵 NFR-Q2 | Parallelism ratio `total/max` | **< 1.3x** | All Week 4 production traces | Dev Lead |
| 🔥 NFR-Q3 | Graceful degradation rate | **> 98%** | All Week 4 requests có ≥1 agent error. 3-tier ladder (parallel / sequential / paced) — paced Tier 3 metric `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_paced"}` from Story 0.6b must be scraped | Dev Lead |
| 🧠 NFR-Q4 | Hallucination rate | **< 1%** | Pattern scan + sample QA | QA |

**Gate Decision Matrix:**
- ✅ **All 4 gates PASS** → GREEN → Launch Phase 1 full rollout + kick off Phase 2 (9.2 + 9.5)
- ⚠️ **1-2 gates fail marginally** (within 20% of target) → AMBER → 1 week remediation sprint, re-evaluate
- ❌ **Any gate fails significantly** or **2+ gates fail** → RED → Rollback canary, root cause analysis, no Phase 2 until resolved

---

## 🎭 Roles & Ownership

| Role | Person | Responsibility |
|------|--------|---------------|
| Dev 1 | TBD | Story 9.1 Tokenomics — spec + prompt + tests |
| Dev 2 | TBD | Story 9.4 Yield Optimizer — spec + IL logic + security check |
| Dev Lead | TBD | Code review, integration, telemetry instrumentation |
| QA | TBD | 100-query QA (Week 3) + canary monitoring (Week 4) |
| DevOps | TBD | Staging deploy, feature flag, canary rollout |
| Product/BA | Mary | Gate review, Phase 2 decision, stakeholder communication |

---

## ⚠️ Risks & Contingencies

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Epic 0 testing (0.4-0.6) chưa pass → Phase 1 delayed | Medium | Stories 0.4-0.6 priority #1 trong week 0. Nếu slip, delay Phase 1 start 1 week |
| CoinGecko rate limit hit khi QA 50 queries | Medium | Throttle QA script 1 req/2s hoặc dùng cached test fixtures |
| System prompt > 500 tokens (NFR-CS1 fail) | Low | Buffer room — aim < 450 tokens trong design, iterate |
| Accuracy < 95% (NFR-Q1 fail) | Medium | 1 week remediation sprint — tighten prompt, add "always cite" instruction |
| Parallelism ratio > 1.5x (major fail) | Low | Debug LangGraph ToolNode batching — likely config issue |
| GoPlus API down cả tuần QA | Low | Mock response fallback + flag test as "API dependency issue" |

---

## 📊 Telemetry Requirements (Week 3 setup)

Dev Lead implement logging cho:
1. **Per-request metrics**:
   - `agents_spawned`: list[str]
   - `parallelism_ratio`: float (`total_time / max(individual_time)`)
   - `agent_errors`: list[dict] (agent_name, error_type)
   - `fallback_used`: bool
2. **Per-agent metrics**:
   - `tokens_in`, `tokens_out`
   - `duration_ms`
   - `tool_calls`: list[str]
3. **Dashboard** (Grafana/basic):
   - Parallelism ratio P50/P95
   - Degradation rate weekly
   - Agent success rate per agent

---

## 🎬 Marketing Coordination (Stakeholder-approved)

**Phase 1 Launch Content** (sync với Week 4 GO decision):
- Blog post: *"Introducing Crypto Orchestra: Tokenomics + Yield Analysts"*
- Twitter thread: 6-tweet explainer + demo video (30s)
- Landing page section: add 2 new agent cards
- Product Hunt soft launch (optional)

Launch only if **ALL 4 gates PASS**. If AMBER → delay launch, keep canary.

---

## 🔗 References

- **PRD**: `_bmad-output/planning-artifacts/prd.md` (v2026-04-23) — FR27, FR30, NFR-Q1-Q4
- **Epics**: `_bmad-output/planning-artifacts/epics.md` — Epic 9 Stories 9.1, 9.4
- **Product Brief**: `_bmad-output/planning-artifacts/briefs/product-brief-epic9-crypto-orchestra.md` (v2)
- **Architecture**: `_bmad-output/planning-artifacts/architecture.md`
- **Crypto Guide**: `nowing_backend/docs/crypto-subagents-guide.md`
- **Existing Agents**: `nowing_backend/app/agents/new_chat/subagents/crypto/` (Epic 1-2)

---

**Status**: Draft ready-for-dev ✅
**Next**: Assign Dev 1, Dev 2, Dev Lead, QA, DevOps → kick-off Week 1 Monday.

---

## 📝 Scope Changelog

### 2026-04-24 — Tier 3 Paced Sequential Escalation (Story 0.6b)

**Discovered during**: Pre-canary E2E smoke test against TrollLLM (10 RPM dev provider).

**Finding**: Tier 2 natural sequential (implemented in Story 0.6) is still faster than very-strict provider RPM windows once KB planner + synthesis LLM calls accumulate → stream aborts on sustained pressure.

**Scope-in**: [Story 0.6b](../stories/0-6b-rate-limit-paced-escalation.md) — Tier 3 paced sequential mode. After 3 consecutive rate-limit events in cooldown window, forces `asyncio.sleep(7)` between agent emissions and retries main synthesis up to 3× with paced backoff.

**Effort**: ~1-2h (single-file change in `chat_deepagent.py`). Does NOT shift sprint timeline — completed within current week.

**Impact on gates**:
- NFR-Q3 target (> 98% graceful degradation) now achievable even against strict-RPM providers
- New metric `GRACEFUL_DEGRADATION_COUNTER{outcome="rate_limit_paced"}` must be scraped by Week 3 telemetry setup
