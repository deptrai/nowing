"""Unit tests for ConnectorHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health.probes.connector_probe import ConnectorHealthProbe


@pytest.mark.asyncio
async def test_connector_probe_not_configured() -> None:
    probe = ConnectorHealthProbe(
        connector_type="google_drive",
        service_name="Google Drive",
        display_group="Google Workspace",
    )
    assert probe.service_id == "connector/google_drive"
    assert probe.category == "connector"

    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = 0
    mock_session.execute.return_value = mock_res

    with patch("app.services.health.probes.connector_probe.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__.return_value = mock_session

        result = await probe.probe()
        assert result.service_id == "connector/google_drive"
        assert result.status == "not_configured"
        assert result.metadata["active_accounts"] == 0


@pytest.mark.asyncio
async def test_connector_probe_healthy_when_active_accounts() -> None:
    probe = ConnectorHealthProbe(
        connector_type="google_drive",
        service_name="Google Drive",
    )

    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_res.scalar.return_value = 3
    mock_session.execute.return_value = mock_res

    with patch("app.services.health.probes.connector_probe.async_session_maker") as mock_maker, \
         patch("app.services.health.probes.connector_probe.httpx.AsyncClient") as mock_client_cls:
        mock_maker.return_value.__aenter__.return_value = mock_session

        mock_client = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await probe.probe()
        assert result.status == "healthy"
        assert result.metadata["active_accounts"] == 3
