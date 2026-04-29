"""Unit tests for Dune Analytics query tool (Story 9-UX-4 AC3, T8)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.new_chat.tools.dune_query import (
    create_run_dune_query_tool,
    list_available_dune_queries,
    _QUERY_REGISTRY,
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


@pytest.fixture
def run_query_tool():
    return create_run_dune_query_tool()


# ── Query registry ────────────────────────────────────────────────────────────


def test_query_registry_loaded():
    """All 4 pre-registered queries should be loaded at import."""
    assert len(_QUERY_REGISTRY) == 4
    assert 12345 in _QUERY_REGISTRY  # uniswap-dex-volume
    assert 12346 in _QUERY_REGISTRY  # lido-staking-flows
    assert 12347 in _QUERY_REGISTRY  # whale-concentration
    assert 12348 in _QUERY_REGISTRY  # nft-collection-floor


def test_query_registry_schema():
    """Each registry entry should have required fields."""
    for qid, meta in _QUERY_REGISTRY.items():
        assert "query_id" in meta, f"query {qid} missing query_id"
        assert "name" in meta, f"query {qid} missing name"
        assert "description" in meta, f"query {qid} missing description"
        assert "dune_url" in meta, f"query {qid} missing dune_url"
        assert str(qid) in meta["dune_url"], f"query {qid} dune_url doesn't contain query_id"


def test_list_available_dune_queries():
    queries = list_available_dune_queries()
    assert len(queries) == 4
    ids = [q["query_id"] for q in queries]
    assert 12347 in ids  # whale-concentration


# ── run_dune_query — success flow ─────────────────────────────────────────────


def _build_dune_mock_client(execute_resp, status_resp, results_resp):
    """Build an AsyncMock client that returns execute → status → results sequence."""
    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_client.post.return_value = execute_resp
    mock_client.get.side_effect = [status_resp, results_resp]
    return mock_cls


@pytest.mark.asyncio
async def test_run_query_success(run_query_tool):
    exec_payload = {"execution_id": "exec-abc-123"}
    status_payload = {"state": "QUERY_STATE_COMPLETED"}
    results_payload = {
        "result": {
            "rows": [
                {"pool_address": "0xabc", "volume_24h_usd": 1_000_000},
                {"pool_address": "0xdef", "volume_24h_usd": 500_000},
            ],
            "metadata": {"column_names": [{"name": "pool_address"}, {"name": "volume_24h_usd"}]},
        }
    }
    mock_cls = _build_dune_mock_client(
        _mock_response(exec_payload),
        _mock_response(status_payload),
        _mock_response(results_payload),
    )
    with patch("app.agents.new_chat.tools.dune_query.httpx.AsyncClient", mock_cls), \
         patch("app.agents.new_chat.tools.dune_query.asyncio.sleep", AsyncMock()), \
         patch.dict("os.environ", {"DUNE_API_KEY": "test-key"}):
        result = await run_query_tool.ainvoke({
            "query_id": 12345,
            "params": {"pool_address": "0xabc"},
        })

    assert result["source_domain"] == "dune.com"
    assert result["query_id"] == 12345
    assert result["query_name"] == _QUERY_REGISTRY[12345]["name"]
    assert result["row_count"] == 2
    assert result["dune_url"] == "https://dune.com/queries/12345"
    assert "error" not in result


@pytest.mark.asyncio
async def test_run_query_unregistered_id(run_query_tool):
    with patch.dict("os.environ", {"DUNE_API_KEY": "test-key"}):
        result = await run_query_tool.ainvoke({"query_id": 99999})
    assert "error" in result
    assert "99999" in result["error"]
    assert result["source_domain"] == "dune.com"


@pytest.mark.asyncio
async def test_run_query_missing_api_key(run_query_tool):
    with patch.dict("os.environ", {}, clear=True):
        result = await run_query_tool.ainvoke({"query_id": 12345})
    assert result["status"] == 401


@pytest.mark.asyncio
async def test_run_query_dune_failed_state(run_query_tool):
    exec_payload = {"execution_id": "exec-fail"}
    status_payload = {"state": "QUERY_STATE_FAILED"}
    results_payload = {}

    mock_cls = _build_dune_mock_client(
        _mock_response(exec_payload),
        _mock_response(status_payload),
        _mock_response(results_payload),
    )
    with patch("app.agents.new_chat.tools.dune_query.httpx.AsyncClient", mock_cls), \
         patch("app.agents.new_chat.tools.dune_query.asyncio.sleep", AsyncMock()), \
         patch.dict("os.environ", {"DUNE_API_KEY": "test-key"}):
        result = await run_query_tool.ainvoke({"query_id": 12345})
    assert "error" in result
    assert "FAILED" in result["error"]


@pytest.mark.asyncio
async def test_run_query_timeout_polling(run_query_tool):
    """When query never completes within polling budget, return timeout error."""
    exec_payload = {"execution_id": "exec-slow"}
    status_payload = {"state": "QUERY_STATE_PENDING"}  # never completes

    mock_cls = MagicMock()
    mock_client = AsyncMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_client.post.return_value = _mock_response(exec_payload)
    mock_client.get.return_value = _mock_response(status_payload)  # always pending

    with patch("app.agents.new_chat.tools.dune_query.httpx.AsyncClient", mock_cls), \
         patch("app.agents.new_chat.tools.dune_query.asyncio.sleep", AsyncMock()), \
         patch.dict("os.environ", {"DUNE_API_KEY": "test-key"}):
        result = await run_query_tool.ainvoke({"query_id": 12345})
    assert "error" in result
    assert "timed out" in result["error"].lower()
