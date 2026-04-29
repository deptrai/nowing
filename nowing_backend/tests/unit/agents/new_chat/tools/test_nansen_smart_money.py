"""Unit tests for Nansen smart money tools (Story 9-UX-4 AC1, T8)."""

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


# ── helpers ──────────────────────────────────────────────────────────────────

def _patch_httpx(module_path: str, response):
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = response
    return patch(module_path, mock_cls), mock_client


# ── get_nansen_smart_money ────────────────────────────────────────────────────


@pytest.fixture
def smart_money_tool():
    return create_nansen_smart_money_tool()


@pytest.mark.asyncio
async def test_smart_money_success(smart_money_tool):
    payload = {
        "data": {
            "wallets": [
                {"address": _VALID_WALLET, "label": "Vitalik.eth", "entityTag": "Individual", "netFlowUsd": 50000},
                {"address": "0xabc123" + "a" * 34, "label": "Jump Trading", "entityTag": "Market Maker", "netFlowUsd": -200000},
            ],
            "netFlow24hUsd": -150000.0,
        }
    }
    patcher, _ = _patch_httpx("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", _mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})

    assert result["source_domain"] == "nansen.ai"
    assert result["signal"] == "distributing"
    assert result["net_flow_24h_usd"] == -150000.0
    assert len(result["smart_money_wallets"]) == 2
    assert "error" not in result


@pytest.mark.asyncio
async def test_smart_money_accumulating_signal(smart_money_tool):
    payload = {"data": {"wallets": [], "netFlow24hUsd": 1_000_000.0}}
    patcher, _ = _patch_httpx("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", _mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["signal"] == "accumulating"


@pytest.mark.asyncio
async def test_smart_money_missing_api_key(smart_money_tool):
    with patch.dict("os.environ", {}, clear=True):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["error"] is not None
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
    patcher, _ = _patch_httpx("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", _mock_response({}, 401))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["status"] == 401
    assert result["source_domain"] == "nansen.ai"


@pytest.mark.asyncio
async def test_smart_money_429_rate_limit(smart_money_tool):
    patcher, _ = _patch_httpx("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", _mock_response({}, 429))
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
    mock_client.get.side_effect = httpx.TimeoutException("timeout")

    with patch("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", mock_cls), \
         patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await smart_money_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert "timeout" in result["error"].lower()


# ── get_nansen_wallet_label ───────────────────────────────────────────────────


@pytest.fixture
def wallet_label_tool():
    return create_nansen_wallet_label_tool()


@pytest.mark.asyncio
async def test_wallet_label_known(wallet_label_tool):
    payload = {"data": {"label": "Vitalik.eth", "entityType": "Individual", "entityTag": "OG"}}
    patcher, _ = _patch_httpx("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", _mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await wallet_label_tool.ainvoke({"address": _VALID_WALLET})
    assert result["label"] == "Vitalik.eth"
    assert result["source_domain"] == "nansen.ai"
    assert "error" not in result


@pytest.mark.asyncio
async def test_wallet_label_unknown_404(wallet_label_tool):
    patcher, _ = _patch_httpx("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", _mock_response({}, 404))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await wallet_label_tool.ainvoke({"address": _VALID_WALLET})
    # 404 returns short address, not error
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
    patcher, _ = _patch_httpx("app.agents.new_chat.tools.nansen_smart_money.httpx.AsyncClient", _mock_response(payload))
    with patcher, patch.dict("os.environ", {"NANSEN_API_KEY": "test-key"}):
        result = await god_mode_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["top_10_concentration_pct"] == 42.3
    assert result["total_holders"] == 45000
    assert len(result["cohort_breakdown"]) == 2
    assert result["cohort_breakdown"][0]["cohort"] == "Smart Money"
    assert result["source_domain"] == "nansen.ai"
