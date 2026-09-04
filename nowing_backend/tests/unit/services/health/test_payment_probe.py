"""Unit tests for PaymentHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health.probes.payment_probe import PaymentHealthProbe


@pytest.mark.asyncio
async def test_payment_probe_not_configured() -> None:
    probe = PaymentHealthProbe(provider="stripe")
    assert probe.service_id == "payment/stripe"
    assert probe.category == "payment"

    with patch("app.config.config.STRIPE_SECRET_KEY", None):
        result = await probe.probe()
        assert result.status == "not_configured"
        assert "STRIPE_SECRET_KEY" in (result.suggested_action or "")


@pytest.mark.asyncio
async def test_payment_probe_healthy() -> None:
    probe = PaymentHealthProbe(provider="stripe")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.config.config.STRIPE_SECRET_KEY", "sk_test_12345"), \
         patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "healthy"


@pytest.mark.asyncio
async def test_payment_probe_degraded_on_401() -> None:
    probe = PaymentHealthProbe(provider="stripe")

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.config.config.STRIPE_SECRET_KEY", "sk_test_12345"), \
         patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "degraded"
        assert "rejected" in (result.last_error or "").lower()


@pytest.mark.asyncio
async def test_payment_probe_unavailable_on_500() -> None:
    probe = PaymentHealthProbe(provider="stripe")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.config.config.STRIPE_SECRET_KEY", "sk_test_12345"), \
         patch("httpx.AsyncClient", return_value=mock_client) as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await probe.probe()
        assert result.status == "unavailable"
        assert "500" in (result.last_error or "")


@pytest.mark.asyncio
async def test_payment_probe_unsupported_provider() -> None:
    probe = PaymentHealthProbe(provider="paypal")
    result = await probe.probe()
    assert result.status == "not_configured"
    assert "paypal" in (result.suggested_action or "").lower()
