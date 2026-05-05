"""Tests for smart money flow tool fallbacks to Arkham and Dune."""

import os
from unittest.mock import AsyncMock

import pytest

from app.agents.new_chat.tools.crypto_smart_money_flow import create_smart_money_flow_tool


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for testing fallbacks."""
    monkeypatch.setenv("NANSEN_API_KEY", "test-nansen-key")
    monkeypatch.setenv("ARKHAM_API_KEY", "test-arkham-key")
    monkeypatch.setenv("DUNE_API_KEY", "test-dune-key")
    return monkeypatch


@pytest.fixture
def mock_nansen(mocker):
    """Mock the underlying Nansen tool."""
    mock_tool = mocker.MagicMock()
    mock_tool.ainvoke = AsyncMock(return_value={"smart_money_wallets": [], "source_domain": "nansen.ai"})
    mock_factory = mocker.patch("app.agents.new_chat.tools.crypto_smart_money_flow.create_nansen_smart_money_tool")
    mock_factory.return_value = mock_tool
    return mock_tool


@pytest.fixture
def tool(mock_env, mock_nansen):
    """Create the smart money flow tool with mocked dependencies."""
    return create_smart_money_flow_tool()


@pytest.mark.asyncio
async def test_nansen_empty_triggers_arkham_fallback(tool, mocker):
    """Test that empty Nansen result falls back to Arkham."""
    # Mock Arkham connector
    mock_try_arkham = mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_arkham",
        new_callable=AsyncMock
    )
    mock_try_arkham.return_value = {
        "in": [
            {
                "fromAddress": {"address": "0x123", "arkhamEntity": {"name": "Test Fund"}},
                "token": {"usdAmount": "5000"}
            }
        ]
    }

    result = await tool.ainvoke({"token_address": "0x1234567890123456789012345678901234567890"})

    assert mock_try_arkham.called
    assert result["source_domain"] == "arkm.com"
    # Label is disambiguated with addr suffix to prevent Sankey node collision.
    # Cohort defaults to "unknown" because the test fixture entity has no `type` field.
    expected_label = "Test Fund (0x123)"
    assert result["nodes"] == [
        {"id": "Market"},
        {"id": expected_label, "cohort": "unknown"},
    ]
    assert result["links"] == [{"source": expected_label, "target": "Market", "value": 5000.0}]
    # Cohort summary aggregates wallets by category (Story 10.1.4 AC3)
    assert result["cohort_summary"] == {"unknown": {"count": 1, "net_flow_usd": -5000.0}}


@pytest.mark.asyncio
async def test_arkham_unavailable_triggers_dune_fallback(tool, mocker):
    """Test that Arkham failure falls back to Dune."""
    # Mock Arkham to return None
    mock_try_arkham = mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_arkham",
        new_callable=AsyncMock,
        return_value=None
    )

    # Mock Dune connector
    mock_try_dune = mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_dune",
        new_callable=AsyncMock
    )
    mock_try_dune.return_value = [
        {"address": "0xabc", "label": "Dune Whale", "net_flow_usd": 10000.0, "tx_count": 5}
    ]

    result = await tool.ainvoke({"token_address": "0x1234567890123456789012345678901234567890"})

    assert mock_try_arkham.called
    assert mock_try_dune.called
    assert result["source_domain"] == "dune.com"
    assert len(result["nodes"]) == 2
    # Net buyer (positive net_flow_usd): Market -> Wallet (label disambiguated with addr)
    assert result["links"][0]["source"] == "Market"
    assert result["links"][0]["target"] == "Dune Whale (0xabc)"
    assert result["links"][0]["value"] == 10000.0


@pytest.mark.asyncio
async def test_all_providers_fail_returns_empty_sankey(tool, mocker):
    """Test that when all fail, it returns an empty sankey."""
    mocker.patch("app.agents.new_chat.tools.crypto_smart_money_flow._try_arkham", new_callable=AsyncMock, return_value=None)
    mocker.patch("app.agents.new_chat.tools.crypto_smart_money_flow._try_dune", new_callable=AsyncMock, return_value=None)

    result = await tool.ainvoke({"token_address": "0x1234567890123456789012345678901234567890"})

    assert result["source_domain"] == "nansen.ai"
    assert result["nodes"] == [{"id": "Market"}]
    assert result["links"] == []


@pytest.mark.asyncio
async def test_arkham_source_domain_set_correctly(tool, mocker):
    """Spec AC8: Arkham-served data must carry source_domain='arkm.com'."""
    mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_arkham",
        new_callable=AsyncMock,
        return_value={
            "in": [
                {
                    "fromAddress": {
                        "address": "0xabc",
                        "arkhamEntity": {"name": "Whale Fund", "type": "fund"},
                    },
                    "token": {"usdAmount": "12345"},
                }
            ]
        },
    )

    result = await tool.ainvoke({"token_address": "0x1234567890123456789012345678901234567890"})

    assert result["source_domain"] == "arkm.com"


@pytest.mark.asyncio
async def test_dune_source_domain_set_correctly(tool, mocker):
    """Spec AC8: Dune-served data must carry source_domain='dune.com'."""
    mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_arkham",
        new_callable=AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_dune",
        new_callable=AsyncMock,
        return_value=[
            {"address": "0xdef", "label": "Dune Whale", "net_flow_usd": 7777.0, "tx_count": 3}
        ],
    )

    result = await tool.ainvoke({"token_address": "0x1234567890123456789012345678901234567890"})

    assert result["source_domain"] == "dune.com"


@pytest.mark.asyncio
async def test_arkham_entity_type_filter_drops_cex(tool, mocker):
    """Spec mitigation: CEX/exchange flows should be filtered out of smart-money view."""
    mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_arkham",
        new_callable=AsyncMock,
        return_value={
            "in": [
                {
                    "fromAddress": {
                        "address": "0xcex",
                        "arkhamEntity": {"name": "Binance", "type": "cex"},
                    },
                    "token": {"usdAmount": "999999"},
                },
                {
                    "fromAddress": {
                        "address": "0xfund",
                        "arkhamEntity": {"name": "Test Fund", "type": "fund"},
                    },
                    "token": {"usdAmount": "5000"},
                },
            ]
        },
    )

    result = await tool.ainvoke({"token_address": "0x1234567890123456789012345678901234567890"})

    # CEX entity dropped; only fund-type wallet should appear (with disambiguating addr suffix)
    assert result["source_domain"] == "arkm.com"
    labels = [n["id"] for n in result["nodes"]]
    assert any("Test Fund" in lbl for lbl in labels)
    assert not any("Binance" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_arkham_label_disambiguation_prevents_collision(tool, mocker):
    """Two transfers from the same entity name must produce distinct Sankey nodes."""
    mocker.patch(
        "app.agents.new_chat.tools.crypto_smart_money_flow._try_arkham",
        new_callable=AsyncMock,
        return_value={
            "in": [
                {
                    "fromAddress": {
                        "address": "0xaaaa1111",
                        "arkhamEntity": {"name": "Whale", "type": "whale"},
                    },
                    "token": {"usdAmount": "1000"},
                },
                {
                    "fromAddress": {
                        "address": "0xbbbb2222",
                        "arkhamEntity": {"name": "Whale", "type": "whale"},
                    },
                    "token": {"usdAmount": "2000"},
                },
            ]
        },
    )

    result = await tool.ainvoke({"token_address": "0x1234567890123456789012345678901234567890"})

    # Both wallets share entity name "Whale" but live at different addresses → must be distinct nodes
    wallet_nodes = [n["id"] for n in result["nodes"] if n["id"] != "Market"]
    assert len(wallet_nodes) == 2, f"expected 2 distinct wallet nodes, got {wallet_nodes}"
