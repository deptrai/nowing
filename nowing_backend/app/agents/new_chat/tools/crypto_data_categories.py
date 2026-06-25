from enum import Enum


class DataCategory(str, Enum):
    PRICE_REALTIME = "price_realtime"
    SENTIMENT_INDEX = "sentiment_index"
    DEFI_TVL = "defi_tvl"
    DEFI_YIELDS = "defi_yields"
    DEFI_OVERVIEW = "defi_overview"
    NEWS = "news"
    TOKEN_FUNDAMENTALS = "token_fundamentals"
    SMART_MONEY = "smart_money"
    SECURITY_AUDIT = "security_audit"
    CONTRACT_INFO = "contract_info"
    TOKENINSIGHT = "tokeninsight"
    CERTIK_INCIDENTS = "certik_incidents"


TTL_SECONDS: dict[str, int] = {
    DataCategory.PRICE_REALTIME: 5 * 60,
    DataCategory.SENTIMENT_INDEX: 15 * 60,
    DataCategory.DEFI_TVL: 60 * 60,
    DataCategory.DEFI_YIELDS: 2 * 60 * 60,
    DataCategory.DEFI_OVERVIEW: 2 * 60 * 60,
    DataCategory.NEWS: 60 * 60,
    DataCategory.TOKEN_FUNDAMENTALS: 60 * 60,
    DataCategory.SMART_MONEY: 2 * 60 * 60,
    DataCategory.SECURITY_AUDIT: 24 * 60 * 60,
    DataCategory.CONTRACT_INFO: 24 * 60 * 60,
    DataCategory.TOKENINSIGHT: 24 * 60 * 60,
    DataCategory.CERTIK_INCIDENTS: 24 * 60 * 60,
}

# Maps tool_name → (DataCategory, api_source)
TOOL_CATEGORY_MAP: dict[str, tuple[DataCategory, str]] = {
    "get_live_token_price": (DataCategory.PRICE_REALTIME, "dexscreener"),
    "get_live_token_data": (DataCategory.PRICE_REALTIME, "dexscreener"),
    "get_cmc_sentiment": (DataCategory.SENTIMENT_INDEX, "coinmarketcap"),
    "get_reddit_crypto_sentiment": (DataCategory.SENTIMENT_INDEX, "reddit"),
    "get_fear_greed_index": (DataCategory.SENTIMENT_INDEX, "alternative.me"),
    "get_defillama_protocol": (DataCategory.DEFI_TVL, "defillama"),
    "get_defillama_yields": (DataCategory.DEFI_YIELDS, "defillama"),
    "get_defillama_tvl_overview": (DataCategory.DEFI_OVERVIEW, "defillama"),
    "get_defillama_stablecoins": (DataCategory.DEFI_OVERVIEW, "defillama"),
    "get_defillama_bridges": (DataCategory.DEFI_OVERVIEW, "defillama"),
    "get_crypto_news": (DataCategory.NEWS, "cryptopanic"),
    "get_coingecko_token_info": (DataCategory.TOKEN_FUNDAMENTALS, "coingecko"),
    "get_nansen_smart_money": (DataCategory.SMART_MONEY, "nansen"),
    "get_nansen_wallet_label": (DataCategory.SMART_MONEY, "nansen"),
    "get_nansen_token_god_mode": (DataCategory.SMART_MONEY, "nansen"),
    "get_smart_money_flow": (DataCategory.SMART_MONEY, "nansen"),
    # run_dune_query excluded: Dune query IDs are not token-resolvable
    "check_token_security": (DataCategory.SECURITY_AUDIT, "goplus"),
    "get_certik_audit_score": (DataCategory.SECURITY_AUDIT, "certik"),
    "get_contract_info": (DataCategory.CONTRACT_INFO, "etherscan"),
    "get_tokeninsight_rating": (DataCategory.TOKENINSIGHT, "tokeninsight"),
    "get_tokeninsight_research_snippet": (DataCategory.TOKENINSIGHT, "tokeninsight"),
    "get_certik_incident_history": (DataCategory.CERTIK_INCIDENTS, "certik"),
}
