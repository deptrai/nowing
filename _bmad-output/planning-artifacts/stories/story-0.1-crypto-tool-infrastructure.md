---
storyId: 0.1
storyTitle: Core Crypto Tool Infrastructure
epicParent: epic-00-crypto-foundation
blocks: [Story 0.2, Epic 8, Epic 9 Phase 1]
relatedFRs: [FR-C1..FR-C11 internal refs from crypto-subagents-epics.md FR1-FR5]
relatedNFRs: [NFR-CS3, NFR-CS4]
priority: P0 (BLOCKING)
estimatedEffort: 1 week
status: ready-for-dev
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 0.1: Core Crypto Tool Infrastructure

## User Story

**As a** backend developer,
**I want** 4 new crypto tool files + 11 tools registered in the tool registry,
**So that** future sub-agents (Epic 0.2 base + Epic 9 advanced) có thể query DeFiLlama, sentiment sources, news APIs, và contract analysis services.

---

## Context

Story này close **implementation drift** phát hiện trong audit 2026-04-23:
- `crypto-subagents-guide.md` đã document chi tiết 11 tools
- `crypto-subagents-epics.md` đánh dấu "✅ HOÀN THÀNH"
- **Thực tế code**: chỉ có `chainlens_research.py`, `crypto_realtime.py` (DexScreener). Các tools documented chưa tồn tại.

Reference blueprint: `nowing_backend/docs/crypto-subagents-guide.md` — full code mẫu cho tất cả 11 tools.

---

## Deliverables

### 📄 Files to Create (4 files)

#### 1. `nowing_backend/app/agents/new_chat/tools/defillama.py`

**5 tools**:
| Tool | Purpose | Endpoint |
|------|---------|----------|
| `get_defillama_protocol(protocol_slug)` | TVL + chain breakdown cho 1 protocol | `api.llama.fi/protocol/{slug}` |
| `get_defillama_tvl_overview(chain?, limit=20)` | Top protocols by TVL | `api.llama.fi/protocols` |
| `get_defillama_yields(symbol?, min_tvl=?)` | Yield pools sorted by APY | `yields.llama.fi/pools` |
| `get_defillama_stablecoins(limit=20)` | Stablecoins by market cap | `stablecoins.llama.fi/stablecoins` |
| `get_defillama_bridges(limit=20)` | Bridges by volume | `bridges.llama.fi/bridges` |

**Factory pattern** (follow `chainlens_research.py`):
```python
def create_defillama_protocol_tool():
    @tool
    async def get_defillama_protocol(protocol_slug: str) -> dict[str, Any]:
        """..."""
        # Implementation
    return get_defillama_protocol
```

#### 2. `nowing_backend/app/agents/new_chat/tools/crypto_sentiment.py`

**2 tools**:
| Tool | Source | Note |
|------|--------|------|
| `get_cmc_sentiment(symbol)` | `api.alternative.me/fng/` | Fear & Greed Index (free, no auth) |
| `get_reddit_crypto_sentiment(symbol, subreddit, limit=25)` | `reddit.com/r/{sub}/search.json` | Reddit public API (no auth) |

#### 3. `nowing_backend/app/agents/new_chat/tools/crypto_news.py`

**2 tools**:
| Tool | Source | Rate Limit |
|------|--------|-----------|
| `get_crypto_news(currencies, kind="news", limit=20)` | `cryptopanic.com/api/v1/posts/` | Public tier |
| `get_coingecko_token_info(coin_id)` | `api.coingecko.com/api/v3/coins/{id}` | 30 req/min free |

⚠️ `get_coingecko_token_info` critical for Story 9.1 Tokenomics Analyst.

#### 4. `nowing_backend/app/agents/new_chat/tools/contract_analysis.py`

**2 tools**:
| Tool | Source | Note |
|------|--------|------|
| `get_contract_info(contract_address, chain)` | Block explorer API (Etherscan/BscScan/etc.) | Requires `*_API_KEY` env vars |
| `check_token_security(contract_address, chain_id)` | `api.gopluslabs.io/api/v1/token_security/{chain}` | GoPlus — 2000 req/day free |

---

### 📝 File to Modify

#### `nowing_backend/app/agents/new_chat/tools/registry.py`

Register all 11 tools dưới dạng `ToolDefinition`:

```python
# Pattern (check existing registry for exact syntax):
ToolDefinition(
    name="get_defillama_protocol",
    factory=lambda deps: create_defillama_protocol_tool(),
    requires=[],  # NFR-CS4 — stateless
    description="...",
)
```

**All 11 tools MUST have `requires=[]`** (no DB, no session state — NFR-CS4).

---

## Acceptance Criteria

### AC1: Tool files created và import thành công

**Given** 4 tool files được tạo
**When** `from app.agents.new_chat.tools.defillama import *` (tương tự cho 3 file khác)
**Then** import thành công, không SyntaxError/ImportError
**And** mỗi file có ít nhất 1 `create_*_tool()` factory function per tool

### AC2: Registry entries

**Given** `registry.py` được load
**When** inspect `BUILTIN_TOOLS`
**Then** có 11 new `ToolDefinition` entries: `get_defillama_protocol`, `get_defillama_tvl_overview`, `get_defillama_yields`, `get_defillama_stablecoins`, `get_defillama_bridges`, `get_cmc_sentiment`, `get_reddit_crypto_sentiment`, `get_crypto_news`, `get_coingecko_token_info`, `get_contract_info`, `check_token_security`
**And** mỗi entry có `requires=[]` (NFR-CS4)
**And** mỗi entry dùng factory lambda pattern

### AC3: Functional calls — DeFiLlama (no API key needed)

**Given** DeFiLlama API available
**When** gọi `get_defillama_tvl_overview(limit=5)`
**Then** trả về dict với `total_protocols=5`, `protocols` list chứa top 5 by TVL
**And** mỗi protocol có `name`, `category`, `chains`, `tvl`, `change_1d`, `change_7d`
**And** response time < 10s (endpoint payload lớn)

**Given** DeFiLlama protocol endpoint
**When** gọi `get_defillama_protocol(protocol_slug="uniswap")`
**Then** trả về `tvl > 0`, `chains` list, `mcap`, `fdv`, `audit_links`
**And** nếu slug invalid → trả về `{"error": "Protocol 'xyz' not found", "status": 404}`

### AC4: Functional calls — CoinGecko (free tier)

**Given** CoinGecko API available (không bị rate limit)
**When** gọi `get_coingecko_token_info(coin_id="bitcoin")`
**Then** trả về dict với `name="Bitcoin"`, `symbol="BTC"`, `current_price_usd > 0`, `market_cap`, `links` (homepage, twitter, github)
**And** trả về community_data (twitter_followers, reddit_subscribers)

**Given** CoinGecko rate limit exceeded (429)
**When** `get_coingecko_token_info` được gọi
**Then** trả về `{"error": "CoinGecko rate limit reached, try again in 1 minute"}`
**And** KHÔNG raise exception cho caller

### AC5: Functional calls — GoPlus Security

**Given** GoPlus API available
**When** gọi `check_token_security(contract_address="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", chain_id="1")`
**Then** trả về `risk_level` in ["SAFE", "LOW", "MEDIUM", "HIGH"]
**And** response có fields: `is_open_source`, `buy_tax_pct`, `sell_tax_pct`, `holder_count`, `is_honeypot`
**And** response có `risks_detected` list với emoji indicators (🟢/🟡/🔴)

### AC6: Functional calls — CryptoPanic News

**Given** CryptoPanic public API available
**When** gọi `get_crypto_news(currencies="BTC", limit=10)`
**Then** trả về ít nhất 1 article trong `articles` với `title`, `published_at`, `source`, `votes`
**And** `sentiment_signal` object với positive/negative ratio

### AC7: Error handling — graceful degradation

**Given** tool call gặp các failure modes: timeout, 4xx, 5xx, network error
**When** bất kỳ tool nào trong 11 tools được gọi
**Then** trả về `{"error": "<descriptive message>"}` — KHÔNG raise exception
**And** log warning với `exc_info=True` để debugging
**And** agent caller không crash

### AC8: Stateless invariant (NFR-CS4)

**Given** tool được instantiate bởi registry factory
**When** tool được gọi multiple times trong parallel
**Then** không có shared mutable state giữa các calls
**And** không access `config.DATABASE_URL`, session objects, hay workspace context
**And** tool có thể chạy trong Celery worker standalone (không cần FastAPI request context)

---

## Definition of Done (7 checkpoints)

- [ ] **DoD-1** 4 tool files created với tất cả 11 factory functions
- [ ] **DoD-2** `registry.py` register 11 `ToolDefinition` với `requires=[]`
- [ ] **DoD-3** Server khởi động không error (`python -m app.main` hoặc equivalent)
- [ ] **DoD-4** Unit tests: mỗi tool có test happy path + error path (rate limit, 4xx, timeout)
- [ ] **DoD-5** Integration test: 1 real call thành công cho mỗi source (DeFiLlama, CoinGecko, GoPlus, CryptoPanic)
- [ ] **DoD-6** Environment config documented trong `.env.example` (ETHERSCAN_API_KEY, etc. nếu needed)
- [ ] **DoD-7** README section mới trong `docs/` hoặc update `crypto-subagents-guide.md` với implementation status ✅

---

## Dev Notes

### Environment Variables (add to `.env.example`)

```bash
# Required for contract_analysis.py
ETHERSCAN_API_KEY=                # Required for Ethereum contract inspection
BSCSCAN_API_KEY=                  # Optional — BSC chain
POLYGONSCAN_API_KEY=              # Optional — Polygon

# GoPlus (no auth for basic endpoint, but rate-limited to 2000/day)
# CoinGecko (no auth for free tier, 30 req/min)
# DeFiLlama (no auth, unlimited)
# CryptoPanic public API (no auth, but limited)
# Reddit public API (no auth for .json endpoints)
# alternative.me Fear & Greed (no auth)
```

### Testing Commands

```bash
cd nowing_backend

# Unit tests
uv run pytest tests/unit/agents/new_chat/tools/test_defillama.py -v
uv run pytest tests/unit/agents/new_chat/tools/test_crypto_sentiment.py -v
uv run pytest tests/unit/agents/new_chat/tools/test_crypto_news.py -v
uv run pytest tests/unit/agents/new_chat/tools/test_contract_analysis.py -v

# Integration test (real API calls — mark with @pytest.mark.integration)
uv run pytest -m integration tests/integration/test_crypto_tools_live.py -v

# Registry check
uv run python -c "
from app.agents.new_chat.tools.registry import BUILTIN_TOOLS
names = [t.name for t in BUILTIN_TOOLS]
crypto_tools = ['get_defillama_protocol', 'get_defillama_tvl_overview', 'get_defillama_yields',
                'get_defillama_stablecoins', 'get_defillama_bridges', 'get_cmc_sentiment',
                'get_reddit_crypto_sentiment', 'get_crypto_news', 'get_coingecko_token_info',
                'get_contract_info', 'check_token_security']
missing = [t for t in crypto_tools if t not in names]
print(f'Registered: {len(crypto_tools) - len(missing)}/11')
assert not missing, f'Missing tools: {missing}'
"
```

### Common Pitfalls

1. ❌ **Đừng** hardcode API keys — dùng `config.ETHERSCAN_API_KEY` pattern
2. ❌ **Đừng** dùng `requests` sync — phải `httpx.AsyncClient` (non-blocking)
3. ❌ **Đừng** raise exceptions — return `{"error": "..."}` dict
4. ❌ **Đừng** quên `timeout=30` (hoặc phù hợp) cho mọi HTTP calls
5. ⚠️ GoPlus `chain_id` là string Ethereum chain ID (1 = Ethereum, 56 = BSC, 137 = Polygon) — mapping trong tool

### Reference Files

- **Blueprint**: `nowing_backend/docs/crypto-subagents-guide.md` (55KB — section "Bước 2: Tạo tool files")
- **Pattern**: `nowing_backend/app/agents/new_chat/tools/chainlens_research.py`
- **Registry**: `nowing_backend/app/agents/new_chat/tools/registry.py`
- **Existing async HTTP example**: `nowing_backend/app/services/chainlens_research_service.py`

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| 11 crypto tools registered | `crypto-subagents-guide.md` Step 2 | AC1, AC2 |
| NFR-CS3 API rate awareness | `prd.md` + `epics.md` | AC4, AC7 |
| NFR-CS4 Stateless tools | `prd.md` + `epics.md` | AC2, AC8 |
| Graceful error handling | Crypto Orchestra brief | AC7 |

---

**Status**: ready-for-dev ✅
**Next**: Story 0.2 (Base Sub-Agents) starts only after this DONE.
