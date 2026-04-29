"""Unit tests for contract analysis tools (Story 0-1)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.agents.new_chat.tools.contract_analysis import (
    create_contract_info_tool,
    create_check_token_security_tool,
)


def _mock_response(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        m.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return m


# ── get_contract_info ───────────────────────────────────────────────────────


@pytest.fixture
def contract_tool():
    return create_contract_info_tool()


_ABI = json.dumps([
    {"type": "function", "name": "transfer", "inputs": [], "outputs": []},
    {"type": "event", "name": "Transfer", "inputs": []},
    {"type": "constructor", "inputs": []},
])

_ETHERSCAN_PAYLOAD = {
    "status": "1",
    "message": "OK",
    "result": [{
        "SourceCode": "pragma solidity ^0.8.0; contract Token {}",
        "ABI": _ABI,
        "ContractName": "Token",
        "CompilerVersion": "v0.8.18",
        "OptimizationUsed": "1",
        "Runs": "200",
        "LicenseType": "MIT",
        "Implementation": "",
    }],
}


@pytest.mark.asyncio
async def test_contract_info_verified(contract_tool):
    with patch.dict("os.environ", {"ETHERSCAN_API_KEY": "testkey"}), \
         patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_ETHERSCAN_PAYLOAD)

        result = await contract_tool.ainvoke({
            "contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            "chain": "ethereum",
        })

    assert result["contract_name"] == "Token"
    assert result["is_verified"] is True
    assert result["optimization_used"] is True
    # ABI summary: 2 items (function + event, constructor excluded)
    assert len(result["abi_summary"]) == 2


@pytest.mark.asyncio
async def test_contract_info_unsupported_chain(contract_tool):
    result = await contract_tool.ainvoke({
        "contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
        "chain": "solana",
    })
    assert "error" in result
    assert "Unsupported chain" in result["error"]


@pytest.mark.asyncio
async def test_contract_info_missing_api_key(contract_tool):
    with patch.dict("os.environ", {}, clear=True):
        # Remove all env vars to ensure no key
        import os
        os.environ.pop("ETHERSCAN_API_KEY", None)
        result = await contract_tool.ainvoke({
            "contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            "chain": "ethereum",
        })
    assert "error" in result
    assert "Missing API key" in result["error"]


@pytest.mark.asyncio
async def test_contract_info_explorer_error(contract_tool):
    payload = {"status": "0", "message": "NOTOK", "result": "Invalid address format"}
    with patch.dict("os.environ", {"ETHERSCAN_API_KEY": "testkey"}), \
         patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(payload)

        result = await contract_tool.ainvoke({
            "contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            "chain": "ethereum",
        })

    assert "error" in result
    assert "Explorer API error" in result["error"]


@pytest.mark.asyncio
async def test_contract_info_bsc_chain(contract_tool):
    with patch.dict("os.environ", {"BSCSCAN_API_KEY": "bsckey"}), \
         patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_ETHERSCAN_PAYLOAD)

        result = await contract_tool.ainvoke({
            "contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            "chain": "bsc",
        })

    assert result["chain"] == "bsc"
    assert "error" not in result


# ── check_token_security ────────────────────────────────────────────────────


@pytest.fixture
def security_tool():
    return create_check_token_security_tool()


_SAFE_TOKEN_DATA = {
    "is_open_source": "1",
    "is_honeypot": "0",
    "is_mintable": "0",
    "is_proxy": "0",
    "can_take_back_ownership": "0",
    "buy_tax": "0.01",
    "sell_tax": "0.01",
    "holder_count": "1500",
    "creator_percent": "0.05",
    "top10_holder_percent": "0.25",
    "token_name": "SafeToken",
    "token_symbol": "SAFE",
    "total_supply": "1000000",
    "lp_holder_count": "10",
}

_HONEYPOT_TOKEN_DATA = {
    "is_open_source": "0",
    "is_honeypot": "1",
    "is_mintable": "1",
    "is_proxy": "0",
    "can_take_back_ownership": "0",
    "buy_tax": "0.05",
    "sell_tax": "0.80",
    "holder_count": "50",
    "creator_percent": "0.60",
    "token_name": "ScamToken",
    "token_symbol": "SCAM",
    "total_supply": "1000000000",
    "lp_holder_count": "1",
}


def _goplus_response(address, token_data):
    return {
        "code": 1,
        "message": "ok",
        "result": {address.lower(): token_data},
    }


@pytest.mark.asyncio
async def test_security_safe_token(security_tool):
    addr = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
    with patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_goplus_response(addr, _SAFE_TOKEN_DATA))

        result = await security_tool.ainvoke({"contract_address": addr, "chain_id": "1"})

    assert result["is_honeypot"] is False
    assert result["is_open_source"] is True
    assert result["risk_level"] == "SAFE"
    assert "🟢" in result["risks_detected"][0]


@pytest.mark.asyncio
async def test_security_honeypot_high_risk(security_tool):
    addr = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    with patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_goplus_response(addr, _HONEYPOT_TOKEN_DATA))

        result = await security_tool.ainvoke({"contract_address": addr, "chain_id": "56"})

    assert result["is_honeypot"] is True
    assert result["risk_level"] == "HIGH"
    honeypot_risk = [r for r in result["risks_detected"] if "HONEYPOT" in r]
    assert len(honeypot_risk) == 1


@pytest.mark.asyncio
async def test_security_chain_name_normalized(security_tool):
    """Chain name 'ethereum' should resolve to '1'."""
    addr = "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"
    with patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response(_goplus_response(addr, _SAFE_TOKEN_DATA))

        result = await security_tool.ainvoke({"contract_address": addr, "chain_id": "ethereum"})

    # Should use numeric chain ID in URL → no error
    assert "error" not in result
    call_url = mock_client.get.call_args[0][0]
    assert "/1" in call_url


@pytest.mark.asyncio
async def test_security_429_returns_error(security_tool):
    with patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({}, status_code=429)

        result = await security_tool.ainvoke({"contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", "chain_id": "1"})

    assert "error" in result
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_security_goplus_api_error(security_tool):
    with patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({"code": 0, "message": "Chain not supported"})

        result = await security_tool.ainvoke({"contract_address": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984", "chain_id": "999"})

    assert "error" in result


@pytest.mark.asyncio
async def test_security_no_token_data(security_tool):
    """Address not found in GoPlus result map."""
    with patch("app.agents.new_chat.tools.contract_analysis.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = _mock_response({"code": 1, "result": {}})

        result = await security_tool.ainvoke({"contract_address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "chain_id": "1"})

    assert "error" in result
    assert "No GoPlus data" in result["error"]
