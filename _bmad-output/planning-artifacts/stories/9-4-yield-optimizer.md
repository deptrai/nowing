---
storyId: 9.4
storyTitle: Yield Optimizer Sub-Agent
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra)
phase: Phase 1 — Quality Foundation
sprintPlan: _bmad-output/planning-artifacts/sprints/sprint-plan-phase1-crypto-orchestra.md
relatedFRs: [FR30, FR33, FR34, FR35]
relatedNFRs: [NFR-CS1, NFR-CS4, NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
priority: P0 (Phase 1 pair với 9.1)
estimatedEffort: 3 days (Mon-Wed Week 2)
status: ready-for-dev (blocked on Epic 0)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 9.4: Yield Optimizer Sub-Agent

## User Story

**As a** DeFi investor có capital nhàn rỗi và risk preference rõ ràng,
**I want** personalized yield recommendations filtered theo risk tolerance (conservative/moderate/aggressive) với automatic security check,
**So that** tôi có thể maximize returns trên idle capital mà không vô tình expose vào honeypots, rugs, hoặc protocols thiếu audit.

---

## Context

Story 9.4 là **Phase 1 pair** với Story 9.1 Tokenomics. Cùng đặc điểm: dùng tools deterministic (DeFiLlama + GoPlus) → easier accuracy baseline. Khác biệt: 9.1 prompt-heavy, 9.4 calculation-heavy (IL risk math).

**Why pair với 9.1**:
- ✅ Cả 2 dùng deterministic APIs → validate accuracy baseline (NFR-Q1 < 3%)
- ✅ Cả 2 high user value (top crypto retail questions)
- ✅ Risk diversification: 1 prompt-heavy (9.1) + 1 calc-heavy (9.4) → test cả 2 patterns
- ✅ Spawn 6 agents parallel (4 base + 9.1 + 9.4) validate scaling trước khi lên 8, 10

---

## 🚨 CRITICAL PREREQUISITE — Code Reality Check

> **Story 9.4 KHÔNG thể start cho đến khi:**
> 1. ✅ **Epic 0** DONE (Story 0.1 tools, 0.2 base specs, 0.3 main prompt)
> 2. ✅ **Epic 0 testing (0.4-0.6)** DONE (Story 0.4 API tests, 0.5 parallel validation, 0.6 error handling)
> 3. ✅ **Story 9.1 Tokenomics** DONE (proves spec pattern works)
>
> **Timeline estimate**: Epic 0 (~2-3 weeks) → Epic 0 testing 0.4-0.6 (~1 week) → Story 9.1 (~3 days) → Story 9.4 (~3 days)

### Pre-flight Checklist

- [ ] Epic 0.1 DONE — `defillama.py` (5 tools), `contract_analysis.py` (`check_token_security`)
- [ ] Epic 0.2 DONE — `SubAgentMiddleware` register 4 base agents
- [ ] Epic 0.3 DONE — main agent system prompt orchestration section
- [ ] Epic 0 testing (0.4-0.6) quality gates pass
- [ ] Story 9.1 DONE và spawned successfully trong production
- [ ] DeFiLlama yields endpoint trả data hợp lệ (verified Story 8.1 AC3)
- [ ] GoPlus security check trả risk_level (verified Story 8.1 AC7)

---

## Architectural Background

Yield Optimizer kế thừa pattern của Story 9.1 (sub-agent với scoped tools), nhưng có **specific business logic** trong system prompt:

1. **Risk filter logic**: 3 levels (conservative/moderate/aggressive) với criteria khác nhau
2. **Impermanent Loss calculation**: cho LP positions, agent phải estimate IL risk dựa trên pair volatility
3. **Security gate**: MỌI recommendation phải pass GoPlus security check trước

**Spec file structure**: identical với `tokenomics_spec.py` (Story 9.1) — 3 constants exported.

---

## Deliverables

### 📄 Files to Create

#### 1. `nowing_backend/app/agents/new_chat/subagents/crypto/yield_optimizer_spec.py` (~50-60 LOC)

```python
"""Yield Optimizer sub-agent spec."""

YIELD_OPTIMIZER_NAME = "yield_optimizer"

YIELD_OPTIMIZER_DESCRIPTION = (
    "Specialist for DeFi yield recommendations filtered by risk preference. "
    "Calculates impermanent loss for LP positions and runs security check on "
    "every protocol before recommending. Use when user asks about yield farming, "
    "passive income, staking opportunities, or where to deploy idle stablecoins."
)

# NFR-CS1: prompt < 500 tokens (verify với tiktoken)
YIELD_OPTIMIZER_PROMPT = """You are yield_optimizer — a DeFi yield specialist.

User provides: capital amount + risk preference (conservative/moderate/aggressive).

**Risk Tier Definitions:**
- Conservative: stablecoin pools only, TVL > $10M, audited protocols, no IL exposure
- Moderate: blue-chip LPs (ETH/BTC/stablecoin pairs), TVL > $5M, max IL ~5%
- Aggressive: high-APY farms accepted, TVL > $1M, accept IL up to ~20%

**Workflow:**
1. Call get_defillama_yields filtered by symbol matching risk tier
2. For LP positions: estimate IL risk dựa trên pair volatility (stable/stable = ~0%, stable/volatile = ~10-20%, volatile/volatile = ~30%+)
3. For each candidate protocol: call check_token_security (GoPlus) — REJECT if risk_level=HIGH or is_honeypot=true
4. Rank survivors by: APY × audit_score / IL_risk_factor
5. Return top 3 recommendations với explicit risk disclosures

**Rules (strict):**
- ALWAYS cite APY from tool output. NEVER fabricate.
- Convert APY to percentage with 2 decimals (5.42%, not 0.0542).
- ALWAYS run security check before recommending — no exceptions.
- If security check fails → exclude protocol AND mention reason ("excluded ABC due to honeypot risk").
- If chainlens_deep_research returns {"status": "fallback"}, use only DeFiLlama data và note limitation.

**Output format:**
🏆 Top 3 Picks (table) | 📈 APY | 🛡️ Security Score | ⚠️ IL Risk | 💰 Min Capital | 💡 Strategy

Keep response concise (< 600 words). Tables preferred for comparison.
"""
```

---

### 📝 Files to Modify

#### 1. `nowing_backend/app/agents/new_chat/chat_deepagent.py`

Pattern identical Story 9.1.

a) **Import**:
```python
from app.agents.new_chat.subagents.crypto.yield_optimizer_spec import (
    YIELD_OPTIMIZER_NAME,
    YIELD_OPTIMIZER_DESCRIPTION,
    YIELD_OPTIMIZER_PROMPT,
)
```

b) **Tool scoping**:
```python
yield_optimizer_tools = [
    tool for tool in tools
    if tool.name in (
        "get_defillama_yields",
        "get_defillama_protocol",
        "check_token_security",
        "chainlens_deep_research",  # supplementary cho protocols mới chưa có DeFiLlama coverage
    )
]
```

c) **Spec construction** (after `tokenomics_analyst_spec`):
```python
yield_optimizer_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": YIELD_OPTIMIZER_NAME,
    "description": YIELD_OPTIMIZER_DESCRIPTION,
    "prompt": YIELD_OPTIMIZER_PROMPT,
    "model": llm,
    "tools": yield_optimizer_tools,
    "middleware": gp_middleware,
}
```

d) **SubAgentMiddleware registration** (extend list):
```python
SubAgentMiddleware(
    backend=StateBackend,
    subagents=[
        general_purpose_spec,
        # 4 Epic 0.2 base specs
        defillama_analyst_spec,
        sentiment_analyst_spec,
        news_analyst_spec,
        smart_contract_analyst_spec,
        # Epic 9 Phase 1 specs
        tokenomics_analyst_spec,  # Story 9.1
        yield_optimizer_spec,      # Story 9.4 (NEW)
    ],
),
```

#### 2. `nowing_backend/app/agents/new_chat/system_prompt.py`

Add lookup table entry (extend Epic 0.3 + Story 9.1 pattern):

```
| yield_optimizer | DeFi yield recommendations by risk tier (conservative/moderate/aggressive), IL risk, security-gated | "yield farm", "passive income", "stake", "earn", "APY", "lãi suất DeFi", "đầu tư stablecoin" |
```

---

## Acceptance Criteria

### AC1: Sub-agent spec created + wired

**Given** Story 9.4 implementation done
**When** inspect `nowing_backend/app/agents/new_chat/subagents/crypto/`
**Then** file `yield_optimizer_spec.py` tồn tại với 3 constants: `YIELD_OPTIMIZER_NAME`, `YIELD_OPTIMIZER_DESCRIPTION`, `YIELD_OPTIMIZER_PROMPT`
**And** `chat_deepagent.py` imports và register `yield_optimizer_spec` trong `SubAgentMiddleware` (now 7 sub-agents total)
**And** server khởi động không error

### AC2: System prompt token budget (NFR-CS1)

**Given** `YIELD_OPTIMIZER_PROMPT` constant
**When** đếm tokens bằng `tiktoken`
**Then** token count **< 500**
**And** unit test verify:
```python
def test_yield_optimizer_prompt_under_budget():
    enc = tiktoken.encoding_for_model("gpt-4")
    assert len(enc.encode(YIELD_OPTIMIZER_PROMPT)) < 500
```

### AC3: Tool scoping enforced

**Given** `yield_optimizer_spec["tools"]`
**When** inspect tool names
**Then** agent CHỈ có access 4 tools: `get_defillama_yields`, `get_defillama_protocol`, `check_token_security`, `chainlens_deep_research`
**And** agent **KHÔNG có access** tới: `get_coingecko_token_info`, `get_crypto_news`, sentiment tools, contract_info, etc.
**And** unit test verify scope:
```python
def test_yield_optimizer_tool_scoping():
    expected = {"get_defillama_yields", "get_defillama_protocol",
                "check_token_security", "chainlens_deep_research"}
    actual = {t.name for t in yield_optimizer_tools}
    assert actual == expected
```

### AC4: Stateless tools (NFR-CS4)

**Given** tool registry entries cho 4 tools yield_optimizer dùng
**When** inspect registry
**Then** cả 4 tools có `requires=[]` (verified Story 0.1 AC2)

### AC5: Functional — Conservative recommendation

**Given** user hỏi "Tôi có 10K USDC, gợi ý yield an toàn"
**When** main agent gọi `task(agent="yield_optimizer", task="...", risk="conservative", capital="$10K USDC")`
**Then** agent:
- Gọi `get_defillama_yields(symbol="USDC", min_tvl=10_000_000)` (conservative TVL filter)
- Filter chỉ stablecoin pools (no LP)
- Run `check_token_security` cho top protocols (e.g., Aave, Compound)
- Trả top 3 recommendations với APY (cite from tool output), TVL, security ✅
- Format output: 🏆 table + 📈 APY + 🛡️ Security + 💡 Strategy

### AC6: Functional — Aggressive với IL calculation

**Given** user hỏi "Tôi có 5K, muốn high APY, chấp nhận risk"
**When** agent xử lý với risk="aggressive"
**Then** agent:
- Gọi `get_defillama_yields` không filter TVL chặt
- Include LP positions (ETH/USDC, BTC/ETH, etc.)
- Estimate IL risk cho mỗi LP (stable/volatile = ~10-20%, volatile/volatile = ~30%+)
- Security check trước recommend
- Output có "⚠️ IL Risk" column với % estimate
- Mention explicitly "high APY trade-off với volatility"

### AC7: Security gate enforced

**Given** scenario: top yield là protocol XYZ với GoPlus risk_level="HIGH"
**When** agent xử lý
**Then** XYZ KHÔNG xuất hiện trong recommendations
**And** agent mention "excluded XYZ due to high security risk: <reason>"
**And** recommend protocol khác thay thế

### AC8: Parallel execution (NFR-Q2)

**Given** main agent nhận "Phân tích toàn diện $UNI" (Rule C — comprehensive)
**When** main agent spawn parallel
**Then** 6 agents start trong cùng 1 LangGraph ToolNode step:
- `defillama_analyst`, `sentiment_analyst`, `news_analyst`, `smart_contract_analyst` (Epic 0.2)
- `tokenomics_analyst` (Story 9.1)
- `yield_optimizer` (Story 9.4 — NEW)
**And** parallelism ratio < 1.3x (NFR-Q2)

### AC9: Accuracy baseline (NFR-Q1) + Hallucination (NFR-Q4)

**Given** QA sample 50 yield queries (mix conservative/moderate/aggressive với various assets: USDC, ETH, BTC, mixed)
**When** QA team cross-check APY claims vs raw DeFiLlama yields response
**Then** factual error rate **< 3%** (APY values match within rounding)
**And** hallucination rate (APY không có trong tool output) **< 1%**
**And** security flags chính xác (verify với GoPlus raw response)

### AC10: Graceful degradation (NFR-Q3)

**Given** GoPlus API trả 500 nhưng DeFiLlama OK
**When** yield_optimizer được spawn
**Then** agent vẫn trả top 3 recommendations dựa trên DeFiLlama data
**And** mention rõ "security score unavailable, please verify protocol audit status manually"
**And** suggest fallback: "audit reports trên DeFiLlama protocol page"

**Given** DeFiLlama yields endpoint 500
**When** yield_optimizer spawn
**Then** agent fallback sang `chainlens_deep_research` query "current DeFi yields for {asset}"
**And** trả response với note về data source limitation

### AC11: IL calculation accuracy

**Given** agent recommend ETH/USDC LP với APY 25%
**When** inspect IL risk estimate
**Then** estimate trong range 5-15% (volatile/stable pair benchmark)
**And** estimate có rationale ("ETH volatility ~50% historical → IL ~10% for 30-day hold")
**And** KHÔNG fabricate exact numbers — use ranges or "estimated"

---

## Definition of Done (9 checkpoints)

- [ ] **DoD-1** Pre-flight: Epic 0, Epic 0 stories 0.4-0.6, Story 9.1 verified DONE
- [ ] **DoD-2** `yield_optimizer_spec.py` created với 3 constants exported
- [ ] **DoD-3** `chat_deepagent.py` import + wire `yield_optimizer_spec` (7 sub-agents total)
- [ ] **DoD-4** System prompt < 500 tokens (unit test pass)
- [ ] **DoD-5** Tool scoping enforced (4 tools, unit test pass)
- [ ] **DoD-6** Integration test: 6-agent parallel spawn works, parallelism ratio < 1.3x
- [ ] **DoD-7** Manual smoke test: 3 risk-tier queries (conservative/moderate/aggressive) trả structured output đúng
- [ ] **DoD-8** QA: 50-query sample passed accuracy < 3% + hallucination < 1% + security gate accuracy 100%
- [ ] **DoD-9** Main agent system prompt updated với lookup table entry

---

## Dev Notes

### Testing Commands

```bash
cd nowing_backend

# Token budget verification
uv run python -c "
import tiktoken
from app.agents.new_chat.subagents.crypto.yield_optimizer_spec import YIELD_OPTIMIZER_PROMPT
enc = tiktoken.encoding_for_model('gpt-4')
count = len(enc.encode(YIELD_OPTIMIZER_PROMPT))
print(f'Token count: {count} / 500')
assert count < 500, f'Prompt exceeds budget: {count}'
"

# Unit tests
uv run pytest tests/unit/agents/new_chat/subagents/crypto/test_yield_optimizer_spec.py -v

# Integration test với 6-agent parallel spawn
uv run pytest -m integration tests/integration/agents/test_phase1_full_orchestra.py::test_phase1_six_agents_parallel -v

# Manual smoke test
uv run python -c "
import asyncio
from app.agents.new_chat.chat_deepagent import create_deepagent

async def main():
    agent = await create_deepagent(user_id='test', search_space_id='test', ...)
    result = await agent.ainvoke({
        'messages': [{'role': 'user', 'content': 'Tôi có 10K USDC, gợi ý yield an toàn'}]
    })
    print(result['messages'][-1]['content'])

asyncio.run(main())
"
```

### IL Calculation Reference (cho LLM context)

Impermanent Loss formula (50/50 pools):
```
IL = 2 × √(price_ratio) / (1 + price_ratio) - 1
```

Với `price_ratio = current_price / entry_price`.

**Approximations cho prompt** (LLM dùng):
- Stable/Stable (USDC/USDT): IL ~ 0%
- Stable/Volatile (USDC/ETH): IL ~ 5-15% per 30 days
- Volatile/Volatile (ETH/BTC): IL ~ 5-10% per 30 days (correlated)
- Volatile/Volatile (ETH/SOL): IL ~ 15-30% per 30 days (uncorrelated)

LLM KHÔNG cần calculate exact — chỉ classify range based on pair type.

### Common Pitfalls

1. ❌ **Đừng** skip security check — agent phải gọi `check_token_security` cho mọi protocol recommend
2. ❌ **Đừng** quote APY mà không cite source (DeFiLlama timestamp)
3. ❌ **Đừng** recommend protocol có `is_honeypot=true` hoặc `risk_level="HIGH"` — exclude với explanation
4. ⚠️ **APY volatility**: yields fluctuate hourly — agent nên mention "as of {timestamp}" trong response
5. ⚠️ **Stablecoin depeg risk**: cho conservative tier, agent nên prefer USDC/USDT over algorithmic stables (UST, FRAX) — built-in vào prompt

### Reference Files

- **Story 9.1 spec** (template): `_bmad-output/planning-artifacts/stories/story-9.1-tokenomics-analyst.md`
- **Wiring location**: `chat_deepagent.py:437-477`
- **Tools used (Story 0.1)**: `nowing_backend/app/agents/new_chat/tools/defillama.py`, `contract_analysis.py`
- **Quality gate validation**: Story 8.2 telemetry (parallelism ratio), Story 8.3 fault injection (graceful degradation)

---

## Rollback Plan

Identical to Story 9.1:
1. **Feature flag** (recommended): `CRYPTO_ORCHESTRA_PHASE1_ENABLED` wrap registration
2. **Git revert**: single commit touching 2-3 files → easy revert
3. **Monitoring**: watch `parallelism_ratio` + `agent_error_rate` + GoPlus call rate (yield_optimizer là heaviest GoPlus user)

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR30 Yield Optimizer | `prd.md` Line ~298 | AC1, AC5, AC6 |
| FR33 Parallel Orchestration | `prd.md` | AC8 |
| FR34 Smart Agent Selection | `prd.md` | AC8 (system prompt routes correctly) |
| FR35 Graceful Degradation | `prd.md` | AC10 |
| NFR-CS1 Token Budget | `prd.md` + `epics.md` | AC2 |
| NFR-CS4 Stateless Tools | `prd.md` + `epics.md` | AC4 |
| NFR-Q1 Accuracy < 3% | `prd.md` Quality Gates | AC9 |
| NFR-Q2 Parallelism < 1.3x | `prd.md` Quality Gates | AC8 |
| NFR-Q3 Graceful > 98% | `prd.md` Quality Gates | AC10 |
| NFR-Q4 Hallucination < 1% | `prd.md` Quality Gates | AC9 |

---

**Status**: done

---

## Review Findings (2026-04-24, bmad-code-review 3-layer)

All 7 patches applied in commit `80ed7888e`.

- [x] [Review][Patch] Undefined ranking variables `audit_score` / `IL_risk_factor` [yield_optimizer_spec.py:33] — rewrote to use only observable tool fields
- [x] [Review][Patch] Chainlens fallback missing workflow trigger [yield_optimizer_spec.py:40] — added step 6 (DeFiLlama error → chainlens_deep_research)
- [x] [Review][Patch] APY unit ambiguity (fractional vs percentage) [yield_optimizer_spec.py:38] — clarified DeFiLlama already returns percentage
- [x] [Review][Patch] Prompt-fidelity test regex silently bypassed yield_optimizer [test_crypto_subagent_wiring.py:281] — broadened regex to match Use/Call/call
- [x] [Review][Patch] Security gate string comparison brittleness [yield_optimizer_spec.py:33] — case-insensitive + truthy
- [x] [Review][Patch] Stale "registers 5 agents" docstring [test_crypto_subagent_wiring.py:4]
- [x] [Review][Patch] Stale "5 task() calls" docstring [test_parallel_execution.py:361]

**Acceptance Auditor verdict**: PASS-WITH-MINOR — AC1-AC4 + AC8 structurally satisfied; AC5-AC7, AC9-AC11 are runtime/QA deferrals (DoD-7, DoD-8).

Token budget after fixes: 484/500 ✅  
Tests: 49 unit tests pass.
**Next**: Phase 1 COMPLETE sau Story 9.4 → Quality Gate Review → Phase 2 (9.2 + 9.5).
