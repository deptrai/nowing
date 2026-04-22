---
storyId: 9.6
storyTitle: Technical Analyst Sub-Agent
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra)
phase: Phase 3 — Spike-Required Tier
sprintPlan: TBD (created sau Phase 2 quality gate review pass + spike DONE)
relatedFRs: [FR32, FR33, FR34, FR35]
relatedNFRs: [NFR-CS1, NFR-CS4, NFR-Q1, NFR-Q2, NFR-Q3, NFR-Q4]
priority: P2 (Phase 3 pair với 9.3 — HIGHEST risk story)
estimatedEffort: 5-7 days (3-5 days spike + 3 days story)
status: blocked-on-spike (cần Story 0.0b Spike trước)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 9.6: Technical Analyst Sub-Agent

## User Story

**As a** crypto trader có short/medium-term trading horizon,
**I want** technical analysis cho 1 token: chart patterns (head & shoulders, double bottom, flags), key support/resistance levels, MA relationships (50/200), RSI overbought/oversold, MACD signals,
**So that** tôi có thể time entries/exits effectively với data-driven signals thay vì random guesses.

---

## Context

Story 9.6 là **Phase 3 pair story** với 9.3 — và là **HIGHEST RISK story trong toàn Crypto Orchestra**.

**Risk factors ranked:**
1. 🔴 **Data source critical gap**: không có free OHLCV (Open/High/Low/Close/Volume) API consistent cho crypto. CoinGecko limited. DexScreener snapshot only.
2. 🔴 **Pattern recognition is hard cho LLM**: head-and-shoulders, cup-and-handle → LLM can fabricate pattern claims
3. 🔴 **Technical indicators require math**: RSI/MACD calculations không thể LLM "guess" từ price number
4. 🔴 **Trader stakes high**: wrong TA → wrong trade → financial damage

**Why Phase 3?** Needs **SPIKE research** trước khi commit scope (tương tự 9.3).

---

## 🚨 PRE-STORY SPIKE — REQUIRED (Different từ 9.3 Spike)

> **Story 9.6 có SPIKE RIÊNG** cần answer:
> 1. OHLCV data source viable? (evaluate: CoinGecko `/ohlc`, TradingView scrape, Binance public API, DexScreener historical)
> 2. TA calculation approach?
>    - Option A: Compute RSI/MACD in a backend tool (deterministic, reliable)
>    - Option B: Delegate to Chainlens với "TA summary" queries (LLM-dependent, less reliable)
>    - Option C: Hybrid — tool computes basic indicators, LLM interprets
> 3. Pattern recognition realistic scope?
>    - Ambitious: visual patterns (H&S, flags) — high hallucination risk
>    - Conservative: only support/resistance + MA crosses + RSI thresholds — deterministic

### Spike Story Spec (Story 0.0b — Pre-Phase 3)

**Effort**: 3-5 days (separate từ Story 0.0 Spike cho 9.3)
**Owner**: Senior dev + Mary

**Spike steps**:
1. **Day 1**: Evaluate OHLCV sources
   - CoinGecko `/coins/{id}/ohlc` (free, limited to ~days/hour granularity)
   - Binance public API (kline endpoints — rate-limited but free)
   - DexScreener (DEX tokens primarily)
2. **Day 2-3**: Prototype Option A (backend TA tool):
   - Build `get_crypto_ta_indicators(symbol, timeframe)` tool
   - Use `pandas-ta` hoặc `ta-lib` library — compute RSI, MACD, MA cross
   - Return structured dict: `{rsi: 72.5, macd_signal: "bullish_cross", ma_50_200: "golden_cross"}`
3. **Day 4-5**: Recommendation memo
   - Option A feasible? → proceed với scope conservative (no visual pattern recognition, only indicators)
   - Option B only? → defer 9.6 hoặc narrow scope drastically
   - Cost estimate (library dep, API rate limits, accuracy test results)

### Pre-flight Checklist (after spike)

- [ ] Spike DONE với OHLCV source selected + TA tool prototype working
- [ ] Phase 2 (Story 9.2 + 9.5) PASS Quality Gates
- [ ] Scope decision: full (patterns + indicators) hoặc conservative (indicators only)
- [ ] Stakeholder approval cho scope decision

---

## Architectural Background

**ASSUMING Option A from spike** (backend TA tool + LLM interpret):

Khác với Phase 2 stories (single-tool Chainlens), 9.6 cần **new tool** từ spike. Add to Epic 0 Story 0.1 list hoặc tạo Story 0.4 "TA Tool Implementation".

### New Tool Required

**File**: `nowing_backend/app/agents/new_chat/tools/crypto_ta.py`

**Tool**: `get_crypto_ta_indicators(symbol: str, timeframe: str = "1d", lookback_days: int = 90)`

**Returns structured dict** (không fabricate, from deterministic calculation):
```python
{
    "symbol": "BTC",
    "timeframe": "1d",
    "current_price_usd": 67_234.56,
    "indicators": {
        "rsi_14": 72.5,  # > 70 = overbought
        "rsi_signal": "overbought",
        "macd": {"line": 125.3, "signal": 98.7, "histogram": 26.6, "cross_type": "bullish"},
        "ma_50": 64_200,
        "ma_200": 58_100,
        "ma_signal": "golden_cross",  # ma_50 > ma_200
    },
    "key_levels": {
        "support_1": 65_000,
        "support_2": 62_500,
        "resistance_1": 69_500,
        "resistance_2": 72_000,
    },
    "trend": {
        "short_term": "bullish",  # 7 days
        "medium_term": "bullish",  # 30 days
        "overall": "bullish",
    },
}
```

Agent (9.6) **interpret** structured dict thành narrative (không calculate, không fabricate).

---

## Deliverables

### 📄 Files to Create

#### 1. `nowing_backend/app/agents/new_chat/tools/crypto_ta.py` (spike prototype → production)

Add to Story 0.1 registry (if spike proceeds với Option A).

#### 2. `nowing_backend/app/agents/new_chat/subagents/crypto/technical_analyst_spec.py`

```python
"""Technical Analyst sub-agent spec."""

TECHNICAL_ANALYST_NAME = "technical_analyst"

TECHNICAL_ANALYST_DESCRIPTION = (
    "Specialist for technical analysis: chart indicators (RSI, MACD, MA), "
    "support/resistance levels, trend classification. Use when user asks "
    "about entry/exit timing, chart signals, or TA-based trade setups."
)

# NFR-CS1: prompt < 500 tokens
TECHNICAL_ANALYST_PROMPT = """You are technical_analyst — a chart analysis specialist.

For any token query:
1. Call get_crypto_ta_indicators(symbol, timeframe) — receives computed indicators
2. Interpret the structured data into narrative:
   - **RSI**: if > 70 = overbought (reversal risk), < 30 = oversold (bounce potential), 30-70 = neutral
   - **MACD**: bullish cross = momentum up, bearish cross = momentum down
   - **MA**: 50 > 200 = golden cross (bullish), 50 < 200 = death cross (bearish)
   - **Support/Resistance**: key price levels to watch for breakouts/breakdowns
3. Short-term outlook (7-30 day horizon): bullish / bearish / neutral với evidence

**Rules (strict):**
- ONLY use numbers từ tool output — NEVER fabricate RSI/MACD/price values
- NEVER invent chart patterns (head & shoulders, cup & handle, etc.) unless tool output explicitly mentions
- Outlook must have evidence: "RSI 72 overbought + MACD bearish cross → bearish short-term"
- Acknowledge limitation: TA is probabilistic, not deterministic. Include "key levels to watch for confirmation/invalidation"

**Output format:**
📊 Current Indicators (RSI, MACD, MA) | 📈 Key Levels (support/resistance) | 🎯 Trend Outlook (short/medium term) | 🚦 Entry/Exit Signals | ⚠️ Invalidation Levels

Keep response concise (< 500 words). Include disclaimer: "TA is one tool among many — combine with fundamental analysis."
"""
```

---

### 📝 Files to Modify

#### 1. `chat_deepagent.py`

```python
from app.agents.new_chat.subagents.crypto.technical_analyst_spec import (
    TECHNICAL_ANALYST_NAME, TECHNICAL_ANALYST_DESCRIPTION, TECHNICAL_ANALYST_PROMPT,
)

technical_analyst_tools = [
    tool for tool in tools
    if tool.name in ("get_crypto_ta_indicators", "chainlens_deep_research")  # chainlens supplementary cho context
]

technical_analyst_spec: SubAgent = {
    "name": TECHNICAL_ANALYST_NAME,
    "description": TECHNICAL_ANALYST_DESCRIPTION,
    "prompt": TECHNICAL_ANALYST_PROMPT,
    "model": llm,
    "tools": technical_analyst_tools,
    "middleware": gp_middleware,
}

# Full Crypto Orchestra — 10 sub-agents tối đa (general + 9 crypto)
SubAgentMiddleware(
    backend=StateBackend,
    subagents=[
        general_purpose_spec,
        defillama_analyst_spec, sentiment_analyst_spec, news_analyst_spec, smart_contract_analyst_spec,
        tokenomics_analyst_spec, yield_optimizer_spec,
        whale_tracker_spec, governance_analyst_spec,
        token_unlock_scheduler_spec,
        technical_analyst_spec,  # Story 9.6 FINAL
    ],
),
```

#### 2. `system_prompt.py` lookup table:
```
| technical_analyst | Chart indicators (RSI, MACD, MA), support/resistance, trend outlook | "TA", "technical analysis", "RSI", "MACD", "support", "resistance", "phân tích kỹ thuật", "biểu đồ" |
```

---

## Acceptance Criteria

### AC1-AC4: Foundation

**AC1**: Spec wired (11 sub-agents total — general + 10 crypto specialists)
**AC2**: Prompt < 500 tokens
**AC3**: Tool scoping (`get_crypto_ta_indicators` + `chainlens_deep_research`)
**AC4**: `requires=[]` cho cả 2 tools (NFR-CS4)

### AC5: TA tool functional

**Given** `get_crypto_ta_indicators(symbol="BTC", timeframe="1d", lookback_days=90)` được gọi
**When** tool execute
**Then** trả về structured dict với indicators RSI, MACD, MA_50, MA_200, support/resistance levels
**And** RSI là float 0-100, MACD có 4 fields (line, signal, histogram, cross_type), MA signal in ["golden_cross", "death_cross", "neutral"]
**And** response time < 10s

### AC6: Functional — Overbought signal

**Given** BTC RSI = 72.5 (overbought)
**When** agent xử lý query "Phân tích kỹ thuật BTC"
**Then** agent interpret RSI 72.5 là overbought
**And** outlook classify bearish hoặc "caution — reversal risk"
**And** mention "support at $65K nếu pullback"
**And** NEVER fabricate RSI/MACD values (phải match tool output exact)

### AC7: Functional — Bullish setup

**Given** ETH có RSI=52, MACD bullish cross, golden_cross MA
**When** agent query
**Then** outlook bullish với evidence chain
**And** recommend "key level to watch: break above $X confirms, fail below $Y invalidates"

### AC8: Hallucination guardrails (NFR-Q4) — HIGHEST stakes story

**Given** agent response với TA numbers
**When** QA verify 100% numbers vs tool output
**Then** 100% numeric values match tool response (no rounding drift)
**And** agent KHÔNG mention patterns không có trong tool (e.g., "head and shoulders forming" when tool chỉ return indicators)
**And** agent KHÔNG fabricate timeframe data (nếu tool chỉ có 1d, không claim "weekly chart shows...")

### AC9: Graceful degradation (NFR-Q3)

**Given** `get_crypto_ta_indicators` fail (data source down)
**When** spawn
**Then** agent fallback Chainlens với query "current BTC technical analysis summary"
**And** response note "full TA indicators unavailable, presenting market context from Chainlens"

**Given** cả 2 tools fail
**When** spawn
**Then** honest response: "TA data currently unavailable. Check TradingView.com/{symbol} directly."

### AC10: Parallel execution (NFR-Q2) — 11 agents (Full Orchestra Final)

**Given** main agent comprehensive query Phase 3 complete
**When** spawn parallel
**Then** 11 agents start trong cùng 1 LangGraph step (general + 10 crypto)
**And** parallelism ratio < 1.3x (ultimate stress test)

### AC11: Accuracy baseline (NFR-Q1) — Numeric precision

**Given** QA sample 50 TA queries
**When** verify indicators match tool output
**Then** factual error rate < 3% (primarily rounding / slight drift)
**And** outlook direction (bullish/bearish/neutral) correctness ≥ 85% manual expert review
**And** NO fabricated chart patterns (AC8 strict)

### AC12: Disclaimer mandatory

**Given** any TA response
**When** inspect tail of response
**Then** ALWAYS include disclaimer:
- "TA is one tool among many — combine with fundamental analysis"
- "Key levels to watch for confirmation/invalidation: ..."
**And** recommend user DYOR (do your own research)

### AC13: Phase 3 Final Quality Gate Review

**Given** Story 9.3 + 9.6 deployed (full 10-agent Crypto Orchestra)
**When** Run ultimate Quality Gate Review (100 queries, mix Rule A/B/C/D)
**Then** all 4 gates pass on FULL 11-agent orchestra:
- NFR-Q1 Accuracy < 3%
- NFR-Q2 Parallelism < 1.3x (11 agents maximum stress)
- NFR-Q3 Graceful > 98%
- NFR-Q4 Hallucination < 1%
**And** decision: 🟢 LAUNCH FULL Crypto Orchestra OR 🟡 Remediate OR 🔴 Rollback

---

## Definition of Done (10 checkpoints)

- [ ] **DoD-0** Spike DONE với Option A prototype working
- [ ] **DoD-1** Pre-flight: Phase 2 quality gate PASS
- [ ] **DoD-2** `crypto_ta.py` tool implemented + registered
- [ ] **DoD-3** `technical_analyst_spec.py` created
- [ ] **DoD-4** `chat_deepagent.py` wires spec (11 sub-agents — FULL orchestra!)
- [ ] **DoD-5** Prompt < 500 tokens
- [ ] **DoD-6** Tool scoping enforced
- [ ] **DoD-7** Integration test: 11-agent parallel, ratio < 1.3x (ultimate stress)
- [ ] **DoD-8** QA: 50-query sample passed accuracy + hallucination + 100% numeric authenticity + 0 fabricated patterns
- [ ] **DoD-9** Phase 3 Final Quality Gate Review — GO/NO-GO decision documented

---

## Dev Notes

### Risks Specific to Story 9.6

| Risk | Mitigation |
|------|-----------|
| No reliable OHLCV API free | Spike Day 1 evaluate. Fallback to paid tier if needed |
| LLM invent "head and shoulders" pattern | Scope conservative (AC8) — NO visual pattern recognition in prompt |
| RSI/MACD calculation errors in tool | Library tested (`pandas-ta` battle-tested) + unit tests trong Story 0.1 expansion |
| User acts on TA → loses money → blames Nowing | AC12 disclaimer mandatory + product legal review |
| 11-agent parallel break ratio < 1.3x (stress) | Telemetry from Story 8.2 + Phase 1/2 provides baseline. Monitor carefully AC10 |

### Testing Commands

```bash
cd nowing_backend

# Tool test
uv run python -c "
import asyncio
from app.agents.new_chat.tools.crypto_ta import create_crypto_ta_indicators_tool
tool = create_crypto_ta_indicators_tool()
result = asyncio.run(tool.ainvoke({'symbol': 'BTC', 'timeframe': '1d'}))
print(result)
"

# Agent smoke test
uv run python tests/manual/test_ta_scenarios.py
# (3 scenarios: BTC overbought, ETH bullish setup, obscure token fallback)
```

### Rollback Plan

`CRYPTO_ORCHESTRA_PHASE3_ENABLED` feature flag (shared với 9.3). Single-commit revert possible.

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR32 Technical Analyst | `prd.md` | AC1, AC5, AC6, AC7 |
| FR33 Parallel | `prd.md` | AC10 |
| FR35 Graceful | `prd.md` | AC9 |
| NFR-CS1 Token Budget | `prd.md` | AC2 |
| NFR-CS4 Stateless | `prd.md` | AC4 |
| NFR-Q1 Accuracy | `prd.md` | AC11 |
| NFR-Q2 Parallelism | `prd.md` | AC10 |
| NFR-Q3 Graceful | `prd.md` | AC9 |
| NFR-Q4 Hallucination | `prd.md` | AC8 (strictest scrutiny) |

---

**Status**: blocked-on-spike ⚠️ (Spike + Phase 2 quality gate must pass + legal disclaimer review)
**Next**: Phase 3 FINAL Quality Gate Review → 🎼 **Crypto Orchestra Full Launch** OR Rollback.
