"""Unit tests for Nansen smart money tools.

Endpoint: POST /api/v1/tgm/who-bought-sold
Auth header: apiKey
Response: {"data": [{"address", "address_label", "bought_volume_usd", "sold_volume_usd"}]}
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.new_chat.tools.nansen_smart_money import (
    create_nansen_smart_money_tool,
    create_nansen_wallet_label_tool,
    create_nansen_token_god_mode_tool,
)

_VALID_TOKEN = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"  # UNI token
_VALID_WALLET = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # vitalik.eth


def _mock_response(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        mock_req = MagicMock(spec=Request)
        mock_resp = MagicMock(spec=Response)
        mock_resp.status_code = status_code
        m.raise_for_status.side_effect = HTTPStatusError("err", request=mock_req, response=mock_resp)
    return m


def _patch_httpx_post(response):
    """Patch httpx.AsyncClient so .post() returns the given response."""
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.post.return_value = response
    return patch("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", mock_cls), mock_client


def _patch_httpx_get(response):
    """Patch httpx.AsyncClient so .get() returns the given response (wallet label / god mode)."""
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = response
    return patch("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", mock_cls), mock_client


# ── get_nansen_smart_money (POST /api/v1/tgm/who-bought-sold) ─────────────────

@pytest.fixture
def smart_money_tool():
    return create_nansen_smart_money_tool()


@pytest.mark.asyncio
async def test_smart_money_success(smart_money_tool):
    """200 response with 2 wallets: net flow = bought - sold per wallet."""
    payload = {
        "data": [
            {
                "address": _VALID_WALLET,
                "address_label": "Vitalik.eth",
                "bought_volume_usd": 250000.0,
                "sold_volume_usd": 50000.0,
            },
            {
                "address": "0xabc" + "a" * 37,
                "address_label": "Jump Trading",
                "bought_volume_usd": 10000.0,
                "sold_volume_usd": 210000.0,
            },
        ],
        "pagination": {"page": 1, "per_page": 30, "is_last_page": True},
    }
    patcher, _ = _patch_httpx_post(_mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})

    assert result["source_domain"] == "nansen.ai"
    # Vitalik: 250k bought - 50k sold = +200k (accumulating)
    # Jump: 10k bought - 210k sold = -200k (distributing)
    # net total = 0 -> signal neutral
    assert result["signal"] == "neutral"
    assert len(result["smart_money_wallets"]) == 2
    assert "error" not in result

    vitalik = next(w for w in result["smart_money_wallets"] if w["label"] == "Vitalik.eth")
    assert vitalik["net_flow_usd"] == pytest.approx(200000.0)
    assert vitalik["direction"] == "accumulating"

    jump = next(w for w in result["smart_money_wallets"] if w["label"] == "Jump Trading")
    assert jump["net_flow_usd"] == pytest.approx(-200000.0)
    assert jump["direction"] == "distributing"


@pytest.mark.asyncio
async def test_smart_money_accumulating_signal(smart_money_tool):
    payload = {
        "data": [
            {"address": "0x" + "a" * 40, "address_label": "Fund A", "bought_volume_usd": 1_000_000.0, "sold_volume_usd": 0.0},
        ],
        "pagination": {"page": 1, "per_page": 30, "is_last_page": True},
    }
    patcher, _ = _patch_httpx_post(_mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["signal"] == "accumulating"
    assert result["net_flow_24h_usd"] == pytest.approx(1_000_000.0)


@pytest.mark.asyncio
async def test_smart_money_distributing_signal(smart_money_tool):
    payload = {
        "data": [
            {"address": "0x" + "b" * 40, "address_label": "Seller", "bought_volume_usd": 0.0, "sold_volume_usd": 500_000.0},
        ],
        "pagination": {"page": 1, "per_page": 30, "is_last_page": True},
    }
    patcher, _ = _patch_httpx_post(_mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["signal"] == "distributing"
    assert result["net_flow_24h_usd"] == pytest.approx(-500_000.0)


@pytest.mark.asyncio
async def test_smart_money_empty_data(smart_money_tool):
    """Empty data list -> neutral signal, wallet_count=0, no error."""
    payload = {"data": [], "pagination": {"page": 1, "per_page": 30, "is_last_page": True}}
    patcher, _ = _patch_httpx_post(_mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["signal"] == "neutral"
    assert result["wallet_count"] == 0
    assert result["smart_money_wallets"] == []
    assert "error" not in result


@pytest.mark.asyncio
async def test_smart_money_404_returns_empty_not_error(smart_money_tool):
    """404 = token not tracked by Nansen — must return empty wallets, NOT error dict."""
    patcher, _ = _patch_httpx_post(_mock_response({}, 404))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert "error" not in result
    assert result["smart_money_wallets"] == []
    assert result["signal"] == "neutral"


@pytest.mark.asyncio
async def test_smart_money_missing_api_key(smart_money_tool):
    with patch.dict("os.environ", {}, clear=True):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["status"] == 401
    assert result["source_domain"] == "nansen.ai"


@pytest.mark.asyncio
async def test_smart_money_invalid_address(smart_money_tool):
    with patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": "not-an-address"})
    assert "error" in result
    assert result["source_domain"] == "nansen.ai"


@pytest.mark.asyncio
async def test_smart_money_401_response(smart_money_tool):
    patcher, _ = _patch_httpx_post(_mock_response({}, 401))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["status"] == 401
    assert result["source_domain"] == "nansen.ai"


@pytest.mark.asyncio
async def test_smart_money_429_rate_limit(smart_money_tool):
    patcher, _ = _patch_httpx_post(_mock_response({}, 429))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["status"] == 429
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_smart_money_timeout(smart_money_tool):
    import httpx
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.post.side_effect = httpx.TimeoutException("timeout")

    with patch("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", mock_cls), \
         patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert "timeout" in result["error"].lower()


@pytest.mark.asyncio
async def test_smart_money_uses_correct_base_url():
    """Must use api.nansen.ai/api/v1 (not /v1) and POST method."""
    import app.agents.new_chat.tools.nansen_smart_money as mod
    assert mod._NANSEN_BASE == "https://api.nansen.ai/api/v1"


@pytest.mark.asyncio
async def test_smart_money_uses_apikey_header():
    """Auth header must be 'apiKey', not 'x-api-key'."""
    import app.agents.new_chat.tools.nansen_smart_money as mod
    with patch.dict("os.environ", {"NANSEN_API_KEY": "nsn_testkey"}):
        headers = mod._auth_headers()
    assert "apiKey" in headers
    assert headers["apiKey"] == "nsn_testkey"
    assert "x-api-key" not in headers


# ── get_nansen_wallet_label ───────────────────────────────────────────────────

@pytest.fixture
def wallet_label_tool():
    return create_nansen_wallet_label_tool()


@pytest.mark.asyncio
async def test_wallet_label_known(wallet_label_tool):
    payload = {"data": {"label": "Vitalik.eth", "entityType": "Individual", "entityTag": "OG"}}
    patcher, _ = _patch_httpx_get(_mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await wallet_label_tool.ainvoke({"address": _VALID_WALLET})
    assert result["label"] == "Vitalik.eth"
    assert result["source_domain"] == "nansen.ai"
    assert "error" not in result


@pytest.mark.asyncio
async def test_wallet_label_unknown_404(wallet_label_tool):
    patcher, _ = _patch_httpx_get(_mock_response({}, 404))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await wallet_label_tool.ainvoke({"address": _VALID_WALLET})
    assert "error" not in result
    assert result["entity_type"] == "unknown"
    assert result["source_domain"] == "nansen.ai"


@pytest.mark.asyncio
async def test_wallet_label_missing_api_key(wallet_label_tool):
    with patch.dict("os.environ", {}, clear=True):
        result = await wallet_label_tool.ainvoke({"address": _VALID_WALLET})
    assert result["status"] == 401


# ── get_nansen_token_god_mode ─────────────────────────────────────────────────

@pytest.fixture
def god_mode_tool():
    return create_nansen_token_god_mode_tool()


@pytest.mark.asyncio
async def test_god_mode_success(god_mode_tool):
    payload = {
        "data": {
            "cohorts": [
                {"name": "Smart Money", "holderCount": 150, "balancePct": 12.5, "description": "Labeled smart money"},
                {"name": "Exchanges", "holderCount": 50, "balancePct": 30.0, "description": "CEX hot wallets"},
            ],
            "top10ConcentrationPct": 42.3,
            "totalHolders": 45000,
        }
    }
    patcher, _ = _patch_httpx_get(_mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await god_mode_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["top_10_concentration_pct"] == 42.3
    assert result["total_holders"] == 45000
    assert len(result["cohort_breakdown"]) == 2
    assert result["cohort_breakdown"][0]["cohort"] == "Smart Money"
    assert result["source_domain"] == "nansen.ai"
