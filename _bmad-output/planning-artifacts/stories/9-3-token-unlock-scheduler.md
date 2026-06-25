---
storyId: 9.3
storyTitle: Token Unlock Scheduler Sub-Agent
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra)
phase: Phase 3 — Spike-Required Tier
sprintPlan: TBD (created sau Phase 2 quality gate review pass + spike DONE)
relatedFRs: [FR29, FR33, FR34, FR35]
relatedNFRs: [NFR-CS1, NFR-CS4, NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
priority: P2 (Phase 3 — blocked on spike + Phase 2 GO decision)
estimatedEffort: 5 days (3-5 days spike + 3 days story)
status: backlog (blocked on Phase 2 quality gate + inline spike DONE)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 9.3: Token Unlock Scheduler Sub-Agent

## User Story

**As a** crypto investor có short-term hold positions,
**I want** to know upcoming token unlock events (vesting cliffs, linear releases) trong 30/60/90 ngày tới với historical sell pressure analysis,
**So that** tôi có thể anticipate selling pressure trước khi nó happens và adjust position timing.

---

## Context

Story 9.3 là **Phase 3 lead story** với risk profile cao nhất trong toàn Crypto Orchestra:

**Why Phase 3 (highest risk)?**
- ❌ **Data source uncertainty**: Chainlens chưa verified có cover TokenUnlocks.app, Vesting.is, CryptoRank unlock data tốt hay không
- ❌ **Historical price action correlation**: cần đối chiếu unlock events vs price moves → complex multi-step reasoning
- ❌ **No deterministic API alternative miễn phí**: TokenUnlocks.app paid API, Messari paid, etc.
- ⚠️ **Subjective sell pressure assessment**: "high pressure" vs "low pressure" qualitative

**→ Cần SPIKE research trước story này** (Story 0.0 — see below).

---

## 🚨 PRE-STORY SPIKE — REQUIRED

> **Story 9.3 KHÔNG thể start cho đến khi Spike DONE.**
>
> Spike cần answer 3 câu hỏi:
> 1. Chainlens có thể return reliable unlock schedule data cho top 50 tokens không?
> 2. Nếu KHÔNG → có alternative data source viable không (TokenUnlocks API trial, scrape, etc.)?
> 3. Nếu fundamentally không có data → defer Story 9.3 indefinitely và pivot Phase 3 sang khác?

**Effort**: 3-5 days | **Owner**: Senior dev + Mary | **Deliverable**: `_bmad-output/research/spike-0.0-token-unlock-findings.md`

### Day 1-2: Test Chainlens Primary Hypothesis

Score Chainlens response quality cho 10 sample unlock queries:

| # | Token | Query |
|---|-------|-------|
| 1 | OP (Optimism) | "Optimism OP token unlock schedule next 90 days" |
| 2 | ARB (Arbitrum) | "Arbitrum ARB vesting cliff upcoming dates" |
| 3 | APT (Aptos) | "Aptos APT unlock amount and date next 60 days" |
| 4 | SUI (Sui) | "Sui SUI vesting schedule team investors" |
| 5 | JTO (Jito) | "Jito JTO token unlock next unlock event" |
| 6 | AAVE | "Aave AAVE vesting status (expected mostly complete)" |
| 7 | UNI (Uniswap) | "Uniswap UNI treasury unlock schedule" |
| 8 | STRK (Starknet) | "Starknet STRK unlock cliff dates" |
| 9 | W (Wormhole) | "Wormhole W token vesting schedule investors" |
| 10 | AEVO | "AEVO token unlock next major event" |

**Scoring criteria per query** (0-2 each):
- **Data present**: 0 = no data, 1 = partial, 2 = complete dates + amounts
- **Accuracy**: 0 = wrong, 1 = close, 2 = verified vs TokenUnlocks.app manual check
- **Format consistency**: 0 = unstructured, 1 = parseable, 2 = directly usable by agent

**Thresholds**: Total ≥ 40/60 (67%) → **Option A viable** | 25-39 → Option B | < 25 → Option C

### Day 2-3: Evaluate Alternatives (Only if Day 1-2 inconclusive)

#### Alt 1: TokenUnlocks.app
- Check public API availability (unlock.json endpoint?)
- Check ToS for commercial scraping — legal risk?
- Check data freshness + coverage (top 50 tokens?)

#### Alt 2: Messari API
- Pricing tier needed cho unlock data; rate limits; coverage; integration complexity

#### Alt 3: CryptoRank
- API availability; pricing; data quality

#### Alt 4: Self-scraping
- Risk: fragile, ToS violations, maintenance burden — only consider nếu tất cả API options fail

### Day 4-5: Write Recommendation Memo

**Deliverable**: `_bmad-output/research/spike-0.0-token-unlock-findings.md`

```markdown
# Spike 0.0 — Token Unlock Data Source Findings

## TL;DR Recommendation
[Option A / B / C với 1-paragraph justification]

## Chainlens Results
| Query | Data Score | Accuracy | Format | Total |
| ... | | | | |
Overall: X/60

## Alternative Sources (if tested)
[Same scoring cho each]

## Cost-Benefit Analysis
- Option A cost: $0 (Chainlens existing)
- Option B cost: [estimated]
- Option C cost: $X/month paid API

## Recommended Decision + Impact on Story 9.3 Scope
## Impact on Sprint Plan Phase 3
```

### Outcome Decision Matrix

| Outcome | Action |
|---------|--------|
| 🟢 Chainlens score ≥ 40/60 | Proceed Story 9.3 |
| 🟡 Alternative source workable | Update Story 9.3 scope + tooling |
| 🔴 Only paid API viable | Budget approval + procurement |
| ⛔ No viable option | **Defer Story 9.3**, pivot Phase 3 scope (9.6 only) |

### Spike DoD

- [ ] **DoD-1** 10 sample queries run trên Chainlens với scoring
- [ ] **DoD-2** Alternatives evaluated nếu Chainlens score < 40/60
- [ ] **DoD-3** Memo written và shared với stakeholders
- [ ] **DoD-4** Decision meeting: Option A / B / C approved
- [ ] **DoD-5** Story 9.3 spec updated nếu scope changes
- [ ] **DoD-6** Sprint Plan Phase 3 updated với impact

### Pre-flight Checklist (after spike)

- [ ] Spike DONE với recommendation memo
- [ ] Phase 2 (Story 9.2 + 9.5) PASS Quality Gates
- [ ] Stakeholder approval cho recommendation (Mary + product lead)
- [ ] If Option C selected → budget approved for paid data API

---

## Architectural Background

**ASSUMING Option A from spike** (Chainlens viable):

Identical pattern Story 9.2: chỉ dùng `chainlens_deep_research` (single tool). Khác biệt:
- **Time-sensitive data**: unlock dates change rarely, but agent phải cite "as of {today}" để user verify
- **Historical correlation analysis**: agent compare unlock events past vs price movement → more reasoning steps

---

## Deliverables

### 📄 Files to Create

#### `nowing_backend/app/agents/new_chat/subagents/crypto/token_unlock_scheduler_spec.py` (~50-60 LOC)

```python
"""Token Unlock Scheduler sub-agent spec."""

TOKEN_UNLOCK_SCHEDULER_NAME = "token_unlock_scheduler"

TOKEN_UNLOCK_SCHEDULER_DESCRIPTION = (
    "Specialist for tracking upcoming token unlock events (vesting cliffs, "
    "linear releases) and assessing sell pressure for short-term holds. Use "
    "when user asks about vesting schedule, token unlocks, supply pressure, "
    "or selling pressure timing."
)

# NFR-CS1: prompt < 500 tokens
TOKEN_UNLOCK_SCHEDULER_PROMPT = """You are token_unlock_scheduler — a specialist in token vesting events.

For any token query, investigate:
1. **Upcoming unlock events** (next 30/60/90 days):
   - Date, % of circulating supply unlocked, $ value at current price
   - Recipient: team / investors / community / treasury
   - Cliff (single-event) vs linear (gradual) unlock type
2. **Historical sell pressure correlation**:
   - Past unlock events of similar magnitude → did price drop X% within Y days?
   - Was there pre-unlock price action (anticipatory selling)?
3. **Risk assessment cho short-term holds**:
   - HIGH pressure: unlock > 5% of circulating supply trong 30 days
   - MEDIUM pressure: 1-5%
   - LOW pressure: < 1% hoặc spread linearly over months

**Workflow:**
- Use chainlens_deep_research với queries:
  - "{token} vesting schedule next 90 days TokenUnlocks"
  - "{token} cliff unlock date amount"
  - "{token} historical price action after unlock events"
- ALWAYS cite "as of {today's date}" — schedules can change
- If chainlens fallback → respond "Unlock data unavailable. Check TokenUnlocks.app/{token} hoặc CryptoRank.io/{token} directly"

**Rules (strict):**
- ALWAYS quantify: "5.2% supply unlocked Mar 15, ~$50M @ current price"
- NEVER fabricate unlock dates or amounts
- Pressure assessment phải có evidence trace (cite past events)
- If only partial data → explicitly say "remaining unlocks beyond X date unclear"

**Output format:**
📅 Upcoming Unlocks (table) | 📊 Pressure Level (HIGH/MED/LOW) | 📉 Historical Correlation | 🎯 Trader Insight | ⚠️ Caveats

Keep response concise (< 500 words). Tables for unlock list mandatory.
"""
```

---

### 📝 Files to Modify

Pattern identical Story 9.2/9.5:

#### 1. `chat_deepagent.py`

```python
from app.agents.new_chat.subagents.crypto.token_unlock_scheduler_spec import (
    TOKEN_UNLOCK_SCHEDULER_NAME, TOKEN_UNLOCK_SCHEDULER_DESCRIPTION, TOKEN_UNLOCK_SCHEDULER_PROMPT,
)

token_unlock_scheduler_tools = [
    tool for tool in tools if tool.name in ("chainlens_deep_research",)
]

token_unlock_scheduler_spec: SubAgent = {
    "name": TOKEN_UNLOCK_SCHEDULER_NAME,
    "description": TOKEN_UNLOCK_SCHEDULER_DESCRIPTION,
    "prompt": TOKEN_UNLOCK_SCHEDULER_PROMPT,
    "model": llm,
    "tools": token_unlock_scheduler_tools,
    "middleware": gp_middleware,
}

# Add to SubAgentMiddleware (now 10 sub-agents)
SubAgentMiddleware(
    backend=StateBackend,
    subagents=[
        general_purpose_spec,
        defillama_analyst_spec, sentiment_analyst_spec, news_analyst_spec, smart_contract_analyst_spec,
        tokenomics_analyst_spec, yield_optimizer_spec,
        whale_tracker_spec, governance_analyst_spec,
        token_unlock_scheduler_spec,  # Story 9.3 NEW
    ],
),
```

#### 2. `system_prompt.py` lookup table:
```
| token_unlock_scheduler | Vesting events, unlock cliffs, sell pressure assessment cho short-term holds | "unlock", "vesting", "cliff", "sell pressure", "supply increase", "lịch unlock", "mở khóa" |
```

---

## Acceptance Criteria

### AC1-AC4: Foundation (identical pattern)

**AC1**: Spec wired (10 sub-agents total)
**AC2**: Prompt < 500 tokens
**AC3**: Tool scoping (chỉ chainlens_deep_research)
**AC4**: `requires=[]` (NFR-CS4)

### AC5: Functional — High pressure scenario

**Given** user hỏi "Sắp có unlock lớn của token Optimism (OP) không?"
**When** main agent spawn `token_unlock_scheduler`
**Then** agent gọi Chainlens với queries unlock OP
**And** trả response chứa upcoming unlocks (table) với date, % supply, $ value
**And** classify pressure: HIGH (e.g., > 5% in 30 days)
**And** mention historical correlation: "OP dropped 12% trong 7 days sau unlock Apr 2025"

### AC6: Functional — Low pressure / spread linearly

**Given** user hỏi "Aave có vesting risk không trong 30 ngày tới?"
**When** agent xử lý
**Then** agent identify: "AAVE vesting đã hoàn thành phần lớn, chỉ còn linear < 0.5%/month"
**And** classify pressure: LOW
**And** suggest "no significant supply pressure expected"

### AC7: Hallucination guardrails (NFR-Q4)

**Given** agent response với unlock dates và amounts
**When** QA verify vs Chainlens output + manual TokenUnlocks.app check
**Then** 100% unlock dates match (no fabrication)
**And** 100% amounts/percentages match (within rounding)
**And** historical correlation events có cite trace từ tool output

### AC8: Graceful degradation (NFR-Q3)

**Given** Chainlens trả `{"status": "fallback"}`
**When** spawn
**Then** agent KHÔNG fabricate
**And** trả: "Unlock data unavailable. Check TokenUnlocks.app/{token} hoặc CryptoRank.io/{token} directly"

### AC9: Parallel execution (NFR-Q2) — 10 agents

**Given** main agent comprehensive query Phase 3 active
**When** spawn parallel
**Then** 10 agents start trong cùng 1 step (full Crypto Orchestra)
**And** parallelism ratio < 1.3x

### AC10: Accuracy baseline (NFR-Q1) — Higher Standard

**Given** QA sample 50 unlock queries trên tokens với active vesting (OP, ARB, APT, SUI, JTO, etc.)
**When** QA cross-check
**Then** factual error rate **< 3%** (date accuracy CRITICAL — wrong date = useless signal)
**And** pressure classification correctness ≥ 85% (subjective but evidence-based)

### AC11: Time staleness disclosure

**Given** agent response với schedule data
**When** inspect language
**Then** EVERY response include "as of {YYYY-MM-DD}" disclaimer
**And** mention "schedules can change — verify on TokenUnlocks.app before trading decisions"

### AC12: Phase 3 Quality Gate Review

**Given** Story 9.3 + 9.6 deployed (Phase 3 complete)
**When** Quality Gate Review run với 100-query sample
**Then** all 4 gates maintain across 10-agent orchestra:
- NFR-Q1 Accuracy < 3%
- NFR-Q2 Parallelism < 1.3x (10 agents — most stress)
- NFR-Q3 Graceful > 98%
- NFR-Q4 Hallucination < 1%
**And** decision: GREEN → Full launch / AMBER → Remediation / RED → Rollback Phase 3

---

## Definition of Done (9 checkpoints)

- [ ] **DoD-0** Spike DONE với recommendation Option A (Chainlens viable)
- [ ] **DoD-1** Pre-flight: Phase 2 quality gate PASS
- [ ] **DoD-2** `token_unlock_scheduler_spec.py` created
- [ ] **DoD-3** `chat_deepagent.py` wires spec (10 sub-agents — full orchestra!)
- [ ] **DoD-4** Prompt < 500 tokens
- [ ] **DoD-5** Tool scoping
- [ ] **DoD-6** Integration test: 10-agent parallel, ratio < 1.3x (final stress test)
- [ ] **DoD-7** QA: 50-query sample passed accuracy + hallucination + 100% date authenticity
- [ ] **DoD-8** Phase 3 Quality Gate Review run + decision documented

---

## Dev Notes

### Why Phase 3 Not Phase 1/2?

**Risk Comparison Matrix:**

| Story | Data Source Reliability | Hallucination Risk | Subjectivity | → Phase |
|-------|------------------------|--------------------|--------------|---------|
| 9.1 Tokenomics | High (CoinGecko deterministic) | Low | Low | 1 |
| 9.4 Yield | High (DeFiLlama deterministic) | Low | Low | 1 |
| 9.2 Whale | Medium (Chainlens-Arkham) | Medium | Medium (phase) | 2 |
| 9.5 Governance | Medium (Chainlens-Snapshot) | Medium | Medium (health) | 2 |
| **9.3 Unlock** | **LOW (uncertain)** | **High (date critical)** | **Low** | **3** |
| 9.6 TA | Low (no clean OHLCV API) | High (pattern recognition) | High | 3 |

→ Story 9.3 và 9.6 cần spike trước; pair lại tách Phase 3.

### Risks Specific to Story 9.3

| Risk | Mitigation |
|------|-----------|
| Chainlens không có TokenUnlocks data | Spike Day 1-2 verifies. Defer story nếu fail |
| Hallucinated unlock dates → user trade wrong date → financial damage | AC7 100% verification + AC11 staleness disclosure mandatory |
| Schedule changes after agent response (project delays unlock) | AC11 always cite "as of date" + suggest user verify |
| Subjective pressure assessment | Provide explicit thresholds in prompt (>5%/30d = HIGH) |

### Testing Commands

```bash
# Token budget
uv run python -c "
import tiktoken
from app.agents.new_chat.subagents.crypto.token_unlock_scheduler_spec import TOKEN_UNLOCK_SCHEDULER_PROMPT
enc = tiktoken.encoding_for_model('gpt-4')
print(f'Tokens: {len(enc.encode(TOKEN_UNLOCK_SCHEDULER_PROMPT))} / 500')
"

# Manual smoke
uv run python tests/manual/test_unlock_scenarios.py
# (3 queries: OP upcoming, AAVE low pressure, ARB historical correlation)
```

### Rollback Plan

`CRYPTO_ORCHESTRA_PHASE3_ENABLED` feature flag. Single-commit revert.

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR29 Token Unlock Scheduler | `prd.md` | AC1, AC5, AC6 |
| FR33 Parallel | `prd.md` | AC9 |
| FR35 Graceful | `prd.md` | AC8 |
| NFR-CS1 Token Budget | `prd.md` | AC2 |
| NFR-CS4 Stateless | `prd.md` | AC4 |
| NFR-Q1 Accuracy | `prd.md` | AC10 |
| NFR-Q2 Parallelism | `prd.md` | AC9 |
| NFR-Q3 Graceful | `prd.md` | AC8 |
| NFR-Q4 Hallucination | `prd.md` | AC7 |

---

**Status**: blocked-on-spike ⚠️ (Spike + Phase 2 quality gate must pass first)
**Next**: Story 9.6 Technical Analyst (Phase 3 pair, also blocked on spike).
