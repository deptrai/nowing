"""CertiK Skynet tools for Nowing deep agent.

Provides 2 tools for CertiK security intelligence:
- get_certik_audit_score: Overall Skynet score + category breakdown
- get_certik_incident_history: Past hacks, timeline, and impact

All tools return {"source_domain": "certik.com", ...} so
SourceAttributionMiddleware emits citation events (AC2, Story 9-UX-1).

CertiK Skynet's public API is free for non-commercial use (60 req/min).
No API key required for basic score endpoint.

Rate limits (AC14):
    Free tier: 60 req/min.
"""

import logging
import os
import re
from typing import Any

import httpx
from langchain_core.tools import tool

from ._rate_limiter import _ApiRateLimiter

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_CERTIK_BASE = "https://api.certik.com/v1"

# AC14: CertiK free tier = 60 req/min
_certik_rate_limit = int(os.getenv("CERTIK_RATE_LIMIT", "60"))
_certik_rl = _ApiRateLimiter(max_calls=_certik_rate_limit, window_seconds=60.0, name="certik")

# CertiK uses project slugs for some endpoints and contract addresses for others.
# Address format: Ethereum 0x...40 hex chars, or Solana base58 32-44 chars.
_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _api_key() -> str | None:
    return os.getenv("CERTIK_API_KEY", "").strip() or None


def _auth_headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        return {}
    # CertiK uses Authorization Bearer for paid endpoints
    return {"Authorization": f"Bearer {key}"}


def _unavailable_error(status: int) -> dict[str, Any]:
    messages = {
        401: "CertiK API key invalid. Check CERTIK_API_KEY env var.",
        403: "CertiK endpoint requires authentication.",
        429: "CertiK rate limit exceeded (60 req/min free tier). Retry later.",
    }
    return {
        "error": messages.get(status, f"CertiK API returned HTTP {status}"),
        "status": status,
        "source_domain": "certik.com",
    }


def create_certik_audit_score_tool():
    """Factory: get_certik_audit_score — Skynet security score for a token."""

    @tool
    async def get_certik_audit_score(
        token_address: str,
        chain: str = "ethereum",
    ) -> dict[str, Any]:
        """Get the CertiK Skynet security score for a token contract.

        Returns an overall security score (0–100) and breakdown across
        code quality, market safety, governance, and community dimensions.
        Also returns audit findings count and formal audit history.

        Use when user asks about CertiK audit, security score,
        or wants to cross-reference with GoPlus token security (AC6).

        When CertiK score diverges from GoPlus by >15 points, flag it
        as a conflict for the synthesizer to surface (AC6, AC7).

        Args:
            token_address: EVM token contract address (0x...).
            chain: Chain — "ethereum", "bsc", "polygon", "solana", etc.

        Returns:
            Dict with overall_score (int 0-100), categories (dict),
            audit_count (int), audited_by (list[str]),
            source_domain "certik.com", or {"error": ..., "status": ...}.
        """
        if not _EVM_ADDRESS_RE.match(token_address or ""):
            return {"error": f"Invalid EVM address: {token_address!r}", "source_domain": "certik.com"}

        await _certik_rl.acquire()
        # CertiK Skynet public endpoint — returns JSON for any token
        url = f"{_CERTIK_BASE}/skynet/leaderboard"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    params={
                        "filters[contracts.address]": token_address,
                        "filters[contracts.chain]": chain,
                    },
                    headers=_auth_headers(),
                )
            if resp.status_code in (401, 403, 429):
                return _unavailable_error(resp.status_code)
            if resp.status_code == 404:
                return {
                    "error": f"Token {token_address} not found on CertiK Skynet",
                    "status": 404,
                    "source_domain": "certik.com",
                }
            resp.raise_for_status()
            data = resp.json()

            # Skynet leaderboard returns a list; pick the first matching entry
            items = data.get("data", {}).get("rows", [])
            if not items:
                return {
                    "error": "No CertiK data found for this token address",
                    "source_domain": "certik.com",
                }
            item = items[0]

            security_score = item.get("securityScore", item.get("overallScore", 0))
            audits = item.get("audits", [])

            categories = {
                "code": item.get("codeScore", None),
                "market": item.get("marketScore", None),
                "governance": item.get("governanceScore", None),
                "community": item.get("communityScore", None),
            }
            # Remove None values so callers can check which are present
            categories = {k: v for k, v in categories.items() if v is not None}

            return {
                "source_domain": "certik.com",
                "token_address": token_address,
                "chain": chain,
                "overall_score": int(security_score),
                "categories": categories,
                "audit_count": len(audits),
                "audited_by": [a.get("auditor", "") for a in audits],
                "project_name": item.get("name", ""),
                "skynet_url": f"https://www.certik.com/projects/{item.get('slug', token_address)}",
            }
        except httpx.TimeoutException:
            logger.warning("certik audit_score timeout for %s", token_address)
            return {"error": "CertiK API timeout", "source_domain": "certik.com"}
        except httpx.HTTPStatusError as exc:
            logger.warning("certik audit_score HTTP error %s for %s", exc.response.status_code, token_address)
            return {"error": f"CertiK API error: {exc.response.status_code}", "source_domain": "certik.com"}
        except Exception as exc:
            logger.exception("certik audit_score unexpected error for %s", token_address)
            return {"error": f"Unexpected error: {exc}", "source_domain": "certik.com"}

    return get_certik_audit_score


def create_certik_incident_history_tool():
    """Factory: get_certik_incident_history — past hacks and incidents for a project."""

    @tool
    async def get_certik_incident_history(project_name: str) -> list[dict[str, Any]]:
        """Get the incident and hack history for a crypto project from CertiK.

        Returns a list of security incidents (exploits, rug pulls, flash
        loan attacks, etc.) with timeline and financial impact (USD lost).

        Use when user asks if a project has been hacked, exploited, or
        has a history of security incidents.

        Args:
            project_name: Project name or slug (e.g. "uniswap", "curve",
                "compound"). Not case-sensitive.

        Returns:
            List of incident dicts with date, type, amount_lost_usd,
            description, source_domain "certik.com";
            or a list containing a single {"error": ...} dict.
        """
        if not project_name or not project_name.strip():
            return [{"error": "project_name is required", "source_domain": "certik.com"}]

        slug = project_name.strip().lower().replace(" ", "-")
        await _certik_rl.acquire()
        url = f"{_CERTIK_BASE}/skynet/incidents"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    params={"filters[projectName]": slug},
                    headers=_auth_headers(),
                )
            if resp.status_code in (401, 403, 429):
                return [_unavailable_error(resp.status_code)]
            if resp.status_code == 404:
                return []  # No incidents found — not an error
            resp.raise_for_status()
            data = resp.json()

            incidents = data.get("data", {}).get("rows", [])
            return [
                {
                    "source_domain": "certik.com",
                    "date": inc.get("date", ""),
                    "type": inc.get("incidentType", "unknown"),
                    "amount_lost_usd": inc.get("amountLostUsd", 0),
                    "description": inc.get("description", ""),
                    "project": inc.get("projectName", project_name),
                    "tx_hash": inc.get("txHash", ""),
                    "certik_url": (
                        f"https://www.certik.com/resources/blog/{inc.get('slug', '')}"
                        if inc.get("slug")
                        else ""
                    ),
                }
                for inc in incidents
            ]
        except httpx.TimeoutException:
            logger.warning("certik incident_history timeout for %s", project_name)
            return [{"error": "CertiK API timeout", "source_domain": "certik.com"}]
        except httpx.HTTPStatusError as exc:
            logger.warning("certik incident_history HTTP error %s for %s", exc.response.status_code, project_name)
            return [{"error": f"CertiK API error: {exc.response.status_code}", "source_domain": "certik.com"}]
        except Exception as exc:
            logger.exception("certik incident_history unexpected error for %s", project_name)
            return [{"error": f"Unexpected error: {exc}", "source_domain": "certik.com"}]

    return get_certik_incident_history
