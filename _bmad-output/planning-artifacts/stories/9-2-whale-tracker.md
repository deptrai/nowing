---
storyId: 9.2
storyTitle: Whale Tracker Sub-Agent
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra)
phase: Phase 2 — Web Research Tier
sprintPlan: TBD (created sau Phase 1 quality gate review pass)
relatedFRs: [FR28, FR33, FR34, FR35]
relatedNFRs: [NFR-CS1, NFR-CS4, NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
priority: P1 (Phase 2 — blocked on Phase 1 GO decision)
estimatedEffort: 3 days
status: ready-for-dev (blocked on Phase 1 quality gate pass)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 9.2: Whale Tracker Sub-Agent

## User Story

**As a** crypto trader,
**I want** to track large wallet movements và smart money flows cho 1 token cụ thể,
**So that** tôi có thể identify accumulation phase (whales mua = bullish signal) hoặc distribution phase (whales bán = bearish signal) early — trước khi price action confirm.

---

## Context

Story 9.2 là **Phase 2 lead** (cùng với Story 9.5 Governance). Phase 2 đặc trưng: **web research–based** (Chainlens deep dive vào Arkham/Nansen/Etherscan) thay vì deterministic API tier như Phase 1.

**Why Phase 2 (không phải Phase 1)?**
- ❌ Không có deterministic API miễn phí cho whale data — Arkham/Nansen đều paid + complex auth
- ✅ Chainlens B2B đã wrapped — 1 tool call lấy synthesized whale insights
- ⚠️ Quality gate dependency: Phase 2 chỉ start sau Phase 1 đạt 4 Quality Gates (proves orchestration works)

**Why pair với Story 9.5 Governance?**
- Cả 2 đều **Chainlens-heavy** (medium prompt engineering effort)
- Cả 2 cho actionable signals (whale flows ~ governance votes ~ market moves)
- Validate Chainlens success rate ở scale (2 agents cùng dùng nhiều)

---

## 🚨 CRITICAL PREREQUISITE

> **Story 9.2 KHÔNG thể start cho đến khi:**
> 1. ✅ **Epic 0** DONE (foundation)
> 2. ✅ **Epic 0 testing (0.4-0.6)** DONE
> 3. ✅ **Story 9.1 + 9.4** DONE và **PASS 4 Quality Gates** trong Phase 1 review
> 4. ✅ Chainlens success rate trong Phase 1 production > 95% (proves Chainlens reliable enough for Phase 2 reliance)

### Pre-flight Checklist

- [ ] Phase 1 Quality Gate Review: PASS (NFR-Q1 < 3%, NFR-Q2 < 1.3x, NFR-Q3 > 98%, NFR-Q4 < 90s)
- [ ] Chainlens success rate trong Phase 1 production > 95% (telemetry verified)
- [ ] Chainlens has access cho data sources: Arkham, Nansen, Etherscan token holders (verified với Chainlens team hoặc test queries)
- [ ] Phase 2 sprint plan generated (Mary tạo sau Phase 1 GO decision)

**Nếu BẤT KỲ item nào FAIL** → KHÔNG start Phase 2. Investigate root cause Phase 1 fail trước.

---

## Architectural Background

Whale Tracker khác Phase 1 agents ở **single primary tool**: chỉ dùng `chainlens_deep_research` (không có deterministic API alternative).

**Risk consequence**: nếu Chainlens down → agent không có fallback ngoài "data unavailable" message. → Need NFR-Q3 graceful degradation strict.

**Spec file structure**: identical pattern (Story 9.1, 9.4) — 3 constants exported.

---

## Deliverables

### 📄 Files to Create

#### `nowing_backend/app/agents/new_chat/subagents/crypto/whale_tracker_spec.py` (~50-60 LOC)

```python
"""Whale Tracker sub-agent spec."""

WHALE_TRACKER_NAME = "whale_tracker"

WHALE_TRACKER_DESCRIPTION = (
    "Specialist for tracking large wallet movements and smart money flows. "
    "Identifies accumulation/distribution phases by analyzing on-chain whale "
    "behavior. Use when user asks about whale activity, smart money, large "
    "transfers, or institutional flow signals."
)

# NFR-CS1: prompt < 500 tokens
WHALE_TRACKER_PROMPT = """You are whale_tracker — a specialist in on-chain whale analysis.

For any token query, investigate:
1. **Known whale wallets**: exchanges (Binance, Coinbase, Kraken), funds (a16z, Paradigm), insiders (team/foundation), market makers (Wintermute, GSR)
2. **Inflow/outflow patterns** (last 7-30 days): which addresses receiving/sending large amounts?
3. **Phase classification**:
   - Accumulation: whales net-buying, slow inflow to cold wallets, low exchange deposits
   - Distribution: whales net-selling, exchange deposits spike, derivatives funding flips
   - Neutral: balanced flows, no clear signal
4. **Smart money signal**: are addresses with historical alpha (early Uniswap LP, NFT flippers) currently entering/exiting?

**Workflow:**
- Always use chainlens_deep_research với specific queries:
  - "{token} whale wallet activity last 30 days Arkham"
  - "{token} top holders distribution Nansen"
  - "{token} large transfers Etherscan"
- If chainlens returns {"status": "fallback"} → respond "Whale data currently unavailable, please check Arkham.com or Nansen.ai directly"

**Rules (strict):**
- ALWAYS cite specific addresses (truncated 0xabc...123) when mentioning whale activity
- NEVER fabricate wallet addresses, transfer amounts, or phase classification
- Quantify: "Top 10 whales hold X% of supply" not "many whales hold a lot"
- Flag uncertainty: "Chainlens data limited to public sources" when applicable

**Output format:**
🐋 Whale Activity Summary | 📊 Phase Classification | 💸 Net Flow (7d/30d) | 🎯 Smart Money Signal | ⚠️ Risk Flags | 💡 Trader Insight

Keep response concise (< 600 words). Tables preferred for top wallets list.
"""
```

---

### 📝 Files to Modify

Pattern identical Story 9.1 + 9.4:

#### 1. `chat_deepagent.py`

```python
from app.agents.new_chat.subagents.crypto.whale_tracker_spec import (
    WHALE_TRACKER_NAME, WHALE_TRACKER_DESCRIPTION, WHALE_TRACKER_PROMPT,
)

whale_tracker_tools = [
    tool for tool in tools
    if tool.name in ("chainlens_deep_research",)
]

whale_tracker_spec: SubAgent = {
    "name": WHALE_TRACKER_NAME,
    "description": WHALE_TRACKER_DESCRIPTION,
    "prompt": WHALE_TRACKER_PROMPT,
    "model": llm,
    "tools": whale_tracker_tools,
    "middleware": gp_middleware,
}

# Add to SubAgentMiddleware list (now 8 sub-agents)
SubAgentMiddleware(
    backend=StateBackend,
    subagents=[
        general_purpose_spec,
        defillama_analyst_spec,
        sentiment_analyst_spec,
        news_analyst_spec,
        smart_contract_analyst_spec,
        tokenomics_analyst_spec,
        yield_optimizer_spec,
        whale_tracker_spec,  # Story 9.2 NEW
    ],
),
```

#### 2. `system_prompt.py` lookup table:
```
| whale_tracker | Large wallet movements, smart money flows, accumulation/distribution phases | "whale", "smart money", "large transfer", "institutional", "ai mua nhiều", "cá voi" |
```

---

## Acceptance Criteria

### AC1-AC4: Foundation (identical Story 9.1/9.4)

**AC1**: Spec file created với 3 constants + wired trong `SubAgentMiddleware` (8 agents total)
**AC2**: System prompt < 500 tokens (`tiktoken` test)
**AC3**: Tool scoping enforced — chỉ `chainlens_deep_research`
**AC4**: `requires=[]` cho tool entry (NFR-CS4)

### AC5: Functional — Accumulation phase detection

**Given** user hỏi "Whale activity của $UNI tuần này"
**When** main agent spawn `whale_tracker`
**Then** agent gọi `chainlens_deep_research` với queries về UNI whale wallets
**And** trả response có 6 sections theo prompt format: 🐋 Summary, 📊 Phase, 💸 Net Flow, 🎯 Smart Money, ⚠️ Risk, 💡 Insight
**And** mention specific wallet addresses (truncated 0xabc...123)
**And** classify phase: accumulation / distribution / neutral với rationale

### AC6: Functional — Distribution phase scenario

**Given** user hỏi "Cá voi đang bán $XYZ không?" (token có exchange inflow spike)
**When** agent xử lý
**Then** agent identify "distribution phase" với evidence:
- Exchange deposits increased X%
- Top 10 holders concentration changed
- Derivative funding rates shifted
**And** quantify metrics (% supply moved, $ value transferred)

### AC7: Hallucination guardrails (NFR-Q4)

**Given** agent response với wallet addresses và amounts
**When** QA verify vs raw Chainlens output
**Then** 100% addresses mentioned exist trong Chainlens response (no fabrication)
**And** 100% transfer amounts match raw data (within rounding)
**And** phase classification có evidence trace từ tool output

### AC8: Graceful degradation (NFR-Q3) — Chainlens fallback critical

**Given** Chainlens trả `{"status": "fallback"}` (Chainlens API down)
**When** whale_tracker được spawn
**Then** agent KHÔNG fabricate whale data
**And** trả response ngắn gọn: "Whale data currently unavailable. Please check Arkham.com hoặc Nansen.ai trực tiếp."
**And** suggest user thử lại sau 5-10 phút
**And** main agent (parent) nhận response này và mention trong final aggregation

### AC9: Parallel execution (NFR-Q2) — 8 agents

**Given** main agent nhận "Phân tích toàn diện $UNI" (Phase 2 active)
**When** main agent spawn parallel
**Then** 8 agents start trong cùng 1 LangGraph ToolNode step:
- 4 base (Epic 0.2)
- Phase 1: tokenomics_analyst, yield_optimizer
- Phase 2: whale_tracker (NEW), governance_analyst (Story 9.5)
**And** parallelism ratio < 1.3x

### AC10: Accuracy baseline (NFR-Q1)

**Given** QA sample 50 whale queries trên top tokens (BTC, ETH, UNI, AAVE, SOL, DOGE)
**When** QA cross-check agent claims vs Chainlens raw response + manual Arkham verification
**Then** factual error rate **< 3%**
**And** phase classification correctness ≥ 90% (manual market context check)

### AC11: Quantification quality

**Given** agent response mentions whale activity
**When** inspect language style
**Then** specific quantification present:
- "Top 10 whales hold 23% of supply" ✅
- NOT "many whales hold a lot" ❌
- "Net inflow $5.2M last 7 days" ✅
- NOT "lots of money flowing in" ❌

---

## Definition of Done (8 checkpoints)

- [ ] **DoD-1** Pre-flight: Phase 1 quality gate PASS + Chainlens success rate > 95%
- [ ] **DoD-2** `whale_tracker_spec.py` created
- [ ] **DoD-3** `chat_deepagent.py` wires spec (8 sub-agents total)
- [ ] **DoD-4** System prompt < 500 tokens (test pass)
- [ ] **DoD-5** Tool scoping (chỉ chainlens_deep_research)
- [ ] **DoD-6** Integration test: 8-agent parallel spawn, ratio < 1.3x
- [ ] **DoD-7** QA: 50-query sample passed accuracy < 3% + hallucination < 1% + 100% address authenticity
- [ ] **DoD-8** Manual smoke test: 3 scenarios (accumulation/distribution/neutral) trả correctly classified responses

---

## Dev Notes

### Risks Specific to Story 9.2

| Risk | Mitigation |
|------|-----------|
| Chainlens không có Arkham access → agent thiếu data | Pre-flight verify với Chainlens team. Nếu fail, defer Story 9.2 hoặc seek alternative |
| LLM hallucinate wallet addresses (no factual grounding) | Strict prompt: "ONLY mention addresses returned in tool output". QA AC7 verify 100% authenticity |
| Phase classification subjective → low accuracy gate fail | Provide explicit criteria trong prompt (exchange deposits %, holder concentration delta). QA manual review |
| Chainlens latency cao cho deep whale queries (~60-90s) | Adjust NFR-Q4 expectation cho whale_tracker individual time. 8-agent parallel still < 90s tổng |

### Testing Commands

```bash
cd nowing_backend

# Token budget
uv run python -c "
import tiktoken
from app.agents.new_chat.subagents.crypto.whale_tracker_spec import WHALE_TRACKER_PROMPT
enc = tiktoken.encoding_for_model('gpt-4')
print(f'Tokens: {len(enc.encode(WHALE_TRACKER_PROMPT))} / 500')
"

# Manual smoke
uv run python -c "
import asyncio
from app.agents.new_chat.chat_deepagent import create_deepagent
async def main():
    agent = await create_deepagent(...)
    result = await agent.ainvoke({'messages': [{'role': 'user', 'content': 'Whale activity của UNI tuần này'}]})
    print(result['messages'][-1]['content'])
asyncio.run(main())
"
```

### Rollback Plan

Identical Story 9.1/9.4: feature flag `CRYPTO_ORCHESTRA_PHASE2_ENABLED`, single-commit revert, watch parallelism ratio.

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR28 Whale Tracker | `prd.md` | AC1, AC5, AC6 |
| FR33 Parallel | `prd.md` | AC9 |
| FR35 Graceful | `prd.md` | AC8 |
| NFR-CS1 Token Budget | `prd.md` | AC2 |
| NFR-CS4 Stateless | `prd.md` | AC4 |
| NFR-Q1 Accuracy | `prd.md` | AC10 |
| NFR-Q2 Parallelism | `prd.md` | AC9 |
| NFR-Q3 Graceful | `prd.md` | AC8 |
| NFR-Q4 Hallucination | `prd.md` | AC7 |

---

**Status**: ready-for-dev ✅ (blocked on Phase 1 quality gate pass)
**Next**: Story 9.5 Governance Analyst (Phase 2 pair).
