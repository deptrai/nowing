# Hướng dẫn tạo Crypto Sub-Agents trong Nowing

## Tổng quan kiến trúc

Nowing sử dụng [deepagents](https://github.com/langchain-ai/deepagents) (LangGraph-based) với kiến trúc **3 tầng song song**:

```
Main Agent (orchestrator)
  ├── Tier 1: asyncio.gather() — song song trong 1 node
  ├── Tier 2: LangGraph fan-out — song song qua graph edges
  └── Tier 3: SubAgentMiddleware.task() — spawn sub-agents
```

**SubAgent** là agent con độc lập, được main agent gọi qua `task` tool. Mỗi SubAgent có:
- System prompt riêng (chuyên môn hóa)
- Tool set riêng (chỉ các tools liên quan)
- Middleware stack riêng

Hiện tại Nowing chỉ có 1 sub-agent: `GENERAL_PURPOSE_SUBAGENT`. Hướng dẫn này mô tả cách thêm nhiều crypto sub-agents để chạy **song song**.

---

## Luồng hoạt động khi có nhiều crypto agents

```
User: "Phân tích toàn diện token $UNI"
         │
         ▼
  Main Agent (orchestrator)
         │
         ├─── task(agent="defillama_analyst", ...)    ─┐
         ├─── task(agent="sentiment_analyst", ...)     ├── chạy SONG SONG
         ├─── task(agent="news_analyst", ...)          ├── qua ToolNode
         ├─── task(agent="portfolio_analyst", ...)    ─┘
         │
         ▼
  Tổng hợp kết quả → Response cho user
```

---

## Bước 1: Tạo tool files cho từng agent

### Cấu trúc thư mục đề xuất

```
app/agents/new_chat/
├── tools/
│   ├── crypto_realtime.py      ✅ đã có (DexScreener)
│   ├── chainlens_research.py   ✅ đã có (deep research)
│   ├── defillama.py            🆕 cần tạo
│   ├── contract_analysis.py    🆕 cần tạo
│   ├── crypto_sentiment.py     🆕 cần tạo
│   └── crypto_news.py          🆕 cần tạo
└── subagents/
    └── crypto/
        ├── __init__.py         🆕 cần tạo
        ├── defillama_spec.py   🆕 cần tạo
        ├── sentiment_spec.py   🆕 cần tạo
        ├── news_spec.py        🆕 cần tạo
        ├── smart_contract_spec.py 🆕 cần tạo
        └── portfolio_spec.py   🆕 cần tạo
```

---

## Bước 2: Tạo tool files

### 2.1 `tools/defillama.py` — DeFiLlama API tools

```python
"""DeFiLlama API tools for DeFi market analysis."""

import logging
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

DEFILLAMA_BASE = "https://api.llama.fi"
DEFILLAMA_COINS = "https://coins.llama.fi"
DEFILLAMA_STABLECOINS = "https://stablecoins.llama.fi"
DEFILLAMA_YIELDS = "https://yields.llama.fi"
DEFILLAMA_BRIDGES = "https://bridges.llama.fi"


def create_defillama_protocol_tool():
    """Lấy thông tin TVL và chi tiết protocol DeFi."""

    @tool
    async def get_defillama_protocol(protocol_slug: str) -> dict[str, Any]:
        """
        Lấy dữ liệu chi tiết của một DeFi protocol từ DeFiLlama.

        Dùng khi user hỏi về TVL, token price, chain breakdown của protocol cụ thể.
        Ví dụ: uniswap, aave, compound, curve, lido, makerdao...

        Args:
            protocol_slug: Tên slug của protocol (VD: "uniswap", "aave-v3", "lido")

        Returns:
            Dict chứa TVL, chain distribution, token info, raises/fundraising info.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{DEFILLAMA_BASE}/protocol/{protocol_slug}")
            if resp.status_code != 200:
                return {"error": f"Protocol '{protocol_slug}' not found", "status": resp.status_code}
            data = resp.json()
            return {
                "name": data.get("name"),
                "slug": data.get("slug"),
                "description": data.get("description"),
                "category": data.get("category"),
                "chains": data.get("chains", []),
                "tvl": data.get("tvl"),
                "change_1h": data.get("change_1h"),
                "change_1d": data.get("change_1d"),
                "change_7d": data.get("change_7d"),
                "mcap": data.get("mcap"),
                "fdv": data.get("fdv"),
                "raises": data.get("raises", []),
                "twitter": data.get("twitter"),
                "url": data.get("url"),
                "audit_links": data.get("audit_links", []),
            }

    return get_defillama_protocol


def create_defillama_tvl_overview_tool():
    """Lấy tổng quan TVL toàn thị trường DeFi."""

    @tool
    async def get_defillama_tvl_overview(
        chain: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Lấy bảng xếp hạng TVL của các DeFi protocols (toàn thị trường hoặc theo chain).

        Dùng khi user hỏi:
        - "Top protocols DeFi theo TVL"
        - "DeFi landscape trên Ethereum/Solana/BSC..."
        - "Thị trường DeFi hiện tại như thế nào"

        Args:
            chain: Tên chain để lọc (VD: "Ethereum", "Solana", "BSC"). None = toàn bộ.
            limit: Số lượng protocols trả về (mặc định 20, tối đa 100).

        Returns:
            Dict với danh sách top protocols theo TVL.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            if chain:
                resp = await client.get(f"{DEFILLAMA_BASE}/protocols")
            else:
                resp = await client.get(f"{DEFILLAMA_BASE}/protocols")

            if resp.status_code != 200:
                return {"error": "Failed to fetch protocols"}

            protocols = resp.json()

            # Lọc theo chain nếu có
            if chain:
                protocols = [
                    p for p in protocols
                    if chain.lower() in [c.lower() for c in p.get("chains", [])]
                ]

            # Sort by TVL
            protocols.sort(key=lambda x: x.get("tvl", 0) or 0, reverse=True)
            protocols = protocols[:limit]

            total_tvl = sum(p.get("tvl", 0) or 0 for p in protocols)

            return {
                "chain_filter": chain,
                "total_protocols": len(protocols),
                "total_tvl_usd": total_tvl,
                "protocols": [
                    {
                        "rank": i + 1,
                        "name": p.get("name"),
                        "category": p.get("category"),
                        "chains": p.get("chains", [])[:5],
                        "tvl": p.get("tvl"),
                        "change_1d": p.get("change_1d"),
                        "change_7d": p.get("change_7d"),
                    }
                    for i, p in enumerate(protocols)
                ],
                "data_source": "DeFiLlama",
            }

    return get_defillama_tvl_overview


def create_defillama_yields_tool():
    """Lấy dữ liệu yield farming / lending rates từ DeFiLlama."""

    @tool
    async def get_defillama_yields(
        symbol: str | None = None,
        chain: str | None = None,
        min_tvl: float = 1_000_000,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Lấy dữ liệu APY/APR của các pool yield farming, lending, staking.

        Dùng khi user hỏi:
        - "APY tốt nhất cho USDC/ETH hiện tại"
        - "Yield farming opportunities trên Arbitrum"
        - "Lãi suất lending của token X"

        Args:
            symbol: Tên token để lọc (VD: "USDC", "ETH", "BTC"). None = tất cả.
            chain: Tên chain để lọc. None = tất cả chains.
            min_tvl: TVL tối thiểu của pool (USD). Mặc định $1M.
            limit: Số lượng pools trả về.

        Returns:
            Dict với các pools có yield cao nhất.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{DEFILLAMA_YIELDS}/pools")
            if resp.status_code != 200:
                return {"error": "Failed to fetch yield data"}

            pools = resp.json().get("data", [])

            # Lọc
            if symbol:
                pools = [p for p in pools if symbol.upper() in p.get("symbol", "").upper()]
            if chain:
                pools = [p for p in pools if p.get("chain", "").lower() == chain.lower()]
            pools = [p for p in pools if (p.get("tvlUsd") or 0) >= min_tvl]

            # Sort by APY
            pools.sort(key=lambda x: x.get("apy", 0) or 0, reverse=True)
            pools = pools[:limit]

            return {
                "filters": {"symbol": symbol, "chain": chain, "min_tvl_usd": min_tvl},
                "total_results": len(pools),
                "pools": [
                    {
                        "pool_id": p.get("pool"),
                        "project": p.get("project"),
                        "chain": p.get("chain"),
                        "symbol": p.get("symbol"),
                        "tvl_usd": p.get("tvlUsd"),
                        "apy": p.get("apy"),
                        "apy_base": p.get("apyBase"),
                        "apy_reward": p.get("apyReward"),
                        "il_risk": p.get("ilRisk"),
                        "stablecoin": p.get("stablecoin"),
                    }
                    for p in pools
                ],
                "data_source": "DeFiLlama Yields",
            }

    return get_defillama_yields


def create_defillama_stablecoins_tool():
    """Lấy dữ liệu stablecoin từ DeFiLlama."""

    @tool
    async def get_defillama_stablecoins(limit: int = 20) -> dict[str, Any]:
        """
        Lấy tổng quan thị trường stablecoin: market cap, peg status, chain distribution.

        Dùng khi user hỏi về stablecoin landscape, depeg risks, USDC/USDT dominance...

        Args:
            limit: Số lượng stablecoins trả về (sorted by market cap).

        Returns:
            Dict với danh sách stablecoins và metrics chính.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{DEFILLAMA_STABLECOINS}/stablecoins")
            if resp.status_code != 200:
                return {"error": "Failed to fetch stablecoin data"}

            data = resp.json().get("peggedAssets", [])
            data.sort(key=lambda x: x.get("circulating", {}).get("peggedUSD", 0) or 0, reverse=True)
            data = data[:limit]

            total_mcap = sum(
                d.get("circulating", {}).get("peggedUSD", 0) or 0 for d in data
            )

            return {
                "total_stablecoin_mcap_usd": total_mcap,
                "stablecoins": [
                    {
                        "name": s.get("name"),
                        "symbol": s.get("symbol"),
                        "peg_type": s.get("pegType"),
                        "peg_mechanism": s.get("pegMechanism"),
                        "circulating_usd": s.get("circulating", {}).get("peggedUSD"),
                        "chains": list(s.get("chainCirculating", {}).keys())[:5],
                        "price": s.get("price"),
                    }
                    for s in data
                ],
                "data_source": "DeFiLlama Stablecoins",
            }

    return get_defillama_stablecoins


def create_defillama_bridges_tool():
    """Lấy dữ liệu cross-chain bridges từ DeFiLlama."""

    @tool
    async def get_defillama_bridges(limit: int = 20) -> dict[str, Any]:
        """
        Lấy thống kê volume và usage của các cross-chain bridges.

        Dùng khi user hỏi về bridge volume, TVL của bridges, top bridges...

        Args:
            limit: Số lượng bridges trả về.

        Returns:
            Dict với danh sách bridges và volume data.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{DEFILLAMA_BRIDGES}/bridges?includeChains=true")
            if resp.status_code != 200:
                return {"error": "Failed to fetch bridges data"}

            bridges = resp.json().get("bridges", [])
            bridges.sort(key=lambda x: x.get("lastDailyVolume", 0) or 0, reverse=True)
            bridges = bridges[:limit]

            return {
                "bridges": [
                    {
                        "id": b.get("id"),
                        "name": b.get("displayName"),
                        "chains": b.get("chains", [])[:5],
                        "volume_24h_usd": b.get("lastDailyVolume"),
                        "volume_7d_usd": b.get("lastWeeklyVolume"),
                        "volume_monthly_usd": b.get("lastMonthlyVolume"),
                    }
                    for b in bridges
                ],
                "data_source": "DeFiLlama Bridges",
            }

    return get_defillama_bridges
```

### 2.2 `tools/crypto_sentiment.py` — Sentiment Analysis tools

```python
"""Crypto sentiment analysis tools - social media & community data."""

import logging
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def create_coinmarketcap_sentiment_tool():
    """Lấy dữ liệu sentiment từ CoinMarketCap (free API)."""

    @tool
    async def get_cmc_sentiment(symbol: str) -> dict[str, Any]:
        """
        Lấy Fear & Greed Index, sentiment score và social metrics từ CoinMarketCap.

        Dùng khi user hỏi về:
        - "Market sentiment hiện tại"
        - "Fear & Greed Index"
        - "Community sentiment của BTC/ETH/..."

        Args:
            symbol: Ký hiệu token (VD: "BTC", "ETH", "SOL")

        Returns:
            Dict với sentiment score, social stats, community data.
        """
        # CoinMarketCap Community API (public, không cần API key)
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.coinmarketcap.com/data-api/v3/fear-and-greed/latest"
            )
            fear_greed = {}
            if resp.status_code == 200:
                fg_data = resp.json().get("data", {})
                fear_greed = {
                    "value": fg_data.get("value"),
                    "value_classification": fg_data.get("value_classification"),
                    "timestamp": fg_data.get("update_time"),
                }

        return {
            "symbol": symbol,
            "fear_greed_index": fear_greed,
            "note": "Dùng web_search để lấy thêm sentiment từ Twitter/Reddit/Telegram",
            "data_source": "CoinMarketCap",
        }

    return get_cmc_sentiment


def create_reddit_crypto_sentiment_tool():
    """Lấy posts từ Reddit crypto subreddits."""

    @tool
    async def get_reddit_crypto_sentiment(
        symbol: str,
        subreddit: str = "CryptoCurrency",
        limit: int = 25,
    ) -> dict[str, Any]:
        """
        Lấy posts Reddit gần nhất về một token để phân tích sentiment cộng đồng.

        Dùng khi user hỏi:
        - "Reddit nói gì về $TOKEN?"
        - "Community Reddit đang nghĩ gì về BTC?"

        Args:
            symbol: Ký hiệu token (VD: "BTC", "ETH", "SOL")
            subreddit: Subreddit để search (mặc định: CryptoCurrency)
                       Gợi ý: "bitcoin", "ethereum", "solana", "CryptoMarkets"
            limit: Số lượng posts lấy về

        Returns:
            Dict với top posts và sentiment summary.
        """
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                f"https://www.reddit.com/r/{subreddit}/search.json",
                params={
                    "q": symbol,
                    "sort": "hot",
                    "limit": limit,
                    "restrict_sr": "on",
                    "t": "week",
                },
                headers={"User-Agent": "NowingCryptoBot/1.0"},
            )
            if resp.status_code != 200:
                return {"error": f"Reddit API error: {resp.status_code}"}

            posts = resp.json().get("data", {}).get("children", [])

        results = []
        for post in posts:
            d = post.get("data", {})
            results.append({
                "title": d.get("title"),
                "score": d.get("score"),
                "num_comments": d.get("num_comments"),
                "upvote_ratio": d.get("upvote_ratio"),
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "created_utc": d.get("created_utc"),
            })

        avg_score = sum(p["score"] for p in results) / len(results) if results else 0
        avg_ratio = sum(p["upvote_ratio"] for p in results) / len(results) if results else 0

        return {
            "symbol": symbol,
            "subreddit": subreddit,
            "posts_analyzed": len(results),
            "avg_score": round(avg_score, 1),
            "avg_upvote_ratio": round(avg_ratio, 3),
            "top_posts": results[:10],
            "data_source": f"Reddit r/{subreddit}",
        }

    return get_reddit_crypto_sentiment
```

> **Lưu ý về X.com/Twitter và Telegram:** API của X.com hiện yêu cầu Basic plan ($100/tháng). Telegram không có public API. Khuyến nghị dùng `web_search` tool để scrape mentions từ các nền tảng này thay vì gọi API trực tiếp.

### 2.3 `tools/crypto_news.py` — News & Blog tools

```python
"""Crypto news aggregation tools."""

import logging
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def create_crypto_news_tool():
    """Lấy tin tức crypto từ CryptoPanic và CoinGecko."""

    @tool
    async def get_crypto_news(
        symbol: str | None = None,
        kind: str = "news",
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Lấy tin tức crypto mới nhất từ CryptoPanic (aggregates 100+ news sources).

        Nguồn bao gồm: CoinDesk, Cointelegraph, Decrypt, The Block, Blockworks...

        Dùng khi user hỏi:
        - "Tin tức mới nhất về Bitcoin/Ethereum/..."
        - "Có sự kiện gì xảy ra với $TOKEN?"
        - "News catalyst cho token này"

        Args:
            symbol: Ký hiệu token để lọc (VD: "BTC", "ETH"). None = all crypto news.
            kind: Loại tin: "news" (tin tức), "media" (video/podcast), "analysis"
            limit: Số lượng tin lấy về (max 50)

        Returns:
            Dict với danh sách tin tức, nguồn, và sentiment signal.
        """
        # CryptoPanic public API (không cần key cho basic usage)
        params = {
            "public": "true",
            "kind": kind,
            "limit": min(limit, 50),
        }
        if symbol:
            params["currencies"] = symbol.upper()

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://cryptopanic.com/api/free/v1/posts/",
                params=params,
            )
            if resp.status_code != 200:
                return {"error": f"CryptoPanic API error: {resp.status_code}"}

            results = resp.json().get("results", [])

        news = []
        for item in results:
            news.append({
                "title": item.get("title"),
                "published_at": item.get("published_at"),
                "source": item.get("source", {}).get("title"),
                "url": item.get("url"),
                "votes": {
                    "positive": item.get("votes", {}).get("positive", 0),
                    "negative": item.get("votes", {}).get("negative", 0),
                    "important": item.get("votes", {}).get("important", 0),
                },
                "currencies": [c.get("code") for c in item.get("currencies", [])],
            })

        # Tính sentiment từ votes
        total_positive = sum(n["votes"]["positive"] for n in news)
        total_negative = sum(n["votes"]["negative"] for n in news)

        return {
            "symbol": symbol,
            "kind": kind,
            "total_news": len(news),
            "sentiment_signal": {
                "positive_votes": total_positive,
                "negative_votes": total_negative,
                "ratio": round(
                    total_positive / (total_positive + total_negative + 1), 2
                ),
            },
            "news": news,
            "data_source": "CryptoPanic (aggregates 100+ sources)",
        }

    return get_crypto_news


def create_coingecko_news_tool():
    """Lấy news từ CoinGecko (free API, không cần key)."""

    @tool
    async def get_coingecko_news(
        coin_id: str,
        vs_currency: str = "usd",
    ) -> dict[str, Any]:
        """
        Lấy thông tin chi tiết token + news từ CoinGecko.

        Dùng khi cần thông tin chính thức: website, social links, team, description...

        Args:
            coin_id: CoinGecko ID của token (VD: "bitcoin", "ethereum", "uniswap")
                     Tìm ID tại: https://www.coingecko.com/en/coins/list
            vs_currency: Currency để so sánh giá (mặc định: "usd")

        Returns:
            Dict với thông tin token đầy đủ từ CoinGecko.
        """
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "true",
                    "developer_data": "true",
                },
            )
            if resp.status_code == 429:
                return {"error": "CoinGecko rate limit reached, try again in 1 minute"}
            if resp.status_code != 200:
                return {"error": f"Coin '{coin_id}' not found on CoinGecko"}

            data = resp.json()

        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "symbol": data.get("symbol", "").upper(),
            "description": (data.get("description", {}).get("en", "") or "")[:500],
            "categories": data.get("categories", []),
            "links": {
                "homepage": data.get("links", {}).get("homepage", [None])[0],
                "whitepaper": data.get("links", {}).get("whitepaper"),
                "twitter": data.get("links", {}).get("twitter_screen_name"),
                "telegram": data.get("links", {}).get("telegram_channel_identifier"),
                "reddit": data.get("links", {}).get("subreddit_url"),
                "github": data.get("links", {}).get("repos_url", {}).get("github", []),
            },
            "community_data": data.get("community_data", {}),
            "developer_data": {
                "forks": data.get("developer_data", {}).get("forks"),
                "stars": data.get("developer_data", {}).get("stars"),
                "commit_count_4_weeks": data.get("developer_data", {}).get("commit_count_4_weeks"),
            },
            "market_data": {
                "current_price_usd": data.get("market_data", {}).get("current_price", {}).get("usd"),
                "market_cap_usd": data.get("market_data", {}).get("market_cap", {}).get("usd"),
                "total_supply": data.get("market_data", {}).get("total_supply"),
                "circulating_supply": data.get("market_data", {}).get("circulating_supply"),
                "max_supply": data.get("market_data", {}).get("max_supply"),
                "ath_usd": data.get("market_data", {}).get("ath", {}).get("usd"),
            },
            "last_updated": data.get("last_updated"),
            "data_source": "CoinGecko",
        }

    return get_coingecko_news
```

### 2.4 `tools/contract_analysis.py` — Smart Contract Analysis tools

```python
"""Smart contract analysis tools - security & feature analysis."""

import logging
from typing import Any

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def create_contract_bytecode_tool():
    """Fetch và phân tích bytecode của smart contract."""

    @tool
    async def get_contract_info(
        contract_address: str,
        chain: str = "ethereum",
    ) -> dict[str, Any]:
        """
        Lấy thông tin và ABI của smart contract từ block explorer.

        Dùng khi user muốn:
        - "Phân tích contract của $TOKEN"
        - "Contract có verified không?"
        - "Tìm vulnerabilities trong contract"

        Args:
            contract_address: Địa chỉ contract (0x...)
            chain: Blockchain ("ethereum", "bsc", "polygon", "arbitrum", "base", "solana")

        Returns:
            Dict với source code, ABI, verification status, contract metadata.
        """
        # Mapping chain sang explorer API
        explorer_apis = {
            "ethereum": "https://api.etherscan.io/api",
            "bsc": "https://api.bscscan.com/api",
            "polygon": "https://api.polygonscan.com/api",
            "arbitrum": "https://api.arbiscan.io/api",
            "base": "https://api.basescan.org/api",
            "optimism": "https://api-optimistic.etherscan.io/api",
            "avalanche": "https://api.snowtrace.io/api",
            "fantom": "https://api.ftmscan.com/api",
        }

        api_url = explorer_apis.get(chain.lower())
        if not api_url:
            return {
                "error": f"Chain '{chain}' chưa được hỗ trợ. Supported: {list(explorer_apis.keys())}",
                "contract_address": contract_address,
            }

        async with httpx.AsyncClient(timeout=30) as client:
            # Lấy source code (free, không cần API key cho basic)
            resp = await client.get(
                api_url,
                params={
                    "module": "contract",
                    "action": "getsourcecode",
                    "address": contract_address,
                    # API key optional để tăng rate limit:
                    # "apikey": config.ETHERSCAN_API_KEY,
                },
            )
            if resp.status_code != 200:
                return {"error": "Failed to fetch contract info"}

            data = resp.json()
            if data.get("status") != "1":
                return {
                    "error": "Contract not found or not verified",
                    "contract_address": contract_address,
                    "chain": chain,
                }

            result = data.get("result", [{}])[0]

        source_code = result.get("SourceCode", "")
        is_verified = bool(source_code)

        # Phân tích sơ bộ source code để tìm patterns
        analysis = {}
        if source_code:
            sc_lower = source_code.lower()
            analysis = {
                "has_ownable": "ownable" in sc_lower,
                "has_pausable": "pausable" in sc_lower,
                "has_upgradeable": any(
                    x in sc_lower for x in ["upgradeable", "proxy", "implementation"]
                ),
                "has_timelock": "timelock" in sc_lower,
                "has_multisig": "multisig" in sc_lower,
                "has_mint_function": "function mint" in sc_lower,
                "has_burn_function": "function burn" in sc_lower,
                "has_blacklist": any(x in sc_lower for x in ["blacklist", "blocklist", "banned"]),
                "has_whitelist": "whitelist" in sc_lower,
                "uses_safemath": "safemath" in sc_lower or "SafeMath" in source_code,
                "uses_reentrancy_guard": "reentrancyguard" in sc_lower,
                "compiler_version": result.get("CompilerVersion"),
                "optimization": result.get("OptimizationUsed") == "1",
            }

        return {
            "contract_address": contract_address,
            "chain": chain,
            "contract_name": result.get("ContractName"),
            "is_verified": is_verified,
            "compiler_version": result.get("CompilerVersion"),
            "license": result.get("LicenseType"),
            "proxy": result.get("Proxy") == "1",
            "implementation": result.get("Implementation"),
            "abi_available": bool(result.get("ABI") and result.get("ABI") != "Contract source code not verified"),
            "security_analysis": analysis,
            "source_code_preview": source_code[:2000] if source_code else None,
            "data_source": f"{chain.capitalize()} Explorer",
            "note": "Để phân tích sâu hơn về vulnerabilities, dùng web_search với Slither/MythX/Solodit",
        }

    return get_contract_info


def create_token_security_check_tool():
    """Kiểm tra token security score qua GoPlus Security API."""

    @tool
    async def check_token_security(
        contract_address: str,
        chain_id: str = "1",
    ) -> dict[str, Any]:
        """
        Kiểm tra token security: rug pull risks, honeypot, tax info qua GoPlus Security.

        Dùng khi user hỏi:
        - "Token này có an toàn không?"
        - "Có phải honeypot không?"
        - "Tax của token này là bao nhiêu?"
        - "Rug pull risk analysis"

        Args:
            contract_address: Địa chỉ contract token
            chain_id: Chain ID (1=ETH, 56=BSC, 137=Polygon, 42161=Arbitrum, 8453=Base, 
                     900=Solana dùng address dạng khác)

        Returns:
            Dict với security analysis, rug indicators, tax info.
        """
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}",
                params={"contract_addresses": contract_address},
            )
            if resp.status_code != 200:
                return {"error": "GoPlus API unavailable"}

            data = resp.json()
            token_data = data.get("result", {}).get(contract_address.lower(), {})

        if not token_data:
            return {
                "error": "Token not found in GoPlus database",
                "contract_address": contract_address,
            }

        # Parse risks
        risks = []
        if token_data.get("is_honeypot") == "1":
            risks.append("🚨 HONEYPOT DETECTED")
        if token_data.get("is_mintable") == "1":
            risks.append("⚠️ Token có thể mint thêm")
        if token_data.get("owner_change_balance") == "1":
            risks.append("🚨 Owner có thể thay đổi balance")
        if token_data.get("can_take_back_ownership") == "1":
            risks.append("🚨 Ownership có thể bị lấy lại")
        if token_data.get("hidden_owner") == "1":
            risks.append("🚨 Hidden owner contract")
        if token_data.get("selfdestruct") == "1":
            risks.append("🚨 Self-destruct function")
        if token_data.get("is_blacklisted") == "1":
            risks.append("⚠️ Có blacklist function")
        if float(token_data.get("buy_tax", "0") or "0") > 10:
            risks.append(f"⚠️ Buy tax cao: {token_data.get('buy_tax')}%")
        if float(token_data.get("sell_tax", "0") or "0") > 10:
            risks.append(f"⚠️ Sell tax cao: {token_data.get('sell_tax')}%")

        return {
            "contract_address": contract_address,
            "chain_id": chain_id,
            "token_name": token_data.get("token_name"),
            "token_symbol": token_data.get("token_symbol"),
            "total_supply": token_data.get("total_supply"),
            "security_score": {
                "is_open_source": token_data.get("is_open_source") == "1",
                "is_proxy": token_data.get("is_proxy") == "1",
                "is_mintable": token_data.get("is_mintable") == "1",
                "is_honeypot": token_data.get("is_honeypot") == "1",
                "buy_tax": token_data.get("buy_tax"),
                "sell_tax": token_data.get("sell_tax"),
                "cannot_sell_all": token_data.get("cannot_sell_all") == "1",
                "is_blacklisted": token_data.get("is_blacklisted") == "1",
                "trading_cooldown": token_data.get("trading_cooldown") == "1",
            },
            "ownership": {
                "owner_address": token_data.get("owner_address"),
                "owner_balance": token_data.get("owner_balance"),
                "owner_percent": token_data.get("owner_percent"),
                "creator_address": token_data.get("creator_address"),
            },
            "risks_detected": risks,
            "risk_level": (
                "HIGH" if any("🚨" in r for r in risks)
                else "MEDIUM" if risks
                else "LOW"
            ),
            "holders": {
                "count": token_data.get("holder_count"),
                "top_10_percent": token_data.get("top10HolderPercent"),
            },
            "lp_info": {
                "lp_locked": token_data.get("lp_total_supply"),
                "lp_holders": token_data.get("lp_holder_count"),
            },
            "data_source": "GoPlus Security",
        }

    return check_token_security
```

---

## Bước 3: Đăng ký tools vào `registry.py`

Mở file `app/agents/new_chat/tools/registry.py` và thêm:

```python
# Import các tools mới
from .defillama import (
    create_defillama_protocol_tool,
    create_defillama_tvl_overview_tool,
    create_defillama_yields_tool,
    create_defillama_stablecoins_tool,
    create_defillama_bridges_tool,
)
from .contract_analysis import (
    create_contract_bytecode_tool,
    create_token_security_check_tool,
)
from .crypto_sentiment import (
    create_coinmarketcap_sentiment_tool,
    create_reddit_crypto_sentiment_tool,
)
from .crypto_news import (
    create_crypto_news_tool,
    create_coingecko_news_tool,
)

# Thêm vào BUILTIN_TOOLS list:
CRYPTO_TOOLS = [
    # DeFiLlama tools
    ToolDefinition(
        name="get_defillama_protocol",
        description="Get DeFi protocol TVL, chains, and metrics from DeFiLlama",
        factory=lambda deps: create_defillama_protocol_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_tvl_overview",
        description="Get top DeFi protocols ranked by TVL from DeFiLlama",
        factory=lambda deps: create_defillama_tvl_overview_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_yields",
        description="Get best yield farming / lending APY rates from DeFiLlama",
        factory=lambda deps: create_defillama_yields_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_stablecoins",
        description="Get stablecoin market overview from DeFiLlama",
        factory=lambda deps: create_defillama_stablecoins_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_defillama_bridges",
        description="Get cross-chain bridge volume and stats from DeFiLlama",
        factory=lambda deps: create_defillama_bridges_tool(),
        requires=[],
    ),
    # Contract analysis tools
    ToolDefinition(
        name="get_contract_info",
        description="Get smart contract source code, ABI and security analysis",
        factory=lambda deps: create_contract_bytecode_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="check_token_security",
        description="Check token security: honeypot, rug pull risks, tax info via GoPlus",
        factory=lambda deps: create_token_security_check_tool(),
        requires=[],
    ),
    # Sentiment tools
    ToolDefinition(
        name="get_cmc_sentiment",
        description="Get Fear & Greed Index and market sentiment from CoinMarketCap",
        factory=lambda deps: create_coinmarketcap_sentiment_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_reddit_crypto_sentiment",
        description="Get Reddit community posts and sentiment for a crypto token",
        factory=lambda deps: create_reddit_crypto_sentiment_tool(),
        requires=[],
    ),
    # News tools
    ToolDefinition(
        name="get_crypto_news",
        description="Get latest crypto news from 100+ sources via CryptoPanic",
        factory=lambda deps: create_crypto_news_tool(),
        requires=[],
    ),
    ToolDefinition(
        name="get_coingecko_info",
        description="Get token description, links, community data from CoinGecko",
        factory=lambda deps: create_coingecko_news_tool(),
        requires=[],
    ),
]
```

---

## Bước 4: Tạo SubAgent specs

### `subagents/crypto/__init__.py`

```python
from .defillama_spec import DEFILLAMA_ANALYST_SUBAGENT
from .sentiment_spec import SENTIMENT_ANALYST_SUBAGENT
from .news_spec import NEWS_ANALYST_SUBAGENT
from .smart_contract_spec import SMART_CONTRACT_ANALYST_SUBAGENT
from .portfolio_spec import PORTFOLIO_ANALYST_SUBAGENT
from .onchain_spec import ONCHAIN_ANALYST_SUBAGENT

__all__ = [
    "DEFILLAMA_ANALYST_SUBAGENT",
    "SENTIMENT_ANALYST_SUBAGENT",
    "NEWS_ANALYST_SUBAGENT",
    "SMART_CONTRACT_ANALYST_SUBAGENT",
    "PORTFOLIO_ANALYST_SUBAGENT",
    "ONCHAIN_ANALYST_SUBAGENT",
]
```

### `subagents/crypto/defillama_spec.py`

```python
"""DeFiLlama Analyst SubAgent - chuyên phân tích DeFi market."""

from deepagents import SubAgent

DEFILLAMA_ANALYST_SYSTEM_PROMPT = """Bạn là DeFiLlama Analyst, chuyên gia phân tích thị trường DeFi.

## Nhiệm vụ
Phân tích toàn diện hệ sinh thái DeFi sử dụng dữ liệu từ DeFiLlama.

## Công cụ có sẵn
- `get_defillama_tvl_overview`: Tổng quan TVL toàn thị trường DeFi
- `get_defillama_protocol`: Chi tiết một protocol cụ thể (TVL, chains, raises)
- `get_defillama_yields`: Cơ hội yield farming / lending APY
- `get_defillama_stablecoins`: Thị trường stablecoin và peg status
- `get_defillama_bridges`: Volume cross-chain bridges
- `get_live_token_price`: Giá real-time từ DexScreener

## Cách phân tích
1. **Tổng quan thị trường**: Dùng `get_defillama_tvl_overview` để xem top protocols
2. **Protocol cụ thể**: Dùng `get_defillama_protocol` với slug của protocol
3. **Yield opportunities**: Dùng `get_defillama_yields` để tìm APY tốt nhất
4. **Stablecoin health**: Dùng `get_defillama_stablecoins` để theo dõi peg

## Output format
Trình bày kết quả có cấu trúc rõ ràng với:
- 📊 Key metrics (TVL, Volume, APY)
- 🔗 Chain distribution
- 📈 Trend (7d, 30d changes)
- 💡 Insights và observations
- ⚠️ Risk factors nếu có

Trả lời bằng tiếng Việt, ngắn gọn và có số liệu cụ thể.
"""

# Spec base - model, tools, middleware sẽ được inject từ create_nowing_deep_agent
DEFILLAMA_ANALYST_SUBAGENT: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": "defillama_analyst",
    "system_prompt": DEFILLAMA_ANALYST_SYSTEM_PROMPT,
}
```

### `subagents/crypto/smart_contract_spec.py`

```python
"""Smart Contract Analyst SubAgent - phân tích security và features."""

from deepagents import SubAgent

SMART_CONTRACT_ANALYST_SYSTEM_PROMPT = """Bạn là Smart Contract Security Analyst, chuyên gia phân tích smart contract.

## Nhiệm vụ
Phân tích smart contracts để tìm lỗ hổng bảo mật, tính năng đặc biệt, và đánh giá rủi ro.

## Công cụ có sẵn
- `get_contract_info`: Lấy source code, ABI, và phân tích sơ bộ từ block explorer
- `check_token_security`: Kiểm tra rug pull risks, honeypot, tax qua GoPlus Security
- `web_search`: Tìm audit reports, past exploits, Solodit findings
- `scrape_webpage`: Đọc audit reports từ các security firms

## Quy trình phân tích
1. **Basic check**: Dùng `check_token_security` để check rug indicators ngay lập tức
2. **Source code**: Dùng `get_contract_info` để lấy code và check patterns
3. **Audit history**: Dùng `web_search` với query "{protocol} audit report site:solodit.xyz OR site:code4rena.com"
4. **Known exploits**: Search "{protocol} hack exploit vulnerability"

## Security checklist
✅ Contract verified on-chain
✅ No hidden owner / backdoors
✅ No mint-without-limit
✅ Reentrancy guard present
✅ SafeMath / Solidity 0.8+ (overflow protection)
✅ Timelock trên admin functions
✅ Professional audit completed
✅ Không có honeypot tax
✅ LP locked / burned

## Output format
Trả về security report với:
- 🟢/🟡/🔴 Risk level (LOW/MEDIUM/HIGH)
- Danh sách risks tìm được
- Contract features quan trọng
- Recommendations

Trả lời bằng tiếng Việt với technical details.
"""

SMART_CONTRACT_ANALYST_SUBAGENT: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": "smart_contract_analyst",
    "system_prompt": SMART_CONTRACT_ANALYST_SYSTEM_PROMPT,
}
```

### `subagents/crypto/sentiment_spec.py`

```python
"""Sentiment Analyst SubAgent - phân tích community sentiment."""

from deepagents import SubAgent

SENTIMENT_ANALYST_SYSTEM_PROMPT = """Bạn là Crypto Sentiment Analyst, chuyên phân tích tâm lý thị trường và cộng đồng.

## Nhiệm vụ
Phân tích sentiment từ nhiều nguồn: social media, community platforms, market indicators.

## Công cụ có sẵn
- `get_cmc_sentiment`: Fear & Greed Index từ CoinMarketCap
- `get_reddit_crypto_sentiment`: Posts và sentiment từ Reddit
- `web_search`: Tìm mentions trên Twitter/X, Telegram, Discord
- `scrape_webpage`: Đọc nội dung từ CoinMarketCap community, Telegram public channels

## Nguồn cần kiểm tra
1. **Market indicators**: Fear & Greed Index, funding rates, long/short ratio
2. **Reddit**: r/CryptoCurrency, r/Bitcoin, r/ethereum, r/{project}-specific subreddits
3. **Twitter/X**: Search "{$TOKEN} -is:retweet lang:en" trên web
4. **Telegram**: Search public Telegram channels qua web
5. **CoinMarketCap**: Community discussions và ratings

## Sentiment signals
- **Bullish signals**: High buying volume, positive news, influencer support, community growth
- **Bearish signals**: High Fear & Greed fear, negative news, whale selling, controversy
- **Neutral**: Mixed signals, low activity period

## Output format
- 📊 Sentiment Score (0-100, 50 = neutral)
- 🌡️ Market Temperature (Extreme Fear / Fear / Neutral / Greed / Extreme Greed)
- 📱 Platform breakdown (Reddit, Twitter, Telegram sentiment)
- 🔑 Key talking points
- 📰 Major news catalysts
- 💡 Sentiment trend (improving/deteriorating)

Trả lời bằng tiếng Việt, objective và data-driven.
"""

SENTIMENT_ANALYST_SUBAGENT: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": "sentiment_analyst",
    "system_prompt": SENTIMENT_ANALYST_SYSTEM_PROMPT,
}
```

### `subagents/crypto/news_spec.py`

```python
"""News Analyst SubAgent - tổng hợp tin tức và sự kiện."""

from deepagents import SubAgent

NEWS_ANALYST_SYSTEM_PROMPT = """Bạn là Crypto News Analyst, chuyên tổng hợp và phân tích tin tức crypto.

## Nhiệm vụ
Thu thập và phân tích tin tức, sự kiện, catalyst có thể ảnh hưởng đến giá và sentiment.

## Công cụ có sẵn
- `get_crypto_news`: Tin tức từ 100+ nguồn qua CryptoPanic
- `get_coingecko_info`: Thông tin chính thức dự án từ CoinGecko
- `web_search`: Tìm kiếm tin tức mới nhất
- `scrape_webpage`: Đọc bài viết chi tiết

## Nguồn tin tức ưu tiên
1. **Tier 1 (Most credible)**: CoinDesk, The Block, Blockworks, Reuters, Bloomberg Crypto
2. **Tier 2**: Cointelegraph, Decrypt, CryptoSlate, BeInCrypto
3. **Tier 3**: Crypto blogs, Medium, Substack

## Phân loại events
- 🚀 **Bullish catalyst**: Partnership, listing, mainnet launch, token burn, buyback
- 📉 **Bearish catalyst**: Hack, regulatory action, team leaving, competition
- ℹ️ **Neutral**: Routine updates, minor partnerships, non-critical news

## Output format
- 📅 Timeline of recent news (newest first)
- 🔑 Key events summary
- 📊 Impact assessment (HIGH/MEDIUM/LOW)
- 🎯 Upcoming events (token unlock, listings, mainnet...)
- 💡 News sentiment signal

Trả lời bằng tiếng Việt, fact-based và objective.
"""

NEWS_ANALYST_SUBAGENT: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": "news_analyst",
    "system_prompt": NEWS_ANALYST_SYSTEM_PROMPT,
}
```

### `subagents/crypto/portfolio_spec.py`

```python
"""Portfolio Analyst SubAgent - phân tích danh mục đầu tư."""

from deepagents import SubAgent

PORTFOLIO_ANALYST_SYSTEM_PROMPT = """Bạn là Portfolio Analyst, chuyên phân tích và tối ưu hóa danh mục đầu tư crypto.

## Nhiệm vụ
Phân tích portfolio, tính toán metrics, đưa ra insights về allocation, risk/reward.

## Công cụ có sẵn
- `get_live_token_price`: Giá hiện tại của token
- `get_live_token_data`: Data chi tiết (market cap, volume, liquidity)
- `get_defillama_protocol`: TVL và metrics của protocols trong portfolio
- `get_defillama_yields`: Tìm yield opportunities để tối ưu vốn nhàn rỗi
- `web_search`: Tìm thêm thông tin về tokens trong portfolio

## Metrics cần tính
- **Portfolio Value**: Tổng giá trị USD hiện tại
- **Allocation %**: % của mỗi token trong tổng portfolio
- **PnL**: Profit/Loss (nếu có thông tin buy price)
- **Risk Score**: Đánh giá rủi ro dựa trên market cap, liquidity, age
- **Diversification**: Phân tích diversity theo chains, sectors

## Risk Categories
- 🔵 **Conservative** (BTC, ETH, stablecoins): Low risk
- 🟢 **Large Cap** (SOL, BNB, MATIC, top 20): Moderate risk
- 🟡 **Mid Cap** (top 100): Higher risk
- 🔴 **Small Cap / DeFi**: High risk
- ⚫ **Micro Cap / Memecoin**: Very high risk

## Output format
Trả về portfolio analysis với:
- 💼 Portfolio overview (total value, allocation breakdown)
- 📊 Risk analysis
- 🎯 Rebalancing suggestions
- 💡 Yield opportunities cho capital nhàn rỗi
- ⚠️ Risk warnings

Trả lời bằng tiếng Việt với số liệu cụ thể.
"""

PORTFOLIO_ANALYST_SUBAGENT: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": "portfolio_analyst",
    "system_prompt": PORTFOLIO_ANALYST_SYSTEM_PROMPT,
}
```

### `subagents/crypto/onchain_spec.py` (Agent bổ sung)

```python
"""On-Chain Analyst SubAgent - phân tích on-chain data."""

from deepagents import SubAgent

ONCHAIN_ANALYST_SYSTEM_PROMPT = """Bạn là On-Chain Analyst, chuyên đọc và phân tích dữ liệu blockchain.

## Nhiệm vụ
Phân tích on-chain metrics: whale movements, holder distribution, token flows, DEX activity.

## Công cụ có sẵn
- `get_live_token_data`: Dữ liệu thực từ DexScreener (txns, liquidity, volume)
- `check_token_security`: Holder distribution, LP info
- `get_contract_info`: Contract metadata
- `web_search`: Tìm Dune Analytics dashboards, Nansen data, Arkham Intel

## Metrics quan trọng
- **Whale activity**: Large transfers, top holder movements
- **DEX flow**: Buy/sell ratio, volume trends
- **Holder count**: Growth/decline trend
- **LP health**: Liquidity depth, lock status
- **Token velocity**: Circulation speed

## Nguồn dữ liệu on-chain
Dùng `web_search` để truy cập:
- Dune Analytics: `site:dune.com/queries {token}`
- Nansen: `site:nansen.ai {token}`  
- Arkham Intel: `site:arkhamintelligence.com {address}`
- Etherscan: `site:etherscan.io/token {address}`

## Output format
- 🐳 Whale activity summary
- 📊 Trading patterns (buy pressure vs sell pressure)
- 👥 Holder distribution changes
- 💧 Liquidity health assessment
- 🚨 Red flags (unusual outflows, whale dumping, LP removal)

Trả lời bằng tiếng Việt với data points cụ thể.
"""

ONCHAIN_ANALYST_SUBAGENT: SubAgent = {  # type: ignore[typeddict-unknown-key]
    "name": "onchain_analyst",
    "system_prompt": ONCHAIN_ANALYST_SYSTEM_PROMPT,
}
```

---

## Bước 5: Đăng ký tất cả vào `chat_deepagent.py`

Mở `app/agents/new_chat/chat_deepagent.py` và sửa hàm `create_nowing_deep_agent`:

```python
# Import thêm ở đầu file
from app.agents.new_chat.subagents.crypto import (
    DEFILLAMA_ANALYST_SUBAGENT,
    SENTIMENT_ANALYST_SUBAGENT,
    NEWS_ANALYST_SUBAGENT,
    SMART_CONTRACT_ANALYST_SUBAGENT,
    PORTFOLIO_ANALYST_SUBAGENT,
    ONCHAIN_ANALYST_SUBAGENT,
)

# Trong hàm create_nowing_deep_agent, sau đoạn build tools:

# ─── Crypto specialist sub-agents ────────────────────────────────────────────
# Tools chuyên biệt cho từng agent (chỉ enable tools liên quan để tiết kiệm context)

defillama_tools = [t for t in tools if t.name in {
    "get_defillama_protocol", "get_defillama_tvl_overview",
    "get_defillama_yields", "get_defillama_stablecoins",
    "get_defillama_bridges", "get_live_token_price",
    "web_search",
}]

contract_tools = [t for t in tools if t.name in {
    "get_contract_info", "check_token_security",
    "web_search", "scrape_webpage",
}]

sentiment_tools = [t for t in tools if t.name in {
    "get_cmc_sentiment", "get_reddit_crypto_sentiment",
    "web_search", "scrape_webpage",
}]

news_tools = [t for t in tools if t.name in {
    "get_crypto_news", "get_coingecko_info",
    "web_search", "scrape_webpage",
}]

portfolio_tools = [t for t in tools if t.name in {
    "get_live_token_price", "get_live_token_data",
    "get_defillama_yields", "get_defillama_protocol",
    "web_search",
}]

onchain_tools = [t for t in tools if t.name in {
    "get_live_token_data", "check_token_security",
    "get_contract_info", "web_search",
}]

# Middleware nhẹ cho sub-agents (không cần KnowledgeBase, Dedup, etc.)
crypto_subagent_middleware = [
    NowingFilesystemMiddleware(
        search_space_id=search_space_id,
        created_by_id=user_id,
    ),
    create_summarization_middleware(llm, StateBackend),
    PatchToolCallsMiddleware(),
    AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
]

# Build specs bằng cách merge base spec với model/tools/middleware
def _build_crypto_spec(base_spec, agent_tools):
    return {
        **base_spec,
        "model": llm,
        "tools": agent_tools,
        "middleware": crypto_subagent_middleware,
    }

defillama_spec = _build_crypto_spec(DEFILLAMA_ANALYST_SUBAGENT, defillama_tools)
contract_spec = _build_crypto_spec(SMART_CONTRACT_ANALYST_SUBAGENT, contract_tools)
sentiment_spec = _build_crypto_spec(SENTIMENT_ANALYST_SUBAGENT, sentiment_tools)
news_spec = _build_crypto_spec(NEWS_ANALYST_SUBAGENT, news_tools)
portfolio_spec = _build_crypto_spec(PORTFOLIO_ANALYST_SUBAGENT, portfolio_tools)
onchain_spec = _build_crypto_spec(ONCHAIN_ANALYST_SUBAGENT, onchain_tools)

# Cập nhật SubAgentMiddleware với tất cả sub-agents
deepagent_middleware = [
    ...
    SubAgentMiddleware(
        backend=StateBackend,
        subagents=[
            general_purpose_spec,    # existing
            defillama_spec,           # NEW
            contract_spec,            # NEW
            sentiment_spec,           # NEW
            news_spec,                # NEW
            portfolio_spec,           # NEW
            onchain_spec,             # NEW
        ],
    ),
    ...
]
```

---

## Bước 6: Cập nhật System Prompt của Main Agent

Thêm vào `build_nowing_system_prompt` để main agent biết cách orchestrate:

```python
CRYPTO_ORCHESTRATION_PROMPT = """
## Crypto Analysis Sub-Agents

Khi user yêu cầu phân tích crypto, bạn có các specialist agents sau. 
Gọi chúng SONG SONG (cùng lúc) trong một lần response để tiết kiệm thời gian:

| Agent | Tên | Chuyên môn |
|-------|-----|-----------|
| DeFiLlama Analyst | `defillama_analyst` | TVL, yields, stablecoins, bridges |
| Smart Contract Analyst | `smart_contract_analyst` | Security, vulnerabilities, audit |
| Sentiment Analyst | `sentiment_analyst` | Social media, community sentiment |
| News Analyst | `news_analyst` | Tin tức, catalysts, events |
| Portfolio Analyst | `portfolio_analyst` | Portfolio optimization, risk |
| On-Chain Analyst | `onchain_analyst` | Whale tracking, on-chain flows |

### Khi nào dùng
- **Full analysis**: Gọi tất cả agents song song qua `task` tool
- **Quick check**: Chỉ gọi agents liên quan
- **Security review**: Chỉ `smart_contract_analyst`
- **Market overview**: `defillama_analyst` + `news_analyst`

### Cách gọi song song (ví dụ)
Để phân tích $UNI, gọi đồng thời:
- task(agent="defillama_analyst", task="Phân tích Uniswap: TVL, chains, competitors")
- task(agent="sentiment_analyst", task="Sentiment cộng đồng về UNI token")
- task(agent="news_analyst", task="Tin tức và catalysts của Uniswap 30 ngày qua")
- task(agent="smart_contract_analyst", task="Security check UNI token contract: 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984")
"""
```

---

## Các agents bổ sung được đề xuất

Ngoài 5 agents trong yêu cầu + On-Chain Analyst, dưới đây là thêm 6 agents có giá trị cao:

### 7. Tokenomics Analyst
**Mục đích**: Phân tích token economics sâu
**Tools cần**: CoinGecko, web scraping
**System prompt focus**:
- Supply schedule (circulating vs total vs max)
- Vesting schedule và unlock timeline
- Token distribution (team, investors, community, treasury)
- Token utility và demand drivers
- Inflation/deflation mechanics

### 8. Whale Tracker Agent
**Mục đích**: Theo dõi large wallets và smart money
**Tools cần**: Block explorer APIs, web_search (Arkham, Nansen)
**System prompt focus**:
- Identify known whale wallets (exchanges, funds, insiders)
- Track inflow/outflow patterns
- Accumulation vs distribution phases
- Copy trading opportunities

### 9. Token Unlock Scheduler
**Mục đích**: Track vesting và unlock events sắp tới
**Tools cần**: web_search (TokenUnlocks.app, Vesting.is, CryptoRank)
**System prompt focus**:
- Upcoming unlock dates
- % supply được unlock (selling pressure)
- Historical price action sau unlock
- Risk assessment cho short-term holds

### 10. Yield Optimizer Agent
**Mục đích**: Tối ưu yield cho capital theo risk preference
**Tools cần**: `get_defillama_yields`, `get_defillama_protocol`, `check_token_security`
**System prompt focus**:
- So sánh yields theo risk level
- Impermanent loss risk cho LP positions
- Protocol security score
- Gas cost consideration

### 11. Governance Analyst
**Mục đích**: Theo dõi DAO governance và proposals
**Tools cần**: web_search (Snapshot.org, Tally, Commonwealth)
**System prompt focus**:
- Active proposals và vote outcomes
- Governance participation rate
- Controversial decisions
- Treasury management

### 12. Technical Analysis Agent
**Mục đích**: Chart patterns và technical indicators
**Tools cần**: `get_live_token_data`, TradingView/Coingecko historical data
**System prompt focus**:
- Key support/resistance levels
- Moving averages (50MA, 200MA)
- RSI, MACD signals
- Chart patterns (head & shoulders, cup & handle, etc.)

---

## Checklist triển khai

```
□ Tạo tool files:
  □ tools/defillama.py
  □ tools/contract_analysis.py  
  □ tools/crypto_sentiment.py
  □ tools/crypto_news.py

□ Đăng ký tools vào registry.py

□ Tạo subagent specs:
  □ subagents/crypto/__init__.py
  □ subagents/crypto/defillama_spec.py
  □ subagents/crypto/smart_contract_spec.py
  □ subagents/crypto/sentiment_spec.py
  □ subagents/crypto/news_spec.py
  □ subagents/crypto/portfolio_spec.py
  □ subagents/crypto/onchain_spec.py

□ Cập nhật chat_deepagent.py:
  □ Import specs
  □ Build tool subsets cho mỗi agent
  □ Thêm vào SubAgentMiddleware

□ Cập nhật system prompt (crypto orchestration instructions)

□ Test:
  □ "Phân tích DeFi market overview"
  □ "Check security của contract 0x..."
  □ "Sentiment của BTC hiện tại"
  □ "Portfolio analysis: 0.5 BTC, 5 ETH, 1000 USDC"
  □ "Full analysis của token Uniswap" (tất cả agents song song)
```

---

## Tips quan trọng

1. **Song song thực sự**: LangGraph's `ToolNode` chạy tất cả `task()` calls trong 1 response **đồng thời** — main agent chỉ cần gọi nhiều `task()` trong 1 turn.

2. **Tool filtering**: Mỗi sub-agent chỉ nhận tools liên quan (không phải toàn bộ 50+ tools) để tránh confusion và tiết kiệm context.

3. **API rate limits**: CoinGecko free tier = 30 req/min, DeFiLlama = unlimited, GoPlus = 2000 req/day. Cân nhắc thêm API keys vào config.

4. **Error handling**: Các free APIs không ổn định. Sub-agents nên fallback sang `web_search` khi API thất bại.

5. **Prompt length**: System prompts của sub-agents nên ngắn gọn (< 500 tokens) để tiết kiệm cost khi spawn nhiều agents cùng lúc.
