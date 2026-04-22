---
storyId: 0.4
storyTitle: API Integration Tests (Crypto Tools Live Validation)
epicParent: epic-00-crypto-foundation
dependsOn: [Story 0.1, 0.2, 0.3 DONE]
blocks: [Story 0.5, Story 0.6, Epic 9 Phase 1]
relatedFRs: [FR-T1]
relatedNFRs: [NFR-CS3 API rate awareness, NFR-Q3 graceful degradation]
priority: P0 (BLOCKING Phase 1)
estimatedEffort: 2-3 days
status: ready-for-dev (blocked on Epic 0)
createdAt: 2026-04-23
author: Mary (Strategic Business Analyst)
---

# Story 8.1: API Integration Tests — Crypto Tools Live Validation

## User Story

**As a** developer,
**I want** to verify each crypto tool connects to its real API correctly and handles real-world response shapes/errors,
**So that** I know the integration works before production deployment, và downstream sub-agents (Epic 9 Phase 1) có foundation đáng tin cậy.

---

## Context

Story 0.4 là bước validate đầu tiên sau khi implement Foundation (Stories 0.1-0.3). Story 0.4 specifically validate **tool-level integration** — không test agent behavior (đó là Story 0.5), không test error handling (Story 0.6).

Mục tiêu: **100% of 11 crypto tools** (implemented in Story 0.1) phải trả đúng data structure khi gọi real APIs, hoặc graceful error khi API fail.

---

## Prerequisites

### Pre-flight Checklist (Dev verify trước khi start)

- [ ] **Epic 0 Story 0.1 DONE**: `defillama.py`, `crypto_sentiment.py`, `crypto_news.py`, `contract_analysis.py` tồn tại với 11 tools
- [ ] **Epic 0 Story 0.1 DoD-5 pass**: Có ít nhất 1 integration test cho mỗi source (DeFiLlama, CoinGecko, GoPlus, CryptoPanic)
- [ ] Environment vars configured: `ETHERSCAN_API_KEY` (nếu `get_contract_info` cần)
- [ ] Network available: test machine có outbound internet

**Nếu BẤT KỲ item nào FAIL** → không start Story 8.1.

---

## Deliverables

### 📄 Files to Create

#### 1. `nowing_backend/tests/integration/tools/test_crypto_tools_live.py`

**Purpose**: Integration test suite gọi real APIs cho tất cả 11 crypto tools. Chạy trên CI khi có flag `@pytest.mark.integration` (không chạy mặc định để tránh CI rate limit).

**Structure template**:

```python
"""Integration tests for crypto tools — real API calls.

Run với: `pytest -m integration tests/integration/tools/test_crypto_tools_live.py -v`
DO NOT run trong unit test CI — gọi external APIs, rate-limit sensitive.
"""
import pytest

pytestmark = pytest.mark.integration


class TestDeFiLlamaLive:
    """5 DeFiLlama tools — no auth, unlimited rate."""

    async def test_get_defillama_tvl_overview_returns_top_protocols(self):
        from app.agents.new_chat.tools.defillama import create_defillama_tvl_overview_tool
        tool = create_defillama_tvl_overview_tool()
        result = await tool.ainvoke({"limit": 5})
        # AC1 assertions
        ...

    async def test_get_defillama_protocol_uniswap(self):
        ...

    async def test_get_defillama_yields_stablecoins(self):
        ...

    async def test_get_defillama_stablecoins_by_mcap(self):
        ...

    async def test_get_defillama_bridges_by_volume(self):
        ...


class TestCoinGeckoLive:
    """CoinGecko — 30 req/min free tier."""

    async def test_get_coingecko_token_info_bitcoin(self):
        ...

    async def test_get_coingecko_rate_limit_returns_error_dict(self):
        # Can't force 429 easily — skip or mock
        pytest.skip("Can't reliably trigger 429 in integration test")


class TestGoPlusLive:
    """GoPlus Security — 2000 req/day free."""

    async def test_check_token_security_uniswap_uni(self):
        ...


class TestCryptoPanicLive:
    """CryptoPanic — public tier, rate-limited."""

    async def test_get_crypto_news_btc_articles(self):
        ...


class TestSentimentLive:
    """Fear & Greed + Reddit."""

    async def test_get_cmc_sentiment_fng_index(self):
        ...

    async def test_get_reddit_crypto_sentiment_btc(self):
        ...


class TestContractAnalysisLive:
    """Etherscan — requires ETHERSCAN_API_KEY."""

    async def test_get_contract_info_uniswap_v3(self):
        import os
        if not os.getenv("ETHERSCAN_API_KEY"):
            pytest.skip("ETHERSCAN_API_KEY not configured")
        ...
```

#### 2. `nowing_backend/tests/integration/tools/conftest.py`

Shared fixtures: retry logic cho flaky APIs, timeout settings.

```python
import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async integration tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def api_retry_delay():
    """Sleep between API calls to respect free-tier limits."""
    return 2.5  # seconds between CoinGecko calls (30/min limit)
```

### 📝 Files to Modify

#### `nowing_backend/pyproject.toml` (hoặc `pytest.ini`)

Add marker registration:
```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
]
```

#### `.github/workflows/` hoặc CI config

Add separate job chạy `pytest -m integration` với schedule (weekly hoặc manual trigger), không phải every PR.

---

## Acceptance Criteria

### AC1: DeFiLlama TVL Overview

**Given** DeFiLlama API available
**When** gọi `get_defillama_tvl_overview(limit=5)`
**Then** trả về dict với key `top_protocols` chứa list 5 protocols
**And** mỗi protocol có `tvl_usd > 0`, `name` (string), `category` (string), `chains` (list)
**And** response time < 10 giây (endpoint `/protocols` payload lớn)

### AC2: DeFiLlama Protocol Detail

**Given** DeFiLlama API available
**When** gọi `get_defillama_protocol(protocol_slug="uniswap")`
**Then** trả về `tvl_usd > 0`, `chains` list non-empty, `mcap > 0`, `audit_links` (có thể empty list nhưng key phải tồn tại)
**And** response có `change_1d`, `change_7d` (float, có thể negative)

**Given** invalid slug
**When** gọi `get_defillama_protocol(protocol_slug="nonexistent-xyz")`
**Then** trả về `{"error": "Protocol 'nonexistent-xyz' not found"}` hoặc tương tự
**And** KHÔNG raise exception

### AC3: DeFiLlama Yields

**Given** DeFiLlama yields endpoint
**When** gọi `get_defillama_yields(symbol="USDC", min_tvl=1000000)`
**Then** trả về list pools với `apy > 0`, `tvl_usd >= 1000000`, `symbol="USDC"`, `project` (protocol name)
**And** ít nhất 3 pools trong kết quả

### AC4: DeFiLlama Stablecoins + Bridges

**Given** DeFiLlama stablecoins endpoint
**When** gọi `get_defillama_stablecoins(limit=10)`
**Then** trả về top 10 stablecoins by market cap với `symbol`, `mcap`, `peg_mechanism`

**Given** DeFiLlama bridges endpoint
**When** gọi `get_defillama_bridges(limit=5)`
**Then** trả về top 5 bridges với `name`, `volume_24h`, `chains`

### AC5: CoinGecko Token Info

**Given** CoinGecko API available (within rate limit — 30 req/min)
**When** gọi `get_coingecko_token_info(coin_id="bitcoin")`
**Then** trả về `name="Bitcoin"`, `symbol="BTC"` (hoặc "btc" case-insensitive), `current_price_usd > 0`
**And** response có `market_cap_usd > 0`, `total_supply` (có thể null), `circulating_supply > 0`
**And** response có `links` dict với `homepage`, `twitter_screen_name`, `subreddit`
**And** response có `community_data` với `twitter_followers`, `reddit_subscribers`

### AC6: CoinGecko Invalid ID

**Given** CoinGecko API
**When** gọi `get_coingecko_token_info(coin_id="xyz-nonexistent-token-id")`
**Then** trả về `{"error": "Token 'xyz-...' not found on CoinGecko"}` hoặc tương tự
**And** không raise exception

### AC7: GoPlus Security (Ethereum UNI)

**Given** GoPlus API available
**When** gọi `check_token_security(contract_address="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", chain_id="1")` (UNI token trên Ethereum mainnet)
**Then** trả về `risk_level` in ["SAFE", "LOW", "MEDIUM", "HIGH"]
**And** response có fields: `is_open_source` (bool), `buy_tax_pct` (float), `sell_tax_pct` (float), `holder_count` (int > 0), `is_honeypot` (bool)
**And** response có `risks_detected` (list of strings, có thể empty cho UNI)

**Given** GoPlus API — invalid address
**When** gọi `check_token_security(contract_address="0xinvalid", chain_id="1")`
**Then** trả về `{"error": "..."}` — KHÔNG raise exception

### AC8: CryptoPanic News

**Given** CryptoPanic public API available
**When** gọi `get_crypto_news(currencies="BTC", limit=10)`
**Then** trả về dict với key `articles` chứa list non-empty
**And** mỗi article có: `title` (string), `url` (string), `published_at` (ISO datetime), `source` (dict với `title`), `votes` (dict với `positive`, `negative`, `important`)
**And** response có `sentiment_signal` object với `positive_count`, `negative_count`, `net_sentiment`

### AC9: Fear & Greed Index

**Given** alternative.me API available
**When** gọi `get_cmc_sentiment(symbol="BTC")`
**Then** trả về dict với `fng_value` (int 0-100), `fng_classification` in ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
**And** response có `timestamp` (unix epoch)

### AC10: Reddit Crypto Sentiment

**Given** Reddit public API (.json endpoints)
**When** gọi `get_reddit_crypto_sentiment(symbol="BTC", subreddit="cryptocurrency", limit=25)`
**Then** trả về dict với `posts` (list non-empty), `average_upvote_ratio` (float 0-1), `total_comments` (int >= 0)
**And** mỗi post có `title`, `score`, `num_comments`, `permalink`

### AC11: Etherscan Contract Info (conditional)

**Given** `ETHERSCAN_API_KEY` configured trong env
**When** gọi `get_contract_info(contract_address="0xE592427A0AEce92De3Edee1F18E0157C05861564", chain="ethereum")` (Uniswap V3 Router)
**Then** trả về `contract_name` (string), `is_verified` (bool True), `compiler_version` (string), `source_code_available` (bool)

**Given** env var missing
**When** tool được invoke
**Then** trả về `{"error": "ETHERSCAN_API_KEY not configured"}` hoặc skip test với pytest.skip

### AC12: Registry Integration Smoke Test

**Given** `registry.py` đã register 11 tools
**When** instantiate tools qua registry factory
**Then** mỗi tool có thể invoke với valid input và trả data hoặc `{"error": ...}`
**And** integration test verify all 11 tools đều phản hồi (pass hoặc graceful error) — KHÔNG tool nào crash Python process

---

## Definition of Done (7 checkpoints)

- [ ] **DoD-1** Pre-flight: Epic 0 Story 0.1-0.3 verified DONE
- [ ] **DoD-2** Test file created với 12 test cases (AC1-AC12)
- [ ] **DoD-3** `pyproject.toml` đăng ký `integration` marker
- [ ] **DoD-4** Tất cả 12 tests pass trên local dev (1 run thành công)
- [ ] **DoD-5** CI config thêm manual/scheduled job cho `pytest -m integration`
- [ ] **DoD-6** Test report artifact: file JSON/HTML lưu result cho audit (optional)
- [ ] **DoD-7** Documentation trong `tests/integration/README.md`: how to run, expected API keys, rate limit notes

---

## Dev Notes

### Testing Commands

```bash
cd nowing_backend

# Run all integration tests (requires internet + API keys)
uv run pytest -m integration tests/integration/tools/test_crypto_tools_live.py -v

# Run single test class
uv run pytest -m integration tests/integration/tools/test_crypto_tools_live.py::TestDeFiLlamaLive -v

# Skip integration tests (default for CI)
uv run pytest -m "not integration" tests/

# Run với verbose output và stop on first failure
uv run pytest -m integration -v -x tests/integration/tools/test_crypto_tools_live.py
```

### Rate Limit Handling Strategy

Để tránh flaky tests vì rate limit:

1. **CoinGecko** (30 req/min): Sleep 2.5s giữa mỗi test call. Chỉ 1 test gọi CoinGecko (AC5).
2. **GoPlus** (2000 req/day): Không vấn đề cho dev testing.
3. **CryptoPanic** (public tier): 1 test (AC8) — acceptable.
4. **DeFiLlama** (unlimited): Không lo.
5. **Reddit** (public .json): Self-regulates qua User-Agent header.
6. **Etherscan** (5 calls/sec free): Sleep 250ms nếu cần.

### Common Pitfalls

1. ❌ **Đừng** commit real API keys vào test files — dùng env vars
2. ❌ **Đừng** assert chính xác số liệu (e.g., BTC price = $70000) — market data fluctuate; assert `> 0` hoặc structure only
3. ❌ **Đừng** chạy integration tests trong CI mỗi PR — setup scheduled job hoặc manual trigger
4. ⚠️ **Watch for**: Some tools trả empty lists thay vì errors cho valid-but-no-data queries → test phải handle cả 2 cases
5. ⚠️ **Timezone**: CryptoPanic trả `published_at` UTC — parse carefully

### Reference Files

- **Tool implementations**: `nowing_backend/app/agents/new_chat/tools/{defillama,crypto_sentiment,crypto_news,contract_analysis}.py` (từ Story 0.1)
- **Existing integration test pattern**: `nowing_backend/tests/integration/` (nếu có)
- **Registry**: `nowing_backend/app/agents/new_chat/tools/registry.py`
- **Existing chainlens test** (reference): `nowing_backend/tests/unit/services/test_chainlens_research_service.py`

### Sample Test Data (valid fixtures)

| Parameter | Valid Example | Source |
|-----------|---------------|--------|
| `protocol_slug` | `"uniswap"`, `"aave"`, `"curve-finance"` | DeFiLlama |
| `coin_id` (CoinGecko) | `"bitcoin"`, `"ethereum"`, `"uniswap"` | CoinGecko |
| `contract_address` (UNI) | `"0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"` | Ethereum mainnet |
| `contract_address` (Uniswap V3 Router) | `"0xE592427A0AEce92De3Edee1F18E0157C05861564"` | Ethereum |
| `chain_id` (GoPlus) | `"1"` (ETH), `"56"` (BSC), `"137"` (Polygon) | GoPlus docs |
| `currencies` (CryptoPanic) | `"BTC"`, `"ETH"`, `"SOL"` | CryptoPanic |
| `subreddit` | `"cryptocurrency"`, `"Bitcoin"`, `"ethereum"` | Reddit |

---

## Traceability

| Requirement | Source | Fulfilled By |
|-------------|--------|--------------|
| FR-T1 Test API integration | `epics.md` Epic 0 | AC1-AC12 |
| NFR-CS3 API rate awareness | `prd.md` | Rate limit handling + AC6/AC7 error paths |
| NFR-Q3 Graceful degradation | `prd.md` | AC6, AC7, AC11 error dict returns |

---

## Rollback Plan

Story 8.1 là **test-only** — không touch production code. Rollback = delete test files. Zero production risk.

---

**Status**: ready-for-dev ✅ (blocked on Epic 0)
**Next**: Story 8.2 Parallel Execution Validation → Story 8.3 Error Handling → Epic 9 Phase 1 start.
