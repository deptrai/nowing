# Story 10.1.2 — Nansen Failover: Dune Analytics + Arkham Intelligence

**Epic:** 10 — Institutional Research & Risk Management Terminal  
**Depends on:** Story 10.1.1 (Smart Money Integration — done)  
**Status:** ready-for-dev  
**Created:** 2026-05-05  
**Why:** Nansen API ($49/mo paid tier required) trả 404 cho tokens không có trong index của họ (e.g., PEPE). Cần free-tier fallback để tool `get_smart_money_flow` trả data thay vì empty Sankey.

---

## Problem Statement

`get_smart_money_flow` wraps `get_nansen_smart_money`. Nansen API:
- Requires paid key ($49/mo minimum)
- Returns HTTP 404 for tokens not in their index → tool returns empty wallets → Sankey không hiển thị
- Local dev chạy với `NANSEN_API_KEY=mock-key-for-testing` → luôn 404

Sau fix story 10.1.1 (404 → empty wallets thay vì error), tool hoạt động đúng về logic nhưng Sankey vẫn trống. Cần fallback real data từ free sources.

**Failover chain:**
```
get_smart_money_flow
  └─▶ Nansen (primary)     [NANSEN_API_KEY required, $49/mo]
       └─▶ on empty/error
           └─▶ Arkham (secondary)  [ARKHAM_API_KEY required, free tier via application]
                └─▶ on unavailable
                    └─▶ Dune (tertiary)  [DUNE_API_KEY required, free tier 40 req/min]
```

---

## API Reference Documentation

### 1. Dune Analytics API

**Base URL:** `https://api.dune.com/api/v1`

**Authentication:**
```http
X-Dune-API-Key: <your-api-key>
```
Key tạo tại: Dune UI → Settings → API → Create New API Key  
Env var convention: `DUNE_API_KEY`

**Endpoints:**

```
POST /query/{query_id}/execute
  Body: {"query_parameters": {"token_address": "0x..."}, "performance": "medium"}
  Returns: {"execution_id": "01HKZJ...", "state": "QUERY_STATE_PENDING"}
  Cost: 10 credits (medium), 20 credits (large)

GET /execution/{execution_id}/results
  Returns: paginated rows with "result" → "rows" array

GET /query/{query_id}/results
  Returns last result WITHOUT triggering new execution (no credit cost)
  Use this for polling cached results.
  Params: limit, offset, allow_partial_results
```

**Rate Limits (Free Tier):**
| Endpoint type | Limit |
|---|---|
| Low-limit (write/execute) | 15 req/min |
| High-limit (read/results) | 40 req/min |
| Per-IP | 1000 req/sec |

**Query Result TTL:** 90 days  
**Max result size:** 8 GB (use `allow_partial_results=true` if needed)

**Python SDK:**
```bash
pip install dune-client
```
```python
from dune_client.client import DuneClient
from dune_client.query import QueryBase

dune = DuneClient(api_key=os.getenv("DUNE_API_KEY"))
result = dune.run_query(QueryBase(query_id=3493826, params={"token_address": "0x..."}))
# or fetch cached (no credits):
result = dune.get_latest_result(query_id=3493826)
```

**Parameterized Queries:**
SQL syntax: `WHERE address = {{token_address}}`  
API call: `{"query_parameters": {"token_address": "0x6982508145454Ce325dDbE47a25d4ec3d2311933"}}`

**Recommended Community Query for Smart Money Flow:**

Query ID `3493826` — "Smart Money TOKEN GOD MODE" by decrypto_space  
URL: https://dune.com/decrypto_space/smart-money-token-watcher  
- Accepts `token_address` parameter (EVM address)
- Returns top wallets with P&L, buy/sell activity, labels

> **Note:** Confirm query_id và parameter names trước khi hardcode. Dune community queries có thể bị archived. Backup: viết custom query dựa trên `ethereum.token_transfers` table.

**Custom Fallback SQL (nếu community query unavailable):**
```sql
SELECT
  "from" AS address,
  'seller' AS direction,
  SUM(CAST(value AS DOUBLE) / 1e18) AS token_amount,
  COUNT(*) AS tx_count
FROM ethereum.token_transfers
WHERE contract_address = {{token_address}}
  AND block_time >= NOW() - INTERVAL '24' HOUR
GROUP BY 1
ORDER BY tx_count DESC
LIMIT 20
```

---

### 2. Arkham Intelligence API

**Base URLs:**
```
https://api.arkm.com/         (primary)
https://api.arkhamintelligence.com/  (alternative)
```

**Authentication:**
```http
API-Key: <your-api-key>
```
Đăng ký tại: https://intel.arkm.com/api  
Env var: `ARKHAM_API_KEY`  
**No publicly documented free tier** — requires application approval. Likely freemium.

**Entity/Wallet Labeling:**
```
GET /intelligence/address/{address}/{chain}
  chain: ethereum | bitcoin | solana | all
  Returns: {arkhamEntity: {name, id, type, service, website, twitter, ...}}

GET /intelligence/address/{address}/all
  Returns labels across all chains
```

**Token Transfer/Flow (HEAVY — 1 req/sec):**
```
GET /transfers
  Params:
    flow: "in" | "out" | "all"
    base: entity slug (e.g., "wintermute")
    from: source address
    to: destination address
    timeLast: time range (e.g., "1d", "7d")
    usdGte: minimum USD value filter
    limit: result count
  
  Returns:
  {
    "in": [
      {
        "transactionHash": "0x...",
        "fromAddress": {"address": "0x...", "arkhamEntity": {"name": "...", "type": "fund"}},
        "toAddress": {...},
        "token": {"symbol": "PEPE", "amount": "1000000", "usdAmount": "5000.00"},
        "timestamp": "2025-05-05T12:34:56Z"
      }
    ],
    "out": [...]
  }
```

**Entity Balances:**
```
GET /balances/entity/{entity_slug}
  Returns: real-time token holdings by chain

GET /portfolio/entity/{entity_slug}
  Returns: time-series portfolio history
```

**Rate Limits:**
| Endpoint type | Limit |
|---|---|
| Standard endpoints | 20 req/sec |
| Heavy endpoints (/transfers, /swaps, /counterparties) | 1 req/sec |

**Python (no official Intel SDK — use httpx/aiohttp):**
```python
async with httpx.AsyncClient() as client:
    resp = await client.get(
        "https://api.arkm.com/transfers",
        params={"flow": "all", "timeLast": "1d", "usdGte": 1000},
        headers={"API-Key": os.getenv("ARKHAM_API_KEY")},
    )
```

**Supported Chains:** Ethereum, Polygon, Arbitrum, Base, Optimism, Avalanche, BSC, Bitcoin, Solana, TRON, TON, Dogecoin

---

## Implementation Plan

### Failover Strategy

```python
# crypto_smart_money_flow.py — updated flow:

async def get_smart_money_flow(token_address: str, chain: str = "ethereum"):
    # 1. Resolve symbol → EVM address (existing DexScreener logic)
    # 2. Try Nansen
    res = await _try_nansen(resolved_address)
    if res and res.get("smart_money_wallets"):
        return _build_sankey(res, source="nansen.ai")
    
    # 3. Fallback: Arkham
    if os.getenv("ARKHAM_API_KEY"):
        res = await _try_arkham(resolved_address, chain)
        if res:
            return _build_sankey_from_arkham(res, source="arkm.com")
    
    # 4. Fallback: Dune
    if os.getenv("DUNE_API_KEY"):
        res = await _try_dune(resolved_address)
        if res:
            return _build_sankey_from_dune(res, source="dune.com")
    
    # 5. All failed — empty but valid Sankey
    return {"nodes": [{"id": "Market"}], "links": [], ...}
```

### Files to Create/Modify

| File | Action | Notes |
|---|---|---|
| `app/connectors/arkham_connector.py` | CREATE | httpx-based async client, `get_token_transfers(address, time_last="1d")` |
| `app/connectors/dune_connector.py` | CREATE | httpx-based, execute + poll results. Use `dune-client` SDK or raw HTTP |
| `app/agents/new_chat/tools/crypto_smart_money_flow.py` | UPDATE | Add `_try_arkham()` + `_try_dune()` fallback branches |
| `nowing_backend/pyproject.toml` | UPDATE | Add `dune-client>=0.3.0` dependency |
| `.env.example` | UPDATE | Add `ARKHAM_API_KEY=` và `DUNE_API_KEY=` |
| `tests/unit/agents/new_chat/tools/test_smart_money_fallback.py` | CREATE | Unit tests for each fallback path |

### Sankey Shape Mapping

**Arkham → Sankey:**
```python
def _build_sankey_from_arkham(transfers: dict) -> dict:
    # transfers["in"]  = list of inflow transfers (smart money buying)
    # transfers["out"] = list of outflow transfers (smart money selling)
    nodes = {"Market": True}
    links = []
    for t in transfers.get("in", []):
        entity = t.get("fromAddress", {}).get("arkhamEntity", {})
        label = entity.get("name") or t["fromAddress"]["address"][:8]
        usd = float(t.get("token", {}).get("usdAmount", 0) or 0)
        if usd > 0:
            nodes[label] = True
            links.append({"source": label, "target": "Market", "value": usd})
    for t in transfers.get("out", []):
        entity = t.get("toAddress", {}).get("arkhamEntity", {})
        label = entity.get("name") or t["toAddress"]["address"][:8]
        usd = float(t.get("token", {}).get("usdAmount", 0) or 0)
        if usd > 0:
            nodes[label] = True
            links.append({"source": "Market", "target": label, "value": usd})
    return {"nodes": [{"id": n} for n in nodes], "links": links}
```

**Dune → Sankey:**
```python
def _build_sankey_from_dune(rows: list[dict]) -> dict:
    # rows from custom query: [{address, direction, token_amount, tx_count}]
    nodes = {"Market": True}
    links = []
    for row in rows:
        label = row.get("label") or row["address"][:8]
        amount = float(row.get("usd_amount", row.get("token_amount", 0)) or 0)
        if amount <= 0:
            continue
        nodes[label] = True
        if row["direction"] == "buyer":
            links.append({"source": "Market", "target": label, "value": amount})
        else:
            links.append({"source": label, "target": "Market", "value": amount})
    return {"nodes": [{"id": n} for n in nodes], "links": links}
```

---

## Acceptance Criteria

**AC1 — Nansen primary:**  
GIVEN `NANSEN_API_KEY` valid AND Nansen has data  
THEN `get_smart_money_flow` uses Nansen, returns Sankey with `source_domain="nansen.ai"`

**AC2 — Arkham fallback:**  
GIVEN Nansen returns empty wallets (404 or no data)  
AND `ARKHAM_API_KEY` set  
THEN tool calls Arkham `/transfers`, returns Sankey with `source_domain="arkm.com"`

**AC3 — Dune fallback:**  
GIVEN Nansen empty AND Arkham unavailable/unset  
AND `DUNE_API_KEY` set  
THEN tool calls Dune query, returns Sankey with `source_domain="dune.com"`

**AC4 — Graceful all-fail:**  
GIVEN all three providers unavailable  
THEN tool returns `{"nodes": [{"id": "Market"}], "links": [], ...}` (no error dict)  
AND FE hides Sankey (links.length === 0 guard already in place)

**AC5 — No cross-contamination:**  
Arkham and Dune calls wrapped in try/except — failure of one fallback does NOT prevent next fallback from running.

**AC6 — Circuit breaker scope:**  
Arkham and Dune failures record to their own circuit breaker keys (`"arkham"`, `"dune"`), not `"nansen"`.

**AC7 — Rate limit compliance:**  
Arkham `/transfers` (heavy endpoint) wrapped in `_ApiRateLimiter(max_calls=1, window_seconds=1.0)`.  
Dune execute calls wrapped in `_ApiRateLimiter(max_calls=15, window_seconds=60.0)`.

**AC8 — Source attribution:**  
`source_domain` field in returned dict reflects which provider served the data.  
FE citation badge shows correct source.

---

## Environment Variables

```bash
# .env (local)
NANSEN_API_KEY=           # paid, $49/mo minimum — https://nansen.ai/
ARKHAM_API_KEY=           # free tier via application — https://intel.arkm.com/api
DUNE_API_KEY=             # free tier (40 req/min) — https://dune.com/settings/api
DUNE_SMART_MONEY_QUERY_ID=3493826  # community query ID, verify before use
```

---

## Risk & Caveats

| Risk | Mitigation |
|---|---|
| Dune community query `3493826` archived/changed | Store query_id in env var, fallback to custom SQL query |
| Arkham has no free tier | Document that `ARKHAM_API_KEY` is optional; tool degrades to Dune gracefully |
| Arkham `/transfers` returns exchange flows (not just smart money) | Filter by `entity.type in ["fund", "whale"]` in response processing |
| Dune results stale (last execution N hours ago) | Use `GET /query/{id}/results` first; if >4h old, trigger new execution |
| Dune credits consumed on free tier | Use `get_latest_result` (no credit) before triggering new execution |

---

## Test Plan

```python
# test_smart_money_fallback.py

async def test_nansen_empty_triggers_arkham_fallback():
    # Nansen returns empty wallets, Arkham returns transfers
    ...

async def test_arkham_unavailable_triggers_dune_fallback():
    # Arkham raises exception, Dune returns rows
    ...

async def test_all_providers_fail_returns_empty_sankey():
    # All three fail → nodes=[Market], links=[]
    ...

async def test_arkham_source_domain_set_correctly():
    # Arkham data → source_domain="arkm.com"
    ...

async def test_dune_source_domain_set_correctly():
    # Dune data → source_domain="dune.com"
    ...
```

---

## References

- [Dune API Authentication](https://docs.dune.com/api-reference/overview/authentication)
- [Dune Execute Query](https://docs.dune.com/api-reference/executions/endpoint/execute-query)
- [Dune Get Query Result](https://docs.dune.com/api-reference/executions/endpoint/get-query-result)
- [Dune Rate Limits](https://docs.dune.com/api-reference/overview/rate-limits)
- [Dune Parameterized Queries](https://docs.dune.com/web-app/query-editor/parameters)
- [Dune Python SDK](https://docs.dune.com/api-reference/overview/sdks)
- [Arkham Intel API Docs](https://intel.arkm.com/api/docs)
- [Arkham API Guide](https://api-guide.intel.arkm.com/)
- [Arkham Rate Limits](https://arkm.com/limits-api)
- [Unofficial Arkham API Reference](https://cipher-rc5.github.io/UnofficialArkhamAPI/)
