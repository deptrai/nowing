"""Unit tests for ModelHealthProbe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.health.probes.model_probe import ModelHealthProbe


@pytest.mark.asyncio
async def test_model_probe_healthy() -> None:
    probe = ModelHealthProbe(
        service_id="model/test-chat",
        service_name="Test Chat",
        provider="openai",
        model_id="gpt-4o",
    )

    mock_res = MagicMock()
    mock_res.verified = True
    mock_res.message = "OK"

    with patch("app.services.health.probes.model_probe.verify_connection", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = mock_res

        result = await probe.probe()
        assert result.service_id == "model/test-chat"
        assert result.status == "healthy"
        assert result.error_rate_15m == 0.0
        assert result.success_rate_15m == 100.0
        assert result.last_error is None


@pytest.mark.asyncio
async def test_model_probe_degraded_on_rate_limit() -> None:
    probe = ModelHealthProbe(
        service_id="model/test-chat",
        service_name="Test Chat",
        provider="openai",
        model_id="gpt-4o",
    )

    mock_res = MagicMock()
    mock_res.verified = False
    mock_res.code = "RATE_LIMITED"
    mock_res.message = "Rate limit exceeded"

    with patch("app.services.health.probes.model_probe.verify_connection", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = mock_res

        result = await probe.probe()
        assert result.status == "degraded"
        assert "Rate limit" in (result.last_error or "")


@pytest.mark.asyncio
async def test_model_probe_unavailable_on_failure() -> None:
    probe = ModelHealthProbe(
        service_id="model/test-chat",
        service_name="Test Chat",
        provider="openai",
        model_id="gpt-4o",
    )

    mock_res = MagicMock()
    mock_res.verified = False
    mock_res.code = "SERVER_ERROR"
    mock_res.message = "Bearer secret_token_123 failed"

    with patch("app.services.health.probes.model_probe.verify_connection", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = mock_res

        result = await probe.probe()
        assert result.status == "unavailable"
        assert "secret_token_123" not in (result.last_error or "")
        assert result.error_rate_15m == 100.0


@pytest.mark.asyncio
async def test_model_probe_not_configured_on_auth_failed() -> None:
    probe = ModelHealthProbe(
        service_id="model/test-chat",
        service_name="Test Chat",
        provider="openai",
        model_id="gpt-4o",
    )

    mock_res = MagicMock()
    mock_res.verified = False
    mock_res.code = "AUTH_FAILED"
    mock_res.message = "Missing API key"

    with patch("app.services.health.probes.model_probe.verify_connection", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = mock_res

        result = await probe.probe()
        assert result.status == "not_configured"


@pytest.mark.asyncio
async def test_model_probe_vllm_fallback() -> None:
    probe = ModelHealthProbe(
        service_id="local/vllm",
        service_name="Local vLLM",
        provider="vllm",
        model_id="qwen",
    )

    with patch("app.services.hybrid_llm_router.HybridLLMRouter._vllm_health", new_callable=AsyncMock) as mock_vllm:
        mock_vllm.return_value = True

        result = await probe.probe()
        assert result.status == "healthy"
