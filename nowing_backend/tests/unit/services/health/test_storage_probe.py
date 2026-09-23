"""Unit tests for StorageHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health.probes.storage_probe import StorageHealthProbe


@pytest.mark.asyncio
async def test_storage_probe_not_configured() -> None:
    probe = StorageHealthProbe(provider="s3")
    assert probe.service_id == "storage/s3"
    assert probe.category == "storage"

    with patch.object(probe, "_read_credentials", return_value={
        "endpoint": None,
        "bucket": None,
        "access_key": None,
        "secret_key": None,
        "region": "us-east-1",
    }):
        result = await probe.probe()
        assert result.status == "not_configured"
        assert "credentials" in (result.suggested_action or "").lower()
        assert result.metadata["configured"] is False


@pytest.mark.asyncio
async def test_storage_probe_healthy_with_default_aws_endpoint() -> None:
    probe = StorageHealthProbe(provider="s3")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch.object(probe, "_read_credentials", return_value={
        "endpoint": "https://test-bucket.s3.us-east-1.amazonaws.com",
        "bucket": "test-bucket",
        "access_key": "AKIAIOSFODNN7EXAMPLE",
        "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1",
    }), \
         patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "healthy"
        assert result.metadata["configured"] is True
        assert result.metadata["bucket"] == "test-bucket"
        assert result.metadata["endpoint"] == "https://test-bucket.s3.us-east-1.amazonaws.com"


@pytest.mark.asyncio
async def test_storage_probe_degraded_on_403() -> None:
    probe = StorageHealthProbe(provider="s3")

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch.object(probe, "_read_credentials", return_value={
        "endpoint": "https://minio.example.com",
        "bucket": "test-bucket",
        "access_key": "minioadmin",
        "secret_key": "minioadmin",
        "region": "us-east-1",
    }), \
         patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "degraded"
        assert "credentials rejected" in (result.last_error or "").lower()


@pytest.mark.asyncio
async def test_storage_probe_unavailable_on_500() -> None:
    probe = StorageHealthProbe(provider="s3")

    mock_resp = MagicMock()
    mock_resp.status_code = 503

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch.object(probe, "_read_credentials", return_value={
        "endpoint": "https://s3.us-east-1.amazonaws.com",
        "bucket": "test-bucket",
        "access_key": "AKIAIOSFODNN7EXAMPLE",
        "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1",
    }), \
         patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "unavailable"
        assert "503" in (result.last_error or "")
