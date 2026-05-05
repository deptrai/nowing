# Story 10.1.4 — Cohort Taxonomy Re-implementation for TGM Endpoint

**Epic:** 10 — Institutional Research & Risk Management Terminal
**Depends on:** Story 10.1.3 (Out-of-Scope Follow-up — TGM endpoint migration)
**Status:** backlog
**Created:** 2026-05-06
**Why:** Story 10.1.1 spec yêu cầu wallet categorization theo cohorts (`smart_money/cex/dex/retail/insider`). Khi migrate sang Nansen TGM endpoint trong story 10.1.3, taxonomy bị **regression** — code mới chỉ dùng raw `address_label` không phân loại. Cần re-implement để FE color-code Sankey theo cohort + analytics phân tích flow theo cohort type.

---

## Problem Statement

**Story 10.1.1 spec (line 89-91):**
> Định nghĩa transform: source/target = wallet labels (smart_money / cex / dex / retail / insider cohorts), value = USD flow trong 24h.

**Hiện trạng sau migrate TGM endpoint:**
- Tool `get_nansen_smart_money` chỉ trả `address_label` (string raw) — không có category
- Wallet "Binance Hot Wallet" và "a16z Fund" và "Anonymous Whale" đều được render cùng màu trên Sankey
- Analytics impossible: không thể answer "smart money inflow vs CEX outflow"

**Old cohort definitions (reference từ 10.1.1):**
| Cohort | Examples | Significance |
|---|---|---|
| `smart_money` | Funds (a16z, Multicoin), known alpha wallets | High signal — accumulation/distribution by alpha |
| `cex` | Exchange hot/cold wallets (Binance, Coinbase) | Volume noise — usually market-neutral |
| `dex` | DEX router contracts, AMM pools | Volume noise — pass-through |
| `retail` | Small wallets, no labels | Background activity |
| `insider` | Team/treasury wallets, vesting contracts | Critical signal — supply unlocks |

---

## Acceptance Criteria

**AC1 — Cohort field per wallet:**
GIVEN tool trả `smart_money_wallets[]`
THEN mỗi wallet item có thêm `cohort: "smart_money" | "cex" | "dex" | "retail" | "insider" | "unknown"`
AND cohort được derive từ `address_label` heuristics (xem AC4)

**AC2 — Sankey nodes carry cohort metadata:**
GIVEN Sankey được build từ wallets có cohort
THEN node objects có shape `{id, cohort}` thay vì chỉ `{id}`
AND FE `SankeyFlowChart` color-code theo cohort:
  - smart_money: green
  - cex: orange
  - dex: blue
  - retail: gray
  - insider: red
  - unknown: light-gray

**AC3 — Cohort summary trong tool result:**
GIVEN N wallets phân loại theo cohort
THEN tool result có `cohort_summary: {smart_money: {count, net_flow_usd}, cex: {...}, ...}`
AND user/agent có thể dùng để answer "smart money đang accumulate hay distribute?"

**AC4 — Cohort classification heuristic:**
Dùng substring matching trên `address_label` (case-insensitive):
- `cex`: "binance", "coinbase", "kraken", "okx", "bybit", "bitfinex", "kucoin", "huobi", "gate.io", "exchange"
- `dex`: "uniswap", "pancakeswap", "sushiswap", "curve", "balancer", "1inch", "router", "amm"
- `insider`: "team", "treasury", "vesting", "founder", "deployer", "mint"
- `smart_money`: "fund", "capital", "ventures", "a16z", "paradigm", "multicoin", "jump", "wintermute", "dragonfly"
- `retail`: addr-only labels (không có entity name) hoặc labels rất generic
- `unknown`: fallback cho mọi case khác

Heuristic ordered theo priority — `insider` > `cex` > `dex` > `smart_money` > `retail`.

**AC5 — FE color legend:**
Component `SankeyLegend` (mới) hiển thị cohort colors + count khi user hover Sankey.

**AC6 — Backward-compat với Arkham/Dune:**
Arkham `arkhamEntity.type` đã có (fund/whale/cex/exchange) → map trực tiếp:
- `fund`/`whale` → `smart_money`
- `cex`/`exchange` → `cex`
- `dex` → `dex`
- else → `unknown`

Dune rows từ query `7431659` → fallback "unknown" (Dune query không trả type).

---

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `nowing_backend/app/agents/new_chat/tools/nansen_smart_money.py` | UPDATE | Add `_classify_cohort(label)` helper + populate `cohort` field |
| `nowing_backend/app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | Forward cohort qua Sankey nodes; aggregate `cohort_summary` |
| `nowing_backend/app/connectors/arkham_connector.py` | NO CHANGE | Already returns `arkhamEntity.type` |
| `nowing_web/lib/chat/streaming-state.ts` | UPDATE | Add `cohort` to `SankeyNode` type + `cohort_summary` to `SmartMoneyFlowData` |
| `nowing_web/components/crypto/SankeyFlowChart.tsx` | UPDATE | Color-code nodes by cohort |
| `nowing_web/components/crypto/SankeyLegend.tsx` | CREATE | New legend component |
| `nowing_backend/tests/unit/agents/new_chat/tools/test_cohort_classification.py` | CREATE | Unit tests for `_classify_cohort` heuristics |

---

## Tasks/Subtasks

- [ ] Implement `_classify_cohort(label: str) -> str` in `nansen_smart_money.py`
- [ ] Update `get_nansen_smart_money` to populate `cohort` per wallet
- [ ] Update Sankey builder to forward cohort + aggregate `cohort_summary`
- [ ] Map Arkham `arkhamEntity.type` → cohort
- [ ] Update `SankeyNode` type + add `cohort` field
- [ ] Update `SankeyFlowChart` color logic
- [ ] Create `SankeyLegend` component
- [ ] Unit tests for classification heuristic (15+ test cases)
- [ ] E2E test: PEPE Sankey shows green smart_money + orange cex nodes
- [ ] Update story 10.1.3 references nếu cần

---

## Test Plan

```python
# test_cohort_classification.py
@pytest.mark.parametrize("label,expected", [
    ("Binance 14", "cex"),
    ("Uniswap V3 Router", "dex"),
    ("a16z Fund", "smart_money"),
    ("Team Treasury Multisig", "insider"),
    ("0xabc...123", "retail"),
    ("", "unknown"),
    ("Coinbase Cold", "cex"),
    ("PancakeSwap Factory", "dex"),
    ("Multicoin Capital", "smart_money"),
    ("Vesting Contract", "insider"),
])
def test_classify_cohort(label, expected):
    assert _classify_cohort(label) == expected
```

E2E:
1. Hỏi "smart money flow for PEPE"
2. Sankey hiển thị nodes color-coded by cohort
3. Hover legend → tooltip "smart_money: 5 wallets, net_flow $1.2M"

---

## Risks

| Risk | Mitigation |
|---|---|
| Heuristic matching false positives (e.g., "Hummingbot Trader" → matches "bot" → not in keyword list) | Comprehensive test fixture với real Nansen labels từ production data |
| New Nansen labels don't fit existing cohorts | "unknown" fallback + log warning để operators tune heuristic |
| Color blind users can't distinguish cohorts | Add cohort name as suffix in node id; legend always visible |
