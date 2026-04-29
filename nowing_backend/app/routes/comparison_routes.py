"""
Token comparison routes for the crypto analysis feature.

POST /compare/tokens — fetch and compare two tokens using CoinGecko + DeFiLlama data,
then synthesize a verdict with LLM. Results are cached for 30 minutes.
"""

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.llm_config import (
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_llm_config_from_yaml,
)
from app.db import CompareResult, get_async_session
from app.services.new_streaming_service import VercelStreamingService
from app.users import User, current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compare", tags=["compare"])

_COMPARE_CACHE_TTL_MINUTES = 30
_COIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,79}$")
_HTTPX_TIMEOUT = 10.0


async def _fetch_coingecko(coin_id: str) -> dict[str, Any]:
    """Fetch basic token data from CoinGecko free tier."""
    if not _COIN_ID_RE.match(coin_id or ""):
        return {"error": f"Invalid coin_id: {coin_id!r}"}
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false",
    }
    try:
        async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
            resp = await client.get(url, params=params)
        if resp.status_code == 429:
            return {"error": "CoinGecko rate limit"}
        if resp.status_code == 404:
            return {"error": f"Token '{coin_id}' not found on CoinGecko"}
        resp.raise_for_status()
        data = resp.json()
        md = data.get("market_data") or {}
        cp = md.get("current_price") or {}
        return {
            "id": data.get("id"),
            "symbol": (data.get("symbol") or "").upper(),
            "name": data.get("name"),
            "current_price_usd": cp.get("usd"),
            "market_cap": (md.get("market_cap") or {}).get("usd"),
            "total_volume_24h": (md.get("total_volume") or {}).get("usd"),
            "price_change_24h_pct": md.get("price_change_percentage_24h"),
            "price_change_7d_pct": md.get("price_change_percentage_7d"),
            "price_change_30d_pct": md.get("price_change_percentage_30d"),
            "circulating_supply": md.get("circulating_supply"),
            "total_supply": md.get("total_supply"),
            "max_supply": md.get("max_supply"),
            "ath_usd": (md.get("ath") or {}).get("usd"),
            "categories": data.get("categories", []),
        }
    except Exception as e:
        logger.warning("CoinGecko fetch error for %s: %s", coin_id, e)
        return {"error": str(e)}


async def _fetch_defillama_tvl(symbol: str) -> dict[str, Any]:
    """Fetch protocol TVL from DeFiLlama by symbol."""
    try:
        async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
            resp = await client.get("https://api.llama.fi/protocols")
        resp.raise_for_status()
        protocols = resp.json()
        sym_lower = symbol.lower()
        matches = [p for p in protocols if (p.get("symbol") or "").lower() == sym_lower]
        if not matches:
            return {"tvl": None, "protocol": None}
        proto = max(matches, key=lambda p: p.get("tvl") or 0)
        return {
            "tvl": proto.get("tvl"),
            "protocol_name": proto.get("name"),
            "category": proto.get("category"),
            "chains": proto.get("chains", [])[:5],
        }
    except Exception as e:
        logger.warning("DeFiLlama fetch error for %s: %s", symbol, e)
        return {"tvl": None, "error": str(e)}


def _build_compare_prompt(
    primary_symbol: str,
    secondary_symbol: str,
    primary_data: dict,
    secondary_data: dict,
) -> str:
    def fmt(data: dict) -> str:
        lines = []
        if data.get("error"):
            return f"  ERROR: {data['error']}"
        if data.get("current_price_usd") is not None:
            lines.append(f"  Price: ${data['current_price_usd']:,.4f}")
        if data.get("market_cap"):
            lines.append(f"  Market Cap: ${data['market_cap']:,.0f}")
        if data.get("total_volume_24h"):
            lines.append(f"  24h Volume: ${data['total_volume_24h']:,.0f}")
        if data.get("price_change_24h_pct") is not None:
            lines.append(f"  24h Change: {data['price_change_24h_pct']:+.1f}%")
        if data.get("price_change_7d_pct") is not None:
            lines.append(f"  7d Change: {data['price_change_7d_pct']:+.1f}%")
        if data.get("circulating_supply"):
            lines.append(f"  Circulating Supply: {data['circulating_supply']:,.0f}")
        if data.get("tvl"):
            lines.append(f"  TVL: ${data['tvl']:,.0f}")
        if data.get("protocol_name"):
            lines.append(f"  DeFiLlama Protocol: {data['protocol_name']} ({data.get('category', '?')})")
        return "\n".join(lines) if lines else "  No data available"

    return f"""Compare {primary_symbol} vs {secondary_symbol}:

**{primary_symbol}:**
{fmt(primary_data)}

**{secondary_symbol}:**
{fmt(secondary_data)}

Write a concise comparison analysis (200-300 words):
1. Side-by-side metric comparison
2. Which token has stronger fundamentals and why
3. Risk profile of each
4. Final verdict: which is better for (a) value accrual, (b) yield farming, (c) speculation

Be direct. Highlight key differences. No bullet-point walls — use 2-3 short paragraphs."""


async def _stream_compare(
    primary_token: str,
    secondary_token: str,
    primary_coingecko_id: str | None,
    secondary_coingecko_id: str | None,
    llm_config_id: int,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    streaming_service = VercelStreamingService()

    # Prefer explicit CoinGecko slug from FE search; fall back to lowercased symbol
    # (which only works if the symbol happens to also be the CG slug, e.g. "btc")
    primary_cg_id = (primary_coingecko_id or primary_token).lower()
    secondary_cg_id = (secondary_coingecko_id or secondary_token).lower()

    primary_cg, secondary_cg, primary_tvl, secondary_tvl = await asyncio.gather(
        _fetch_coingecko(primary_cg_id),
        _fetch_coingecko(secondary_cg_id),
        _fetch_defillama_tvl(primary_token),
        _fetch_defillama_tvl(secondary_token),
    )

    primary_data = {**primary_cg, **primary_tvl}
    secondary_data = {**secondary_cg, **secondary_tvl}

    yield streaming_service.format_data(
        "compare-data",
        {"primary": primary_data, "secondary": secondary_data},
    )

    # Load LLM
    if llm_config_id >= 0:
        agent_config = await load_agent_config(
            session=session, config_id=llm_config_id, search_space_id=None
        )
        llm = create_chat_litellm_from_agent_config(agent_config) if agent_config else None
    else:
        llm_config = load_llm_config_from_yaml(llm_config_id=llm_config_id)
        llm = create_chat_litellm_from_config(llm_config) if llm_config else None

    if not llm:
        yield streaming_service.format_error("LLM not available for verdict synthesis")
        yield streaming_service.format_done()
        return

    # Stream verdict
    verdict_messages = [
        SystemMessage(
            content="You are a crypto analyst. Write a clear, direct comparison. No hype. Facts only."
        ),
        HumanMessage(
            content=_build_compare_prompt(
                primary_token, secondary_token, primary_data, secondary_data
            )
        ),
    ]

    verdict = ""
    stream_completed = False
    try:
        try:
            async for chunk in llm.astream(verdict_messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    verdict += token
                    yield streaming_service.format_data(
                        "compare-verdict-delta", {"delta": token}
                    )
            stream_completed = True
        except asyncio.CancelledError:
            logger.info("[compare_tokens] Stream cancelled by client")
            raise
        except Exception as e:
            logger.error("[compare_tokens] LLM stream error: %s", e)
            yield streaming_service.format_error(f"Verdict synthesis failed: {e}")
            yield streaming_service.format_done()
            return
    finally:
        # Persist cache only if stream completed cleanly — never persist partial verdict
        if stream_completed and verdict:
            try:
                result = CompareResult(
                    primary_token=primary_token.upper(),
                    secondary_token=secondary_token.upper(),
                    primary_data=primary_data,
                    secondary_data=secondary_data,
                    verdict=verdict,
                )
                session.add(result)
                await session.commit()
            except Exception as e:
                logger.warning("[compare_tokens] Failed to persist compare result: %s", e)

    yield streaming_service.format_data(
        "compare-complete",
        {
            "primary_token": primary_token,
            "secondary_token": secondary_token,
        },
    )
    yield streaming_service.format_done()


_TOKEN_RE = re.compile(r"^[A-Za-z0-9\-]{1,32}$")


class CompareTokensRequest(BaseModel):
    primary_token: str = Field(..., min_length=1, max_length=32)
    secondary_token: str = Field(..., min_length=1, max_length=32)
    primary_coingecko_id: str | None = Field(default=None, max_length=80)
    secondary_coingecko_id: str | None = Field(default=None, max_length=80)
    llm_config_id: int = -1

    @field_validator("primary_token", "secondary_token")
    @classmethod
    def _validate_token(cls, v: str) -> str:
        if not _TOKEN_RE.match(v):
            raise ValueError("token must match [A-Za-z0-9-], length 1-32")
        return v


@router.post("/tokens")
async def compare_tokens(
    req: CompareTokensRequest,
    session: AsyncSession = Depends(get_async_session),
    _current_user: User = Depends(current_active_user),
) -> StreamingResponse:
    primary = req.primary_token.upper()
    secondary = req.secondary_token.upper()

    if primary == secondary:
        raise HTTPException(
            status_code=400, detail="Cannot compare a token with itself"
        )

    # Check cache — skip rows with empty verdict (treat as miss to avoid infinite spinner)
    cache_cutoff = datetime.now(UTC) - timedelta(minutes=_COMPARE_CACHE_TTL_MINUTES)
    cached = await session.execute(
        select(CompareResult).where(
            CompareResult.primary_token == primary,
            CompareResult.secondary_token == secondary,
            CompareResult.created_at >= cache_cutoff,
        )
    )
    cached_result = cached.scalars().first()

    if cached_result and not (cached_result.verdict or "").strip():
        # Stale empty cache row — ignore so we re-run synthesis
        cached_result = None

    if cached_result:
        streaming_service = VercelStreamingService()

        async def _serve_cache() -> AsyncGenerator[str, None]:
            yield streaming_service.format_data(
                "compare-data",
                {
                    "primary": cached_result.primary_data,
                    "secondary": cached_result.secondary_data,
                },
            )
            if cached_result.verdict:
                yield streaming_service.format_data(
                    "compare-verdict-delta", {"delta": cached_result.verdict}
                )
            yield streaming_service.format_data(
                "compare-complete",
                {
                    "primary_token": primary,
                    "secondary_token": secondary,
                    "cached": True,
                },
            )
            yield streaming_service.format_done()

        return StreamingResponse(
            _serve_cache(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    return StreamingResponse(
        _stream_compare(
            primary_token=primary,
            secondary_token=secondary,
            primary_coingecko_id=req.primary_coingecko_id,
            secondary_coingecko_id=req.secondary_coingecko_id,
            llm_config_id=req.llm_config_id,
            session=session,
        ),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ─── CoinGecko price proxy (Story 9-UX-2 — avoid client-side rate limit) ──────


@router.get("/coingecko-price/{coin_id}")
async def coingecko_price_proxy(
    coin_id: str,
    _user: User = Depends(current_active_user),
) -> dict[str, Any]:
    if not _COIN_ID_RE.match(coin_id or ""):
        raise HTTPException(status_code=400, detail=f"Invalid coin_id: {coin_id!r}")

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=_HTTPX_TIMEOUT) as client:
            resp = await client.get(url, params=params)
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail="CoinGecko rate limit")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Token '{coin_id}' not found")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("CoinGecko price proxy error for %s: %s", coin_id, exc)
        raise HTTPException(status_code=502, detail="CoinGecko API error") from exc
