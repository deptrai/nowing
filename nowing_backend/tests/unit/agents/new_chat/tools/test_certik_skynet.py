"""Unit tests for CertiK Skynet tools (Story 9-UX-4 AC2, T8)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.new_chat.tools.certik_skynet import (
    create_certik_audit_score_tool,
    create_certik_incident_history_tool,
)

_VALID_TOKEN = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"  # UNI


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


def _patch_httpx(response):
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = response
    return patch("app.agents.new_chat.tools.certik_skynet.httpx.AsyncClient", mock_cls)


# ── get_certik_audit_score ────────────────────────────────────────────────────


@pytest.fixture
def audit_score_tool():
    return create_certik_audit_score_tool()


_CERTIK_LEADERBOARD_PAYLOAD = {
    "data": {
        "rows": [{
            "name": "Uniswap",
            "slug": "uniswap",
            "securityScore": 92,
            "codeScore": 95,
            "marketScore": 88,
            "governanceScore": 90,
            "communityScore": 91,
            "audits": [
                {"auditor": "Trail of Bits"},
                {"auditor": "ABDK"},
            ],
        }]
    }
}


@pytest.mark.asyncio
async def test_audit_score_success(audit_score_tool):
    with _patch_httpx(_mock_response(_CERTIK_LEADERBOARD_PAYLOAD)):
        result = await audit_score_tool.ainvoke({"token_address": _VALID_TOKEN, "chain": "ethereum"})
    assert result["overall_score"] == 92
    assert result["audit_count"] == 2
    assert "Trail of Bits" in result["audited_by"]
    assert result["source_domain"] == "certik.com"
    assert "error" not in result


@pytest.mark.asyncio
async def test_audit_score_categories(audit_score_tool):
    with _patch_httpx(_mock_response(_CERTIK_LEADERBOARD_PAYLOAD)):
        result = await audit_score_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["categories"]["code"] == 95
    assert result["categories"]["market"] == 88
    assert result["categories"]["governance"] == 90
    assert result["categories"]["community"] == 91


@pytest.mark.asyncio
async def test_audit_score_no_results(audit_score_tool):
    empty = {"data": {"rows": []}}
    with _patch_httpx(_mock_response(empty)):
        result = await audit_score_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert "error" in result
    assert result["source_domain"] == "certik.com"


@pytest.mark.asyncio
async def test_audit_score_invalid_address(audit_score_tool):
    result = await audit_score_tool.ainvoke({"token_address": "bad-address"})
    assert "error" in result
    assert result["source_domain"] == "certik.com"


@pytest.mark.asyncio
async def test_audit_score_429(audit_score_tool):
    with _patch_httpx(_mock_response({}, 429)):
        result = await audit_score_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert result["status"] == 429
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_audit_score_timeout(audit_score_tool):
    import httpx
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.side_effect = httpx.TimeoutException("timeout")

    with patch("app.agents.new_chat.tools.certik_skynet.httpx.AsyncClient", mock_cls):
        result = await audit_score_tool.ainvoke({"token_address": _VALID_TOKEN})
    assert "timeout" in result["error"].lower()


# ── get_certik_incident_history ───────────────────────────────────────────────


@pytest.fixture
def incident_tool():
    return create_certik_incident_history_tool()


_INCIDENT_PAYLOAD = {
    "data": {
        "rows": [
            {
                "date": "2023-07-31",
                "incidentType": "Price Manipulation",
                "amountLostUsd": 73000000,
                "description": "Flash loan attack via price oracle manipulation",
                "projectName": "curve",
                "txHash": "0xabc123",
                "slug": "curve-hack-2023",
            }
        ]
    }
}


@pytest.mark.asyncio
async def test_incident_history_success(incident_tool):
    with _patch_httpx(_mock_response(_INCIDENT_PAYLOAD)):
        result = await incident_tool.ainvoke({"project_name": "curve"})
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["type"] == "Price Manipulation"
    assert result[0]["amount_lost_usd"] == 73_000_000
    assert result[0]["source_domain"] == "certik.com"


@pytest.mark.asyncio
async def test_incident_history_no_incidents(incident_tool):
    with _patch_httpx(_mock_response({}, 404)):
        result = await incident_tool.ainvoke({"project_name": "unknown-project"})
    assert result == []


@pytest.mark.asyncio
async def test_incident_history_empty_name(incident_tool):
    result = await incident_tool.ainvoke({"project_name": ""})
    assert isinstance(result, list)
    assert result[0]["source_domain"] == "certik.com"
    assert "error" in result[0]


@pytest.mark.asyncio
async def test_incident_history_429(incident_tool):
    with _patch_httpx(_mock_response({}, 429)):
        result = await incident_tool.ainvoke({"project_name": "curve"})
    assert result[0]["status"] == 429
