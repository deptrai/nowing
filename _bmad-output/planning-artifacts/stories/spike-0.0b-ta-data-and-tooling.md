---
storyId: spike-0.0b
storyTitle: SPIKE — TA Data Sources + Tooling Evaluation
type: research-spike
epicParent: epic-09-advanced-crypto-agents (Crypto Orchestra Phase 3)
dependsOn: [Phase 2 Quality Gate Review PASS]
blocks: [9-6-technical-analyst]
estimatedEffort: 3-5 days
status: ready-for-dev (blocked on Phase 2 GO)
priority: P2 (Phase 3 prerequisite — HIGHEST stakes spike)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Spike 0.0b: TA Data Sources + Tooling Evaluation

## Spike Goal

**Decide** (1) OHLCV data source, (2) TA calculation approach (backend tool vs LLM), và (3) realistic scope cho Story 9.6 Technical Analyst.

**Questions to answer**:
1. Có OHLCV data source free/cheap reliable cho top 100 crypto tokens không?
2. Nên compute RSI/MACD/MA server-side (deterministic) hay delegate cho Chainlens/LLM (unreliable)?
3. Pattern recognition (H&S, flags) — scope ambitious hay conservative?

---

## Context

**Story 9.6 là HIGHEST RISK trong toàn Crypto Orchestra** vì:
- Không có free clean OHLCV API cho crypto (như stocks có Yahoo Finance)
- Pattern recognition LLM dễ hallucinate
- Trader stakes cao — wrong TA → financial damage → legal risk

**Spike này quyết định** Story 9.6 có feasible hay không. Có thể outcome là defer indefinitely.

---

## Spike Protocol

### Day 1: Evaluate OHLCV Sources

**Test sources** (queries for BTC, ETH, UNI daily + hourly data 90 days):

#### Option 1: CoinGecko `/coins/{id}/ohlc`
- Endpoint: `https://api.coingecko.com/api/v3/coins/{id}/ohlc?vs_currency=usd&days=30`
- Free tier: 30 req/min
- Pros: Already using CoinGecko, no new auth
- Cons: Limited granularity (daily only, hourly restricted)

#### Option 2: Binance Public API
- Endpoint: `https://api.binance.com/api/v3/klines?symbol={pair}&interval={1h,1d}&limit=500`
- Rate limit: 1200/min IP weight
- Pros: High granularity, free, reliable
- Cons: Chỉ có tokens listed on Binance (subset of universe)

#### Option 3: DexScreener
- Already integrated cho `crypto_realtime.py`
- Historical? Limited to snapshot
- Coverage: DEX tokens primarily

#### Option 4: TradingView scrape
- Legal risk (ToS)
- Fragile
- Skip unless desperate

**Scoring per source** (0-2):
- Coverage (top 50 tokens): 0=limited, 1=partial, 2=comprehensive
- Granularity: 0=daily only, 1=hourly, 2=1m/5m available
- Free tier viable: 0=paid needed, 1=strict limits, 2=generous
- Integration effort: 0=new auth+library, 1=some work, 2=plug-and-play

**Threshold**: Source total ≥ 6/8 → viable primary. Else need backup.

### Day 2-3: Prototype Option A (Backend TA Tool)

**Build**: `nowing_backend/app/agents/new_chat/tools/crypto_ta.py`

**Dependencies**:
- `pandas-ta` hoặc `ta` library (verify license OSS, test coverage)
- `httpx` (existing) cho OHLCV fetch

**Tool signature**:
```python
async def get_crypto_ta_indicators(
    symbol: str,
    timeframe: str = "1d",  # "1h", "4h", "1d"
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Compute TA indicators server-side."""
    # 1. Fetch OHLCV from selected source
    # 2. Compute: RSI_14, MACD (line+signal+histogram), MA_50, MA_200
    # 3. Detect: golden_cross / death_cross, bullish/bearish MACD cross
    # 4. Identify key levels: support (recent lows), resistance (recent highs)
    # 5. Return structured dict
```

**Test với 5 tokens**:
- BTC, ETH (high liquidity — most reliable)
- UNI, AAVE (mid-cap DeFi)
- SOL (L1 with different characteristics)

**Verify accuracy**:
- Cross-check RSI output vs TradingView manual lookup (±0.5 acceptable)
- Cross-check MACD cross detection (golden/death) vs chart visual
- Cross-check support/resistance vs obvious price levels

### Day 4: Decide Pattern Recognition Scope

**Test** — có thể LLM reliably detect patterns không?

Manual experiment: ask Claude/GPT-4 với chart data summary → does it correctly identify H&S / double bottom / flag?

**Expected finding**: LLM **không reliable** cho pattern recognition without vision (chỉ có numeric data). Risk cao vì:
- LLM sẽ fabricate patterns để sound authoritative
- Not verifiable cho QA
- Legal exposure

**Recommended scope**: **Conservative** — skip visual patterns entirely. Focus:
- ✅ Indicators (RSI, MACD, MA)
- ✅ Key levels (support/resistance từ OHLCV data, algorithmic)
- ✅ Trend classification (bullish/bearish/neutral từ MA + momentum)
- ❌ Chart patterns (H&S, cup & handle, flags) — EXCLUDE

### Day 5: Write Recommendation Memo

**Deliverable**: `_bmad-output/research/spike-0.0b-ta-findings.md`

**Memo structure**:
```markdown
# Spike 0.0b — TA Tooling Findings

## TL;DR Recommendation
[Option A backend tool / Option B LLM-only / Option defer]

## OHLCV Source Decision
Selected: [CoinGecko / Binance / hybrid]
Rationale: [...]

## Prototype Tool Results
- RSI accuracy: ±X vs TradingView
- MACD cross detection: X/Y correct
- Library choice: pandas-ta (rationale)

## Pattern Recognition Scope Decision
Recommended: Conservative (indicators only, NO visual patterns)
Rationale: LLM hallucination risk + legal exposure

## Impact on Story 9.6 Scope
- Keep: [indicators list]
- Drop: [patterns list]
- Agent prompt changes: [summary]

## Impact on Story 0.1
- ADD `crypto_ta.py` tool to tool infrastructure
- Retroactive task if Phase 3 proceeds

## Cost Estimate
- Library dep: free (pandas-ta OSS)
- API calls: [rate limit consumption estimate]
- Dev effort: [original estimate vs adjusted]

## Recommended Decision
[Proceed Story 9.6 với conservative scope / Defer / ...]
```

---

## Deliverables

- [ ] Spike findings memo
- [ ] OHLCV source scored + selected
- [ ] Prototype `crypto_ta.py` working (if Option A)
- [ ] Sample RSI/MACD/MA output vs TradingView reference
- [ ] Pattern recognition scope decision với rationale
- [ ] Story 9.6 spec updates (nếu scope changes)
- [ ] Story 0.1 update (nếu thêm crypto_ta tool)

---

## Definition of Done

- [ ] **DoD-1** 3+ OHLCV sources evaluated với scoring
- [ ] **DoD-2** Prototype tool built (Option A) hoặc rationale cho skip
- [ ] **DoD-3** Memo written và shared
- [ ] **DoD-4** Decision meeting: proceed / defer / scope narrow
- [ ] **DoD-5** Story 9.6 spec updated
- [ ] **DoD-6** Story 0.1 updated nếu thêm crypto_ta tool
- [ ] **DoD-7** Legal notified về TA disclaimer requirements (AC12 trong Story 9.6)

---

## Outcome-Driven Success Criteria

| Outcome | Action |
|---------|--------|
| 🟢 Option A (backend tool) viable + conservative scope | Proceed Story 9.6 |
| 🟡 Option A works nhưng OHLCV limited | Narrow scope (fewer tokens supported) |
| 🔴 No viable OHLCV source | **Defer Story 9.6 indefinitely** — launch Phase 3 without TA |
| ⛔ Pattern recognition fundamentally unreliable | Confirm conservative scope (already recommended) |

---

## Why This Spike is Critical

Story 9.6 represents **25% of Phase 3 value** (1 of 2 stories). Nếu spike fail:
- Phase 3 scope reduced to chỉ Story 9.3
- Crypto Orchestra still launches với 10 agents (instead of 11)
- **Product still strong** — 10 agents vẫn là differentiation play significant

**Defer là acceptable outcome** — better defer than launch fabricating TA signals to users.

---

**Status**: ready-for-dev ✅
**Next**: After DONE → Story 9.6 proceeds with selected scope OR defers.
