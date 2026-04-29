"""
Narration templates for SourceAttributionMiddleware (Story 9-UX-1).

Template strings are deterministic — no LLM call, just string formatting.
Pre-call narration must be emitted BEFORE handler(request) per AC2.
Post-call narration is emitted AFTER handler(request) using format-string
substitution against extracted fact summaries (AC2 second-half spec example:
"Thấy TVL $3.2B, tăng 2.1% vs 7d...").
"""

from __future__ import annotations

from typing import Any

# Pre-call narration: emitted before tool execution
PRE_CALL: dict[str, str] = {
    "get_coingecko_token_info": "Đang query CoinGecko cho thông tin token...",
    "get_coingecko_market_chart": "Đang lấy lịch sử giá từ CoinGecko...",
    "get_defillama_protocol": "Đang query DeFiLlama cho dữ liệu TVL...",
    "get_defillama_pools": "Đang lấy danh sách yield pools từ DeFiLlama...",
    "check_token_security": "Đang kiểm tra bảo mật hợp đồng thông minh qua GoPlus...",
    "get_cryptopanic_news": "Đang lấy tin tức crypto mới nhất từ CryptoPanic...",
    "get_reddit_crypto_sentiment": "Đang phân tích sentiment từ Reddit...",
    "get_fear_greed_index": "Đang lấy chỉ số Fear & Greed...",
    "chainlens_deep_research": "Đang thực hiện nghiên cứu on-chain chuyên sâu...",
    "get_certik_audit_score": "Đang lấy điểm bảo mật CertiK Skynet...",
    "get_certik_incident_history": "Đang kiểm tra lịch sử sự cố từ CertiK...",
    "get_nansen_smart_money": "Đang phân tích dòng tiền smart money từ Nansen...",
    "get_nansen_wallet_label": "Đang tra cứu nhãn ví từ Nansen...",
    "get_nansen_token_god_mode": "Đang lấy phân bố holder từ Nansen Token God Mode...",
    "run_dune_query": "Đang thực thi truy vấn on-chain từ Dune Analytics...",
    "get_tokeninsight_rating": "Đang lấy xếp hạng từ TokenInsight...",
    "get_tokeninsight_research_snippet": "Đang lấy phân tích chuyên sâu từ TokenInsight...",
}


# Source domain mapping: tool_name → (domain, favicon_url, deeplink_template)
# `deeplink_template` may contain `{symbol}` placeholder filled at emit time.
TOOL_SOURCE_MAP: dict[str, tuple[str, str, str]] = {
    "get_coingecko_token_info": (
        "coingecko.com",
        "https://icons.duckduckgo.com/ip3/coingecko.com.ico",
        "https://www.coingecko.com/",
    ),
    "get_coingecko_market_chart": (
        "coingecko.com",
        "https://icons.duckduckgo.com/ip3/coingecko.com.ico",
        "https://www.coingecko.com/",
    ),
    "get_defillama_protocol": (
        "defillama.com",
        "https://icons.duckduckgo.com/ip3/defillama.com.ico",
        "https://defillama.com/",
    ),
    "get_defillama_pools": (
        "defillama.com",
        "https://icons.duckduckgo.com/ip3/defillama.com.ico",
        "https://defillama.com/yields",
    ),
    "check_token_security": (
        "gopluslabs.io",
        "https://icons.duckduckgo.com/ip3/gopluslabs.io.ico",
        "https://gopluslabs.io/",
    ),
    "get_cryptopanic_news": (
        "cryptopanic.com",
        "https://icons.duckduckgo.com/ip3/cryptopanic.com.ico",
        "https://cryptopanic.com/",
    ),
    "get_reddit_crypto_sentiment": (
        "reddit.com",
        "https://icons.duckduckgo.com/ip3/reddit.com.ico",
        "https://reddit.com/r/CryptoCurrency",
    ),
    "get_fear_greed_index": (
        "alternative.me",
        "https://icons.duckduckgo.com/ip3/alternative.me.ico",
        "https://alternative.me/crypto/fear-and-greed-index/",
    ),
    "chainlens_deep_research": (
        "chainlens.xyz",
        "https://icons.duckduckgo.com/ip3/chainlens.xyz.ico",
        "https://chainlens.xyz/",
    ),
    "get_certik_audit_score": (
        "certik.com",
        "https://icons.duckduckgo.com/ip3/certik.com.ico",
        "https://www.certik.com/",
    ),
    "get_certik_incident_history": (
        "certik.com",
        "https://icons.duckduckgo.com/ip3/certik.com.ico",
        "https://www.certik.com/",
    ),
    "get_nansen_smart_money": (
        "nansen.ai",
        "https://icons.duckduckgo.com/ip3/nansen.ai.ico",
        "https://app.nansen.ai/",
    ),
    "get_nansen_wallet_label": (
        "nansen.ai",
        "https://icons.duckduckgo.com/ip3/nansen.ai.ico",
        "https://app.nansen.ai/",
    ),
    "get_nansen_token_god_mode": (
        "nansen.ai",
        "https://icons.duckduckgo.com/ip3/nansen.ai.ico",
        "https://app.nansen.ai/",
    ),
    "run_dune_query": (
        "dune.com",
        "https://icons.duckduckgo.com/ip3/dune.com.ico",
        "https://dune.com/",
    ),
    "get_tokeninsight_rating": (
        "tokeninsight.com",
        "https://icons.duckduckgo.com/ip3/tokeninsight.com.ico",
        "https://tokeninsight.com/",
    ),
    "get_tokeninsight_research_snippet": (
        "tokeninsight.com",
        "https://icons.duckduckgo.com/ip3/tokeninsight.com.ico",
        "https://tokeninsight.com/",
    ),
}


# Tone classification per tool — drives FE animation hue (fetching/analyzing/synthesizing).
TOOL_TONE: dict[str, str] = {
    "get_coingecko_token_info": "fetching",
    "get_coingecko_market_chart": "fetching",
    "get_defillama_protocol": "fetching",
    "get_defillama_pools": "fetching",
    "check_token_security": "analyzing",  # security audit = analyzing
    "get_cryptopanic_news": "fetching",
    "get_reddit_crypto_sentiment": "analyzing",  # sentiment scoring
    "get_fear_greed_index": "fetching",
    "chainlens_deep_research": "synthesizing",  # multi-source synthesis
    "get_certik_audit_score": "analyzing",
    "get_certik_incident_history": "fetching",
    "get_nansen_smart_money": "analyzing",
    "get_nansen_wallet_label": "fetching",
    "get_nansen_token_god_mode": "analyzing",
    "run_dune_query": "fetching",
    "get_tokeninsight_rating": "fetching",
    "get_tokeninsight_research_snippet": "analyzing",
}


def post_call_narration(tool_name: str, result: Any) -> str | None:
    """Build a post-call narration line summarizing 1-2 key findings.

    Returns None if the tool / result combination doesn't yield a meaningful
    summary — the middleware then skips emitting a post-call event for that call.

    All numeric coercions are guarded — non-numeric tool outputs (string TVL
    from a future API change, NaN, etc.) silently fall back to None rather than
    raising into the tool middleware. Field names verified against actual tool
    return shapes in `tools/{contract_analysis,crypto_news,crypto_sentiment,defillama}.py`.
    """
    if not isinstance(result, dict):
        return None

    if tool_name == "get_defillama_protocol":
        tvl = _safe_float(result.get("tvl"))
        change = _safe_float(result.get("change_7d") or result.get("change_1d"))
        if tvl is not None:
            tvl_str = _format_usd(tvl)
            if change is not None:
                sign = "+" if change >= 0 else ""
                return f"Thấy TVL {tvl_str}, {sign}{change:.1f}% vs 7d. Đang kiểm tra yield pools..."
            return f"Thấy TVL {tvl_str}. Đang kiểm tra thêm metrics..."

    if tool_name == "get_coingecko_token_info":
        # Actual field: current_price_usd (verified in crypto_news.py:180)
        price = _safe_float(result.get("current_price_usd") or result.get("price"))
        change = _safe_float(
            result.get("price_change_24h_pct") or result.get("price_change_24h")
        )
        if price is not None:
            price_str = _format_usd(price)
            if change is not None:
                sign = "+" if change >= 0 else ""
                return f"Giá hiện tại {price_str} ({sign}{change:.1f}% 24h). Đang lấy chart..."
            return f"Giá hiện tại {price_str}. Đang lấy thêm dữ liệu..."

    if tool_name == "check_token_security":
        # Actual fields: risk_level (str: "low"/"medium"/"high") + risk_score (numeric)
        risk_level = result.get("risk_level")
        score = _safe_float(result.get("risk_score"))
        if risk_level:
            if score is not None:
                return f"Security {risk_level} ({score:.0f}/100). Đang đối chiếu kết quả..."
            return f"Security risk: {risk_level}. Đang đối chiếu kết quả..."

    if tool_name == "get_fear_greed_index":
        # Actual field: fear_greed_value (verified in crypto_sentiment.py:72)
        value = _safe_float(result.get("fear_greed_value") or result.get("value"))
        classification = (
            result.get("classification")
            or result.get("value_classification")
            or result.get("fear_greed_classification")
        )
        if value is not None:
            if classification:
                return f"Fear & Greed: {value:.0f} ({classification})."
            return f"Fear & Greed Index: {value:.0f}."

    if tool_name == "get_defillama_pools":
        pools = result.get("pools") or []
        if isinstance(pools, list) and pools:
            return f"Tìm thấy {len(pools)} yield pools, đang sắp xếp theo APY..."

    if tool_name == "get_certik_audit_score":
        score = _safe_float(result.get("overall_score") or result.get("security_score"))
        if score is not None:
            return f"CertiK Skynet score: {score:.0f}/100. Đang đối chiếu với GoPlus..."

    if tool_name == "get_tokeninsight_rating":
        rating = result.get("overall_rating")
        score = _safe_float(result.get("overall_score"))
        if rating:
            suffix = f" ({score:.0f}/100)" if score is not None else ""
            return f"TokenInsight rating: {rating}{suffix}."

    if tool_name == "get_nansen_smart_money":
        signal = result.get("signal")
        if signal:
            return f"Smart money signal: {signal}. Đang phân tích chi tiết..."

    return None


def extract_facts(tool_name: str, result: Any) -> list[dict[str, Any]]:
    """Extract numeric facts from a tool result for AC4 fact_captured events.

    Returns a list of {factSummary, value?, unit?} dicts. Empty list = no facts.
    All coercions guarded by _safe_float — never raises into the caller.
    """
    if not isinstance(result, dict):
        return []

    facts: list[dict[str, Any]] = []

    if tool_name == "get_defillama_protocol":
        tvl = _safe_float(result.get("tvl"))
        if tvl is not None:
            facts.append({"factSummary": f"TVL {_format_usd(tvl)}", "value": tvl, "unit": "usd"})

    if tool_name == "get_coingecko_token_info":
        # Field verified: current_price_usd in crypto_news.py:180
        price = _safe_float(result.get("current_price_usd") or result.get("price"))
        if price is not None:
            facts.append({"factSummary": f"Price {_format_usd(price)}", "value": price, "unit": "usd"})
        mc = _safe_float(result.get("market_cap") or result.get("market_cap_usd"))
        if mc is not None:
            facts.append({"factSummary": f"MC {_format_usd(mc)}", "value": mc, "unit": "usd"})

    if tool_name == "check_token_security":
        # Field verified: risk_score in contract_analysis.py:282
        score = _safe_float(result.get("risk_score"))
        if score is not None:
            facts.append({"factSummary": f"Risk score {score:.0f}/100", "value": score, "unit": "score"})

    if tool_name == "get_fear_greed_index":
        # Field verified: fear_greed_value in crypto_sentiment.py:72
        value = _safe_float(result.get("fear_greed_value") or result.get("value"))
        if value is not None:
            facts.append({"factSummary": f"Fear & Greed {value:.0f}", "value": value, "unit": "score"})

    if tool_name == "get_certik_audit_score":
        score = _safe_float(result.get("overall_score") or result.get("security_score"))
        if score is not None:
            facts.append({"factSummary": f"CertiK score {score:.0f}/100", "value": score, "unit": "score"})

    if tool_name == "get_tokeninsight_rating":
        rating = result.get("overall_rating")
        score = _safe_float(result.get("overall_score"))
        if rating:
            facts.append({"factSummary": f"TokenInsight {rating}", "value": score, "unit": "rating"})

    return facts


def _safe_float(value: Any) -> float | None:
    """Coerce a value to float; return None on any failure (string, NaN, None, dict, etc.).

    V2-P4: prevents tool middleware from raising on non-numeric responses
    (e.g. API returns "1.2B" string, or NaN, or `Decimal('1.2')` from a SQL tool).
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    # Reject NaN/Inf — they break downstream JSON serialization.
    if f != f or f == float("inf") or f == float("-inf"):
        return None
    return f


def _format_usd(value: float | int) -> str:
    """Compact USD formatting: $1.2B / $345M / $1.5K."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.0f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.1f}K"
    if abs(v) >= 1:
        return f"${v:.2f}"
    return f"${v:.4f}"
