"""Unit tests for TokenInsight rating tools (Story 9-UX-4 AC4, T8)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.new_chat.tools.tokeninsight_rating import (
    create_tokeninsight_rating_tool,
    create_tokeninsight_research_snippet_tool,
)


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
    return patch("app.agents.new_chat.tools.tokeninsight_rating.httpx.AsyncClient", mock_cls)


# ── get_tokeninsight_rating ───────────────────────────────────────────────────


@pytest.fixture
def rating_tool():
    return create_tokeninsight_rating_tool()


_RATING_PAYLOAD = {
    "data": {
        "rating": "A",
        "score": 93,
        "technologyScore": 95,
        "teamScore": 90,
        "ecosystemScore": 94,
        "tokenomicsScore": 88,
        "updatedAt": "2026-04-01",
    }
}


@pytest.mark.asyncio
async def test_rating_success(rating_tool):
    with _patch_httpx(_mock_response(_RATING_PAYLOAD)):
        result = await rating_tool.ainvoke({"token_symbol": "ETH"})
    assert result["overall_rating"] == "A"
    assert result["overall_score"] == 93
    assert result["categories"]["technology"] == 95
    assert result["symbol"] == "ETH"
    assert result["source_domain"] == "tokeninsight.com"
    assert "error" not in result


@pytest.mark.asyncio
async def test_rating_symbol_normalized(rating_tool):
    """Symbol should be uppercased regardless of input case."""
    with _patch_httpx(_mock_response(_RATING_PAYLOAD)):
        result = await rating_tool.ainvoke({"token_symbol": "eth"})
    assert result["symbol"] == "ETH"


@pytest.mark.asyncio
async def test_rating_404_not_found(rating_tool):
    with _patch_httpx(_mock_response({}, 404)):
        result = await rating_tool.ainvoke({"token_symbol": "UNKNOWNCOIN999"})
    assert result["status"] == 404
    assert result["source_domain"] == "tokeninsight.com"


@pytest.mark.asyncio
async def test_rating_empty_symbol(rating_tool):
    result = await rating_tool.ainvoke({"token_symbol": ""})
    assert "error" in result


@pytest.mark.asyncio
async def test_rating_429(rating_tool):
    with _patch_httpx(_mock_response({}, 429)):
        result = await rating_tool.ainvoke({"token_symbol": "BTC"})
    assert result["status"] == 429
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_rating_partial_categories(rating_tool):
    """Categories with None values should be excluded from output."""
    payload = {"data": {"rating": "B", "score": 75}}  # no category scores
    with _patch_httpx(_mock_response(payload)):
        result = await rating_tool.ainvoke({"token_symbol": "UNI"})
    assert result["categories"] == {}


# ── get_tokeninsight_research_snippet ─────────────────────────────────────────


@pytest.fixture
def snippet_tool():
    return create_tokeninsight_research_snippet_tool()


_SNIPPET_PAYLOAD = {
    "data": {
        "title": "Ethereum Q1 2026 Research Update",
        "content": "Ethereum continues to dominate smart contract platforms with 65% DApp market share. " * 10,
        "publishedAt": "2026-04-01",
        "url": "https://tokeninsight.com/en/research/ethereum-q1-2026",
    }
}


@pytest.mark.asyncio
async def test_snippet_success(snippet_tool):
    with _patch_httpx(_mock_response(_SNIPPET_PAYLOAD)), \
         patch.dict("os.environ", {"TOKENINSIGHT_API_KEY": "test-key"}):
        result = await snippet_tool.ainvoke({"token_symbol": "ETH"})
    assert result["source_domain"] == "tokeninsight.com"
    assert len(result["excerpt"]) <= 503  # 500 + "..."
    assert result["excerpt"].endswith("...")
    assert "error" not in result


@pytest.mark.asyncio
async def test_snippet_requires_api_key(snippet_tool):
    """Research snippets require TOKENINSIGHT_API_KEY (paid tier)."""
    with patch.dict("os.environ", {}, clear=True):
        result = await snippet_tool.ainvoke({"token_symbol": "ETH"})
    assert result["status"] == 401


@pytest.mark.asyncio
async def test_snippet_short_content_no_ellipsis(snippet_tool):
    """Content shorter than 500 chars should NOT get '...' appended."""
    payload = {"data": {"content": "Short note.", "publishedAt": "2026-04-01"}}
    with _patch_httpx(_mock_response(payload)), \
         patch.dict("os.environ", {"TOKENINSIGHT_API_KEY": "test-key"}):
        result = await snippet_tool.ainvoke({"token_symbol": "ETH"})
    assert result["excerpt"] == "Short note."


@pytest.mark.asyncio
async def test_snippet_timeout(snippet_tool):
    import httpx
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.side_effect = httpx.TimeoutException("timeout")

    with patch("app.agents.new_chat.tools.tokeninsight_rating.httpx.AsyncClient", mock_cls), \
         patch.dict("os.environ", {"TOKENINSIGHT_API_KEY": "test-key"}):
        result = await snippet_tool.ainvoke({"token_symbol": "ETH"})
    assert "timeout" in result["error"].lower()
